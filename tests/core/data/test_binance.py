from datetime import date
from unittest.mock import Mock, patch

import pytest

from quantlab.core.data.binance import BinanceProvider
from quantlab.core.data.provider import DataNotFoundError
from quantlab.core.universe import Instrument

# Recorded live from https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=3
# on 2026-09-23. See ADR-0007.
_RECORDED_KLINES = [
    [
        1789948800000, "81178.01000000", "87395.67000000", "80850.22000000",
        "86620.00000000", "31963.17872000", 1790035199999, "2702559883.82269890",
        4461004, "16545.20736000", "1398317660.97195110", "0",
    ],
    [
        1790035200000, "86620.01000000", "86717.60000000", "85114.00000000",
        "86208.56000000", "21328.45813000", 1790121599999, "1834036114.86076060",
        3386775, "9485.28663000", "815537527.83543300", "0",
    ],
]

_BTC_USDT = Instrument(id="btc-usdt", symbol="BTCUSDT", asset_class="crypto", quote_asset="USDT")


def _mock_response(status_code: int, json_body: object) -> Mock:
    response = Mock()
    response.status_code = status_code
    response.json.return_value = json_body
    response.raise_for_status.side_effect = None if status_code < 400 else Exception("http error")
    return response


@patch("quantlab.core.data.binance.requests.get")
def test_fetch_returns_price_bars_sorted_chronologically(mock_get, tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    mock_get.return_value = _mock_response(200, _RECORDED_KLINES)

    bars = BinanceProvider().fetch(_BTC_USDT, date(2026, 9, 20), date(2026, 9, 22))

    assert [bar.ts for bar in bars] == sorted(bar.ts for bar in bars)
    assert bars[0].close == 86620.00
    assert bars[0].source == "binance"
    assert bars[0].adj_close is None


@patch("quantlab.core.data.binance.requests.get")
def test_fetch_uses_cache_on_second_call_for_same_range(mock_get, tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    mock_get.return_value = _mock_response(200, _RECORDED_KLINES)
    provider = BinanceProvider()

    first = provider.fetch(_BTC_USDT, date(2026, 9, 20), date(2026, 9, 22))
    second = provider.fetch(_BTC_USDT, date(2026, 9, 20), date(2026, 9, 22))

    assert mock_get.call_count == 1
    assert first == second


@patch("quantlab.core.data.binance.requests.get")
def test_unknown_symbol_raises_data_not_found_error(mock_get, tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    mock_get.return_value = _mock_response(400, {"code": -1121, "msg": "Invalid symbol."})

    with pytest.raises(DataNotFoundError):
        BinanceProvider().fetch(_BTC_USDT, date(2026, 9, 20), date(2026, 9, 22))
