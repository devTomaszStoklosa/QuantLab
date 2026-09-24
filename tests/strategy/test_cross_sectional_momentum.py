from datetime import date, timedelta

import numpy as np
import pytest
from pydantic import TypeAdapter, ValidationError

from quantlab import cli
from quantlab.backtest.rebalance import OnSignalChange
from quantlab.core.data.events import Delisting, InstrumentEvents, Split
from quantlab.core.data.provider import PriceBar
from quantlab.core.universe import Instrument, Membership, Universe
from quantlab.costs.zero import ZeroCostModel
from quantlab.research.definition import (
    CostModelParameters,
    CrossSectionalMomentumParameters,
    StudyParameters,
)
from quantlab.strategy.cross_sectional_momentum import CrossSectionalMomentum, month_end_bar
from quantlab.strategy.members_only import MembersOnly


def _bar(instrument_id: str, ts: date, close: float, raw: float | None = None) -> PriceBar:
    return PriceBar(
        instrument_id=instrument_id,
        ts=ts,
        open=close,
        high=close,
        low=close,
        close=close,
        volume=1e6,
        source="test",
        unadjusted_close=raw,
    )


def _month_ends(instrument_id: str, closes: dict[tuple[int, int], float]) -> list[PriceBar]:
    """One bar on the 28th of each given month."""
    return [
        _bar(instrument_id, date(year, month, 28), close)
        for (year, month), close in sorted(closes.items())
    ]


def _strategy(**changes: object) -> CrossSectionalMomentum:
    arguments = {
        "formation_months": 12,
        "skip_months": 1,
        "quantile": 0.2,
        "long_short": True,
        "min_price": 5.0,
    }
    return CrossSectionalMomentum(**(arguments | changes))


def test_month_end_bar_is_the_last_bar_inside_the_month() -> None:
    bars = [_bar("a", date(2024, 1, d), float(d)) for d in (3, 30, 31)] + [
        _bar("a", date(2024, 3, 1), 1.0)
    ]

    assert month_end_bar(bars, 2024, 1).close == 31.0
    assert month_end_bar(bars, 2024, 2) is None
    assert month_end_bar(bars, 2023, 12) is None


def test_momentum_is_twelve_one_from_month_ends_before_the_holding_month() -> None:
    closes = {(2022, m): 100.0 + m for m in range(1, 13)} | {
        (2023, m): 200.0 + m for m in range(1, 13)
    }
    bars = _month_ends("a", closes)

    # Held in March 2023: from the end of February 2022 (m-13) to the end of January 2023 (m-2).
    assert _strategy().momentum(bars, 2023, 3) == pytest.approx(201.0 / 102.0 - 1.0)


def test_nothing_after_the_end_of_the_previous_month_is_used() -> None:
    closes = {(2022, m): 100.0 + m for m in range(1, 13)} | {(2023, 1): 150.0, (2023, 2): 160.0}
    bars = _month_ends("a", closes)
    later = bars + [_bar("a", date(2023, 3, 1), 1.0), _bar("a", date(2023, 3, 20), 999.0)]

    assert _strategy().momentum(later, 2023, 3) == _strategy().momentum(bars, 2023, 3)


def test_an_instrument_missing_a_window_end_is_not_ranked() -> None:
    closes = {(2022, m): 100.0 for m in range(3, 13)} | {(2023, 1): 110.0, (2023, 2): 120.0}

    assert _strategy().momentum(_month_ends("a", closes), 2023, 3) is None  # no Feb 2022


def test_the_price_filter_reads_the_quoted_price_not_the_adjusted_one() -> None:
    base = {(2022, m): 100.0 for m in range(1, 13)} | {(2023, 1): 120.0}
    bars = _month_ends("a", base)
    cheap = [*bars, _bar("a", date(2023, 2, 28), 120.0, raw=4.0)]  # adjusted high, quoted low
    dear = [*bars, _bar("a", date(2023, 2, 28), 3.0, raw=30.0)]  # adjusted low, quoted high

    assert _strategy().momentum(cheap, 2023, 3) is None
    assert _strategy().momentum(dear, 2023, 3) == pytest.approx(0.2)


def _cross_section(momenta: dict[str, float]) -> dict[str, list[PriceBar]]:
    return {
        instrument_id: _month_ends(
            instrument_id,
            {(2022, 2): 100.0, (2023, 1): 100.0 * (1.0 + value), (2023, 2): 100.0},
        )
        for instrument_id, value in momenta.items()
    }


