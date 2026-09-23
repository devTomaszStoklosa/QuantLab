from datetime import date

import pytest
from pydantic import ValidationError

from quantlab.core.universe import Instrument, Universe


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
    duplicate = Instrument(id="btc-usdt", symbol="BTCUSDT", asset_class="crypto", quote_asset="USDT")

    with pytest.raises(ValidationError, match="Duplicate instrument id"):
        Universe(name="broken", asof_date=date(2026, 9, 23), instruments=[duplicate, duplicate])
