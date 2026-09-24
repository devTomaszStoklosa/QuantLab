import importlib.metadata
import importlib.resources
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Annotated, NamedTuple

import typer
from pydantic import BaseModel

from quantlab.attribution.trade_ledger import (
    HOLDING_PERIOD_BUCKETS,
    PnlGroup,
    build_trade_ledger,
    by_holding_period,
    group_pnl,
)
from quantlab.attribution.trade_ledger import by_regime as by_regime_at_entry
from quantlab.backtest.event_driven.engine import EventDrivenResult
from quantlab.backtest.event_driven.engine import run as run_event_driven
from quantlab.backtest.event_driven.execution import (
    CloseExecution,
    ExecutionModel,
    NextBarExecution,
)
from quantlab.backtest.event_driven.fills import FillPolicy, FullFill, VolumeParticipationFill
from quantlab.backtest.run import BacktestRun
from quantlab.backtest.vectorized.engine import run as run_backtest
from quantlab.core import sp500
from quantlab.core.data.binance import BinanceProvider
from quantlab.core.data.corporate_actions import MarketData, with_assumed_return, with_events
from quantlab.core.data.coverage import price_coverage
from quantlab.core.data.provider import DataProvider, DataSourceUnavailableError, PriceBar
from quantlab.core.data.tiingo import TiingoProvider
from quantlab.core.universe import Universe
from quantlab.costs.base import CostModel
from quantlab.costs.naive import NaiveCostModel
from quantlab.costs.zero import ZeroCostModel
from quantlab.reporting.contrast import return_correlation
from quantlab.reporting.cost_comparison import cost_sensitivity, run_metrics
from quantlab.reporting.engine_comparison import (
    EngineComparisonRow,
    capacity,
    comparison_row,
    max_equity_difference,
)
from quantlab.reporting.multiple_testing import (
    MultipleTesting,
    aligned_active_returns,
    multiple_testing,
)
from quantlab.reporting.results_store import (
    REGISTRY_FILE,
    RegistryRow,
    RunEvidence,
    write_registry,
    write_run,
)
from quantlab.reporting.tear_sheet import Contrast, TearSheet, render_html
from quantlab.research.definition import StudyParameters
from quantlab.research.hypothesis import concluded_status
from quantlab.research.trials import (
    Trial,
    TrialRegistryError,
    registered_trials,
    trials_on_same_data,
)
from quantlab.risk.conditional import regime_conditional_metrics
from quantlab.risk.regime import VOLATILITY_REGIMES, VolatilityTercileClassifier, label_periods
from quantlab.risk.stress import ShockScenario, stress_run, worst_day_scenario
from quantlab.strategy.base import Strategy
from quantlab.strategy.members_only import MembersOnly
from quantlab.validation.base import SignificanceTest, Validator
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
from quantlab.validation.pbo import PboResult, probability_of_backtest_overfitting
from quantlab.validation.permutation import PermutationTestValidator
from quantlab.validation.random_portfolio import RandomPortfolioValidator
from quantlab.validation.walk_forward import WalkForwardValidator

app = typer.Typer()


def entry() -> None:
    """The `quantlab` command: the app, with a source that fails mid-download (a quota
    reached) reported in one line; what was downloaded stays cached."""
    try:
        app()
    except DataSourceUnavailableError as error:
        typer.echo(f"Error: {error}", err=True)
        raise SystemExit(1) from error


# Lab-wide methodology, the same for every hypothesis. What a hypothesis itself
# defines - strategy, parameters, universe, cost model, training and holdout
# dates - comes only from its committed file in _HOLDOUT_DIR (REQ-301).
_SEED = 0  # seeds the permutation test's shuffles, so reruns reproduce its p-value
_PERMUTATIONS = 10_000
_PERMUTATION_ALPHA = 0.1
# Annualization and the regime windows come from the universe's market (REQ-506):
# universe.periods_per_year, 365 for crypto.
_STRESS_SHOCK = 0.20  # the AC-10 example size, applied down and up
# A delisting return a source does not give is a frozen assumption of the
# hypothesis; the run also shows the result under Shumway's (1997) average for
# performance-related delistings, so the assumption's weight is visible (q5 Q6).
_DELISTING_STRESS_RETURN = -0.30
# Execution simulation for the engine comparison (q2): lab-wide too, and they
# only change how orders fill in a descriptive comparison, never a verdict.
_NOMINAL_CAPITAL = 100_000.0  # USDT, a private researcher's scale
_MAX_PARTICIPATION = 0.025  # of the fill bar's volume; zipline's VolumeShareSlippage default
# CSCV blocks for PBO: the example of Bailey, Borwein, Lopez de Prado and Zhu (2017).
_PBO_BLOCKS = 16
# Parity differences above this are not floating-point noise.
_PARITY_NOISE = 1e-9
_DEFAULT_HYPOTHESIS = "momentum_v1"
_HOLDOUT_DIR = Path("config/holdout")
# What the presentation layer reads (q7, ADR-0008); gitignored, since the trade
# ledger carries market prices.
_RESULTS_DIR = Path("results")
# Where universe files live; build-universe writes the S&P 500 one here (q5, REQ-553).
_UNIVERSES_DIR = Path(str(importlib.resources.files("quantlab.config"))) / "universes"
# Data providers by the source name a universe file gives (REQ-506): a new source
# is a new entry here, never a branch on the asset class.
_PROVIDERS: dict[str, Callable[[], DataProvider]] = {
    "binance": BinanceProvider,
    "tiingo": TiingoProvider,
}


