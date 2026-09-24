from datetime import date

import pytest

from quantlab.backtest.vectorized.engine import run
from quantlab.core.data.provider import PriceBar
from quantlab.costs.naive import NaiveCostModel
from quantlab.costs.zero import ZeroCostModel
from quantlab.strategy.signal import Signal

_DAY1 = date(2026, 1, 1)
_DAY2 = date(2026, 1, 2)
_DAY3 = date(2026, 1, 3)


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


class _FixedSignalsStrategy:
    """Test double: returns pre-scripted signals per as_of date, ignoring bars."""

    def __init__(self, signals_by_date: dict[date, list[Signal]]) -> None:
        self._signals_by_date = signals_by_date

    def generate_signals(self, bars: dict[str, list[PriceBar]], as_of: date) -> list[Signal]:
        return self._signals_by_date.get(as_of, [])


def test_equal_weight_signed_positions_compound_correctly() -> None:
    bars = {
        "a": [_bar("a", _DAY1, 100.0), _bar("a", _DAY2, 110.0), _bar("a", _DAY3, 121.0)],
        "b": [_bar("b", _DAY1, 100.0), _bar("b", _DAY2, 90.0), _bar("b", _DAY3, 81.0)],
    }
    strategy = _FixedSignalsStrategy(
        {
            _DAY1: [
                Signal(instrument_id="a", ts=_DAY1, direction="long", strength=0.0),
                Signal(instrument_id="b", ts=_DAY1, direction="short", strength=0.0),
            ],
            _DAY2: [
                Signal(instrument_id="a", ts=_DAY2, direction="long", strength=0.0),
                Signal(instrument_id="b", ts=_DAY2, direction="flat", strength=0.0),
            ],
        }
    )

    result = run(
        strategy=strategy,
        cost_model=ZeroCostModel(),
        bars=bars,
        universe_name="test-universe",
        start=_DAY1,
        end=_DAY3,
        seed=1,
        git_sha="deadbeef",
        strategy_name="fixed",
        strategy_params={"lookback_days": 1},
    )

    assert result.universe_name == "test-universe"
    assert result.cost_model_name == "zero-cost"
    assert result.strategy_name == "fixed"
    assert result.strategy_params == {"lookback_days": 1}
    assert result.seed == 1
    assert result.git_sha == "deadbeef"

    assert [snapshot.ts for snapshot in result.snapshots] == [_DAY1, _DAY2, _DAY3]

    assert result.snapshots[0].equity == 1.0
    assert result.snapshots[0].cash == 1.0
    assert result.snapshots[0].positions == {}

    # a: +10% with weight +0.5, b: -10% with weight -0.5 -> both legs contribute +0.05
    assert result.snapshots[1].positions == {"a": 0.5, "b": -0.5}
    assert result.snapshots[1].equity == pytest.approx(1.10)
    assert result.snapshots[1].cash == pytest.approx(0.0)

    # b flat on day 2's signal -> excluded, a alone at full weight, +10%
    assert result.snapshots[2].positions == {"a": 1.0}
    assert result.snapshots[2].equity == pytest.approx(1.21)
    assert result.snapshots[2].cash == pytest.approx(0.0)


def test_all_flat_signals_leave_equity_unchanged() -> None:
    bars = {"a": [_bar("a", _DAY1, 100.0), _bar("a", _DAY2, 110.0)]}
    strategy = _FixedSignalsStrategy(
        {_DAY1: [Signal(instrument_id="a", ts=_DAY1, direction="flat", strength=0.0)]}
    )

    result = run(
        strategy=strategy,
        cost_model=ZeroCostModel(),
        bars=bars,
        universe_name="u",
        start=_DAY1,
        end=_DAY2,
        seed=1,
        git_sha="x",
        strategy_name="fixed",
        strategy_params={},
    )

    assert result.snapshots[1].positions == {}
    assert result.snapshots[1].equity == 1.0
    assert result.snapshots[1].cash == 1.0


def test_one_snapshot_per_date_with_no_gaps() -> None:
    bars = {
        "a": [_bar("a", _DAY1, 100.0), _bar("a", _DAY2, 101.0), _bar("a", _DAY3, 102.0)],
    }
    strategy = _FixedSignalsStrategy({})

    result = run(
        strategy=strategy,
        cost_model=ZeroCostModel(),
        bars=bars,
        universe_name="u",
        start=_DAY1,
        end=_DAY3,
        seed=1,
        git_sha="x",
        strategy_name="fixed",
        strategy_params={},
    )

    assert [snapshot.ts for snapshot in result.snapshots] == [_DAY1, _DAY2, _DAY3]


def test_instrument_missing_bar_excluded_from_period_without_crashing() -> None:
    bars = {
        "a": [_bar("a", _DAY1, 100.0), _bar("a", _DAY2, 110.0)],  # no bar on _DAY3
        "b": [_bar("b", _DAY1, 50.0), _bar("b", _DAY2, 50.0), _bar("b", _DAY3, 55.0)],
    }
    strategy = _FixedSignalsStrategy(
        {_DAY2: [Signal(instrument_id="a", ts=_DAY2, direction="long", strength=0.0)]}
    )

    result = run(
        strategy=strategy,
        cost_model=ZeroCostModel(),
        bars=bars,
        universe_name="u",
        start=_DAY1,
        end=_DAY3,
        seed=1,
        git_sha="x",
        strategy_name="fixed",
        strategy_params={},
    )

    assert [snapshot.ts for snapshot in result.snapshots] == [_DAY1, _DAY2, _DAY3]
    assert result.snapshots[2].positions == {}
    assert result.snapshots[2].equity == pytest.approx(1.0)


