from dataclasses import replace
from datetime import date, timedelta
from itertools import pairwise

import numpy as np
import pytest
from pydantic import ValidationError

from quantlab import cli
from quantlab.backtest.vectorized.engine import run as run_backtest
from quantlab.core.data.provider import PriceBar, WithoutEvents
from quantlab.core.universe import Instrument, Universe
from quantlab.costs.realistic import RealisticCostModel
from quantlab.reporting.metrics import sharpe
from quantlab.research.definition import (
    CostModelParameters,
    TimeSeriesMomentumSelectedParameters,
)
from quantlab.strategy.selected_parameter import SelectedParameter
from quantlab.strategy.signal import Signal
from quantlab.strategy.time_series_momentum import TimeSeriesMomentum

_FIRST = date(2016, 1, 1)
_LAST = date(2021, 12, 31)
_COSTS = CostModelParameters(name="realistic", fee_bps=10, k=0.05, vol_window=30)


def _bars() -> dict[str, list[PriceBar]]:
    """Two instruments with trends that turn every few months: short lookbacks catch
    them, long ones lag; seeded, so every test sees the same history."""
    rng = np.random.default_rng(42)
    days = (_LAST - _FIRST).days + 1
    drift = np.repeat(rng.choice([-0.004, 0.004], size=days // 90 + 1), 90)[:days]
    bars = {}
    for instrument_id in ("aaa", "bbb"):
        closes = 100.0 * np.cumprod(1.0 + drift + rng.normal(0.0, 0.02, days))
        bars[instrument_id] = [
            PriceBar(
                instrument_id=instrument_id,
                ts=_FIRST + timedelta(days=i),
                open=float(close),
                high=float(close),
                low=float(close),
                close=float(close),
                volume=1.0,
                source="test",
            )
            for i, close in enumerate(closes)
        ]
    return bars


def _selection(history_start: date = date(2017, 1, 1), min_history_days: int = 365):
    return SelectedParameter(
        variants={
            str(lookback): lambda lookback=lookback: TimeSeriesMomentum(lookback)
            for lookback in (30, 90, 180)
        },
        cost_model=_COSTS.build(),
        warm_up_days=180,
        history_start=history_start,
        min_history_days=min_history_days,
    )


def _net_sharpe(lookback: int, bars, start: date, end: date) -> float:
    run = run_backtest(
        strategy=TimeSeriesMomentum(lookback),
        cost_model=_COSTS.build(),
        bars=bars,
        universe_name="u",
        start=start,
        end=end,
        seed=0,
        git_sha="x",
        strategy_name="x",
        strategy_params={},
    )
    equity = [snapshot.equity for snapshot in run.snapshots]
    return sharpe([b / a - 1.0 for a, b in pairwise(equity)], 1)


def test_the_choice_is_the_best_net_sharpe_on_the_history_before_the_year() -> None:
    bars = _bars()

    record = _selection().choice(bars, 2019)

    # The window: from history_start 2017-01-01 (later than the first bar plus the
    # longest warm-up, 2016-06-29) to the last day before 2019.
    assert (record.evaluated_from, record.evaluated_to) == (date(2017, 1, 1), date(2018, 12, 31))
    expected = {
        str(lb): _net_sharpe(lb, bars, date(2017, 1, 1), date(2018, 12, 31)) for lb in (30, 90, 180)
    }
    assert record.sharpes == pytest.approx(expected, rel=1e-12)
    assert record.chosen == max(expected, key=expected.get)


def test_bars_on_or_after_the_first_day_of_the_year_do_not_change_its_choice() -> None:
    bars = _bars()
    future = {
        instrument_id: [
            replace(bar, close=bar.close * (3.0 if bar.ts >= date(2019, 1, 1) else 1.0))
            for bar in series
        ]
        for instrument_id, series in bars.items()
    }

    assert _selection().choice(future, 2019) == _selection().choice(bars, 2019)


def test_no_position_before_the_minimum_history() -> None:
    bars = _bars()
    selection = _selection(min_history_days=730)

    too_short = selection.choice(bars, 2018)  # 2017 alone: 365 days
    enough = selection.choice(bars, 2019)

    assert too_short.chosen is None
    assert too_short.days == 365
    assert set(too_short.sharpes.values()) == {None}
    assert enough.chosen is not None
    assert selection.generate_signals(bars, date(2018, 6, 1)) == []


def test_the_window_waits_for_the_longest_warm_up() -> None:
    record = _selection(history_start=date(2016, 1, 1)).choice(_bars(), 2018)

    assert record.evaluated_from == date(2016, 1, 1) + timedelta(days=180)


def test_signals_come_from_the_chosen_lookback() -> None:
    bars = _bars()
    selection = _selection()
    chosen = int(selection.choice(bars, 2020).chosen)

    assert selection.generate_signals(bars, date(2020, 3, 2)) == TimeSeriesMomentum(
        chosen
    ).generate_signals(bars, date(2020, 3, 2))
    assert [record.year for record in selection.history] == [2020]


def test_ties_go_to_the_earlier_value_of_the_grid() -> None:
    class _Same:
        def generate_signals(self, bars, as_of):
            return [Signal(instrument_id="aaa", ts=as_of, direction="long", strength=0.0)]

    selection = SelectedParameter(
        variants={"first": _Same, "second": _Same},
        cost_model=_COSTS.build(),
        warm_up_days=0,
        history_start=date(2016, 2, 1),  # a month of prices for the cost model's volatility
        min_history_days=30,
    )

    record = selection.choice(_bars(), 2017)

    assert record.sharpes["first"] == record.sharpes["second"]
    assert record.chosen == "first"


def _parameters(**changes) -> TimeSeriesMomentumSelectedParameters:
    fields = {
        "strategy": "time_series_momentum_selected",
        "lookback_grid": [30, 90, 180],
        "history_start": date(2017, 1, 1),
        "min_history_days": 365,
        "universe": "mvp-crypto",
        "cost_model": _COSTS,
    } | changes
    return TimeSeriesMomentumSelectedParameters(**fields)


@pytest.mark.parametrize(
    ("grid", "message"),
    [([30], "at least 2"), ([30, 30], "must not repeat"), ([90, 30], "ascending")],
)
def test_the_grid_is_at_least_two_distinct_ascending_values(grid, message) -> None:
    with pytest.raises(ValidationError, match=message):
        _parameters(lookback_grid=grid)


def test_the_definition_fetches_the_anchored_history_and_counts_its_grid() -> None:
    parameters = _parameters()

    assert parameters.configurations == 3
    assert parameters.fetch_start(date(2020, 1, 1)) == date(2017, 1, 1) - timedelta(days=180)
    assert parameters.fetch_start(date(2016, 6, 1)) == date(2016, 6, 1) - timedelta(days=180)
    assert parameters.strategy_params() == {
        "lookback_grid": [30, 90, 180],
        "history_start": "2017-01-01",
        "min_history_days": 365,
    }


class _Market(WithoutEvents):
    def __init__(self) -> None:
        self.bars = _bars()

    def fetch(self, instrument: Instrument, start: date, end: date) -> list[PriceBar]:
        return [bar for bar in self.bars[instrument.id] if start <= bar.ts <= end]


def test_both_engines_trade_the_selection_alike() -> None:
    universe = Universe(
        name="pair",
        asof_date=_LAST,
        source="synthetic",
        periods_per_year=365,
        market_proxy="aaa",
        instruments=[
            Instrument(id=i, symbol=i.upper(), asset_class="crypto", quote_asset="USDT")
            for i in ("aaa", "bbb")
        ],
    )

    comparison = cli.run_engine_comparison(
        _Market(), _parameters(), universe, date(2018, 1, 1), _LAST, 0, "t", 1e6, 1.0
    )

    # Choices change between years: switching is traded and costed in both engines.
    assert comparison.parity_difference < 1e-9


def test_a_change_of_value_between_years_is_traded() -> None:
    bars = _bars()
    selection = _selection(history_start=date(2016, 7, 1), min_history_days=180)
    run = run_backtest(
        strategy=selection,
        cost_model=RealisticCostModel(fee_bps=10, k=0.05, vol_window=30),
        bars=bars,
        universe_name="u",
        start=date(2017, 1, 1),
        end=_LAST,
        seed=0,
        git_sha="x",
        strategy_name="x",
        strategy_params={},
    )

    chosen = [record.chosen for record in selection.history]
    assert len(set(chosen)) > 1, chosen  # the synthetic trends make the choice move
    assert [record.year for record in selection.history] == list(range(2017, 2022))
    first_days = [s for s in run.snapshots if s.ts in {date(y, 1, 2) for y in range(2018, 2022)}]
    assert any(snapshot.traded for snapshot in first_days)
