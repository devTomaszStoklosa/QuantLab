"""The narrative of a result: Polish text from stored facts alone (q13)."""

import re
from datetime import date
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from quantlab.reporting import narrative
from quantlab.reporting.narrative import TemplateNarrator, narrative_rows, research_log_draft
from quantlab.reporting.results_store import (
    NarrativeUnavailableError,
    RegistryRow,
    stored_facts,
)
from quantlab.research.plan import logged_hypotheses
from quantlab.validation.holdout import HoldoutRecord

_STORE = Path(__file__).parents[2] / "presentation" / "fixtures" / "results"
_TODAY = date(2026, 9, 27)
# Words that would turn a description into advice (ADR-0005), in Polish and English:
# stems of verbs and nouns, and words that only advise as a whole ("warto", not
# "wartości").
_ADVICE_STEMS = ("kup", "sprzeda", "zwiększ", "zmniejsz", "inwestuj", "rekomend", "polec")
_ADVICE_WORDS = {"warto", "należy", "powinien", "powinno", "buy", "sell", "should", "recommend"}
_NUMBER = re.compile(r"(?<![\w.−-])[−-]?\d+(?:\.\d+)?%?(?![\w])")
_DATES = re.compile(r"\d{4}-\d{2}-\d{2}(?: \d{2}:\d{2})?")


def _registry() -> dict[str, dict]:
    rows = pq.read_table(_STORE / "hypotheses.parquet").to_pylist()
    return {row["hypothesis"]: row for row in rows}


def _row(hypothesis: str) -> RegistryRow:
    stored = _registry()[hypothesis]
    holdout = (
        HoldoutRecord(
            hypothesis=hypothesis,
            frozen_at_commit=stored["frozen_at_commit"],
            opened_at=stored["holdout_opened_at"],
            opened_at_commit=stored["holdout_opened_at_commit"],
            start=stored["holdout_start"],
            end=stored["holdout_end"],
            cost_model_name=stored["holdout_cost_model"],
            cagr=stored["holdout_cagr"],
            sharpe=stored["holdout_sharpe"],
            sortino=stored["holdout_sortino"],
            calmar=stored["holdout_calmar"],
            max_drawdown=stored["holdout_max_drawdown"],
            p_value=stored["holdout_p_value"],
            permutation={},
            criterion=stored["criterion"],
            verdict=stored["holdout_verdict"],
        )
        if stored["holdout_verdict"]
        else None
    )
    fields = {name: stored[name] for name in RegistryRow.model_fields if name != "holdout"}
    return RegistryRow(**fields, holdout=holdout)


def _text(hypothesis: str) -> tuple[str, object]:
    facts = stored_facts(_STORE, _row(hypothesis))
    return research_log_draft(facts, TemplateNarrator().sections(facts), _TODAY), facts


def _allowed_numbers(facts) -> set[str]:
    """Every number token the facts can print as: each numeric fact under each of the
    narrator's formats, and every number written inside a stored text or identifier."""
    values: list = []
    texts: list[str] = ["1.00"]  # the template's unit of P&L: starting equity 1.00

    def collect(value) -> None:
        if isinstance(value, bool) or value is None:
            return
        if isinstance(value, int | float):
            values.append(value)
        elif isinstance(value, str):
            texts.extend([value, value[:7]])
        elif isinstance(value, dict):
            for item in value.values():
                collect(item)
        elif isinstance(value, list | tuple):
            for item in value:
                collect(item)

    row = facts.row
    collect(row.model_dump(exclude={"holdout"}))
    if row.holdout is not None:
        collect(row.holdout.model_dump())
    for table in (facts.run, facts.metrics, facts.windows, facts.regimes, facts.asset_classes):
        collect(table)
    formatted = []
    for value in values:
        formatted += [str(value), f"{value:g}", f"{value:.4f}"]
        formatted += [
            narrative.pct(value),
            narrative.ratio(value),
            narrative.p_value(value),
            narrative.pnl(value),
            f"{value:.1%}",
        ]
    return {token for text in texts + formatted for token in _NUMBER.findall(text)} | {
        token.lstrip("−-") for text in formatted for token in _NUMBER.findall(text)
    }


@pytest.mark.parametrize(
    "hypothesis", ["demo_momentum", "demo_pairs", "demo_xsmom", "demo_select", "demo_portfolio"]
)
def test_every_number_in_the_draft_comes_from_the_stored_facts(hypothesis: str) -> None:
    draft, facts = _text(hypothesis)

    numbers = _NUMBER.findall(_DATES.sub("", draft))

    assert numbers
    assert set(numbers) - _allowed_numbers(facts) == set()


