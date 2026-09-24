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
| Okresy w roku | liczba dni notowań w roku kalendarzowym na rynku uniwersum: 365 dla krypto, 252 dla akcji amerykańskich; mnożnik annualizacji każdej statystyki |
| Przekrój decyzji | instrumenty, dla których strategia dała w dniu decyzji jakikolwiek sygnał (long, short albo flat) i które mają cenę na obu końcach następnego okresu — to, spośród czego strategia wybierała |
| Losowy portfel | wagi docelowe decyzji przypisane instrumentom wylosowanym bez zwracania z przekroju tej decyzji |

## Actors and permissions

| Actor | Action | Allowed |
|---|---|---|
| Strategia | widzi bary instrumentu, który w dniu sygnału nie jest członkiem uniwersum | nie (REQ-503) |
| Strategia | używa poziomu ceny skorygowanej (np. filtr ceny minimalnej) | nie — tylko `unadjusted_close` (reguły biznesowe) |
| Silnik | pomija zwrot z delistingu pozycji trzymanej do końca notowań | nie (REQ-523) |
| Kod epiku | uruchamia hipotezę akcyjną na danych rynkowych przed zamrożeniem definicji | nie (REQ-561) |

## Functional requirements (EARS)

Uniwersum point-in-time

- REQ-501 (AC-1): A universe shall optionally list membership periods; without any, it shall be static. With periods, every instrument except the market proxy shall have at least one, the periods of one instrument shall not overlap, and an instrument shall be a member on date t exactly when t falls in one of its periods. A market proxy without periods is never a member: it sets regimes and the stress scenario (REQ-526), and no strategy sees or trades it.
- REQ-502 (AC-1): Universes shall be loaded by name from one file per universe (`quantlab/config/universes/<name>.yaml`); `mvp-crypto` shall keep its instruments and behaviour.
- REQ-503 (AC-1): Every run shall give the strategy only the bars of instruments that are members on the signal date; for a static universe the strategy shall receive the bars unchanged.
- REQ-504 (AC-1): An instrument's asset class shall be `crypto` or `equity`.
- REQ-505 (AC-1): A run shall fetch only the instruments that are members on some date of its window, and the market proxy, each from the start of the hypothesis's warm-up; a static universe fetches all its instruments, as today.
- REQ-506 (AC-1, AC-6): A universe shall name its data source and its periods per year. The runner shall take the data provider from a registry of source names, and an unknown name shall stop the run before any fetch. Every annualized statistic of a run (metrics, walk-forward, significance tests, regimes, multiple testing, engine comparison) shall use the universe's periods per year, and the regime classifier shall use one month (`round(n / 12)`) and one year (`n`) of them; `mvp-crypto` names `binance` and 365, so its results stay bit-identical.

Corporate actions

- REQ-510 (AC-2): A corporate action shall be a split (ratio of new to old shares) or a cash dividend (amount per share), with its instrument and ex-date.
- REQ-511 (AC-2): Adjusting an instrument's bars shall multiply open, high, low and close of every bar dated before an ex-date by that action's factor, compounding across actions; volume shall be multiplied by the inverse of the split factors only; `unadjusted_close` shall keep the raw close; bars on or after the last ex-date shall keep their raw prices.
- REQ-512 (AC-2): The close-to-close return of adjusted bars across an ex-date shall equal the total return: `C₀ · ratio / C₋₁ − 1` for a split, `(C₀ + D) / C₋₁ − 1` for a dividend.
- REQ-513 (AC-2): An action with no bar before its ex-date, or with no bar on or after it, shall adjust nothing.
- REQ-514 (AC-2): Every data provider shall report its instruments' corporate actions (none for crypto), and every run shall adjust the bars it fetched with them; bars of an instrument without actions shall pass through unchanged.

Delisting

