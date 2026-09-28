from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import yaml
from typer.testing import CliRunner

from quantlab import cli
from quantlab.core import sp500
from quantlab.core.sp500 import Change, Constituent, Page, Revision
from quantlab.core.universe import Membership, Universe

# Shaped like Wikipedia's two pages (a date spanning two rows, headers over two rows,
# footnote markers, links, the "Refs" column, a navbox), with made-up companies: the
# cloud environment cannot reach Wikipedia. Since 2026-08-11 the list has only the
# constituents, and the table of changes has a page of its own.
_LIST_HTML = """
<div class="mw-parser-output">
<table class="wikitable sortable mw-collapsible sticky-header" id="constituents"><tbody>
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
<h2>See also</h2>
<ul><li><a href="/wiki/Historical_components_of_the_S%26P_500">Historical components</a></li></ul>
<table class="nowraplinks mw-collapsible mw-collapsed navbox-inner"><tbody>
<tr><th colspan="2">vte S&amp;P 500 companies</th></tr>
<tr><th>Industrials</th><td>Alpha</td></tr>
</tbody></table>
</div>
"""
_HISTORY_HTML = """
<div class="mw-parser-output">
<table class="wikitable sortable" id="changes"><tbody><tr>
<th data-sort-type="date" rowspan="2">Effective Date
</th><th colspan="2">Added
</th><th colspan="2">Removed
</th><th rowspan="2">Reason
</th><th rowspan="2">Refs
</th></tr>
<tr><th>Ticker</th><th>Security</th><th>Ticker</th><th>Security
</th></tr>
<tr><td>June 22, 2020
</td><td>NEW
</td><td><a href="/wiki/New_Co" title="New Co">New Co</a>
</td><td>OLD
</td><td>Old Co
</td><td>Market capitalization change.
</td><td><sup class="reference"><a href="#cite_note-5"><span class="cite-bracket">&#91;</span>5
<span class="cite-bracket">&#93;</span></a></sup>
</td></tr>
<tr><td rowspan="2">December 23, 2013</td><td>FB</td><td>Facebook</td><td>GONE</td>
<td>Gone Co</td><td>Acquired.</td><td></td></tr>
<tr><td></td><td></td><td>DEAD</td><td>Dead Co</td><td>Bankruptcy.</td><td></td></tr>
<tr><td>February 16, 2010</td><td>BRK.B</td><td>Berkshire</td><td>BNI</td>
<td>Burlington</td><td>Acquired by Berkshire.</td><td></td></tr>
<tr><td>March 3, 1999</td><td>XXX</td><td>Early</td><td>YYY</td><td>Earlier</td><td>Old.</td>
<td></td></tr>
<tr><td>n/a</td><td>ZZZ</td><td>Undated</td><td></td><td></td><td>?</td><td></td></tr>
</tbody></table>
</div>
"""
_SINCE, _AS_OF = date(2000, 1, 1), date(2026, 9, 24)


def _periods(memberships: list[Membership]) -> set[tuple[str, date, date | None]]:
    return {(m.instrument_id, m.start, m.end) for m in memberships}


def test_the_pages_give_constituents_and_changes_as_tiingo_spells_tickers() -> None:
    page = sp500.parse_pages(_LIST_HTML, _HISTORY_HTML)

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


def test_a_page_without_the_table_names_the_tables_it_has() -> None:
    with pytest.raises(ValueError, match="No table 'changes' on the page; its tables: id "):
        sp500.parse_changes(_LIST_HTML)  # the list since the table moved away


def test_walking_back_through_the_changes_gives_every_membership() -> None:
    result = sp500.reconstruct(
        sp500.parse_pages(_LIST_HTML, _HISTORY_HTML), {"FB": "META"}, _SINCE, _AS_OF
    )

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
    result = sp500.reconstruct(sp500.parse_pages(_LIST_HTML, _HISTORY_HTML), {}, _SINCE, _AS_OF)

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
    result = sp500.reconstruct(
        sp500.parse_pages(_LIST_HTML, _HISTORY_HTML), {"FB": "META"}, _SINCE, _AS_OF
    )

    universe = sp500.universe_from(result, _AS_OF)

    assert (universe.name, universe.source, universe.periods_per_year) == ("sp500", "tiingo", 252)
    assert universe.market_proxy == "spy"
    assert {i.id: i.symbol for i in universe.instruments}["brk-b"] == "BRK-B"
    assert universe.members(date(2013, 12, 22)) == {"aaa", "brk-b", "dead", "gone", "old"}
    assert universe.members(date(2013, 12, 23)) == {"aaa", "brk-b", "meta", "old"}
    assert "spy" not in universe.members(_AS_OF)


