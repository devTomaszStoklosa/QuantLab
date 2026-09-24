from datetime import date, timedelta

from quantlab.backtest.vectorized.engine import run as run_backtest
from quantlab.core.data.provider import PriceBar
from quantlab.core.universe import Instrument, Membership, Universe
from quantlab.costs.zero import ZeroCostModel
from quantlab.strategy.members_only import MembersOnly
from quantlab.strategy.signal import Signal

_FIRST = date(2024, 1, 1)


def _bars(instrument_id: str, days: int = 10) -> list[PriceBar]:
    return [
        PriceBar(
            instrument_id=instrument_id,
            ts=_FIRST + timedelta(days=i),
            open=100.0 + i,
            high=100.0 + i,
            low=100.0 + i,
            close=100.0 + i,
            volume=1.0,
            source="test",
        )
        for i in range(days)
    ]


class _LongEverything:
    """Long every instrument it is shown; remembers what it saw."""

    def __init__(self) -> None:
        self.seen: dict[date, dict[str, list[PriceBar]]] = {}

    def generate_signals(self, bars: dict[str, list[PriceBar]], as_of: date) -> list[Signal]:
        self.seen[as_of] = bars
        return [
            Signal(instrument_id=instrument_id, ts=as_of, direction="long", strength=1.0)
            for instrument_id in sorted(bars)
        ]


def _universe(*memberships: Membership) -> Universe:
    ids = sorted({membership.instrument_id for membership in memberships})
    return Universe(
        name="pit",
        asof_date=_FIRST,
        source="synthetic",
        periods_per_year=252,
        instruments=[
            Instrument(id=i, symbol=i.upper(), asset_class="equity", quote_asset="USD") for i in ids
        ],
        memberships=list(memberships),
    )


def test_a_static_universe_passes_the_bars_through_untouched() -> None:
    inner = _LongEverything()
    bars = {"aaa": _bars("aaa"), "bbb": _bars("bbb")}
    static = Universe(
        name="static",
        asof_date=_FIRST,
        source="synthetic",
        periods_per_year=252,
        instruments=[
            Instrument(id=i, symbol=i, asset_class="crypto", quote_asset="USDT")
            for i in ("aaa", "bbb")
        ],
    )

    MembersOnly(inner, static).generate_signals(bars, _FIRST)

    assert inner.seen[_FIRST] is bars


def test_the_strategy_sees_only_the_members_of_the_signal_date() -> None:
    inner = _LongEverything()
    bars = {"aaa": _bars("aaa"), "bbb": _bars("bbb"), "ccc": _bars("ccc")}
    universe = _universe(
        Membership(instrument_id="aaa", start=_FIRST, end=None),
        Membership(instrument_id="bbb", start=_FIRST + timedelta(days=3), end=None),
        Membership(instrument_id="ccc", start=_FIRST, end=_FIRST + timedelta(days=4)),
    )
    strategy = MembersOnly(inner, universe)

    early = strategy.generate_signals(bars, _FIRST)
    late = strategy.generate_signals(bars, _FIRST + timedelta(days=5))

    assert set(inner.seen[_FIRST]) == {"aaa", "ccc"}
    assert [signal.instrument_id for signal in early] == ["aaa", "ccc"]
    assert [signal.instrument_id for signal in late] == ["aaa", "bbb"]


def test_a_backtest_holds_an_instrument_only_while_it_is_a_member() -> None:
    bars = {"aaa": _bars("aaa"), "bbb": _bars("bbb")}
    joins, leaves = _FIRST + timedelta(days=3), _FIRST + timedelta(days=6)
    universe = _universe(
        Membership(instrument_id="aaa", start=_FIRST, end=None),
        Membership(instrument_id="bbb", start=joins, end=leaves),
    )

    run = run_backtest(
        strategy=MembersOnly(_LongEverything(), universe),
        cost_model=ZeroCostModel(),
        bars=bars,
        universe_name="pit",
        start=_FIRST,
        end=_FIRST + timedelta(days=9),
        seed=0,
        git_sha="test",
        strategy_name="long_everything",
        strategy_params={},
    )

    # A position held over (t, t+1) is decided at t, so it is the membership on t that counts.
    held = {
        snapshot.ts - timedelta(days=1): set(snapshot.positions) for snapshot in run.snapshots[1:]
    }
    for decision, instruments in held.items():
        expected = {"aaa"} | ({"bbb"} if joins <= decision <= leaves else set())
        assert instruments == expected, decision
