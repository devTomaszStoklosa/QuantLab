"""The S&P 500 point-in-time universe, rebuilt from Wikipedia (q5, X7d, REQ-553).

Wikipedia's *List of S&P 500 companies* has today's constituents and a table of
changes (effective date, ticker added, ticker removed). Walking back from
today's set through the changes gives the index on every earlier date: undoing
a change puts the removed ticker back and takes the added one out. The page is
read at one pinned revision, the last before a fixed instant, so the universe
file is reproducible and cannot drift after the hypothesis is frozen.

Content from Wikipedia is licensed CC BY-SA 4.0; the universe file carries the
attribution and the revision it was built from.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from html.parser import HTMLParser
from typing import ClassVar

import requests
import yaml

from quantlab.core.universe import Instrument, Membership, Universe

PAGE_TITLE = "List of S&P 500 companies"
API_URL = "https://en.wikipedia.org/w/api.php"
# The revision read is the last one before this instant; fixed before xsmom_v1 is
# frozen (q5 X8), after the holdout's end (2025-12-31), so every change it needs is in.
PINNED_AS_OF = datetime(2026, 9, 24, tzinfo=UTC)
# Wikipedia's table of changes is considered complete from here on; memberships
# are not reconstructed before it (DATA-SOURCES).
DEFAULT_SINCE = date(2000, 1, 1)
UNIVERSE_NAME = "sp500"
MARKET_PROXY = Instrument(id="spy", symbol="SPY", asset_class="equity", quote_asset="USD")
PERIODS_PER_YEAR = 252
_USER_AGENT = "QuantLab/0.1 (research project; https://github.com/devTomaszStoklosa/QuantLab)"
_DATE_FORMATS = ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d", "%d %B %Y")


# --- reading the page ---------------------------------------------------------------


@dataclass
class _Cell:
    text: str
    header: bool
    rowspan: int
    colspan: int


@dataclass
class _Table:
    attrs: dict[str, str]
    rows: list[list[_Cell]] = field(default_factory=list)


class _Tables(HTMLParser):
    """Every table of a page as rows of cells, footnote markers left out."""

    _SKIPPED: ClassVar[set[str]] = {"sup", "style", "script"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[_Table] = []
        self._open: list[_Table] = []
        self._cell: _Cell | None = None
        self._skipping = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name: value or "" for name, value in attrs}
        if tag in self._SKIPPED:
            self._skipping += 1
        elif tag == "table":
            self._open.append(_Table(values))
        elif tag == "tr" and self._open:
            self._open[-1].rows.append([])
        elif tag in ("td", "th") and self._open and self._open[-1].rows:
            self._cell = _Cell(
                "",
                tag == "th",
                int(values.get("rowspan") or 1),
                int(values.get("colspan") or 1),
            )
            self._open[-1].rows[-1].append(self._cell)
        elif tag == "br" and self._cell is not None:
            self._cell.text += " "

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIPPED:
            self._skipping = max(0, self._skipping - 1)
        elif tag == "table" and self._open:
            self.tables.append(self._open.pop())
        elif tag in ("td", "th"):
            self._cell = None

    def handle_data(self, data: str) -> None:
        if self._cell is not None and not self._skipping:
            self._cell.text += data


def _grid(table: _Table) -> list[list[_Cell]]:
    """The table's rows with row- and column-spanning cells repeated where they reach."""
    grid: list[list[_Cell]] = []
    spanning: dict[int, tuple[int, _Cell]] = {}  # column -> (rows still covered, cell)
    for row in table.rows:
        cells = iter(row)
        line: list[_Cell] = []
        column = 0
        while True:
            if column in spanning:
                remaining, cell = spanning[column]
                line.append(cell)
                if remaining == 1:
                    del spanning[column]
                else:
                    spanning[column] = (remaining - 1, cell)
                column += 1
                continue
            cell = next(cells, None)
            if cell is None:
                if not any(c >= column for c in spanning):
                    break
                column += 1  # a gap before a spanning cell further right
                continue
            for _ in range(cell.colspan):
                line.append(cell)
                if cell.rowspan > 1:
                    spanning[column] = (cell.rowspan - 1, cell)
                column += 1
        grid.append(line)
    return grid


def _clean(text: str) -> str:
    return " ".join(text.split())


def _headers(grid: list[list[_Cell]]) -> tuple[list[str], list[list[_Cell]]]:
    """Column names (header rows joined) and the data rows below them."""
    header_rows = []
    while grid and grid[0] and all(cell.header for cell in grid[0]):
        header_rows.append(grid.pop(0))
    width = max((len(row) for row in header_rows), default=0)
    names = []
    for column in range(width):
        parts = []
        for row in header_rows:
            if column < len(row):
                text = _clean(row[column].text).lower()
                if text and text not in parts:
                    parts.append(text)
        names.append(" ".join(parts))
    return names, grid


