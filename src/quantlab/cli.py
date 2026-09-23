import importlib.metadata
import subprocess
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import typer

from quantlab.backtest.vectorized.engine import BacktestRun
from quantlab.backtest.vectorized.engine import run as run_backtest
from quantlab.core.data.binance import BinanceProvider
from quantlab.core.data.provider import DataProvider, PriceBar
from quantlab.core.universe import Universe
from quantlab.costs.base import CostModel
from quantlab.costs.naive import NaiveCostModel
from quantlab.costs.realistic import RealisticCostModel
from quantlab.costs.zero import ZeroCostModel
from quantlab.reporting.cost_comparison import cost_sensitivity, run_metrics
from quantlab.strategy.time_series_momentum import TimeSeriesMomentum
from quantlab.validation.holdout import (
    FrozenHoldout,
    HoldoutAlreadyOpenedError,
    HoldoutRecord,
    holdout_verdict,
    load_frozen_holdout,
    read_holdout_record,
    write_holdout_record,
)
from quantlab.validation.permutation import PermutationTestValidator
from quantlab.validation.walk_forward import WalkForwardValidator

app = typer.Typer()

_UNIVERSE_NAME = "mvp-crypto"
# Training period only. The 2024-01-01..2025-12-31 holdout is deliberately never
# fetched or evaluated here - it gets frozen (S10) before anything looks at it.
_TRAINING_START = date(2018, 1, 1)
_TRAINING_END = date(2023, 12, 31)
_LOOKBACK_DAYS = 365  # ~12-month formation period, Moskowitz/Ooi/Pedersen (2012)
_COST_BPS = 10  # Binance spot default maker/taker fee for regular users: 0.1%
# Trading a few minutes after the close moves price by ~sigma_daily * sqrt(min/1440),
# about 0.05-0.06 sigma for ~5 minutes. Conservative: zero-mean drift charged as cost.
_SLIPPAGE_K = 0.05
_VOL_WINDOW_DAYS = 30
_SEED = 0  # seeds the permutation test's shuffles, so reruns reproduce its p-value
_PERMUTATIONS = 10_000
_PERMUTATION_ALPHA = 0.1
_PERIODS_PER_YEAR = 365  # crypto trades every calendar day
_HOLDOUT_CONFIG = Path("config/holdout/momentum_v1.yaml")
_HOLDOUT_RECORD = Path("config/holdout/momentum_v1.opened.json")


def _version_callback(show_version: bool) -> None:
    if show_version:
        typer.echo(importlib.metadata.version("quantlab"))
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True
    ),
) -> None:
    pass


def _fetch_bars(
    provider: DataProvider, universe: Universe, lookback_days: int, start: date, end: date
) -> dict[str, list[PriceBar]]:
    """History from `lookback_days` before `start`, so a signal can exist from
    the window's first day where data allows. Nothing after `end` is requested.
    """
    fetch_start = start - timedelta(days=lookback_days)
    return {
        instrument.id: provider.fetch(instrument, fetch_start, end)
        for instrument in universe.instruments
    }


def _run_momentum(
    bars: dict[str, list[PriceBar]],
    cost_model: CostModel,
    universe: Universe,
    lookback_days: int,
    start: date,
    end: date,
    seed: int,
    git_sha: str,
) -> BacktestRun:
    return run_backtest(
        strategy=TimeSeriesMomentum(lookback_days=lookback_days),
        cost_model=cost_model,
        bars=bars,
        universe_name=universe.name,
        start=start,
        end=end,
        seed=seed,
        git_sha=git_sha,
        strategy_name="time_series_momentum",
        strategy_params={"lookback_days": lookback_days},
    )


def run_momentum_study(
    provider: DataProvider,
    cost_model: CostModel,
    universe: Universe,
    lookback_days: int,
    start: date,
    end: date,
    seed: int,
    git_sha: str,
) -> BacktestRun:
    """Fetch data, run time-series momentum through the vectorized engine."""
    bars = _fetch_bars(provider, universe, lookback_days, start, end)
    return _run_momentum(bars, cost_model, universe, lookback_days, start, end, seed, git_sha)


def run_cost_comparison(
    provider: DataProvider,
    cost_models: list[CostModel],
    universe: Universe,
    lookback_days: int,
    start: date,
    end: date,
    seed: int,
    git_sha: str,
) -> list[BacktestRun]:
    """Same inputs under each cost model; data is fetched once and shared (REQ-031)."""
    bars = _fetch_bars(provider, universe, lookback_days, start, end)
    return [
        _run_momentum(bars, cost_model, universe, lookback_days, start, end, seed, git_sha)
        for cost_model in cost_models
    ]


