# q2-event-driven-engine - Design

Status: Ready for dev
Owner role: Architect
Upstream: 02-spec.md
ADRs: docs/adr/0002-dual-backtest-engine.md, docs/adr/0003-float-not-decimal-core-engine.md, docs/adr/0004-validation-first-frozen-holdout.md

## Context and constraints

- Silnik wektorowy (`quantlab.backtest.vectorized`) ma test golden-master i jest silnikiem walidacji; jego wynik nie może się zmienić ani o bit.
- `BacktestRun` i `PortfolioSnapshot` mieszkają dziś w `backtest/vectorized/engine.py`, a importuje je 11 modułów i testów — kontrakt jest de facto wspólny, ale leży w jednym z silników ([ADR-0002](../../adr/0002-dual-backtest-engine.md) wymaga kontraktu wspólnego).
- Reguła wag (równe wagi po znaku sygnału) jest wpisana w pętlę silnika wektorowego; drugi silnik z własną kopią tej reguły mógłby się po cichu rozjechać.
- `Strategy.generate_signals(bars, as_of)` dostaje słownik list barów; strategie filtrują `ts <= as_of` same. `CostModel.cost(instrument_bars, as_of, traded_weight)` działa tak samo. Interfejsy zostają bez zmian.
- `PriceBar` ma `open` i `volume` (Binance: wolumen w jednostkach instrumentu), więc egzekucja na otwarciu i limit wolumenu nie wymagają nowych danych.
- Konsumenci snapshotów: metryki, porównanie kosztów, walk-forward i reżimy czytają tylko equity; rejestr transakcji, test permutacyjny i stress test czytają `positions` razy zwrot zamknięcie-zamknięcie. Pole `cash` czytają tylko testy silnika wektorowego.

## Quality attribute scenarios

| Source | Stimulus | Response | Measure |
|---|---|---|---|
| Deweloper | uruchamia oba silniki z egzekucją na zamknięciu | ten sam przebieg | każde pole snapshotu zgodne z tolerancją względną 1e-12 |
| Deweloper | pisze strategię, która czyta ostatni bar listy | strategia nie widzi przyszłości | test: wynik równy strategii uczciwej |
| Deweloper | dodaje nowy tryb egzekucji albo politykę wypełnień | nowa klasa, silnik bez zmian | 0 gałęzi `if`/`match` po typie w silniku |
| Recenzent | pyta, czy wynik przeżyje realną egzekucję | tabela porównania i kapitał graniczny | jedna komenda, < 1 min |

## Options — struktura silnika

### Option A - Ogólna kolejka zdarzeń z handlerami

Klasyczny układ (DataHandler → Strategy → Portfolio → ExecutionHandler): `deque` zdarzeń `MarketEvent`, `SignalEvent`, `OrderEvent`, `FillEvent`, tablica handlerów po typie zdarzenia. Kolejność w obrębie dnia wynika z kolejności rejestracji handlerów i z tego, kiedy kolejka jest opróżniana — żeby zlecenia nie liczyły się od pozycji sprzed zaległych wypełnień, zamknięcie dnia trzeba rozbić na kilka zdarzeń.

### Option B - Pętla symulacji po dniach z jawnymi fazami i odsłanianym strumieniem barów

`BarFeed` odsłania bary dzień po dniu i nie ma metody zwracającej bar z przyszłości. Pętla po dniach wywołuje w stałej kolejności: wypełnienia na otwarciu → wycena i snapshot → wypełnienia na zamknięciu → sygnały i nowe zlecenia. Zdarzeniami są otwarcie i zamknięcie baru; kolejką — zlecenia oczekujące w modelu egzekucji. Strategia, model egzekucji i model kosztów widzą rynek wyłącznie przez `BarFeed`.

### Option C - Silnik wektorowy z przesuniętymi cenami

Egzekucja na otwarciu t+1 przez podmianę cen w silniku wektorowym. Najtańsze, ale nie daje braku look-ahead z konstrukcji, zleceń, częściowych wypełnień ani rejestru zleceń.

## Trade-off matrix (1-5)

| Criterion | A | B | C |
|---|---|---|---|
| Brak look-ahead z konstrukcji (AC-2) | 5 | 5 — `BarFeed` nie ma przyszłości | 1 |
| Czytelna, deterministyczna kolejność faz (REQ-211) | 3 — rozproszona po handlerach | 5 — widoczna w 6 liniach pętli | 4 |
| Zlecenia, częściowe wypełnienia, rejestr (AC-4) | 5 | 5 | 1 |
| Rozszerzalność (dane śróddzienne, zlecenia z limitem ceny) | 5 | 3 | 1 |
| Złożoność | 2 | 4 | 5 |

## Decision

