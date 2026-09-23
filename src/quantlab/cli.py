import importlib.metadata
import subprocess
from datetime import date, timedelta

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
_SEED = 0  # placeholder: nothing in the vectorized engine is random until S11
_PERIODS_PER_YEAR = 365  # crypto trades every calendar day


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
    runs = run_cost_comparison(
        provider=BinanceProvider(),
        cost_models=[ZeroCostModel(), naive, realistic],
        universe=Universe.load(_UNIVERSE_NAME),
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
