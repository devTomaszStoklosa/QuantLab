import math
import statistics
from datetime import date, timedelta

import pytest

from quantlab.backtest.vectorized.engine import run
from quantlab.core.data.provider import PriceBar
from quantlab.reporting.metrics import sharpe
from quantlab.strategy.signal import Signal

_PERIODS_PER_YEAR = 365
_START = date(2026, 1, 1)


class _AlwaysLongStrategy:
    """Buy-and-hold test double: long on a single instrument, every day."""

    def __init__(self, instrument_id: str) -> None:
        self._instrument_id = instrument_id

    def generate_signals(self, bars: dict, as_of: date) -> list[Signal]:
        return [Signal(instrument_id=self._instrument_id, ts=as_of, direction="long", strength=0.0)]


def _bar(instrument_id: str, ts: date, close: float) -> PriceBar:
    return PriceBar(
        instrument_id=instrument_id,
        ts=ts,
        open=close,
        high=close,
        low=close,
        close=close,
        volume=1.0,
        adj_close=None,
        source="test",
    )


def test_buy_and_hold_sharpe_matches_analytically_expected_value() -> None:
    # Deterministic, exactly-reproducible synthetic trend (a literally constant
    # per-period return would give zero variance and an undefined Sharpe).
    period_returns = [0.04, -0.02, 0.04, -0.02]
    prices = [100.0]
    for period_return in period_returns:
        prices.append(prices[-1] * (1.0 + period_return))

    bars = {
        "a": [_bar("a", _START + timedelta(days=i), price) for i, price in enumerate(prices)]
    }
    strategy = _AlwaysLongStrategy("a")

    result = run(
        strategy=strategy,
        bars=bars,
        universe_name="golden-master",
        start=_START,
        end=_START + timedelta(days=len(period_returns)),
        seed=1,
        git_sha="golden",
        strategy_name="always-long",
        strategy_params={},
    )

    equity = [snapshot.equity for snapshot in result.snapshots]
    realized_returns = [equity[i] / equity[i - 1] - 1.0 for i in range(1, len(equity))]

    expected_sharpe = (
        statistics.mean(period_returns)
        / statistics.stdev(period_returns)
        * math.sqrt(_PERIODS_PER_YEAR)
    )

    assert realized_returns == pytest.approx(period_returns)
    assert sharpe(realized_returns, _PERIODS_PER_YEAR) == pytest.approx(expected_sharpe)
