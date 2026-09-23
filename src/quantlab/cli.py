import importlib.metadata
import subprocess
from datetime import date, timedelta

import typer

from quantlab.backtest.vectorized.engine import BacktestRun
from quantlab.backtest.vectorized.engine import run as run_backtest
from quantlab.core.data.binance import BinanceProvider
from quantlab.core.data.provider import DataProvider
from quantlab.core.universe import Universe
from quantlab.reporting.metrics import cagr, calmar, max_drawdown, sharpe, sortino
from quantlab.strategy.time_series_momentum import TimeSeriesMomentum

app = typer.Typer()

_UNIVERSE_NAME = "mvp-crypto"
# Training period only. The 2024-01-01..2025-12-31 holdout is deliberately never
# fetched or evaluated here - it gets frozen (S10) before anything looks at it.
_TRAINING_START = date(2018, 1, 1)
_TRAINING_END = date(2023, 12, 31)
_LOOKBACK_DAYS = 365  # ~12-month formation period, Moskowitz/Ooi/Pedersen (2012)
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


def run_momentum_study(
    provider: DataProvider,
    universe: Universe,
    lookback_days: int,
    start: date,
    end: date,
    seed: int,
    git_sha: str,
) -> BacktestRun:
    """Fetch data, run time-series momentum through the vectorized engine.

    History is fetched from `lookback_days` before `start`, so a signal can
    exist from the first day of the window wherever the data allows it. That
    warm-up history precedes the window; nothing after `end` is requested.
    """
    fetch_start = start - timedelta(days=lookback_days)
    bars = {
        instrument.id: provider.fetch(instrument, fetch_start, end)
        for instrument in universe.instruments
    }
    return run_backtest(
        strategy=TimeSeriesMomentum(lookback_days=lookback_days),
        bars=bars,
        universe_name=universe.name,
        start=start,
        end=end,
        seed=seed,
        git_sha=git_sha,
        strategy_name="time_series_momentum",
        strategy_params={"lookback_days": lookback_days},
    )


def _current_git_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


@app.command()
def run() -> None:
    """Run the momentum study on the MVP basket, training period only."""
    result = run_momentum_study(
        provider=BinanceProvider(),
        universe=Universe.load(_UNIVERSE_NAME),
        lookback_days=_LOOKBACK_DAYS,
        start=_TRAINING_START,
        end=_TRAINING_END,
        seed=_SEED,
        git_sha=_current_git_sha(),
    )

    equity = [snapshot.equity for snapshot in result.snapshots]
    returns = [equity[i] / equity[i - 1] - 1.0 for i in range(1, len(equity))]
    first_position = next(
        (snapshot.ts for snapshot in result.snapshots if snapshot.positions), None
    )

    typer.echo(f"Run {result.id} (git {result.git_sha[:7]})")
    typer.echo(f"Universe:       {result.universe_name}")
    typer.echo(f"Strategy:       {result.strategy_name} {result.strategy_params}")
    typer.echo(f"Period:         {result.start} .. {result.end} (training only)")
    typer.echo(f"Cost model:     {result.cost_model_name}")
    typer.echo(f"First position: {first_position}")
    typer.echo("")
    typer.echo(f"CAGR:           {cagr(equity, _PERIODS_PER_YEAR):8.2%}")
    typer.echo(f"Sharpe:         {sharpe(returns, _PERIODS_PER_YEAR):8.2f}")
    typer.echo(f"Sortino:        {sortino(returns, _PERIODS_PER_YEAR):8.2f}")
    typer.echo(f"Calmar:         {calmar(equity, _PERIODS_PER_YEAR):8.2f}")
    typer.echo(f"Max drawdown:   {max_drawdown(equity):8.2%}")
