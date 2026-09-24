"""Results store: each hypothesis's latest run and the hypothesis registry as Parquet.

The presentation layer (q7, ADR-0008) reads these files and nothing else, so
every number is computed before it gets here; this module lays the numbers out
as tables and computes nothing but the monthly returns and drawdowns the
tear-sheet also shows, and the registry status from the recorded gates. The
schema is the contract with the .NET API: renaming a column or changing its
type raises SCHEMA_VERSION. Schema: docs/specs/q7-dotnet-react-presentation/02-spec.md.
"""

import json
import math
import shutil
from datetime import date, datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import BaseModel, model_validator

from quantlab.attribution.trade_ledger import PnlGroup, Trade
from quantlab.reporting.cost_comparison import CostSensitivity
from quantlab.reporting.metrics import drawdown_series, monthly_returns
from quantlab.reporting.tear_sheet import TearSheet
from quantlab.research.definition import TrainingDiagnostic
from quantlab.research.hypothesis import Status, concluded_status
from quantlab.research.trials import registered_trials, trials_on_same_data
from quantlab.risk.regime import VOLATILITY_REGIMES
from quantlab.validation.holdout import HoldoutRecord, holdout_passed, read_holdout_record

SCHEMA_VERSION = 1
REGISTRY_FILE = "hypotheses.parquet"
RUN_FILE = "run.parquet"

_DATE = pa.date32()
_TIMESTAMP = pa.timestamp("us", tz="UTC")


def _field(name: str, kind: pa.DataType, nullable: bool = False) -> pa.Field:
    return pa.field(name, kind, nullable=nullable)


def _optional(name: str, kind: pa.DataType) -> pa.Field:
    return pa.field(name, kind, nullable=True)


REGISTRY_SCHEMA = pa.schema(
    [
        _field("schema_version", pa.int64()),
        _field("hypothesis", pa.string()),
        _field("strategy", pa.string()),
        _field("universe", pa.string()),
        _field("cost_model", pa.string()),
        _field("parameters", pa.string()),
        _field("training_start", _DATE),
        _field("training_end", _DATE),
        _field("holdout_start", _DATE),
        _field("holdout_end", _DATE),
        _field("criterion", pa.string()),
        _field("min_sharpe", pa.float64()),
        _field("max_p_value", pa.float64()),
        _field("frozen_at_commit", pa.string()),
        _field("registered_at", _TIMESTAMP),
        _field("trials_on_same_data", pa.int64()),
        _field("status", pa.string()),
        _field("has_run", pa.bool_()),
        _optional("holdout_opened_at", _TIMESTAMP),
        _optional("holdout_opened_at_commit", pa.string()),
        _optional("holdout_cost_model", pa.string()),
        _optional("holdout_cagr", pa.float64()),
        _optional("holdout_sharpe", pa.float64()),
        _optional("holdout_sortino", pa.float64()),
        _optional("holdout_calmar", pa.float64()),
        _optional("holdout_max_drawdown", pa.float64()),
        _optional("holdout_p_value", pa.float64()),
        _optional("holdout_verdict", pa.string()),
    ]
)

