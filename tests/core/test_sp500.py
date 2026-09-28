from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import yaml
from typer.testing import CliRunner

from quantlab import cli
from quantlab.core import sp500
from quantlab.core.sp500 import Change, Constituent, Page, Rename, Renames, Revision
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
_FB = Renames((Rename("FB", "META"),))


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
        Change(date(2020, 6, 22), "NEW", "OLD", "New Co", "Old Co"),
        Change(date(2013, 12, 23), "FB", "GONE", "Facebook", "Gone Co"),
        Change(date(2013, 12, 23), None, "DEAD", "", "Dead Co"),  # the date spans two rows
        Change(date(2010, 2, 16), "BRK-B", "BNI", "Berkshire", "Burlington"),
        Change(date(1999, 3, 3), "XXX", "YYY", "Early", "Earlier"),
    ]
    assert page.unreadable_rows == ["n/a | ZZZ | Undated | ?"]


def test_a_page_without_the_table_names_the_tables_it_has() -> None:
    with pytest.raises(ValueError, match="No table 'changes' on the page; its tables: id "):
        sp500.parse_changes(_LIST_HTML)  # the list since the table moved away


def test_walking_back_through_the_changes_gives_every_membership() -> None:
    result = sp500.reconstruct(sp500.parse_pages(_LIST_HTML, _HISTORY_HTML), _FB, _SINCE, _AS_OF)

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
    assert result.started_at_date_added == []  # the list and the table agree
    assert result.date_added_mismatches == []
    assert result.several_periods == []


def test_a_rename_missing_from_the_map_is_reported_with_the_security() -> None:
    result = sp500.reconstruct(
        sp500.parse_pages(_LIST_HTML, _HISTORY_HTML), Renames(), _SINCE, _AS_OF
    )

    assert result.added_but_not_in_index == [(date(2013, 12, 23), "FB", "Facebook")]
    # The list's date added still starts META's period, not the table's start.
    assert ("META", date(2013, 12, 23), None) in _periods(result.memberships)
    assert result.started_at_date_added == [("META", date(2013, 12, 23), date(2000, 1, 1))]


def test_a_removal_of_a_ticker_still_in_the_index_is_reported() -> None:
    page = Page(
        [Constituent("AAA", None)], [Change(date(2015, 5, 1), None, "AAA", "", "Alpha")], []
    )

    result = sp500.reconstruct(page, Renames(), _SINCE, _AS_OF)

    assert result.removed_but_still_in_index == [(date(2015, 5, 1), "AAA", "Alpha")]
    assert _periods(result.memberships) == {("AAA", date(2000, 1, 1), None)}


def test_a_constituent_without_its_addition_in_the_table_starts_at_its_date_added() -> None:
    page = Page([Constituent("MMM", date(2008, 7, 18))], [], [])

    result = sp500.reconstruct(page, Renames(), _SINCE, _AS_OF)

    # Not a member before it joined the index, which would favour momentum.
    assert _periods(result.memberships) == {("MMM", date(2008, 7, 18), None)}
    assert result.started_at_date_added == [("MMM", date(2008, 7, 18), date(2000, 1, 1))]


def test_a_date_added_before_the_table_s_start_extends_the_present_period() -> None:
    # A share class change the table records as an addition, the first one missing.
    page = Page([Constituent("GGG", date(2006, 4, 3))], [Change(date(2014, 4, 3), "GGG", None)], [])

    result = sp500.reconstruct(page, Renames(), _SINCE, _AS_OF)

    assert _periods(result.memberships) == {("GGG", date(2006, 4, 3), None)}


def test_a_date_added_inside_an_earlier_period_leaves_the_table_s_start() -> None:
    page = Page(
        [Constituent("AAA", date(2011, 1, 3))],
        [Change(date(2018, 1, 2), "AAA", None), Change(date(2012, 7, 1), None, "AAA")],
        [],
    )

    result = sp500.reconstruct(page, Renames(), _SINCE, _AS_OF)

    assert ("AAA", date(2018, 1, 2), None) in _periods(result.memberships)
    assert result.date_added_mismatches == [("AAA", date(2011, 1, 3), date(2018, 1, 2))]
    assert result.started_at_date_added == []


def test_a_ticker_change_recorded_as_an_addition_and_a_removal_is_continuous() -> None:
    page = Page(
        [Constituent("WTW", date(2016, 1, 5))],
        [Change(date(2022, 1, 10), "WTW", "WLTW"), Change(date(2016, 1, 5), "WLTW", None)],
        [],
    )

    result = sp500.reconstruct(page, Renames((Rename("WLTW", "WTW"),)), _SINCE, _AS_OF)

    assert _periods(result.memberships) == {
        ("WTW", date(2016, 1, 5), date(2022, 1, 9)),
        ("WTW", date(2022, 1, 10), None),
    }
    # The list dates the start of the periods that touch: consistent, nothing to check.
    assert (result.date_added_mismatches, result.started_at_date_added) == ([], [])


def test_a_ticker_two_companies_swapped_on_one_day_keeps_the_first_company() -> None:
    # 21st Century Fox left on 2019-03-19 and Fox Corp took FOXA the same day.
    page = Page(
        [Constituent("FOXA", date(2019, 3, 19))],
        [Change(date(2019, 3, 19), "FOXA", "FOXA")],
        [],
    )

    result = sp500.reconstruct(page, Renames(), _SINCE, _AS_OF)

    assert _periods(result.memberships) == {
        ("FOXA", date(2000, 1, 1), date(2019, 3, 18)),
        ("FOXA", date(2019, 3, 19), None),
    }
    assert result.started_at_date_added == []
    assert result.several_periods == ["FOXA"]


