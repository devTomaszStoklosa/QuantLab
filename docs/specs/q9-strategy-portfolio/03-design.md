# q9-strategy-portfolio - Design

Status: Ready for dev
Owner role: Architect
Upstream: 02-spec.md
ADRs: docs/adr/0002-dual-backtest-engine.md, docs/adr/0004-validation-first-frozen-holdout.md, docs/adr/0008-results-store-parquet-duckdb.md

## Context and constraints

- Silnik bierze od strategii sygnały, od sizera wagi docelowe (`Sizer.weights(signals)`), od polityki rebalansu decyzję, czy handlować; oba silniki dzielą te obiekty (parytet `q2`). Sygnał może nieść wielkość wagi (`Signal.weight`, `q4`).
- Definicja hipotezy buduje strategię, sizer i politykę rebalansu (`build_*`); runner nie rozgałęzia się po typie strategii (CLAUDE.md, zasada 9). Definicja zna tylko siebie: nie czyta innych plików.
- Walidatory, raport, magazyn wyników i aplikacja pracują na jednym `BacktestRun`; diagnostyka treningu (`TrainingDiagnostic`) przechodzi do magazynu i aplikacji bez zmiany schematu (tabela `diagnostics`).
- `q8` ma wzorzec: strategia, która w dniu decyzji uruchamia silnik wektorowy na barach sprzed tego dnia (`net_returns`) i zapamiętuje decyzję na okres.
- Holdouty składników `mean_reversion_v1`, `pairs_v1`, `momentum_select_v1` (2026-01-01 → 2026-08-31) są nieotwarte; `momentum_v1` otwarty (2024–2025).
- Zamrożone definicje i ich wyniki nie mogą się zmienić (zrzut bajt w bajt).

## Quality attribute scenarios

| Source | Stimulus | Response | Measure |
|---|---|---|---|
| Badacz | wagi na dzień rebalansu d | tylko bary sprzed d | test: bar z dnia d i późniejszy zmieniony po fakcie nie zmienia wag |
| Deweloper | portfel w obu silnikach | ten sam wynik | parytet < 1e-9 |
| Badacz | portfel jednego rękawu z wagą 1 | przebieg rękawu | ta sama krzywa kapitału (< 1e-12) |
| Badacz | dwa rękawy o przeciwnych pozycjach | pozycja netto 0, brak obrotu | test syntetyczny |
| Badacz | otwarcie holdoutu portfela przed składnikami | odmowa przed pobraniem danych | test CLI |
| Deweloper | hipotezy bez portfela | bez zmian | zrzut `momentum_v1`, `mean_reversion_v1`, `pairs_v1` bajt w bajt |

## Options

### Decyzja 1 — gdzie żyje portfel

- **A. Strategia `StrategyPortfolio` + sizer `CarriedWeights`.** Strategia pyta każdy rękaw o sygnały, jego sizer o wagi docelowe, mnoży przez wagę rękawu w bieżącym miesiącu i sumuje w pozycje netto, które oddaje jako sygnały z wagą; `CarriedWeights` przekazuje je silnikowi. Jeden `BacktestRun`: silnik handluje i kosztuje zmianę pozycji netto, a walidatory, raport, magazyn i aplikacja działają bez zmian.
- B. Średnia ważona krzywych kapitału rękawów — każdy rękaw płaci za swój obrót (brak kompensacji pozycji), wynik nie jest przebiegiem silnika (brak pozycji dla testu permutacyjnego, rejestru transakcji, parytetu).
- C. Runner składa pozycje rękawów — `if` po typie hipotezy w runnerze i osobna ścieżka dla silnika event-driven.

### Decyzja 2 — skąd zwroty rękawów do wag

- **A. Samodzielny przebieg rękawu zakotwiczony w `history_start`, na barach obciętych przed dniem rebalansu, raz na miesiąc.** Dokładnie zwroty ciągłego rękawu do d − 1; zajrzenie w przyszłość niemożliwe z konstrukcji (jak wybór w `q8`). Koszt: przebiegi rosnącej długości, ok. 72 × K w treningu.
- B. Jeden pełny przebieg rękawu, wycinany przed d — szybciej, ale brak przyszłości zależy tylko od przyczynowości silnika i strategii, bez drugiej linii obrony.
- C. Przebieg rękawu tylko na oknie — tanio, ale pierwszy dzień niesie koszt wejścia, którego ciągły rękaw nie płaci, a przez inną normalizację trzymanych wag różnią się też koszty kolejnych dni: zwroty nie są zwrotami rękawu.

### Decyzja 3 — jak portfel zna składniki

