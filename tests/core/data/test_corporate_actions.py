from datetime import date, timedelta
from itertools import pairwise

import numpy as np
import pytest
from pydantic import TypeAdapter, ValidationError

from quantlab.core.data.corporate_actions import adjust_bars, with_events
from quantlab.core.data.events import (
    CashDividend,
    CorporateAction,
    Delisting,
    InstrumentEvents,
    Split,
)
from quantlab.core.data.provider import PriceBar

_FIRST = date(2024, 1, 1)


def _bars(closes: list[float], skip: set[int] | None = None) -> list[PriceBar]:
    return [
        PriceBar(
            instrument_id="aaa",
            ts=_FIRST + timedelta(days=i),
            open=close * 0.99,
            high=close * 1.01,
            low=close * 0.98,
            close=close,
            volume=1_000.0,
            source="test",
        )
        for i, close in enumerate(closes)
        if i not in (skip or set())
    ]


def _day(i: int) -> date:
    return _FIRST + timedelta(days=i)


def _returns(bars: list[PriceBar]) -> list[float]:
    return [b.close / a.close - 1.0 for a, b in pairwise(bars)]


def test_a_split_leaves_no_jump_in_the_adjusted_returns() -> None:
    raw = _bars([100.0, 102.0, 52.0, 53.0])

    adjusted = adjust_bars(raw, [Split(instrument_id="aaa", ex_date=_day(2), ratio=2.0)])

    assert [bar.close for bar in adjusted] == [50.0, 51.0, 52.0, 53.0]
    assert _returns(adjusted)[1] == pytest.approx(52.0 * 2.0 / 102.0 - 1.0, abs=1e-12)
    assert [bar.volume for bar in adjusted] == [2_000.0, 2_000.0, 1_000.0, 1_000.0]
    assert adjusted[0].open == pytest.approx(99.0 / 2.0)
    assert adjusted[0].high == pytest.approx(101.0 / 2.0)
    assert [bar.unadjusted_close for bar in adjusted] == [100.0, 102.0, 52.0, 53.0]
    assert [bar.raw_close for bar in adjusted] == [100.0, 102.0, 52.0, 53.0]


def test_a_dividend_enters_the_return_on_its_ex_date() -> None:
    raw = _bars([100.0, 101.0, 99.5, 100.0])

    adjusted = adjust_bars(raw, [CashDividend(instrument_id="aaa", ex_date=_day(2), amount=2.0)])

    returns = _returns(adjusted)
    assert returns[0] == pytest.approx(101.0 / 100.0 - 1.0, abs=1e-12)  # before: unchanged
    assert returns[1] == pytest.approx((99.5 + 2.0) / 101.0 - 1.0, abs=1e-12)  # total return
    assert returns[2] == pytest.approx(100.0 / 99.5 - 1.0, abs=1e-12)
    assert [bar.volume for bar in adjusted] == [1_000.0] * 4
    assert adjusted[-1].close == 100.0  # the series ends at the quoted price


def test_an_action_on_a_day_without_trading_uses_the_next_bar() -> None:
    raw = _bars([100.0, 101.0, 999.0, 50.0], skip={2})

    adjusted = adjust_bars(raw, [Split(instrument_id="aaa", ex_date=_day(2), ratio=2.0)])

    assert [bar.close for bar in adjusted] == [50.0, 50.5, 50.0]


@pytest.mark.parametrize("ex_day", [0, 10])
def test_an_action_without_a_bar_on_both_sides_adjusts_nothing(ex_day: int) -> None:
    raw = _bars([100.0, 101.0, 102.0])

    adjusted = adjust_bars(raw, [Split(instrument_id="aaa", ex_date=_day(ex_day), ratio=2.0)])

    assert [bar.close for bar in adjusted] == [100.0, 101.0, 102.0]


def test_without_actions_the_same_bars_come_back() -> None:
    raw = _bars([100.0, 101.0])

    assert adjust_bars(raw, []) is raw


def test_adjusted_returns_are_total_returns_under_many_actions() -> None:
    rng = np.random.default_rng(7)
    closes = list(100.0 * np.cumprod(1.0 + rng.normal(0.0, 0.02, 300)))
    actions: list[CorporateAction] = []
    ratios = {40: 2.0, 150: 0.5, 220: 3.0}
    dividends = {60: 0.8, 120: 1.1, 150: 0.4, 270: 0.9}  # 150: split and dividend together
    for day, ratio in ratios.items():
        for later in range(day, len(closes)):
            closes[later] /= ratio  # the quote after a split is in new shares
        actions.append(Split(instrument_id="aaa", ex_date=_day(day), ratio=ratio))
    actions += [
        CashDividend(instrument_id="aaa", ex_date=_day(day), amount=amount)
        for day, amount in dividends.items()
    ]
    raw = _bars(closes)

    adjusted = adjust_bars(raw, actions)

    for t in range(1, len(closes)):
        economic = ratios.get(t, 1.0) * (closes[t] + dividends.get(t, 0.0)) / closes[t - 1] - 1.0
        assert adjusted[t].close / adjusted[t - 1].close - 1.0 == pytest.approx(economic, abs=1e-12)
    assert adjusted[-1].close == closes[-1]


def test_with_events_adjusts_only_instruments_that_have_events() -> None:
    plain, split = _bars([100.0, 101.0]), _bars([100.0, 50.0])
    events = {
        "split": InstrumentEvents(
            actions=[Split(instrument_id="split", ex_date=_day(1), ratio=2.0)]
        ),
        "plain": InstrumentEvents(),
    }

    result = with_events({"plain": plain, "split": split, "other": plain}, events).bars

    assert result["plain"] is plain
    assert result["other"] is plain
    assert [bar.close for bar in result["split"]] == [50.0, 50.0]


