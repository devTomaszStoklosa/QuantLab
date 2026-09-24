"""AC-2: the feed has no future, so no strategy can read one."""

import math
from datetime import date, timedelta
from itertools import pairwise

import pytest

from quantlab.backtest.event_driven.engine import run as event_driven_run
from quantlab.backtest.event_driven.execution import CloseExecution
from quantlab.backtest.event_driven.feed import BarFeed
from quantlab.backtest.vectorized.engine import run as vectorized_run
from quantlab.core.data.provider import PriceBar
from quantlab.costs.zero import ZeroCostModel
from quantlab.strategy.signal import Signal

_START = date(2026, 1, 1)


def _bar(instrument_id: str, day: int, close: float) -> PriceBar:
    return PriceBar(
        instrument_id=instrument_id,
        ts=_START + timedelta(days=day),
        open=close,
        high=close,
        low=close,
        close=close,
        volume=1.0,
        source="test",
    )


def test_feed_reveals_bars_up_to_the_current_date_only() -> None:
    # Deliberately out of order: the feed sorts.
    feed = BarFeed({"a": [_bar("a", 2, 102.0), _bar("a", 0, 100.0), _bar("a", 1, 101.0)]})

    assert feed.history() == {"a": []}
    assert feed.last_close("a") is None

    feed.advance(_START + timedelta(days=1))

    assert [bar.close for bar in feed.history()["a"]] == [100.0, 101.0]
    assert feed.bar("a").close == 101.0
    assert feed.last_close("a") == 101.0


def test_bar_is_none_on_a_date_the_instrument_did_not_trade() -> None:
    feed = BarFeed({"a": [_bar("a", 0, 100.0), _bar("a", 2, 102.0)], "b": [_bar("b", 1, 50.0)]})

    feed.advance(_START + timedelta(days=1))

    assert feed.bar("a") is None
    assert feed.last_close("a") == 100.0
    assert feed.bar("b").close == 50.0


def test_feed_only_moves_forward() -> None:
    feed = BarFeed({"a": [_bar("a", 0, 100.0)]})
    feed.advance(_START + timedelta(days=1))

    with pytest.raises(ValueError, match="only moves forward"):
        feed.advance(_START + timedelta(days=1))


class _PeekingStrategy:
    """Trades on tomorrow's close whenever the bars it is given contain it.

    Records the latest bar date it was shown on each call.
    """

    def __init__(self) -> None:
        self.latest_seen: list[tuple[date, date]] = []

    def generate_signals(self, bars: dict[str, list[PriceBar]], as_of: date) -> list[Signal]:
        history = bars["a"]
        self.latest_seen.append((as_of, max(bar.ts for bar in history)))
        today = next(bar for bar in history if bar.ts == as_of)
        tomorrow = next((bar for bar in history if bar.ts > as_of), None)
        if tomorrow is None:
            return [Signal(instrument_id="a", ts=as_of, direction="flat", strength=0.0)]
        direction = "long" if tomorrow.close > today.close else "short"
        return [Signal(instrument_id="a", ts=as_of, direction=direction, strength=0.0)]


def test_a_strategy_that_reads_ahead_finds_nothing_to_read() -> None:
    closes = [100.0, 110.0, 99.0, 120.0, 90.0, 95.0]
    bars = {"a": [_bar("a", day, close) for day, close in enumerate(closes)]}
    args = {
        "cost_model": ZeroCostModel(),
        "bars": bars,
        "universe_name": "peek",
        "start": _START,
        "end": _START + timedelta(days=len(closes) - 1),
        "seed": 0,
        "git_sha": "peek",
        "strategy_name": "peek",
        "strategy_params": {},
    }

    peeking = _PeekingStrategy()
    event_driven = event_driven_run(strategy=peeking, **args, execution=CloseExecution())

    assert all(latest <= as_of for as_of, latest in peeking.latest_seen)
    assert [snapshot.equity for snapshot in event_driven.run.snapshots] == [1.0] * len(closes)
    assert event_driven.orders == []

    # The vectorized engine hands over the whole history and trusts the strategy:
    # the same code earns every day's move in absolute value (perfect foresight).
    vectorized = vectorized_run(strategy=_PeekingStrategy(), **args)
    foresight = math.prod(1.0 + abs(b / a - 1.0) for a, b in pairwise(closes))
    assert vectorized.snapshots[-1].equity == pytest.approx(foresight)
