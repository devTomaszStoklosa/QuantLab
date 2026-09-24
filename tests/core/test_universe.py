from datetime import date

import pytest
from pydantic import ValidationError

from quantlab.core.universe import Instrument, Membership, Universe


def test_load_returns_configured_universe() -> None:
    universe = Universe.load("mvp-crypto")

    symbols = {instrument.symbol for instrument in universe.instruments}
    assert symbols == {"BTCUSDT", "ETHUSDT"}
    assert all(instrument.asset_class == "crypto" for instrument in universe.instruments)
    assert all(instrument.quote_asset == "USDT" for instrument in universe.instruments)


def test_load_unknown_name_raises() -> None:
    with pytest.raises(ValueError, match="does-not-exist"):
        Universe.load("does-not-exist")


def test_duplicate_instrument_ids_rejected() -> None:
    duplicate = Instrument(
        id="btc-usdt", symbol="BTCUSDT", asset_class="crypto", quote_asset="USDT"
    )

    with pytest.raises(ValidationError, match="Duplicate instrument id"):
        Universe(name="broken", asof_date=date(2026, 9, 23), instruments=[duplicate, duplicate])


def _equity(instrument_id: str) -> Instrument:
    return Instrument(
        id=instrument_id, symbol=instrument_id.upper(), asset_class="equity", quote_asset="USD"
    )


def _point_in_time(*memberships: Membership) -> Universe:
    ids = sorted({membership.instrument_id for membership in memberships})
    return Universe(
        name="pit",
        asof_date=date(2026, 9, 24),
        instruments=[_equity(i) for i in ids],
        memberships=list(memberships),
    )


def test_a_static_universe_has_every_instrument_on_every_date() -> None:
    universe = Universe.load("mvp-crypto")

    assert universe.is_static
    assert universe.members(date(1990, 1, 1)) == {"btc-usdt", "eth-usdt"}


def test_members_follow_their_periods_with_inclusive_ends() -> None:
    universe = _point_in_time(
        Membership(instrument_id="aaa", start=date(2020, 1, 1), end=date(2020, 6, 30)),
        Membership(instrument_id="aaa", start=date(2021, 1, 1), end=None),
        Membership(instrument_id="bbb", start=date(2020, 3, 1), end=date(2020, 3, 31)),
    )

    assert not universe.is_static
    assert universe.members(date(2019, 12, 31)) == set()
    assert universe.members(date(2020, 1, 1)) == {"aaa"}
    assert universe.members(date(2020, 3, 31)) == {"aaa", "bbb"}
    assert universe.members(date(2020, 6, 30)) == {"aaa"}
    assert universe.members(date(2020, 7, 1)) == set()  # between aaa's two periods
    assert universe.members(date(2030, 1, 1)) == {"aaa"}


def test_every_instrument_of_a_point_in_time_universe_needs_a_membership() -> None:
    with pytest.raises(ValidationError, match="without a membership.*'bbb'"):
        Universe(
            name="pit",
            asof_date=date(2026, 9, 24),
            instruments=[_equity("aaa"), _equity("bbb")],
            memberships=[Membership(instrument_id="aaa", start=date(2020, 1, 1), end=None)],
        )


def test_memberships_of_unknown_instruments_are_rejected() -> None:
    with pytest.raises(ValidationError, match="not in universe.*'zzz'"):
        Universe(
            name="pit",
            asof_date=date(2026, 9, 24),
            instruments=[_equity("aaa")],
            memberships=[
                Membership(instrument_id="aaa", start=date(2020, 1, 1), end=None),
                Membership(instrument_id="zzz", start=date(2020, 1, 1), end=None),
            ],
        )


@pytest.mark.parametrize(
    "second",
    [
        Membership(instrument_id="aaa", start=date(2020, 6, 30), end=None),  # touches the end
        Membership(instrument_id="aaa", start=date(2019, 1, 1), end=date(2020, 1, 1)),
    ],
)
def test_overlapping_memberships_are_rejected(second: Membership) -> None:
    first = Membership(instrument_id="aaa", start=date(2020, 1, 1), end=date(2020, 6, 30))

    with pytest.raises(ValidationError, match="Overlapping memberships of aaa"):
        _point_in_time(first, second)


def test_an_open_membership_overlaps_every_later_one() -> None:
    with pytest.raises(ValidationError, match="Overlapping"):
        _point_in_time(
            Membership(instrument_id="aaa", start=date(2020, 1, 1), end=None),
            Membership(instrument_id="aaa", start=date(2025, 1, 1), end=None),
        )


def test_a_membership_cannot_end_before_it_starts() -> None:
    with pytest.raises(ValidationError, match="ends 2019-12-31 before it starts 2020-01-01"):
        Membership(instrument_id="aaa", start=date(2020, 1, 1), end=date(2019, 12, 31))