def test_a_dated_rename_maps_a_reused_ticker_only_inside_its_window() -> None:
    # UA was Under Armour's class A (UAA today) until the class C shares took it in 2016.
    page = Page(
        [],
        [
            Change(date(2021, 6, 1), None, "UA"),
            Change(date(2021, 6, 1), None, "UAA"),
            Change(date(2016, 4, 8), "UA", None),
            Change(date(2014, 5, 1), "UA", None),
        ],
        [],
    )
    dated = Renames((Rename("UA", "UAA", end=date(2016, 4, 7)),))

    renamed = sp500.reconstruct(page, dated, _SINCE, _AS_OF)
    plain = sp500.reconstruct(page, Renames(), _SINCE, _AS_OF)

    assert _periods(renamed.memberships) == {
        ("UA", date(2016, 4, 8), date(2021, 5, 31)),
        ("UAA", date(2014, 5, 1), date(2021, 5, 31)),
    }
    assert renamed.added_but_not_in_index == []
    # Without the window, UAA looks like a member long before it joined the index.
    assert ("UAA", date(2000, 1, 1), date(2021, 5, 31)) in _periods(plain.memberships)
    assert plain.added_but_not_in_index == [(date(2014, 5, 1), "UA", "")]


def test_a_ticker_that_left_and_came_back_has_two_periods() -> None:
    page = Page(
        [Constituent("AAA", date(2018, 1, 2))],
        [Change(date(2018, 1, 2), "AAA", None), Change(date(2012, 7, 1), None, "AAA")],
        [],
    )

    result = sp500.reconstruct(page, Renames(), _SINCE, _AS_OF)

    assert _periods(result.memberships) == {
        ("AAA", date(2000, 1, 1), date(2012, 6, 30)),
        ("AAA", date(2018, 1, 2), None),
    }
    assert result.several_periods == ["AAA"]
    assert result.date_added_mismatches == []  # the page dates the current period


def test_the_universe_trades_through_tiingo_with_spy_as_a_benchmark() -> None:
    result = sp500.reconstruct(sp500.parse_pages(_LIST_HTML, _HISTORY_HTML), _FB, _SINCE, _AS_OF)

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
    result = sp500.reconstruct(sp500.parse_pages(_LIST_HTML, _HISTORY_HTML), _FB, _SINCE, _AS_OF)
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
    assert "Present period starts at the page's date added, not the table's (0): none" in (
        result.output
    )
    assert "Rows of the table of changes without a readable date (1): n/a | ZZZ" in result.output


def test_the_committed_renames_cover_plain_and_dated_ticker_changes() -> None:
    text = (Path(str(cli._UNIVERSES_DIR)) / "sp500-renames.yaml").read_text(encoding="utf-8")

    renames = sp500.load_renames(text)

    assert renames.ticker("FB", date(2013, 12, 23)) == "META"
    assert renames.ticker("PCLN", date(2009, 11, 3)) == "BKNG"
    assert renames.ticker("AAPL", date(2009, 11, 3)) == "AAPL"
    assert renames.ticker("UA", date(2014, 5, 1)) == "UAA"
    assert renames.ticker("UA", date(2016, 4, 8)) == "UA"
    assert renames.ticker("IR", date(2010, 11, 17)) == "TT"
    assert renames.ticker("IR", date(2020, 3, 2)) == "IR"
    assert renames.ticker("Q", date(2009, 1, 1)) == "Q"
    assert renames.ticker("Q", date(2017, 11, 15)) == "IQV"
    assert renames.ticker("Q", date(2025, 11, 3)) == "Q"  # Qnity Electronics


def test_three_companies_that_traded_as_q_keep_their_own_periods() -> None:
    # Qwest until 2011, QuintilesIMS in 2017 (IQV today), Qnity Electronics since 2025.
    text = (Path(str(cli._UNIVERSES_DIR)) / "sp500-renames.yaml").read_text(encoding="utf-8")
    page = Page(
        [Constituent("Q", date(2025, 11, 3)), Constituent("IQV", date(2017, 8, 29))],
        [
            Change(date(2025, 11, 3), "Q", None, "Qnity Electronics"),
            Change(date(2017, 11, 15), "IQV", "Q", "IQVIA", "Quintiles IMS"),
            Change(date(2017, 8, 29), "Q", None, "Quintiles IMS"),
            Change(date(2011, 4, 1), None, "Q", "", "Qwest Communications"),
        ],
        [],
    )

    result = sp500.reconstruct(page, sp500.load_renames(text), _SINCE, _AS_OF)

    assert _periods(result.memberships) == {
        ("Q", date(2000, 1, 1), date(2011, 3, 31)),
        ("Q", date(2025, 11, 3), None),
        ("IQV", date(2017, 8, 29), date(2017, 11, 14)),
        ("IQV", date(2017, 11, 15), None),
    }
    assert result.added_but_not_in_index == result.removed_but_still_in_index == []
    assert result.date_added_mismatches == result.started_at_date_added == []


def test_a_dated_rename_without_a_window_is_refused() -> None:
    with pytest.raises(ValueError, match="needs ticker, to and from or until"):
        sp500.load_renames("dated_renames:\n  - {ticker: UA, to: UAA}\n")


def test_a_stray_character_next_to_a_ticker_is_dropped() -> None:
    assert sp500.normalize_ticker("ALLE|") == "ALLE"
    assert sp500.normalize_ticker(" brk.b ") == "BRK-B"
