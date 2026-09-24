# q5-equities-cross-section - Specification

Status: Ready for dev
Owner role: BA
Upstream: 01-story.md

## Glossary

| Term | Meaning |
|---|---|
| Członkostwo | okres, w którym instrument należy do uniwersum: `start` włącznie, `end` włącznie albo otwarty |
| Uniwersum statyczne | uniwersum bez okresów członkostwa: każdy instrument jest członkiem każdego dnia (dzisiejsze `mvp-crypto`) |
| Ex-date | pierwszy dzień notowań bez prawa do dywidendy albo po splicie |
| Czynnik korekty | mnożnik cen sprzed ex-date: split `1 / ratio`, dywidenda `C₀ / (C₀ + D)` (C₀ — surowe zamknięcie z pierwszego dnia notowań od ex-date). Dzięki temu zwrot przez ex-date jest dokładnie zwrotem całkowitym `(C₀ + D) / C₋₁ − 1`; popularny czynnik `1 − D / C₋₁` daje `C₀ / (C₋₁ − D) − 1`, z błędem drugiego rzędu |
| Bar skorygowany | bar z cenami OHLC przemnożonymi przez iloczyn czynników wszystkich późniejszych ex-date; `unadjusted_close` trzyma surowe zamknięcie |
| Zwrot z delistingu | zwrot od ostatniego zamknięcia do wartości, którą akcjonariusz dostał przy zdjęciu z obrotu (odpowiednik DLRET w CRSP) |
| Miesiąc formacji | dla dnia t: ostatni dzień notowań poprzedniego miesiąca kalendarzowego, znany w dniu t bez patrzenia w przyszłość |
| Momentum 12-1 | zwrot od końca miesiąca m−13 do końca miesiąca m−2, gdy portfel trzymany jest w miesiącu m (pominięty ostatni miesiąc przed formacją) |

## Actors and permissions

| Actor | Action | Allowed |
|---|---|---|
| Strategia | widzi bary instrumentu, który w dniu sygnału nie jest członkiem uniwersum | nie (REQ-503) |
| Strategia | używa poziomu ceny skorygowanej (np. filtr ceny minimalnej) | nie — tylko `unadjusted_close` (reguły biznesowe) |
| Silnik | pomija zwrot z delistingu pozycji trzymanej do końca notowań | nie (REQ-523) |
| Kod epiku | uruchamia hipotezę akcyjną na danych rynkowych przed zamrożeniem definicji | nie (REQ-561) |

## Functional requirements (EARS)

Uniwersum point-in-time

- REQ-501 (AC-1): A universe shall optionally list membership periods; without any, it shall be static. With periods, every instrument shall have at least one, the periods of one instrument shall not overlap, and an instrument shall be a member on date t exactly when t falls in one of its periods.
- REQ-502 (AC-1): Universes shall be loaded by name from one file per universe (`quantlab/config/universes/<name>.yaml`); `mvp-crypto` shall keep its instruments and behaviour.
- REQ-503 (AC-1): Every run shall give the strategy only the bars of instruments that are members on the signal date; for a static universe the strategy shall receive the bars unchanged.
- REQ-504 (AC-1): An instrument's asset class shall be `crypto` or `equity`.

Corporate actions

- REQ-510 (AC-2): A corporate action shall be a split (ratio of new to old shares) or a cash dividend (amount per share), with its instrument and ex-date.
- REQ-511 (AC-2): Adjusting an instrument's bars shall multiply open, high, low and close of every bar dated before an ex-date by that action's factor, compounding across actions; volume shall be multiplied by the inverse of the split factors only; `unadjusted_close` shall keep the raw close; bars on or after the last ex-date shall keep their raw prices.
- REQ-512 (AC-2): The close-to-close return of adjusted bars across an ex-date shall equal the total return: `C₀ · ratio / C₋₁ − 1` for a split, `(C₀ + D) / C₋₁ − 1` for a dividend.
- REQ-513 (AC-2): An action with no bar before its ex-date, or with no bar on or after it, shall adjust nothing.
- REQ-514 (AC-2): Every data provider shall report its instruments' corporate actions (none for crypto), and every run shall adjust the bars it fetched with them; bars of an instrument without actions shall pass through unchanged.

Delisting

- REQ-520 (AC-3): A delisting shall have its instrument, its delisting date and its delisting return (unknown allowed).
- REQ-521 (AC-3): The data layer shall end a delisted instrument's bars with one bar on the delisting date, priced at the last close times one plus the delisting return, with zero volume; nothing after it.
- REQ-522 (AC-3): When the delisting return is unknown, the hypothesis's frozen `missing_delisting_return` shall apply, and the run shall report how many delistings used it.
- REQ-523 (AC-3): In both engines, a position held into the delisting date shall earn the delisting return and then close.
- REQ-524 (AC-3): A synthetic test shall measure the survivorship bias: the same strategy on the same synthetic universe with dead companies (and their delisting returns) against the survivors only, with the difference known in advance.

Rebalans

- REQ-530 (AC-4): The hypothesis definition shall choose a rebalance policy: `daily` (every period back to the target weights, today's rule) or `on_signal_change` (when the targets equal the previous decision's targets, hold the drifted positions without trading; otherwise trade to the targets).
- REQ-531 (AC-4): Both engines shall apply the policy through the same object and keep parity (`q2`) under both policies.
- REQ-532 (AC-4): `daily` shall be the default, and existing hypotheses shall give bit-identical results.

Strategia przekrojowa

