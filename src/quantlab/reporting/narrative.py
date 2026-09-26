"""A hypothesis's result in words, assembled by templates from stored numbers (q13).

The facts are what the results store and the registry already hold - the training
run's summary, its tables, the definition and the holdout record - so the text
says nothing the lab did not compute: templates format numbers and compare them
only with thresholds the definition or the lab's rules set (REQ-1311). The text
is Polish, as every report of the lab, and describes history without advice
(ADR-0005). A `Narrator` turns facts into sections; `TemplateNarrator` is the one
implementation, and callers never ask which one they hold (REQ-1314).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Protocol

from pydantic import BaseModel

if TYPE_CHECKING:
    from quantlab.reporting.results_store import RegistryRow

# How the log and the terminal show numbers: a true minus sign in the log's tables.
_MINUS = "−"

_GATES = {
    "walk_forward": "walk-forward",
    "cpcv": "CPCV (mediana Sharpe ścieżek)",
}
_TESTS = {
    "day_shuffle": "test permutacyjny (tasowanie dni względem trzymanych pozycji)",
    "random_portfolio": "test losowych portfeli z tego samego przekroju",
}
_REGIMES = {"low": "niski", "medium": "średni", "high": "wysoki", "undefined": "nieokreślony"}
_ASSET_CLASSES = {
    "crypto": "krypto",
    "equity": "akcje",
    "bond": "obligacje",
    "commodity": "surowce",
    "currency": "waluty",
    "real_estate": "nieruchomości",
    "cash": "gotówka",
}
_METRICS = (
    ("CAGR", "cagr", "pct"),
    ("Sharpe", "sharpe", "ratio"),
    ("Sortino", "sortino", "ratio"),
    ("Calmar", "calmar", "ratio"),
    ("Max drawdown", "max_drawdown", "pct"),
)
_INTERPRETATION = (
    "do uzupełnienia przez badacza: co mówią liczby poza werdyktem, ograniczenia badania, co dalej."
)


def plural(count: int, one: str, few: str, many: str) -> str:
    """`count` with the Polish noun form it takes: 1 transakcja, 2 transakcje, 5 transakcji."""
    if count == 1:
        form = one
    elif count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
        form = few
    else:
        form = many
    return f"{count} {form}"


def _signed(text: str) -> str:
    return text.replace("-", _MINUS)


def pct(value: float | None) -> str:
    return "n/a" if value is None else _signed(f"{value:.2%}")


def ratio(value: float | None) -> str:
    return "n/a" if value is None else _signed(f"{value:.2f}")


def p_value(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def pnl(value: float) -> str:
    return _signed(f"{value:+.4f}")


def _share(value: float | None) -> str:
    """A share already stored as a fraction, e.g. a percentile of the null."""
    return "n/a" if value is None else f"{value:.1%}"


class Paragraph(BaseModel):
    """A labelled line of a section. `draft_only` lines ask the researcher for
    something; they belong in the research-log draft, not in the app."""

    label: str | None = None
    text: str
    draft_only: bool = False


class Section(BaseModel):
    heading: str
    paragraphs: list[Paragraph]
    table: list[list[str]] | None = None  # header row first


@dataclass(frozen=True)
class Facts:
    """One hypothesis as stored: its registry row and its training run's tables."""

    row: RegistryRow
    run: dict
    metrics: list[dict]
    windows: list[dict]
    regimes: list[dict]
    asset_classes: list[dict]


class Narrator(Protocol):
    def sections(self, facts: Facts) -> list[Section]: ...