def _column(names: list[str], *words: str) -> int:
    for index, name in enumerate(names):
        if all(word in name for word in words):
            return index
    raise ValueError(f"No column with {' and '.join(words)!r} among {names}")


def _find(tables: list[_Table], table_id: str, *words: str) -> _Table:
    """The table with this id, else the first whose header has all the words."""
    for table in tables:
        if table.attrs.get("id") == table_id:
            return table
    for table in tables:
        names, _ = _headers(_grid(table))
        if all(any(word in name for name in names) for word in words):
            return table
    raise ValueError(f"No table '{table_id}' on the page")


def normalize_ticker(text: str) -> str:
    """A ticker as Tiingo spells it: upper case, a class suffix after a hyphen (BRK-B)."""
    return _clean(text).upper().replace(".", "-").replace(" ", "")


def _parse_date(text: str) -> date | None:
    text = _clean(text)
    for pattern in _DATE_FORMATS:
        try:
            return datetime.strptime(text, pattern).replace(tzinfo=UTC).date()
        except ValueError:
            continue
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


@dataclass(frozen=True)
class Constituent:
    ticker: str
    date_added: date | None


@dataclass(frozen=True)
class Change:
    effective: date
    added: str | None
    removed: str | None


@dataclass
class Page:
    constituents: list[Constituent]
    changes: list[Change]
    unreadable_rows: list[str]  # rows of the table of changes without a date


def parse_page(html: str) -> Page:
    """Today's constituents and the table of changes from the page's HTML."""
    parser = _Tables()
    parser.feed(html)

    names, rows = _headers(_grid(_find(parser.tables, "constituents", "symbol", "date added")))
    symbol, added = _column(names, "symbol"), _column(names, "date added")
    constituents = [
        Constituent(normalize_ticker(row[symbol].text), _parse_date(row[added].text))
        for row in rows
        if len(row) > max(symbol, added) and _clean(row[symbol].text)
    ]

    names, rows = _headers(_grid(_find(parser.tables, "changes", "added", "removed")))
    effective = _column(names, "date")
    added_ticker, removed_ticker = (
        _column(names, "added", "ticker"),
        _column(names, "removed", "ticker"),
    )
    changes, unreadable = [], []
    for row in rows:
        if len(row) <= max(effective, added_ticker, removed_ticker):
            continue
        day = _parse_date(row[effective].text)
        if day is None:
            unreadable.append(" | ".join(text for cell in row if (text := _clean(cell.text))))
            continue
        changes.append(
            Change(
                effective=day,
                added=normalize_ticker(row[added_ticker].text) or None,
                removed=normalize_ticker(row[removed_ticker].text) or None,
            )
        )
    return Page(constituents, changes, unreadable)


# --- walking back through the changes ------------------------------------------------


@dataclass
class Reconstruction:
    memberships: list[Membership]
    # What the table of changes contradicts; every entry is a date and a ticker to check.
    added_but_not_in_index: list[tuple[date, str]]
    removed_but_still_in_index: list[tuple[date, str]]
    date_added_mismatches: list[tuple[str, date, date]]  # ticker, page's date, reconstructed
    several_periods: list[str]
    unreadable_rows: list[str]


