"""HTML tear-sheet of one completed training run (REQ-070), holdout kept apart (REQ-042).

Every number on the page is computed before rendering - metrics, drawdowns,
validation and regime results arrive as inputs - and this module only formats
and draws them. Charts are inline SVG, so the file is self-contained: no
JavaScript, no plotting dependency, opens offline. The page text is Polish,
like the project's other reports; colours follow the presentation design
system's tokens (presentation/design-system/project/tokens.json).
"""

import html
import math
from datetime import date, datetime
from typing import Self

from pydantic import BaseModel, model_validator

from quantlab.backtest.vectorized.engine import BacktestRun
from quantlab.reporting.cost_comparison import RunMetrics
from quantlab.reporting.metrics import drawdown_series
from quantlab.research.hypothesis import concluded_status
from quantlab.risk.conditional import RegimeMetrics
from quantlab.risk.regime import VOLATILITY_REGIMES
from quantlab.validation.base import ValidationResult
from quantlab.validation.holdout import HoldoutRecord, holdout_passed

DISCLAIMER = (
    "Symulacja historyczna na danych z przeszłości, wykonana w celach badawczych i "
    "edukacyjnych. Nic w tym raporcie nie jest rekomendacją inwestycyjną."
)

_MINUS = "\u2212"
_MISSING = "\u2014"
_THIN_SPACE = "\u2009"  # thousands separator, 10 000
_OUTCOME = {True: "passed", False: "failed", None: "inconclusive"}

_CHART_WIDTH = 960
_MARGIN_LEFT = 64
_MARGIN_RIGHT = 16
_MARGIN_TOP = 12
_MARGIN_BOTTOM = 28


class TearSheet(BaseModel):
    """Everything one tear-sheet shows, computed before rendering.

    `run` is the training run behind the charts and the regime, walk-forward
    and permutation results; `cost_comparison` holds the same inputs under each
    cost model, `run`'s own included. `holdout` is the record of the one-time
    holdout opening, or None while the holdout is still sealed.
    """

    hypothesis: str
    run: BacktestRun
    cost_comparison: list[RunMetrics]
    regimes: dict[str, RegimeMetrics]
    regime_method: str
    walk_forward: ValidationResult
    permutation: ValidationResult
    holdout: HoldoutRecord | None
    generated_at: datetime

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.run.cost_model_name not in {m.cost_model_name for m in self.cost_comparison}:
            raise ValueError(f"No metrics for the run's cost model {self.run.cost_model_name}")
        if self.walk_forward.method != "walk_forward":
            raise ValueError(f"Expected a walk-forward result, got {self.walk_forward.method}")
        if self.permutation.method != "permutation":
            raise ValueError(f"Expected a permutation result, got {self.permutation.method}")
        holdout = self.holdout
        if holdout is not None:
            if holdout.hypothesis != self.hypothesis:
                raise ValueError(
                    f"Holdout record is for {holdout.hypothesis}, not {self.hypothesis}"
                )
            # REQ-042: a training result that includes holdout days would merge the two.
            if self.run.start <= holdout.end and holdout.start <= self.run.end:
                raise ValueError(
                    f"Run {self.run.start}..{self.run.end} overlaps the holdout "
                    f"{holdout.start}..{holdout.end}"
                )
        return self


def _e(value: object) -> str:
    return html.escape(str(value))


def _number(value: float | None, pattern: str) -> str:
    if value is None or math.isnan(value):
        return _MISSING
    return format(value, pattern).replace("-", _MINUS)


def _pct(value: float | None) -> str:
    return _number(value, ".1%")


def _ratio(value: float | None) -> str:
    return _number(value, ".2f")


def _p_value(value: float | None) -> str:
    return _number(value, ".3f")


def _nice_ticks(low: float, high: float, count: int = 4) -> list[float]:
    """Round values from at or below `low` to at or above `high`, about `count` steps apart."""
    if high <= low:
        pad = abs(low) * 0.05 or 0.01
        low, high = low - pad, high + pad
    raw_step = (high - low) / count
    magnitude = 10 ** math.floor(math.log10(raw_step))
    step = next(m * magnitude for m in (1, 2, 5, 10) if m * magnitude >= raw_step)
    first = math.floor(low / step + 1e-9)
    last = math.ceil(high / step - 1e-9)
    return [k * step for k in range(first, last + 1)]


