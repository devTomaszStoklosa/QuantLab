from datetime import date

import pytest

from quantlab.costs.naive import NaiveCostModel
from quantlab.costs.zero import ZeroCostModel

_AS_OF = date(2026, 1, 1)


def test_naive_cost_is_bps_times_traded_weight() -> None:
    model = NaiveCostModel(bps=10)

    assert model.cost([], _AS_OF, traded_weight=0.5) == pytest.approx(0.0005)


def test_naive_name_records_the_bps_parameter() -> None:
    assert NaiveCostModel(bps=10).name == "naive-10bps"
    assert NaiveCostModel(bps=7.5).name == "naive-7.5bps"


def test_zero_cost_model_charges_nothing() -> None:
    model = ZeroCostModel()

    assert model.cost([], _AS_OF, traded_weight=1.0) == 0.0
    assert model.name == "zero-cost"