def test_long_the_top_quantile_and_short_the_bottom_one_ties_by_id() -> None:
    momenta = {
        f"s{i:02d}": value
        for i, value in enumerate([0.5, 0.4, 0.3, 0.3, 0.1, 0.0, -0.1, -0.2, -0.2, -0.4])
    }

    signals = _strategy().generate_signals(_cross_section(momenta), date(2023, 3, 1))

    assert {(s.instrument_id, s.direction) for s in signals} == {
        ("s00", "long"),
        ("s01", "long"),
        ("s09", "short"),
        ("s07", "short"),  # tied with s08 at -0.2: the lower id goes first
    }
    assert {s.instrument_id: s.strength for s in signals}["s00"] == pytest.approx(0.5)


def test_long_only_holds_the_winners_alone() -> None:
    momenta = {f"s{i}": value for i, value in enumerate([0.3, 0.2, 0.1, 0.0, -0.1])}

    signals = _strategy(long_short=False, quantile=0.4).generate_signals(
        _cross_section(momenta), date(2023, 3, 15)
    )

    assert [(s.instrument_id, s.direction) for s in signals] == [("s0", "long"), ("s1", "long")]


def test_too_small_a_cross_section_takes_no_position() -> None:
    momenta = {f"s{i}": 0.1 * i for i in range(4)}  # 4 * 0.2 < 1 per leg

    assert _strategy().generate_signals(_cross_section(momenta), date(2023, 3, 1)) == []


def test_signals_stay_the_same_through_the_month() -> None:
    bars = _cross_section({f"s{i}": 0.1 * i for i in range(10)})
    strategy = _strategy()

    early = strategy.generate_signals(bars, date(2023, 3, 1))
    late = strategy.generate_signals(bars, date(2023, 3, 31))

    assert [(s.instrument_id, s.direction) for s in early] == [
        (s.instrument_id, s.direction) for s in late
    ]


def test_parameters_parse_from_a_definition_and_hold_between_formations() -> None:
    parameters = TypeAdapter(StudyParameters).validate_python(
        {
            "strategy": "cross_sectional_momentum",
            "formation_months": 12,
            "skip_months": 1,
            "quantile": 0.1,
            "long_short": True,
            "min_price": 5.0,
            "missing_delisting_return": -0.3,
            "universe": "sp500-pit",
            "cost_model": {"name": "realistic", "fee_bps": 5, "k": 0.05, "vol_window": 30},
        }
    )

    assert isinstance(parameters, CrossSectionalMomentumParameters)
    assert isinstance(parameters.build_rebalance_policy(), OnSignalChange)
    assert parameters.warm_up_days >= 13 * 31


@pytest.mark.parametrize(
    "changes",
    [
        {"skip_months": 12},
        {"quantile": 0.6},
        {"formation_months": 1},
        {"missing_delisting_return": None},
    ],
)
def test_parameters_reject_an_impossible_definition(changes: dict) -> None:
    arguments = {
        "strategy": "cross_sectional_momentum",
        "formation_months": 12,
        "skip_months": 1,
        "quantile": 0.1,
        "long_short": True,
        "min_price": 5.0,
        "missing_delisting_return": -0.3,
        "universe": "u",
        "cost_model": CostModelParameters(name="realistic", fee_bps=5, k=0.05, vol_window=30),
    }
    with pytest.raises(ValidationError):
        CrossSectionalMomentumParameters(**(arguments | changes))


# End to end on a synthetic point-in-time universe: joiners, leavers, a split and a delisting.

_START = date(2019, 1, 1)
_END = date(2021, 12, 31)
_NAMES = [f"s{i:02d}" for i in range(20)]
_SPLIT = date(2020, 6, 1)


class _Market:
    """Economic price paths; s03's quote divides by 4 at its split, s19 stops at its delisting."""

    def __init__(self) -> None:
        rng = np.random.default_rng(5)
        days = (_END - _START).days + 1
        drifts = rng.normal(0.0003, 0.0008, len(_NAMES))
        self.closes = {
            name: 50.0 * np.cumprod(1.0 + drift + rng.normal(0.0, 0.015, days))
            for name, drift in zip(_NAMES, drifts, strict=True)
        }

    def economic(self, instrument_id: str, start: date, end: date) -> list[PriceBar]:
        return [
            _bar(instrument_id, _START + timedelta(days=i), float(close))
            for i, close in enumerate(self.closes[instrument_id])
            if start <= _START + timedelta(days=i) <= end
        ]

    def fetch(self, instrument: Instrument, start: date, end: date) -> list[PriceBar]:
        last = date(2021, 3, 15) if instrument.id == "s19" else _END
        bars = self.economic(instrument.id, start, min(end, last))
        if instrument.id == "s03":
            bars = [
                bar.model_copy(update={"close": bar.close / 4.0}) if bar.ts >= _SPLIT else bar
                for bar in bars
            ]
        return bars

    def events(self, instrument: Instrument, start: date, end: date) -> InstrumentEvents:
        if instrument.id == "s19":
            return InstrumentEvents(
                delisting=Delisting(
                    instrument_id="s19", date=date(2021, 3, 16), delisting_return=None
                )
            )
        if instrument.id == "s03":
            return InstrumentEvents(actions=[Split(instrument_id="s03", ex_date=_SPLIT, ratio=4.0)])
        return InstrumentEvents()


