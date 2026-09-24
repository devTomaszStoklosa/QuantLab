import importlib.metadata
import subprocess
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Annotated

import typer

from quantlab.attribution.trade_ledger import (
    HOLDING_PERIOD_BUCKETS,
    PnlGroup,
    build_trade_ledger,
    by_holding_period,
    group_pnl,
)
from quantlab.attribution.trade_ledger import by_regime as by_regime_at_entry
from quantlab.backtest.vectorized.engine import BacktestRun
from quantlab.backtest.vectorized.engine import run as run_backtest
from quantlab.core.data.binance import BinanceProvider
from quantlab.core.data.provider import DataProvider, PriceBar
from quantlab.core.universe import Universe
from quantlab.costs.base import CostModel
from quantlab.costs.naive import NaiveCostModel
from quantlab.costs.zero import ZeroCostModel
from quantlab.reporting.cost_comparison import cost_sensitivity, run_metrics
from quantlab.reporting.tear_sheet import TearSheet, render_html
from quantlab.research.definition import StudyParameters
from quantlab.research.hypothesis import concluded_status
from quantlab.risk.conditional import regime_conditional_metrics
from quantlab.risk.regime import VOLATILITY_REGIMES, VolatilityTercileClassifier, label_periods
from quantlab.risk.stress import ShockScenario, stress_run, worst_day_scenario
from quantlab.validation.holdout import (
    FrozenHoldout,
    HoldoutAlreadyOpenedError,
    HoldoutNotFrozenError,
    HoldoutRecord,
    holdout_passed,
    holdout_verdict,
    load_frozen_holdout,
    read_holdout_record,
    write_holdout_record,
)
from quantlab.validation.permutation import PermutationTestValidator
from quantlab.validation.walk_forward import WalkForwardValidator

app = typer.Typer()

# Lab-wide methodology, the same for every hypothesis. What a hypothesis itself
# defines - strategy, parameters, universe, cost model, training and holdout
# dates - comes only from its committed file in _HOLDOUT_DIR (REQ-301).
_SEED = 0  # seeds the permutation test's shuffles, so reruns reproduce its p-value
_PERMUTATIONS = 10_000
_PERMUTATION_ALPHA = 0.1
_PERIODS_PER_YEAR = 365  # crypto trades every calendar day
# Market regime for the whole portfolio: BTC as the usual crypto market proxy,
# 30-day volatility ranked against its own last 365 days.
_REGIME_INSTRUMENT = "btc-usdt"
_REGIME_VOL_WINDOW_DAYS = 30
_REGIME_HISTORY_DAYS = 365
_STRESS_SHOCK = 0.20  # the AC-10 example size, applied down and up
_DEFAULT_HYPOTHESIS = "momentum_v1"
_HOLDOUT_DIR = Path("config/holdout")


def _definition_path(hypothesis: str) -> Path:
    return _HOLDOUT_DIR / f"{hypothesis}.yaml"


def _record_path(hypothesis: str) -> Path:
    return _HOLDOUT_DIR / f"{hypothesis}.opened.json"


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
    provider: DataProvider, universe: Universe, warm_up_days: int, start: date, end: date
) -> dict[str, list[PriceBar]]:
    """History from `warm_up_days` before `start`, so a signal can exist from
    the window's first day where data allows. Nothing after `end` is requested.
    """
    fetch_start = start - timedelta(days=warm_up_days)
    return {
        instrument.id: provider.fetch(instrument, fetch_start, end)
        for instrument in universe.instruments
    }


def _run_study(
    bars: dict[str, list[PriceBar]],
    parameters: StudyParameters,
    cost_model: CostModel,
    universe: Universe,
    start: date,
    end: date,
    seed: int,
    git_sha: str,
) -> BacktestRun:
    return run_backtest(
        strategy=parameters.build_strategy(),
        cost_model=cost_model,
        bars=bars,
        universe_name=universe.name,
        start=start,
        end=end,
        seed=seed,
        git_sha=git_sha,
        strategy_name=parameters.strategy,
        strategy_params=parameters.strategy_params(),
    )


def run_study(
    provider: DataProvider,
    parameters: StudyParameters,
    cost_model: CostModel,
    universe: Universe,
    start: date,
    end: date,
    seed: int,
    git_sha: str,
) -> BacktestRun:
    """Fetch data, run the hypothesis's strategy through the vectorized engine."""
    bars = _fetch_bars(provider, universe, parameters.warm_up_days, start, end)
    return _run_study(bars, parameters, cost_model, universe, start, end, seed, git_sha)