Recommended: **Option B**. Rezygnujemy z: ogólnej kolejki zdarzeń (A) — przy barach dziennych i jednym źródle zdarzeń daje tę samą semantykę co B przy większej ceremonii i kolejności rozproszonej po handlerach — oraz z przesuniętych cen (C), które nie spełniają AC-2 ani AC-4. Konsekwencja: własność „brak look-ahead" przenosi się ze strategii na `BarFeed` — także model egzekucji i model kosztów nie mogą sięgnąć po bar, którego pętla jeszcze nie odsłoniła. Revisit if: pojawią się dane śróddzienne albo zlecenia żyjące między barami (limit, stop) z wieloma źródłami zdarzeń — wtedy Option A.

Silnik wektorowy zostaje silnikiem walidacji i werdyktów; silnik event-driven służy do opisowego porównania założeń egzekucji.

## Diagrams

```
for ts in trading_dates(start..end):
    feed.advance(ts)                                   # odsłania bary z datą <= ts
    portfolio.apply(execution.due("open", feed))       # zlecenia z t-1 w trybie otwarcie t+1
    portfolio.snapshot(ts)                             # wycena po last_close, PortfolioSnapshot
    portfolio.apply(execution.due("close", feed))      # zlecenia z t-1 w trybie zamknięcie t+1
    if ts is not last:
        signals = strategy.generate_signals(feed.history(), ts)
        orders  = portfolio.orders(equal_weight_by_sign(active(signals)), ts)
        portfolio.apply(execution.submit(orders, feed))  # tryb zamknięcie t: wypełnia od razu

ExecutionModel:  CloseExecution | NextBarExecution(phase="open"|"close")
FillPolicy:      FullFill | VolumeParticipationFill(max_participation=0.025)
CostModel:       bez zmian (as_of = dzień decyzji, historia z feed)
wynik:           EventDrivenResult(run: BacktestRun, orders: list[OrderRecord])
```

Na ostatnim dniu przebiegu nie powstają zlecenia (jak w silniku wektorowym: nie ma okresu, który by niosły).

## Contracts

### Pliki

```
src/quantlab/backtest/
  run.py                       # BacktestRun, PortfolioSnapshot — kontrakt wspólny (E1, przeniesione)
  sizing.py                    # equal_weight_by_sign() — jedna reguła wag dla obu silników (E1)
  vectorized/engine.py         # importuje run.py i sizing.py; wynik bez zmian (E1)
  event_driven/
    feed.py                    # BarFeed (E2)
    orders.py                  # Order, Execution, OrderRecord (E2)
    fills.py                   # FillPolicy, FullFill (E2), VolumeParticipationFill (E4)
    execution.py               # ExecutionModel, CloseExecution (E2), NextBarExecution (E3)
    portfolio.py               # Portfolio: gotówka, ilości, zlecenia, koszty, snapshoty (E2)
    engine.py                  # run(...) -> EventDrivenResult (E2)
src/quantlab/reporting/
  engine_comparison.py         # total_costs(), capacity(), EngineComparisonRow (E4)
src/quantlab/cli.py            # quantlab compare-engines [HYPOTHESIS] (E5)
tests/backtest/event_driven/
  test_parity.py               # AC-1: oba silniki, 3 modele kosztów, obie strategie, long/short/flip
  test_feed.py                 # AC-2: brak przyszłości w feed; strategia „podglądająca"
  test_execution.py            # AC-3: wynik liczony ręcznie dla otwarcia i zamknięcia t+1; luki
  test_fills.py                # AC-4: limit wolumenu, anulowanie reszty
tests/reporting/test_engine_comparison.py
tests/test_cli.py              # compare-engines: odmowa bez commitu, brak danych po końcu treningu
```

### Kontrakty (sygnatury poglądowe)

```python
# backtest/sizing.py
def equal_weight_by_sign(signals: list[Signal]) -> dict[str, float]: ...   # tylko aktywne, bez "flat"

# backtest/event_driven/feed.py
class BarFeed:
    def __init__(self, bars: dict[str, list[PriceBar]]) -> None: ...
    def advance(self, ts: date) -> None: ...                  # daty tylko rosną
    def history(self) -> dict[str, list[PriceBar]]: ...       # bary z datą <= ts
    def bar(self, instrument_id: str) -> PriceBar | None: ...  # bar z bieżącego dnia
    def last_close(self, instrument_id: str) -> float | None: ...

# backtest/event_driven/orders.py
class Order(BaseModel):          # instrument_id, decision_ts, quantity, decision_equity
class Execution(BaseModel):      # order, filled_quantity, fill_ts, fill_price (None = anulowane)
class OrderRecord(BaseModel):    # pola z 02-spec „Data and validation"

# backtest/event_driven/fills.py
class FillPolicy(Protocol):
    def fillable(self, quantity: float, bar: PriceBar) -> float: ...   # ze znakiem, |wynik| <= |quantity|

# backtest/event_driven/execution.py
class ExecutionModel(Protocol):
    name: str
    def submit(self, orders: list[Order], feed: BarFeed, fills: FillPolicy) -> list[Execution]: ...
    def due(self, phase: Literal["open", "close"], feed: BarFeed, fills: FillPolicy) -> list[Execution]: ...

# backtest/event_driven/engine.py
class EventDrivenResult(BaseModel):
    run: BacktestRun
    orders: list[OrderRecord]

def run(strategy, cost_model, bars, universe_name, start, end, seed, git_sha,
        strategy_name, strategy_params, execution: ExecutionModel,
        fill_policy: FillPolicy = FullFill(), capital: float = 1.0) -> EventDrivenResult: ...

# reporting/engine_comparison.py
def total_costs(run: BacktestRun) -> float: ...   # suma kosztów w jednostkach kapitału początkowego
def capacity(orders: list[OrderRecord], bars, capital: float, max_participation: float) -> float | None: ...
```