def _tick_label(value: float, step: float, percent: bool) -> str:
    """As many decimals as the step needs: steps are 1, 2 or 5 times a power of ten."""
    scale = 100 if percent else 1
    decimals = max(0, -math.floor(math.log10(step * scale) + 1e-9))
    return _number(value * scale, f".{decimals}f") + ("%" if percent else "")


def _x_ticks(dates: list[date]) -> list[tuple[date, str]]:
    first, last = dates[0], dates[-1]
    years = [
        date(year, 1, 1)
        for year in range(first.year, last.year + 1)
        if first <= date(year, 1, 1) <= last
    ]
    if len(years) >= 2:
        return [(day, str(day.year)) for day in years]
    return [(first, first.isoformat()), (last, last.isoformat())]


def _chart(
    chart_id: str,
    title: str,
    dates: list[date],
    values: list[float],
    ticks: list[float],
    percent: bool,
    height: int,
    area: bool,
) -> str:
    """Line (or area down to zero) over time, horizontal gridlines only."""
    left, right = _MARGIN_LEFT, _CHART_WIDTH - _MARGIN_RIGHT
    top, bottom = _MARGIN_TOP, height - _MARGIN_BOTTOM
    low, high = ticks[0], ticks[-1]
    step = ticks[1] - ticks[0]
    first, span = dates[0], max((dates[-1] - dates[0]).days, 1)

    def x(day: date) -> float:
        return left + (day - first).days / span * (right - left)

    def y(value: float) -> float:
        return bottom - (value - low) / (high - low) * (bottom - top)

    parts = [
        (
            f'<svg id="{chart_id}" class="chart" viewBox="0 0 {_CHART_WIDTH} {height}" '
            f'role="img" aria-labelledby="{chart_id}-title">'
        ),
        f'<title id="{chart_id}-title">{_e(title)}</title>',
    ]
    for tick in ticks:
        parts.append(
            f'<line class="grid" x1="{left}" y1="{y(tick):.1f}" x2="{right}" y2="{y(tick):.1f}"/>'
        )
        parts.append(
            f'<text class="axis" x="{left - 8}" y="{y(tick) + 4:.1f}" '
            f'text-anchor="end">{_tick_label(tick, step, percent)}</text>'
        )
    for day, label in _x_ticks(dates):
        parts.append(
            f'<text class="axis" x="{x(day):.1f}" y="{height - 8}" '
            f'text-anchor="middle">{_e(label)}</text>'
        )
    points = " ".join(
        f"{x(day):.1f},{y(value):.1f}" for day, value in zip(dates, values, strict=True)
    )
    if area:
        baseline = y(0.0)
        parts.append(
            f'<path class="area" d="M{x(dates[0]):.1f},{baseline:.1f} L{points} '
            f'L{x(dates[-1]):.1f},{baseline:.1f} Z"/>'
        )
    parts.append(f'<polyline class="{"area-edge" if area else "line"}" points="{points}"/>')
    parts.append("</svg>")
    return "\n".join(parts)


def _table(headers: list[str], rows: list[list[str]], numeric_from: int = 1) -> str:
    """Columns from `numeric_from` on are right-aligned numbers. Cells are pre-escaped."""

    def cell(tag: str, index: int, content: str) -> str:
        css = ' class="num"' if index >= numeric_from else ""
        return f"<{tag}{css}>{content}</{tag}>"

    head = "".join(cell("th", i, header) for i, header in enumerate(headers))
    body = "".join(
        "<tr>" + "".join(cell("td", i, content) for i, content in enumerate(row)) + "</tr>"
        for row in rows
    )
    return (
        f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead>'
        f"<tbody>{body}</tbody></table></div>"
    )


