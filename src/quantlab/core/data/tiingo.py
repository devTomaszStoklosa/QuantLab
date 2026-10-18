"""Tiingo end-of-day data for US equities: prices, dividends, splits, delistings (q5, X7c).

Endpoints (https://www.tiingo.com/documentation/end-of-day):
- GET /tiingo/daily/<ticker>/prices?startDate=&endDate= - one row per trading day with
  the raw `open`, `high`, `low`, `close`, `volume`, Tiingo's own adjusted columns
  (`adjClose`, ...), `divCash` (cash dividend with that ex-date) and `splitFactor`
  (new shares per old share on that ex-date, 1.0 on other days);
- GET /tiingo/daily/<ticker> - metadata with `startDate` and `endDate`, the first and
  last day Tiingo has a price for, and the `name` of the company.

Tiingo files one company under a ticker, usually the last one to use it, with that
company's whole price history; an earlier company with the ticker gets its prices
(#104). `listing` says which company it is, for `quantlab audit-tickers`.

Bars stay raw: the data layer adjusts them with the actions this adapter reports
(core.data.corporate_actions), so every source is adjusted the same way. Tiingo
gives no delisting return and no reason, so a delisting takes the hypothesis's
frozen assumption.
"""

import os
import time
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

import requests

from quantlab.core.data.cache import read_cached_json, write_cached_json
from quantlab.core.data.events import CashDividend, Delisting, InstrumentEvents, Split
from quantlab.core.data.identity import Listing
from quantlab.core.data.provider import DataSourceUnavailableError, PriceBar
from quantlab.core.universe import Instrument

_BASE_URL = "https://api.tiingo.com/tiingo/daily"
_SOURCE = "tiingo"
API_KEY_VARIABLE = "TIINGO_API_KEY"
INTERVAL_VARIABLE = "TIINGO_REQUEST_INTERVAL_SECONDS"
MONTHLY_SYMBOLS_VARIABLE = "TIINGO_MONTHLY_SYMBOLS"
# The free Starter plan ($0) as described on 2026-09-26: 50 requests an hour, 1,000
# a day and 500 different tickers a calendar month (DATA-SOURCES). Spacing requests
# by 90 s keeps within the first two; counting the tickers asked about stops a run
# before the third, so a download never hits a limit midway and resumes from the
# cache next month. Both environment variables exist only to follow a change of
# the plan's limits.
DEFAULT_INTERVAL_SECONDS = 90.0
DEFAULT_MONTHLY_SYMBOLS = 500
_TIMEOUT_SECONDS = 30
# A last price date seen this long after a range's end is final for that range:
# the ticker stopped trading within it.
_SETTLED_DAYS = 7
# Metadata kept in the cache: the last price date for delistings, the rest to tell
# which company Tiingo files under the ticker (#104).
_METADATA_FIELDS = ("ticker", "name", "startDate", "endDate", "description")

_last_request_at: float | None = None


def _today() -> date:
    return datetime.now(tz=UTC).date()


def _month() -> str:
    """The month Tiingo's monthly limit counts in. It resets on the 1st at midnight
    Eastern time; UTC-5 never turns the month before Tiingo does."""
    return (datetime.now(tz=UTC) - timedelta(hours=5)).strftime("%Y-%m")


def _day(stamp: str) -> date:
    """A Tiingo date, `2019-01-02` or `2019-01-02T00:00:00.000Z`."""
    return date.fromisoformat(stamp[:10])


