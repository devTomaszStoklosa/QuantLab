from datetime import date, timedelta
from itertools import pairwise
from unittest.mock import Mock, patch

import pytest

from quantlab import cli
from quantlab.core.data import tiingo
from quantlab.core.data.corporate_actions import with_events
from quantlab.core.data.events import CashDividend, Split
from quantlab.core.data.provider import DataSourceUnavailableError
from quantlab.core.data.tiingo import TiingoProvider
from quantlab.core.universe import Instrument

# Shaped like Tiingo's documented end-of-day responses, with synthetic numbers: the
# cloud environment that wrote the adapter cannot reach api.tiingo.com, and raw
# prices are never committed (DATA-SOURCES rule 5). A 4:1 split on Monday
# 2020-08-31 and a 0.80 dividend going ex on Wednesday 2020-09-02.
_PRICES = [
    ("2020-08-27", 400.0, 0.0, 1.0),
    ("2020-08-28", 404.0, 0.0, 1.0),
    ("2020-08-31", 102.0, 0.0, 4.0),
    ("2020-09-01", 103.0, 0.0, 1.0),
    ("2020-09-02", 102.5, 0.8, 1.0),
    ("2020-09-03", 104.0, 0.0, 1.0),
]
_START, _END = date(2020, 8, 27), date(2020, 9, 30)
_SYN = Instrument(id="syn", symbol="SYN", asset_class="equity", quote_asset="USD")


def _row(day: str, close: float, dividend: float, split: float) -> dict:
    return {
        "date": f"{day}T00:00:00.000Z",
        "close": close,
        "high": close * 1.01,
        "low": close * 0.99,
        "open": close * 0.995,
        "volume": 1_000_000,
        "adjClose": close * 0.9,
        "adjHigh": close * 0.91,
        "adjLow": close * 0.89,
        "adjOpen": close * 0.9,
        "adjVolume": 1_000_000,
        "divCash": dividend,
        "splitFactor": split,
    }


def _meta(end_date: str | None) -> dict:
    return {
        "ticker": "SYN",
        "name": "Synthetic Corp",
        "exchangeCode": "NYSE",
        "startDate": "2010-01-04",
        "endDate": end_date,
        "description": "A synthetic company.",
    }


def _response(status_code: int, body: object) -> Mock:
    response = Mock()
    response.status_code = status_code
    response.json.return_value = body
    response.raise_for_status.side_effect = None if status_code < 400 else Exception("http")
    return response


def _tiingo(prices: list[tuple] | None = _PRICES, last: str | None = "2026-09-23") -> Mock:
    """requests.get answering like Tiingo: prices and metadata by URL; 404 when unknown."""

    def get(url: str, params=None, headers=None, timeout=None) -> Mock:
        if url.endswith("/prices"):
            if prices is None:
                return _response(404, {"detail": "Error: Ticker 'SYN' not found"})
            return _response(200, [_row(*row) for row in prices])
        return _response(200, _meta(last)) if prices is not None else _response(404, {})

    return Mock(side_effect=get)


@pytest.fixture(autouse=True)
def _offline(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)  # the disk cache lives under the working directory
    monkeypatch.setenv(tiingo.API_KEY_VARIABLE, "test-key")
    monkeypatch.setenv(tiingo.INTERVAL_VARIABLE, "0")
    monkeypatch.setattr(tiingo, "_last_request_at", None)
    monkeypatch.setattr(tiingo, "_today", lambda: date(2026, 9, 24))


def test_fetch_gives_the_raw_bars_of_the_range() -> None:
    get = _tiingo()
    with patch("quantlab.core.data.tiingo.requests.get", get):
        bars = TiingoProvider().fetch(_SYN, _START, _END)

    assert [bar.ts for bar in bars] == [date.fromisoformat(row[0]) for row in _PRICES]
    assert [bar.close for bar in bars] == [row[1] for row in _PRICES]
    assert bars[0].adj_close == pytest.approx(360.0)  # Tiingo's own, for reference only
    assert {bar.source for bar in bars} == {"tiingo"}
    assert all(bar.unadjusted_close is None for bar in bars)  # raw until the data layer
    (url,) = get.call_args.args
    assert url == "https://api.tiingo.com/tiingo/daily/SYN/prices"
    assert get.call_args.kwargs["params"]["startDate"] == "2020-08-27"
    assert get.call_args.kwargs["params"]["endDate"] == "2020-09-30"
    assert get.call_args.kwargs["headers"]["Authorization"] == "Token test-key"


def test_dividends_and_splits_come_from_the_price_rows() -> None:
    with patch("quantlab.core.data.tiingo.requests.get", _tiingo()):
        events = TiingoProvider().events(_SYN, _START, _END)

    assert events.actions == [
        Split(instrument_id="syn", ex_date=date(2020, 8, 31), ratio=4.0),
        CashDividend(instrument_id="syn", ex_date=date(2020, 9, 2), amount=0.8),
    ]
    assert events.delisting is None  # still trading in 2026


def test_adjusted_bars_carry_total_returns_across_the_split_and_the_dividend() -> None:
    with patch("quantlab.core.data.tiingo.requests.get", _tiingo()):
        provider = TiingoProvider()
        bars = provider.fetch(_SYN, _START, _END)
        events = provider.events(_SYN, _START, _END)

    adjusted = with_events({"syn": bars}, {"syn": events}).bars["syn"]
    returns = [b.close / a.close - 1.0 for a, b in pairwise(adjusted)]

    assert returns[1] == pytest.approx(102.0 * 4 / 404.0 - 1.0)  # no -75% on the split
    assert returns[3] == pytest.approx((102.5 + 0.8) / 103.0 - 1.0)  # dividend included
    assert [bar.raw_close for bar in adjusted] == [row[1] for row in _PRICES]