def _header(sheet: TearSheet) -> str:
    run = sheet.run
    params = ", ".join(f"{key}={value}" for key, value in run.strategy_params.items())
    facts = [
        ("Strategia", f"<code>{_e(run.strategy_name)}</code> ({_e(params)})"),
        ("Uniwersum", f"<code>{_e(run.universe_name)}</code>"),
        ("Okres treningowy", f"{run.start.isoformat()} → {run.end.isoformat()}"),
        ("Model kosztów", f"<code>{_e(run.cost_model_name)}</code>"),
        ("Commit", f"<code>{_e(run.git_sha[:7])}</code>"),
        ("Seed", str(run.seed)),
        ("Przebieg", f"<code>{_e(run.id)}</code>"),
        ("Wygenerowano", f"{sheet.generated_at:%Y-%m-%d %H:%M} UTC"),
    ]
    items = "".join(f"<dt>{label}</dt><dd>{value}</dd>" for label, value in facts)
    return (
        '<header><p class="eyebrow">Tear-sheet</p>'
        f'<h1>{_e(sheet.hypothesis)}</h1><dl class="facts">{items}</dl></header>'
    )


def _verdict(sheet: TearSheet) -> str:
    """The hypothesis status the pre-registered gates give, or why there is none yet."""
    opening = '<section id="verdict"><p class="eyebrow">Werdykt hipotezy</p>'
    walk_forward = _OUTCOME[sheet.walk_forward.passed]
    if sheet.holdout is None:
        return (
            f"{opening}<p>Brak werdyktu: holdout nie został jeszcze otwarty. "
            f"Walk-forward: <strong>{walk_forward}</strong>.</p></section>"
        )
    status = concluded_status(sheet.walk_forward.passed, holdout_passed(sheet.holdout.verdict))
    return (
        f'{opening}<p class="verdict-word"><strong class="verdict verdict-{status}">'
        f"{status}</strong></p>"
        f"<p>Walk-forward: <strong>{walk_forward}</strong>; holdout: "
        f"<strong>{_e(sheet.holdout.verdict)}</strong>. Status wynika z reguł ustalonych przed "
        "wynikiem: <code>confirmed</code> wymaga zaliczenia obu bramek, niezaliczona bramka "
        "daje <code>rejected</code>, pozostałe przypadki \u2014 <code>inconclusive</code>.</p>"
        "</section>"
    )


def _metrics_table(sheet: TearSheet) -> str:
    rows = [
        ("CAGR", lambda m: _pct(m.cagr)),
        ("Sharpe", lambda m: _ratio(m.sharpe)),
        ("Sortino", lambda m: _ratio(m.sortino)),
        ("Calmar", lambda m: _ratio(m.calmar)),
        ("Max drawdown", lambda m: _pct(m.max_drawdown)),
    ]
    headers = ["Metryka"] + [
        f"<code>{_e(m.cost_model_name)}</code>"
        + (" *" if m.cost_model_name == sheet.run.cost_model_name else "")
        for m in sheet.cost_comparison
    ]
    return _table(
        headers, [[label, *(fmt(m) for m in sheet.cost_comparison)] for label, fmt in rows]
    )


def _regime_order(labels: list[str]) -> list[str]:
    known = [label for label in VOLATILITY_REGIMES if label in labels]
    return known + sorted(label for label in labels if label not in VOLATILITY_REGIMES)


def _regime_table(regimes: dict[str, RegimeMetrics]) -> str:
    if not regimes:
        return '<p class="muted">Brak dni z pozycją — nie ma czego dzielić na reżimy.</p>'
    total_days = sum(regime.days for regime in regimes.values())
    rows = [
        [
            f"<code>{_e(label)}</code>",
            str(regimes[label].days),
            _pct(regimes[label].days / total_days),
            _pct(regimes[label].cagr),
            _ratio(regimes[label].sharpe),
            _ratio(regimes[label].sortino),
        ]
        for label in _regime_order(list(regimes))
    ]
    return _table(["Reżim", "Dni", "Udział", "CAGR", "Sharpe", "Sortino"], rows)