RUN_SCHEMA = pa.schema(
    [
        _field("schema_version", pa.int64()),
        _field("hypothesis", pa.string()),
        _field("run_id", pa.string()),
        _field("strategy", pa.string()),
        _field("universe", pa.string()),
        _field("cost_model", pa.string()),
        _field("strategy_params", pa.string()),
        _field("start", _DATE),
        _field("end", _DATE),
        _optional("first_position", _DATE),
        _field("seed", pa.int64()),
        _field("git_sha", pa.string()),
        _field("generated_at", _TIMESTAMP),
        _field("data_source", pa.string()),
        _field("cost_sensitivity", pa.string()),
        _optional("cost_sharpe_difference", pa.float64()),
        _optional("cost_cagr_sign_flip", pa.bool_()),
        _optional("walk_forward_passed", pa.bool_()),
        _field("walk_forward_rule", pa.string()),
        _field("walk_forward_positive_windows", pa.int64()),
        _field("walk_forward_windows_with_sharpe", pa.int64()),
        _optional("permutation_passed", pa.bool_()),
        _field("permutation_statistic", pa.string()),
        _field("permutation_count", pa.int64()),
        _field("permutation_seed", pa.int64()),
        _field("permutation_alpha", pa.float64()),
        _field("permutation_active_days", pa.int64()),
        _field("permutation_low_confidence", pa.bool_()),
        _optional("permutation_actual", pa.float64()),
        _optional("permutation_null_mean", pa.float64()),
        _optional("permutation_null_std", pa.float64()),
        _optional("permutation_percentile", pa.float64()),
        _optional("permutation_p_value", pa.float64()),
        _optional("permutation_reason", pa.string()),
        _field("trials", pa.list_(pa.string())),
        _field("returns_count", pa.int64()),
        _optional("sharpe_annualized", pa.float64()),
        _optional("psr", pa.float64()),
        _optional("dsr_threshold", pa.float64()),
        _optional("dsr", pa.float64()),
        _optional("contrast_hypothesis", pa.string()),
        _optional("contrast_cost_model", pa.string()),
        _optional("contrast_correlation", pa.float64()),
        _field("regime_method", pa.string()),
        _field("trades", pa.int64()),
        _field("trades_open_at_end", pa.int64()),
        _field("trades_winning", pa.int64()),
    ]
)

TABLE_SCHEMAS = {
    "metrics": pa.schema(
        [
            _field("position", pa.int64()),
            _field("cost_model", pa.string()),
            _optional("cagr", pa.float64()),
            _optional("sharpe", pa.float64()),
            _optional("sortino", pa.float64()),
            _optional("calmar", pa.float64()),
            _optional("max_drawdown", pa.float64()),
            _field("turnover", pa.float64()),
            _field("primary", pa.bool_()),
        ]
    ),
    "equity": pa.schema(
        [
            _field("ts", _DATE),
            _field("equity", pa.float64()),
            _field("drawdown", pa.float64()),
        ]
    ),
    "walk_forward": pa.schema(
        [
            _field("position", pa.int64()),
            _field("start", _DATE),
            _field("end", _DATE),
            _field("partial", pa.bool_()),
            _field("aggregate", pa.bool_()),
            _optional("cagr", pa.float64()),
            _optional("sharpe", pa.float64()),
            _optional("max_drawdown", pa.float64()),
        ]
    ),
    "regimes": pa.schema(
        [
            _field("position", pa.int64()),
            _field("regime", pa.string()),
            _field("days", pa.int64()),
            _field("share", pa.float64()),
            _optional("cagr", pa.float64()),
            _optional("sharpe", pa.float64()),
            _optional("sortino", pa.float64()),
        ]
    ),
    "monthly": pa.schema(
        [
            _field("year", pa.int64()),
            _field("month", pa.int64()),
            _field("net_return", pa.float64()),
        ]
    ),
    "pnl_groups": pa.schema(
        [
            _field("dimension", pa.string()),
            _field("position", pa.int64()),
            _field("key", pa.string()),
            _field("trades", pa.int64()),
            _field("win_rate", pa.float64()),
            _field("total_net_pnl", pa.float64()),
            _field("mean_net_pnl", pa.float64()),
            _field("median_net_pnl", pa.float64()),
            _field("worst_net_pnl", pa.float64()),
            _field("best_net_pnl", pa.float64()),
            _field("costs", pa.float64()),
        ]
    ),
    "diagnostics": pa.schema(
        [
            _field("position", pa.int64()),
            _field("title", pa.string()),
            _field("label", pa.string()),
            _optional("value", pa.float64()),
        ]
    ),
    "trades": pa.schema(
        [
            _field("trade_id", pa.int64()),
            _field("instrument_id", pa.string()),
            _field("side", pa.string()),
            _field("entry_ts", _DATE),
            _field("entry_price", pa.float64()),
            _field("exit_ts", _DATE),
            _field("exit_price", pa.float64()),
            _field("size", pa.float64()),
            _field("gross_pnl", pa.float64()),
            _field("costs", pa.float64()),
            _field("net_pnl", pa.float64()),
            _field("holding_days", pa.int64()),
            _field("regime_at_entry", pa.string()),
            _field("open_at_end", pa.bool_()),
        ]
    ),
}


