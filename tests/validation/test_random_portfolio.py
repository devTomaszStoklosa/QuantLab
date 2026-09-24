from datetime import date, timedelta
from itertools import pairwise

import numpy as np
import pytest

from quantlab.backtest.rebalance import Daily, OnSignalChange, RebalancePolicy
from quantlab.backtest.run import BacktestRun
from quantlab.backtest.sizing import EqualWeightBySign
from quantlab.backtest.vectorized.engine import run as run_backtest
from quantlab.core.data.provider import PriceBar
from quantlab.costs.zero import ZeroCostModel
from quantlab.reporting.metrics import sharpe
from quantlab.strategy.base import Strategy
from quantlab.strategy.cross_sectional_momentum import CrossSectionalMomentum
from quantlab.strategy.signal import Signal
from quantlab.validation.permutation import PermutationTestValidator
from quantlab.validation.random_portfolio import RandomPortfolioValidator

_FIRST = date(2021, 1, 1)
_DAYS = 400


def _day(i: int) -> date:
    return _FIRST + timedelta(days=i)


def _bars(instrument_id: str, returns: np.ndarray, last: int | None = None) -> list[PriceBar]:
    closes = 100.0 * np.cumprod(np.concatenate([[1.0], 1.0 + returns]))
    return [
        PriceBar(
            instrument_id=instrument_id,
            ts=_day(i),
            open=close,
            high=close,
            low=close,
            close=close,
            volume=1.0,
            source="test",
        )
        for i, close in enumerate(closes)
        if last is None or i <= last
    ]


def _market(drifts: dict[str, float], seed: int = 3) -> dict[str, list[PriceBar]]:
    """Instruments sharing one market shock a day, each with its own lasting drift."""
    rng = np.random.default_rng(seed)
    market = rng.normal(0.0, 0.01, _DAYS)
    return {
        instrument_id: _bars(instrument_id, drift + market + rng.normal(0.0, 0.005, _DAYS))
        for instrument_id, drift in drifts.items()
    }


class _Pick:
    """Long the instruments of the current block of `rotation`, flat on the rest of
    `cross_section`; moves to the next block every `every` days."""

    def __init__(self, rotation: list[str], cross_section: list[str], every: int = 1) -> None:
        self.rotation = rotation  # each block: instrument ids joined by "+"
        self.cross_section = cross_section
        self.every = every

    def generate_signals(self, bars: dict[str, list[PriceBar]], as_of: date) -> list[Signal]:
        block = (as_of - _FIRST).days // self.every
        chosen = self.rotation[block % len(self.rotation)].split("+")
        return [
            Signal(
                instrument_id=instrument_id,
                ts=as_of,
                direction="long" if instrument_id in chosen else "flat",
                strength=0.0,
            )
            for instrument_id in self.cross_section
        ]


def _run(
    strategy: Strategy, bars: dict[str, list[PriceBar]], rebalance: RebalancePolicy, seed: int = 0
) -> BacktestRun:
    return run_backtest(
        strategy=strategy,
        cost_model=ZeroCostModel(),
        bars=bars,
        universe_name="test",
        start=_FIRST,
        end=_day(_DAYS),
        seed=seed,
        git_sha="x",
        strategy_name="test",
        strategy_params={},
        rebalance=rebalance,
    )


def _validator(
    strategy: Strategy,
    bars: dict[str, list[PriceBar]],
    rebalance: RebalancePolicy,
    n_permutations: int = 200,
) -> RandomPortfolioValidator:
    return RandomPortfolioValidator(
        bars=bars,
        strategy=strategy,
        sizer=EqualWeightBySign(),
        rebalance=rebalance,
        n_permutations=n_permutations,
        alpha=0.1,
        periods_per_year=365,
    )


def _net_returns(run: BacktestRun) -> list[float]:
    equity = [snapshot.equity for snapshot in run.snapshots]
    return [b / a - 1.0 for a, b in pairwise(equity)]


