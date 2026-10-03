from datetime import date

from quantlab.core.data.coverage import price_coverage
from quantlab.core.data.events import CashDividend, InstrumentEvents
from quantlab.core.data.provider import NotInSource, PriceBar
from quantlab.core.universe import Instrument, Membership, Universe

_DAY = date(2008, 1, 2)


def _stock(symbol: str) -> Instrument:
    return Instrument(id=symbol.lower(), symbol=symbol, asset_class="equity", quote_asset="USD")


class _Source:
    """One synthetic bar and one dividend for any ticker, and a log of what was asked."""

    def __init__(self) -> None:
        self.asked: list[tuple[str, str]] = []

    def fetch(self, instrument: Instrument, start: date, end: date) -> list[PriceBar]:
        self.asked.append(("prices", instrument.symbol))
        return [
            PriceBar(
                instrument_id=instrument.id,
                ts=_DAY,
                open=1.0,
                high=1.0,
                low=1.0,
                close=1.0,
                volume=1.0,
                source="synthetic",
            )
        ]

    def events(self, instrument: Instrument, start: date, end: date) -> InstrumentEvents:
        self.asked.append(("events", instrument.symbol))
        return InstrumentEvents(
            actions=[CashDividend(instrument_id=instrument.id, ex_date=_DAY, amount=0.1)]
        )


def test_an_instrument_not_in_source_gets_nothing_and_the_source_is_not_asked() -> None:
    source = _Source()
    provider = NotInSource(source, ["mil"])

    assert provider.fetch(_stock("MIL"), _DAY, _DAY) == []
    assert provider.events(_stock("MIL"), _DAY, _DAY) == InstrumentEvents()
    assert source.asked == []  # no request, so no ticker counted in Tiingo's month


def test_every_other_instrument_comes_from_the_source() -> None:
    source = _Source()
    provider = NotInSource(source, ["mil"])

    assert len(provider.fetch(_stock("AAA"), _DAY, _DAY)) == 1
    assert len(provider.events(_stock("AAA"), _DAY, _DAY).actions) == 1
    assert source.asked == [("prices", "AAA"), ("events", "AAA")]


def test_a_member_not_in_source_is_a_member_without_prices_in_the_coverage_report() -> None:
    universe = Universe(
        name="pit",
        asof_date=_DAY,
        source="synthetic",
        periods_per_year=252,
        instruments=[_stock("AAA"), _stock("MIL")],
        memberships=[Membership(instrument_id=i, start=_DAY, end=None) for i in ("aaa", "mil")],
        not_in_source=["mil"],
    )
    provider = NotInSource(_Source(), universe.not_in_source)
    bars = {i.id: provider.fetch(i, _DAY, _DAY) for i in universe.instruments}

    coverage = price_coverage(universe, bars, _DAY, _DAY)

    assert (coverage.priced_days, coverage.member_days) == (1, 2)
    assert coverage.without_prices == ["mil"]
