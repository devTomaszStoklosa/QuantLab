# q13-research-narrative - Design

Status: Ready for dev
Owner role: Architect
Upstream: 02-spec.md
ADRs: docs/adr/0005-descriptive-reports-no-investment-advice.md, docs/adr/0006-dotnet-react-presentation-layer-only.md, docs/adr/0008-results-store-parquet-duckdb.md, docs/adr/0009-private-repo-free-tiingo-plan.md

## Context and constraints

- **Liczby już są w magazynie.** `quantlab run` zapisuje przebieg treningowy w `results/<hipoteza>/*.parquet`. `run`, `open-holdout` i `registry` odświeżają rejestr `hypotheses.parquet`, łącznie ze statusem i zapisem otwarcia holdoutu.
- **Warstwa prezentacji tylko czyta** ([ADR-0006](../../adr/0006-dotnet-react-presentation-layer-only.md)). Tekst składa Python; .NET i React go tylko pokazują.
- **Za darmo i na słabej maszynie** ([ADR-0009](../../adr/0009-private-repo-free-tiingo-plan.md), decyzja 2026-09-26). Opis powstaje z szablonów, bez modelu językowego.
- **Opisowo** ([ADR-0005](../../adr/0005-descriptive-reports-no-investment-advice.md)): bez rekomendacji.

## Quality attribute scenarios

| Source | Stimulus | Response | Measure |
|---|---|---|---|
| Badacz | szkic wpisu | każda liczba z magazynu | test: liczby w tekście ⊆ sformatowane fakty |
| Badacz | holdout otwarty po przebiegu | opis w aplikacji z werdyktem | test: odświeżenie rejestru przepisuje opis |
| Deweloper | nowy szablon | brak słów rekomendacji | test na liście zakazanych fraz |
| Deweloper | magazyn sprzed `q13` | aplikacja działa | test API: brak tabeli → pusty opis |
| Deweloper | wyniki hipotez | bez zmian | zrzut regresji bajt w bajt |

## Options

### Decyzja 1 — skąd fakty

- **A. Z magazynu wyników i rejestru** (`read_facts(store, row)`). To te same liczby co w aplikacji i w terminalu. Narracja działa bez ponownego przebiegu i nadąża za otwarciem holdoutu.
- B. Z obiektów w pamięci podczas `run`: opis byłby nieaktualny po `open-holdout` i niedostępny bez ponownego przebiegu.

### Decyzja 2 — kto składa tekst

- **A. `Narrator` (Protocol) z implementacją `TemplateNarrator`.** Czyste funkcje z faktów do sekcji. Model językowy mógłby później przyjść jako inna implementacja.
- B. Szablony w .NET/React: tekst liczony poza Pythonem (ADR-0006) i dwa miejsca do utrzymania.

### Decyzja 3 — gdzie opis żyje

- **A. Szkic w `quantlab narrate` (Markdown dla dziennika) i akapity w tabeli `narrative` magazynu, zapisywanej przy każdym odświeżeniu rejestru.** Aplikacja czyta tabelę; jej brak to pusty opis.
- B. Tylko komenda, bez aplikacji. Mniej pracy, ale aplikacja dalej pokazuje same tabele.
- C. Kolumna tekstowa w rejestrze. Zmiana schematu rejestru i wersji magazynu, a wszystkie przebiegi stałyby się nieaktualne w planie.

## Trade-off matrix (1-5)

| Criterion | 1A | 1B | 2A | 2B | 3A | 3B | 3C |
|---|---|---|---|---|---|---|---|
| Liczby tylko z kodu | 5 | 5 | 5 | 3 | 5 | 5 | 5 |
| Aktualność po otwarciu holdoutu | 5 | 2 | — | — | 5 | 5 | 5 |
| Zgodność z ADR-0006 | 5 | 5 | 5 | 1 | 5 | 5 | 5 |
| Zgodność wsteczna magazynu | 5 | 5 | — | — | 5 | 5 | 2 |
| Złożoność | 4 | 4 | 5 | 3 | 3 | 5 | 3 |

## Decision

Recommended: **1A, 2A, 3A.**

- Fakty czyta się z magazynu i rejestru.
- `TemplateNarrator` implementuje `Narrator`.
- Szkic wpisu daje `quantlab narrate`, a akapity opisu trafiają do tabeli `narrative` przy każdym odświeżeniu rejestru.

Revisit if: szablony okażą się za sztywne do opisu nowych rodzajów hipotez. Wtedy powstaje osobny epik z modelem jako drugą implementacją `Narrator`, a liczby w tekście nadal są sprawdzane z faktami.

## Contracts

```python
# reporting/narrative.py
class Facts(BaseModel):          # one hypothesis: registry row + stored run tables
    row: RegistryRow; run: dict; metrics: list[dict]; windows: list[dict]
    regimes: list[dict]; asset_classes: list[dict]
class Section(BaseModel): heading: str; paragraphs: list[str]; table: list[list[str]] | None
class Narrator(Protocol):
    def sections(self, facts: Facts) -> list[Section]: ...
class TemplateNarrator: ...       # Polish templates
def read_facts(store: Path, row: RegistryRow) -> Facts        # raises NarrativeUnavailable
def research_log_draft(facts: Facts, sections: list[Section], today: date) -> str
def narrative_rows(sections: list[Section]) -> list[dict]      # position, section, text

# reporting/results_store.py
write_registry(...)  # also writes <h>/narrative.parquet for hypotheses with a run

# cli.py
quantlab narrate HYPOTEZA [--output PATH]
```

Pliki:

- `src/quantlab/reporting/narrative.py`, `src/quantlab/reporting/results_store.py`, `src/quantlab/cli.py`, `src/quantlab/research/plan.py`;
- `presentation/QuantLab.Api/Store/*`, `presentation/web/src/api.ts`, `presentation/web/src/screens/*`;
- testy: `tests/reporting/test_narrative.py`, `tests/test_narrate_command.py`, testy magazynu, API i aplikacji.

## Rollout and rollback

1. **N1** dokumentacja: 01-story, 02-spec, 03-design, ROADMAP.
2. **N2** fakty, `TemplateNarrator`, szkic wpisu, `quantlab narrate`, krok planu; testy liczb, zakazanych fraz i statusów.
3. **N3** tabela `narrative` przy odświeżeniu rejestru, API, panel aplikacji, odświeżone fixtures.
4. **N4** dokumentacja użytkowa: INSTRUKCJA (rozdział o dzienniku), README, ARCHITECTURE, CLAUDE.md (zasada 3).

Rollback: `git revert` per slice. Żaden slice nie zmienia wyników ani werdyktów.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Liczba w opisie niezgodna z magazynem | niska | wysoki | liczby tylko z faktów; test porównuje liczby w tekście z faktami |
| Opis brzmi jak rekomendacja | niska | wysoki | lista zakazanych fraz sprawdzana testem na każdym statusie |
| Opis nieaktualny po otwarciu holdoutu | średnia | średni | zapis przy każdym odświeżeniu rejestru |
| Szablon zbyt ogólny dla hipotez z diagnostyką (pary, portfel, dobór) | średnia | niski | ogólne sekcje; diagnostyka zostaje w panelach i w interpretacji badacza |

## Handoff notes

- Szkic wpisu nie zastępuje interpretacji. Sekcja „Interpretacja" zostaje pusta z przypomnieniem, a wpis zatwierdza badacz.