@pytest.mark.parametrize("rebalance", [Daily(), OnSignalChange()])
def test_the_actual_statistic_is_the_runs_own_sharpe_without_costs(rebalance) -> None:
    bars = _market({"a": 0.001, "b": 0.0, "c": -0.001, "d": 0.0005})
    # Two instruments at a time, rotating monthly: their weights drift under OnSignalChange.
    strategy = _Pick(["a+b", "c+d", "a+d"], ["a", "b", "c", "d"], every=30)
    run = _run(strategy, bars, rebalance)

    result = _validator(strategy, bars, rebalance).validate(run)

    assert result.detail["actual"] == pytest.approx(sharpe(_net_returns(run), 365), rel=1e-9)
    assert result.detail["decisions"] == (_DAYS if isinstance(rebalance, Daily) else 14)


def test_always_picking_the_best_instrument_gets_the_smallest_p_value() -> None:
    ids = [f"s{i}" for i in range(10)]
    bars = _market({instrument_id: 0.0005 * (i - 5) for i, instrument_id in enumerate(ids)})
    strategy = _Pick(["s9"], ids)

    result = _validator(strategy, bars, Daily()).validate(_run(strategy, bars, Daily()))

    assert result.method == "permutation"
    assert result.detail["test"] == "random_portfolio"
    assert result.detail["p_value"] == pytest.approx(1 / 201)
    assert result.passed is True
    assert result.detail["mean_cross_section"] == 10.0


def test_one_decision_gives_the_null_only_as_many_outcomes_as_the_cross_section() -> None:
    # Held without rebalancing, one draw decides the whole run: about 1 in 10 draws
    # repeats the best instrument, so p cannot fall far below 0.1 however good it is.
    ids = [f"s{i}" for i in range(10)]
    bars = _market({instrument_id: 0.0005 * (i - 5) for i, instrument_id in enumerate(ids)})
    strategy = _Pick(["s9"], ids)

    result = _validator(strategy, bars, OnSignalChange()).validate(
        _run(strategy, bars, OnSignalChange())
    )

    assert result.detail["decisions"] == 1
    assert 0.05 < result.detail["p_value"] < 0.2


def test_holding_the_whole_cross_section_is_indistinguishable_from_chance() -> None:
    ids = [f"s{i}" for i in range(5)]
    bars = _market({instrument_id: 0.0005 * i for i, instrument_id in enumerate(ids)})

    class _All:
        def generate_signals(self, bars, as_of):
            return [Signal(instrument_id=i, ts=as_of, direction="long", strength=0.0) for i in ids]

    result = _validator(_All(), bars, OnSignalChange()).validate(
        _run(_All(), bars, OnSignalChange())
    )

    # Every draw is a relabeling of equal weights: the same portfolio, so p = 1.
    assert result.detail["p_value"] == pytest.approx(1.0)
    assert result.passed is None


def test_random_portfolios_draw_only_from_the_strategys_cross_section() -> None:
    # "c" soars but the strategy never ranks it; "a" and "b" move identically.
    rng = np.random.default_rng(5)
    common = rng.normal(0.0, 0.01, _DAYS)
    bars = {
        "a": _bars("a", common),
        "b": _bars("b", common),
        "c": _bars("c", common + 0.01),
    }
    strategy = _Pick(["a"], ["a", "b"])

    result = _validator(strategy, bars, Daily()).validate(_run(strategy, bars, Daily()))

    assert result.detail["null_mean"] == pytest.approx(result.detail["actual"])
    assert result.detail["p_value"] == pytest.approx(1.0)


def test_an_instrument_that_stops_trading_keeps_its_last_value_in_a_random_portfolio() -> None:
    rng = np.random.default_rng(9)
    a_returns = 0.001 + rng.normal(0.0, 0.01, _DAYS)
    # "b" loses 50% into its last bar on day 20, as into a delisting bar; the strategy
    # holds "a" throughout, so the run has one decision and draws hold b to the end.
    b_returns = rng.normal(0.0, 0.01, _DAYS)
    b_returns[19] = -0.5
    bars = {"a": _bars("a", a_returns), "b": _bars("b", b_returns, last=20)}
    strategy = _Pick(["a"], ["a", "b"])
    n_permutations = 50

    result = _validator(strategy, bars, OnSignalChange(), n_permutations).validate(
        _run(strategy, bars, OnSignalChange())
    )

    # Each draw holds a (the actual portfolio) or b: its fall, then its last value.
    held_b = sharpe(list(np.concatenate([b_returns[:20], np.zeros(_DAYS - 20)])), 365)
    actual = result.detail["actual"]
    share_of_a = (result.detail["null_mean"] - held_b) / (actual - held_b)
    assert result.detail["n_valid"] == n_permutations
    assert 0.0 < share_of_a < 1.0
    assert share_of_a * n_permutations == pytest.approx(round(share_of_a * n_permutations))