def test_actions_parse_by_kind_and_reject_nonsense() -> None:
    parse = TypeAdapter(CorporateAction).validate_python

    assert isinstance(
        parse({"kind": "split", "instrument_id": "a", "ex_date": "2024-01-02", "ratio": 4}), Split
    )
    assert isinstance(
        parse(
            {"kind": "cash_dividend", "instrument_id": "a", "ex_date": "2024-01-02", "amount": 0.5}
        ),
        CashDividend,
    )
    with pytest.raises(ValidationError):
        parse({"kind": "split", "instrument_id": "a", "ex_date": "2024-01-02", "ratio": 0})
    with pytest.raises(ValidationError):
        parse(
            {"kind": "cash_dividend", "instrument_id": "a", "ex_date": "2024-01-02", "amount": -1}
        )
    with pytest.raises(ValidationError):
        parse({"kind": "merger", "instrument_id": "a", "ex_date": "2024-01-02"})


def test_a_bar_never_adjusted_has_its_close_as_raw_close() -> None:
    assert _bars([123.0])[0].raw_close == 123.0


def _delisting(day: int, rate: float | None) -> Delisting:
    return Delisting(instrument_id="aaa", date=_day(day), delisting_return=rate)


def test_a_delisting_ends_the_bars_with_its_return() -> None:
    raw = _bars([100.0, 101.0, 80.0])

    market = with_events({"aaa": raw}, {"aaa": InstrumentEvents(delisting=_delisting(4, -0.5))})

    bars = market.bars["aaa"]
    assert [bar.ts for bar in bars] == [_day(0), _day(1), _day(2), _day(4)]
    final = bars[-1]
    assert (final.open, final.high, final.low, final.close) == (40.0, 40.0, 40.0, 40.0)
    assert final.volume == 0.0
    assert final.close / bars[-2].close - 1.0 == pytest.approx(-0.5)
    assert [(d.instrument_id, d.delisting_return, d.assumed) for d in market.delistings] == [
        ("aaa", -0.5, False)
    ]


def test_an_unknown_delisting_return_takes_the_definitions_assumption() -> None:
    market = with_events(
        {"aaa": _bars([100.0, 90.0])},
        {"aaa": InstrumentEvents(delisting=_delisting(2, None))},
        missing_delisting_return=-0.3,
    )

    assert market.bars["aaa"][-1].close == pytest.approx(63.0)
    assert market.assumed_delistings == 1


def test_an_unknown_delisting_return_without_an_assumption_is_refused() -> None:
    with pytest.raises(ValueError, match="no missing_delisting_return"):
        with_events(
            {"aaa": _bars([100.0])}, {"aaa": InstrumentEvents(delisting=_delisting(1, None))}
        )


def test_a_delisting_before_the_last_bar_contradicts_the_data() -> None:
    with pytest.raises(ValueError, match="delisted on 2024-01-02 but has a bar on 2024-01-03"):
        with_events(
            {"aaa": _bars([100.0, 101.0, 102.0])},
            {"aaa": InstrumentEvents(delisting=_delisting(1, -0.1))},
        )


def test_a_total_loss_leaves_a_zero_price_and_nothing_less() -> None:
    market = with_events(
        {"aaa": _bars([100.0, 101.0])}, {"aaa": InstrumentEvents(delisting=_delisting(3, -1.0))}
    )

    assert market.bars["aaa"][-1].close == 0.0
    with pytest.raises(ValidationError):
        Delisting(instrument_id="aaa", date=_day(3), delisting_return=-1.5)


def test_a_delisting_follows_the_adjusted_prices_and_keeps_the_raw_one() -> None:
    events = InstrumentEvents(
        actions=[Split(instrument_id="aaa", ex_date=_day(1), ratio=2.0)],
        delisting=_delisting(3, -0.5),
    )

    bars = with_events({"aaa": _bars([100.0, 50.0, 60.0])}, {"aaa": events}).bars["aaa"]

    assert [bar.close for bar in bars] == [50.0, 50.0, 60.0, 30.0]
    assert bars[-1].unadjusted_close == 30.0


def test_a_delisting_without_bars_ends_nothing() -> None:
    market = with_events({"aaa": []}, {"aaa": InstrumentEvents(delisting=_delisting(3, -0.5))})

    assert market.bars["aaa"] == []
    assert market.delistings == []


def _other(days: list[int]) -> list[PriceBar]:
    return [
        bar.model_copy(update={"instrument_id": "bbb"})
        for bar in _bars([50.0] * 10, None)
        if (bar.ts - _FIRST).days in days
    ]


def test_a_delisting_dated_off_the_market_lands_on_the_next_session() -> None:
    # The source gives the day after the last price (3); the market is closed on 3 and 4.
    market = with_events(
        {"aaa": _bars([100.0, 101.0, 102.0]), "bbb": _other([0, 1, 2, 5, 6])},
        {"aaa": InstrumentEvents(delisting=_delisting(3, -0.5))},
    )

    assert [bar.ts for bar in market.bars["aaa"]] == [_day(0), _day(1), _day(2), _day(5)]
    assert [delisting.date for delisting in market.delistings] == [_day(5)]
    assert market.bars["bbb"] == _other([0, 1, 2, 5, 6])


def test_a_delisting_on_a_session_keeps_its_date() -> None:
    market = with_events(
        {"aaa": _bars([100.0, 101.0]), "bbb": _other([0, 1, 2, 3])},
        {"aaa": InstrumentEvents(delisting=_delisting(3, -0.5))},
    )

    assert market.bars["aaa"][-1].ts == _day(3)
