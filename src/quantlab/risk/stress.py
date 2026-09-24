from collections.abc import Mapping
from datetime import date
from itertools import pairwise

from pydantic import BaseModel, field_validator

from quantlab.backtest.run import BacktestRun
from quantlab.core.data.provider import PriceBar


class ShockScenario(BaseModel):
    name: str
    description: str
    shocks: dict[str, float]  # instrument id -> instantaneous simple return

    @field_validator("shocks")
    @classmethod
    def _prices_stay_positive(cls, shocks: dict[str, float]) -> dict[str, float]:
        for instrument_id, shock in shocks.items():
            if shock <= -1.0:
                raise ValueError(
                    f"Shock {shock} would take {instrument_id} to a zero or negative price"
                )
        return shocks


class StressResult(BaseModel):
    scenario: ShockScenario
    last_held_on: date
    last_impact: float
    worst_held_on: date
    worst_impact: float
    losing_share: float


def stress_impact(positions: Mapping[str, float], scenario: ShockScenario) -> float:
    """Change in portfolio value, as a fraction of equity, if the scenario hit now (REQ-052).

    Weights are fractions of equity, so for spot positions and an instantaneous
    shock the impact is exactly sum(weight * shock) - no risk model involved.
    A held instrument the scenario says nothing about is an error, not 0%.
    """
    held = {instrument_id: weight for instrument_id, weight in positions.items() if weight != 0.0}
    missing = sorted(held.keys() - scenario.shocks.keys())
    if missing:
        raise ValueError(f"Scenario {scenario.name} has no shock for held {', '.join(missing)}")
    return sum(weight * scenario.shocks[instrument_id] for instrument_id, weight in held.items())


def stress_run(run: BacktestRun, scenario: ShockScenario) -> StressResult:
    """The scenario applied to the last day's positions and to every day's.

    A snapshot's positions are the weights held over the day ending at its ts.
    Days count from the first held position, so the warm-up is not diluting
    the share of days on which the shock would have caused a loss.
    """
    snapshots = run.snapshots
    first = next((i for i in range(1, len(snapshots)) if snapshots[i].positions), None)
    if first is None:
        raise ValueError("Stress test needs a run that held positions")

    impacts = [
        (snapshot.ts, stress_impact(snapshot.positions, scenario)) for snapshot in snapshots[first:]
    ]
    worst_held_on, worst_impact = min(impacts, key=lambda item: item[1])
    last_held_on, last_impact = impacts[-1]
    return StressResult(
        scenario=scenario,
        last_held_on=last_held_on,
        last_impact=last_impact,
        worst_held_on=worst_held_on,
        worst_impact=worst_impact,
        losing_share=sum(1 for _, impact in impacts if impact < 0.0) / len(impacts),
    )


def worst_day_scenario(
    name: str, bars: dict[str, list[PriceBar]], reference_instrument: str, start: date, end: date
) -> ShockScenario:
    """Replay of the reference instrument's worst daily return between start and end.

    Every instrument is shocked by the return it actually had that day, so the
    scenario comes from the data rather than from hand-picked numbers. In a
    point-in-time universe (q5) some instruments did not trade that day - not
    yet listed or already delisted - yet may be held on other days; they move
    with the reference instrument, and the description says how many did.
    """
    reference_bars = sorted(bars[reference_instrument], key=lambda bar: bar.ts)
    candidates = [
        (current.close / previous.close - 1.0, previous.ts, current.ts)
        for previous, current in pairwise(reference_bars)
        if start <= current.ts <= end
    ]
    if not candidates:
        raise ValueError(f"No {reference_instrument} returns between {start} and {end}")
    worst, previous_ts, worst_ts = min(candidates)

    shocks = {}
    without_prices = 0
    for instrument_id, instrument_bars in bars.items():
        closes = {bar.ts: bar.close for bar in instrument_bars}
        if previous_ts in closes and worst_ts in closes:
            shocks[instrument_id] = closes[worst_ts] / closes[previous_ts] - 1.0
        else:
            shocks[instrument_id] = worst
            without_prices += 1
    description = f"replay of {reference_instrument}'s worst day in the period, {worst_ts}"
    if without_prices:
        description += (
            f"; {without_prices} instruments without prices that day move with "
            f"{reference_instrument}"
        )
    return ShockScenario(name=name, description=description, shocks=shocks)