def _walk_forward(result: ValidationResult) -> str:
    detail = result.detail

    def row(label: str, window: dict) -> list[str]:
        return [
            label,
            _pct(window["cagr"]),
            _ratio(window["sharpe"]),
            _pct(window["max_drawdown"]),
        ]

    rows = [
        row(f"{window['start']} → {window['end']}{' *' if window['partial'] else ''}", window)
        for window in detail["windows"]
    ]
    if detail["aggregate"] is not None:
        rows.append(row("Łącznie", detail["aggregate"]))
    table = (
        _table(["Okno", "CAGR", "Sharpe", "Max drawdown"], rows)
        if rows
        else '<p class="muted">Brak okien z pozycją.</p>'
    )
    counts = (
        f" ({detail['positive_windows']} z {detail['windows_with_sharpe']} okien ze Sharpe > 0)"
        if "positive_windows" in detail
        else ""
    )
    return (
        f"{table}"
        '<p class="note">* niepełny rok kalendarzowy</p>'
        f"<p>Reguła (zarejestrowana przed wynikiem): <q>{_e(detail['rule'])}</q></p>"
        f"<p>Wynik: <strong>{_OUTCOME[result.passed]}</strong>{counts}</p>"
    )


def _permutation(result: ValidationResult) -> str:
    detail = result.detail
    shuffles = f"{detail['n_permutations']:,}".replace(",", _THIN_SPACE)
    header = (
        f"<p>Statystyka: <q>{_e(detail['statistic'])}</q>; {shuffles} przetasowań zwrotów "
        f"względem trzymanych pozycji, seed {detail['seed']}, "
        f"α = {_p_value(detail['alpha'])}.</p>"
    )
    if "reason" in detail:
        body = f"<p>Wynik: <strong>inconclusive</strong> ({_e(detail['reason'])})</p>"
    else:
        body = (
            f"<p>Sharpe brutto {_ratio(detail['actual'])} wobec średniej przetasowań "
            f"{_ratio(detail['null_mean'])} (odch. std. {_ratio(detail['null_std'])}); "
            f"wyższy niż {_pct(detail['percentile'])} przetasowań.</p>"
            f"<p>Wynik: p = {_p_value(detail['p_value'])}, "
            f"<strong>{_OUTCOME[result.passed]}</strong></p>"
        )
    warning = (
        f'<p class="callout">Niska wiarygodność: tylko {detail["active_days"]} dni z pozycją.</p>'
        if detail["low_confidence"]
        else ""
    )
    return header + body + warning


def _training_section(sheet: TearSheet) -> str:
    run = sheet.run
    dates = [snapshot.ts for snapshot in run.snapshots]
    equity = [snapshot.equity for snapshot in run.snapshots]
    drawdowns = drawdown_series(equity)
    cost_model = _e(run.cost_model_name)
    equity_chart = _chart(
        "equity-chart",
        f"Krzywa kapitału, {run.cost_model_name}",
        dates,
        equity,
        _nice_ticks(min(equity), max(equity)),
        percent=False,
        height=300,
        area=False,
    )
    drawdown_chart = _chart(
        "drawdown-chart",
        f"Obsunięcie kapitału, {run.cost_model_name}",
        dates,
        drawdowns,
        _nice_ticks(min(min(drawdowns), -0.01), 0.0),
        percent=True,
        height=160,
        area=True,
    )
    return (
        '<section id="training" class="partition-training">'
        '<p class="tag tag-training">trening</p>'
        f"<h2>Okres treningowy {run.start.isoformat()} → {run.end.isoformat()}</h2>"
        '<p class="muted">Wszystkie liczby w tej sekcji pochodzą z okresu treningowego. '
        "Holdout jest oceniany osobno, w sekcji niżej, i nie jest tu wliczony.</p>"
        '<h3 id="metrics">Metryki</h3>'
        '<p class="muted">Te same sygnały i dane pod każdym modelem kosztów; '
        "<code>zero-cost</code> to wynik brutto. * model kosztów wykresów i tabel niżej.</p>"
        f"{_metrics_table(sheet)}"
        f'<h3>Krzywa kapitału</h3><p class="muted">Wartość portfela startującego od 1.00, '
        f"<code>{cost_model}</code>.</p>{equity_chart}"
        f'<h3>Obsunięcie kapitału</h3><p class="muted">Spadek od poprzedniego szczytu, '
        f"<code>{cost_model}</code>.</p>{drawdown_chart}"
        '<h3 id="regimes">Wyniki warunkowe per reżim</h3>'
        f'<p class="muted">{_e(sheet.regime_method)} Zwroty netto, <code>{cost_model}</code>. '
        "Opisowe: nie są częścią żadnej reguły zaliczenia ani werdyktu hipotezy.</p>"
        f"{_regime_table(sheet.regimes)}"
        '<h3 id="walk-forward">Walk-forward</h3>'
        f'<p class="muted">Okna roczne, <code>{cost_model}</code>.</p>'
        f"{_walk_forward(sheet.walk_forward)}"
        '<h3 id="permutation">Test permutacyjny</h3>'
        f"{_permutation(sheet.permutation)}"
        "</section>"
    )