@pytest.mark.parametrize(
    "hypothesis", ["demo_momentum", "demo_pairs", "demo_xsmom", "demo_select", "demo_portfolio"]
)
def test_the_text_describes_and_never_advises(hypothesis: str) -> None:
    draft, _ = _text(hypothesis)

    words = re.findall(r"\w+", draft.lower())
    advice = [w for w in words if w.startswith(_ADVICE_STEMS) or w in _ADVICE_WORDS]
    assert advice == []


def test_the_draft_has_the_log_s_heading_so_the_plan_sees_the_entry(tmp_path) -> None:
    draft, _ = _text("demo_momentum")
    log = tmp_path / "RESEARCH_LOG.md"
    log.write_text("# Dziennik\n\n" + draft, encoding="utf-8")

    assert draft.startswith("## 2026-09-27 — demo_momentum: time_series_momentum na mvp-crypto")
    assert logged_hypotheses(log) == {"demo_momentum"}
    for heading in ("Hipoteza", "Metodologia", "Wynik — okres treningowy", "Wynik — holdout"):
        assert f"**{heading}" in draft
    assert "| Metryka | zero-cost | naive-10bps | realistic-10bps-k0.05-vol30d |" in draft


def test_an_opened_holdout_gives_the_recorded_verdict_and_the_registry_status() -> None:
    draft, facts = _text("demo_momentum")
    row = facts.row

    assert row.holdout is not None
    assert f"**Werdykt holdoutu:** {row.holdout.verdict}" in draft
    assert (
        f"**Status końcowy:** {row.status}. Wynika z reguł zapisanych przed wynikami: "
        f"walk-forward niezaliczony, holdout {row.holdout.verdict} → {row.status}."
    ) in draft
    assert "| p (test istotności) | 0.547 |" in draft


def test_a_sealed_holdout_names_the_command_and_gives_no_verdict() -> None:
    draft, facts = _text("demo_pairs")

    assert facts.row.holdout is None
    assert (
        "Holdout nieotwarty. Otwiera go jednorazowo komenda uv run quantlab open-holdout " in draft
    )
    assert "demo_pairs; do tego czasu hipoteza nie ma werdyktu." in draft
    assert (
        f"**Status końcowy:** brak werdyktu — holdout nieotwarty, status {facts.row.status}."
    ) in draft


def test_a_cpcv_gate_is_told_by_its_paths() -> None:
    draft, facts = _text("demo_select")

    assert "**CPCV (mediana Sharpe ścieżek):** " in draft
    assert f"{facts.run['cpcv_paths']} ścieżek, mediana Sharpe " in draft


def test_pnl_by_asset_class_is_told_when_stored() -> None:
    draft, facts = _text("demo_momentum")

    (crypto,) = facts.asset_classes
    assert (
        f"krypto {narrative.pnl(crypto['total_net_pnl'])} ({crypto['trades']} transakcji" in draft
    )
    assert "Opisowo, bez testu istotności per klasa." in draft


def test_the_app_gets_the_paragraphs_without_what_asks_the_researcher() -> None:
    facts = stored_facts(_STORE, _row("demo_momentum"))
    sections = TemplateNarrator().sections(facts)

    rows = narrative_rows(sections)

    assert [row["position"] for row in rows] == list(range(len(rows)))
    assert {row["section"] for row in rows} >= {"Hipoteza", "Metodologia", "Wniosek"}
    assert not any(
        "do uzupełnienia" in row["text"] or "jedno zdanie" in row["text"] for row in rows
    )
    assert all("|" not in row["text"] for row in rows)


def test_a_hypothesis_without_a_run_has_no_facts() -> None:
    row = _row("demo_reversal")

    with pytest.raises(NarrativeUnavailableError, match="uv run quantlab run demo_reversal"):
        stored_facts(_STORE, row)


@pytest.mark.parametrize(
    ("count", "text"),
    [
        (1, "1 transakcja"),
        (2, "2 transakcje"),
        (4, "4 transakcje"),
        (5, "5 transakcji"),
        (12, "12 transakcji"),
        (22, "22 transakcje"),
        (108, "108 transakcji"),
        (0, "0 transakcji"),
    ],
)
def test_counts_take_the_polish_plural_they_need(count: int, text: str) -> None:
    assert narrative.plural(count, "transakcja", "transakcje", "transakcji") == text
