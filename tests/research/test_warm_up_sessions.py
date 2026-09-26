"""Warm-ups counted in the sessions of the universe's market (q12, REQ-1201..1203)."""

from bisect import bisect_left
from datetime import date, timedelta
from pathlib import Path

import pytest

from quantlab.core.data.provider import PriceBar
from quantlab.core.universe import Instrument, Universe
from quantlab.research.definition import (
    CostModelParameters,
    CrossSectionalMomentumParameters,
    TimeSeriesMomentumParameters,
)
from quantlab.strategy.time_series_momentum import compute_momentum_signal
from quantlab.validation.holdout import parse_holdout_config

_COST_MODEL = CostModelParameters(name="realistic", fee_bps=3, k=0.05, vol_window=21)


def _weekday_market(name: str = "etfs") -> Universe:
    return Universe(
        name=name,
        asof_date=date(2026, 9, 26),
        source="synthetic",
        periods_per_year=252,
        instruments=[Instrument(id="aaa", symbol="AAA", asset_class="bond", quote_asset="USD")],
    )


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))


def _us_like_sessions(first_year: int, last_year: int) -> list[date]:
    """Weekdays without ten holidays a year and two unscheduled closures: a calendar at
    least as sparse as the NYSE's."""
    closed = {date(2001, 9, 11) + timedelta(days=i) for i in range(4)} | {
        date(2012, 10, 29),
        date(2012, 10, 30),
    }
    for year in range(first_year, last_year + 1):
        closed |= {
            date(year, 1, 1),
            _nth_weekday(year, 1, 0, 3),
            _nth_weekday(year, 2, 0, 3),
            _nth_weekday(year, 4, 4, 2),  # a Good Friday stand-in
            _nth_weekday(year, 5, 0, 4) + timedelta(days=7 if year % 2 else 0),
            date(year, 6, 19),
            date(year, 7, 4),
            _nth_weekday(year, 9, 0, 1),
            _nth_weekday(year, 11, 3, 4),
            date(year, 12, 25),
        }
    day, sessions = date(first_year, 1, 1), []
    while day.year <= last_year:
        if day.weekday() < 5 and day not in closed:
            sessions.append(day)
        day += timedelta(days=1)
    return sessions


@pytest.mark.parametrize("sessions", [1, 5, 21, 63, 126, 252, 504])
def test_a_weekday_market_s_calendar_days_hold_the_sessions(sessions: int) -> None:
    calendar = _us_like_sessions(1999, 2014)
    days = _weekday_market().calendar_days(sessions)

    shortest = min(
        bisect_left(calendar, start) - bisect_left(calendar, start - timedelta(days=days))
        for start in (date(2001, 1, 1) + timedelta(days=i) for i in range(13 * 365))
    )

    assert shortest >= sessions


@pytest.mark.parametrize("sessions", [1, 30, 90, 365, 730])
def test_a_market_open_every_day_needs_exactly_its_sessions(sessions: int) -> None:
    assert Universe.load("mvp-crypto").calendar_days(sessions) == sessions


def test_momentum_on_a_weekday_market_signals_from_the_window_s_first_day() -> None:
    universe = _weekday_market()
    parameters = TimeSeriesMomentumParameters(
        strategy="time_series_momentum",
        lookback_days=252,
        universe=universe.name,
        cost_model=_COST_MODEL,
    )
    bars = [
        PriceBar(
            instrument_id="aaa",
            ts=day,
            open=100.0 + i,
            high=100.0 + i,
            low=100.0 + i,
            close=100.0 + i,
            volume=1e6,
            source="test",
        )
        for i, day in enumerate(_us_like_sessions(2005, 2010))
    ]
    first = next(bar.ts for bar in bars if bar.ts >= date(2009, 1, 1))

    fetched = [bar for bar in bars if bar.ts >= parameters.fetch_start(first, universe)]
    # A warm-up of 252 calendar days holds about 173 sessions: no signal for months.
    too_short = [bar for bar in bars if bar.ts >= first - timedelta(days=252)]

    assert compute_momentum_signal(fetched, first, 252) is not None
    assert compute_momentum_signal(too_short, first, 252) is None


def test_every_frozen_crypto_definition_keeps_its_warm_up() -> None:
    crypto = Universe.load("mvp-crypto")
    definitions = Path(__file__).parents[2] / "config" / "holdout"

    for path in sorted(definitions.glob("*_v1.yaml")):
        parameters = parse_holdout_config(path).parameters
        if parameters.universe != crypto.name:
            continue
        resolved = parameters.resolve(
            lambda name: parse_holdout_config(definitions / f"{name}.yaml")
        )
        assert resolved.warm_up_calendar_days(crypto) == resolved.warm_up_days, path.name


def test_calendar_months_stay_calendar_days_on_a_weekday_market() -> None:
    parameters = CrossSectionalMomentumParameters(
        strategy="cross_sectional_momentum",
        formation_months=12,
        skip_months=1,
        quantile=0.1,
        long_short=True,
        min_price=5.0,
        missing_delisting_return=0.0,
        universe="etfs",
        cost_model=_COST_MODEL,
    )

    assert parameters.warm_up_calendar_days(_weekday_market()) == 14 * 31
    assert parameters.fetch_start(date(2020, 1, 1), _weekday_market()) == date(
        2020, 1, 1
    ) - timedelta(days=14 * 31)