def open_frozen_holdout(
    provider: DataProvider,
    frozen: FrozenHoldout,
    record_path: Path,
    n_permutations: int,
    seed: int,
    git_sha: str,
    opened_at: datetime,
) -> HoldoutRecord:
    """Evaluate the frozen holdout once, using only the frozen parameters.

    Refuses before fetching anything if a record of an earlier opening exists.
    The record is written with exclusive create and is meant to be committed,
    so any later re-opening would be visible in git history.
    """
    if record_path.exists():
        raise HoldoutAlreadyOpenedError(f"Holdout already opened; see {record_path}")

    config = frozen.config
    parameters = config.parameters
    universe = Universe.load(parameters.universe)
    cost_model = RealisticCostModel(
        fee_bps=parameters.cost_model.fee_bps,
        k=parameters.cost_model.k,
        vol_window=parameters.cost_model.vol_window,
    )
    bars = _fetch_bars(provider, universe, parameters.lookback_days, config.start, config.end)
    run = _run_momentum(
        bars, cost_model, universe, parameters.lookback_days, config.start, config.end, seed, git_sha
    )
    metrics = run_metrics(run, _PERIODS_PER_YEAR)
    permutation = PermutationTestValidator(
        bars=bars,
        n_permutations=n_permutations,
        alpha=config.success_criterion.max_p_value,
        periods_per_year=_PERIODS_PER_YEAR,
    ).validate(run)
    p_value = permutation.detail["p_value"]

    record = HoldoutRecord(
        hypothesis=config.hypothesis,
        frozen_at_commit=frozen.frozen_at_commit,
        opened_at=opened_at,
        opened_at_commit=git_sha,
        start=config.start,
        end=config.end,
        cost_model_name=run.cost_model_name,
        cagr=metrics.cagr,
        sharpe=metrics.sharpe,
        sortino=metrics.sortino,
        calmar=metrics.calmar,
        max_drawdown=metrics.max_drawdown,
        p_value=p_value,
        permutation=permutation.detail,
        criterion=config.success_criterion.description,
        verdict=holdout_verdict(config.success_criterion, metrics.sharpe, p_value),
    )
    write_holdout_record(record_path, record)
    return record


def _current_git_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


@app.command()
def run() -> None:
    """Run the momentum study on the MVP basket under each cost model, training period only."""
    naive = NaiveCostModel(bps=_COST_BPS)
    realistic = RealisticCostModel(fee_bps=_COST_BPS, k=_SLIPPAGE_K, vol_window=_VOL_WINDOW_DAYS)
    provider = BinanceProvider()
    universe = Universe.load(_UNIVERSE_NAME)
    runs = run_cost_comparison(
        provider=provider,
        cost_models=[ZeroCostModel(), naive, realistic],
        universe=universe,
        lookback_days=_LOOKBACK_DAYS,
        start=_TRAINING_START,
        end=_TRAINING_END,
        seed=_SEED,
        git_sha=_current_git_sha(),
    )
    metrics = [run_metrics(result, _PERIODS_PER_YEAR) for result in runs]
    sensitivity = cost_sensitivity(lower_cost=metrics[1], higher_cost=metrics[2])

    first = runs[0]
    first_position = next((snapshot.ts for snapshot in first.snapshots if snapshot.positions), None)
    typer.echo(f"Universe:       {first.universe_name}")
    typer.echo(f"Strategy:       {first.strategy_name} {first.strategy_params}")
    typer.echo(f"Period:         {first.start} .. {first.end} (training only)")
    typer.echo(f"First position: {first_position}")
    typer.echo(f"Git:            {first.git_sha[:7]}")
    typer.echo("")

    width = max(len(m.cost_model_name) for m in metrics) + 2
    typer.echo(" " * 14 + "".join(f"{m.cost_model_name:>{width}}" for m in metrics))
    rows = [
        ("CAGR", lambda m: f"{m.cagr:.2%}"),
        ("Sharpe", lambda m: f"{m.sharpe:.2f}"),
        ("Sortino", lambda m: f"{m.sortino:.2f}"),
        ("Calmar", lambda m: f"{m.calmar:.2f}"),
        ("Max drawdown", lambda m: f"{m.max_drawdown:.2%}"),
    ]
    for label, fmt in rows:
        typer.echo(f"{label:<14}" + "".join(f"{fmt(m):>{width}}" for m in metrics))

    typer.echo("")
    meaning = (
        "result is robust to cost assumptions"
        if sensitivity.verdict == "robust"
        else "result depends on cost assumptions - report as a limitation"
    )
    typer.echo(
        f"Cost sensitivity ({sensitivity.lower_cost_model} vs {sensitivity.higher_cost_model}): "
        f"Sharpe difference {sensitivity.sharpe_difference:.2f}"
        f"{', CAGR changes sign' if sensitivity.cagr_sign_flip else ''} "
        f"-> {sensitivity.verdict}: {meaning}"
    )

    walk_forward = WalkForwardValidator(_PERIODS_PER_YEAR).validate(runs[2])
    typer.echo("")
    typer.echo(f"Walk-forward ({runs[2].cost_model_name}), calendar-year windows:")
    typer.echo(f"{'Window':<26}{'CAGR':>10}{'Sharpe':>10}{'Max DD':>10}")

    def _row(label: str, window: dict) -> str:
        def fmt(value: float | None, pattern: str) -> str:
            return "n/a" if value is None else format(value, pattern)

        return (
            f"{label:<26}{fmt(window['cagr'], '.2%'):>10}"
            f"{fmt(window['sharpe'], '.2f'):>10}{fmt(window['max_drawdown'], '.2%'):>10}"
        )

    for window in walk_forward.detail["windows"]:
        marker = "*" if window["partial"] else ""
        typer.echo(_row(f"{window['start']}..{window['end']}{marker}", window))
    if walk_forward.detail["aggregate"] is not None:
        typer.echo(_row("Aggregate", walk_forward.detail["aggregate"]))
    typer.echo("* partial year")
    typer.echo(f"Rule: {walk_forward.detail['rule']}")
    outcome = {True: "passed", False: "failed", None: "inconclusive"}[walk_forward.passed]
    typer.echo(
        f"Result: {outcome} ({walk_forward.detail.get('positive_windows', 0)} of "
        f"{walk_forward.detail.get('windows_with_sharpe', 0)} windows with Sharpe > 0)"
    )

    # Same bars the runs used; a cache hit, not a second download.
    bars = _fetch_bars(provider, universe, _LOOKBACK_DAYS, _TRAINING_START, _TRAINING_END)
    permutation = PermutationTestValidator(
        bars=bars,
        n_permutations=_PERMUTATIONS,
        alpha=_PERMUTATION_ALPHA,
        periods_per_year=_PERIODS_PER_YEAR,
    ).validate(runs[2])
    detail = permutation.detail
    typer.echo("")
    typer.echo(
        f"Permutation test ({detail['n_permutations']:,} shuffles of returns against the "
        f"positions held, seed {detail['seed']}):"
    )
    if "reason" in detail:
        typer.echo(f"Result: inconclusive ({detail['reason']})")
    else:
        significance = (
            f"significant at {detail['alpha']}"
            if permutation.passed
            else f"not significant at {detail['alpha']} -> inconclusive"
        )
        typer.echo(
            f"Gross Sharpe {detail['actual']:.2f} vs shuffled mean {detail['null_mean']:.2f} "
            f"(sd {detail['null_std']:.2f}); beats {detail['percentile']:.1%} of shuffles"
        )
        typer.echo(f"Result: p = {detail['p_value']:.4f}, {significance}")
    if detail["low_confidence"]:
        typer.echo(f"Low confidence: only {detail['active_days']} days with a position")