- **A. Definicja wymienia składniki po id; runner rozwiązuje je hakiem `resolve(load)` każdej definicji (domyślnie: ona sama).** Portfel dostaje zamrożone definicje składników wczytane tą samą ścieżką co każdy przebieg (commit, niezmienność), a runner nie wie, że ma do czynienia z portfelem.
- B. Kopie parametrów składników w pliku portfela — duplikacja, która może rozjechać się z zamrożonym oryginałem; walidacja zgodności i tak wymaga wczytania oryginałów.

### Decyzja 4 — gdzie trafia raport portfela

- **A. Diagnostyka treningu (`TrainingDiagnostic`)**: korelacje, wagi (średnia, min, max), mediana współczynnika dywersyfikacji, Sharpe reguł i rękawów. Tabela `diagnostics` magazynu, panel diagnostyki aplikacji i tear-sheet — bez zmiany schematu v3.
- B. Nowe tabele (historia wag na rebalans, macierz korelacji) — schemat v4, zmiany w API i aplikacji; wraca, jeśli historia wag okaże się potrzebna w aplikacji.

### Decyzja 5 — straż holdoutów składników

- **A. Hak definicji `holdout_prerequisites(start, end)`** (domyślnie pusty): portfel zwraca składniki, których holdout nachodzi na jego własny; `open-holdout` sprawdza ich zapisane otwarcia przed pobraniem danych.
- B. Ręczna dyscyplina opisana w dzienniku — sprzeczne z zasadą, że reguły walidacji egzekwuje kod.

## Trade-off matrix (1-5)

| Criterion | 1A | 1B | 1C | 2A | 2B | 2C | 3A | 3B | 4A | 4B | 5A | 5B |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Zgodność wsteczna (bit w bit) | 5 | 5 | 4 | 5 | 5 | 5 | 5 | 5 | 5 | 3 | 5 | 5 |
| Podstawialność, brak `if` po typie | 5 | 3 | 2 | 5 | 5 | 5 | 5 | 3 | 5 | 4 | 5 | — |
| Parytet silników i wierność kosztów | 5 | 1 | 3 | 5 | 5 | 2 | — | — | — | — | — | — |
| Ochrona przed zajrzeniem w przyszłość | 5 | 4 | 4 | 5 | 3 | 5 | 4 | 3 | — | — | 5 | 2 |
| Złożoność | 4 | 5 | 2 | 3 | 5 | 4 | 4 | 3 | 5 | 2 | 4 | 5 |

## Decision

Recommended: **1A, 2A, 3A, 4A, 5A**. Portfel to strategia pozycji netto (jeden przebieg silnika, koszty kompensacji, parytet), wagi rękawów pochodzą z ich ciągłych samodzielnych przebiegów na obciętej historii, składniki są rozwiązywane z ich zamrożonych definicji hakiem, który runner woła dla każdej hipotezy, raport idzie istniejącą diagnostyką, a otwarcie holdoutu portfela strzeże hak wymagań. Rezygnujemy z mieszania krzywych kapitału (1B) i z przebiegów rękawów tylko na oknie (2C). Revisit if: przebiegi 2A przekroczą budżet czasu (pamięć przebiegów rękawów między miesiącami) albo aplikacja będzie potrzebowała historii wag (4B, schemat v4).

## Diagrams

```
definition (components, allocation, window, history_start) ──resolve(load)──> frozen component definitions
   │
StrategyPortfolio(sleeves: strategy + sizer + rebalance + cost model, rule, window)
   rebalance day d (first trading day of a month):
      for each sleeve s: vectorized.run(sleeve s, bars < d, from history_start) -> last `window` net returns
      eligible(returns, min_window_days) -> rule.weights -> w_s        (memoized per month)
   as_of in month of d:
      t_s = sleeve s sizer(sleeve s signals(as_of));  net_i = Σ_s w_s · t_{s,i}
      -> signals with weight |net_i|  ─> CarriedWeights ─> vectorized / event-driven engine ─> BacktestRun

training report: sleeve correlations, weights (mean/min/max), median diversification ratio,
                 Sharpe of the portfolio under each rule and of each sleeve alone -> TrainingDiagnostic
open-holdout: holdout_prerequisites(start, end) -> components with overlapping holdouts -> records must exist
```

## Contracts

### Pliki

```
src/quantlab/portfolio/allocation.py           # AllocationRule, reguły, kwalifikacja, dywersyfikacja (P2)
src/quantlab/backtest/sizing.py                # CarriedWeights (P3)
src/quantlab/strategy/portfolio.py             # Sleeve, StrategyPortfolio, AllocationRecord (P3)
src/quantlab/research/definition.py            # resolve, holdout_prerequisites, StrategyPortfolioParameters (P4)
src/quantlab/cli.py                            # resolve przy wczytaniu, straż w open-holdout, raport (P4, P5)
src/quantlab/reporting/tear_sheet.py           # sekcja portfela (P5)
tests/test_results_fixture.py                  # demo_portfolio w syntetycznym magazynie (P6)
config/holdout/portfolio_v1.yaml               # zamrożona definicja (P7)
```