def _holdout_section(holdout: HoldoutRecord | None) -> str:
    opening = (
        '<section id="holdout" class="partition-holdout"><p class="tag tag-holdout">holdout</p>'
    )
    if holdout is None:
        return (
            f"{opening}<h2>Holdout</h2>"
            "<p>Holdout jest zamrożony i nie został jeszcze otwarty — w tym raporcie nie "
            "ma z niego żadnych liczb.</p></section>"
        )
    rows = [
        ["CAGR", _pct(holdout.cagr)],
        ["Sharpe", _ratio(holdout.sharpe)],
        ["Sortino", _ratio(holdout.sortino)],
        ["Calmar", _ratio(holdout.calmar)],
        ["Max drawdown", _pct(holdout.max_drawdown)],
        ["p-value (test permutacyjny)", _p_value(holdout.p_value)],
    ]
    facts = [
        ("Zamrożony w commicie", f"<code>{_e(holdout.frozen_at_commit[:7])}</code>"),
        (
            "Otwarty",
            (
                f"{holdout.opened_at:%Y-%m-%d %H:%M} UTC, commit "
                f"<code>{_e(holdout.opened_at_commit[:7])}</code>"
            ),
        ),
        ("Model kosztów", f"<code>{_e(holdout.cost_model_name)}</code>"),
    ]
    items = "".join(f"<dt>{label}</dt><dd>{value}</dd>" for label, value in facts)
    return (
        f"{opening}<h2>Holdout {holdout.start.isoformat()} → {holdout.end.isoformat()}</h2>"
        '<p class="muted">Wynik jednorazowego otwarcia zamrożonego holdoutu, odczytany z '
        "zapisanego rekordu. Nie jest łączony z okresem treningowym.</p>"
        f'<dl class="facts">{items}</dl>'
        f"{_table(['Metryka', 'Holdout'], rows)}"
        f"<p>Kryterium (zamrożone przed otwarciem): <q>{_e(holdout.criterion)}</q></p>"
        f'<p>Werdykt holdoutu: <strong class="verdict verdict-{_e(holdout.verdict)}">'
        f"{_e(holdout.verdict)}</strong></p></section>"
    )


