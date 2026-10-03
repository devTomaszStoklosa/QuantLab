"""`quantlab audit-tickers` (#104): whose prices the source files under each former
S&P 500 member's ticker, from metadata and the training prices only.

The universe, the table of changes and the source are synthetic; the company names
are the ones step 0 of #104 found (2026-10-02).
"""

import csv
import subprocess
from datetime import date

from typer.testing import CliRunner

from quantlab import cli
from quantlab.core import sp500
from quantlab.core.data.identity import Listing
from quantlab.core.data.provider import PriceBar
from quantlab.core.sp500 import Revision
from quantlab.core.universe import Instrument, Membership, Universe

_TRAINING_END = date(2019, 12, 31)


def _stock(symbol: str) -> Instrument:
    return Instrument(id=symbol.lower(), symbol=symbol, asset_class="equity", quote_asset="USD")


_SP500 = Universe(
    name="sp500",
    asof_date=date(2026, 9, 24),
    source="tiingo",
    periods_per_year=252,
    market_proxy="spy",
    instruments=[_stock(s) for s in ("AAA", "EP", "GONE", "MIL", "NEWCO", "SVU", "SPY")],
    memberships=[
        Membership(instrument_id="aaa", start=date(2000, 1, 1), end=None),
        Membership(instrument_id="ep", start=date(2000, 1, 1), end=date(2012, 5, 24)),
        Membership(instrument_id="gone", start=date(2000, 1, 1), end=date(2008, 1, 1)),
        Membership(instrument_id="mil", start=date(2000, 1, 1), end=date(2010, 7, 14)),
        Membership(instrument_id="newco", start=date(2021, 1, 4), end=date(2023, 5, 31)),
        Membership(instrument_id="svu", start=date(2000, 1, 1), end=date(2012, 12, 19)),
    ],
    not_in_source=["mil"],
)


def _row(day: str, added: str, added_name: str, removed: str, removed_name: str) -> str:
    cells = (day, added, added_name, removed, removed_name, "", "")
    return "<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>"


_CHANGES_HTML = (
    '<table class="wikitable" id="changes"><tbody>'
    '<tr><th rowspan="2">Effective Date</th><th colspan="2">Added</th>'
    '<th colspan="2">Removed</th><th rowspan="2">Reason</th><th rowspan="2">Refs</th></tr>'
    "<tr><th>Ticker</th><th>Security</th><th>Ticker</th><th>Security</th></tr>"
    + _row("June 1, 2023", "", "", "NEWCO", "New Co")
    + _row("January 4, 2021", "NEWCO", "New Co", "", "")
    + _row("December 20, 2012", "", "", "SVU", "Supervalu")
    + _row("May 25, 2012", "", "", "EP", "El Paso Corp.")
    + _row("July 15, 2010", "", "", "MIL", "Millipore Corp.")
    + _row("January 2, 2008", "", "", "GONE", "Gone Co")
    + "</tbody></table>"
)

_LISTINGS = {
    "EP": Listing("Empire Petroleum Corporation", date(2011, 2, 23), date(2026, 10, 1)),
    "MIL": Listing("MFC Industrial Ltd", date(1996, 5, 8), date(2016, 2, 12), "DELISTED - MFC"),
    "NEWCO": Listing("New Co Inc", date(2015, 3, 2), date(2026, 10, 1)),
    "SVU": Listing("SUPERVALU INC.", date(1985, 7, 1), date(2018, 12, 14)),
}


class _Tiingo:
    """Listings by ticker (GONE unknown) and a 25 USD bar for every ticker, logged."""

    def __init__(self) -> None:
        self.listed: list[str] = []
        self.fetched: list[tuple[str, date, date]] = []

    def listing(self, instrument: Instrument) -> Listing | None:
        self.listed.append(instrument.symbol)
        return _LISTINGS.get(instrument.symbol)

    def fetch(self, instrument: Instrument, start: date, end: date) -> list[PriceBar]:
        self.fetched.append((instrument.symbol, start, end))
        return [
            PriceBar(
                instrument_id=instrument.id,
                ts=date(2007, 6, 1),
                open=25.0,
                high=25.0,
                low=25.0,
                close=25.0,
                volume=1_000.0,
                source="synthetic",
            )
        ]


