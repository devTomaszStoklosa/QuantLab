# q5-equities-cross-section - Design

Status: Ready for dev
Owner role: Architect
Upstream: 02-spec.md
ADRs: docs/adr/0002-dual-backtest-engine.md, docs/adr/0004-validation-first-frozen-holdout.md, docs/adr/0007-binance-not-stooq-for-first-adapter.md

## Context and constraints

- Strategie dostają `bars: dict[str, list[PriceBar]]` i dzień sygnału; silniki liczą zwroty z `close` i pomijają instrument bez baru na którymkolwiek końcu okresu (wektorowy) albo bez baru w dniu decyzji (event-driven).
- `Universe` to statyczna lista z jednego pliku `quantlab/config/universe.yaml`; runner pobiera bary każdego instrumentu uniwersum (`_fetch_bars`), dostawca jest na sztywno `BinanceProvider`.
- Definicja hipotezy buduje strategię i `Sizer` (`build_strategy`, `build_sizer`); runner nie rozgałęzia się po typie strategii (CLAUDE.md, zasada 9).
- Oba silniki rebalansują co dzień do wag docelowych; obrót liczony względem wag po ruchu cen.
- Zamrożone definicje (`config/holdout/*.yaml`) nie mogą się zmienić; ich wyniki muszą zostać identyczne co do bitu.
- Maszyna deweloperska: 8 GB RAM. Bary to obiekty pydantic — setki spółek × lata dni to miliony obiektów.

## Quality attribute scenarios

| Source | Stimulus | Response | Measure |
|---|---|---|---|
| Deweloper | dodaje uniwersum z okresami członkostwa | strategia widzi tylko członków; krypto bez zmian | zrzut snapshotów trzech hipotez identyczny bajt w bajt |
| Badacz | spółka upada, gdy portfel ją trzyma | strata z delistingu w wyniku | test syntetyczny ze znanym zwrotem |
| Badacz | split 2:1 w dniu trzymania pozycji | brak fałszywego −50% | zwrot = zwrot ekonomiczny co do 1e-12 |
| Deweloper | nowa strategia miesięczna | silnik nie handluje dryfem | obrót = obrót z formacji, test na parze silników |
| Badacz | przebieg 500 spółek × 10 lat | kończy się na maszynie deweloperskiej | < 10 min, < 4 GB (pomiar w X5) |

## Options

### Decyzja 1 — gdzie filtrować członków uniwersum

- **A. Dekorator strategii `MembersOnly(strategy, universe)`, zakładany przez runner.** Strategia dostaje bary tylko członków w dniu sygnału; każda obecna i przyszła strategia dostaje filtr za darmo; dla uniwersum statycznego bary przechodzą nietknięte.
- B. Filtr w silnikach — dwa miejsca do utrzymania, a strategia przekrojowa i tak rankuje tylko członków, więc potrzebowałaby filtra drugi raz.
- C. Każda strategia sama — łatwo zapomnieć w następnej strategii.

### Decyzja 2 — gdzie korekty o corporate actions i delisting

- **A. Warstwa danych: czysta funkcja `with_events(bars, events, missing_delisting_return)` wołana przez runner zawsze, dla każdego dostawcy.** Źródło zdarzeń to protokół `EventSource.events(instrument, start, end)`; `BinanceProvider` zwraca pusty zbiór, więc bary krypto przechodzą nietknięte. Silniki zostają bez zmian: delisting to ostatni bar, zwrot całkowity to stosunek skorygowanych cen.
- B. Silniki rozumieją akcje korporacyjne i delistingi — zmiana w obu silnikach, ryzyko parytetu, a zwroty i tak liczy się z cen.
- C. Dostawca zwraca od razu bary skorygowane (dekorator dostawcy) — ale zwrot z delistingu przy braku danych to założenie hipotezy (zamrożone w definicji), nie dostawcy.

### Decyzja 3 — gdzie reguła rebalansu