class RunEvidence(BaseModel):
    """Everything the store keeps of one training run: the tear-sheet and what
    `quantlab run` prints beside it.

    `pnl_groups` maps a dimension (`regime`, `holding_period`) to its groups in
    display order; `data_source` names where the bars came from (REQ-705).
    """

    sheet: TearSheet
    cost_sensitivity: CostSensitivity
    trades: list[Trade]
    pnl_groups: dict[str, dict[str, PnlGroup]]
    diagnostics: list[TrainingDiagnostic]
    data_source: str

    @model_validator(mode="after")
    def _complete(self) -> "RunEvidence":
        if self.sheet.multiple_testing is None:
            raise ValueError("The store needs the run's multiple-testing result")
        return self


class RegistryRow(BaseModel):
    """One committed hypothesis definition as the registry shows it (REQ-710)."""

    hypothesis: str
    strategy: str
    universe: str
    cost_model: str
    parameters: str
    training_start: date
    training_end: date
    holdout_start: date
    holdout_end: date
    criterion: str
    min_sharpe: float
    max_p_value: float
    frozen_at_commit: str
    registered_at: datetime
    trials_on_same_data: int
    status: Status
    has_run: bool
    holdout: HoldoutRecord | None


def _number(value: float | None) -> float | None:
    """A stored number: undefined values are NULL, never NaN or infinity (REQ-702)."""
    if value is None or not math.isfinite(value):
        return None
    return float(value)


def _write_table(path: Path, schema: pa.Schema, rows: list[dict]) -> None:
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), path)


def _regime_order(labels: list[str]) -> list[str]:
    known = [label for label in VOLATILITY_REGIMES if label in labels]
    return known + sorted(label for label in labels if label not in VOLATILITY_REGIMES)


def _run_row(evidence: RunEvidence) -> dict:
    sheet = evidence.sheet
    run = sheet.run
    walk_forward = sheet.walk_forward.detail
    permutation = sheet.permutation.detail
    deflation = sheet.multiple_testing
    contrast = sheet.contrast
    sensitivity = evidence.cost_sensitivity
    first_position = next((s.ts for s in run.snapshots if s.positions), None)
    return {
        "schema_version": SCHEMA_VERSION,
        "hypothesis": sheet.hypothesis,
        "run_id": run.id,
        "strategy": run.strategy_name,
        "universe": run.universe_name,
        "cost_model": run.cost_model_name,
        "strategy_params": json.dumps(run.strategy_params, sort_keys=True),
        "start": run.start,
        "end": run.end,
        "first_position": first_position,
        "seed": run.seed,
        "git_sha": run.git_sha,
        "generated_at": sheet.generated_at,
        "data_source": evidence.data_source,
        "cost_sensitivity": sensitivity.verdict,
        "cost_sharpe_difference": _number(sensitivity.sharpe_difference),
        "cost_cagr_sign_flip": sensitivity.cagr_sign_flip,
        "walk_forward_passed": sheet.walk_forward.passed,
        "walk_forward_rule": walk_forward["rule"],
        "walk_forward_positive_windows": walk_forward.get("positive_windows", 0),
        "walk_forward_windows_with_sharpe": walk_forward.get("windows_with_sharpe", 0),
        "permutation_passed": sheet.permutation.passed,
        "permutation_statistic": permutation["statistic"],
        "permutation_count": permutation["n_permutations"],
        "permutation_seed": permutation["seed"],
        "permutation_alpha": permutation["alpha"],
        "permutation_active_days": permutation["active_days"],
        "permutation_low_confidence": permutation["low_confidence"],
        "permutation_actual": _number(permutation.get("actual")),
        "permutation_null_mean": _number(permutation.get("null_mean")),
        "permutation_null_std": _number(permutation.get("null_std")),
        "permutation_percentile": _number(permutation.get("percentile")),
        "permutation_p_value": _number(permutation.get("p_value")),
        "permutation_reason": permutation.get("reason"),
        "trials": deflation.trials,
        "returns_count": deflation.n_returns,
        "sharpe_annualized": _number(deflation.sharpe_annualized),
        "psr": _number(deflation.psr),
        "dsr_threshold": _number(deflation.threshold_annualized),
        "dsr": _number(deflation.dsr),
        "contrast_hypothesis": contrast.hypothesis if contrast else None,
        "contrast_cost_model": contrast.cost_model_name if contrast else None,
        "contrast_correlation": _number(contrast.correlation) if contrast else None,
        "regime_method": sheet.regime_method,
        "trades": len(evidence.trades),
        "trades_open_at_end": sum(1 for trade in evidence.trades if trade.open_at_end),
        "trades_winning": sum(1 for trade in evidence.trades if trade.net_pnl > 0),
    }


