import time
from datetime import UTC, date, datetime, timedelta

import requests

from quantlab.core.data.cache import read_cached_bars, write_cached_bars
from quantlab.core.data.provider import DataNotFoundError, PriceBar, WithoutEvents
from quantlab.core.universe import Instrument

_BASE_URL = "https://api.binance.com/api/v3/klines"
_MIN_REQUEST_INTERVAL_SECONDS = 0.25
_SOURCE = "binance"
_INVALID_SYMBOL_CODE = -1121

_last_request_at: float | None = None


def _throttle() -> None:
    global _last_request_at
    if _last_request_at is not None:
        remaining = _MIN_REQUEST_INTERVAL_SECONDS - (time.monotonic() - _last_request_at)
        if remaining > 0:
            time.sleep(remaining)
    _last_request_at = time.monotonic()


def _to_open_time_ms(day: date) -> int:
    return int(datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp() * 1000)


def _from_open_time_ms(ms: int) -> date:
    return datetime.fromtimestamp(ms / 1000, tz=UTC).date()


class BinanceProvider(WithoutEvents):
    """DataProvider backed by Binance public REST klines. No API key required."""

    def fetch(self, instrument: Instrument, start: date, end: date) -> list[PriceBar]:
        cached = read_cached_bars(_SOURCE, instrument.id, start, end)
        if cached is not None:
            return [PriceBar(**bar) for bar in cached]

        bars: list[PriceBar] = []
        page_start = start
        while True:
            _throttle()
            response = requests.get(
                _BASE_URL,
                params={
                    "symbol": instrument.symbol,
                    "interval": "1d",
                    "startTime": _to_open_time_ms(page_start),
                    "endTime": _to_open_time_ms(end),
                    "limit": 1000,
                },
                timeout=10,
            )
            if response.status_code == 400 and response.json().get("code") == _INVALID_SYMBOL_CODE:
                raise DataNotFoundError(instrument.symbol)
            response.raise_for_status()

            candles = response.json()
            if not candles:
                break

            page_bars = [
                PriceBar(
                    instrument_id=instrument.id,
                    ts=_from_open_time_ms(candle[0]),
                    open=float(candle[1]),
                    high=float(candle[2]),
                    low=float(candle[3]),
                    close=float(candle[4]),
                    volume=float(candle[5]),
                    adj_close=None,
                    source=_SOURCE,
                )
                for candle in candles
            ]
            bars.extend(page_bars)

            # A single request returns at most 1000 daily bars (Binance API
            # limit), so a range longer than that needs multiple pages: keep
            # requesting from just past the last bar received until either the
            # range is exhausted or a short page signals no more data exists.
            if page_bars[-1].ts >= end or len(candles) < 1000:
                break
            page_start = page_bars[-1].ts + timedelta(days=1)

        bars.sort(key=lambda bar: bar.ts)

        write_cached_bars(
            _SOURCE, instrument.id, start, end, [bar.model_dump(mode="json") for bar in bars]
        )
        return bars