def test_a_run_of_another_strategy_is_refused() -> None:
    bars = _market({"a": 0.001, "b": 0.0})
    run = _run(_Pick(["a"], ["a", "b"]), bars, Daily())

    with pytest.raises(ValueError, match="not the strategy's targets"):
        _validator(_Pick(["b"], ["a", "b"]), bars, Daily()).validate(run)


def test_the_same_seed_reproduces_the_result() -> None:
    ids = [f"s{i}" for i in range(6)]
    bars = _market({instrument_id: 0.0002 * i for i, instrument_id in enumerate(ids)})
    strategy = _Pick(["s3+s4", "s1"], ids, every=20)

    first = _validator(strategy, bars, OnSignalChange()).validate(
        _run(strategy, bars, OnSignalChange(), seed=7)
    )
    second = _validator(strategy, bars, OnSignalChange()).validate(
        _run(strategy, bars, OnSignalChange(), seed=7)
    )
    other = _validator(strategy, bars, OnSignalChange()).validate(
        _run(strategy, bars, OnSignalChange(), seed=8)
    )

    assert first.detail == second.detail
    assert other.detail["null_mean"] != first.detail["null_mean"]


def test_no_positions_is_inconclusive_with_a_reason() -> None:
    bars = _market({"a": 0.001, "b": 0.0})

    class _Nothing:
        def generate_signals(self, bars, as_of):
            return []

    result = _validator(_Nothing(), bars, Daily()).validate(_run(_Nothing(), bars, Daily()))

    assert result.passed is None
    assert "undefined" in result.detail["reason"]
    assert result.detail["decisions"] == 0


def _business_days(first: date, last: date) -> list[date]:
    days = [first + timedelta(days=i) for i in range((last - first).days + 1)]
    return [day for day in days if day.weekday() < 5]


def test_it_detects_the_selection_of_cross_sectional_momentum_where_day_shuffles_cannot() -> None:
    # Lasting drift differences between stocks (as in the demo_xsmom fixture): momentum
    # picks the same winners month after month, so its edge is selection, not timing.
    rng = np.random.default_rng(20260924)
    days = _business_days(date(2019, 1, 1), date(2022, 12, 31))
    drifts = rng.normal(0.0002, 0.0006, 20)
    bars = {}
    for i, drift in enumerate(drifts):
        closes = 40.0 * np.cumprod(1.0 + drift + rng.normal(0.0, 0.018, len(days)))
        instrument_id = f"eq{i:02d}"
        bars[instrument_id] = [
            PriceBar(
                instrument_id=instrument_id,
                ts=day,
                open=close,
                high=close,
                low=close,
                close=close,
                volume=1.0,
                source="test",
            )
            for day, close in zip(days, closes, strict=True)
        ]
    strategy = CrossSectionalMomentum(
        formation_months=12, skip_months=1, quantile=0.2, long_short=True, min_price=5.0
    )
    run = run_backtest(
        strategy=strategy,
        cost_model=ZeroCostModel(),
        bars=bars,
        universe_name="test",
        start=date(2020, 3, 1),
        end=date(2022, 12, 31),
        seed=0,
        git_sha="x",
        strategy_name="cross_sectional_momentum",
        strategy_params={},
        rebalance=OnSignalChange(),
    )

    selection = RandomPortfolioValidator(
        bars=bars,
        strategy=strategy,
        sizer=EqualWeightBySign(),
        rebalance=OnSignalChange(),
        n_permutations=500,
        alpha=0.1,
        periods_per_year=252,
    ).validate(run)
    timing = PermutationTestValidator(
        bars=bars, n_permutations=500, alpha=0.1, periods_per_year=252
    ).validate(run)

    assert selection.detail["decisions"] >= 30  # one a month
    assert selection.detail["p_value"] < 0.05
    assert timing.detail["p_value"] > 0.5
