# q1-momentum-research-mvp - Design

Status: Ready for dev
Owner role: Architect
Upstream: 02-spec.md
ADRs: docs/adr/0002-dual-backtest-engine.md, docs/adr/0003-float-not-decimal-core-engine.md, docs/adr/0004-validation-first-frozen-holdout.md, docs/adr/0005-descriptive-reports-no-investment-advice.md

## Context and constraints

- Jeden deweloper; kod ma być czytelny i dobrze przetestowany bardziej niż maksymalnie ogólny.
- Silnik: wyłącznie wektorowy w tym epiku ([ADR-0002](../../adr/0002-dual-backtest-engine.md)); event-driven to `q2`.
- Ceny/zwroty: `float64`, nie `Decimal` ([ADR-0003](../../adr/0003-float-not-decimal-core-engine.md)).
- Maszyna bez AVX2, 8 GB RAM, bez GPU — żadna metoda walidacji nie może zakładać GPU ani wielogodzinnego treningu lokalnie.
- Dane z `lab-foundation`: `PriceBar`, `Universe`, storage DuckDB/Parquet już gotowe.

## Quality attribute scenarios

| Source | Stimulus | Response | Measure |
|---|---|---|---|
| Deweloper | zmienia parametr lookback i uruchamia ponownie | pełny wynik (metryki + walidacja) | jedna komenda, < 1 min |
| Deweloper | próbuje oznaczyć hipotezę `confirmed` bez holdout | system odmawia | REQ-090 wymuszony w kodzie, nie tylko w dokumentacji |
| Recenzent (przyszły pracodawca) | czyta `docs/RESEARCH_LOG.md` | rozumie hipotezę, metodę i wniosek bez czytania kodu | jeden wpis, samowystarczalny |
| Deweloper | uruchamia dwa razy ten sam przebieg | identyczny wynik liczbowy | deterministyczny seed |

## Options — sygnał i konstrukcja strategii

### Option A - Cross-sectional ranking momentum

Ranking instrumentów w koszyku po zwrocie N-okresowym, długo top-decyl / krótko bottom-decyl (albo long-only top-K przy koszyku par kryptowalutowych).

### Option B - Time-series momentum (per-instrument)

Każdy instrument osobno: długo jeśli własny zwrot N-okresowy dodatni, krótko/płasko jeśli ujemny (Moskowitz/Ooi/Pedersen 2012) — nie zależy od rankingu względem innych instrumentów w koszyku.

### Option C - Dual momentum (łączy A i B)

Filtr time-series (czy w ogóle wchodzić) plus ranking cross-sectional (co wybrać spośród kwalifikujących się).

## Trade-off matrix (1-5)

| Criterion | A | B | C |
|---|---|---|---|
| Scenario fit (prostota pierwszej hipotezy) | 3 | 5 — najprostsza, jeden instrument na raz, łatwa do zweryfikowania golden-master | 3 |
| Complexity | 3 | 5 — najmniej ruchomych części | 2 |
| Literatura/wiarygodność | 4 | 5 — bezpośrednio odwzorowuje znaną publikację | 4 |
| Delivery time | 3 | 5 | 2 |
| Rozszerzalność (przyszłe q3/q4) | 4 | 4 — łatwo dodać drugą strategię obok, nie zamiast | 3 |

## Decision

Recommended: **Option B (time-series momentum per-instrument)**. Rezygnujemy z: cross-sectional ranking (mniej bezpośrednie odwzorowanie znanej publikacji, więcej ruchomych części na pierwszą hipotezę). Revisit if: wynik na koszyku MVP jest `inconclusive` z powodu zbyt małej liczby niezależnych sygnałów — wtedy rozważyć cross-sectional (Option A) jako `q3` zamiast/obok mean-reversion.

## Diagrams