_UNIVERSE = Universe(
    name="pit-xs",
    asof_date=_END,
    source="synthetic",
    periods_per_year=252,
    market_proxy="s00",
    instruments=[
        Instrument(id=n, symbol=n.upper(), asset_class="equity", quote_asset="USD") for n in _NAMES
    ],
    memberships=[
        *(Membership(instrument_id=n, start=_START, end=None) for n in _NAMES[:15]),
        *(Membership(instrument_id=n, start=date(2020, 7, 1), end=None) for n in _NAMES[15:18]),
        Membership(instrument_id="s18", start=_START, end=date(2020, 9, 30)),
        Membership(instrument_id="s19", start=_START, end=date(2021, 3, 16)),
    ],
)

_PARAMETERS = CrossSectionalMomentumParameters(
    strategy="cross_sectional_momentum",
    formation_months=6,
    skip_months=1,
    quantile=0.2,
    long_short=True,
    min_price=5.0,
    missing_delisting_return=-0.3,
    universe="pit-xs",
    cost_model=CostModelParameters(name="realistic", fee_bps=5, k=0.05, vol_window=20),
)
_RUN_START, _RUN_END = date(2020, 1, 1), date(2021, 12, 31)


def test_a_run_holds_members_only_in_equal_legs_and_trades_about_monthly() -> None:
    run = cli.run_study(
        _Market(), _PARAMETERS, ZeroCostModel(), _UNIVERSE, _RUN_START, _RUN_END, 0, "t"
    )

    for previous, current in zip(run.snapshots, run.snapshots[1:], strict=False):
        assert set(current.positions) <= _UNIVERSE.members(previous.ts), previous.ts
    held = [s for s in run.snapshots if s.positions]
    assert held, "the strategy never held a position"
    assert all(
        sum(w > 0 for w in s.positions.values()) == sum(w < 0 for w in s.positions.values())
        for s in held
    )
    # 24 formations plus membership changes and the delisting, not 730 daily rebalances.
    assert len([s for s in run.snapshots if s.traded]) < 40


def test_both_engines_agree_on_the_cross_sectional_run() -> None:
    comparison = cli.run_engine_comparison(
        _Market(), _PARAMETERS, _UNIVERSE, _RUN_START, _RUN_END, 0, "t", 1e9, 1.0
    )

    assert comparison.parity_difference < 1e-12


def test_a_split_inside_the_window_leaves_the_momentum_economic() -> None:
    market = _Market()
    bars = cli._fetch_bars(market, _UNIVERSE, _PARAMETERS, _RUN_START, date(2020, 8, 31))
    strategy = _PARAMETERS.build_strategy()
    raw = market.fetch(_UNIVERSE.instruments[3], _START, date(2020, 8, 31))
    economic = market.economic("s03", _START, date(2020, 8, 31))

    # Held in August 2020: January to June 2020, across the 4:1 split on 1 June.
    adjusted = strategy.momentum(bars["s03"], 2020, 8)
    assert adjusted == pytest.approx(strategy.momentum(economic, 2020, 8), rel=1e-12)
    assert strategy.momentum(raw, 2020, 8) < adjusted - 0.5


def test_the_membership_decides_the_ranking_within_the_month() -> None:
    bars = cli._fetch_bars(_Market(), _UNIVERSE, _PARAMETERS, _RUN_START, _RUN_END)
    strategy = MembersOnly(_PARAMETERS.build_strategy(), _UNIVERSE)

    def book(day: date) -> set[tuple[str, str]]:
        return {(s.instrument_id, s.direction) for s in strategy.generate_signals(bars, day)}

    assert book(date(2020, 8, 3)) == book(date(2020, 8, 31))
    assert all(name != "s18" for name, _ in book(date(2020, 10, 1)))  # left on 30 September