class TemplateNarrator:
    """Polish sections of a research-log entry from the facts alone (REQ-1310)."""

    def sections(self, facts: Facts) -> list[Section]:
        return [
            self._hypothesis(facts),
            self._methodology(facts),
            self._training(facts),
            self._holdout(facts),
            self._conclusion(facts),
        ]

    @staticmethod
    def _hypothesis(facts: Facts) -> Section:
        row = facts.row
        return Section(
            heading="Hipoteza",
            paragraphs=[
                Paragraph(text="jedno zdanie, co testujemy.", draft_only=True),
                Paragraph(
                    text=f"Strategia {row.strategy} z parametrami {_parameters(facts)} "
                    f"na uniwersum {row.universe}."
                ),
            ],
        )

    @staticmethod
    def _methodology(facts: Facts) -> Section:
        row, run = facts.row, facts.run
        holdout = row.holdout
        opened = (
            f"otwarty {holdout.opened_at:%Y-%m-%d %H:%M} UTC (commit "
            f"{holdout.opened_at_commit[:7]})"
            if holdout
            else "jeszcze nieotwarty"
        )
        models = ", ".join(metric["cost_model"] for metric in facts.metrics)
        return Section(
            heading="Metodologia",
            paragraphs=[
                Paragraph(
                    label="Dane",
                    text=f"źródło {run['data_source']}, uniwersum {row.universe}; pierwsza "
                    f"pozycja {run['first_position'] or 'brak'}.",
                ),
                Paragraph(
                    label="Koszty",
                    text=f"trzy modele na tych samych sygnałach: {models}. Główny, na którym "
                    f"liczone są walidacja, reżimy i rejestr transakcji: {row.cost_model}.",
                ),
                Paragraph(
                    label="Okres treningowy",
                    text=f"{row.training_start} → {row.training_end}.",
                ),
                Paragraph(
                    label="Holdout",
                    text=f"{row.holdout_start} → {row.holdout_end}, zamrożony w "
                    f"config/holdout/{row.hypothesis}.yaml (commit {row.frozen_at_commit[:7]}) "
                    f"przed pierwszym przebiegiem; {opened}.",
                ),
                Paragraph(
                    label="Walidacja",
                    text=f"bramka in-sample: {_gate(row.in_sample_validation)}; "
                    f"{_TESTS.get(run['permutation_test'], run['permutation_test'])}, "
                    f"{plural(run['permutation_count'], 'losowanie', 'losowania', 'losowań')}, "
                    f"seed {run['permutation_seed']}, "
                    f"statystyka: {run['permutation_statistic']}, α = "
                    f"{run['permutation_alpha']:g}; kryterium holdoutu: {row.criterion}",
                ),
                Paragraph(
                    label="Wielokrotne testowanie",
                    text=f"{plural(len(run['trials']), 'próba', 'próby', 'prób')} na tym "
                    f"uniwersum i nakładającym się okresie treningowym "
                    f"({', '.join(run['trials'])}), "
                    f"{plural(run['configurations'], 'konfiguracja', 'konfiguracje', 'konfiguracji')}"
                    " w progu deflated Sharpe.",
                ),
            ],
        )

    def _training(self, facts: Facts) -> Section:
        run = facts.run
        paragraphs = [
            Paragraph(label="Koszty", text=_costs(run)),
            Paragraph(
                label=_capitalized(_gate(facts.row.in_sample_validation)), text=_gate_result(facts)
            ),
            Paragraph(label="Test istotności", text=_significance(run)),
            Paragraph(
                label="Wielokrotne testowanie",
                text=f"Sharpe roczny {ratio(run['sharpe_annualized'])}, PSR "
                f"{ratio(run['psr'])}, próg deflated Sharpe "
                f"{ratio(run['dsr_threshold'])}, DSR {ratio(run['dsr'])}.",
            ),
        ]
        if facts.regimes:
            paragraphs.append(Paragraph(label="Reżimy", text=_regimes(facts)))
        if facts.asset_classes:
            paragraphs.append(Paragraph(label="Skąd wynik", text=_asset_classes(facts)))
        paragraphs.append(
            Paragraph(
                label="Transakcje",
                text=f"{plural(run['trades'], 'transakcja', 'transakcje', 'transakcji')} ("
                f"{plural(run['trades_open_at_end'], 'otwarta', 'otwarte', 'otwartych')} na "
                f"końcu), {run['trades_winning']} z dodatnim P&L netto.",
            )
        )
        header = ["Metryka", *(f"{metric['cost_model']}" for metric in facts.metrics)]
        table = [header] + [
            [name, *(_format(metric[key], kind) for metric in facts.metrics)]
            for name, key, kind in _METRICS
        ]
        return Section(
            heading=f"Wynik — okres treningowy {run['start']} → {run['end']}",
            paragraphs=paragraphs,
            table=table,
        )

    @staticmethod
    def _holdout(facts: Facts) -> Section:
        row = facts.row
        holdout = row.holdout
        heading = f"Wynik — holdout {row.holdout_start} → {row.holdout_end}"
        if holdout is None:
            return Section(
                heading=heading,
                paragraphs=[
                    Paragraph(
                        text="Holdout nieotwarty. Otwiera go jednorazowo komenda uv run "
                        f"quantlab open-holdout {row.hypothesis}; do tego czasu hipoteza "
                        "nie ma werdyktu."
                    )
                ],
            )
        table = [
            ["Metryka", "Holdout"],
            ["CAGR", pct(holdout.cagr)],
            ["Sharpe netto", ratio(holdout.sharpe)],
            ["Sortino", ratio(holdout.sortino)],
            ["Calmar", ratio(holdout.calmar)],
            ["Max drawdown", pct(holdout.max_drawdown)],
            ["p (test istotności)", p_value(holdout.p_value)],
        ]
        return Section(
            heading=heading,
            paragraphs=[
                Paragraph(
                    text=f"Jednorazowe otwarcie, model {holdout.cost_model_name}: CAGR "
                    f"{pct(holdout.cagr)}, Sharpe netto {ratio(holdout.sharpe)}, max "
                    f"drawdown {pct(holdout.max_drawdown)}, p = {p_value(holdout.p_value)}."
                ),
                Paragraph(
                    label="Werdykt holdoutu",
                    text=f"{holdout.verdict} (kryterium: {holdout.criterion})",
                ),
            ],
            table=table,
        )

    @staticmethod
    def _conclusion(facts: Facts) -> Section:
        row = facts.row
        holdout = row.holdout
        if holdout is None:
            status = Paragraph(
                label="Status końcowy",
                text=f"brak werdyktu — holdout nieotwarty, status {row.status}.",
            )
        else:
            gate = _gate(row.in_sample_validation)
            passed = facts.run["in_sample_passed"]
            gate_state = {True: "zaliczony", False: "niezaliczony", None: "nierozstrzygnięty"}
            status = Paragraph(
                label="Status końcowy",
                text=f"{row.status}. Wynika z reguł zapisanych przed wynikami: "
                f"{gate} {gate_state[passed]}, holdout {holdout.verdict} → {row.status}.",
            )
        return Section(
            heading="Wniosek",
            paragraphs=[
                status,
                Paragraph(label="Interpretacja", text=_INTERPRETATION, draft_only=True),
            ],
        )


