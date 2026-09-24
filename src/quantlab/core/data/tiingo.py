"""Tiingo end-of-day data for US equities: prices, dividends, splits, delistings (q5, X7c).

Endpoints (https://www.tiingo.com/documentation/end-of-day):
- GET /tiingo/daily/<ticker>/prices?startDate=&endDate= - one row per trading day with
  the raw `open`, `high`, `low`, `close`, `volume`, Tiingo's own adjusted columns
  (`adjClose`, ...), `divCash` (cash dividend with that ex-date) and `splitFactor`
  (new shares per old share on that ex-date, 1.0 on other days);
- GET /tiingo/daily/<ticker> - metadata with `startDate` and `endDate`, the first and
  last day Tiingo has a price for.

Bars stay raw: the data layer adjusts them with the actions this adapter reports
(core.data.corporate_actions), so every source is adjusted the same way. Tiingo
gives no delisting return and no reason, so a delisting takes the hypothesis's
frozen assumption.
"""

import os
import time
from datetime import UTC, date, datetime, timedelta

import requests

from quantlab.core.data.cache import read_cached_json, write_cached_json
from quantlab.core.data.events import CashDividend, Delisting, InstrumentEvents, Split
from quantlab.core.data.provider import DataSourceUnavailableError, PriceBar
from quantlab.core.universe import Instrument

_BASE_URL = "https://api.tiingo.com/tiingo/daily"
_SOURCE = "tiingo"
API_KEY_VARIABLE = "TIINGO_API_KEY"
INTERVAL_VARIABLE = "TIINGO_REQUEST_INTERVAL_SECONDS"
# Spacing between requests on our side (DATA-SOURCES rule 2). 90 s keeps within
# both limits of the free tier as known when this was written (about 50 requests
# an hour and 1,000 a day; to verify on tiingo.com). A paid tier can set a
# shorter interval through TIINGO_REQUEST_INTERVAL_SECONDS.
DEFAULT_INTERVAL_SECONDS = 90.0
_TIMEOUT_SECONDS = 30
# A last price date seen this long after a range's end is final for that range:
# the ticker stopped trading within it.
_SETTLED_DAYS = 7

_last_request_at: float | None = None


def _today() -> date:
    return datetime.now(tz=UTC).date()


def _day(stamp: str) -> date:
    """A Tiingo date, `2019-01-02` or `2019-01-02T00:00:00.000Z`."""
    return date.fromisoformat(stamp[:10])


class TiingoProvider:
    """DataProvider and source of corporate actions and delistings backed by Tiingo.

    Raw responses are cached on disk (data/cache/), so an interrupted download
    resumes where it stopped and `events` reuses the prices `fetch` downloaded.
    A ticker Tiingo does not know gives no bars rather than an error: a
    point-in-time universe has members a source may lack, and the run reports
    them (REQ-554).
    """

    def __init__(self) -> None:
        key = os.environ.get(API_KEY_VARIABLE)
        if not key:
            raise DataSourceUnavailableError(
                f"Tiingo needs an API key: set {API_KEY_VARIABLE} (a free key at tiingo.com)"
            )
        self._key = key
        self._interval = float(os.environ.get(INTERVAL_VARIABLE, DEFAULT_INTERVAL_SECONDS))

    def _throttle(self) -> None:
        global _last_request_at
        if _last_request_at is not None:
            remaining = self._interval - (time.monotonic() - _last_request_at)
            if remaining > 0:
                time.sleep(remaining)
        _last_request_at = time.monotonic()

    def _get(self, url: str, params: dict | None = None) -> object | None:
        """The JSON body, or None when Tiingo does not know the ticker."""
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
        meta = self._get(f"{_BASE_URL}/{instrument.symbol}") or {}
        cached = {"endDate": meta.get("endDate"), "fetchedOn": _today().isoformat()}
        write_cached_json(_SOURCE, cached, "meta", instrument.symbol)
        return None if cached["endDate"] is None else _day(cached["endDate"])

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
