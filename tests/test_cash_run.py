"""Runs on a universe with cash: positions earn returns above it, in both engines (q12, C3)."""

from datetime import date, timedelta
from itertools import pairwise

import pytest

from quantlab import cli
from quantlab.core.data.events import CashDividend, InstrumentEvents
from quantlab.core.data.provider import PriceBar
from quantlab.core.universe import Instrument, Universe
from quantlab.costs.zero import ZeroCostModel
from quantlab.research.definition import CostModelParameters, TimeSeriesMomentumParameters

_FIRST, _DAYS = date(2021, 1, 1), 120
_CASH_RATE = 0.0002
# Daily returns: rising faster than cash, exactly like cash, and falling.
_RATES = {"up": 0.003, "flat": _CASH_RATE, "down": -0.001}
_CASH = Instrument(id="bil", symbol="BIL", asset_class="cash", quote_asset="USD")


class _Market:
    """Instruments at constant daily rates and a cash ETF paying its return as a monthly
    distribution, so the cash index needs the dividend adjustment to grow."""

    def __init__(self) -> None:
        self.requested: list[str] = []

    def fetch(self, instrument: Instrument, start: date, end: date) -> list[PriceBar]:
        self.requested.append(instrument.id)
        closes = (
            self._cash_closes()
            if instrument.id == "bil"
            else [100.0 * (1.0 + _RATES[instrument.id]) ** i for i in range(_DAYS)]
        )
        return [
            PriceBar(
                instrument_id=instrument.id,
                ts=_FIRST + timedelta(days=i),
                open=close,
                high=close,
                low=close,
                close=close,
                volume=1e9,
                source="test",
            )
            for i, close in enumerate(closes)
            if start <= _FIRST + timedelta(days=i) <= end
        ]

    @staticmethod
    def _cash_closes() -> list[float]:
        """A price that accrues interest and drops by it on each 30th day's ex-date."""
        closes, accrued = [], 1.0
        for i in range(_DAYS):
            if i and i % 30 == 0:
                accrued = 1.0
            closes.append(50.0 * accrued)
            accrued *= 1.0 + _CASH_RATE
        return closes

    def events(self, instrument: Instrument, start: date, end: date) -> InstrumentEvents:
        if instrument.id != "bil":
            return InstrumentEvents(actions=[], delisting=None)
        closes = self._cash_closes()
        return InstrumentEvents(
            actions=[
                CashDividend(
                    instrument_id="bil",
                    ex_date=_FIRST + timedelta(days=i),
                    amount=closes[i - 1] * (1.0 + _CASH_RATE) - closes[i],
                )
                for i in range(30, _DAYS, 30)
                if start <= _FIRST + timedelta(days=i) <= end
            ],
            delisting=None,
        )


def _universe(*ids: str, cash: Instrument | None = _CASH) -> Universe:
    return Universe(
        name="etfs",
        asof_date=_FIRST,
        source="synthetic",
        periods_per_year=365,
        instruments=[
            Instrument(id=i, symbol=i.upper(), asset_class="bond", quote_asset="USD") for i in ids
        ],
        cash=cash,
    )


_PARAMETERS = TimeSeriesMomentumParameters(
    strategy="time_series_momentum",
    lookback_days=5,
    universe="etfs",
    cost_model=CostModelParameters(name="realistic", fee_bps=3, k=0.05, vol_window=21),
)
_START, _END = _FIRST + timedelta(days=10), _FIRST + timedelta(days=_DAYS - 1)


def _period_returns(universe: Universe) -> list[float]:
    run = cli.run_study(_Market(), _PARAMETERS, ZeroCostModel(), universe, _START, _END, 0, "test")
    return [
        current.equity / previous.equity - 1.0
        for previous, current in pairwise(run.snapshots)
        if previous.positions
    ]


def test_a_long_position_earns_its_return_above_cash() -> None:
    returns = _period_returns(_universe("up"))

    assert len(returns) > 50
    assert returns == pytest.approx([1.003 / (1.0 + _CASH_RATE) - 1.0] * len(returns), rel=1e-9)


def test_a_short_position_earns_minus_the_excess() -> None:
    returns = _period_returns(_universe("down"))

    assert len(returns) > 50
    assert returns == pytest.approx([1.0 - 0.999 / (1.0 + _CASH_RATE)] * len(returns), rel=1e-9)


def test_an_instrument_growing_like_cash_earns_nothing_above_it() -> None:
    run = cli.run_study(
        _Market(), _PARAMETERS, ZeroCostModel(), _universe("flat"), _START, _END, 0, "test"
    )

    assert run.snapshots[-1].equity == pytest.approx(1.0, abs=1e-9)


def test_without_cash_returns_are_total_returns_and_cash_is_not_fetched() -> None:
    market = _Market()
    run = cli.run_study(
        market, _PARAMETERS, ZeroCostModel(), _universe("up", cash=None), _START, _END, 0, "t"
    )
    returns = [
        current.equity / previous.equity - 1.0
        for previous, current in pairwise(run.snapshots)
        if previous.positions
    ]

    assert returns == pytest.approx([0.003] * len(returns), rel=1e-9)
    assert "bil" not in market.requested


def test_both_engines_trade_the_prices_above_cash_alike() -> None:
    comparison = cli.run_engine_comparison(
        _Market(), _PARAMETERS, _universe("up", "flat", "down"), _START, _END, 0, "t", 1e6, 1.0
    )

    assert comparison.parity_difference < 1e-9


def test_a_run_says_its_returns_are_above_cash(capsys) -> None:
    cli._echo_cash(_universe("up"))
    cli._echo_cash(_universe("up", cash=None))

    line = (
        "Returns:        above cash (BIL); prices in the trade ledger are in units of cash, "
        "not quotes"
    )
    assert capsys.readouterr().out.splitlines() == [line]


def test_a_cash_instrument_the_source_lacks_stops_the_run() -> None:
    class _WithoutCash(_Market):
        def fetch(self, instrument: Instrument, start: date, end: date) -> list[PriceBar]:
            return [] if instrument.id == "bil" else super().fetch(instrument, start, end)

    with pytest.raises(cli.DataSourceUnavailableError, match="BIL, the cash of universe etfs"):
        cli.run_study(
            _WithoutCash(), _PARAMETERS, ZeroCostModel(), _universe("up"), _START, _END, 0, "t"
        )
