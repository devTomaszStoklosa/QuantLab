"""Survivorship bias, measured (q5, REQ-523, REQ-524).

Four synthetic stocks rise 0.1% a day; one is delisted on day 50. Holding
every member equally, the run that knows the dead company realizes its
delisting return; the run on survivors only - today's constituents carried
back in time - never meets it. Both results are known in closed form, so the
bias is measured exactly, not estimated.
"""

import subprocess
from datetime import date, timedelta

import pytest
from typer.testing import CliRunner

from quantlab import cli
from quantlab.backtest.event_driven.engine import run as run_event_driven
from quantlab.backtest.event_driven.execution import NextBarExecution
from quantlab.core.data.events import Delisting, InstrumentEvents
from quantlab.core.data.provider import PriceBar
from quantlab.core.universe import Instrument, Membership, Universe
from quantlab.costs.zero import ZeroCostModel
from quantlab.research.definition import CostModelParameters, TimeSeriesMomentumParameters
from quantlab.strategy.members_only import MembersOnly

_DAY0 = date(2024, 1, 1)
_GROWTH = 0.001
_LOOKBACK = 5  # days of momentum, and of warm-up before the first position on _START
_START = _LOOKBACK
_DEATH = 50  # delisting date; its last trading day is 49
_LAST = 99
# Periods from _START to the dead stock's last trading day, and after its delisting.
_BEFORE = _DEATH - 1 - _START
_AFTER = _LAST - _DEATH


def _day(i: int) -> date:
    return _DAY0 + timedelta(days=i)


class _Stocks:
    """Four stocks compounding at _GROWTH a day; "ddd" trades until day 49."""

    def __init__(self, delisting_return: float | None) -> None:
        self.delisting_return = delisting_return

    def fetch(self, instrument: Instrument, start: date, end: date) -> list[PriceBar]:
        last = _DEATH - 1 if instrument.id == "ddd" else _LAST
        return [
            PriceBar(
                instrument_id=instrument.id,
                ts=_day(i),
                open=100.0 * (1.0 + _GROWTH) ** i,
                high=100.0 * (1.0 + _GROWTH) ** i,
                low=100.0 * (1.0 + _GROWTH) ** i,
                close=100.0 * (1.0 + _GROWTH) ** i,
                volume=1e9,
                source="synthetic",
            )
            for i in range(last + 1)
            if start <= _day(i) <= end
        ]

    def events(self, instrument: Instrument, start: date, end: date) -> InstrumentEvents:
        if instrument.id != "ddd" or not start <= _day(_DEATH) <= end:
            return InstrumentEvents()
        return InstrumentEvents(
            delisting=Delisting(
                instrument_id="ddd", date=_day(_DEATH), delisting_return=self.delisting_return
            )
        )


def _stock(instrument_id: str) -> Instrument:
    return Instrument(
        id=instrument_id, symbol=instrument_id.upper(), asset_class="equity", quote_asset="USD"
    )


_POINT_IN_TIME = Universe(
    name="pit-test",
    asof_date=_day(_LAST),
    source="synthetic",
    periods_per_year=252,
    market_proxy="aaa",
    instruments=[_stock(i) for i in ("aaa", "bbb", "ccc", "ddd")],
    memberships=[
        *(Membership(instrument_id=i, start=_DAY0, end=None) for i in ("aaa", "bbb", "ccc")),
        Membership(instrument_id="ddd", start=_DAY0, end=_day(_DEATH)),
    ],
)
_SURVIVORS = Universe(
    name="survivors-test",
    asof_date=_day(_LAST),
    source="synthetic",
    periods_per_year=252,
    instruments=[_stock(i) for i in ("aaa", "bbb", "ccc")],
)


def _parameters(missing_delisting_return: float | None = None) -> TimeSeriesMomentumParameters:
    # Every rising stock has positive momentum, so the portfolio holds every member.
    return TimeSeriesMomentumParameters(
        strategy="time_series_momentum",
        lookback_days=_LOOKBACK,
        universe="pit-test",
        cost_model=CostModelParameters(name="realistic", fee_bps=10, k=0.05, vol_window=5),
        missing_delisting_return=missing_delisting_return,
    )


def _final_equity(universe: Universe, provider: _Stocks, parameters=None) -> float:
    run = cli.run_study(
        provider,
        parameters or _parameters(),
        ZeroCostModel(),
        universe,
        _day(_START),
        _day(_LAST),
        0,
        "t",
    )
    return run.snapshots[-1].equity


@pytest.mark.parametrize("delisting_return", [-1.0, -0.3, 0.2])
def test_the_run_realizes_the_delisting_return_of_a_dead_member(delisting_return: float) -> None:
    equity = _final_equity(_POINT_IN_TIME, _Stocks(delisting_return))

    # Periods holding all four, the delisting period, periods holding the three left.
    expected = (1.0 + _GROWTH) ** (_BEFORE + _AFTER) * (1.0 + (3 * _GROWTH + delisting_return) / 4)
    assert equity == pytest.approx(expected, rel=1e-12)