def _provider(universe: Universe) -> DataProvider:
    """The universe's data provider, or exit before fetching anything."""
    factory = _PROVIDERS.get(universe.source)
    if factory is None:
        typer.echo(
            f"Error: universe {universe.name} names data source '{universe.source}'; "
            f"known sources: {', '.join(sorted(_PROVIDERS))}",
            err=True,
        )
        raise typer.Exit(1)
    try:
        return factory()
    except DataSourceUnavailableError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error


def _regime_windows(universe: Universe) -> tuple[int, int]:
    """Market regime for the whole portfolio: the market proxy's volatility over a month
    of sessions, ranked against its last year of them (30 and 365 days for crypto)."""
    return round(universe.periods_per_year / 12), universe.periods_per_year


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
    version: bool = typer.Option(False, "--version", callback=_version_callback, is_eager=True),
) -> None:
    pass


def _fetch_market_data(
    provider: DataProvider,
    universe: Universe,
    parameters: StudyParameters,
    start: date,
    end: date,
) -> MarketData:
    """History from the hypothesis's warm-up before `start`, so a signal can exist
    from the window's first day where data allows; nothing after `end` is
    requested. Bars come adjusted for corporate actions and ended by delistings,
    unknown delisting returns taking the definition's assumption (q5). Only the
    window's members and the market proxy are fetched (REQ-505).
    """
    fetch_start = start - timedelta(days=parameters.warm_up_days)
    instruments = universe.instruments_between(start, end)
    bars = {
        instrument.id: provider.fetch(instrument, fetch_start, end) for instrument in instruments
    }
    events = {
        instrument.id: provider.events(instrument, fetch_start, end) for instrument in instruments
    }
    return with_events(bars, events, parameters.missing_delisting_return)


def _fetch_bars(
    provider: DataProvider,
    universe: Universe,
    parameters: StudyParameters,
    start: date,
    end: date,
) -> dict[str, list[PriceBar]]:
    return _fetch_market_data(provider, universe, parameters, start, end).bars


def _strategy(parameters: StudyParameters, universe: Universe) -> Strategy:
    """The hypothesis's strategy, seeing only the universe's members on each date (REQ-503)."""
    return MembersOnly(parameters.build_strategy(), universe)


@dataclass(frozen=True)
class _TestInputs:
    """What a significance test may need: the run's bars and the hypothesis behind it."""

    bars: dict[str, list[PriceBar]]
    parameters: StudyParameters
    universe: Universe
    n_permutations: int
    alpha: float


# Significance tests by the name a success criterion gives (REQ-563); a new test is
# a new entry here, never a branch on the strategy.
_SIGNIFICANCE_TESTS: dict[SignificanceTest, Callable[[_TestInputs], Validator]] = {
    "day_shuffle": lambda given: PermutationTestValidator(
        bars=given.bars,
        n_permutations=given.n_permutations,
        alpha=given.alpha,
        periods_per_year=given.universe.periods_per_year,
    ),
    "random_portfolio": lambda given: RandomPortfolioValidator(
        bars=given.bars,
        strategy=_strategy(given.parameters, given.universe),
        sizer=given.parameters.build_sizer(),
        rebalance=given.parameters.build_rebalance_policy(),
        n_permutations=given.n_permutations,
        alpha=given.alpha,
        periods_per_year=given.universe.periods_per_year,
    ),
}


class _Wording(NamedTuple):
    title: str
    draws: str
    null_mean: str
    beaten: str


