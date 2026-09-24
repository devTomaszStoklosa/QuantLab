from datetime import date, timedelta

import numpy as np
import pytest

from quantlab.backtest.event_driven.engine import run as event_driven_run
from quantlab.backtest.event_driven.execution import NextBarExecution
from quantlab.backtest.event_driven.fills import VolumeParticipationFill
from quantlab.backtest.event_driven.orders import OrderRecord
from quantlab.backtest.run import BacktestRun, PortfolioSnapshot
from quantlab.core.data.provider import PriceBar
from quantlab.costs.naive import NaiveCostModel
from quantlab.reporting.engine_comparison import (
    capacity,
    comparison_row,
    max_equity_difference,
    total_costs,
)
from quantlab.strategy.short_term_reversal import ShortTermReversal

_START = date(2026, 1, 1)


def _day(offset: int) -> date:
    return _START + timedelta(days=offset)


def _run(snapshots: list[PortfolioSnapshot]) -> BacktestRun:
    return BacktestRun(
        id="r",
        strategy_name="s",
        strategy_params={},
        cost_model_name="c",
        universe_name="u",
        start=snapshots[0].ts,
        end=snapshots[-1].ts,
        seed=0,
        git_sha="x",
        snapshots=snapshots,
    )


def _snapshot(day: int, equity: float, costs: dict[str, float] | None = None) -> PortfolioSnapshot:
    return PortfolioSnapshot(ts=_day(day), cash=0.0, positions={}, equity=equity, costs=costs or {})


def test_total_costs_scale_each_period_by_the_equity_it_was_charged_on() -> None:
    run = _run(
        [
            _snapshot(0, 1.0),
            _snapshot(1, 1.1, {"a": 0.01}),
            _snapshot(2, 1.0, {"a": 0.02, "b": 0.01}),
        ]
    )

    assert total_costs(run) == pytest.approx(0.01 * 1.0 + 0.03 * 1.1)


def test_max_equity_difference_is_the_largest_daily_gap() -> None:
    a = _run([_snapshot(0, 1.0), _snapshot(1, 1.2), _snapshot(2, 0.9)])
    b = _run([_snapshot(0, 1.0), _snapshot(1, 1.15), _snapshot(2, 0.99)])

    assert max_equity_difference(a, b) == pytest.approx(0.09)
    with pytest.raises(ValueError, match="different dates"):
        max_equity_difference(a, _run([_snapshot(0, 1.0), _snapshot(1, 1.0)]))


def _order(quantity: float, fill_day: int | None, filled: float | None = None) -> OrderRecord:
    filled = quantity if filled is None else filled
    return OrderRecord(
        instrument_id="a",
        decision_ts=_day(0),
        quantity=quantity,
        decision_equity=1_000.0,
        filled_quantity=filled if fill_day is not None else 0.0,
        fill_ts=_day(fill_day) if fill_day is not None else None,
        fill_price=100.0 if fill_day is not None else None,
        cost=0.0,
    )


def _volume_bars(volumes: list[float]) -> dict[str, list[PriceBar]]:
    return {
        "a": [
            PriceBar(
                instrument_id="a",
                ts=_day(day),
                open=100.0,
                high=100.0,
                low=100.0,
                close=100.0,
                volume=volume,
                source="test",
            )
            for day, volume in enumerate(volumes)
        ]
    }


def test_capacity_is_set_by_the_order_largest_against_its_bar_volume() -> None:
    # 2.5% of 1 000 is 25 (order 10 uses 0.4 of it); 2.5% of 100 is 2.5
    # (order -4 uses 1.6): the limit binds above 1 000 / 1.6 = 625.
    orders = [_order(10.0, fill_day=1), _order(-4.0, fill_day=2), _order(3.0, fill_day=None)]

    result = capacity(orders, _volume_bars([0.0, 1_000.0, 100.0]), 1_000.0, 0.025)

    assert result == pytest.approx(625.0)


def test_capacity_edge_cases() -> None:
    bars = _volume_bars([0.0, 1_000.0])

    assert capacity([], bars, 1_000.0, 0.025) is None
    assert capacity([_order(1.0, fill_day=0)], bars, 1_000.0, 0.025) == 0.0
    with pytest.raises(ValueError, match="full fills"):
        capacity([_order(10.0, fill_day=1, filled=5.0)], bars, 1_000.0, 0.025)


def _random_walk_with_volume(days: int) -> dict[str, list[PriceBar]]:
    rng = np.random.default_rng(9)
    bars = {}
    for instrument_id in ("a", "b"):
        price, series = 100.0, []
        for day in range(days):
            price *= 1.0 + rng.normal(0.0, 0.03)
            series.append(
                PriceBar(
                    instrument_id=instrument_id,
                    ts=_day(day),
                    open=price * (1.0 + rng.normal(0.0, 0.002)),
                    high=price,
                    low=price,
                    close=price,
                    volume=float(rng.uniform(500.0, 5_000.0)),
                    source="test",
                )
            )
        bars[instrument_id] = series
    return bars


def test_the_limit_starts_binding_just_above_the_capacity() -> None:
    bars = _random_walk_with_volume(120)
    args = {
        "strategy": ShortTermReversal(formation_days=3),
        "cost_model": NaiveCostModel(bps=10),
        "bars": bars,
        "universe_name": "test",
        "start": _day(5),
        "end": _day(119),
        "seed": 0,
        "git_sha": "test",
        "strategy_name": "reversal",
        "strategy_params": {},
    }
    unconstrained = event_driven_run(**args, execution=NextBarExecution("open"), capital=1_000.0)
    limit = capacity(unconstrained.orders, bars, 1_000.0, 0.025)

    def limited_orders(capital: float) -> int:
        result = event_driven_run(
            **args,
            execution=NextBarExecution("open"),
            fill_policy=VolumeParticipationFill(max_participation=0.025),
            capital=capital,
        )
        return comparison_row("limited", result.run, result.orders, 365).limited_orders

    assert limited_orders(limit * 0.999) == 0
    assert limited_orders(limit * 1.001) >= 1


def test_comparison_row_reports_costs_and_limited_orders() -> None:
    bars = _random_walk_with_volume(60)
    result = event_driven_run(
        strategy=ShortTermReversal(formation_days=3),
        cost_model=NaiveCostModel(bps=10),
        bars=bars,
        universe_name="test",
        start=_day(5),
        end=_day(59),
        seed=0,
        git_sha="test",
        strategy_name="reversal",
        strategy_params={},
        execution=NextBarExecution("open"),
        capital=10_000.0,
    )

    row = comparison_row("next-open", result.run, result.orders, 365)
    vectorized_like = comparison_row("vectorized", result.run, None, 365)

    assert row.total_costs == pytest.approx(sum(o.cost for o in result.orders) / 10_000.0)
    assert row.limited_orders == 0
    assert vectorized_like.limited_orders is None
    assert row.metrics.sharpe == vectorized_like.metrics.sharpe