_STYLE = """
:root {
  color-scheme: light dark;
  --ground: #f4f3ef; --surface: #ffffff; --surface-sunken: #ebe9e3; --line: #dddad2;
  --ink: #16181b; --ink-muted: #565a61; --chart-grid: #ebe9e3;
  --loss: #b8322a; --drawdown: rgba(184, 50, 42, 0.16);
  --partition-is: #61666f; --partition-is-soft: #eceef1;
  --partition-holdout: #5b47b8; --partition-holdout-soft: #ece8fa;
  --status-confirmed: #17745f; --status-confirmed-soft: #ddf1ea;
  --status-rejected: #3b434e; --status-rejected-soft: #e5e7ea;
  --status-inconclusive: #8a5d00; --status-inconclusive-soft: #f6ecd2;
  --warning: #8a5d00; --warning-soft: #f6ecd2;
}
@media (prefers-color-scheme: dark) {
  :root {
    --ground: #0d0f11; --surface: #15181b; --surface-sunken: #0a0b0d; --line: #272b30;
    --ink: #ebe9e4; --ink-muted: #9ea4ac; --chart-grid: #20242a;
    --loss: #ff8a7a; --drawdown: rgba(255, 138, 122, 0.20);
    --partition-is: #8a9099; --partition-is-soft: #1d2126;
    --partition-holdout: #aa9bf2; --partition-holdout-soft: #211b3b;
    --status-confirmed: #4cc3a2; --status-confirmed-soft: #0f2a23;
    --status-rejected: #c0c7d1; --status-rejected-soft: #252a31;
    --status-inconclusive: #e3b24f; --status-inconclusive-soft: #2e2410;
    --warning: #e3b24f; --warning-soft: #2e2410;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--ground); color: var(--ink);
  font: 14px/1.5 "IBM Plex Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
}
main { max-width: 1040px; margin: 0 auto; padding: 32px 16px 48px; }
code, .num, .facts dd, .chart .axis {
  font-family: "IBM Plex Mono", ui-monospace, Consolas, monospace;
  font-variant-numeric: tabular-nums;
}
code { font-size: 0.92em; }
h1 { font-size: 28px; margin: 4px 0 16px; }
h2 { font-size: 20px; margin: 4px 0 8px; }
h3 { font-size: 15px; margin: 28px 0 4px; }
.eyebrow, .tag, th {
  text-transform: uppercase; letter-spacing: 0.06em; font-size: 11px; font-weight: 600;
}
.eyebrow { color: var(--ink-muted); margin: 0; }
.facts { display: grid; grid-template-columns: max-content 1fr; gap: 4px 16px; margin: 0; }
.facts dt { color: var(--ink-muted); }
.facts dd { margin: 0; overflow-wrap: anywhere; }
section {
  background: var(--surface); border: 1px solid var(--line); border-radius: 6px;
  padding: 16px 20px 20px; margin-top: 20px;
}
.partition-training { border-left: 3px solid var(--partition-is); }
.partition-holdout {
  border-left: 3px solid var(--partition-holdout);
  background-image: repeating-linear-gradient(
    45deg, var(--partition-holdout-soft) 0 1px, transparent 1px 10px);
}
.tag { display: inline-block; margin: 0; padding: 2px 8px; border-radius: 3px; }
.tag-training { background: var(--partition-is-soft); color: var(--partition-is); }
.tag-holdout { background: var(--partition-holdout-soft); color: var(--partition-holdout); }
.muted, .note { color: var(--ink-muted); }
.note { font-size: 12px; margin-top: 4px; }
.table-wrap { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; margin-top: 8px; }
th {
  color: var(--ink-muted); background: var(--surface-sunken); text-align: left;
  padding: 6px 12px; white-space: nowrap;
}
td { padding: 6px 12px; border-top: 1px solid var(--line); white-space: nowrap; }
.num { text-align: right; }
th code { text-transform: none; letter-spacing: 0; }
.chart { display: block; width: 100%; height: auto; margin-top: 8px; }
.chart .grid { stroke: var(--chart-grid); stroke-width: 1; }
.chart .axis { fill: var(--ink-muted); font-size: 11px; }
.chart .line { fill: none; stroke: var(--ink); stroke-width: 1.6; }
.chart .area { fill: var(--drawdown); }
.chart .area-edge { fill: none; stroke: var(--loss); stroke-width: 1.2; }
.callout {
  background: var(--warning-soft); color: var(--warning); padding: 8px 12px; border-radius: 4px;
}
.verdict { padding: 2px 8px; border-radius: 3px; }
.verdict-passed, .verdict-confirmed {
  background: var(--status-confirmed-soft); color: var(--status-confirmed);
}
.verdict-word { font-size: 20px; margin: 8px 0; }
.verdict-rejected { background: var(--status-rejected-soft); color: var(--status-rejected); }
.verdict-inconclusive {
  background: var(--status-inconclusive-soft); color: var(--status-inconclusive);
}
.disclaimer { color: var(--ink-muted); font-size: 12px; margin-top: 24px; }
@media (max-width: 600px) {
  section { padding: 12px 12px 16px; }
  td, th { padding: 6px 8px; }
}
"""


def render_html(sheet: TearSheet) -> str:
    """The tear-sheet as one self-contained HTML page."""
    return (
        '<!DOCTYPE html>\n<html lang="pl">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>Tear-sheet {_e(sheet.hypothesis)}</title>\n<style>{_STYLE}</style>\n"
        "</head>\n<body>\n<main>\n"
        f"{_header(sheet)}\n{_verdict(sheet)}\n{_training_section(sheet)}\n"
        f"{_holdout_section(sheet.holdout)}\n"
        f'<p class="disclaimer">{DISCLAIMER}</p>\n'
        "</main>\n</body>\n</html>\n"
    )