```
Hypothesis (proposed)
  -> Strategy.generate_signals(PriceBar[]) -> Signal[]           (S2, S3)
  -> backtest.vectorized.run(Signal[], CostModel) -> BacktestRun  (S4)
       -> PortfolioSnapshot[], Trade[]
  -> reporting.metrics(BacktestRun) -> PerformanceMetrics         (S5)
  -> validation.WalkForwardValidator(BacktestRun) -> ValidationResult   (S9)
  -> validation.holdout (zamrożony config) -> ValidationResult          (S10)
  -> validation.PermutationTestValidator(BacktestRun) -> ValidationResult (S11)
  -> risk.RegimeClassifier(PriceBar[]) -> RegimeLabel[]            (S12)
  -> attribution.TradeLedger(Trade[], RegimeLabel[]) -> cięcia P&L (S14)
  -> reporting.TearSheet(...) -> raport                            (S15)
  -> Hypothesis (confirmed / rejected / inconclusive) -> RESEARCH_LOG.md (S16)
```

## Contracts

### Pliki

```
src/quantlab/
  research/
    hypothesis.py                  # Hypothesis, status transitions (REQ-002, REQ-090)
  strategy/
    base.py                         # Strategy (Protocol)
    time_series_momentum.py         # TimeSeriesMomentum
  backtest/
    vectorized/
      engine.py                     # run(), BacktestRun, PortfolioSnapshot
      golden_master.py              # referencyjne syntetyczne serie + oczekiwane metryki (test)
  costs/
    base.py                         # CostModel (Protocol)
    naive.py                        # NaiveCostModel
    realistic.py                    # RealisticCostModel
  validation/
    base.py                         # Validator (Protocol), ValidationResult
    walk_forward.py                 # WalkForwardValidator
    permutation.py                  # PermutationTestValidator
    holdout.py                      # freeze_holdout(), load_frozen_holdout(), enforce before use
  risk/
    regime.py                       # RegimeClassifier, RegimeLabel
    stress.py                       # scenario shock
  attribution/
    trade_ledger.py                 # Trade, TradeLedger, group_by(...)
  reporting/
    metrics.py                      # cagr, sharpe, sortino, calmar, max_drawdown (własny kod)
    tear_sheet.py                   # generate_tear_sheet(BacktestRun, ValidationResult) -> plik HTML
config/
  holdout/momentum_v1.yaml          # zamrożony zakres dat + parametry + success_criterion (REQ-041)
tests/
  strategy/test_time_series_momentum.py   # brak look-ahead (REQ-010)
  backtest/vectorized/test_golden_master.py  # REQ-020, tolerancja numeryczna
  validation/test_holdout_guard.py            # REQ-090: confirmed bez holdout -> błąd
  reporting/test_metrics.py                   # metryki własnym kodem, porównanie z wartością referencyjną liczoną ręcznie
```

### Kontrakty (sygnatury poglądowe)

```python
class Signal(BaseModel):
    instrument_id: str
    ts: date
    direction: Literal["long", "short", "flat"]
    strength: float  # znormalizowana, do cięcia po decylach (REQ-061)

class Strategy(Protocol):
    def generate_signals(self, bars: dict[str, list[PriceBar]], as_of: date) -> list[Signal]: ...

class CostModel(Protocol):  # S7: silnik rebalansuje wagi dziennie, nie ma transakcji
    name: str
    def cost(self, instrument_bars: list[PriceBar], as_of: date, traded_weight: float) -> float: ...
    # koszt jako ułamek equity; tylko dane <= as_of; turnover liczony od wag po dryfie cen

class BacktestRun(BaseModel):
    id: str
    strategy_name: str
    strategy_params: dict
    cost_model_name: str
    universe_name: str
    start: date
    end: date
    seed: int
    git_sha: str
    snapshots: list[PortfolioSnapshot]
    trades: list[Trade]

class Validator(Protocol):
    def validate(self, run: BacktestRun) -> ValidationResult: ...

class ValidationResult(BaseModel):
    method: Literal["walk_forward", "permutation", "holdout"]
    passed: bool | None       # None = inconclusive
    detail: dict

class RegimeClassifier(Protocol):
    def label(self, bars: list[PriceBar], as_of: date) -> str: ...  # tylko dane <= as_of (REQ-050)

def cagr(equity_curve: list[float], periods_per_year: int) -> float: ...
def sharpe(returns: list[float], periods_per_year: int, risk_free: float = 0.0) -> float: ...
```

