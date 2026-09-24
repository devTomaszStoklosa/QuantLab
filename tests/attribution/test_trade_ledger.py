from datetime import date, timedelta

import numpy as np
import pytest
from pydantic import ValidationError

from quantlab.attribution.trade_ledger import (
    Trade,
    build_trade_ledger,
    by_exit_month,
    by_holding_period,
    by_regime,
    group_pnl,
)
from quantlab.backtest.vectorized.engine import run
from quantlab.core.data.provider import PriceBar
from quantlab.costs.naive import NaiveCostModel
from quantlab.costs.realistic import RealisticCostModel
from quantlab.strategy.signal import Signal
from quantlab.strategy.time_series_momentum import TimeSeriesMomentum

_FIRST_DAY = date(2020, 1, 1)


def _day(i: int) -> date:
    return _FIRST_DAY + timedelta(days=i)


def _bars(instrument_id: str, closes: list[float]) -> list[PriceBar]:
    return [
        PriceBar(
            instrument_id=instrument_id,
            ts=_day(i),
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


class _FixedSignalsStrategy:
    """Test double: signals[i] is the list of (instrument, direction) decided as of day i."""

    def __init__(self, signals: list[list[tuple[str, str]]]) -> None:
        self._signals = signals

    def generate_signals(self, bars: dict[str, list[PriceBar]], as_of: date) -> list[Signal]:
        index = (as_of - _FIRST_DAY).days
        if index >= len(self._signals):
            return []
        return [
            Signal(instrument_id=instrument_id, ts=as_of, direction=direction, strength=0.0)
            for instrument_id, direction in self._signals[index]
        ]


def _run(bars, strategy, cost_model=None):
    last = max(bar.ts for instrument_bars in bars.values() for bar in instrument_bars)
    return run(
        strategy=strategy,
        cost_model=cost_model or NaiveCostModel(bps=100),
        bars=bars,
        universe_name="u",
        start=_FIRST_DAY,
        end=last,
        seed=0,
        git_sha="x",
        strategy_name="s",
        strategy_params={},
    )


def _labels(n_days: int, label: str = "low") -> dict[date, str]:
    return {_day(i): label for i in range(n_days)}


def test_closed_trade_has_entry_exit_and_costs_of_both() -> None:
    bars = {"a": _bars("a", [100.0, 110.0, 110.0])}
    backtest = _run(bars, _FixedSignalsStrategy([[("a", "long")], [("a", "flat")]]))

    [trade] = build_trade_ledger(backtest, bars, _labels(3))

    assert (trade.side, trade.entry_ts, trade.exit_ts) == ("long", _day(0), _day(1))
    assert (trade.entry_price, trade.exit_price) == (100.0, 110.0)
    assert trade.size == 1.0
    assert trade.holding_days == 1
    # +10% on equity 1.0; 1% to buy 1.00, 1% to sell the position worth 1.10.
    assert trade.gross_pnl == pytest.approx(0.10)
    assert trade.costs == pytest.approx(0.01 + 0.011)
    assert trade.net_pnl == pytest.approx(0.079)
    assert trade.open_at_end is False


def test_flip_closes_one_trade_opens_another_and_splits_the_cost() -> None:
    bars = {"a": _bars("a", [100.0, 110.0, 99.0])}
    backtest = _run(bars, _FixedSignalsStrategy([[("a", "long")], [("a", "short")]]))

    long_trade, short_trade = build_trade_ledger(backtest, bars, _labels(3))

    # Selling the long leg (worth 1.10) and opening the short (1.09 of equity) at 1%.
    assert long_trade.side == "long"
    assert long_trade.costs == pytest.approx(0.01 + 0.011)
    assert short_trade.side == "short"
    assert short_trade.entry_ts == _day(1)
    assert short_trade.costs == pytest.approx(0.0109)
    # Short 1.09 of equity through a 10% fall.
    assert short_trade.gross_pnl == pytest.approx(0.109)
    assert short_trade.open_at_end is True
    assert short_trade.exit_price == 99.0


def test_position_held_at_the_end_is_open_without_an_exit_cost() -> None:
    bars = {"a": _bars("a", [100.0, 110.0, 121.0])}
    backtest = _run(bars, _FixedSignalsStrategy([[("a", "long")], [("a", "long")]]))

    [trade] = build_trade_ledger(backtest, bars, _labels(3))

    assert trade.open_at_end is True
    assert trade.exit_ts == _day(2)
    assert trade.holding_days == 2
    # Entry at 1%; the entry cost left the position worth 1.10 of equity 1.09,
    # and trading it back to weight 1.0 costs 1% of the 0.01 excess.
    assert trade.costs == pytest.approx(0.01 + 0.01 * (1.10 - 1.09))


def test_rebalancing_within_a_side_adjusts_the_same_trade() -> None:
    bars = {"a": _bars("a", [100.0, 110.0, 110.0]), "b": _bars("b", [100.0, 100.0, 100.0])}
    signals = [[("a", "long")], [("a", "long"), ("b", "long")]]
    backtest = _run(bars, _FixedSignalsStrategy(signals))

    trades = build_trade_ledger(backtest, bars, _labels(3))

    assert [(trade.instrument_id, trade.entry_ts) for trade in trades] == [
        ("a", _day(0)),
        ("b", _day(1)),
    ]
    a_trade = trades[0]
    # Entry at weight 1.0 (0.01), then trimmed from a position worth 1.10 to half
    # of equity 1.09.
    assert a_trade.size == 1.0
    assert a_trade.costs == pytest.approx(0.01 + 0.01 * (1.10 - 0.5 * 1.09))


def test_regime_at_entry_comes_from_the_entry_close() -> None:
    bars = {"a": _bars("a", [100.0, 110.0, 110.0, 120.0])}
    backtest = _run(bars, _FixedSignalsStrategy([[], [("a", "long")], [("a", "long")]]))
    labels = {_day(0): "low", _day(1): "high", _day(2): "low", _day(3): "low"}

    [trade] = build_trade_ledger(backtest, bars, labels)

    assert trade.entry_ts == _day(1)
    assert trade.regime_at_entry == "high"


def test_costs_above_gross_profit_give_negative_net_pnl() -> None:
    bars = {"a": _bars("a", [100.0, 100.5, 100.5])}
    backtest = _run(bars, _FixedSignalsStrategy([[("a", "long")], [("a", "flat")]]))

    [trade] = build_trade_ledger(backtest, bars, _labels(3))

    assert trade.gross_pnl > 0
    assert trade.net_pnl < 0


def test_missing_regime_label_raises() -> None:
    bars = {"a": _bars("a", [100.0, 110.0])}
    backtest = _run(bars, _FixedSignalsStrategy([[("a", "long")]]))

    with pytest.raises(ValueError, match="No regime label"):
        build_trade_ledger(backtest, bars, {})


def test_net_pnl_of_all_trades_adds_up_to_the_equity_change() -> None:
    rng = np.random.default_rng(3)
    bars = {
        instrument_id: _bars(
            instrument_id, (100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.04, 300)))).tolist()
        )
        for instrument_id in ("a", "b")
    }
    backtest = _run(
        bars,
        TimeSeriesMomentum(lookback_days=5),
        RealisticCostModel(fee_bps=10, k=0.05, vol_window=10),
    )

    trades = build_trade_ledger(backtest, bars, _labels(300))

    assert len(trades) > 20
    assert any(trade.costs > 0 for trade in trades)
    assert sum(trade.net_pnl for trade in trades) == pytest.approx(
        backtest.snapshots[-1].equity - backtest.snapshots[0].equity, abs=1e-12
    )
    assert all(trade.exit_ts > trade.entry_ts for trade in trades)