- REQ-540 (AC-5): Cross-sectional momentum on date t shall rank by the return from the last close of month m−1−`formation_months` to the last close of month m−1−`skip_months`, where m is t's month, using adjusted closes and only bars dated ≤ t.
- REQ-541 (AC-5): An instrument shall enter the ranking only if it is a member on t, has closes at both ends of its formation window, and has an unadjusted close of at least `min_price` at the last close of month m−1.
- REQ-542 (AC-5): The portfolio shall be long the top ⌊n · `quantile`⌋ instruments and, when `long_short`, short the bottom as many, with ties broken by instrument id; with fewer than one instrument per leg there shall be no position.
- REQ-543 (AC-5): The strategy's signals shall stay the same within a month, so that with `on_signal_change` the engines trade only at formation or when a held instrument leaves the ranking.

Źródło danych

- REQ-550 (AC-6): An equities adapter shall implement `DataProvider` and a source of corporate actions and delistings; a provider decorator shall turn raw bars, actions and delistings into adjusted bars, so the runner does not branch on the asset class.
- REQ-551 (AC-6): The adapter shall throttle on our side, cache on disk and have an offline test on a recorded response; the source's terms shall be recorded in `docs/DATA-SOURCES.md` with the date checked.

Pre-rejestracja i wynik

- REQ-561 (AC-7): The hypothesis definition shall be committed before any run of it reads market data, with the answers to the story's open questions 1–5.
- REQ-562 (AC-7): The research log entry shall state the status, PSR and DSR with the trial count from the registry, the cost sensitivity, and the number of delistings and of default delisting returns in the run.

## Business rules

- Ceny skorygowane służą tylko do stosunków cen (zwroty, momentum). Każda reguła na poziomie ceny (np. cena minimalna) używa `unadjusted_close`. Korekta wstecz zmienia poziomy historycznych cen, gdy pojawi się nowa akcja korporacyjna, ale nie zmienia żadnego zwrotu — dlatego nie wprowadza look-ahead do sygnałów opartych na zwrotach.
- Status hipotezy — jak w `q1` (`concluded_status`). Liczba delistingów i założonych zwrotów z delistingu jest opisowa.

## Data and validation

`Membership` (w pliku uniwersum)

| Field | Type | Required | Range or format |
|---|---|---|---|
| `instrument_id` | string | tak | instrument z tego uniwersum |
| `start` | date | tak | ISO |
| `end` | date \| null | tak | ≥ `start`; null = trwa |

`CorporateAction`

| Field | Type | Required | Range or format |
|---|---|---|---|
| `instrument_id` | string | tak | |
| `ex_date` | date | tak | |
| `kind` | enum | tak | `split`, `cash_dividend` |
| `ratio` | float | dla `split` | > 0 (2.0 = split 2:1, 0.1 = scalenie 1:10) |
| `amount` | float | dla `cash_dividend` | > 0, w walucie notowań |

`Delisting`

| Field | Type | Required | Range or format |
|---|---|---|---|
| `instrument_id` | string | tak | |
| `date` | date | tak | po ostatnim barze notowań |
| `delisting_return` | float \| null | tak | > −1 albo = −1 (utrata całości); null = nieznany |

`CrossSectionalMomentumParameters` (w definicji hipotezy)

| Field | Type | Required | Range or format |
|---|---|---|---|
| `strategy` | enum | tak | `cross_sectional_momentum` |
| `formation_months` | int | tak | ≥ 2 |
| `skip_months` | int | tak | 0 ≤ `skip_months` < `formation_months` |
| `quantile` | float | tak | (0, 0.5] |
| `long_short` | bool | tak | |
| `min_price` | float | tak | ≥ 0 |
| `missing_delisting_return` | float | tak | ≥ −1 |
| `universe`, `cost_model` | — | tak | jak w pozostałych definicjach |

## Edge and error cases

- Instrument w pliku uniwersum bez okresu członkostwa, gdy inne go mają → błąd walidacji przy wczytaniu.
- Nakładające się okresy jednego instrumentu → błąd walidacji.
- Ex-date w dniu bez notowań → czynnik stosuje się do barów przed ex-date, jak zawsze.
- Split i dywidenda tego samego dnia → oba czynniki, iloczyn.
- Delisting bez wcześniejszych barów → brak baru delistingu (nic do zrealizowania).
- Delisting z datą nie po ostatnim barze → błąd walidacji (dane sprzeczne).
- Za mało instrumentów na kwantyl → brak pozycji w tym miesiącu (nie błąd).
- Pierwszy miesiąc bez pełnej historii formacji → brak pozycji.

## Non-functional requirements

- Performance: syntetyczny przebieg 500 instrumentów × 10 lat (wszystkie modele kosztów, walidacja, 10 000 permutacji) < 10 min i < 4 GB RAM na maszynie deweloperskiej — mierzone przy X5; przekroczenie → osobny slice z kolumnowym (numpy) przechowywaniem barów.
- Reproducibility: deterministycznie (ranking z rozstrzyganiem remisów po id).
- Compatibility: wyniki `momentum_v1`, `mean_reversion_v1` i `pairs_v1` bez zmian co do bitu (zrzut przed i po każdym slice'ie dotykającym silników lub danych).

## Traceability

| AC | REQ |
|---|---|
| AC-1 | REQ-501, REQ-502, REQ-503, REQ-504 |
| AC-2 | REQ-510, REQ-511, REQ-512, REQ-513, REQ-514 |
| AC-3 | REQ-520, REQ-521, REQ-522, REQ-523, REQ-524 |
| AC-4 | REQ-530, REQ-531, REQ-532 |
| AC-5 | REQ-540, REQ-541, REQ-542, REQ-543 |
| AC-6 | REQ-550, REQ-551 |
| AC-7 | REQ-561, REQ-562 |

## Open questions

| # | Question | Owner |
|---|---|---|
| 1 | Pytania 1–5 z [01-story.md](01-story.md) (źródło danych, uniwersum, parametry, zwrot z delistingu, okresy i kryterium) | Tomasz |
