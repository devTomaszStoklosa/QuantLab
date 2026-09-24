# q3-mean-reversion-hypothesis - Design

Status: Draft
Owner role: Architect
Upstream: 02-spec.md
ADRs: docs/adr/0002-dual-backtest-engine.md, docs/adr/0004-validation-first-frozen-holdout.md, docs/adr/0005-descriptive-reports-no-investment-advice.md

## Context and constraints

- Cały pipeline z `q1` istnieje i jest przetestowany: silnik wektorowy (golden-master), trzy modele kosztów, walk-forward, test permutacyjny, reżimy, stress test, rejestr transakcji, tear-sheet, `concluded_status`.
- Jedyne miejsce specyficzne dla momentum to orkiestracja: `quantlab run` bierze parametry ze stałych w `cli.py` (`_LOOKBACK_DAYS`, `_TRAINING_START`…), a `HoldoutParameters.strategy` przyjmuje tylko `time_series_momentum`. Test pilnuje, że stałe CLI zgadzają się z zamrożonym plikiem — dwa źródła tej samej prawdy.
- Zamrożony plik `config/holdout/momentum_v1.yaml` nie może się zmienić (jego commit `a9cb0b0` jest dowodem pre-rejestracji); nowy schemat musi go czytać bez modyfikacji.
- Ta sama maszyna i te same limity co w `q1`: bez GPU, 8 GB RAM, pełny przebieg < 1 min.

## Quality attribute scenarios

| Source | Stimulus | Response | Measure |
|---|---|---|---|
| Deweloper | dodaje trzecią hipotezę innej rodziny | nowa klasa strategii + plik definicji, bez zmian w runnerze | 0 nowych gałęzi `if`/`match` po typie strategii |
| Deweloper | uruchamia `momentum_v1` po uogólnieniu | identyczny wynik | każda wartość equity równa co do bitu |
| Deweloper | uruchamia hipotezę z niezacommitowaną definicją | odmowa przed pobraniem danych | REQ-303 wymuszony w kodzie |
| Recenzent | czyta dziennik | widzi obie hipotezy, ich kontrast i liczbę prób | jeden wpis na hipotezę, samowystarczalny |

## Options — skąd runner bierze parametry hipotezy

### Option A - Zamrożony plik jako jedyna definicja hipotezy

`config/holdout/<id>.yaml` (format `momentum_v1`) zawiera strategię z parametrami, uniwersum, koszty, okres treningowy, holdout i kryterium. `quantlab run <id>` wczytuje go przez `load_frozen_holdout`, więc przebieg bez zacommitowanej definicji jest niemożliwy. Parametry strategii to unia rozróżniana polem `strategy`; każdy wariant sam buduje swoją strategię.

### Option B - Osobny plik definicji treningu i osobny plik holdoutu

`config/hypotheses/<id>.yaml` do treningu, `config/holdout/<id>.yaml` do holdoutu. Dwa pliki na hipotezę, które muszą się zgadzać — ten sam problem, który dziś rozwiązuje test porównujący stałe CLI z plikiem.

### Option C - Rejestr definicji w kodzie Pythona

Słownik `HypothesisDefinition` w module `research`. Zmiana parametru to zmiana kodu; zamrożenie nadal trzeba by dowodzić osobnym plikiem, więc wraca problem dwóch źródeł.

## Trade-off matrix (1-5)

| Criterion | A | B | C |
|---|---|---|---|
| Jedno źródło prawdy | 5 — plik zamrożony jest definicją | 2 — dwa pliki do pilnowania | 2 — kod + plik zamrożenia |
| Wymuszenie pre-rejestracji | 5 — przebieg bez commitu niemożliwy | 3 | 2 |
| Zgodność z `momentum_v1.yaml` | 5 — ten sam format | 4 | 3 |
| Złożoność | 4 — unia rozróżniana w pydantic | 3 | 4 |
| Rozszerzalność (q4, q5) | 4 | 4 | 3 |

## Decision