def reconstruct(page: Page, renames: dict[str, str], since: date, as_of: date) -> Reconstruction:
    """Membership periods from `since` to today by undoing the changes, newest first.

    A change effective on D makes the added ticker a member from D and the removed
    one a member until D - 1. `renames` maps a ticker the table used at the time to
    the one the company trades under today. Changes before `since` are not undone,
    so everyone in the index then is a member from `since`.
    """

    def rename(ticker: str) -> str:
        return renames.get(ticker, ticker)

    members: dict[str, date | None] = {c.ticker: None for c in page.constituents}  # -> end
    periods: dict[str, list[Membership]] = defaultdict(list)
    added_but_not_in_index, removed_but_still_in_index = [], []

    changes = sorted(
        (c for c in page.changes if since < c.effective <= as_of),
        key=lambda change: change.effective,
        reverse=True,
    )
    for change in changes:
        if change.added is not None:
            added = rename(change.added)
            in_index = added in members
            end = members.get(added)
            if not in_index or (end is not None and end < change.effective):
                # Not in the index after its addition (a rename missing from the map, or
                # an unrecorded removal), or removed on the very day it was added.
                added_but_not_in_index.append((change.effective, added))
            else:
                del members[added]
                periods[added].append(
                    Membership(instrument_id=added, start=change.effective, end=end)
                )
        if change.removed is not None:
            removed = rename(change.removed)
            if removed in members:
                removed_but_still_in_index.append((change.effective, removed))
            else:
                members[removed] = change.effective - timedelta(days=1)
    for ticker, end in members.items():
        periods[ticker].append(Membership(instrument_id=ticker, start=since, end=end))

    memberships = []
    for ticker in sorted(periods):
        memberships.extend(sorted(periods[ticker], key=lambda span: span.start))
    # The page's "date added" is when a constituent's current period began.
    current_start = {span.instrument_id: span.start for span in memberships if span.end is None}
    date_added_mismatches = [
        (c.ticker, c.date_added, current_start[c.ticker])
        for c in page.constituents
        if c.date_added is not None
        and c.date_added > since
        and c.ticker in current_start
        and current_start[c.ticker] != c.date_added
    ]
    return Reconstruction(
        memberships=memberships,
        added_but_not_in_index=sorted(added_but_not_in_index),
        removed_but_still_in_index=sorted(removed_but_still_in_index),
        date_added_mismatches=sorted(date_added_mismatches),
        several_periods=sorted(t for t, spans in periods.items() if len(spans) > 1),
        unreadable_rows=page.unreadable_rows,
    )


def universe_from(reconstruction: Reconstruction, as_of: date) -> Universe:
    """The universe file's content: every ticker ever a member since `since`, and SPY."""
    tickers = sorted({span.instrument_id for span in reconstruction.memberships})
    return Universe(
        name=UNIVERSE_NAME,
        asof_date=as_of,
        source="tiingo",
        periods_per_year=PERIODS_PER_YEAR,
        market_proxy=MARKET_PROXY.id,
        instruments=[
            *(
                Instrument(
                    id=ticker.lower(), symbol=ticker, asset_class="equity", quote_asset="USD"
                )
                for ticker in tickers
            ),
            MARKET_PROXY,
        ],
        memberships=[
            span.model_copy(update={"instrument_id": span.instrument_id.lower()})
            for span in reconstruction.memberships
        ],
    )


# --- fetching and writing -------------------------------------------------------------


@dataclass(frozen=True)
class Revision:
    id: int
    timestamp: str
    html: str


def _get(params: dict) -> dict:
    response = requests.get(
        API_URL,
        params={**params, "format": "json", "formatversion": 2},
        headers={"User-Agent": _USER_AGENT},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def fetch_revision(as_of: datetime) -> Revision:
    """The page's last revision before `as_of`, with its rendered HTML (MediaWiki API)."""
    query = _get(
        {
            "action": "query",
            "prop": "revisions",
            "titles": PAGE_TITLE,
            "rvlimit": 1,
            "rvdir": "older",
            "rvstart": as_of.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "rvprop": "ids|timestamp",
        }
    )
    [revision] = query["query"]["pages"][0]["revisions"]
    parsed = _get({"action": "parse", "oldid": revision["revid"], "prop": "text"})
    return Revision(
        id=revision["revid"], timestamp=revision["timestamp"], html=parsed["parse"]["text"]
    )


def universe_yaml(universe: Universe, revision: Revision, since: date) -> str:
    """The universe file, with the attribution and provenance CC BY-SA 4.0 asks for."""
    header = (
        "# S&P 500 point-in-time universe (q5, REQ-553). Generated by\n"
        "#   uv run quantlab build-universe\n"
        "# Do not edit by hand: rebuild it, and fix tickers in sp500-renames.yaml.\n"
        "#\n"
        '# Membership derived from Wikipedia, "List of S&P 500 companies", revision\n'
        f"# {revision.id} of {revision.timestamp}:\n"
        f"# https://en.wikipedia.org/w/index.php?oldid={revision.id}\n"
        "# Wikipedia content is licensed CC BY-SA 4.0\n"
        "# (https://creativecommons.org/licenses/by-sa/4.0/); this file, as an\n"
        "# adaptation of it, is shared under the same license.\n"
        f"# Memberships before {since.isoformat()} are not reconstructed: the table of\n"
        "# changes is not reliable earlier. SPY is the market proxy, never a member.\n"
    )
    content = universe.model_dump(mode="json", exclude_defaults=False)
    return header + yaml.safe_dump(content, sort_keys=False, allow_unicode=True)


def load_renames(text: str) -> dict[str, str]:
    raw = yaml.safe_load(text) or {}
    return {
        normalize_ticker(old): normalize_ticker(new)
        for old, new in (raw.get("renames") or {}).items()
    }