def _audit(tmp_path, monkeypatch, hypothesis: str = "audit_v1"):
    repo = tmp_path / "definitions"
    repo.mkdir()
    (repo / "audit_v1.yaml").write_text(
        """hypothesis: audit_v1
training_start: 2005-01-01
training_end: 2019-12-31
start: 2020-01-01
end: 2025-12-31
parameters:
  strategy: cross_sectional_momentum
  formation_months: 12
  skip_months: 1
  quantile: 0.1
  long_short: true
  min_price: 5.0
  missing_delisting_return: 0.0
  universe: sp500
  cost_model: {name: realistic, fee_bps: 5, k: 0.05, vol_window: 21}
success_criterion: {description: test, min_sharpe: 0.0, max_p_value: 0.1}
""",
        encoding="utf-8",
    )
    for args in (["init", "-q"], ["add", "audit_v1.yaml"], ["commit", "-q", "-m", "freeze"]):
        subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
            cwd=repo,
            check=True,
            capture_output=True,
        )
    monkeypatch.setattr(cli, "_HOLDOUT_DIR", repo)
    monkeypatch.setattr(Universe, "load", classmethod(lambda cls, name: _SP500))
    tiingo = _Tiingo()
    monkeypatch.setitem(cli._LISTING_SOURCES, "tiingo", lambda: tiingo)
    monkeypatch.setitem(cli._PROVIDERS, "tiingo", lambda: tiingo)
    history = Revision(sp500.CHANGES_PAGE, 8, "2026-09-21T20:49:21Z", _CHANGES_HTML)
    monkeypatch.setattr(sp500, "fetch_revision", lambda title, as_of: history)
    result = CliRunner().invoke(cli.app, ["audit-tickers", hypothesis])
    return result, tiingo


def _table() -> list[dict[str, str]]:
    path = cli._RESULTS_DIR / "ticker-audit-audit_v1.csv"
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def test_the_audit_flags_another_company_s_prices_first(tmp_path, monkeypatch) -> None:
    result, _ = _audit(tmp_path, monkeypatch)

    assert result.exit_code == 0, result.output
    table = _table()
    assert [row["ticker"] for row in table] == ["GONE", "EP", "MIL", "NEWCO", "SVU"]
    assert [row["flags"] for row in table] == [
        "unknown to the source",
        "name differs; prices start after membership",
        "name differs",
        "",
        "",
    ]
    mil = table[2]
    assert (mil["index names"], mil["source name"]) == ("Millipore Corp.", "MFC Industrial Ltd")
    assert (mil["first member day"], mil["last member day"]) == ("2005-01-01", "2010-07-14")
    assert (mil["source first price"], mil["source last price"]) == ("1996-05-08", "2016-02-12")
    assert (mil["name similarity"], mil["not in source"]) == ("0.00", "yes")
    assert (mil["median close"], mil["median dollar volume"]) == ("25.00", "25000")
    assert mil["source description"] == "DELISTED - MFC"
    assert table[0]["source name"] == table[0]["name similarity"] == ""


def test_the_audit_reads_former_members_only_and_no_holdout_prices(tmp_path, monkeypatch) -> None:
    _, tiingo = _audit(tmp_path, monkeypatch)

    # AAA is a member today and SPY only the benchmark; MIL is checked again.
    assert sorted(tiingo.listed) == ["EP", "GONE", "MIL", "NEWCO", "SVU"]
    # The training run's prices, with its warm-up; NEWCO is a member in the holdout only.
    assert sorted(symbol for symbol, _, _ in tiingo.fetched) == ["EP", "GONE", "MIL", "SVU"]
    assert {end for _, _, end in tiingo.fetched} == {_TRAINING_END}
    assert all(start < date(2005, 1, 1) for _, start, _ in tiingo.fetched)


def test_the_audit_lists_the_flagged_tickers(tmp_path, monkeypatch) -> None:
    result, _ = _audit(tmp_path, monkeypatch)

    assert (
        "Ticker audit of audit_v1 (sp500 members 2005-01-01 .. 2025-12-31): "
        "5 former members, 3 flagged -> " in result.output
    )
    assert "  GONE: unknown to the source\n" in result.output
    assert "  EP: name differs; prices start after membership\n" in result.output
    assert "  MIL: name differs, already not in source\n" in result.output
    assert "SVU:" not in result.output


def test_the_audit_checks_the_s_and_p_500_universe_only() -> None:
    result = CliRunner().invoke(cli.app, ["audit-tickers", "momentum_v1"])

    assert result.exit_code == 1
    assert "audit-tickers checks the sp500 universe's former members" in result.output