Recommended: **Option A**. Rezygnujemy z: osobnych definicji treningu (dwa źródła prawdy) i definicji w kodzie (zamrożenie nadal wymagałoby pliku). Konsekwencja: definicja hipotezy — łącznie z holdoutem i kryterium — jest commitowana **przed pierwszym przebiegiem treningowym**, a nie dopiero przed otwarciem holdoutu jak w `q1`. To silniejsza pre-rejestracja niż w MVP, możliwa dlatego, że jedyny parametr strategii pochodzi z literatury. Revisit if: hipoteza będzie miała parametry dobierane na danych treningowych (wtedy potrzebny etap „trening przed zamrożeniem" i Option B).

Ustawienia metodologii wspólne dla całego laboratorium — liczba permutacji, seed, α, klasyfikator reżimów, scenariusze stress testu, reguła walk-forward — zostają stałymi w kodzie, jednymi dla wszystkich hipotez. Dzięki temu obie hipotezy są oceniane tą samą, już zacommitowaną miarą.

## Diagrams

```
config/holdout/<id>.yaml --load_frozen_holdout--> HoldoutConfig
  .parameters: TimeSeriesMomentumParameters | ShortTermReversalParameters  (unia po `strategy`)
      .build_strategy() -> Strategy
      .warm_up_days, .strategy_params()
  -> backtest.vectorized.run(...) x 3 modele kosztów          (bez zmian)
       -> PortfolioSnapshot.traded (nowe, M3) -> annualized_turnover
  -> WalkForward, Permutation, regimes, stress, ledger        (bez zmian)
  -> reporting.contrast.return_correlation(run, momentum_run) (M3)
  -> TearSheet (+ obrót)                                       (M3)
  -> concluded_status -> RESEARCH_LOG.md                       (M7)
```

## Contracts

### Pliki

```
src/quantlab/
  research/
    definition.py              # TimeSeriesMomentumParameters, ShortTermReversalParameters, StudyParameters (M1)
  strategy/
    short_term_reversal.py     # compute_reversal_signal(), ShortTermReversal (M2)
  backtest/vectorized/engine.py  # PortfolioSnapshot.traded (M3)
  reporting/
    metrics.py                 # annualized_turnover() (M3)
    contrast.py                # return_correlation() (M3)
  validation/holdout.py        # HoldoutConfig.parameters: StudyParameters (M1)
  cli.py                       # quantlab run [HYPOTHESIS], open-holdout [HYPOTHESIS] (M1)
config/holdout/
  momentum_v1.yaml             # bez zmian
  mean_reversion_v1.yaml       # zamrożona definicja (M4, osobny commit)
tests/
  research/test_definition.py
  strategy/test_short_term_reversal.py      # brak look-ahead (REQ-310)
  test_cli.py                               # regresja momentum_v1 (REQ-302), odmowa bez commitu (REQ-303)
```

### Kontrakty (sygnatury poglądowe)

```python
class TimeSeriesMomentumParameters(BaseModel):
    strategy: Literal["time_series_momentum"]
    lookback_days: int
    universe: str
    cost_model: CostModelParameters

    @property
    def warm_up_days(self) -> int: ...          # historia potrzebna przed startem okna
    def strategy_params(self) -> dict: ...      # do BacktestRun.strategy_params
    def build_strategy(self) -> Strategy: ...

class ShortTermReversalParameters(BaseModel):
    strategy: Literal["short_term_reversal"]
    formation_days: int = Field(ge=1)
    universe: str
    cost_model: CostModelParameters
    # te same trzy metody

StudyParameters = Annotated[
    TimeSeriesMomentumParameters | ShortTermReversalParameters, Field(discriminator="strategy")
]

def compute_reversal_signal(bars: list[PriceBar], as_of: date, formation_days: int) -> Signal | None: ...

class PortfolioSnapshot(BaseModel):
    ...
    traded: dict[str, float] = {}   # |zmiana wagi| per instrument w okresie kończącym się w ts

def annualized_turnover(run: BacktestRun, periods_per_year: int) -> float: ...
def return_correlation(a: BacktestRun, b: BacktestRun) -> float | None: ...
```

## Rollout and rollback

Każdy slice z zielonymi testami przed następnym:

1. **M1** uogólniony runner: `research.definition`, unia w `HoldoutConfig`, `quantlab run [HYPOTHESIS]` i `open-holdout [HYPOTHESIS]` (domyślnie `momentum_v1`), odmowa bez zacommitowanej definicji. Test regresji: `momentum_v1` identyczne co do bitu; test, że `momentum_v1.yaml` parsuje się bez zmian.
2. **M2** `compute_reversal_signal` jako czysta funkcja + `ShortTermReversal`; testy braku look-ahead i przypadków brzegowych.
3. **M3** `PortfolioSnapshot.traded` (tylko zapis — golden-master bez zmian), `annualized_turnover`, `return_correlation`; w `quantlab run` i tear-sheecie.
4. **M4** zamrożenie `config/holdout/mean_reversion_v1.yaml` — **osobny commit, przed jakimkolwiek przebiegiem tej hipotezy na danych**. Wymaga odpowiedzi na pytania 1–4 z 01-story.
5. **M5** pierwszy przebieg treningowy na realnych danych (lokalnie — Binance jest zablokowany w środowisku chmurowym) z wynikiem w PR.
6. **M6** jednorazowe otwarcie holdoutu, zapis commitowany.
7. **M7** wpis w `docs/RESEARCH_LOG.md` z kontrastem do `momentum_v1` i liczbą prób.

Rollback: `git revert` per slice. M1 nie zmienia żadnego zamrożonego pliku ani zapisu otwarcia, więc cofnięcie nie narusza dowodów pre-rejestracji `momentum_v1`.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Uogólnienie runnera cicho zmienia wynik `momentum_v1` | średnia | wysoki | test regresji co do bitu na syntetycznych danych + ponowny lokalny przebieg z porównaniem do liczb z PR #18/#20 |
| Zmiana schematu łamie parsowanie zamrożonego `momentum_v1.yaml` | niska | wysoki | test parsowania prawdziwego pliku; plik nietknięty |
| Obrót tak duży, że koszty dominują wynik | wysoka | średni | obrót w raporcie (REQ-320); `rejected` z powodu kosztów to pełnoprawny wynik |
| Pokusa otwarcia holdoutu przed przeglądem wyniku treningowego (dane holdoutu już istnieją) | średnia | wysoki | kolejność M5 → M6 jako osobne PR; zapis otwarcia z commitem |
| Mała moc testu na 8-miesięcznym holdoucie | wysoka | średni | przyjęte z góry w 01-story; wynik `inconclusive` opisany jako ograniczenie, nie porażka |

## Handoff notes

- Zacznij od M1 i traktuj test regresji `momentum_v1` jako blokujący — bez niego nie wiadomo, czy druga hipoteza jest oceniana tą samą miarą co pierwsza.
- M2 i M3 nie wymagają odpowiedzi na otwarte pytania; M4 wymaga wszystkich czterech.
- Nie uruchamiaj `ShortTermReversal` na realnych danych przed M4 — nawet „dla sprawdzenia, czy działa". Syntetyczne dane w testach wystarczą.
