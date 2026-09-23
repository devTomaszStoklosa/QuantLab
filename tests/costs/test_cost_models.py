import statistics
from datetime import date, timedelta

import pytest

from quantlab.core.data.provider import PriceBar
from quantlab.costs.naive import NaiveCostModel
from quantlab.costs.realistic import RealisticCostModel
from quantlab.costs.zero import ZeroCostModel

_AS_OF = date(2026, 1, 1)


def _bars(first_day: date, closes: list[float]) -> list[PriceBar]:
    return [
        PriceBar(
            instrument_id="a",
            ts=first_day + timedelta(days=i),
            open=close,
            high=close,
            low=close,
            close=close,
            volume=1.0,
            adj_close=None,
            source="test",
        )
        for i, close in enumerate(closes)
    ]


def test_naive_cost_is_bps_times_traded_weight() -> None:
    model = NaiveCostModel(bps=10)

    assert model.cost([], _AS_OF, traded_weight=0.5) == pytest.approx(0.0005)


def test_naive_name_records_the_bps_parameter() -> None:
    assert NaiveCostModel(bps=10).name == "naive-10bps"
    assert NaiveCostModel(bps=7.5).name == "naive-7.5bps"


def test_realistic_cost_is_fee_plus_k_times_recent_volatility() -> None:
    closes = [100.0, 101.0, 99.0, 102.0, 100.0]
    bars = _bars(date(2026, 1, 1), closes)
    as_of = date(2026, 1, 5)
    # vol_window=3 -> only the last 3 returns count, the first one (100 -> 101) doesn't
    last_returns = [99.0 / 101.0 - 1, 102.0 / 99.0 - 1, 100.0 / 102.0 - 1]
    expected = (10 / 10_000 + 0.05 * statistics.stdev(last_returns)) * 0.5

    model = RealisticCostModel(fee_bps=10, k=0.05, vol_window=3)

    assert model.cost(bars, as_of, traded_weight=0.5) == pytest.approx(expected)


def test_realistic_cost_ignores_bars_after_as_of() -> None:
    history = _bars(date(2026, 1, 1), [100.0, 101.0, 99.0, 102.0, 100.0])
    future = _bars(date(2026, 1, 6), [300.0, 10.0, 500.0])
    model = RealisticCostModel(fee_bps=10, k=0.05, vol_window=3)
    as_of = date(2026, 1, 5)

    assert model.cost(history + future, as_of, 1.0) == model.cost(history, as_of, 1.0)


def test_realistic_name_records_all_parameters() -> None:
    model = RealisticCostModel(fee_bps=10, k=0.05, vol_window=30)

    assert model.name == "realistic-10bps-k0.05-vol30d"


def test_realistic_cost_raises_without_enough_history() -> None:
    bars = _bars(date(2026, 1, 1), [100.0, 101.0])
    model = RealisticCostModel(fee_bps=10, k=0.05, vol_window=30)

    with pytest.raises(ValueError, match="at least 2 daily returns"):
        model.cost(bars, date(2026, 1, 2), traded_weight=1.0)


def test_zero_cost_model_charges_nothing() -> None:
    model = ZeroCostModel()

    assert model.cost([], _AS_OF, traded_weight=1.0) == 0.0
    assert model.name == "zero-cost"