# How each significance test reads in the output.
_TEST_WORDING: dict[str, _Wording] = {
    "day_shuffle": _Wording(
        "Permutation test",
        "shuffles of returns against the positions held",
        "shuffled mean",
        "shuffles",
    ),
    "random_portfolio": _Wording(
        "Random-portfolio test",
        "random portfolios from each decision's cross-section",
        "random-portfolio mean",
        "random portfolios",
    ),
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
        strategy=_strategy(parameters, universe),
        cost_model=cost_model,
        bars=bars,
        universe_name=universe.name,
        start=start,
        end=end,
        seed=seed,
        git_sha=git_sha,
        strategy_name=parameters.strategy,
        strategy_params=parameters.strategy_params(),
        sizer=parameters.build_sizer(),
        rebalance=parameters.build_rebalance_policy(),
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
    bars = _fetch_bars(provider, universe, parameters, start, end)
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
    bars = _fetch_bars(provider, universe, parameters, start, end)
    return [
        _run_study(bars, parameters, cost_model, universe, start, end, seed, git_sha)
        for cost_model in cost_models
    ]


class EngineComparison(BaseModel):
    rows: list[EngineComparisonRow]
    parity_difference: float  # vectorized vs event-driven close t, in normalized equity
    capacity: float | None  # of the event-driven open t+1 run, in currency


def run_engine_comparison(
    provider: DataProvider,
    parameters: StudyParameters,
    universe: Universe,
    start: date,
    end: date,
    seed: int,
    git_sha: str,
    capital: float,
    max_participation: float,
) -> EngineComparison:
    """The hypothesis under both engines and each execution mode (REQ-250).

    Data is fetched once, with the same warm-up and end as a training run, and
    every run uses the hypothesis's own cost model.
    """
    bars = _fetch_bars(provider, universe, parameters, start, end)
    cost_model = parameters.cost_model.build()
    vectorized = _run_study(bars, parameters, cost_model, universe, start, end, seed, git_sha)

    def event_driven(execution: ExecutionModel, fills: FillPolicy) -> EventDrivenResult:
        return run_event_driven(
            strategy=_strategy(parameters, universe),
            cost_model=cost_model,
            bars=bars,
            universe_name=universe.name,
            start=start,
            end=end,
            seed=seed,
            git_sha=git_sha,
            strategy_name=parameters.strategy,
            strategy_params=parameters.strategy_params(),
            execution=execution,
            fill_policy=fills,
            capital=capital,
            sizer=parameters.build_sizer(),
            rebalance=parameters.build_rebalance_policy(),
        )

    close = event_driven(CloseExecution(), FullFill())
    next_open = event_driven(NextBarExecution("open"), FullFill())
    next_close = event_driven(NextBarExecution("close"), FullFill())
    limited = event_driven(NextBarExecution("open"), VolumeParticipationFill(max_participation))
    event_driven_rows = [
        ("event-driven, close t", close),
        ("event-driven, open t+1", next_open),
        ("event-driven, close t+1", next_close),
        (f"event-driven, open t+1, {max_participation:.1%} vol", limited),
    ]
    return EngineComparison(
        rows=[
            comparison_row("vectorized, close t", vectorized, None, universe.periods_per_year),
            *(
                comparison_row(label, result.run, result.orders, universe.periods_per_year)
                for label, result in event_driven_rows
            ),
        ],
        parity_difference=max_equity_difference(vectorized, close.run),
        capacity=capacity(next_open.orders, bars, capital, max_participation),
    )


class TrialResult(BaseModel):
    trial: Trial
    deflation: MultipleTesting


class TrialsComparison(BaseModel):
    trials: list[TrialResult]
    pbo: PboResult | None  # None with fewer than 2 trials or too few common days
    common_days: int
    common_start: date | None


def run_trials(
    provider: DataProvider, trials: list[Trial], seed: int, git_sha: str
) -> TrialsComparison:
    """Each trial over its own training period, from its committed definition (REQ-641).

    Each trial fetches only its own training data (with its warm-up) and runs
    under its own realistic cost model; PBO compares their net daily returns on
    the dates all of them hold a position.
    """
    runs, universes = [], []
    for trial in trials:
        definition = trial.definition
        parameters = definition.parameters
        universe = Universe.load(parameters.universe)
        universes.append(universe)
        runs.append(
            run_study(
                provider,
                parameters,
                parameters.cost_model.build(),
                universe,
                definition.training_start,
                definition.training_end,
                seed,
                git_sha,
            )
        )
    dates, returns = aligned_active_returns(runs)
    pbo = None
    if len(trials) >= 2 and len(dates) >= _PBO_BLOCKS:
        pbo = probability_of_backtest_overfitting(returns, _PBO_BLOCKS)
    return TrialsComparison(
        trials=[
            TrialResult(
                trial=trial,
                deflation=multiple_testing(run, trials, universe.periods_per_year),
            )
            for trial, run, universe in zip(trials, runs, universes, strict=True)
        ],
        pbo=pbo,
        common_days=len(dates),
        common_start=dates[0] if dates else None,
    )


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
    bars = _fetch_bars(provider, universe, parameters, config.start, config.end)
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
    metrics = run_metrics(run, universe.periods_per_year)
    criterion = config.success_criterion
    permutation = _SIGNIFICANCE_TESTS[criterion.significance_test](
        _TestInputs(bars, parameters, universe, n_permutations, criterion.max_p_value)
    ).validate(run)
    p_value = permutation.detail.get("p_value")  # absent when there was nothing to test

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


def _fmt_ratio(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def _fmt_pct(value: float | None, pattern: str = ".2%") -> str:
    return "n/a" if value is None else format(value, pattern)


def _in_order(groups: dict[str, PnlGroup], order: tuple[str, ...]) -> dict[str, PnlGroup]:
    return {key: groups[key] for key in order if key in groups}


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
    contrast: Annotated[
        str | None,
        typer.Option(
            help="Also correlate the realistic-cost run's daily net returns with this "
            "hypothesis's, over its own committed definition."
        ),
    ] = None,
) -> None:
    """Run a hypothesis under each cost model, over its training period only.

    Its holdout is never fetched here; that happens once, in open-holdout.
    """
    frozen = _load_definition(hypothesis)
    # Both definitions are checked before any data is fetched (REQ-303).
    contrast_definition = _load_definition(contrast).config if contrast is not None else None
    config = frozen.config
    git_sha = _current_git_sha()
    parameters = config.parameters
    universe = Universe.load(parameters.universe)
    provider = _provider(universe)
    periods_per_year = universe.periods_per_year
    market_proxy = universe.market_proxy
    if market_proxy is None:
        typer.echo(
            f"Error: universe {universe.name} names no market_proxy for regimes and stress",
            err=True,
        )
        raise typer.Exit(1)
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
        git_sha=git_sha,
    )
    metrics = [run_metrics(result, periods_per_year) for result in runs]
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
        ("CAGR", lambda m: _fmt_pct(m.cagr)),
        ("Sharpe", lambda m: _fmt_ratio(m.sharpe)),
        ("Sortino", lambda m: _fmt_ratio(m.sortino)),
        ("Calmar", lambda m: _fmt_ratio(m.calmar)),
        ("Max drawdown", lambda m: _fmt_pct(m.max_drawdown)),
        ("Turnover", lambda m: f"{m.turnover:.1f}x/yr"),
    ]
    for label, fmt in rows:
        typer.echo(f"{label:<14}" + "".join(f"{fmt(m):>{width}}" for m in metrics))

    typer.echo("")
    meaning = {
        "robust": "result is robust to cost assumptions",
        "cost-dependent": "result depends on cost assumptions - report as a limitation",
        "undefined": "no Sharpe to compare (no variance: no positions held?)",
    }[sensitivity.verdict]
    typer.echo(
        f"Cost sensitivity ({sensitivity.lower_cost_model} vs {sensitivity.higher_cost_model}): "
        f"Sharpe difference {_fmt_ratio(sensitivity.sharpe_difference)}"
        f"{', CAGR changes sign' if sensitivity.cagr_sign_flip else ''} "
        f"-> {sensitivity.verdict}: {meaning}"
    )

    walk_forward = WalkForwardValidator(periods_per_year).validate(runs[2])
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
    market = _fetch_market_data(
        provider, universe, parameters, config.training_start, config.training_end
    )
    bars = market.bars
    if market.delistings:
        assumed = market.assumed_delistings
        typer.echo("")
        typer.echo(
            f"Delistings in the data: {len(market.delistings)}"
            + (
                f", {assumed} at the definition's assumed return "
                f"{parameters.missing_delisting_return:+.0%} (source gave none)"
                if assumed
                else ", all with the source's delisting return"
            )
        )
        if assumed and parameters.missing_delisting_return != _DELISTING_STRESS_RETURN:
            stressed_run = _run_study(
                with_assumed_return(market, _DELISTING_STRESS_RETURN).bars,
                parameters,
                parameters.cost_model.build(),
                universe,
                config.training_start,
                config.training_end,
                _SEED,
                git_sha,
            )
            stressed_metrics = run_metrics(stressed_run, periods_per_year)
            typer.echo(
                f"At an assumed delisting return of {_DELISTING_STRESS_RETURN:+.0%} "
                f"(Shumway 1997) instead ({runs[2].cost_model_name}): Sharpe "
                f"{_fmt_ratio(stressed_metrics.sharpe)} vs {_fmt_ratio(metrics[2].sharpe)}, "
                f"CAGR {_fmt_pct(stressed_metrics.cagr)} vs {_fmt_pct(metrics[2].cagr)}"
            )
            typer.echo("Descriptive only: not part of any pass rule or of the hypothesis verdict.")
    if not universe.is_static:
        coverage = price_coverage(universe, bars, config.training_start, config.training_end)
        typer.echo("")
        typer.echo(
            f"Price coverage of the point-in-time universe: {_fmt_pct(coverage.share, '.1%')} "
            f"of member-days ({coverage.priced_days:,} of {coverage.member_days:,})"
        )
        if coverage.without_prices:
            typer.echo(
                f"Members without any price in the source ({len(coverage.without_prices)}), "
                f"invisible to the strategy: {', '.join(coverage.without_prices)}"
            )
    permutation = _SIGNIFICANCE_TESTS[config.success_criterion.significance_test](
        _TestInputs(bars, parameters, universe, _PERMUTATIONS, _PERMUTATION_ALPHA)
    ).validate(runs[2])
    detail = permutation.detail
    wording = _TEST_WORDING[detail["test"]]
    typer.echo("")
    typer.echo(
        f"{wording.title} ({detail['n_permutations']:,} {wording.draws}, seed {detail['seed']}):"
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
            f"Gross Sharpe {detail['actual']:.2f} vs {wording.null_mean} "
            f"{detail['null_mean']:.2f} (sd {detail['null_std']:.2f}); "
            f"beats {detail['percentile']:.1%} of {wording.beaten}"
        )
        typer.echo(f"Result: p = {detail['p_value']:.4f}, {significance}")
    if detail["low_confidence"]:
        typer.echo(f"Low confidence: only {detail['active_days']} days with a position")

    diagnostics = parameters.training_diagnostics(bars, config.training_start, config.training_end)
    for diagnostic in diagnostics:
        typer.echo("")
        typer.echo(
            f"{diagnostic.title} (training {config.training_start} .. {config.training_end}):"
        )
        typer.echo(
            "; ".join(
                f"{label} {'n/a' if value is None else format(value, '.4g')}"
                for label, value in diagnostic.values.items()
            )
        )
        typer.echo("Descriptive only: not part of any pass rule or of the hypothesis verdict.")

    deflation = multiple_testing(
        runs[2],
        trials_on_same_data(config.hypothesis, registered_trials(_HOLDOUT_DIR)),
        periods_per_year,
    )
    typer.echo("")
    typer.echo(
        f"Multiple testing ({runs[2].cost_model_name}, net daily returns from the first "
        f"position, {deflation.n_returns} days):"
    )
    typer.echo(
        f"Trials on this universe and training period: {len(deflation.trials)} "
        f"({', '.join(deflation.trials)})"
    )
    typer.echo(
        f"Sharpe {_fmt_ratio(deflation.sharpe_annualized)}; PSR(0) {_fmt_ratio(deflation.psr)}; "
        f"best of {len(deflation.trials)} no-edge trials expected at Sharpe "
        f"{_fmt_ratio(deflation.threshold_annualized)} -> DSR {_fmt_ratio(deflation.dsr)}"
    )
    typer.echo("Descriptive only: not part of any pass rule or of the hypothesis verdict.")

    vol_window, regime_history = _regime_windows(universe)
    classifier = VolatilityTercileClassifier(vol_window=vol_window, history_days=regime_history)
    labels = label_periods(
        classifier, bars[market_proxy], [snapshot.ts for snapshot in runs[2].snapshots]
    )
    by_regime = regime_conditional_metrics(runs[2], labels, periods_per_year)
    total_days = sum(regime.days for regime in by_regime.values())
    typer.echo("")
    typer.echo(
        f"Regimes ({runs[2].cost_model_name}): {market_proxy} {vol_window}-session "
        f"volatility tercile vs its last {regime_history} sessions, "
        "as of the session before each return"
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

    instrument_ids = list(bars)
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
        worst_day_scenario(
            f"worst-{market_proxy.split('-')[0]}-day",
            bars,
            market_proxy,
            runs[2].start,
            runs[2].end,
        ),
    ]
    typer.echo("")
    typer.echo(
        f"Stress test ({runs[2].cost_model_name}): instantaneous shock, "
        "impact = sum of weight x shock, costs of reacting not included"
    )
    if first_position is None:
        typer.echo("n/a: no positions were held")
    else:
        stress = [stress_run(runs[2], scenario) for scenario in scenarios]
        typer.echo(
            f"{'Scenario':<16}{'Last day':>10}{'Worst':>10}{'Worst held on':>15}{'Losing days':>13}"
        )
        for result in stress:
            typer.echo(
                f"{result.scenario.name:<16}{result.last_impact:>10.2%}"
                f"{result.worst_impact:>10.2%}{result.worst_held_on!s:>15}"
                f"{result.losing_share:>13.1%}"
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
        f"({open_at_end} open at the end), "
        f"{_fmt_pct(winners / len(trades) if trades else None, '.1%')} with net P&L > 0"
    )
    typer.echo(
        f"Net P&L of all trades {sum(trade.net_pnl for trade in trades):+.4f} "
        f"= equity change {equity_change:+.4f} (P&L in equity units, portfolio started at 1.00)"
    )
    header = (
        f"{'Trades':>7}{'Win rate':>10}{'Total':>10}{'Mean':>10}{'Median':>10}"
        f"{'Worst':>10}{'Best':>10}{'Costs':>9}"
    )

    def _print_groups(title: str, groups: dict[str, PnlGroup]) -> None:
        typer.echo(f"{title:<12}{header}")
        for key, group in groups.items():
            typer.echo(
                f"{key:<12}{group.trades:>7}{group.win_rate:>10.1%}{group.total_net_pnl:>+10.4f}"
                f"{group.mean_net_pnl:>+10.4f}{group.median_net_pnl:>+10.4f}"
                f"{group.worst_net_pnl:>+10.4f}{group.best_net_pnl:>+10.4f}{group.costs:>9.4f}"
            )

    pnl_groups = {
        "regime": _in_order(group_pnl(trades, by_regime_at_entry), VOLATILITY_REGIMES),
        "holding_period": _in_order(group_pnl(trades, by_holding_period), HOLDING_PERIOD_BUCKETS),
    }
    _print_groups("Regime", pnl_groups["regime"])
    _print_groups("Holding", pnl_groups["holding_period"])
    typer.echo("Regime = market regime as of the entry close. Descriptive only.")

    contrast_result = None
    if contrast_definition is not None:
        other = contrast_definition.parameters
        other_run = run_study(
            provider,
            other,
            other.cost_model.build(),
            Universe.load(other.universe),
            contrast_definition.training_start,
            contrast_definition.training_end,
            _SEED,
            git_sha,
        )
        contrast_result = Contrast(
            hypothesis=contrast_definition.hypothesis,
            cost_model_name=other_run.cost_model_name,
            correlation=return_correlation(runs[2], other_run),
        )
        correlation = contrast_result.correlation
        shown = "n/a" if correlation is None else f"{correlation:+.2f}"
        typer.echo("")
        typer.echo(
            f"Contrast with {contrast_result.hypothesis} ({other_run.cost_model_name}, "
            f"training {other_run.start} .. {other_run.end}): correlation of daily net returns "
            f"on days both held a position {shown}"
        )
        typer.echo("Descriptive only: not part of any pass rule or of the hypothesis verdict.")

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

    sheet = TearSheet(
        hypothesis=config.hypothesis,
        run=runs[2],
        cost_comparison=metrics,
        regimes=by_regime,
        regime_method=(
            f"Reżim rynku: tercyl zmienności {market_proxy} z {vol_window} sesji "
            f"względem jej wartości z ostatnich {regime_history} sesji, "
            "na sesję przed każdym zwrotem."
        ),
        walk_forward=walk_forward,
        permutation=permutation,
        holdout=holdout,
        contrast=contrast_result,
        multiple_testing=deflation,
        generated_at=datetime.now(tz=UTC),
    )
    stored = write_run(
        _RESULTS_DIR,
        RunEvidence(
            sheet=sheet,
            cost_sensitivity=sensitivity,
            trades=trades,
            pnl_groups=pnl_groups,
            diagnostics=diagnostics,
            data_source=",".join(
                sorted({bar.source for series in bars.values() for bar in series})
            ),
        ),
    )
    write_registry(_RESULTS_DIR, _HOLDOUT_DIR)
    typer.echo("")
    typer.echo(f"Results written to {stored} (registry: {_RESULTS_DIR / REGISTRY_FILE})")

    if tear_sheet is not None:
        tear_sheet.parent.mkdir(parents=True, exist_ok=True)
        tear_sheet.write_text(render_html(sheet), encoding="utf-8")
        typer.echo("")
        typer.echo(f"Tear-sheet written to {tear_sheet}")


