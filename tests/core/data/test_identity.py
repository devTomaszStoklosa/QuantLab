from datetime import date, timedelta

import pytest

from quantlab.core.data.identity import (
    Listing,
    TickerAudit,
    former_members,
    member_medians,
    member_spans,
    name_similarity,
    name_words,
    review_order,
)
from quantlab.core.data.provider import PriceBar
from quantlab.core.universe import Instrument, Membership, Universe

# Names as Wikipedia and Tiingo spelled them in step 0 of #104 (2026-10-02); every
# price below is synthetic.
_START, _END = date(2005, 1, 1), date(2025, 12, 31)


def _stock(symbol: str) -> Instrument:
    return Instrument(id=symbol.lower(), symbol=symbol, asset_class="equity", quote_asset="USD")


def _audit(
    listing: Listing | None,
    names: tuple[str, ...] = ("Millipore Corp.",),
    first: date = _START,
    last: date = date(2010, 7, 14),
) -> TickerAudit:
    return TickerAudit(
        instrument=_stock("MIL"),
        index_names=names,
        first_member_day=first,
        last_member_day=last,
        listing=listing,
    )


def test_a_name_s_words_leave_out_punctuation_case_and_legal_forms() -> None:
    assert name_words("El Paso Corp.") == {"el", "paso"}
    assert name_words("SUPERVALU INC.") == {"supervalu"}
    assert name_words("The Hartford Financial Services Group") == {
        "hartford",
        "financial",
        "services",
    }


@pytest.mark.parametrize(
    ("index_name", "source_name", "similarity"),
    [
        ("Millipore Corp.", "MFC Industrial Ltd", 0.0),  # another company took MIL
        ("El Paso Corp.", "Empire Petroleum Corporation", 0.0),
        ("Supervalu", "SUPERVALU INC.", 1.0),  # the same one, spelled differently
        ("Sprint Nextel", "Sprint Corp", 0.5),  # renamed: a review tells
        ("Inc.", "Sprint Corp", 0.0),  # nothing but a legal form
    ],
)
def test_names_compare_by_the_words_they_share(
    index_name: str, source_name: str, similarity: float
) -> None:
    assert name_similarity(index_name, source_name) == similarity


def test_another_company_s_name_is_flagged() -> None:
    audit = _audit(Listing("MFC Industrial Ltd", date(1996, 5, 8), date(2016, 2, 12)))

    assert audit.similarity == 0.0
    assert audit.flags == ["name differs"]


def test_prices_that_start_after_the_membership_are_flagged() -> None:
    audit = _audit(
        Listing("Empire Petroleum Corporation", date(2011, 2, 23), date(2026, 10, 1)),
        names=("El Paso Corp.",),
        last=date(2012, 5, 24),
    )

    assert audit.flags == ["name differs", "prices start after membership"]


def test_the_member_s_own_prices_raise_no_flag() -> None:
    audit = _audit(
        Listing("SUPERVALU INC.", date(1985, 7, 1), date(2018, 12, 14)),
        names=("Supervalu",),
        last=date(2012, 12, 19),
    )

    assert audit.flags == []


def test_a_last_price_a_few_days_before_the_removal_is_no_flag_but_months_before_is() -> None:
    last = date(2010, 7, 14)

    def flags(last_price: date) -> list[str]:
        return _audit(Listing("Millipore Corporation", date(1990, 1, 2), last_price)).flags

    assert flags(last - timedelta(days=3)) == []  # the last session before a weekend
    assert flags(last - timedelta(days=90)) == ["prices end before membership"]


def test_a_ticker_the_source_does_not_know_or_a_member_without_a_name_is_flagged() -> None:
    assert _audit(None).flags == ["unknown to the source"]
    assert _audit(None).similarity is None
    nameless = _audit(Listing("Millipore Corporation", date(1990, 1, 2), date(2010, 7, 14)), ())
    assert nameless.flags == ["no name in the index's table"]


def _universe() -> Universe:
    return Universe(
        name="pit",
        asof_date=_END,
        source="synthetic",
        periods_per_year=252,
        market_proxy="spy",
        instruments=[_stock(s) for s in ("AAA", "MIL", "OLD", "TWICE", "SPY")],
        memberships=[
            Membership(instrument_id="aaa", start=date(2000, 1, 1), end=None),
            Membership(instrument_id="mil", start=date(2000, 1, 1), end=date(2010, 7, 14)),
            Membership(instrument_id="old", start=date(2000, 1, 1), end=date(2003, 6, 30)),
            Membership(instrument_id="twice", start=date(2006, 3, 1), end=date(2008, 2, 29)),
            Membership(instrument_id="twice", start=date(2019, 5, 1), end=date(2021, 9, 30)),
        ],
    )


def test_former_members_are_the_window_s_members_that_are_not_members_any_more() -> None:
    # aaa is a member today, old left before the window, SPY is only the benchmark.
    assert [i.id for i in former_members(_universe(), _START, _END)] == ["mil", "twice"]


def test_member_spans_are_cut_to_the_window() -> None:
    spans = member_spans(_universe(), "twice", date(2007, 1, 1), date(2019, 12, 31))

    assert [(span.start, span.end) for span in spans] == [
        (date(2007, 1, 1), date(2008, 2, 29)),
        (date(2019, 5, 1), date(2019, 12, 31)),
    ]
    assert member_spans(_universe(), "aaa", _START, _END)[0].end == _END


def _bar(day: date, close: float, volume: float, raw: float | None = None) -> PriceBar:
    return PriceBar(
        instrument_id="mil",
        ts=day,
        open=close,
        high=close,
        low=close,
        close=close,
        volume=volume,
        source="synthetic",
        unadjusted_close=raw,
    )


def test_medians_are_of_member_days_quoted_prices() -> None:
    spans = [Membership(instrument_id="mil", start=date(2010, 7, 1), end=date(2010, 7, 14))]
    bars = [
        _bar(date(2010, 6, 30), 1.0, 1.0),  # before the membership: left out
        _bar(date(2010, 7, 1), 10.0, 100.0),
        _bar(date(2010, 7, 2), 20.0, 300.0),
        _bar(date(2010, 7, 6), 99.0, 200.0, raw=30.0),  # an adjusted bar counts as quoted
        _bar(date(2010, 7, 15), 1e6, 1e6),  # after it
    ]

    assert member_medians(bars, spans) == (20.0, 6000.0)
    assert member_medians([], spans) == (None, None)


def test_flagged_tickers_come_first_the_least_similar_first() -> None:
    clean = _audit(Listing("Millipore Corporation", date(1990, 1, 2), date(2010, 7, 14)))
    partly = _audit(Listing("Millipore Sigma Holdings", date(1990, 1, 2), date(2010, 7, 14)))
    other = _audit(Listing("MFC Industrial Ltd", date(1996, 5, 8), date(2016, 2, 12)))
    unknown = _audit(None)

    assert review_order([clean, partly, other, unknown]) == [unknown, other, partly, clean]
