# q1-momentum-research-mvp - Specification

Status: Ready for architect
Owner role: BA
Upstream: 01-story.md

## Glossary

| Term | Meaning |
|---|---|
| Hipoteza | encja z tezą, statusem (`proposed`/`testing`/`confirmed`/`rejected`/`inconclusive`) i uzasadnieniem |
| Sygnał | wartość per instrument i data mówiąca strategii, czy wejść długo/krótko/nic nie robić |
| BacktestRun | jeden przebieg silnika: konfiguracja strategii + uniwersum + zakres dat + model kosztów + wynik |
| PortfolioSnapshot | stan portfela (equity, gotówka, pozycje) w jednym punkcie czasu przebiegu |
| Trade | jedna zamknięta pozycja z pełną historią wejścia/wyjścia i kosztów |
| Holdout | zakres dat celowo nieużyty przy budowie/dostrajaniu hipotezy, zamrożony przed sprawdzeniem wyniku |
| Zamrożenie | zapis parametrów hipotezy i zakresu holdout w pliku, commitowany przed uruchomieniem na holdout |
| Reżim | etykieta okresu rynkowego (np. tercyl zmienności zrealizowanej) używana do warunkowych metryk |
| Walk-forward | metoda walidacji: rolling okno treningowe + test, przesuwane chronologicznie |
| Test permutacyjny | test istotności: porównanie wyniku strategii z rozkładem wyników na losowo przetasowanych danych |

## Actors and permissions

| Actor | Action | Allowed |
|---|---|---|
| Kod epiku | czyta dane przez `core.data`/`core.storage` z lab-foundation | tak |
| Kod epiku | oznacza hipotezę jako `confirmed` bez przejścia walk-forward i holdout | nie (REQ-090) |
| Silnik backtestu | używa danych z zakresu holdout przed jego formalnym „odmrożeniem" | nie, poza jawnym przebiegiem walidacji końcowej |

## Functional requirements (EARS)

Hipoteza

- REQ-001 (AC-1): When a new hypothesis is registered, the system shall store title, statement, creation date and initial status `proposed`.
- REQ-002: The system shall allow updating a hypothesis status only to one of `proposed`, `testing`, `confirmed`, `rejected`, `inconclusive`.

Sygnał i strategia

- REQ-010 (AC-3): When `Strategy.generate_signals` computes a signal for date `t`, the computation shall use only data with timestamp `<= t`.
- REQ-011 (AC-3): The momentum signal shall be a pure function of price history and the lookback parameter, with no hidden state between calls.

Silnik backtestu

- REQ-020 (AC-2): Given a synthetic price series with a known constant trend, when the vectorized engine runs a buy-and-hold strategy, the resulting Sharpe ratio shall match the analytically computed value within a defined numerical tolerance.
- REQ-021 (AC-4): When a backtest run completes, the system shall produce one `PortfolioSnapshot` per period covering the full requested date range, with no gaps.
- REQ-022 (AC-4): The engine shall compute CAGR, Sharpe, Sortino, Calmar and max drawdown from the run's own equity curve, not from an external library's implementation.
- REQ-023: Every `BacktestRun` shall record the git commit hash, strategy parameters and cost model used, so the run is reproducible.

Koszty

- REQ-030 (AC-5): The system shall provide at least two `CostModel` implementations: a fixed-bps naive model and a volatility-scaled realistic model.
- REQ-031 (AC-5): When the same `BacktestRun` inputs are evaluated under two different cost models, the report shall show the difference in net result attributable to costs.

Walidacja

- REQ-040 (AC-6): The `WalkForwardValidator` shall report metrics per rolling window in chronological order, in addition to the aggregate.
- REQ-041 (AC-7): The holdout date range and hypothesis parameters shall be written to a file and committed to git before any run reads data from that range for evaluation purposes.
- REQ-042 (AC-7): The final report shall present training-period results and holdout-period results as clearly separate sections, never merged into one aggregate.
- REQ-043 (AC-8): The permutation test shall run a configurable number of random reshuffles of the return series and report where the actual result falls in that distribution.

Ryzyko i reżimy

- REQ-050 (AC-9): The regime classifier shall label each period by realized volatility tercile, computed only from data available up to that period.
- REQ-051 (AC-9): Performance metrics shall be computable conditional on a given regime label.
- REQ-052 (AC-10): The stress test shall compute portfolio impact directly from position weights and a shock scenario, with no LLM or subjective judgment involved.

Atrybucja

- REQ-060 (AC-11): Every closed position shall produce one `Trade` record with entry/exit timestamp and price, size, side, gross and net P&L, costs, holding period and the regime label at entry.
- REQ-061 (AC-12): The trade ledger shall support grouping P&L by regime, by holding-period bucket and by calendar month.

Raportowanie

- REQ-070 (AC-13): The tear-sheet shall include an equity curve chart, a drawdown chart, a metrics table and a table of regime-conditional results, generated from a single completed `BacktestRun`.

Dziennik badawczy