@app.command("compare-engines")
def compare_engines(
    hypothesis: Annotated[str, _HYPOTHESIS_ARGUMENT] = _DEFAULT_HYPOTHESIS,
) -> None:
    """Compare execution assumptions on a hypothesis's training period.

    Descriptive only: its holdout is never fetched and no status changes;
    validation and verdicts stay on the vectorized engine (REQ-253).
    """
    frozen = _load_definition(hypothesis)
    config = frozen.config
    parameters = config.parameters
    git_sha = _current_git_sha()
    universe = Universe.load(parameters.universe)
    comparison = run_engine_comparison(
        provider=_provider(universe),
        parameters=parameters,
        universe=universe,
        start=config.training_start,
        end=config.training_end,
        seed=_SEED,
        git_sha=git_sha,
        capital=_NOMINAL_CAPITAL,
        max_participation=_MAX_PARTICIPATION,
    )

    typer.echo(f"Hypothesis:     {config.hypothesis} (defined at {frozen.frozen_at_commit[:7]})")
    typer.echo(f"Universe:       {parameters.universe}")
    typer.echo(f"Strategy:       {parameters.strategy} {parameters.strategy_params()}")
    typer.echo(f"Period:         {config.training_start} .. {config.training_end} (training only)")
    typer.echo(f"Cost model:     {comparison.rows[0].metrics.cost_model_name}")
    typer.echo(
        f"Capital:        {_NOMINAL_CAPITAL:,.0f} (nominal: sizes orders against volume; "
        "results are normalized)"
    )
    typer.echo(f"Git:            {git_sha[:7]}")
    typer.echo("")
    typer.echo(
        f"{'Engine, execution':<36}{'CAGR':>9}{'Sharpe':>8}{'Max DD':>9}"
        f"{'Turnover':>12}{'Costs':>8}{'Limited':>9}"
    )
    for row in comparison.rows:
        metrics = row.metrics
        limited = "n/a" if row.limited_orders is None else str(row.limited_orders)
        typer.echo(
            f"{row.label:<36}{_fmt_pct(metrics.cagr):>9}{_fmt_ratio(metrics.sharpe):>8}"
            f"{_fmt_pct(metrics.max_drawdown):>9}{f'{metrics.turnover:.1f}x/yr':>12}"
            f"{row.total_costs:>8.2%}{limited:>9}"
        )
    typer.echo(
        "Costs = all costs as a share of starting capital. "
        "Limited = orders filled for less than ordered."
    )

    typer.echo("")
    difference = comparison.parity_difference
    note = (
        "numerical noise only"
        if difference <= _PARITY_NOISE
        else "above numerical noise: the engines treat missing bars differently (see q2 02-spec)"
    )
    typer.echo(
        f"Parity (vectorized vs event-driven, close t): max equity difference "
        f"{difference:.1e} - {note}"
    )
    if comparison.capacity is None:
        typer.echo("Capacity: n/a (no filled orders)")
    else:
        typer.echo(
            f"Capacity (event-driven, open t+1): the {_MAX_PARTICIPATION:.1%} volume limit "
            f"first binds above a capital of {comparison.capacity:,.0f}"
        )
    typer.echo(
        "Descriptive only: validation and verdicts stay on the vectorized engine "
        "and the frozen rules."
    )


