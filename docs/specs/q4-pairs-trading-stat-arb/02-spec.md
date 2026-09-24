# q4-pairs-trading-stat-arb - Specification

Status: Ready for dev
Owner role: BA
Upstream: 01-story.md

## Glossary

| Term | Meaning |
|---|---|
| Noga | jeden z dwóch instrumentów pary: y (zależny) i x (objaśniający) |
| Współczynnik zabezpieczenia β | nachylenie regresji MNK log(y) = α + β·log(x) + ε na oknie formacji |
| Spread | reszta tej regresji: ε = log(y) − α − β·log(x) |
| z-score | spread z dnia t podzielony przez odchylenie standardowe reszt z okna formacji |
| Okno formacji | ostatnie N dni (z dniem t włącznie), na których estymowane są α, β i odchylenie spreadu |
| Test Engle'a-Grangera | test ADF na resztach regresji kointegrującej, z p-value MacKinnona; H₀: brak kointegracji |
| Półtrwanie | czas, w którym odchylenie spreadu od średniej maleje o połowę: −ln 2 / ln(1 + λ) z regresji Δε_t = c + λ·ε_{t−1} |
| Pozycja w spreadzie | +1 (long spread: long y, short x), −1 (short spread: short y, long x), 0 |

## Actors and permissions

| Actor | Action | Allowed |
|---|---|---|
| Strategia par | trzyma jedną nogę bez drugiej | nie (REQ-422) |
| Strategia par | używa danych z datą po dniu sygnału | nie (REQ-420) |
| Kod epiku | uruchamia `pairs_v1` na danych rynkowych przed zamrożeniem definicji | nie (REQ-440) |

## Functional requirements (EARS)

Kointegracja

- REQ-401 (AC-1): The system shall estimate β and α by OLS of log(y) on log(x) with a constant, and return the residual spread.
- REQ-402 (AC-1): The system shall run the Engle-Granger test on the pair and return its statistic, MacKinnon p-value and 1/5/10% critical values.
- REQ-403 (AC-1): The system shall estimate the spread's half-life from Δε_t = c + λ·ε_{t−1}; unless −1 < λ < 0 (λ ≥ 0: no mean reversion; λ ≤ −1: the spread overshoots its mean every period) the half-life shall be undefined.

Kontrakt wag

- REQ-410 (AC-2): A signal shall optionally carry a target weight magnitude; the direction keeps the sign.
- REQ-411 (AC-2): Both engines shall size positions through a `Sizer` chosen by the hypothesis definition; equal weight by sign shall stay the default and give bit-identical results for existing hypotheses.
- REQ-412 (AC-2): The pair sizer shall take the weights from the signals when both legs are tradable and give no position otherwise.

Sygnał pary

- REQ-420 (AC-3): When the pair strategy computes a position for date t, it shall use only bars with `ts <= t`, and only dates on which both legs have a bar.
- REQ-421 (AC-3): The position shall follow a state machine over the z-score path from the first date with a full formation window: flat → short spread when z ≥ entry, flat → long spread when z ≤ −entry; long spread → flat when z ≥ −exit, short spread → flat when z ≤ exit; an exit and an opposite entry may happen on the same date.
- REQ-422 (AC-3): The legs' weights shall be w_y = s / (1 + |β|) and w_x = −s·β / (1 + |β|) with s the spread position and β from the formation window ending at t, so gross exposure is 1.
- REQ-423 (AC-3): When the definition sets a cointegration filter, a new position shall open only if the Engle-Granger p-value on the formation window ending at t is below the filter's threshold; an open position shall close only by the exit rule.

Diagnostyka

- REQ-430 (AC-4): For a pair hypothesis, `quantlab run` shall print β, the Engle-Granger statistic and p-value and the spread's half-life over the training period, marked descriptive.

Pre-rejestracja i wynik

- REQ-440 (AC-5): `config/holdout/pairs_v1.yaml` shall be committed before any run of `pairs_v1` reads market data, with the answers to the story's open questions.
- REQ-441 (AC-6): The research log entry shall state the Engle-Granger result on the training period, PSR, DSR with the trial count from the registry, PBO over all trials on the same data, and the correlation of daily net returns with `momentum_v1` and `mean_reversion_v1`.

## Business rules

Status hipotezy — jak w `q1` (`concluded_status`). Test kointegracji na okresie treningowym jest opisowy: nie zmienia statusu, bo nie ma go w zamrożonym kryterium.

## Data and validation

`PairsSpreadParameters` (w definicji hipotezy)

| Field | Type | Required | Range or format |
|---|---|---|---|
| `strategy` | enum | tak | `pairs_spread` |
| `dependent`, `explanatory` | string | tak | różne instrumenty z uniwersum |
| `formation_days` | int | tak | ≥ 30 |
| `entry_z` | float | tak | > 0 |
| `exit_z` | float | tak | 0 ≤ `exit_z` < `entry_z` |
| `max_coint_p_value` | float \| null | tak | w (0, 1) albo null (bez filtra) |
| `universe`, `cost_model` | — | tak | jak w pozostałych definicjach |

## Edge and error cases

- Dzień, w którym któraś noga nie ma baru → brak sygnału na ten dzień; stan maszyny nie przechodzi przez ten dzień (liczy się tylko wspólne daty).
- Okno formacji z zerową wariancją log(x) albo reszt → z-score niezdefiniowany, pozycja zamknięta, stan wraca do 0.
- β ujemne → wzór wag bez zmian (obie nogi po tej samej stronie); dla BTC/ETH nie oczekiwane, ale nie błąd.
- Krótka historia (mniej niż okno formacji) → brak sygnału.
- Test Engle'a-Grangera niemożliwy do policzenia (np. za krótkie okno) → filtr nie pozwala otworzyć pozycji.

## Non-functional requirements

- Performance: pełny `quantlab run` hipotezy par (trzy modele kosztów, walidacja, 10 000 permutacji) poniżej 1 minuty na maszynie deweloperskiej, także z filtrem kointegracji.
- Reproducibility: deterministycznie; test kointegracji bez losowości.
- Environment: statsmodels i scipy z testem importu w `tests/test_environment.py`.

## Traceability

| AC | REQ |
|---|---|
| AC-1 | REQ-401, REQ-402, REQ-403 |
| AC-2 | REQ-410, REQ-411, REQ-412 |
| AC-3 | REQ-420, REQ-421, REQ-422, REQ-423 |
| AC-4 | REQ-430 |
| AC-5 | REQ-440 |
| AC-6 | REQ-441 |

## Open questions

| # | Question | Owner |
|---|---|---|
| 1 | Pytania 1–4 z [01-story.md](01-story.md) (para i parametry, filtr kointegracji, holdout, kryterium) blokują zamrożenie (P5) | Tomasz |
