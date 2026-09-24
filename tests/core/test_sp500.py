from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import Mock, patch

import yaml
from typer.testing import CliRunner

from quantlab import cli
from quantlab.core import sp500
from quantlab.core.sp500 import Change, Constituent, Page, Revision
from quantlab.core.universe import Membership, Universe

# Shaped like the two tables of Wikipedia's "List of S&P 500 companies" (a date
# spanning two rows, headers over two rows, footnote markers, links), with made-up
# companies: the cloud environment cannot reach Wikipedia.
_HTML = """
<div class="mw-parser-output">
<table class="wikitable sortable" id="constituents"><tbody>
<tr><th>Symbol</th><th>Security</th><th>GICS Sector</th><th>GICS Sub-Industry</th>
<th>Headquarters Location</th><th>Date added</th><th>CIK</th><th>Founded</th></tr>
<tr><td><a class="external text" href="https://www.nyse.com/quote/XNYS:AAA">AAA</a></td>
<td><a href="/wiki/Alpha">Alpha</a></td><td>Industrials</td><td>Machinery</td>
<td>Town, Ohio</td><td>1990-01-01</td><td>0000000001</td><td>1901</td></tr>
<tr><td>BRK.B</td><td>Berkshire</td><td>Financials</td><td>Insurance</td>
<td>Omaha</td><td>2010-02-16</td><td>0000000002</td><td>1839</td></tr>
<tr><td>META</td><td>Meta</td><td>Communication</td><td>Media</td>
<td>Menlo Park</td><td>2013-12-23</td><td>0000000003</td><td>2004</td></tr>
<tr><td>NEW</td><td>New Co</td><td>Energy</td><td>Oil</td>
<td>Houston</td><td>2020-06-22<sup class="reference">[3]</sup></td><td>0000000004</td><td>2015</td></tr>
</tbody></table>
<table class="wikitable sortable" id="changes"><tbody>
<tr><th rowspan="2">Effective Date</th><th colspan="2">Added</th><th colspan="2">Removed</th>
<th rowspan="2">Reason</th></tr>
<tr><th>Ticker</th><th>Security</th><th>Ticker</th><th>Security</th></tr>
<tr><td>June 22, 2020</td><td>NEW</td><td>New Co</td><td>OLD</td><td>Old Co</td>
<td>Market capitalization change.<sup class="reference">[5]</sup></td></tr>
<tr><td rowspan="2">December 23, 2013</td><td>FB</td><td>Facebook</td><td>GONE</td>
<td>Gone Co</td><td>Acquired.</td></tr>
<tr><td></td><td></td><td>DEAD</td><td>Dead Co</td><td>Bankruptcy.</td></tr>
<tr><td>February 16, 2010</td><td>BRK.B</td><td>Berkshire</td><td>BNI</td>
<td>Burlington</td><td>Acquired by Berkshire.</td></tr>
<tr><td>March 3, 1999</td><td>XXX</td><td>Early</td><td>YYY</td><td>Earlier</td><td>Old.</td></tr>
<tr><td>n/a</td><td>ZZZ</td><td>Undated</td><td></td><td></td><td>?</td></tr>
</tbody></table>
</div>
"""
_SINCE, _AS_OF = date(2000, 1, 1), date(2026, 9, 24)


def _periods(memberships: list[Membership]) -> set[tuple[str, date, date | None]]:
    return {(m.instrument_id, m.start, m.end) for m in memberships}


def test_the_page_gives_constituents_and_changes_as_tiingo_spells_tickers() -> None:
    page = sp500.parse_page(_HTML)

    assert page.constituents == [
        Constituent("AAA", date(1990, 1, 1)),
        Constituent("BRK-B", date(2010, 2, 16)),
        Constituent("META", date(2013, 12, 23)),
        Constituent("NEW", date(2020, 6, 22)),  # the footnote marker is left out
    ]
    assert page.changes == [
        Change(date(2020, 6, 22), "NEW", "OLD"),
        Change(date(2013, 12, 23), "FB", "GONE"),
        Change(date(2013, 12, 23), None, "DEAD"),  # the date spans two rows
        Change(date(2010, 2, 16), "BRK-B", "BNI"),
        Change(date(1999, 3, 3), "XXX", "YYY"),
    ]
    assert page.unreadable_rows == ["n/a | ZZZ | Undated | ?"]


def test_walking_back_through_the_changes_gives_every_membership() -> None:
    result = sp500.reconstruct(sp500.parse_page(_HTML), {"FB": "META"}, _SINCE, _AS_OF)

    assert _periods(result.memberships) == {
        ("AAA", date(2000, 1, 1), None),  # a member before the table starts
        ("BNI", date(2000, 1, 1), date(2010, 2, 15)),  # until the day before its removal
        ("BRK-B", date(2010, 2, 16), None),
        ("DEAD", date(2000, 1, 1), date(2013, 12, 22)),
        ("GONE", date(2000, 1, 1), date(2013, 12, 22)),
        ("META", date(2013, 12, 23), None),  # added as FB
        ("NEW", date(2020, 6, 22), None),
        ("OLD", date(2000, 1, 1), date(2020, 6, 21)),
    }
    assert result.added_but_not_in_index == []
    assert result.removed_but_still_in_index == []
    assert result.date_added_mismatches == []
    assert result.several_periods == []