def _tables(evidence: RunEvidence) -> dict[str, list[dict]]:
    sheet = evidence.sheet
    run = sheet.run
    dates = [snapshot.ts for snapshot in run.snapshots]
    equity = [snapshot.equity for snapshot in run.snapshots]
    drawdowns = drawdown_series(equity) if equity else []
    windows = sheet.walk_forward.detail["windows"]
    aggregate = sheet.walk_forward.detail["aggregate"]
    total_days = sum(regime.days for regime in sheet.regimes.values())
    return {
        "metrics": [
            {
                "position": position,
                "cost_model": metrics.cost_model_name,
                "cagr": _number(metrics.cagr),
                "sharpe": _number(metrics.sharpe),
                "sortino": _number(metrics.sortino),
                "calmar": _number(metrics.calmar),
                "max_drawdown": _number(metrics.max_drawdown),
                "turnover": metrics.turnover,
                "primary": metrics.cost_model_name == run.cost_model_name,
            }
            for position, metrics in enumerate(sheet.cost_comparison)
        ],
        "equity": [
            {"ts": day, "equity": value, "drawdown": drawdown}
            for day, value, drawdown in zip(dates, equity, drawdowns, strict=True)
        ],
        "walk_forward": [
            {
                "position": position,
                "start": date.fromisoformat(window["start"]),
                "end": date.fromisoformat(window["end"]),
                "partial": window["partial"],
                "aggregate": is_aggregate,
                "cagr": _number(window["cagr"]),
                "sharpe": _number(window["sharpe"]),
                "max_drawdown": _number(window["max_drawdown"]),
            }
            for position, (window, is_aggregate) in enumerate(
                [(window, False) for window in windows]
                + ([(aggregate, True)] if aggregate is not None else [])
            )
        ],
        "regimes": [
            {
                "position": position,
                "regime": label,
                "days": sheet.regimes[label].days,
                "share": sheet.regimes[label].days / total_days,
                "cagr": _number(sheet.regimes[label].cagr),
                "sharpe": _number(sheet.regimes[label].sharpe),
                "sortino": _number(sheet.regimes[label].sortino),
            }
            for position, label in enumerate(_regime_order(list(sheet.regimes)))
        ],
        "monthly": [
            {"year": year, "month": month, "net_return": value}
            for year, month, value in monthly_returns(dates, equity)
        ],
        "pnl_groups": [
            {"dimension": dimension, "position": position} | group.model_dump()
            for dimension, groups in evidence.pnl_groups.items()
            for position, group in enumerate(groups.values())
        ],
        "diagnostics": [
            {"position": position, "title": diagnostic.title, "label": label, "value": value}
            for position, (diagnostic, label, value) in enumerate(
                (diagnostic, label, _number(value))
                for diagnostic in evidence.diagnostics
                for label, value in diagnostic.values.items()
            )
        ],
        "trades": [
            {"trade_id": trade_id} | trade.model_dump()
            for trade_id, trade in enumerate(evidence.trades, start=1)
        ],
    }


def write_run(store: Path, evidence: RunEvidence) -> Path:
    """Write a hypothesis's run to `store/<hypothesis>/`, replacing its previous run
    as a whole (REQ-701, REQ-703): the tables go to a temporary directory that is
    then swapped in, so no reader sees tables of two runs once this returns.
    """
    hypothesis = evidence.sheet.hypothesis
    target = store / hypothesis
    staging = store / f".{hypothesis}.new"
    retired = store / f".{hypothesis}.old"
    for leftover in (staging, retired):
        if leftover.exists():
            shutil.rmtree(leftover)
    staging.mkdir(parents=True)
    _write_table(staging / RUN_FILE, RUN_SCHEMA, [_run_row(evidence)])
    for name, rows in _tables(evidence).items():
        _write_table(staging / f"{name}.parquet", TABLE_SCHEMAS[name], rows)
    if target.exists():
        target.rename(retired)
    staging.rename(target)
    if retired.exists():
        shutil.rmtree(retired)
    return target


