"""AC-4: orders larger than the volume limit fill in part; the rest is cancelled."""

from datetime import date, timedelta

import pytest

from quantlab.backtest.event_driven.engine import run as event_driven_run
from quantlab.backtest.event_driven.execution import NextBarExecution
from quantlab.backtest.event_driven.fills import FullFill, VolumeParticipationFill
from quantlab.core.data.provider import PriceBar
from quantlab.costs.zero import ZeroCostModel
from quantlab.strategy.signal import Signal

_START = date(2026, 1, 1)


def _day(offset: int) -> date:
    return _START + timedelta(days=offset)


def _bar(day: int, volume: float, close: float = 100.0) -> PriceBar:
    return PriceBar(
        instrument_id="a",
        ts=_day(day),
        open=close,
        high=close,
        low=close,
        close=close,
        volume=volume,
        source="test",
    )


def test_full_fill_takes_the_whole_order() -> None:
    assert FullFill().fillable(-7.5, _bar(0, volume=0.0)) == -7.5


@pytest.mark.parametrize(
    ("quantity", "volume", "expected"),
    [(2.0, 100.0, 2.0), (-2.0, 100.0, -2.0), (5.0, 100.0, 2.5), (-5.0, 100.0, -2.5)],
)
def test_participation_caps_the_fill_at_its_share_of_volume(
    quantity: float, volume: float, expected: float
) -> None:
    policy = VolumeParticipationFill(max_participation=0.025)

    assert policy.fillable(quantity, _bar(0, volume=volume)) == pytest.approx(expected)


def test_nothing_fills_on_a_bar_without_volume() -> None:
    assert VolumeParticipationFill(max_participation=0.025).fillable(3.0, _bar(0, 0.0)) == 0.0


@pytest.mark.parametrize("participation", [0.0, -0.1, 1.5])
def test_participation_must_be_a_fraction(participation: float) -> None:
    with pytest.raises(ValueError, match="max_participation"):
        VolumeParticipationFill(max_participation=participation)


class _AlwaysLong:
    def generate_signals(self, bars: dict[str, list[PriceBar]], as_of: date) -> list[Signal]:
        return [Signal(instrument_id="a", ts=as_of, direction="long", strength=0.0)]


def test_the_unfilled_rest_is_cancelled_and_the_next_order_re_targets() -> None:
    # 1 000 of capital at 100 wants 10 units; day 1 trades 200, so 2.5% is 5.
    bars = {"a": [_bar(0, 200.0), _bar(1, 200.0), _bar(2, 1_000.0), _bar(3, 1_000.0)]}

    result = event_driven_run(
        strategy=_AlwaysLong(),
        cost_model=ZeroCostModel(),
        bars=bars,
        universe_name="test",
        start=_day(0),
        end=_day(3),
        seed=0,
        git_sha="test",
        strategy_name="test",
        strategy_params={},
        execution=NextBarExecution("open"),
        fill_policy=VolumeParticipationFill(max_participation=0.025),
        capital=1_000.0,
    )

    assert [(o.quantity, o.filled_quantity, o.limited) for o in result.orders] == [
        (pytest.approx(10.0), pytest.approx(5.0), True),
        (pytest.approx(5.0), pytest.approx(5.0), False),
    ]
    assert [s.positions for s in result.run.snapshots] == [
        {},
        {"a": pytest.approx(0.5)},
        {"a": pytest.approx(1.0)},
        {"a": pytest.approx(1.0)},
    ]