def test_a_rename_missing_from_the_map_is_reported_twice_over() -> None:
    result = sp500.reconstruct(sp500.parse_page(_HTML), {}, _SINCE, _AS_OF)

    assert result.added_but_not_in_index == [(date(2013, 12, 23), "FB")]
    # META then looks like a member since before the table, unlike the page's date added.
    assert ("META", date(2000, 1, 1), None) in _periods(result.memberships)
    assert result.date_added_mismatches == [("META", date(2013, 12, 23), date(2000, 1, 1))]


def test_a_removal_of_a_ticker_still_in_the_index_is_reported() -> None:
    page = Page([Constituent("AAA", None)], [Change(date(2015, 5, 1), None, "AAA")], [])

    result = sp500.reconstruct(page, {}, _SINCE, _AS_OF)

    assert result.removed_but_still_in_index == [(date(2015, 5, 1), "AAA")]
    assert _periods(result.memberships) == {("AAA", date(2000, 1, 1), None)}


def test_a_ticker_that_left_and_came_back_has_two_periods() -> None:
    page = Page(
        [Constituent("AAA", date(2018, 1, 2))],
        [Change(date(2018, 1, 2), "AAA", None), Change(date(2012, 7, 1), None, "AAA")],
        [],
    )

    result = sp500.reconstruct(page, {}, _SINCE, _AS_OF)

    assert _periods(result.memberships) == {
        ("AAA", date(2000, 1, 1), date(2012, 6, 30)),
        ("AAA", date(2018, 1, 2), None),
    }
    assert result.several_periods == ["AAA"]
    assert result.date_added_mismatches == []  # the page dates the current period


def test_the_universe_trades_through_tiingo_with_spy_as_a_benchmark() -> None:
    result = sp500.reconstruct(sp500.parse_page(_HTML), {"FB": "META"}, _SINCE, _AS_OF)

    universe = sp500.universe_from(result, _AS_OF)

    assert (universe.name, universe.source, universe.periods_per_year) == ("sp500", "tiingo", 252)
    assert universe.market_proxy == "spy"
    assert {i.id: i.symbol for i in universe.instruments}["brk-b"] == "BRK-B"
    assert universe.members(date(2013, 12, 22)) == {"aaa", "brk-b", "dead", "gone", "old"}
    assert universe.members(date(2013, 12, 23)) == {"aaa", "brk-b", "meta", "old"}
    assert "spy" not in universe.members(_AS_OF)


def test_the_file_carries_its_revision_and_attribution_and_loads_back() -> None:
    revision = Revision(id=123456789, timestamp="2026-09-23T10:00:00Z", html=_HTML)
    result = sp500.reconstruct(sp500.parse_page(_HTML), {"FB": "META"}, _SINCE, _AS_OF)
    universe = sp500.universe_from(result, _AS_OF)

    text = sp500.universe_yaml(universe, revision, _SINCE)

    assert "https://en.wikipedia.org/w/index.php?oldid=123456789" in text
    assert "CC BY-SA 4.0" in text
    assert Universe.model_validate(yaml.safe_load(text)) == universe


def test_the_revision_is_the_last_before_the_pinned_instant() -> None:
    query = {
        "query": {"pages": [{"revisions": [{"revid": 42, "timestamp": "2026-09-20T08:00:00Z"}]}]}
    }
    parsed = {"parse": {"text": _HTML}}
    get = Mock(
        side_effect=[
            Mock(status_code=200, json=Mock(return_value=query)),
            Mock(status_code=200, json=Mock(return_value=parsed)),
        ]
    )
    with patch("quantlab.core.sp500.requests.get", get):
        revision = sp500.fetch_revision(datetime(2026, 9, 24, tzinfo=UTC))

    assert (revision.id, revision.html) == (42, _HTML)
    first, second = (call.kwargs["params"] for call in get.call_args_list)
    assert first["titles"] == "List of S&P 500 companies"
    assert (first["rvstart"], first["rvdir"], first["rvlimit"]) == (
        "2026-09-24T00:00:00Z",
        "older",
        1,
    )
    assert (second["action"], second["oldid"]) == ("parse", 42)
    assert "QuantLab" in get.call_args.kwargs["headers"]["User-Agent"]


def test_build_universe_writes_the_file_and_lists_what_to_check(tmp_path, monkeypatch) -> None:
    renames = Path(str(cli._UNIVERSES_DIR)) / "sp500-renames.yaml"
    (tmp_path / "sp500-renames.yaml").write_text(renames.read_text(encoding="utf-8"))
    monkeypatch.setattr(cli, "_UNIVERSES_DIR", tmp_path)
    revision = Revision(id=7, timestamp="2026-09-23T10:00:00Z", html=_HTML)
    monkeypatch.setattr(sp500, "fetch_revision", lambda as_of: revision)

    result = CliRunner().invoke(cli.app, ["build-universe"])

    assert result.exit_code == 0, result.output
    universe = Universe.model_validate(
        yaml.safe_load((tmp_path / "sp500.yaml").read_text(encoding="utf-8"))
    )
    assert len(universe.instruments) == 9  # eight tickers and SPY
    assert "Wikipedia revision 7 (2026-09-23T10:00:00Z): 4 constituents, 5 changes" in result.output
    assert "Added but not in the index afterwards (0): none" in result.output
    assert "Rows of the table of changes without a readable date (1): n/a | ZZZ" in result.output


def test_the_committed_renames_map_the_facebook_ticker_to_meta() -> None:
    renames = (Path(str(cli._UNIVERSES_DIR)) / "sp500-renames.yaml").read_text(encoding="utf-8")

    assert sp500.load_renames(renames) == {"FB": "META"}