- **A. Obiekt `RebalancePolicy` przekazywany obu silnikom, budowany przez definicję (`build_rebalance_policy()`, domyślnie `Daily`).** Silnik pyta politykę, czy przy tych samych celach trzymać pozycje po dryfie.
- B. Strategia zwraca „brak zmiany" — protokół `Strategy` się zmienia, a silnik i tak musi odróżnić „trzymaj" od „rebalansuj".
- C. `Sizer` z pamięcią poprzednich wag — `Sizer` nie zna wag po ruchu cen, więc nie może zwrócić „trzymaj dryf".

### Decyzja 4 — test istotności strategii przekrojowej (po X6)

Test permutacyjny `q1` tasuje kolejność dni wspólnie dla wszystkich instrumentów: pyta o timing. Momentum przekrojowe zarabia na selekcji (które spółki, nie kiedy), więc na `demo_xsmom` daje p = 0.99 przy Sharpe treningowym 1.8 (2.2 przed annualizacją 252 sesjami w X7a).

- **A. Losowe portfele z przekroju decyzji, symulowane macierzowo.** W każdej decyzji, w której przebieg handluje do nowych celów, N losowych portfeli dostaje te same wagi na instrumentach wylosowanych z przekroju decyzji i trzyma je z dryfem do następnej takiej decyzji. Wartość portfela w okresie trzymania to `1 + (G − 1) · w`, gdzie `G` to macierz wzrostu cen od dnia decyzji (dni × instrumenty przekroju), a `w` — wagi; dla N portfeli naraz to jedno mnożenie macierzy na okres trzymania. Harmonogram, wagi, dryf, delistingi i filtr ceny (przez przekrój) są wspólne z przebiegiem; losowy jest tylko wybór spółek.
- B. Tasowanie dni (`q1`) — mierzy timing, nie selekcję (p = 0.99 na `demo_xsmom`).
- C. Ponowne przebiegi silnika z losowym rankingiem — dokładne łącznie z kosztami, ale 10 000 przebiegów po ok. 12 s to ok. 33 h na maszynie deweloperskiej.
- D. Test t średniego spreadu long-short miesięcznych zwrotów (Fama-MacBeth) — parametryczny, zakłada normalność i niezależność miesięcy, ignoruje dryf i delistingi w trakcie miesiąca.

Przekrój decyzji to instrumenty, dla których strategia dała sygnał (także flat) — strategia przekrojowa daje więc flat każdemu instrumentowi z rankingu poza nogami. Walidator dostaje strategię, sizer i politykę rebalansu z definicji i odtwarza decyzje tak jak silnik wektorowy (te same wywołania), zamiast zapisywać przekrój w `BacktestRun` (zmiana kontraktu wyniku obu silników). Który test wchodzi do kryterium, zapisuje zamrożona definicja (`success_criterion.significance_test`, domyślnie `day_shuffle`, więc zamrożone definicje krypto nie zmieniają znaczenia).

### Decyzja 5 — kalendarz i źródło danych w pliku uniwersum

- **A. Plik uniwersum nazywa `source` i `periods_per_year`; runner bierze dostawcę z rejestru nazw, a annualizację i okna reżimu z uniwersum.** Rynek (i jego kalendarz) to własność uniwersum, nie hipotezy ani laboratorium.
- B. Kalendarz z klasy aktywów instrumentów — `if` po klasie aktywów w runnerze.
- C. Liczba okresów liczona z danych (dni z barami na rok) — zależy od okna i od luk w danych; ta sama hipoteza miałaby inną annualizację w treningu i w holdoucie.

### Decyzja 6 — data delistingu ze źródła bez kalendarza

Tiingo podaje tylko ostatni dzień z ceną. Dzień po nim bywa weekendem albo świętem; bar delistingu na dniu bez notowań innych instrumentów dodałby do przebiegu „dzień", w którym nikt poza nim nie ma ceny, a silnik wyłączyłby z tego okresu cały portfel.