Nazwy pól i dokładne wzory metryk (np. konwencja rocznicowania Sharpe, definicja Sortino z downside deviation) zweryfikować względem standardowej literatury przed implementacją S5 — łatwo o subtelny błąd w rocznicowaniu, który zafałszuje porównywalność wyników.

## Rollout and rollback

Kolejność slice'ów z 01-story/ROADMAP, każdy z zielonymi testami przed przejściem dalej:

1. **S1** `research.hypothesis` — rejestracja, przejścia statusu, test REQ-002/REQ-090 (guard najpierw, zanim będzie co blokować).
2. **S2** sygnał momentum jako czysta funkcja + test braku look-ahead.
3. **S3** `TimeSeriesMomentum` implementuje `Strategy`.
4. **S4** silnik wektorowy + `BacktestRun`/`PortfolioSnapshot`, bez kosztów (koszt=0 na start).
5. **S5** `reporting.metrics` własnym kodem + **test golden-master** (AC-2) — blokujący dla wiarygodności wszystkiego dalej.
6. **S6** pierwszy pełny przebieg end-to-end na realnym koszyku (wymaga odpowiedzi na open question #1 z 01-story).
7. **S7** `NaiveCostModel`.
8. **S8** `RealisticCostModel` + raport porównawczy wrażliwości na koszty.
9. **S9** `WalkForwardValidator`.
10. **S10** zamrożenie holdout (`config/holdout/momentum_v1.yaml`, commit przed użyciem) + `validation.holdout` z wymuszeniem REQ-041.
11. **S11** `PermutationTestValidator`.
12. **S12** `RegimeClassifier` + metryki warunkowe.
13. **S13** stress test scenariuszowy.
14. **S14** `TradeLedger` + cięcia P&L.
15. **S15** `TearSheet`.
16. **S16** wpis w `docs/RESEARCH_LOG.md`, status końcowy hipotezy — zamyka MVP.

Rollback: `git revert` per slice — brak migracji, brak stanu zewnętrznego poza plikami wynikowymi w `data/` (gitignored, bezpiecznie usuwalne i odtwarzalne ponownym przebiegiem, poza zamrożonym plikiem holdout, który celowo nie jest odtwarzalny — to jego funkcja).

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Silnik ma subtelny błąd (np. off-by-one w dacie sygnału vs wykonania) niewykryty bez golden-master | średnia | wysoki | S5 golden-master blokujący przed S6 |
| Pokusa zmiany `success_criterion` po zobaczeniu wyniku na holdout | średnia | wysoki (unieważnia całą walidację) | plik zamrożony i commitowany w S10, przed S11; REQ-090 w kodzie, nie tylko w procesie |
| Zbyt mały koszyk/zakres dat na wiarygodny test permutacyjny | średnia | średni | REQ w 02-spec: wynik `low_confidence` jawnie oznaczony, nie ukryty |
| Rocznicowanie/definicja Sortino niezgodna ze standardem | niska | średni | weryfikacja wzorów przed S5, nie z pamięci |

## Handoff notes

- Zacznij od S1, ale traktuj S5 (golden-master) jako priorytet ryzyka: rejestr hipotez jest prosty, golden-master jest tym, co daje wiarygodność wszystkiemu, co przyjdzie później — nie odkładaj go mimo że numerycznie wypada w środku sekwencji.
- Nie zgaduj wzorów metryk (Sharpe, Sortino, Calmar) z pamięci — subtelności rocznicowania i doboru stopy wolnej od ryzyka różnią się między źródłami; zweryfikuj przed S5.
- S10 (zamrożenie holdout) musi być commitem oddzielnym od S11 — inaczej nie ma dowodu, że parametry były ustalone przed zobaczeniem wyniku.
- Koszyk instrumentów i zakres dat (open question #1 w 01-story) blokują S6 — rozwiąż przed rozpoczęciem tego slice'u.
- Nie commituj bez prośby właściciela.