def test_the_file_carries_its_revisions_and_attribution_and_loads_back() -> None:
    revisions = [
        Revision(sp500.CONSTITUENTS_PAGE, 123456789, "2026-09-20T22:18:13Z", _LIST_HTML),
        Revision(sp500.CHANGES_PAGE, 123456790, "2026-09-21T20:49:21Z", _HISTORY_HTML),
    ]
    result = sp500.reconstruct(
        sp500.parse_pages(_LIST_HTML, _HISTORY_HTML), {"FB": "META"}, _SINCE, _AS_OF
    )
    universe = sp500.universe_from(result, _AS_OF)

    text = sp500.universe_yaml(universe, revisions, _SINCE)

    assert '"List of S&P 500 companies", revision 123456789 of 2026-09-20T22:18:13Z' in text
    assert "https://en.wikipedia.org/w/index.php?oldid=123456789" in text
    assert '"Historical components of the S&P 500", revision 123456790' in text
    assert "https://en.wikipedia.org/w/index.php?oldid=123456790" in text
    assert "CC BY-SA 4.0" in text
    assert Universe.model_validate(yaml.safe_load(text)) == universe


def test_the_revision_is_the_last_before_the_pinned_instant() -> None:
    query = {
        "query": {"pages": [{"revisions": [{"revid": 42, "timestamp": "2026-09-20T08:00:00Z"}]}]}
    }
    parsed = {"parse": {"text": _HISTORY_HTML}}
    get = Mock(
        side_effect=[
            Mock(status_code=200, json=Mock(return_value=query)),
            Mock(status_code=200, json=Mock(return_value=parsed)),
        ]
    )
    with patch("quantlab.core.sp500.requests.get", get):
        revision = sp500.fetch_revision(sp500.CHANGES_PAGE, datetime(2026, 9, 24, tzinfo=UTC))

    assert revision == Revision(sp500.CHANGES_PAGE, 42, "2026-09-20T08:00:00Z", _HISTORY_HTML)
    first, second = (call.kwargs["params"] for call in get.call_args_list)
    assert first["titles"] == "Historical components of the S&P 500"
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
    revisions = {
        sp500.CONSTITUENTS_PAGE: Revision(
            sp500.CONSTITUENTS_PAGE, 7, "2026-09-20T22:18:13Z", _LIST_HTML
        ),
        sp500.CHANGES_PAGE: Revision(sp500.CHANGES_PAGE, 8, "2026-09-21T20:49:21Z", _HISTORY_HTML),
    }
    monkeypatch.setattr(sp500, "fetch_revision", lambda title, as_of: revisions[title])

    result = CliRunner().invoke(cli.app, ["build-universe"])

    assert result.exit_code == 0, result.output
    universe = Universe.model_validate(
        yaml.safe_load((tmp_path / "sp500.yaml").read_text(encoding="utf-8"))
    )
    assert len(universe.instruments) == 9  # eight tickers and SPY
    assert (
        'Wikipedia "List of S&P 500 companies", revision 7 (2026-09-20T22:18:13Z): 4 constituents'
        in result.output
    )
    assert (
        'Wikipedia "Historical components of the S&P 500", revision 8 (2026-09-21T20:49:21Z): '
        "5 changes" in result.output
    )
    assert "oldid=7" in (tmp_path / "sp500.yaml").read_text(encoding="utf-8")
    assert "Added but not in the index afterwards (0): none" in result.output
    assert "Rows of the table of changes without a readable date (1): n/a | ZZZ" in result.output


def test_the_committed_renames_map_the_facebook_ticker_to_meta() -> None:
    renames = (Path(str(cli._UNIVERSES_DIR)) / "sp500-renames.yaml").read_text(encoding="utf-8")

    assert sp500.load_renames(renames) == {"FB": "META"}