- **A. Adapter podaje dzień po ostatniej cenie, warstwa danych przesuwa bar delistingu na pierwszy dzień notowań przebiegu od tej daty** (`with_events`, kalendarz z barów wszystkich instrumentów). Dane syntetyczne z datą delistingu w dniu notowań — bez zmian.
- B. Adapter pobiera kalendarz giełdy — zależność od biblioteki kalendarzy albo drugiego źródła.

## Trade-off matrix (1-5)

| Criterion | 1A | 1B | 1C | 2A | 2B | 2C | 3A | 3B | 3C |
|---|---|---|---|---|---|---|---|---|---|
| Zgodność wsteczna (bit w bit) | 5 | 4 | 5 | 5 | 3 | 5 | 5 | 3 | 4 |
| Podstawialność, brak `if` po typie | 5 | 4 | 2 | 5 | 3 | 4 | 5 | 3 | 2 |
| Parytet silników | 5 | 3 | 5 | 5 | 2 | 5 | 4 | 4 | 3 |
| Złożoność | 4 | 3 | 3 | 4 | 2 | 4 | 4 | 3 | 3 |

## Decision

**Korekta po X3 (2026-09-24):** test parytetu pokazał, że silniki nie mogą zostać całkiem bez zmian: silnik event-driven otwierał pozycję na barze delistingu (bar „handlowy" z ceną wartości delistingu), a wektorowy liczył koszt zamknięcia. Bar delistingu ma więc flagę `delisting`; oba silniki traktują go jako wypłatę gotówki bez zlecenia i kosztu, a event-driven nie wypełnia na nim zleceń. Poza tą jedną regułą decyzja 2A bez zmian.

Po decyzjach 1–5 z 01-story (2026-09-24): **4A, 5A, 6A** — uzasadnienia przy opcjach powyżej.

**Korekta po X8 (2026-09-24), warunek „Revisit if" spełniony:** przebieg w skali `xsmom_v1` (900 spółek × 16 lat) zajmował 6,0 GB, bo bar jako model pydantic to ok. 1 455 bajtów. Zamiast kolumnowych barów (zmiana interfejsu strategii i silników) `PriceBar` jest teraz zamrożonym dataclassem ze slotami: 298 bajtów, ten sam interfejs pól, 1,7 GB szczytowo. Kolumnowe bary wracają, gdyby uniwersum urosło kilkukrotnie.

Recommended: **1A, 2A, 3A**. Filtr członków jako dekorator strategii zakładany przez runner, korekty jako czysta funkcja warstwy danych nad protokołem źródła zdarzeń, rebalans jako polityka przekazywana obu silnikom. Rezygnujemy ze zmian w silnikach dla uniwersum i danych (1B, 2B) — każda taka zmiana to ryzyko parytetu — i z rozproszenia odpowiedzialności po strategiach (1C) i dostawcach (2C). Revisit if: pomiar w X5 przekroczy budżet pamięci — wtedy kolumnowe bary (numpy) za tym samym interfejsem strategii, osobny slice.

Uniwersa: jeden plik na uniwersum w `quantlab/config/universes/<name>.yaml`; plik uniwersum nazywa źródło danych (`source: binance`), a runner bierze dostawcę z rejestru nazw (słownik nazwa → fabryka), nie z `if` po klasie aktywów.

Strategia przekrojowa liczy ranking raz na miesiąc formacji i zapamiętuje go (klucz: miesiąc i członkowie), bo silnik woła ją co dzień.

## Diagrams

```
universe file (members, source) ──> Universe.members(t)
provider registry[source] ──> DataProvider.fetch (raw bars) + EventSource.events (actions, delisting)
                                   │
                         with_events(bars, events, missing_delisting_return)
                           ├─ adjust_bars: back-adjusted OHLC, split-adjusted volume, unadjusted_close
                           └─ delisting bar: last close × (1 + r), volume 0, nothing after
                                   │
definition.build_strategy() ──> MembersOnly(strategy, universe)   (runner, every path)
definition.build_sizer(), definition.build_rebalance_policy()
                                   │
vectorized.run / event_driven.run (policy: Daily | OnSignalChange)
```

## Contracts

### Pliki

```
src/quantlab/core/universe.py                  # Membership, Universe.members, load z universes/ (X1)
src/quantlab/config/universes/mvp-crypto.yaml   # przeniesiony universe.yaml, te same instrumenty (X1)
src/quantlab/strategy/members_only.py          # MembersOnly (X1)
src/quantlab/core/data/provider.py             # PriceBar.unadjusted_close, EventSource, InstrumentEvents (X2)
src/quantlab/core/data/corporate_actions.py    # CorporateAction, Delisting, adjust_bars, with_events (X2, X3)
src/quantlab/backtest/rebalance.py             # RebalancePolicy, Daily, OnSignalChange (X4)
src/quantlab/strategy/cross_sectional_momentum.py  # CrossSectionalMomentum (X5)
src/quantlab/research/definition.py            # build_rebalance_policy, CrossSectionalMomentumParameters (X4, X5)
src/quantlab/cli.py                            # rejestr dostawców, with_events, MembersOnly, polityka (X1–X4)
src/quantlab/validation/random_portfolio.py    # RandomPortfolioValidator (X7b)
src/quantlab/core/data/tiingo.py               # TiingoProvider: ceny, dywidendy, splity, delistingi (X7c)
src/quantlab/core/sp500.py                     # skład S&P 500 z Wikipedii: parser tabel, odtwarzanie wstecz (X7d)
src/quantlab/config/universes/sp500-renames.yaml  # zmiany tickerów (stary → Tiingo), uzupełniane z raportu budowy (X7d)
config/holdout/xsmom_v1.yaml                   # zamrożona definicja (X8)
```

### Kontrakty (sygnatury poglądowe)

```python
# core/universe.py
class Membership(BaseModel):
    instrument_id: str; start: date; end: date | None
class Universe(BaseModel):
    name: str; asof_date: date; source: str; instruments: list[Instrument]; memberships: list[Membership] = []
    def members(self, as_of: date) -> set[str]: ...
    def is_static(self) -> bool: ...

# core/data/corporate_actions.py
class CorporateAction(BaseModel):
    instrument_id: str; ex_date: date; kind: Literal["split", "cash_dividend"]; ratio: float | None; amount: float | None
class Delisting(BaseModel):
    instrument_id: str; date: date; delisting_return: float | None
class InstrumentEvents(BaseModel):
    actions: list[CorporateAction] = []; delisting: Delisting | None = None
def adjust_bars(bars: list[PriceBar], actions: list[CorporateAction]) -> list[PriceBar]: ...
def with_events(bars, events: dict[str, InstrumentEvents], missing_delisting_return: float | None) -> dict[str, list[PriceBar]]: ...

# backtest/rebalance.py
class RebalancePolicy(Protocol):
    def holds(self, previous_targets: dict[str, float] | None, targets: dict[str, float]) -> bool: ...

# strategy/members_only.py
class MembersOnly:
    def __init__(self, strategy: Strategy, universe: Universe) -> None: ...
    def generate_signals(self, bars, as_of) -> list[Signal]: ...
```

## Rollout and rollback

Każdy slice z zielonymi bramkami i zrzutem wyników trzech zamrożonych hipotez (na danych syntetycznych) identycznym przed i po:

1. **X1** point-in-time uniwersum: `Membership`, `members`, pliki per uniwersum, `source`, klasa `equity`, `MembersOnly` w każdej ścieżce runnera.
2. **X2** corporate actions: `unadjusted_close`, `CorporateAction`, `adjust_bars`, `EventSource` (Binance: pusto), `with_events` w runnerze.
3. **X3** delisting: bar delistingu, `missing_delisting_return` w definicji, raport liczby delistingów, test survivorship bias.
4. **X4** polityka rebalansu w obu silnikach, parytet dla obu polityk.
5. **X5** `CrossSectionalMomentum` i jej parametry; pomiar czasu i pamięci na syntetycznym uniwersum 500 × 10 lat.
6. **X6** hipoteza demonstracyjna `demo_xsmom` w syntetycznym magazynie wyników (`q7`), żeby UI pokazał akcje przekrojowo.
7. **X7** adapter wybranego źródła (decyzje 1–2), w czterech częściach, wszystkie na danych syntetycznych i nagranych odpowiedziach:
   - **X7a** `source` i `periods_per_year` w pliku uniwersum, rejestr dostawców, pobieranie tylko członków okna, proxy rynku bez członkostwa, przesunięcie baru delistingu na dzień notowań; zrzut krypto bez zmian.
   - **X7b** test losowych portfeli, sygnały flat w momentum przekrojowym, `significance_test` w kryterium, magazyn wyników i UI.
   - **X7c** `TiingoProvider` z cache i throttlingiem, test na nagranej odpowiedzi.
   - **X7d** budowa uniwersum `sp500` z Wikipedii (`quantlab build-universe`), raport niespójności, pokrycie cenami w `run` (REQ-554); plik uniwersum budowany i commitowany lokalnie.
8. **X8** zamrożenie definicji (decyzje 3–5 i pytania 6–7) — osobny commit przed jakimkolwiek przebiegiem na danych.
9. **X9** przebieg treningowy lokalnie, **X10** otwarcie holdoutu, **X11** wpis w dzienniku.

Rollback: `git revert` per slice; żaden slice nie zmienia plików w `config/holdout/`.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Pamięć: miliony obiektów `PriceBar` | średnia | wysoki | pomiar w X5; kolumnowe bary za tym samym interfejsem jako osobny slice |
| Brak delistingów w darmowym źródle | średnia | wysoki | jawnie w 01-story; wynik opisany jako obciążony |
| Zmiana wyników krypto przez uniwersum/dane/silniki | niska | wysoki | zrzut bajt w bajt przed i po; bary krypto przechodzą nietknięte (ten sam obiekt) |
| Look-ahead przez korektę wstecz | niska | wysoki | reguła: poziom ceny tylko z `unadjusted_close`; test, że ranking nie zależy od przyszłej dywidendy |
| Wolna strategia przekrojowa (ranking co dzień) | wysoka | średni | ranking raz na miesiąc formacji, zapamiętany |
| Limity darmowego tieru Tiingo przy ok. 1 050 tickerach S&P 500 z lat 2004–2025 | wysoka | średni | cache odpowiedzi, wznawianie pobierania, konfigurowalny odstęp żądań; ewentualnie miesiąc płatnego tieru |
| Ponownie użyte i zmienione tickery (Wikipedia pisze ticker z dnia zmiany, Tiingo — dzisiejszy) | wysoka | wysoki | mapa zmian tickerów w repo, raport niespójności budowy, raport pokrycia cenami w `run` |
| Niekompletna tabela zmian w Wikipedii | średnia | średni | raport niespójności (m.in. data dodania bieżących członków vs odtworzona); wynik opisany z tym ograniczeniem |

## Handoff notes

- X1–X6 nie wymagają odpowiedzi na pytania z 01-story; X7 wymaga 1–2, X8 wymaga 3–7 (wszystkie rozstrzygnięte 2026-09-24).
- Plik `sp500.yaml` powstaje lokalnie (`quantlab build-universe`) i jest commitowany przed pierwszym przebiegiem; poprawki w `sp500-renames.yaml` wynikają wyłącznie z raportu budowy, zanim jakikolwiek przebieg przeczyta ceny.
- Nie uruchamiaj żadnej hipotezy akcyjnej na danych rynkowych przed X8.