### Kontrakty (sygnatury poglądowe)

```python
# portfolio/allocation.py
class AllocationRule(Protocol):
    def weights(self, returns: np.ndarray, eligible: np.ndarray) -> np.ndarray: ...  # T x K -> K
ALLOCATION_RULES: dict[str, AllocationRule]  # equal_weight, inverse_volatility, risk_parity
def eligible_sleeves(returns: np.ndarray, min_days: int) -> np.ndarray: ...          # K bools
def diversification_ratio(weights: np.ndarray, covariance: np.ndarray) -> float: ...

# backtest/sizing.py
class CarriedWeights:  # Sizer: {instrument: +weight | -weight} from the signals
    def weights(self, signals: list[Signal]) -> dict[str, float]: ...

# strategy/portfolio.py
@dataclass(frozen=True)
class Sleeve:
    name: str
    build: Callable[[], Strategy]
    sizer: Sizer
    rebalance: RebalancePolicy
    cost_model: CostModel

class AllocationRecord(BaseModel):
    month: date                        # the rebalance day
    returns_days: dict[str, int]       # returns in each sleeve's window
    weights: dict[str, float]          # 0 for ineligible sleeves
    diversification_ratio: float | None

class StrategyPortfolio:               # Strategy
    def __init__(self, sleeves: list[Sleeve], rule: AllocationRule, window_days: int,
                 min_window_days: int, history_start: date): ...
    def allocation(self, bars, rebalance_day: date) -> AllocationRecord: ...   # memoized
    history: list[AllocationRecord]
    def generate_signals(self, bars, as_of) -> list[Signal]: ...

# research/definition.py
class StudyParametersBase:
    def resolve(self, load: Callable[[str], HoldoutConfig]) -> Self: ...        # default: self
    def holdout_prerequisites(self, start: date, end: date) -> list[str]: ...   # default: []
class StrategyPortfolioParameters(StudyParametersBase):
    strategy: Literal["strategy_portfolio"]
    components: list[str]; allocation: str; window_days: int; min_window_days: int
    history_start: date
```

## Rollout and rollback

1. **P1** dokumentacja: 01-story, 02-spec, 03-design, ROADMAP.
2. **P2** reguły alokacji (równe wagi, odwrotność zmienności, risk parity), kwalifikacja rękawów, współczynnik dywersyfikacji; testy na wartościach policzalnych z góry.
3. **P3** `CarriedWeights` i `StrategyPortfolio`: wagi z zakotwiczonych przebiegów rękawów na obciętej historii, pozycje netto; parytet silników, test zajrzenia w przyszłość, portfel jednego rękawu = rękaw, kompensacja przeciwnych pozycji; pomiar czasu.
4. **P4** definicja `strategy_portfolio`: hak `resolve`, walidacja składników, `fetch_start`, jedna konfiguracja, straż `open-holdout`.
5. **P5** raport: korelacje, wagi, współczynnik dywersyfikacji, Sharpe reguł i rękawów — terminal, tear-sheet, magazyn (diagnostyka).
6. **P6** `demo_portfolio` w syntetycznym magazynie; aplikacja pokazuje diagnostykę.
7. **P7** zamrożenie `portfolio_v1` (odpowiedzi 1–6) — osobny commit przed przebiegiem.
8. Lokalnie: przebieg treningowy; holdout po otwarciu holdoutów składników; wpis w dzienniku.

Rollback: `git revert` per slice; żaden slice nie zmienia plików w `config/holdout/` poza P7.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Zajrzenie w przyszłość w wagach (silnik wektorowy podaje wszystkie bary) | średnia | wysoki | przebiegi rękawów na barach jawnie obciętych przed dniem rebalansu; test ze zmienionym przyszłym barem |
| Otwarcie holdoutu portfela zdradza holdouty składników | średnia | wysoki | straż w `open-holdout` (REQ-930), test CLI |
| Czas przebiegów rękawów (72 × K, rosnąca historia; trzy reguły w raporcie) | średnia | średni | wybór wag raz na miesiąc, zapamiętany; rękaw z doborem (`q8`) zapamiętuje swoje wybory roczne; pomiar w P3 |
| Pozycja netto łamie regułę sizera rękawu przy brakującym barze | niska | niski | ograniczenie opisane w raporcie; na dziennych danych krypto luki są rzadkie |

## Handoff notes

- P2–P6 nie wymagają odpowiedzi na pytania z 01-story; P7 wymaga 1–6.
- Nie uruchamiaj portfela na danych rynkowych przed P7; holdout portfela dopiero po otwarciu holdoutów `mean_reversion_v1`, `pairs_v1` i `momentum_select_v1`.
- Po P7 opisowy DSR hipotez krypto spadnie przy ich następnym przebiegu (kolejna próba na tych danych) — jak po `q8`.