- REQ-520 (AC-3): A delisting shall have its instrument, its delisting date and its delisting return (unknown allowed).
- REQ-521 (AC-3): The data layer shall end a delisted instrument's bars with one bar, priced at the last close times one plus the delisting return, with zero volume; nothing after it. The bar shall be dated on the first date on or after the delisting date on which any instrument of the run has a bar (the market's next session, since a source may give only the day after the last price), or on the delisting date itself when there is none.
- REQ-522 (AC-3): When the delisting return is unknown, the hypothesis's frozen `missing_delisting_return` shall apply, and the run shall report how many delistings used it.
- REQ-523 (AC-3): In both engines, a position held into the delisting date shall earn the delisting return and then turn into cash at that value, without an order or a cost; no order shall fill against a delisting bar and no position shall open on it.
- REQ-525 (AC-3): The permutation test shall accept instruments that start or stop trading within the run: a shuffle pairing a position with a day its instrument did not trade shall earn nothing, and the count of such cells shall be reported; a held position without prices at both ends of its period shall be an error.
- REQ-526 (AC-3): A universe shall name its market proxy (the instrument whose volatility sets the regimes and whose worst day is the stress scenario); `quantlab run` shall refuse a universe without one, and `mvp-crypto` shall name `btc-usdt`. An instrument without prices on the proxy's worst day (not yet listed or already delisted) shall move with the proxy in that scenario, and the scenario shall say how many did.
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
- REQ-552 (AC-6): The Tiingo adapter shall read raw daily prices, cash dividends (`divCash` on the ex-date) and splits (`splitFactor` other than 1 on the ex-date) from the prices endpoint, and shall report a delisting when the ticker's last price date in the metadata endpoint falls inside the requested range: dated the day after that last price, with an unknown delisting return. The key shall come from the `TIINGO_API_KEY` environment variable, the spacing of requests shall be configurable, and responses shall be cached on disk so an interrupted download resumes.
- REQ-553 (AC-6): The S&P 500 universe shall be built from one pinned revision of Wikipedia's *List of S&P 500 companies* (the last revision before a fixed timestamp): today's constituents walked back through the table of changes, each change effective at its date (an added ticker is a member from it, a removed one until the day before). Tickers shall be spelled as Tiingo spells them (a class suffix after a hyphen, `BRK-B`), renames shall come from a committed map, and SPY shall be the market proxy without membership. The builder shall report every inconsistency it finds — an addition whose ticker is not in the index afterwards (typically a rename missing from the map), a removal whose ticker still is, a current constituent whose date added disagrees with the start of its current period, a ticker with more than one period (possibly two companies), a row without a readable date — and the file shall carry the revision id and the CC BY-SA 4.0 attribution. Memberships shall not be reconstructed before 2000-01-01 (the table's reliable part); a member then is a member from that date.
- REQ-554 (AC-6): `quantlab run` on a point-in-time universe shall report the price coverage of its members: member-days with a price over member-days in the window, and the members without any price (the survivorship risk the source leaves).

Pre-rejestracja i wynik

- REQ-561 (AC-7): The hypothesis definition shall be committed before any run of it reads market data, with the answers to the story's open questions 1–7.
- REQ-562 (AC-7): The research log entry shall state the status, PSR and DSR with the trial count from the registry, the cost sensitivity, the number of delistings and of default delisting returns in the run, the result under a −30% delisting return, and the price coverage of the universe.
- REQ-566 (AC-3, AC-7): When a run's data has delistings at the definition's assumed return and that assumption is not −30%, `quantlab run` shall also report the realistic-cost Sharpe and CAGR with −30% (Shumway 1997) assumed instead, as a descriptive sensitivity.

Test istotności

- REQ-563 (AC-7): The success criterion shall name its significance test: `day_shuffle` (the permutation test of `q1`, the default, so every frozen definition keeps its meaning) or `random_portfolio`. `quantlab run` and `quantlab open-holdout` shall apply the named test through a registry of names, and the results store shall record which test gave the p-value.
- REQ-564 (AC-7): The random-portfolio test shall take every decision at which the run trades to new targets (its rebalance policy does not hold) and, in each of N random portfolios, assign the decision's target weights to instruments drawn without replacement from the decision's cross-section, held and drifting with prices until the next such decision; an instrument without a price later in the holding keeps its last price (a delisting included). The statistic shall be the annualized Sharpe of gross daily returns, computed by the same construction for the actual assignment; p = (1 + #{random ≥ actual}) / (1 + N), drawn from the run's seed.
- REQ-565 (AC-5, AC-7): Cross-sectional momentum shall give a flat signal for every ranked instrument in neither leg, so that its cross-section is its ranking; weights, trades and results shall not change.

## Business rules

- Ceny skorygowane służą tylko do stosunków cen (zwroty, momentum). Każda reguła na poziomie ceny (np. cena minimalna) używa `unadjusted_close`. Korekta wstecz zmienia poziomy historycznych cen, gdy pojawi się nowa akcja korporacyjna, ale nie zmienia żadnego zwrotu — dlatego nie wprowadza look-ahead do sygnałów opartych na zwrotach.
- Status hipotezy — jak w `q1` (`concluded_status`). Liczba delistingów i założonych zwrotów z delistingu jest opisowa.
- Dwa testy istotności odpowiadają na różne pytania. Tasowanie dni (`day_shuffle`) pyta o timing: czy pozycje trafiły w dni, które po nich nastąpiły. Losowe portfele (`random_portfolio`) pytają o selekcję: czy wybrane instrumenty zarobiły więcej niż wylosowane z tego samego przekroju, przy tym samym harmonogramie, tych samych wagach i tym samym trzymaniu. Strategia przekrojowa z trwałymi różnicami zwrotów między spółkami nie ma timingu do wykrycia (na `demo_xsmom` tasowanie daje p = 0.99 przy Sharpe treningowym 1.8), więc jej kryterium używa losowych portfeli. Który test wchodzi do kryterium, zapisuje zamrożona definicja.
- Oba testy liczą Sharpe brutto: koszty ocenia porównanie modeli kosztów i netto-połowa kryterium.

## Data and validation

`Universe` (plik uniwersum)

| Field | Type | Required | Range or format |
|---|---|---|---|
| `source` | string | tak | nazwa z rejestru dostawców: `binance`, `tiingo` |
| `periods_per_year` | int | tak | > 0; 365 krypto, 252 akcje USA |
| `market_proxy` | string \| null | nie | instrument tego uniwersum; w uniwersum point-in-time może nie mieć członkostwa |

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

`SuccessCriterion.significance_test` (w definicji hipotezy)

| Field | Type | Required | Range or format |
|---|---|---|---|
| `significance_test` | enum | nie | `day_shuffle` (domyślnie) albo `random_portfolio` |

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
- Nieznane `source` w pliku uniwersum → błąd przed pobraniem danych.
- Decyzja bez wag docelowych (brak pozycji) → wszystkie losowe portfele mają w tym okresie zwrot 0.
- Losowy portfel trzyma instrument, który w trakcie trzymania przestaje być notowany → jego wartość zostaje na ostatniej cenie (po delistingu: na wartości delistingu), jak gotówka.
- Ticker bez cen w Tiingo (np. ponownie użyty przez inną spółkę) → brak barów; raport pokrycia (REQ-554) go wymienia.
- Zmiana w tabeli Wikipedii sprzeczna z odtwarzanym składem → ostrzeżenie w raporcie budowy, nie ciche pominięcie.

## Non-functional requirements

- Performance: syntetyczny przebieg 500 instrumentów × 10 lat (wszystkie modele kosztów, walidacja, 10 000 permutacji) < 10 min i < 4 GB RAM na maszynie deweloperskiej — mierzone przy X5; przekroczenie → osobny slice z kolumnowym (numpy) przechowywaniem barów. **Pomiar X5 (2026-09-24, środowisko chmurowe):** 500 spółek × 2 608 dni roboczych, momentum 12-1, decyle long-short: trzy przebiegi wektorowe 35 s, walk-forward 11 s, 10 000 permutacji 22 s, reżimy i rejestr transakcji 2 s — łącznie 69 s, szczytowo 2,2 GB RSS. Na i5-2500K spodziewane 2–3× dłużej; pamięć w budżecie. **Pomiar X7b (2026-09-24):** ten sam przebieg z rotacją składu (co piąta spółka opuszcza uniwersum w innym dniu) i sygnałami flat dla całego rankingu: trzy przebiegi wektorowe 41 s (sygnały flat +20%), test losowych portfeli ×10 000 — 15 s (115 decyzji, średnio 446 spółek w przekroju), łącznie 91 s, szczytowo 2,2 GB.
- Kalibracja testu losowych portfeli (X7b): na 60 syntetycznych rynkach bez przewagi (błądzenie losowe, 40 spółek, 4 lata, momentum 12-1, 400 portfeli) średnie p = 0.455, p < 0.1 w 8.3% przypadków, rozkład p bliski jednostajnemu — test nie zawyża istotności.
- Reproducibility: deterministycznie (ranking z rozstrzyganiem remisów po id).
- Compatibility: wyniki `momentum_v1`, `mean_reversion_v1` i `pairs_v1` bez zmian co do bitu (zrzut przed i po każdym slice'ie dotykającym silników lub danych).

## Traceability

| AC | REQ |
|---|---|
| AC-1 | REQ-501, REQ-502, REQ-503, REQ-504, REQ-505, REQ-506 |
| AC-2 | REQ-510, REQ-511, REQ-512, REQ-513, REQ-514 |
| AC-3 | REQ-520, REQ-521, REQ-522, REQ-523, REQ-524, REQ-525, REQ-526, REQ-566 |
| AC-4 | REQ-530, REQ-531, REQ-532 |
| AC-5 | REQ-540, REQ-541, REQ-542, REQ-543, REQ-565 |
| AC-6 | REQ-506, REQ-550, REQ-551, REQ-552, REQ-553, REQ-554 |
| AC-7 | REQ-561, REQ-562, REQ-563, REQ-564, REQ-565, REQ-566 |

## Open questions

| # | Question | Owner |
|---|---|---|
| — | Brak: pytania 1–7 z [01-story.md](01-story.md) rozstrzygnięte 2026-09-24 | — |