@app.command("trials")
def trials_command(
    hypothesis: Annotated[str, _HYPOTHESIS_ARGUMENT] = _DEFAULT_HYPOTHESIS,
) -> None:
    """Every trial on a hypothesis's data: Sharpe, PSR and DSR each, and PBO of picking one.

    A trial is any hypothesis whose definition was ever committed, deleted ones
    included. Training periods only; descriptive, no status changes.
    """
    target = _load_definition(hypothesis).config
    try:
        trials = trials_on_same_data(hypothesis, registered_trials(_HOLDOUT_DIR))
    except TrialRegistryError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error
    # Every trial still on disk must match its committed version (REQ-642).
    for trial in (trial for trial in trials if not trial.deleted):
        try:
            load_frozen_holdout(_HOLDOUT_DIR / trial.path)
        except HoldoutNotFrozenError as error:
            typer.echo(f"Error: {error}", err=True)
            raise typer.Exit(1) from error

    provider = _provider(Universe.load(target.parameters.universe))
    comparison = run_trials(provider, trials, _SEED, _current_git_sha())

    typer.echo(
        f"Trials on {target.parameters.universe} with a training period overlapping "
        f"{hypothesis}'s ({target.training_start} .. {target.training_end}): {len(trials)}"
    )
    width = max(len(trial.hypothesis) for trial in trials) + 3
    typer.echo(
        f"{'Trial':<{width}}{'Registered':<12}{'Training':<26}{'Days':>6}{'Sharpe':>8}"
        f"{'PSR(0)':>8}{'Threshold':>11}{'DSR':>7}"
    )
    for result in comparison.trials:
        trial, deflation = result.trial, result.deflation
        name = trial.hypothesis + ("*" if trial.deleted else "")
        typer.echo(
            f"{name:<{width}}{trial.registered_at:%Y-%m-%d}  "
            f"{f'{trial.training_start} .. {trial.training_end}':<26}{deflation.n_returns:>6}"
            f"{_fmt_ratio(deflation.sharpe_annualized):>8}{_fmt_ratio(deflation.psr):>8}"
            f"{_fmt_ratio(deflation.threshold_annualized):>11}{_fmt_ratio(deflation.dsr):>7}"
        )
    typer.echo(
        "Net daily returns from each trial's first position under its own cost model; "
        f"Sharpe annualized. Threshold = expected best Sharpe of {len(trials)} no-edge trials."
    )
    if any(trial.deleted for trial in trials):
        typer.echo(
            "* definition deleted since; still a trial, run from its last committed version."
        )

    typer.echo("")
    pbo = comparison.pbo
    if pbo is None:
        reason = (
            "needs at least 2 trials"
            if len(trials) < 2
            else f"only {comparison.common_days} days on which every trial holds a position"
        )
        typer.echo(f"PBO: n/a ({reason})")
    else:
        typer.echo(
            f"PBO of picking the best trial in-sample: {pbo.pbo:.2f} (CSCV: {pbo.n_blocks} "
            f"blocks, {pbo.n_splits:,} splits, {pbo.rows_used:,} of {comparison.common_days:,} "
            f"common days from {comparison.common_start}; median logit {pbo.logit_median:+.2f})"
        )
        if pbo.n_configurations == 2:
            typer.echo(
                "With 2 trials, PBO is the share of splits in which the in-sample winner is "
                "the out-of-sample loser."
            )
    typer.echo("Descriptive only: not part of any pass rule or of any hypothesis verdict.")