def _trade(net_pnl: float, holding_days: int = 1, regime: str = "low", exit_day: int = 10) -> Trade:
    exit_ts = _day(exit_day)
    return Trade(
        instrument_id="a",
        side="long",
        entry_ts=exit_ts - timedelta(days=holding_days),
        entry_price=100.0,
        exit_ts=exit_ts,
        exit_price=100.0,
        size=1.0,
        gross_pnl=net_pnl + 0.01,
        costs=0.01,
        net_pnl=net_pnl,
        holding_days=holding_days,
        regime_at_entry=regime,
        open_at_end=False,
    )


def test_group_pnl_reports_the_distribution_per_group() -> None:
    trades = [
        _trade(0.03, regime="low"),
        _trade(-0.01, regime="low"),
        _trade(0.01, regime="low"),
        _trade(-0.02, regime="high"),
    ]

    groups = group_pnl(trades, by_regime)

    low = groups["low"]
    assert low.trades == 3
    assert low.win_rate == pytest.approx(2 / 3)
    assert low.total_net_pnl == pytest.approx(0.03)
    assert low.mean_net_pnl == pytest.approx(0.01)
    assert low.median_net_pnl == pytest.approx(0.01)
    assert (low.worst_net_pnl, low.best_net_pnl) == (-0.01, 0.03)
    assert low.costs == pytest.approx(0.03)
    assert groups["high"].win_rate == 0.0


@pytest.mark.parametrize(
    ("holding_days", "bucket"),
    [
        (1, "1-7d"),
        (7, "1-7d"),
        (8, "8-30d"),
        (30, "8-30d"),
        (31, "31-90d"),
        (90, "31-90d"),
        (91, "91-365d"),
        (365, "91-365d"),
        (366, "366d+"),
    ],
)
def test_holding_period_buckets(holding_days: int, bucket: str) -> None:
    assert by_holding_period(_trade(0.0, holding_days=holding_days, exit_day=400)) == bucket


def test_exit_month_groups_by_calendar_month_of_exit() -> None:
    trades = [_trade(0.01, exit_day=10), _trade(0.02, exit_day=20), _trade(0.03, exit_day=40)]

    groups = group_pnl(trades, by_exit_month)

    assert {key: group.trades for key, group in groups.items()} == {"2020-01": 2, "2020-02": 1}


def test_trade_must_exit_after_it_enters() -> None:
    with pytest.raises(ValidationError):
        _trade(0.0, holding_days=0)