def _format(value: float | None, kind: str) -> str:
    return pct(value) if kind == "pct" else ratio(value)


def _parameters(facts: Facts) -> str:
    parameters = json.loads(facts.run["strategy_params"])
    return ", ".join(f"{name} = {value}" for name, value in parameters.items()) or "brak"


def _gate(validation: str) -> str:
    return _GATES.get(validation, validation)


def _capitalized(text: str) -> str:
    return text[:1].upper() + text[1:]


def _costs(run: dict) -> str:
    difference = run["cost_sharpe_difference"]
    text = (
        f"werdykt wrażliwości na koszty: {run['cost_sensitivity']}; różnica Sharpe między "
        f"modelem naiwnym a realistycznym {ratio(difference)}"
    )
    if run["cost_cagr_sign_flip"]:
        text += "; realistyczne koszty zmieniają znak CAGR"
    return text + "."


def _gate_result(facts: Facts) -> str:
    run = facts.run
    state = {True: "zaliczony", False: "niezaliczony", None: "nierozstrzygnięty"}
    if facts.row.in_sample_validation == "cpcv":
        return (
            f"{state[run['in_sample_passed']]}; "
            f"{plural(run['cpcv_paths'], 'ścieżka', 'ścieżki', 'ścieżek')}, mediana Sharpe "
            f"{ratio(run['cpcv_median_sharpe'])}, najniższy {ratio(run['cpcv_min_sharpe'])}, "
            f"najwyższy {ratio(run['cpcv_max_sharpe'])}, dodatnie "
            f"{_share(run['cpcv_positive_share'])} ścieżek. Reguła: {run['cpcv_rule']}."
        )
    windows = "; ".join(
        f"{window['start']} → {window['end']}"
        + (" (niepełny)" if window["partial"] else "")
        + f": CAGR {pct(window['cagr'])}, Sharpe {ratio(window['sharpe'])}"
        for window in facts.windows
        if not window["aggregate"]
    )
    with_sharpe = run["walk_forward_windows_with_sharpe"]
    return (
        f"{state[run['walk_forward_passed']]}, {run['walk_forward_positive_windows']} z "
        f"{with_sharpe} {'okna' if with_sharpe == 1 else 'okien'} ze Sharpe > 0. Reguła: "
        f"{run['walk_forward_rule']}. Okna: {windows}."
    )


