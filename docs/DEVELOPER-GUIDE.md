# Przewodnik programisty

Dokument dla osoby, która rozwija pakiet `quantlab`. Uzupełnia [ARCHITECTURE.md](ARCHITECTURE.md) (zasady i kontrakty) opisem tego, jak moduły współpracują w przebiegu badania i jak je rozszerzać. Komendy opisuje [CLI-REFERENCE.md](CLI-REFERENCE.md), konwencje pracy [TESTING-AND-CI.md](TESTING-AND-CI.md).

## Środowisko

- Python ≥ 3.12 (`.python-version`), zależności i środowisko przez [uv](https://docs.astral.sh/uv/): `uv sync`. Nie używaj launchera `py`, bo startuje inną wersję Pythona niż przypięta; zawsze `uv run …`.
- Zależności: `duckdb`, `numpy`, `pandas`, `pyarrow`, `pydantic`, `pyyaml`, `requests`, `statsmodels`, `typer`. Grupa `dev`: `pytest`, `ruff`.
- Maszyna docelowa: Windows, procesor bez AVX2, 8 GB RAM, bez GPU. Każda nowa zależność natywna wymaga testu importu w `tests/test_environment.py`.
- Lint i formatowanie: `uv run ruff check .`, `uv run ruff format .` (długość linii 100, cel `py312`).

## Zasady kodu

- Ceny i zwroty to `float64` (numpy); `Decimal` tylko w końcowej księdze pojedynczej transakcji ([ADR-0003](adr/0003-float-not-decimal-core-engine.md)).
- Brak look-ahead: strategia, model kosztów i klasyfikator reżimu widzą tylko dane z datą ≤ `as_of`.
- Interfejsy to `typing.Protocol` (`Strategy`, `CostModel`, `Validator`, `DataProvider`, `Narrator`, `Sizer`, `RebalancePolicy`, `AllocationRule`, `ExecutionModel`, `FillPolicy`, `VolatilityEstimator`, `RegimeClassifier`). Nowe zachowanie dodaje się jako nowa implementacja, nie jako kolejny `if` po typie.
- Zależności wstrzykuje się przez konstruktor lub rejestry nazw (`cli._PROVIDERS`, `cli._SIGNIFICANCE_TESTS`, unia `StudyParameters`).
- Komentarze i identyfikatory po angielsku; dokumentacja po polsku.

## Przepływ badania

```
config/holdout/<id>.yaml  (zamrożona definicja, commit)
        │ research.definition: StudyParameters + SuccessCriterion
        ▼
core.universe.Universe ──► DataProvider (Binance / Tiingo) ──► PriceBar, InstrumentEvents
        │                         │ core.data.cache, corporate_actions, cash, quality
        ▼                         ▼
strategy.Strategy ──► Signal ──► backtest.sizing.Sizer ──► wagi
        │                                         │
        └──── backtest.vectorized / event_driven ◄┘  + costs.CostModel + rebalance.RebalancePolicy
                              ▼
                        BacktestRun (snapshoty kapitału i pozycji)
                              ▼
 validation (walk-forward, permutacja / losowe portfele, CPCV, PSR/DSR/PBO)
 risk (reżimy, stress)    attribution (rejestr transakcji, cięcia P&L)
                              ▼
 reporting (metryki, tear-sheet, results_store, narrative)
                              ▼
                 results/ (Parquet)  ──►  QuantLab.Api  ──►  web
```

Kroki `quantlab run <hipoteza>` ([`cli.py`](../src/quantlab/cli.py)):

1. Wczytanie zamrożonej definicji (`_load_definition`); odmowa, gdy plik nie jest zacommitowany.
2. Uniwersum (`Universe.load`) i dostawca z rejestru nazw po polu `source`.
3. Pobranie danych okresu treningowego z rozgrzewką przed początkiem (`StudyParametersBase.fetch_start`), korekta o splity i dywidendy, zakończenie delistingami, ewentualne przeliczenie na zwroty ponad gotówkę. Holdout nie jest pobierany.
4. Kontrola jakości danych (`core.data.quality`); błąd zatrzymuje przebieg.
5. Przebieg silnika wektorowego pod modelami kosztów `zero`, `naive` i `realistic`.
6. Walidacja in-sample: walk-forward albo, dla hipotez z siatką, CPCV; test istotności wskazany w kryterium; PSR/DSR i PBO na próbach z historii gita.
7. Reżimy, stress test, rejestr transakcji i cięcia P&L, diagnostyka treningowa definicji.
8. Zapis do magazynu wyników (`reporting.results_store.write_run`) i odświeżenie rejestru.

`open-holdout` powtarza kroki 2–5 na okresie holdoutu raz, stosuje zamrożone kryterium (`validation.holdout.holdout_verdict`) i zapisuje `<id>.opened.json`.

## Mapa pakietu `src/quantlab`

| Pakiet | Odpowiedzialność | Najważniejsze elementy |
|---|---|---|
| `core.data` | źródła danych i kanoniczny schemat | `PriceBar`, `DataProvider`, `BinanceProvider`, `TiingoProvider`, `cache`, `corporate_actions` (`adjust_bars`, `MarketData`), `events`, `cash`, `quality`, `coverage`, `identity` |
| `core.universe`, `core.sp500`, `core.storage` | uniwersum point-in-time, odtwarzanie składu S&P 500, I/O barów | `Universe`, `Instrument`, `Membership`, `reconstruct`, `write_price_bars` |
| `research` | definicje i stan badań | `Hypothesis` i statusy, `definition` (parametry per strategia), `trials` (próby z gita), `plan` (kroki `quantlab plan`) |
| `strategy` | generowanie sygnałów | `Strategy`, `Signal`, `TimeSeriesMomentum`, `ShortTermReversal`, `PairsSpreadReversion`, `CrossSectionalMomentum`, `SelectedParameter`, `StrategyPortfolio`, `VolatilityTargeted`, `MembersOnly` |
| `backtest` | silniki i wspólny kontrakt | `BacktestRun`, `PortfolioSnapshot`, `sizing`, `rebalance`; `vectorized.run`; `event_driven` (`run`, `ExecutionModel`, `FillPolicy`, `Portfolio`, `BarFeed`) |
| `costs` | koszty transakcyjne | `CostModel`, `ZeroCostModel`, `NaiveCostModel`, `RealisticCostModel` |
| `validation` | wiarygodność wyniku | `Validator`, `WalkForwardValidator`, `PermutationTestValidator`, `RandomPortfolioValidator`, `cpcv`, `pbo`, `sharpe_inference`, `holdout` |
| `risk` | reżimy, zmienność, stres | `VolatilityTercileClassifier`, `stress_run`, `RollingVolatility`, `EwmaVolatility`, `regime_conditional_metrics` |
| `attribution` | analiza transakcji | `Trade`, `build_trade_ledger`, `group_pnl` i cięcia |
| `portfolio` | alokacja między rękawami | `EqualWeight`, `InverseVolatility`, `RiskParity`, `portfolio_report` |
| `reporting` | metryki i wyjście | `metrics`, `tear_sheet`, `cost_comparison`, `engine_comparison`, `grid_report`, `multiple_testing`, `results_store`, `narrative` |
| `cli` | orkiestracja | komendy Typer, rejestry nazw |

## Jak dodać…

### …nową strategię (hipotezę nowego rodzaju)

1. Zaimplementuj `Strategy.generate_signals(bars, as_of) -> list[Signal]` w `strategy/` (bez `if` po typie instrumentu; tylko dane ≤ `as_of`).
2. Dodaj klasę parametrów w `research/definition.py` dziedziczącą po `StudyParametersBase`, z polem `strategy: Literal["nazwa"]`. Wymagane: `warm_up_days`, `strategy_params()`, `build_strategy()`. Opcjonalnie nadpisz `build_sizer()`, `build_rebalance_policy()`, `configurations`, `training_diagnostics()`, `grid_evidence()`, `resolve()`, `holdout_prerequisites()`.
3. Dopisz klasę do unii `StudyParameters` (dyskryminator `strategy`).
4. Napisz testy w `tests/strategy/` i `tests/research/` (w tym golden-master na danych syntetycznych, jeśli zmienia się rachunek silnika).
5. Zamroź hipotezę: `config/holdout/<id>.yaml` z parametrami, okresami i `success_criterion`; commit przed jakimkolwiek spojrzeniem na holdout ([INSTRUKCJA.md](INSTRUKCJA.md), rozdział „Nowa hipoteza").

### …nowy model kosztów

Klasa z atrybutem `name` i metodą `cost(instrument_bars, as_of, traded_weight) -> float` (ułamek kapitału, tylko bary ≤ `as_of`) w `costs/`. Definicja hipotezy wybiera dziś tylko model `realistic` (`CostModelParameters`, `research/definition.py`); `run` porównuje go z `ZeroCostModel` i `NaiveCostModel` o tej samej opłacie. Model wybieralny w definicji wymaga rozszerzenia `CostModelParameters` (np. unii z dyskryminatorem `name`) i planu zmiany.

### …nowy walidator lub test istotności

Walidator ma metodę `validate(run: BacktestRun) -> ValidationResult`. Test istotności wskazywany w kryterium sukcesu rejestruje się w `cli._SIGNIFICANCE_TESTS` pod nazwą (typ `SignificanceTest` w `validation/base.py`) oraz opisem w `cli._TEST_WORDING`.

### …nowe źródło danych

1. Klasa implementująca `DataProvider` (`fetch` i `events`; źródło bez zdarzeń korporacyjnych dziedziczy po `WithoutEvents`) w `core/data/`.
2. Wpis w `cli._PROVIDERS` pod nazwą używaną w polu `source` uniwersum.
3. Plik uniwersum w `src/quantlab/config/universes/<nazwa>.yaml` (pola: `name`, `source`, `periods_per_year`, `market_proxy`, `asof_date`, `instruments`).
4. Sprawdź licencję i dopisz źródło według checklisty w [DATA-SOURCES.md](DATA-SOURCES.md); dane i ceny nie trafiają do repozytorium ([ADR-0010](adr/0010-public-repo-data-boundary.md)).

### …nowy opis wyniku

Druga implementacja `Narrator.sections(facts) -> list[Section]` w `reporting/narrative.py`. Liczby bierze wyłącznie z `Facts` odczytanych z magazynu; żadnych obliczeń finansowych w narratorze.

### …nowe pole w magazynie wyników

Zob. „Zmiana schematu" w [RESULTS-STORE.md](RESULTS-STORE.md).

## Hipoteza jako dane

Definicja `config/holdout/<id>.yaml` zawiera: `hypothesis`, `training_start`/`training_end`, `start`/`end` holdoutu, `parameters` (strategia, uniwersum, model kosztów i parametry strategii) oraz `success_criterion` (`description`, `min_sharpe`, `max_p_value`; opcjonalnie `significance_test` — domyślnie `day_shuffle`, `in_sample_validation` — domyślnie `walk_forward`, i `cpcv` z ustawieniami dla bramki CPCV). Plik `<id>.opened.json` powstaje przy otwarciu holdoutu. Obie rodziny plików są częścią historii badania: rejestr prób (`research/trials.py`) liczy próby z historii gita tego katalogu, więc przepisanie historii tego katalogu zmieniłoby liczbę prób, a z nią próg DSR.

Dziewięć zamrożonych hipotez: `momentum_v1`, `mean_reversion_v1`, `pairs_v1`, `xsmom_v1`, `momentum_select_v1`, `portfolio_v1`, `momentum_voltarget_v1`, `momentum_multiasset_v1`, `momentum_voltarget_multiasset_v1`. Wyniki: [RESEARCH_LOG.md](RESEARCH_LOG.md).

## Cykl życia hipotezy

Statusy: `proposed` → `testing` → `confirmed` | `rejected` | `inconclusive` (przejścia tylko do przodu, `research/hypothesis.py`). `confirmed` wymaga zaliczonego walk-forward i zaliczonego holdoutu; w rejestrze magazynu status wynika z zapisanych bramek (`concluded_status`).