def _print_holdout(record: HoldoutRecord) -> None:
    permutation = record.permutation
    typer.echo("")
    typer.echo(f"HOLDOUT {record.start} .. {record.end} ({record.hypothesis})")
    typer.echo(f"Frozen at:      {record.frozen_at_commit[:7]}")
    typer.echo(f"Opened at:      {record.opened_at:%Y-%m-%d %H:%M} UTC, commit {record.opened_at_commit[:7]}")
    typer.echo(f"Cost model:     {record.cost_model_name}")
    typer.echo("")
    typer.echo(f"CAGR:           {record.cagr:8.2%}")
    typer.echo(f"Sharpe (net):   {record.sharpe:8.2f}")
    typer.echo(f"Sortino:        {record.sortino:8.2f}")
    typer.echo(f"Calmar:         {record.calmar:8.2f}")
    typer.echo(f"Max drawdown:   {record.max_drawdown:8.2%}")
    typer.echo("")
    typer.echo(
        f"Permutation:    gross Sharpe {permutation['actual']:.2f} vs shuffled mean "
        f"{permutation['null_mean']:.2f}; p = {record.p_value:.4f} "
        f"({permutation['n_permutations']:,} shuffles, seed {permutation['seed']})"
    )
    if permutation["low_confidence"]:
        typer.echo(f"Low confidence: only {permutation['active_days']} days with a position")
    typer.echo(f"Criterion:      {record.criterion}")
    typer.echo(f"Verdict:        {record.verdict.upper()}")


@app.command("open-holdout")
def open_holdout() -> None:
    """Open the frozen holdout exactly once and record the result (REQ-041, REQ-042)."""
    if _HOLDOUT_RECORD.exists():
        record = read_holdout_record(_HOLDOUT_RECORD)
        typer.echo(
            f"Holdout already opened on {record.opened_at:%Y-%m-%d %H:%M} UTC - not re-running. "
            f"Showing the recorded result from {_HOLDOUT_RECORD}."
        )
    else:
        record = open_frozen_holdout(
            provider=BinanceProvider(),
            frozen=load_frozen_holdout(_HOLDOUT_CONFIG),
            record_path=_HOLDOUT_RECORD,
            n_permutations=_PERMUTATIONS,
            seed=_SEED,
            git_sha=_current_git_sha(),
            opened_at=datetime.now(tz=UTC),
        )
        typer.echo(f"Holdout opened. Result recorded in {_HOLDOUT_RECORD} - commit it.")
    _print_holdout(record)