def test_prices_that_stop_inside_the_range_are_a_delisting_with_unknown_return() -> None:
    last_day = [row for row in _PRICES if row[0] <= "2020-09-03"]
    with patch("quantlab.core.data.tiingo.requests.get", _tiingo(last_day, last="2020-09-03")):
        events = TiingoProvider().events(_SYN, _START, _END)

    assert events.delisting is not None
    assert events.delisting.date == date(2020, 9, 4)  # the day after the last price
    assert events.delisting.delisting_return is None  # Tiingo does not say


def test_a_delisting_after_the_range_is_not_reported_in_it() -> None:
    with patch("quantlab.core.data.tiingo.requests.get", _tiingo(last="2021-03-01")):
        events = TiingoProvider().events(_SYN, _START, _END)

    assert events.delisting is None


def test_responses_are_cached_so_events_reuse_the_prices_and_a_rerun_asks_nothing() -> None:
    get = _tiingo()
    with patch("quantlab.core.data.tiingo.requests.get", get):
        provider = TiingoProvider()
        first = provider.fetch(_SYN, _START, _END)
        provider.events(_SYN, _START, _END)
        assert get.call_count == 2  # prices once, metadata once
        second = TiingoProvider().fetch(_SYN, _START, _END)
        TiingoProvider().events(_SYN, _START, _END)

    assert get.call_count == 2
    assert first == second


def test_a_last_price_date_before_the_end_is_final_once_seen_after_it() -> None:
    stopped = [row for row in _PRICES if row[0] <= "2020-09-01"]
    get = _tiingo(stopped, last="2020-09-01")
    with patch("quantlab.core.data.tiingo.requests.get", get):
        TiingoProvider().events(_SYN, _START, _END)
        TiingoProvider().events(_SYN, _START, _END)

    assert get.call_count == 2  # seen on 2026-09-24, long after the range: asked once


def test_a_last_price_date_seen_before_the_end_passed_is_asked_again(monkeypatch) -> None:
    get = _tiingo(last="2020-09-10")
    with patch("quantlab.core.data.tiingo.requests.get", get):
        monkeypatch.setattr(tiingo, "_today", lambda: date(2020, 9, 10))
        TiingoProvider().events(_SYN, _START, _END)
        monkeypatch.setattr(tiingo, "_today", lambda: date(2026, 9, 24))
        TiingoProvider().events(_SYN, _START, _END)

    metadata_requests = [c for c in get.call_args_list if not c.args[0].endswith("/prices")]
    assert len(metadata_requests) == 2


def test_an_unknown_ticker_gives_no_bars_and_no_events() -> None:
    with patch("quantlab.core.data.tiingo.requests.get", _tiingo(prices=None)):
        provider = TiingoProvider()
        bars = provider.fetch(_SYN, _START, _END)
        events = provider.events(_SYN, _START, _END)

    assert bars == []
    assert events.actions == []
    assert events.delisting is None


def test_without_a_key_the_source_is_unavailable_and_run_stops_before_fetching(
    monkeypatch,
) -> None:
    monkeypatch.delenv(tiingo.API_KEY_VARIABLE)

    with pytest.raises(DataSourceUnavailableError, match="TIINGO_API_KEY"):
        TiingoProvider()
    universe = cli.Universe.load("mvp-crypto").model_copy(update={"source": "tiingo"})
    with pytest.raises(cli.typer.Exit):
        cli._provider(universe)


def test_a_reached_request_limit_says_the_download_resumes_from_the_cache() -> None:
    with (
        patch(
            "quantlab.core.data.tiingo.requests.get",
            Mock(return_value=_response(429, {"detail": "limit"})),
        ),
        pytest.raises(DataSourceUnavailableError, match="cached, so rerun later"),
    ):
        TiingoProvider().fetch(_SYN, _START, _END)


def test_the_command_reports_an_unavailable_source_in_one_line(monkeypatch, capsys) -> None:
    def fail() -> None:
        raise DataSourceUnavailableError("Tiingo's request limit is reached")

    monkeypatch.setattr(cli, "app", fail)

    with pytest.raises(SystemExit) as exit_:
        cli.entry()

    assert exit_.value.code == 1
    assert capsys.readouterr().err == "Error: Tiingo's request limit is reached\n"


def test_requests_are_spaced_by_the_configured_interval(monkeypatch) -> None:
    monkeypatch.setenv(tiingo.INTERVAL_VARIABLE, "90")
    clock = iter([1000.0, 1030.0, 1120.0])  # first request, second one asks, second one sent
    sleeps = []
    monkeypatch.setattr(tiingo.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(tiingo.time, "sleep", sleeps.append)

    with patch("quantlab.core.data.tiingo.requests.get", _tiingo()):
        provider = TiingoProvider()
        provider.fetch(_SYN, _START, _END)
        provider.fetch(_SYN, _START, _END + timedelta(days=1))

    assert sleeps == [60.0]  # 90 s apart: 30 s had passed


def test_the_default_spacing_keeps_within_the_free_tiers_hourly_and_daily_limits() -> None:
    assert 3600 / tiingo.DEFAULT_INTERVAL_SECONDS <= 50
    assert 86400 / tiingo.DEFAULT_INTERVAL_SECONDS <= 1000