def _stored_walk_forward(store: Path, hypothesis: str) -> tuple[bool, bool | None]:
    """Whether the store holds a current-schema run of the hypothesis, and its
    walk-forward result."""
    path = store / hypothesis / RUN_FILE
    if not path.exists():
        return False, None
    table = pq.read_table(path, columns=["schema_version", "walk_forward_passed"]).to_pylist()
    if len(table) != 1 or table[0]["schema_version"] != SCHEMA_VERSION:
        return False, None  # a run written by another schema version is not shown
    return True, table[0]["walk_forward_passed"]


def _status(
    has_run: bool, walk_forward_passed: bool | None, holdout: HoldoutRecord | None
) -> Status:
    """REQ-711: the gates decide once the holdout is open; before that, a stored run
    means the hypothesis is being tested."""
    if holdout is not None:
        return concluded_status(walk_forward_passed, holdout_passed(holdout.verdict))
    return "testing" if has_run else "proposed"


def registry_rows(store: Path, definitions_dir: Path) -> list[RegistryRow]:
    """Every committed definition, oldest first, with its holdout record and the
    status its gates give (REQ-710, REQ-711). Deleted definitions are left out
    but still count as trials on their data."""
    trials = registered_trials(definitions_dir)
    rows = []
    for trial in (trial for trial in trials if not trial.deleted):
        config = trial.definition
        parameters = config.parameters
        record_path = definitions_dir / f"{trial.hypothesis}.opened.json"
        holdout = read_holdout_record(record_path) if record_path.exists() else None
        has_run, walk_forward_passed = _stored_walk_forward(store, trial.hypothesis)
        rows.append(
            RegistryRow(
                hypothesis=trial.hypothesis,
                strategy=parameters.strategy,
                universe=parameters.universe,
                cost_model=parameters.cost_model.build().name,
                parameters=json.dumps(parameters.model_dump(mode="json"), sort_keys=True),
                training_start=config.training_start,
                training_end=config.training_end,
                holdout_start=config.start,
                holdout_end=config.end,
                criterion=config.success_criterion.description,
                min_sharpe=config.success_criterion.min_sharpe,
                max_p_value=config.success_criterion.max_p_value,
                frozen_at_commit=trial.last_commit,
                registered_at=trial.registered_at,
                trials_on_same_data=len(trials_on_same_data(trial.hypothesis, trials)),
                status=_status(has_run, walk_forward_passed, holdout),
                has_run=has_run,
                holdout=holdout,
            )
        )
    return rows


def write_registry(store: Path, definitions_dir: Path) -> list[RegistryRow]:
    """Rewrite `store/hypotheses.parquet` from the committed definitions (REQ-710)."""
    rows = registry_rows(store, definitions_dir)
    records = []
    for row in rows:
        holdout = row.holdout
        records.append(
            {"schema_version": SCHEMA_VERSION}
            | row.model_dump(exclude={"holdout"})
            | {
                "holdout_opened_at": holdout.opened_at if holdout else None,
                "holdout_opened_at_commit": holdout.opened_at_commit if holdout else None,
                "holdout_cost_model": holdout.cost_model_name if holdout else None,
                "holdout_cagr": _number(holdout.cagr) if holdout else None,
                "holdout_sharpe": _number(holdout.sharpe) if holdout else None,
                "holdout_sortino": _number(holdout.sortino) if holdout else None,
                "holdout_calmar": _number(holdout.calmar) if holdout else None,
                "holdout_max_drawdown": _number(holdout.max_drawdown) if holdout else None,
                "holdout_p_value": _number(holdout.p_value) if holdout else None,
                "holdout_verdict": holdout.verdict if holdout else None,
            }
        )
    store.mkdir(parents=True, exist_ok=True)
    staging = store / f".{REGISTRY_FILE}.new"
    _write_table(staging, REGISTRY_SCHEMA, records)
    staging.replace(store / REGISTRY_FILE)
    return rows
