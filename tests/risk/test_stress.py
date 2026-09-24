from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from quantlab.backtest.run import BacktestRun, PortfolioSnapshot
from quantlab.core.data.provider import PriceBar
from quantlab.risk.stress import ShockScenario, stress_impact, stress_run, worst_day_scenario

_FIRST_DAY = date(2020, 1, 1)


def _day(i: int) -> date:
    return _FIRST_DAY + timedelta(days=i)


def _scenario(**shocks: float) -> ShockScenario:
    return ShockScenario(name="s", description="test", shocks=shocks)


def _run(positions: list[dict[str, float]]) -> BacktestRun:
    """Snapshot i holds positions[i] over the day ending at its ts."""
    return BacktestRun(
        id="r",
        strategy_name="s",
        strategy_params={},
        cost_model_name="c",
        universe_name="u",
        start=_FIRST_DAY,
        end=_day(len(positions) - 1),
        seed=0,
        git_sha="x",
        snapshots=[
            PortfolioSnapshot(ts=_day(i), cash=0.0, positions=weights, equity=1.0)
            for i, weights in enumerate(positions)
        ],
    )


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


def test_impact_is_the_weighted_sum_of_shocks() -> None:
    impact = stress_impact({"a": 0.5, "b": -0.5}, _scenario(a=-0.2, b=-0.3))

    assert impact == pytest.approx(0.5 * -0.2 + -0.5 * -0.3)


def test_short_position_gains_in_a_crash_and_loses_in_a_rally() -> None:
    assert stress_impact({"a": -1.0}, _scenario(a=-0.2)) == pytest.approx(0.2)
    assert stress_impact({"a": -1.0}, _scenario(a=0.2)) == pytest.approx(-0.2)


def test_instrument_not_held_does_not_count() -> None:
    assert stress_impact({"a": 1.0}, _scenario(a=-0.2, b=-0.9)) == pytest.approx(-0.2)
    assert stress_impact({}, _scenario(a=-0.2)) == 0.0


def test_held_instrument_without_a_shock_raises() -> None:
    with pytest.raises(ValueError, match="no shock for held b"):
        stress_impact({"a": 0.5, "b": 0.5}, _scenario(a=-0.2))


def test_shock_of_minus_100_percent_or_worse_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _scenario(a=-1.0)


def test_stress_run_reports_last_day_worst_day_and_losing_share() -> None:
    run = _run(
        [
            {},  # start
            {},  # warm-up, not counted
            {"a": 0.5, "b": 0.5},
            {"a": 0.5, "b": -0.5},
            {"a": -0.5, "b": -0.5},
            {"a": 0.5, "b": 0.5},
        ]
    )

    result = stress_run(run, _scenario(a=-0.2, b=-0.4))

    assert result.last_held_on == _day(5)
    assert result.last_impact == pytest.approx(-0.3)
    assert result.worst_held_on == _day(2)
    assert result.worst_impact == pytest.approx(-0.3)
    assert result.losing_share == pytest.approx(2 / 4)


def test_stress_run_without_positions_raises() -> None:
    with pytest.raises(ValueError, match="held positions"):
        stress_run(_run([{}, {}, {}]), _scenario(a=-0.2))


def test_worst_day_scenario_replays_every_instrument_on_the_reference_worst_day() -> None:
    bars = {
        "a": _bars("a", [100.0, 90.0, 95.0, 57.0, 60.0]),  # worst day: day 3, -40%
        "b": _bars("b", [50.0, 40.0, 40.0, 30.0, 31.0]),
    }

    scenario = worst_day_scenario("worst", bars, "a", _day(0), _day(4))

    assert scenario.shocks == pytest.approx({"a": 57.0 / 95.0 - 1.0, "b": 30.0 / 40.0 - 1.0})
    assert str(_day(3)) in scenario.description


def test_worst_day_scenario_stays_within_the_period() -> None:
    bars = {"a": _bars("a", [100.0, 50.0, 55.0, 50.0, 52.0])}  # -50% on day 1 is before start

    scenario = worst_day_scenario("worst", bars, "a", _day(2), _day(4))

    assert scenario.shocks["a"] == pytest.approx(50.0 / 55.0 - 1.0)


def test_worst_day_scenario_with_missing_bars_raises() -> None:
    bars = {"a": _bars("a", [100.0, 90.0, 60.0]), "b": _bars("b", [50.0, 45.0])}

    with pytest.raises(ValueError, match="b has no bars"):
        worst_day_scenario("worst", bars, "a", _day(0), _day(2))