class TiingoProvider:
    """DataProvider and source of corporate actions and delistings backed by Tiingo.

    Raw responses are cached on disk (data/cache/), so an interrupted download
    resumes where it stopped and `events` reuses the prices `fetch` downloaded.
    `progress` hears one line before each request, so a download that waits
    between requests for hours is visibly alive; cached answers ask nothing and
    say nothing.
    A ticker Tiingo does not know gives no bars rather than an error: a
    point-in-time universe has members a source may lack, and the run reports
    them (REQ-554).
    """

    def __init__(self, progress: Callable[[str], None] | None = None) -> None:
        key = os.environ.get(API_KEY_VARIABLE)
        if not key:
            raise DataSourceUnavailableError(
                f"Tiingo needs an API key: set {API_KEY_VARIABLE} (a free key at tiingo.com)"
            )
        self._key = key
        self._interval = float(os.environ.get(INTERVAL_VARIABLE, DEFAULT_INTERVAL_SECONDS))
        self._monthly_symbols = int(
            os.environ.get(MONTHLY_SYMBOLS_VARIABLE, DEFAULT_MONTHLY_SYMBOLS)
        )
        self._progress = progress or (lambda line: None)

    def _count(self, symbol: str) -> int:
        """Record `symbol` among the tickers asked about this month, or stop before a
        request would exceed the plan's monthly number of different tickers. Cached
        responses ask nothing, so they never count. The ticker's place this month."""
        month = _month()
        used = read_cached_json(_SOURCE, "symbols", month) or []
        if symbol in used:
            return used.index(symbol) + 1
        if len(used) >= self._monthly_symbols:
            raise DataSourceUnavailableError(
                f"Tiingo's free plan serves {self._monthly_symbols} different tickers a "
                f"month and {len(used)} were asked about in {month}; what was downloaded is "
                "cached, so rerun next month to continue"
            )
        write_cached_json(_SOURCE, [*used, symbol], "symbols", month)
        return len(used) + 1

    def _throttle(self) -> None:
        global _last_request_at
        if _last_request_at is not None:
            remaining = self._interval - (time.monotonic() - _last_request_at)
            if remaining > 0:
                time.sleep(remaining)
        _last_request_at = time.monotonic()

    def _get(self, symbol: str, what: str, url: str, params: dict | None = None) -> object | None:
        """The JSON body about `symbol`, or None when Tiingo does not know the ticker."""
        place = self._count(symbol)
        self._progress(
            f"Tiingo: {symbol} {what}, ticker {place} of {self._monthly_symbols} this month "
            f"({self._interval:g} s between requests)"
        )
        self._throttle()
        response = requests.get(
            url,
            params=params,
            headers={"Authorization": f"Token {self._key}", "Content-Type": "application/json"},
            timeout=_TIMEOUT_SECONDS,
        )
        if response.status_code == 404:
            return None
        if response.status_code in (401, 403):
            raise DataSourceUnavailableError(f"Tiingo refused the key in {API_KEY_VARIABLE}")
        if response.status_code == 429:
            raise DataSourceUnavailableError(
                "Tiingo's request limit is reached; what was downloaded is cached, "
                "so rerun later to continue"
            )
        response.raise_for_status()
        return response.json()

    def _prices(self, instrument: Instrument, start: date, end: date) -> list[dict]:
        cached = read_cached_json(_SOURCE, "prices", instrument.symbol, str(start), str(end))
        if cached is not None:
            return cached
        rows = self._get(
            instrument.symbol,
            f"prices {start}..{end}",
            f"{_BASE_URL}/{instrument.symbol}/prices",
            {
                "startDate": start.isoformat(),
                "endDate": end.isoformat(),
                "format": "json",
                "resampleFreq": "daily",
            },
        )
        rows = [row for row in rows or [] if start <= _day(row["date"]) <= end]
        rows.sort(key=lambda row: row["date"])
        write_cached_json(_SOURCE, rows, "prices", instrument.symbol, str(start), str(end))
        return rows

    def _metadata(self, instrument: Instrument, what: str, earlier: dict | None = None) -> dict:
        """Tiingo's metadata of the instrument's ticker, asked now and cached with the day
        it was asked; every field None for a ticker Tiingo does not know. With an
        `earlier` answer, its last price date and the day it was asked stay: runs date
        delistings from them, and Tiingo's answer may have changed since (#126)."""
        meta = self._get(instrument.symbol, what, f"{_BASE_URL}/{instrument.symbol}") or {}
        cached = {
            **{field: meta.get(field) for field in _METADATA_FIELDS},
            "fetchedOn": _today().isoformat(),
        }
        if earlier is not None:
            cached.update(endDate=earlier["endDate"], fetchedOn=earlier["fetchedOn"])
        write_cached_json(_SOURCE, cached, "meta", instrument.symbol)
        return cached

    def _last_price_date(self, instrument: Instrument, end: date) -> date | None:
        """The last day Tiingo has a price for, None for an unknown ticker.

        An active ticker's last day moves forward, so a cached value before `end`
        is asked again unless it was seen well after `end`: then it is final.
        """
        cached = read_cached_json(_SOURCE, "meta", instrument.symbol)
        if cached is not None:
            last = None if cached["endDate"] is None else _day(cached["endDate"])
            settled = _day(cached["fetchedOn"]) > end + timedelta(days=_SETTLED_DAYS)
            if settled or (last is not None and last >= end):
                return last
        cached = self._metadata(instrument, "last price date")
        return None if cached["endDate"] is None else _day(cached["endDate"])

    def listing(self, instrument: Instrument) -> Listing | None:
        """What Tiingo files under the instrument's ticker (#104): the company's name, its
        first and last price dates and its description; None for a ticker Tiingo does
        not know. Metadata cached for the last price date serves it; metadata cached
        before names were kept gets the names only and keeps its last price date."""
        cached = read_cached_json(_SOURCE, "meta", instrument.symbol)
        if cached is None:
            cached = self._metadata(instrument, "listing")
        elif "ticker" not in cached:
            cached = self._metadata(instrument, "listing", earlier=cached)
        if cached["ticker"] is None:
            return None
        return Listing(
            name=cached["name"] or "",
            start=None if cached["startDate"] is None else _day(cached["startDate"]),
            end=None if cached["endDate"] is None else _day(cached["endDate"]),
            description=cached["description"] or "",
        )

    def fetch(self, instrument: Instrument, start: date, end: date) -> list[PriceBar]:
        return [
            PriceBar(
                instrument_id=instrument.id,
                ts=_day(row["date"]),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
                adj_close=None if row.get("adjClose") is None else float(row["adjClose"]),
                source=_SOURCE,
            )
            for row in self._prices(instrument, start, end)
        ]

    def events(self, instrument: Instrument, start: date, end: date) -> InstrumentEvents:
        """Dividends and splits on their ex-dates in [start, end], and a delisting when the
        ticker's last price falls inside the range: dated the day after it (the data layer
        moves it to the next session), its return unknown."""
        actions = []
        for row in self._prices(instrument, start, end):
            ex_date = _day(row["date"])
            if (row.get("divCash") or 0.0) > 0.0:
                actions.append(
                    CashDividend(
                        instrument_id=instrument.id, ex_date=ex_date, amount=row["divCash"]
                    )
                )
            if row.get("splitFactor") not in (None, 1.0):
                actions.append(
                    Split(instrument_id=instrument.id, ex_date=ex_date, ratio=row["splitFactor"])
                )
        last = self._last_price_date(instrument, end)
        delisting = None
        if last is not None and start <= last < end:
            delisting = Delisting(
                instrument_id=instrument.id,
                date=last + timedelta(days=1),
                delisting_return=None,
            )
        return InstrumentEvents(actions=actions, delisting=delisting)
