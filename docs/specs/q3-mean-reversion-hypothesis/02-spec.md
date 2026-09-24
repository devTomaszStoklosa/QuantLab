# q3-mean-reversion-hypothesis - Specification

Status: Draft
Owner role: BA
Upstream: 01-story.md

## Glossary

| Term | Meaning |
|---|---|
| Okres formacji | liczba dni `k`, z których liczony jest zwrot decydujący o sygnale odwrócenia |
| Sygnał odwrócenia | pozycja przeciwna do znaku zwrotu z okresu formacji: po spadku long, po wzroście short |
| Definicja hipotezy | zacommitowany plik z parametrami strategii, uniwersum, modelem kosztów, okresem treningowym, zakresem holdoutu i kryterium sukcesu — jedyne źródło parametrów przebiegu |
| Obrót (turnover) | suma wartości bezwzględnych handlowanych wag w okresie, jako krotność kapitału na rok |
| Liczba prób | liczba hipotez przetestowanych dotąd na tym samym koszyku i okresie |

Terminy z `q1` (hipoteza, `BacktestRun`, holdout, zamrożenie, reżim, walk-forward, test permutacyjny) bez zmian — patrz [q1 02-spec](../q1-momentum-research-mvp/02-spec.md).

## Actors and permissions

| Actor | Action | Allowed |
|---|---|---|
| Kod epiku | uruchamia przebieg hipotezy, której definicja nie jest zacommitowana | nie (REQ-303) |
| Kod epiku | zmienia zamrożony plik `momentum_v1` przy uogólnianiu schematu | nie (REQ-302) |
| Kod epiku | wczytuje dane z zakresu holdoutu `mean_reversion_v1` poza jednorazowym otwarciem | nie (REQ-041 z q1) |

## Functional requirements (EARS)

Uogólniony runner

- REQ-301 (AC-3): The study runner shall read strategy, strategy parameters, universe, cost model and training range from the hypothesis definition, and shall build the strategy without branching on the hypothesis or strategy type.
- REQ-302 (AC-1): When `momentum_v1` is run through the generalized runner, every snapshot and metric shall equal the pre-generalization result, and `config/holdout/momentum_v1.yaml` shall parse without modification.
- REQ-303 (AC-3): When a hypothesis definition is missing, uncommitted or has uncommitted changes, `quantlab run` shall refuse to run that hypothesis before fetching any data.
- REQ-304 (AC-7): `quantlab open-holdout` shall open any defined hypothesis's holdout at most once, with one opening record per hypothesis.

Sygnał

- REQ-310 (AC-2): When `ShortTermReversal.generate_signals` computes a signal for date `t`, the computation shall use only data with timestamp `<= t`.
- REQ-311 (AC-2): The reversal signal shall be a pure function of price history and the formation period: short after a positive formation-period return, long after a negative one, flat after an exactly zero one, and no signal when history is shorter than the formation period or there is no bar for `t`.

Koszty i obrót

- REQ-320 (AC-4): The report shall show the annualized turnover of each run, computed from weights actually traded by the engine.
- REQ-321 (AC-4): The cost comparison and sensitivity verdict of `q1` (REQ-030, REQ-031) shall apply to this hypothesis unchanged.

Walidacja i raport

- REQ-330 (AC-5): Walk-forward, permutation test, regime-conditional metrics, stress test, trade ledger and tear-sheet shall run for this hypothesis with the same settings and pass rules as for `momentum_v1`.
- REQ-331: The walk-forward pass rule, permutation settings, success criterion and holdout range shall be committed before the first run of `mean_reversion_v1` that reads market data.
- REQ-332: The terminal status shall come from `concluded_status` (REQ-090 of `q1`).

Kontrast

- REQ-340 (AC-6): The report shall show the Pearson correlation of daily net returns of `momentum_v1` and `mean_reversion_v1` over the dates on which both runs hold a position.

Dziennik

- REQ-350 (AC-7): The research log entry shall state the number of hypotheses tested so far on the same basket and period.

## Business rules

Status hipotezy — jak w `q1` (`concluded_status`): `confirmed` tylko przy zaliczonym walk-forward i holdoucie, niezaliczona bramka → `rejected`, pozostałe przypadki → `inconclusive`.

Interpretacja korelacji z `momentum_v1` (opisowa, poza regułami statusu)

| Korelacja dziennych zwrotów | Interpretacja w raporcie |
|---|---|
| silnie ujemna | strategie są w dużej mierze lustrem — reversal to w praktyce „momentum z odwrotnym znakiem", nie osobny efekt |
| bliska zera | strategie reagują na różne ruchy rynku — osobne źródła wyniku (lub osobny szum) |
| silnie dodatnia | obie strategie zarabiają i tracą razem — wspólna ekspozycja, np. na kierunek rynku |

## Data and validation

`ShortTermReversalParameters` (w definicji hipotezy)

| Field | Type | Required | Range or format |
|---|---|---|---|
| `strategy` | enum | tak | `short_term_reversal` |
| `formation_days` | int | tak | ≥ 1 |
| `universe` | string | tak | nazwa istniejącego uniwersum |
| `cost_model` | object | tak | jak w `momentum_v1` |

Definicja `momentum_v1` pozostaje w obecnym formacie (`strategy: time_series_momentum`, `lookback_days`); schemat rozróżnia strategie po polu `strategy`.

## Edge and error cases

- Zwrot z okresu formacji równy zero → brak pozycji na ten dzień, nie błąd.
- Instrument bez baru na dzień `t` albo z historią krótszą niż okres formacji → brak sygnału dla tego instrumentu, reszta koszyka działa.
- Nieznana wartość `strategy` w definicji hipotezy → błąd walidacji przy wczytaniu, przed pobraniem danych.
- Przebieg bez żadnej transakcji → obrót 0, nie błąd.
- Korelacja, gdy jedna z serii nie ma wariancji albo wspólnych dni z pozycją jest mniej niż 2 → wynik „niezdefiniowana", nie liczba.
- Zakres holdoutu `mean_reversion_v1` nachodzący na okres treningowy → błąd przy wczytaniu (jak w `q1`).

## Non-functional requirements

- Performance: pełny przebieg jednej hipotezy (trzy modele kosztów, walidacja, 10 000 permutacji) poniżej 1 minuty na maszynie deweloperskiej.
- Reproducibility: ten sam seed i te same wejścia dają identyczny wynik; `momentum_v1` identyczne przed i po uogólnieniu runnera.
- Security and privacy: brak danych osobowych.

## Traceability

| AC | REQ |
|---|---|
| AC-1 | REQ-302 |
| AC-2 | REQ-310, REQ-311 |
| AC-3 | REQ-301, REQ-303 |
| AC-4 | REQ-320, REQ-321 |
| AC-5 | REQ-330, REQ-331 |
| AC-6 | REQ-340 |
| AC-7 | REQ-304, REQ-332, REQ-350 |

## Open questions

| # | Question | Owner |
|---|---|---|
| 1 | Pytania 1–4 z [01-story.md](01-story.md) (okres formacji, koszyk, zakres holdoutu, kryterium sukcesu) blokują zamrożenie (M4) | Tomasz |
