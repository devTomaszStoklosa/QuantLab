from datetime import date, timedelta

import numpy as np
import pytest

from quantlab.backtest.rebalance import Daily
from quantlab.backtest.sizing import CarriedWeights, EqualWeightBySign
from quantlab.core.data.provider import PriceBar
from quantlab.costs.realistic import RealisticCostModel
from quantlab.portfolio.allocation import ALLOCATION_RULES
from quantlab.portfolio.report import portfolio_report
from quantlab.reporting.metrics import sharpe
from quantlab.strategy.portfolio import Sleeve, SleeveHistory, StrategyPortfolio
from quantlab.strategy.selected_parameter import net_returns
from quantlab.strategy.short_term_reversal import ShortTermReversal
from quantlab.strategy.time_series_momentum import TimeSeriesMomentum

_FIRST, _START, _END = date(2017, 1, 1), date(2018, 1, 1), date(2019, 6, 30)


def _costs() -> RealisticCostModel:
    return RealisticCostModel(fee_bps=10, k=0.05, vol_window=30)


def _bars() -> dict[str, list[PriceBar]]:
    rng = np.random.default_rng(11)
    days = (_END - _FIRST).days + 1
    drift = np.repeat(rng.choice([-0.003, 0.003], size=days // 90 + 1), 90)[:days]
    return {
        instrument_id: [
            PriceBar(
                instrument_id=instrument_id,
                ts=_FIRST + timedelta(days=i),
                open=float(close),
                high=float(close),
                low=float(close),
                close=float(close),
                volume=1e9,
                source="test",
            )
            for i, close in enumerate(100.0 * np.cumprod(1.0 + drift + rng.normal(0.0, 0.02, days)))
        ]
        for instrument_id in ("aaa", "bbb")
    }


def _sleeves() -> list[Sleeve]:
    return [
        Sleeve("momentum", lambda: TimeSeriesMomentum(60), EqualWeightBySign(), Daily(), _costs()),
        Sleeve("reversal", lambda: ShortTermReversal(7), EqualWeightBySign(), Daily(), _costs()),
    ]


def _report(bars):
    return portfolio_report(
        history=SleeveHistory(_sleeves(), _START),
        rules=ALLOCATION_RULES,
        frozen="inverse_volatility",
        window_days=90,
        min_window_days=60,
        cost_model=_costs(),
        bars=bars,
        start=_START,
        end=_END,
        periods_per_year=365,
    )


def test_the_report_is_the_sleeves_and_the_rules_over_the_training_period() -> None:
    bars = _bars()

    report = _report(bars)

    alone = {
        sleeve.name: net_returns(sleeve.build(), _costs(), bars, _START, _END)
        for sleeve in _sleeves()
    }
    correlations = report["Sleeve correlations (daily net returns)"]
    assert correlations["momentum ~ reversal"] == pytest.approx(
        np.corrcoef(alone["momentum"], alone["reversal"])[0, 1], rel=1e-9
    )
    sharpes = report["Net Sharpe by allocation rule and of each sleeve alone"]
    for name, returns in alone.items():
        assert sharpes[f"{name} alone"] == pytest.approx(sharpe(returns, 365), rel=1e-9)
    frozen = net_returns(
        StrategyPortfolio(
            SleeveHistory(_sleeves(), _START), ALLOCATION_RULES["inverse_volatility"], 90, 60
        ),
        _costs(),
        bars,
        _START,
        _END,
        sizer=CarriedWeights(),
    )
    assert sharpes["inverse_volatility (frozen)"] == pytest.approx(sharpe(frozen, 365), rel=1e-12)
    assert set(sharpes) == {
        "equal_weight",
        "inverse_volatility (frozen)",
        "risk_parity",
        "momentum alone",
        "reversal alone",
    }


def test_the_weights_summarize_the_months_with_an_allocation() -> None:
    weights = _report(_bars())["Sleeve weights (inverse_volatility, monthly)"]

    # 18 months, the first three before 60 days of history: 15 allocated.
    assert weights["months allocated"] == 15.0
    for name in ("momentum", "reversal"):
        assert 0.0 <= weights[f"{name} min"] <= weights[f"{name} mean"] <= weights[f"{name} max"]
    assert weights["momentum mean"] + weights["reversal mean"] == pytest.approx(1.0)
    assert weights["diversification ratio (median)"] >= 1.0