### Wycena i koszty w portfelu (REQ-222, REQ-240, semantyka snapshotu)

- Chwila decyzji t: `E_s` = gotówka + Σ ilość × `last_close`. Ilość docelowa = waga × `E_s` / zamknięcie t; zlecenie = docelowa − trzymana (zamknięcie do zera daje dokładnie `−trzymana`).
- Wypełnienie: ilość += wypełniona; gotówka −= wypełniona × cena; waga wypełnienia = |wypełniona| × cena / `E_s`; koszt = `cost_model.cost(historia z feed, t, waga) × E_s`, odjęty od gotówki.
- Snapshot w `ts`: equity = wycena / kapitał; `positions` = bieżące ilości × zamknięcia z poprzedniej chwili decyzji / jej `E_s`; `costs` i `traded` — suma od poprzedniego snapshotu (koszty / equity poprzedniego snapshotu w walucie).

Przy egzekucji na zamknięciu `E_s` równa się equity snapshotu, więc ilość × cena / `E_s` odtwarza wagę docelową, a koszt / equity poprzedniego snapshotu odtwarza ułamek z modelu kosztów — stąd parytet z silnikiem wektorowym.

## Rollout and rollback

Każdy slice z zielonymi testami (`uv run ruff check . && uv run pytest -q`) przed następnym:

1. **E1** kontrakt wspólny: `backtest/run.py`, `backtest/sizing.py`, importy wszystkich konsumentów. Silnik wektorowy liczy przez `equal_weight_by_sign`; golden-master i testy silnika bez zmian.
2. **E2** rdzeń event-driven: `BarFeed`, `Order`/`Execution`/`OrderRecord`, `FullFill`, `CloseExecution`, `Portfolio`, `run`. Testy: parytet (AC-1) na kilku scenariuszach syntetycznych, strategia „podglądająca" (AC-2), konsumenci equity na przebiegu event-driven (AC-6).
3. **E3** `NextBarExecution` (otwarcie i zamknięcie t+1): testy z wynikiem policzonym ręcznie; luki w danych (anulowanie, wycena po ostatnim zamknięciu).
4. **E4** `VolumeParticipationFill`, `total_costs`, `capacity`.
5. **E5** `quantlab compare-engines [HYPOTHESIS]`: pięć konfiguracji, różnica parytetu, kapitał graniczny; odmowa bez zacommitowanej definicji; tylko zakres treningowy.
6. **E6** przebieg lokalny na danych Binance (zablokowany w środowisku chmurowym) z wynikiem w PR i uzupełnieniem wpisu `momentum_v1` w dzienniku (REQ-260). Dla `mean_reversion_v1` — dopiero po jej przebiegu treningowym M5.

Rollback: `git revert` per slice. E1 zmienia tylko miejsce kontraktu i jest weryfikowany istniejącymi testami; żaden slice nie dotyka zamrożonych plików ani zapisów otwarcia holdoutu.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| E1 cicho zmienia wynik silnika wektorowego | niska | wysoki | golden-master i testy silnika bez zmian; reguła wag przeniesiona 1:1 |
| Parytet psuje kolejność działań zmiennoprzecinkowych | średnia | niski | tolerancja względna 1e-12, test na długiej serii (setki dni) |
| Rejestr transakcji albo test permutacyjny użyty na przebiegu z egzekucją t+1 daje nieścisły P&L | średnia | średni | poza zakresem (01-story); porównanie używa tylko metryk z equity |
| Różnica wyjdzie pomijalna i epik wygląda na zbędny | wysoka | niski | to pełnoprawny wynik; tryb zamknięcie t+1 i kapitał graniczny i tak dają informację |
| Wolniejszy silnik zablokuje porównanie | niska | niski | NFR < 10 s na przebieg; bez walidacji permutacyjnej na event-driven |

## Handoff notes

- Zacznij od E1 i traktuj istniejący golden-master jako blokujący — kontrakt przenosi się bez zmiany zachowania.
- W E2 parytet jest bramką: dopóki oba silniki nie dają tego samego przebiegu przy tych samych założeniach, różnice w trybach t+1 nie mają interpretacji.
- Nie uruchamiaj porównania na danych holdoutu żadnej hipotezy; `compare-engines` czyta tylko zakres treningowy z definicji.