class _RecordingCostModel:
    """Test double: records every cost() call, charges nothing."""

    name = "recording"

    def __init__(self) -> None:
        self.calls: list[tuple[date, float]] = []

    def cost(self, instrument_bars: list[PriceBar], as_of: date, traded_weight: float) -> float:
        self.calls.append((as_of, traded_weight))
        return 0.0


def _run_with(cost_model, bars, strategy, end=_DAY3):
    return run(
        strategy=strategy,
        cost_model=cost_model,
        bars=bars,
        universe_name="u",
        start=_DAY1,
        end=end,
        seed=1,
        git_sha="x",
        strategy_name="fixed",
        strategy_params={},
    )


def test_entry_and_exit_are_charged_on_traded_weight() -> None:
    bars = {"a": [_bar("a", _DAY1, 100.0), _bar("a", _DAY2, 110.0), _bar("a", _DAY3, 110.0)]}
    strategy = _FixedSignalsStrategy(
        {
            _DAY1: [Signal(instrument_id="a", ts=_DAY1, direction="long", strength=0.0)],
            _DAY2: [Signal(instrument_id="a", ts=_DAY2, direction="flat", strength=0.0)],
        }
    )

    result = _run_with(NaiveCostModel(bps=100), bars, strategy)

    assert result.cost_model_name == "naive-100bps"
    # Entry: buy weight 1.0 at 1% -> 0.01; +10% gross -> equity 1.09.
    assert result.snapshots[1].equity == pytest.approx(1.09)
    # Exit: position is worth 1.10 of the original equity, 1% of that -> 0.011.
    assert result.snapshots[2].equity == pytest.approx(1.079)


def test_rebalancing_price_drift_is_charged_even_when_targets_do_not_change() -> None:
    bars = {
        "a": [_bar("a", _DAY1, 100.0), _bar("a", _DAY2, 110.0), _bar("a", _DAY3, 110.0)],
        "b": [_bar("b", _DAY1, 100.0), _bar("b", _DAY2, 90.0), _bar("b", _DAY3, 90.0)],
    }
    long_a_short_b = [
        Signal(instrument_id="a", ts=_DAY1, direction="long", strength=0.0),
        Signal(instrument_id="b", ts=_DAY1, direction="short", strength=0.0),
    ]
    strategy = _FixedSignalsStrategy({_DAY1: long_a_short_b, _DAY2: long_a_short_b})

    result = _run_with(NaiveCostModel(bps=100), bars, strategy)

    # Entry: traded 0.5 + 0.5 at 1% -> 0.01; both legs +5% gross -> equity 1.09.
    assert result.snapshots[1].equity == pytest.approx(1.09)
    # Held weights drifted to 0.55/1.09 and -0.45/1.09; trading back to +-0.5 is
    # 0.1/1.09 of equity, costing 0.001 of the original equity -> 1.089.
    assert result.snapshots[2].equity == pytest.approx(1.089)


def test_costs_are_recorded_per_instrument_and_add_up_to_the_charge() -> None:
    bars = {
        "a": [_bar("a", _DAY1, 100.0), _bar("a", _DAY2, 110.0), _bar("a", _DAY3, 110.0)],
        "b": [_bar("b", _DAY1, 100.0), _bar("b", _DAY2, 90.0), _bar("b", _DAY3, 90.0)],
    }
    long_a_short_b = [
        Signal(instrument_id="a", ts=_DAY1, direction="long", strength=0.0),
        Signal(instrument_id="b", ts=_DAY1, direction="short", strength=0.0),
    ]
    only_a = [Signal(instrument_id="a", ts=_DAY2, direction="long", strength=0.0)]
    strategy = _FixedSignalsStrategy({_DAY1: long_a_short_b, _DAY2: only_a})

    result = _run_with(NaiveCostModel(bps=100), bars, strategy)

    assert result.snapshots[0].costs == {}
    assert result.snapshots[1].costs == pytest.approx({"a": 0.005, "b": 0.005})
    # b is closed on day 2 and still charged; a goes from 0.55/1.09 to 1.0.
    assert result.snapshots[2].costs == pytest.approx(
        {"a": 0.01 * (1.0 - 0.55 / 1.09), "b": 0.01 * 0.45 / 1.09}
    )
    # Prices don't move on day 3, so the period's return is minus its total cost.
    assert result.snapshots[2].equity / result.snapshots[1].equity - 1.0 == pytest.approx(
        -sum(result.snapshots[2].costs.values())
    )


def test_cost_model_is_asked_at_the_rebalance_date() -> None:
    bars = {"a": [_bar("a", _DAY1, 100.0), _bar("a", _DAY2, 110.0), _bar("a", _DAY3, 110.0)]}
    strategy = _FixedSignalsStrategy(
        {_DAY2: [Signal(instrument_id="a", ts=_DAY2, direction="long", strength=0.0)]}
    )
    cost_model = _RecordingCostModel()

    _run_with(cost_model, bars, strategy)

    assert cost_model.calls == [(_DAY2, 1.0)]


def test_raises_when_no_price_data_in_range() -> None:
    with pytest.raises(ValueError, match="No price data available"):
        run(
            strategy=_FixedSignalsStrategy({}),
            cost_model=ZeroCostModel(),
            bars={},
            universe_name="u",
            start=_DAY1,
            end=_DAY3,
            seed=1,
            git_sha="x",
            strategy_name="fixed",
            strategy_params={},
        )