- REQ-080 (AC-14): When a hypothesis reaches a terminal status (`confirmed`, `rejected` or `inconclusive`), a research log entry shall be written containing the hypothesis, methodology, key results and conclusion.
- REQ-090 (guardrail): The system shall not allow a hypothesis to be marked `confirmed` unless both a walk-forward validation result and a holdout evaluation exist for it.

## Business rules

Status hipotezy — przejścia dozwolone

| Z | Do | Warunek |
|---|---|---|
| `proposed` | `testing` | pierwszy `BacktestRun` uruchomiony |
| `testing` | `confirmed` | walk-forward zielony i wynik na zamrożonym holdout zgodny z kryterium sukcesu ustalonym przed jego odmrożeniem |
| `testing` | `rejected` | walk-forward albo holdout nie potwierdza tezy |
| `testing` | `inconclusive` | wynik niejednoznaczny (np. test permutacyjny nie odrzuca hipotezy zerowej, ale też jej nie potwierdza) |
| dowolny | dowolny wcześniejszy | niedozwolone bez nowego wpisu w dzienniku wyjaśniającego dlaczego |

Porównanie modeli kosztów

| Różnica netto między modelami | Interpretacja w raporcie |
|---|---|
| mała względem zmienności wyniku | strategia odporna na założenia kosztowe |
| duża, zmienia znak wyniku | wynik zależny od założeń kosztowych — raportowane jawnie jako ograniczenie |

## Data and validation

`Hypothesis`

| Field | Type | Required | Range or format |
|---|---|---|---|
| `id` | string | tak | unikalny |
| `title` | string | tak | – |
| `statement` | string | tak | jedno zdanie tezy |
| `status` | enum | tak | proposed/testing/confirmed/rejected/inconclusive |
| `created_at` | date | tak | – |

`Trade`

| Field | Type | Required | Range or format |
|---|---|---|---|
| `entry_ts`, `exit_ts` | date | tak | `exit_ts > entry_ts` |
| `side` | enum | tak | long/short |
| `qty` | float | tak | > 0 |
| `entry_price`, `exit_price` | float | tak | > 0 |
| `gross_pnl`, `net_pnl`, `costs` | float | tak | – |
| `regime_at_entry` | string | tak | zgodna z etykietami klasyfikatora reżimu |

`HoldoutConfig` (plik zamrożony)

| Field | Type | Required | Range or format |
|---|---|---|---|
| `start`, `end` | date | tak | poza zakresem treningowym |
| `frozen_at_commit` | string | tak | git SHA commita, w którym plik został zapisany |
| `success_criterion` | string | tak | jednoznaczne, ustalone przed odmrożeniem (np. „Sharpe netto > 0 i p-value testu permutacyjnego < 0.1") |

## Edge and error cases

- Sygnał momentum na instrumencie z krótszą historią niż lookback → brak sygnału dla tego okresu, nie błąd całego przebiegu.
- Zerowa zmienność w oknie klasyfikacji reżimu (rynek płaski) → etykieta reżimu jawnie `undefined`, nie wymuszony tercyl.
- Test permutacyjny na zbyt krótkiej serii (za mało obserwacji na wiarygodny rozkład) → wynik oznaczony jako `low_confidence`, nie ukrywany.
- Próba uruchomienia walidacji na holdout bez istniejącego pliku zamrożenia → błąd blokujący, nie ciche pominięcie.
- Dwie hipotezy o tym samym `id` → błąd przy rejestracji.
- Koszt transakcji większy niż brutto zysk pojedynczej transakcji → `net_pnl` ujemne, raportowane wprost, nie ucinane do zera.

## Non-functional requirements

- Performance: pełny przebieg wektorowy na koszyku MVP (rząd wielkości: kilkanaście instrumentów, kilka-kilkanaście lat danych dziennych) poniżej 1 minuty na maszynie deweloperskiej.
- Reproducibility: dwa uruchomienia z tym samym seedem i tymi samymi wejściami dają identyczny wynik liczbowy.
- Security and privacy: brak danych osobowych w tym epiku (dane rynkowe publiczne).

## Traceability

| AC | REQ |
|---|---|
| AC-1 | REQ-001 |
| AC-2 | REQ-020 |
| AC-3 | REQ-010, REQ-011 |
| AC-4 | REQ-021, REQ-022, REQ-023 |
| AC-5 | REQ-030, REQ-031 |
| AC-6 | REQ-040 |
| AC-7 | REQ-041, REQ-042 |
| AC-8 | REQ-043 |
| AC-9 | REQ-050, REQ-051 |
| AC-10 | REQ-052 |
| AC-11 | REQ-060 |
| AC-12 | REQ-061 |
| AC-13 | REQ-070 |
| AC-14 | REQ-080, REQ-090 |

## Open questions

| # | Question | Owner |
|---|---|---|
| 1 | Liczba powtórzeń testu permutacyjnego (koszt obliczeniowy vs moc testu) | Tomasz |
| 2 | Konkretny próg `success_criterion` dla holdout — ustalić przed zamrożeniem pliku, nie po | Tomasz |