def test_survivors_only_overstates_the_result_by_a_known_amount() -> None:
    with_the_dead = _final_equity(_POINT_IN_TIME, _Stocks(-1.0))
    survivors = _final_equity(_SURVIVORS, _Stocks(-1.0))

    assert survivors == pytest.approx((1.0 + _GROWTH) ** (_BEFORE + 1 + _AFTER), rel=1e-12)
    bias = survivors / with_the_dead - 1.0
    assert bias == pytest.approx((1.0 + _GROWTH) / (1.0 + (3 * _GROWTH - 1.0) / 4) - 1.0, rel=1e-9)
    assert bias > 0.3  # a quarter of the book lost, never seen by the survivors-only run


def test_an_unknown_delisting_return_takes_the_frozen_assumption() -> None:
    assumed = _final_equity(
        _POINT_IN_TIME, _Stocks(None), _parameters(missing_delisting_return=-0.3)
    )
    known = _final_equity(_POINT_IN_TIME, _Stocks(-0.3))

    assert assumed == known


def test_an_unknown_delisting_return_without_an_assumption_stops_the_run() -> None:
    with pytest.raises(ValueError, match="no missing_delisting_return"):
        _final_equity(_POINT_IN_TIME, _Stocks(None))


def test_both_engines_realize_the_delisting_return() -> None:
    comparison = cli.run_engine_comparison(
        _Stocks(-0.3), _parameters(), _POINT_IN_TIME, _day(_START), _day(_LAST), 0, "t", 1e6, 1.0
    )

    assert comparison.parity_difference < 1e-12


def test_run_reports_the_delistings_it_met(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "definitions"
    repo.mkdir()
    (repo / "dead_v1.yaml").write_text(
        """hypothesis: dead_v1
training_start: 2024-01-06
training_end: 2024-04-09
start: 2024-06-01
end: 2024-12-31
parameters:
  strategy: time_series_momentum
  lookback_days: 5
  universe: pit-test
  missing_delisting_return: -0.3
  cost_model: {name: realistic, fee_bps: 10, k: 0.05, vol_window: 5}
success_criterion: {description: test, min_sharpe: 0.0, max_p_value: 0.1}
""",
        encoding="utf-8",
    )
    for args in (["init", "-q"], ["add", "dead_v1.yaml"], ["commit", "-q", "-m", "freeze"]):
        subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
            cwd=repo,
            check=True,
            capture_output=True,
        )
    monkeypatch.setattr(cli, "_HOLDOUT_DIR", repo)
    monkeypatch.setitem(cli._PROVIDERS, "synthetic", lambda: _Stocks(None))
    monkeypatch.setattr(cli, "_PERMUTATIONS", 20)
    monkeypatch.setattr(Universe, "load", classmethod(lambda cls, name: _POINT_IN_TIME))

    result = CliRunner().invoke(cli.app, ["run", "dead_v1"])

    assert result.exit_code == 0, result.output
    assert (
        "Delistings in the data: 1, 1 at the definition's assumed return -30% (source gave none)"
        in result.output
    )
    # Every member-day has a price in this synthetic source (REQ-554).
    assert "Price coverage of the point-in-time universe: 100.0% of member-days" in result.output
    assert "Members without any price" not in result.output


def test_the_cash_out_is_not_a_trade_in_the_vectorized_engine() -> None:
    run = cli.run_study(
        _Stocks(-0.3),
        _parameters(),
        ZeroCostModel(),
        _POINT_IN_TIME,
        _day(_START),
        _day(_LAST),
        0,
        "t",
    )

    delisting_day = next(s for s in run.snapshots if s.ts == _day(_DEATH + 1))
    assert "ddd" not in delisting_day.traded
    assert "ddd" not in delisting_day.positions


def test_next_open_orders_never_fill_on_a_delisting_bar() -> None:
    result = run_event_driven(
        strategy=MembersOnly(_parameters().build_strategy(), _POINT_IN_TIME),
        cost_model=ZeroCostModel(),
        bars=cli._fetch_bars(
            _Stocks(-0.3), _POINT_IN_TIME, _parameters(), _day(_START), _day(_LAST)
        ),
        universe_name="pit-test",
        start=_day(_START),
        end=_day(_LAST),
        seed=0,
        git_sha="t",
        strategy_name="time_series_momentum",
        strategy_params={},
        execution=NextBarExecution("open"),
    )

    ddd = [record for record in result.orders if record.instrument_id == "ddd"]
    assert all(record.fill_ts != _day(_DEATH) for record in ddd if record.filled_quantity)
    assert all("ddd" not in s.positions for s in result.run.snapshots if s.ts > _day(_DEATH))
    # Held from next-open fills, it earned the delisting return on its last marked day.
    assert result.run.snapshots[-1].equity > 0


def test_a_market_proxy_outside_the_universe_is_rejected() -> None:
    with pytest.raises(ValueError, match="Market proxy zzz is not in universe"):
        Universe(
            name="x",
            asof_date=_DAY0,
            source="synthetic",
            periods_per_year=252,
            instruments=[_stock("aaa")],
            market_proxy="zzz",
        )