def _print_holdout(record: HoldoutRecord) -> None:
    permutation = record.permutation
    # Records opened before q5 name no test: they come from the day shuffle.
    wording = _TEST_WORDING[permutation.get("test", "day_shuffle")]
    typer.echo("")
    typer.echo(f"HOLDOUT {record.start} .. {record.end} ({record.hypothesis})")
    typer.echo(f"Frozen at:      {record.frozen_at_commit[:7]}")
    typer.echo(
        f"Opened at:      {record.opened_at:%Y-%m-%d %H:%M} UTC, commit {record.opened_at_commit[:7]}"
    )
    typer.echo(f"Cost model:     {record.cost_model_name}")
    typer.echo("")
    typer.echo(f"CAGR:           {_fmt_pct(record.cagr):>8}")
    typer.echo(f"Sharpe (net):   {_fmt_ratio(record.sharpe):>8}")
    typer.echo(f"Sortino:        {_fmt_ratio(record.sortino):>8}")
    typer.echo(f"Calmar:         {_fmt_ratio(record.calmar):>8}")
    typer.echo(f"Max drawdown:   {_fmt_pct(record.max_drawdown):>8}")
    typer.echo("")
    if "reason" in permutation:
        typer.echo(f"Permutation:    inconclusive ({permutation['reason']})")
    else:
        typer.echo(
            f"Permutation:    gross Sharpe {permutation['actual']:.2f} vs {wording.null_mean} "
            f"{permutation['null_mean']:.2f}; p = {record.p_value:.4f} "
            f"({permutation['n_permutations']:,} {wording.beaten}, seed {permutation['seed']})"
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
        frozen = _load_definition(hypothesis)
        record = open_frozen_holdout(
            provider=_provider(Universe.load(frozen.config.parameters.universe)),
            frozen=frozen,
            record_path=record_path,
            n_permutations=_PERMUTATIONS,
            seed=_SEED,
            git_sha=_current_git_sha(),
            opened_at=datetime.now(tz=UTC),
        )
        typer.echo(f"Holdout opened. Result recorded in {record_path} - commit it.")
    _print_holdout(record)
    try:
        write_registry(_RESULTS_DIR, _HOLDOUT_DIR)
    except TrialRegistryError as error:
        typer.echo(f"Registry not refreshed: {error}", err=True)


def _listed(entries: list, show) -> str:
    return "; ".join(show(entry) for entry in entries) if entries else "none"


@app.command("build-universe")
def build_universe_command() -> None:
    """Rebuild the S&P 500 point-in-time universe from its pinned Wikipedia revision.

    Reads today's constituents and the table of changes of the last revision before
    the pinned instant, walks back through the changes (REQ-553), and writes
    quantlab/config/universes/sp500.yaml with the attribution CC BY-SA 4.0 asks for.
    Then lists what the table contradicts: fix tickers in sp500-renames.yaml,
    rebuild, and commit both files before the hypothesis is frozen.
    """
    renames = sp500.load_renames(
        (_UNIVERSES_DIR / "sp500-renames.yaml").read_text(encoding="utf-8")
    )
    revision = sp500.fetch_revision(sp500.PINNED_AS_OF)
    page = sp500.parse_page(revision.html)
    as_of = sp500.PINNED_AS_OF.date()
    reconstruction = sp500.reconstruct(page, renames, sp500.DEFAULT_SINCE, as_of)
    universe = sp500.universe_from(reconstruction, as_of)
    target = _UNIVERSES_DIR / f"{sp500.UNIVERSE_NAME}.yaml"
    target.write_text(
        sp500.universe_yaml(universe, revision, sp500.DEFAULT_SINCE), encoding="utf-8"
    )

    typer.echo(
        f"Wikipedia revision {revision.id} ({revision.timestamp}): "
        f"{len(page.constituents)} constituents, {len(page.changes)} changes"
    )
    typer.echo(
        f"Universe {universe.name}: {len(universe.instruments) - 1} tickers and "
        f"{sp500.MARKET_PROXY.symbol}, {len(universe.memberships)} membership periods "
        f"from {sp500.DEFAULT_SINCE} -> {target}"
    )
    typer.echo("")
    typer.echo("To check (renames go to sp500-renames.yaml; then rebuild):")
    typer.echo(
        f"Added but not in the index afterwards ({len(reconstruction.added_but_not_in_index)}): "
        + _listed(reconstruction.added_but_not_in_index, lambda e: f"{e[0]} {e[1]}")
    )
    typer.echo(
        "Removed but still in the index afterwards "
        f"({len(reconstruction.removed_but_still_in_index)}): "
        + _listed(reconstruction.removed_but_still_in_index, lambda e: f"{e[0]} {e[1]}")
    )
    typer.echo(
        "Date added on the page differs from the reconstruction "
        f"({len(reconstruction.date_added_mismatches)}): "
        + _listed(
            reconstruction.date_added_mismatches, lambda e: f"{e[0]} page {e[1]}, rebuilt {e[2]}"
        )
    )
    typer.echo(
        f"Tickers with more than one period ({len(reconstruction.several_periods)}), "
        "a reused ticker is two companies: " + _listed(reconstruction.several_periods, str)
    )
    typer.echo(
        f"Rows of the table of changes without a readable date "
        f"({len(reconstruction.unreadable_rows)}): " + _listed(reconstruction.unreadable_rows, str)
    )


def _holdout_state(row: RegistryRow) -> str:
    if row.holdout is None:
        return f"sealed {row.holdout_start}..{row.holdout_end}"
    return f"opened {row.holdout.opened_at:%Y-%m-%d}: {row.holdout.verdict}"


@app.command("registry")
def registry_command() -> None:
    """Refresh the results store's hypothesis registry from the committed definitions.

    Reads config/holdout, the holdout records next to it and git history; fetches
    no data (REQ-712). The presentation layer reads the registry it writes.
    """
    try:
        rows = write_registry(_RESULTS_DIR, _HOLDOUT_DIR)
    except TrialRegistryError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error
    width = max((len(row.hypothesis) for row in rows), default=10) + 2
    typer.echo(f"{'Hypothesis':<{width}}{'Status':<14}{'Stored run':<12}Holdout")
    for row in rows:
        typer.echo(
            f"{row.hypothesis:<{width}}{row.status:<14}{'yes' if row.has_run else 'no':<12}"
            f"{_holdout_state(row)}"
        )
    typer.echo(f"Registry written to {_RESULTS_DIR / REGISTRY_FILE}")
