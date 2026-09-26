# q14-data-quality - Design

Status: Ready for dev
Owner role: Architect
Upstream: 02-spec.md
ADRs: docs/adr/0004-validation-first-frozen-holdout.md, docs/adr/0009-private-repo-free-tiingo-plan.md

## Context and constraints

- **Jeden punkt wejścia danych.** Wszystkie przebiegi pobierają bary przez `cli._fetch_market_data`. Po nim bary są skorygowane o akcje korporacyjne, zakończone delistingiem i (na uniwersum z gotówką) przeliczone przez gotówkę.
- **Diagnostyka treningu** (`TrainingDiagnostic`: tytuł i wartości liczbowe) trafia do terminala, tear-sheetu, magazynu i aplikacji bez zmiany schematu.
- **Holdout otwiera się raz,** a zapis powstaje dopiero po obliczeniu wyniku.
- **SOLID:** kontrole to podstawialne implementacje, bez `if` po typie.

## Options

### Decyzja 1 — gdzie żyją kontrole

- **A. `core.data.quality`: protokół `DataCheck` i lista implementacji.** `quality_report(bars, sessions)` uruchamia wszystkie kontrole i zbiera ustalenia. Nowa kontrola to nowa klasa na liście.
- B. Kontrole w adapterach źródeł: każde źródło sprawdzałoby inaczej, a wady powstałe przy korektach (split) byłyby niewidoczne.

### Decyzja 2 — co robi wada

- **A. Dwa poziomy.** Błąd zatrzymuje przed backtestem albo przed obliczeniem holdoutu. Ostrzeżenie jest raportowane, a przebieg liczy dalej.
- B. Wszystko raportowane, nic nie zatrzymuje. Wtedy wynik na zduplikowanych datach albo cenie zero trafiłby do magazynu, a holdout otworzyłby się na złych danych.
- C. Naprawa danych (usunięcie duplikatów, interpolacja luk): zmiana danych po cichu, czyli reguła czyszczenia, której żadna hipoteza nie zamroziła.

### Decyzja 3 — raport w magazynie

- **A. Diagnostyka treningu „Data quality"** z liczbą ustaleń per kontrola. Działa bez zmiany schematu, a pełna lista jest w `quantlab check-data`.
- B. Nowa tabela ustaleń: więcej szczegółów w aplikacji, ale nowa tabela w magazynie, API i UI dla danych, które badacz ogląda w terminalu.

## Decision

Recommended: **1A, 2A, 3A.**

- Kontrole są listą implementacji `DataCheck` w `core.data.quality`.
- Błędy zatrzymują `run` i otwarcie holdoutu, a ostrzeżenia są raportowane.
- Magazyn dostaje diagnostykę z liczbami ustaleń, a szczegóły daje `check-data`.

Revisit if: badacz potrzebuje listy ustaleń w aplikacji (3B) albo reguły czyszczenia danych jako części definicji hipotezy (nowy epik).

## Contracts

```python
# core/data/quality.py
Level = Literal["error", "warning"]
@dataclass(frozen=True)
class Finding: check: str; level: Level; instrument_id: str; day: date | None; detail: str
class DataCheck(Protocol):
    name: str; level: Level
    def findings(self, instrument_id: str, bars: list[PriceBar], sessions: list[date]) -> list[Finding]: ...
CHECKS: tuple[DataCheck, ...]   # the lab's checks, in report order
@dataclass(frozen=True)
class QualityReport:
    instruments: int; bars: int; findings: list[Finding]
    errors / warnings / counts() / diagnostic() -> TrainingDiagnostic
def reference_sessions(universe: Universe, bars) -> list[date]
def quality_report(bars, sessions, checks=CHECKS) -> QualityReport

# core/universe.py
Universe.trades_every_day   # periods_per_year >= 365; also used by calendar_days

# cli.py
quantlab run: fetch -> quality_report -> errors: exit 1 | warnings: report + diagnostic
open_frozen_holdout: errors -> DataQualityError before the backtest
quantlab check-data HYPOTEZA
```

## Rollout and rollback

1. **D1** dokumentacja: 01-story, 02-spec, 03-design, ROADMAP.
2. **D2** kontrole, raport, `run`, `open-holdout`, `check-data`; odświeżone fixtures (nowe wiersze diagnostyki); testy na danych z wadami w znanych datach; zrzut regresji bez zmian.
3. **D3** dokumentacja użytkowa: INSTRUKCJA (rozdział o wynikach i o błędach), README, ARCHITECTURE.

Rollback: `git revert` per slice.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Fałszywe braki sesji w świętach | średnia | niski | sesje referencyjne z danych rynku (suma dat instrumentów) |
| Prawdziwy krach jako wada | wysoka | niski | skrajne ruchy tylko jako ostrzeżenia z datą |
| Wolna kontrola na S&P 500 | niska | niski | jedna pętla po barach na kontrolę; numpy dla zwrotów |