def run_cost_comparison(
    provider: DataProvider,
    parameters: StudyParameters,
    cost_models: list[CostModel],
    universe: Universe,
    start: date,
    end: date,
    seed: int,
    git_sha: str,
) -> list[BacktestRun]:
    """Same inputs under each cost model; data is fetched once and shared (REQ-031)."""
    bars = _fetch_bars(provider, universe, parameters.warm_up_days, start, end)
    return [
        _run_study(bars, parameters, cost_model, universe, start, end, seed, git_sha)
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
    bars = _fetch_bars(provider, universe, parameters.warm_up_days, config.start, config.end)
    run = _run_study(
        bars,
        parameters,
        parameters.cost_model.build(),
        universe,
        config.start,
        config.end,
        seed,
        git_sha,
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


def _load_definition(hypothesis: str) -> FrozenHoldout:
    """The hypothesis's committed definition, or exit before fetching any data (REQ-303)."""
    try:
        return load_frozen_holdout(_definition_path(hypothesis))
    except HoldoutNotFrozenError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error


def _current_git_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


_HYPOTHESIS_ARGUMENT = typer.Argument(
    help="Hypothesis id; its committed definition is config/holdout/<id>.yaml."
)


@app.command()
def run(
    hypothesis: Annotated[str, _HYPOTHESIS_ARGUMENT] = _DEFAULT_HYPOTHESIS,
    tear_sheet: Annotated[
        Path | None,
        typer.Option(help="Also write an HTML tear-sheet of the realistic-cost run to this file."),
    ] = None,
) -> None:
    """Run a hypothesis under each cost model, over its training period only.

    Its holdout is never fetched here; that happens once, in open-holdout.
    """
    frozen = _load_definition(hypothesis)
    config = frozen.config
    parameters = config.parameters
    provider = BinanceProvider()
    universe = Universe.load(parameters.universe)
    runs = run_cost_comparison(
        provider=provider,
        parameters=parameters,
        cost_models=[
            ZeroCostModel(),
            NaiveCostModel(bps=parameters.cost_model.fee_bps),
            parameters.cost_model.build(),
        ],
        universe=universe,
        start=config.training_start,
        end=config.training_end,
        seed=_SEED,
        git_sha=_current_git_sha(),
    )
    metrics = [run_metrics(result, _PERIODS_PER_YEAR) for result in runs]
    sensitivity = cost_sensitivity(lower_cost=metrics[1], higher_cost=metrics[2])

    first = runs[0]
    first_position = next((snapshot.ts for snapshot in first.snapshots if snapshot.positions), None)
    typer.echo(f"Hypothesis:     {config.hypothesis} (defined at {frozen.frozen_at_commit[:7]})")
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
    bars = _fetch_bars(
        provider, universe, parameters.warm_up_days, config.training_start, config.training_end
    )
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

    classifier = VolatilityTercileClassifier(
        vol_window=_REGIME_VOL_WINDOW_DAYS, history_days=_REGIME_HISTORY_DAYS
    )
    labels = label_periods(
        classifier, bars[_REGIME_INSTRUMENT], [snapshot.ts for snapshot in runs[2].snapshots]
    )
    by_regime = regime_conditional_metrics(runs[2], labels, _PERIODS_PER_YEAR)
    total_days = sum(regime.days for regime in by_regime.values())
    typer.echo("")
    typer.echo(
        f"Regimes ({runs[2].cost_model_name}): {_REGIME_INSTRUMENT} {_REGIME_VOL_WINDOW_DAYS}-day "
        f"volatility tercile vs its last {_REGIME_HISTORY_DAYS} days, "
        "as of the day before each return"
    )
    typer.echo(f"{'Regime':<12}{'Days':>7}{'Share':>9}{'CAGR':>10}{'Sharpe':>10}{'Sortino':>10}")

    def _fmt(value: float | None, pattern: str) -> str:
        return "n/a" if value is None else format(value, pattern)

    for label in (label for label in VOLATILITY_REGIMES if label in by_regime):
        regime = by_regime[label]
        typer.echo(
            f"{label:<12}{regime.days:>7}{regime.days / total_days:>9.1%}"
            f"{_fmt(regime.cagr, '.2%'):>10}{_fmt(regime.sharpe, '.2f'):>10}"
            f"{_fmt(regime.sortino, '.2f'):>10}"
        )
    typer.echo("Descriptive only: not part of any pass rule or of the hypothesis verdict.")

    instrument_ids = [instrument.id for instrument in universe.instruments]
    scenarios = [
        ShockScenario(
            name=f"crash-{_STRESS_SHOCK:.0%}",
            description=f"every instrument -{_STRESS_SHOCK:.0%} at once",
            shocks={instrument_id: -_STRESS_SHOCK for instrument_id in instrument_ids},
        ),
        ShockScenario(
            name=f"rally-{_STRESS_SHOCK:.0%}",
            description=f"every instrument +{_STRESS_SHOCK:.0%} at once; hurts short positions",
            shocks={instrument_id: _STRESS_SHOCK for instrument_id in instrument_ids},
        ),
        worst_day_scenario("worst-btc-day", bars, _REGIME_INSTRUMENT, runs[2].start, runs[2].end),
    ]
    stress = [stress_run(runs[2], scenario) for scenario in scenarios]
    typer.echo("")
    typer.echo(
        f"Stress test ({runs[2].cost_model_name}): instantaneous shock, "
        "impact = sum of weight x shock, costs of reacting not included"
    )
    typer.echo(
        f"{'Scenario':<16}{'Last day':>10}{'Worst':>10}{'Worst held on':>15}{'Losing days':>13}"
    )
    for result in stress:
        typer.echo(
            f"{result.scenario.name:<16}{result.last_impact:>10.2%}{result.worst_impact:>10.2%}"
            f"{result.worst_held_on!s:>15}{result.losing_share:>13.1%}"
        )
    typer.echo(f"Last day = positions held on {stress[0].last_held_on}.")
    for result in stress:
        shocks = ", ".join(
            f"{instrument_id} {shock:+.1%}"
            for instrument_id, shock in result.scenario.shocks.items()
        )
        typer.echo(f"{result.scenario.name}: {result.scenario.description} ({shocks})")

    trades = build_trade_ledger(runs[2], bars, labels)
    open_at_end = sum(1 for trade in trades if trade.open_at_end)
    winners = sum(1 for trade in trades if trade.net_pnl > 0)
    equity_change = runs[2].snapshots[-1].equity - runs[2].snapshots[0].equity
    typer.echo("")
    typer.echo(
        f"Trade ledger ({runs[2].cost_model_name}): {len(trades)} trades "
        f"({open_at_end} open at the end), {winners / len(trades):.1%} with net P&L > 0"
    )
    typer.echo(
        f"Net P&L of all trades {sum(trade.net_pnl for trade in trades):+.4f} "
        f"= equity change {equity_change:+.4f} (P&L in equity units, portfolio started at 1.00)"
    )
    header = (
        f"{'Trades':>7}{'Win rate':>10}{'Total':>10}{'Mean':>10}{'Median':>10}"
        f"{'Worst':>10}{'Best':>10}{'Costs':>9}"
    )

    def _print_groups(title: str, groups: dict[str, PnlGroup], order: tuple[str, ...]) -> None:
        typer.echo(f"{title:<12}{header}")
        for key in (key for key in order if key in groups):
            group = groups[key]
            typer.echo(
                f"{key:<12}{group.trades:>7}{group.win_rate:>10.1%}{group.total_net_pnl:>+10.4f}"
                f"{group.mean_net_pnl:>+10.4f}{group.median_net_pnl:>+10.4f}"
                f"{group.worst_net_pnl:>+10.4f}{group.best_net_pnl:>+10.4f}{group.costs:>9.4f}"
            )

    _print_groups("Regime", group_pnl(trades, by_regime_at_entry), VOLATILITY_REGIMES)
    _print_groups("Holding", group_pnl(trades, by_holding_period), HOLDING_PERIOD_BUCKETS)
    typer.echo("Regime = market regime as of the entry close. Descriptive only.")

    # The holdout's result comes only from the record of its one-time opening.
    record_path = _record_path(hypothesis)
    holdout = read_holdout_record(record_path) if record_path.exists() else None
    typer.echo("")
    if holdout is None:
        typer.echo(f"Hypothesis {hypothesis}: no verdict until the frozen holdout is opened")
    else:
        status = concluded_status(walk_forward.passed, holdout_passed(holdout.verdict))
        typer.echo(
            f"Hypothesis {hypothesis}: {status.upper()} "
            f"(walk-forward {outcome}, holdout {holdout.verdict} "
            f"as recorded {holdout.opened_at:%Y-%m-%d})"
        )

    if tear_sheet is not None:
        sheet = TearSheet(
            hypothesis=config.hypothesis,
            run=runs[2],
            cost_comparison=metrics,
            regimes=by_regime,
            regime_method=(
                f"Reżim rynku: tercyl {_REGIME_VOL_WINDOW_DAYS}-dniowej zmienności "
                f"{_REGIME_INSTRUMENT} względem jej ostatnich {_REGIME_HISTORY_DAYS} dni, "
                "na dzień przed każdym zwrotem."
            ),
            walk_forward=walk_forward,
            permutation=permutation,
            holdout=holdout,
            generated_at=datetime.now(tz=UTC),
        )
        tear_sheet.parent.mkdir(parents=True, exist_ok=True)
        tear_sheet.write_text(render_html(sheet), encoding="utf-8")
        typer.echo("")
        typer.echo(f"Tear-sheet written to {tear_sheet}")


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
def open_holdout(hypothesis: Annotated[str, _HYPOTHESIS_ARGUMENT] = _DEFAULT_HYPOTHESIS) -> None:
    """Open a hypothesis's frozen holdout exactly once and record the result (REQ-041, REQ-042)."""
    record_path = _record_path(hypothesis)
    if record_path.exists():
        record = read_holdout_record(record_path)
        typer.echo(
            f"Holdout already opened on {record.opened_at:%Y-%m-%d %H:%M} UTC - not re-running. "
            f"Showing the recorded result from {record_path}."
        )
    else:
        record = open_frozen_holdout(
            provider=BinanceProvider(),
            frozen=_load_definition(hypothesis),
            record_path=record_path,
            n_permutations=_PERMUTATIONS,
            seed=_SEED,
            git_sha=_current_git_sha(),
            opened_at=datetime.now(tz=UTC),
        )
        typer.echo(f"Holdout opened. Result recorded in {record_path} - commit it.")
    _print_holdout(record)
