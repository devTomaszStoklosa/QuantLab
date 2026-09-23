import importlib.metadata
from datetime import date, timedelta

from typer.testing import CliRunner

from quantlab.cli import app, run_momentum_study
from quantlab.core.data.provider import PriceBar
from quantlab.core.universe import Instrument, Universe
from quantlab.costs.zero import ZeroCostModel

runner = CliRunner()

_FIRST_DAY = date(2026, 1, 1)
_CLOSES = {
    "a": [100.0, 101.0, 102.0, 103.0, 104.0],
    "b": [100.0, 99.0, 98.0, 97.0, 96.0],
}
_UNIVERSE = Universe(
    name="test-universe",
    asof_date=_FIRST_DAY,
    instruments=[
        Instrument(id="a", symbol="AUSDT", asset_class="crypto", quote_asset="USDT"),
        Instrument(id="b", symbol="BUSDT", asset_class="crypto", quote_asset="USDT"),
    ],
)


class _FixtureProvider:
    """DataProvider test double: serves fixed daily closes, records each request."""

    def __init__(self) -> None:
        self.requests: list[tuple[str, date, date]] = []

    def fetch(self, instrument: Instrument, start: date, end: date) -> list[PriceBar]:
        self.requests.append((instrument.id, start, end))
        bars = []
        for offset, close in enumerate(_CLOSES[instrument.id]):
            ts = _FIRST_DAY + timedelta(days=offset)
            if start <= ts <= end:
                bars.append(
                    PriceBar(
                        instrument_id=instrument.id,
                        ts=ts,
                        open=close,
                        high=close,
                        low=close,
                        close=close,
                        volume=1.0,
                        adj_close=None,
                        source="test",
                    )
                )
        return bars


def test_version_flag_prints_installed_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert importlib.metadata.version("quantlab") in result.stdout


def test_run_momentum_study_fetches_warm_up_history_and_nothing_after_end() -> None:
    provider = _FixtureProvider()
    start, end = date(2026, 1, 3), date(2026, 1, 5)

    run_momentum_study(
        provider=provider,
        cost_model=ZeroCostModel(),
        universe=_UNIVERSE,
        lookback_days=2,
        start=start,
        end=end,
        seed=0,
        git_sha="abc123",
    )

    assert provider.requests == [("a", date(2026, 1, 1), end), ("b", date(2026, 1, 1), end)]


def test_run_momentum_study_uses_warm_up_history_for_first_window_signal() -> None:
    start, end = date(2026, 1, 3), date(2026, 1, 5)

    result = run_momentum_study(
        provider=_FixtureProvider(),
        cost_model=ZeroCostModel(),
        universe=_UNIVERSE,
        lookback_days=2,
        start=start,
        end=end,
        seed=0,
        git_sha="abc123",
    )

    assert [snapshot.ts for snapshot in result.snapshots] == [
        date(2026, 1, 3),
        date(2026, 1, 4),
        date(2026, 1, 5),
    ]
    # Signal as-of the window's first day needs the two warm-up bars before it.
    assert result.snapshots[1].positions == {"a": 0.5, "b": -0.5}


def test_run_momentum_study_records_run_metadata() -> None:
    result = run_momentum_study(
        provider=_FixtureProvider(),
        cost_model=ZeroCostModel(),
        universe=_UNIVERSE,
        lookback_days=2,
        start=date(2026, 1, 3),
        end=date(2026, 1, 5),
        seed=7,
        git_sha="abc123",
    )

    assert result.universe_name == "test-universe"
    assert result.strategy_name == "time_series_momentum"
    assert result.strategy_params == {"lookback_days": 2}
    assert result.seed == 7
    assert result.git_sha == "abc123"