def _significance(run: dict) -> str:
    p = run["permutation_p_value"]
    if p is None:
        return f"brak wyniku: {run['permutation_reason']}."
    alpha = run["permutation_alpha"]
    verdict = "istotny" if p < alpha else "nieistotny"
    text = (
        f"statystyka {ratio(run['permutation_actual'])} wobec średniej losowań "
        f"{ratio(run['permutation_null_mean'])} (odch. std. "
        f"{ratio(run['permutation_null_std'])}); wyższa niż "
        f"{_share(run['permutation_percentile'])} losowań; p = {p_value(p)}, {verdict} "
        f"przy α = {alpha:g}"
    )
    if run["permutation_low_confidence"]:
        days = plural(run["permutation_active_days"], "dzień", "dni", "dni")
        text += f"; niska wiarygodność: tylko {days} z pozycją"
    return text + "."


def _regimes(facts: Facts) -> str:
    return (
        "; ".join(
            f"{_REGIMES.get(regime['regime'], regime['regime'])}: CAGR {pct(regime['cagr'])}, "
            f"Sharpe {ratio(regime['sharpe'])} ({plural(regime['days'], 'dzień', 'dni', 'dni')})"
            for regime in facts.regimes
        )
        + f". {facts.run['regime_method']}"
    )


def _asset_classes(facts: Facts) -> str:
    return (
        "P&L netto transakcji w jednostkach kapitału startowego 1.00: "
        + "; ".join(
            f"{_ASSET_CLASSES.get(group['key'], group['key'])} {pnl(group['total_net_pnl'])} "
            f"({plural(group['trades'], 'transakcja', 'transakcje', 'transakcji')}, koszty "
            f"{group['costs']:.4f})"
            for group in facts.asset_classes
        )
        + ". Opisowo, bez testu istotności per klasa."
    )


def research_log_draft(facts: Facts, sections: list[Section], today: date) -> str:
    """The draft of a research-log entry in the log's Markdown (REQ-1320, REQ-1321):
    its heading is the form `quantlab plan` recognizes once committed to the log."""
    row = facts.row
    lines = [f"## {today.isoformat()} — {row.hypothesis}: {row.strategy} na {row.universe}", ""]
    for section in sections:
        lines.append(f"**{section.heading}:**")
        lines.append("")
        for paragraph in section.paragraphs:
            text = f"_{paragraph.text}_" if paragraph.draft_only else paragraph.text
            lines.append(f"- **{paragraph.label}:** {text}" if paragraph.label else f"- {text}")
        if section.table:
            header, *body = section.table
            lines.append("")
            lines.append("| " + " | ".join(header) + " |")
            lines.append("|---|" + "---:|" * (len(header) - 1))
            lines.extend("| " + " | ".join(cells) + " |" for cells in body)
        lines.append("")
    return "\n".join(lines)


def narrative_rows(sections: list[Section]) -> list[dict]:
    """The paragraphs the app shows, in order (REQ-1330): what asks the researcher
    for something stays in the draft, and tables stay in the app's own panels."""
    rows = []
    for section in sections:
        for paragraph in section.paragraphs:
            if paragraph.draft_only:
                continue
            text = f"{paragraph.label}: {paragraph.text}" if paragraph.label else paragraph.text
            rows.append({"position": len(rows), "section": section.heading, "text": text})
    return rows
