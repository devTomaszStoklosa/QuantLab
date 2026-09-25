# Architektura

Dokument żywy: docelowy układ repo i kontrakty modułów wspólnych. Decyzje z uzasadnieniem w [adr/](adr/), szczegóły pierwszej implementacji w [specs/lab-foundation/03-design.md](specs/lab-foundation/03-design.md) i [specs/q1-momentum-research-mvp/03-design.md](specs/q1-momentum-research-mvp/03-design.md).

## Zasady

1. Jeden pakiet Pythona `quantlab`, podpakiet per warstwa ([ADR-0001](adr/0001-python-uv-single-package.md)).
2. Dwa silniki backtestu — wektorowy i event-driven — za wspólnym kontraktem wejścia/wyjścia ([ADR-0002](adr/0002-dual-backtest-engine.md)).
3. Ceny i zwroty w `float64`; `Decimal` tylko w końcowej księdze pojedynczej transakcji ([ADR-0003](adr/0003-float-not-decimal-core-engine.md)).
4. Hipoteza bez walidacji (walk-forward + zamrożony holdout) nie jest „confirmed" ([ADR-0004](adr/0004-validation-first-frozen-holdout.md)).
5. Raporty opisowe, bez rekomendacji inwestycyjnych ([ADR-0005](adr/0005-descriptive-reports-no-investment-advice.md)).
6. .NET i React tylko w warstwie prezentacji/orkiestracji, nie w rdzeniu obliczeniowym ([ADR-0006](adr/0006-dotnet-react-presentation-layer-only.md)).
7. `core` nie zależy od żadnej warstwy domenowej; warstwy domenowe zależą od `core`, nie od siebie nawzajem poza jawnymi punktami integracji (`reporting` czyta wyniki `backtest`; `validation` i `risk` czytają wyniki `backtest`).

## Warstwy i przepływ

1. **Data layer** (`core.data`, `core.universe`) — pozyskanie i kanoniczny schemat OHLCV, point-in-time uniwersum.
2. **Research layer** (`quantlab.research`, notebooki) — rejestr `Hypothesis`, definicje hipotez (`research.definition`: strategia z parametrami, uniwersum, model kosztów; każdy wariant sam buduje swoją strategię), eksploracja przed kodem produkcyjnym.
3. **Strategy layer** (`quantlab.strategy`) — interfejs `Strategy.generate_signals`, jedna implementacja per hipoteza: momentum szeregów czasowych, krótkoterminowe odwrócenie, spread pary (kointegracja), momentum przekrojowe 12-1 na point-in-time uniwersum (`q5`, rebalans przy zmianie sygnału), parametr wybierany co rok z siatki (`q8`, `SelectedParameter`) i portfel zamrożonych hipotez (`q9`, `StrategyPortfolio`: rękawy ważone co miesiąc zamrożoną regułą z `quantlab.portfolio.allocation` — równe wagi, odwrotność zmienności, risk parity — na historii sprzed dnia rebalansu, pozycje netto dla silnika przez sizer `CarriedWeights`). Definicja odwołująca się do innych hipotez ładuje je hakiem `resolve(load)`, który runner woła dla każdej definicji, a `open-holdout` sprawdza `holdout_prerequisites` (portfel nie otwiera holdoutu nachodzącego na nieotwarty holdout składnika).
4. **Backtest engine** (`quantlab.backtest.vectorized`, `quantlab.backtest.event_driven`) — dwa silniki za wspólnym kontraktem `BacktestRun` (`quantlab.backtest.run`), jedną regułą wag (`quantlab.backtest.sizing`) i jedną polityką rebalansu (`quantlab.backtest.rebalance`: `Daily` domyślnie, `OnSignalChange` dla strategii miesięcznych); konsumenci wyników nie zależą od żadnego z silników.
5. **Cost & execution model** (`quantlab.costs`) — interfejs `CostModel`, implementacje naiwna i realistyczna.
6. **Validation layer** (`quantlab.validation`) — interfejs `Validator`: walk-forward, permutacyjny, docelowo purged k-fold/CPCV.
7. **Risk & regime analytics** (`quantlab.risk`) — klasyfikacja reżimów, metryki warunkowe.
8. **Trade & attribution analysis** (`quantlab.attribution`) — rejestr `Trade`, cięcia P&L.
9. **Reporting layer** (`quantlab.reporting`) — tear-sheet z metrykami liczonymi własnym kodem.
10. **Orchestration/CLI** (`quantlab.cli`) — `quantlab run [HIPOTEZA]`, `quantlab open-holdout [HIPOTEZA]`, `quantlab compare-engines [HIPOTEZA]` (opisowe porównanie silników na okresie treningowym) i `quantlab trials [HIPOTEZA]` (wszystkie próby na tych samych danych z PSR, DSR i PBO; próby liczone z historii gita `config/holdout/`, `quantlab.research.trials`), `quantlab registry` (rejestr hipotez w magazynie wyników, bez pobierania danych). `quantlab run` zapisuje dowody przebiegu głównego do magazynu wyników `results/` (`quantlab.reporting.results_store`, [ADR-0008](adr/0008-results-store-parquet-duckdb.md)); `run` i `open-holdout` odświeżają przy tym rejestr. Parametry hipotezy pochodzą wyłącznie z jej zacommitowanej definicji `config/holdout/<id>.yaml` (przebieg bez commitu jest odrzucany przed pobraniem danych); stałe w CLI to tylko metodologia wspólna dla wszystkich hipotez (seed, liczba permutacji, reżimy, scenariusze stress testu).
11. **Presentation** (poza pakietem Python, rozszerzenie `q7`) — ASP.NET Core Web API + React, czyta wyłącznie magazyn wyników: tabele Parquet w `results/` (schemat w [specs/q7-dotnet-react-presentation/02-spec.md](specs/q7-dotnet-react-presentation/02-spec.md)). Syntetyczny magazyn do testów i trybu demo: `presentation/fixtures/results/`, generowany pełnym pipeline'em (`tests/test_results_fixture.py`).

## Układ repo

```
QuantLab/
├── pyproject.toml              # extras: stats, ui
├── .python-version             # 3.12
├── src/quantlab/
│   ├── cli.py                   # komenda `quantlab`
│   ├── core/
│   │   ├── data/                 # DataProvider, adapter Binance, kanoniczny schemat
│   │   ├── universe.py           # point-in-time uniwersum
│   │   └── storage.py            # DuckDB/Parquet I/O
│   ├── research/                 # Hypothesis, rejestr
│   ├── strategy/                 # interfejs Strategy + implementacje per hipoteza
│   ├── backtest/
│   │   ├── vectorized/
│   │   └── event_driven/
│   ├── costs/                     # CostModel + implementacje
│   ├── portfolio/                 # reguły alokacji rękawów i raport portfela (q9)
│   ├── validation/                # Validator + implementacje
│   ├── risk/                      # reżimy, metryki warunkowe
│   ├── attribution/                # Trade ledger, cięcia P&L
│   └── reporting/                 # tear-sheet
├── global.json                     # .NET SDK 10.0.1xx, runner testów MTP (q7)
├── presentation/                  # rozszerzenie q7 (ADR-0006, ADR-0008)
│   ├── QuantLab.Api/               # ASP.NET Core minimal API, IResultsStore (DuckDB.NET)
│   ├── QuantLab.Api.Tests/         # xUnit v3: kontrakt na syntetycznym magazynie, test środowiska DuckDB
│   ├── web/                        # Vite + React 18 + TypeScript: rejestr hipotez, dowody, rejestr transakcji
│   ├── fixtures/results/           # syntetyczny magazyn wyników (generowany przez tests/test_results_fixture.py)
│   └── design-system/              # QuantForge: tokeny, komponenty React 18
├── data/
│   ├── fixtures/                  # syntetyczne dane testowe (w repo)
│   ├── raw/                       # pobrane dane publiczne (gitignored)
│   └── cache/                     # cache HTTP (gitignored)
├── notebooks/                      # eksploracja per hipoteza
├── tests/                          # lustro src/
└── docs/
```

## Mapa zależności

```
quantlab.strategy, quantlab.costs, quantlab.validation, quantlab.risk
  wszystkie zależą od -> quantlab.core (data, universe, storage)
quantlab.backtest (vectorized, event_driven)
  zależy od -> strategy, costs
  wynik (BacktestRun) czytany przez -> validation, risk, attribution, reporting
presentation (.NET + React, rozszerzenie q7)
  czyta -> DuckDB/Parquet zapisane przez quantlab.reporting/backtest
  nie wywołuje Pythona synchronicznie
```

## Kontrakty modułów core

### `core.data`

- `DataProvider` (interfejs): `fetch(instrument, start, end) -> list[PriceBar]`. Implementacje: `BinanceProvider` ([ADR-0007](adr/0007-binance-not-stooq-for-first-adapter.md) — Stooq odrzucony, blokuje dostęp programistyczny) i `TiingoProvider` (akcje USA, `q5`: surowe ceny, dywidendy i splity z wierszy cen, delisting z ostatniego dnia notowań w metadanych, bez zwrotu z delistingu). Runner bierze dostawcę z rejestru nazw (`cli._PROVIDERS`) po polu `source` pliku uniwersum, bez `if` po klasie aktywów.
- Kanoniczny schemat `PriceBar`: instrument_id, ts, open, high, low, close, volume, adj_close, source, `unadjusted_close` (surowe zamknięcie baru skorygowanego; `raw_close` do reguł na poziomie ceny). Zamrożony dataclass ze slotami, nie model pydantic: uniwersum akcji to miliony barów (ok. 300 zamiast 1 450 bajtów na bar); zmiana przez `dataclasses.replace`, cache przez `to_json`/`from_json`.
- `DataProvider.events` podaje corporate actions (`Split`, `CashDividend`, `core.data.events`; krypto: brak), a runner koryguje nimi każde pobrane bary (`core.data.corporate_actions.with_events`): ceny wstecz, tak że zwrot przez ex-date jest zwrotem całkowitym. Delisting kończy bary barem wartości delistingu (flaga `delisting`, zwrot ze źródła albo zamrożone `missing_delisting_return` definicji); oba silniki zamieniają trzymaną pozycję na gotówkę po tej wartości, bez kosztu.
- Cache na dysku (`data/cache/`), throttling po stronie klienta, nigdy retry-on-429 jako jedyna ochrona.

### `core.universe`

- `Universe`: nazwa, `asof_date`, lista `Instrument`, opcjonalnie okresy członkostwa (`Membership`); jeden plik na uniwersum w `quantlab/config/universes/<nazwa>.yaml`. Bez okresów uniwersum jest statyczne (`mvp-crypto`); z okresami `members(t)` zwraca skład znany w dniu t (point-in-time, `q5`). Runner owija każdą strategię w `MembersOnly`, więc strategia widzi tylko członków w dniu sygnału. `market_proxy` uniwersum wyznacza reżimy zmienności i scenariusz najgorszego dnia (BTC dla `mvp-crypto`); w uniwersum point-in-time może nie mieć członkostwa (benchmark, np. SPY), wtedy żadna strategia go nie widzi. Plik uniwersum nazywa też źródło danych (`source`) i liczbę sesji w roku (`periods_per_year`: 365 krypto, 252 akcje) — z niej annualizacja wszystkich statystyk i okna reżimu (miesiąc i rok sesji). Przebieg pobiera tylko członków swojego okna i proxy. Uniwersum `sp500` buduje `quantlab build-universe` (`core.sp500`: tabele Wikipedii z zapisanej rewizji, skład odtwarzany wstecz przez tabelę zmian, mapa zmian tickerów `sp500-renames.yaml`); `run` na uniwersum point-in-time raportuje pokrycie cenami (`core.data.coverage`).

### `backtest` (wspólny kontrakt obu silników)

- Wejście: `StrategyConfig`, `Universe`, zakres dat, `CostModelConfig`, seed.
- Wyjście: `BacktestRun` z referencją do `PortfolioSnapshot[]`, `Trade[]`, `PerformanceMetrics`.
- `BacktestRun` niesie `git_sha` i parametry — reprodukowalność eksperymentu jako wymóg, nie luksus.

### `costs`

- `CostModel` (interfejs): `apply(trade_intent) -> Trade` (z uwzględnieniem spreadu, prowizji, poślizgu).
- Implementacje: `NaiveCostModel` (stałe bps), `RealisticCostModel` (poślizg skalowany zmiennością).

### `validation`

- `Validator` (interfejs): `validate(backtest_run) -> ValidationResult`.
- Implementacje MVP: `WalkForwardValidator`, `PermutationTestValidator`; `q6`: PSR, deflated Sharpe, PBO (CSCV); `q8`: CPCV procedury doboru parametru (`validation.cpcv`: grupy, podziały z purgingiem i embargo, ścieżki, wybór najlepszej wartości siatki na każdym zbiorze treningowym na macierzy dziennych zwrotów siatki).
- Test istotności kryterium wybiera zamrożona definicja (`success_criterion.significance_test`, rejestr nazw `cli._SIGNIFICANCE_TESTS`): `day_shuffle` (`PermutationTestValidator`, timing; domyślny) albo `random_portfolio` (`RandomPortfolioValidator`, `q5`: selekcja — losowe portfele z przekroju każdej decyzji rebalansu, te same wagi, harmonogram i dryf; przekrój to instrumenty z sygnałem, także flat).
- Holdout: zakres dat i parametry hipotezy zamrożone w pliku commitowanym przed pierwszym uruchomieniem na tym zakresie.

### `risk`

- Klasyfikacja reżimu (`RegimeLabel`) po zmienności zrealizowanej (tercyle) i/lub trend/range.
- Metryki `PerformanceMetrics` liczone warunkowo per reżim.

### `attribution`

- `Trade`: wejście/wyjście, wielkość, P&L brutto/netto, koszty, holding period, reżim w momencie wejścia, siła sygnału.
- Cięcia: po reżimie, holding period, miesiącu, decylu siły sygnału.

### `reporting`

- Metryki własnym kodem: CAGR, Sharpe, Sortino, Calmar, max drawdown, hit rate, profit factor, turnover.
- Tear-sheet (`reporting.tear_sheet`, S15): jeden samowystarczalny plik HTML z wykresami jako inline SVG (equity curve, drawdown) — bez JavaScriptu i bez zależności do rysowania; moduł tylko formatuje i rysuje liczby policzone wcześniej. Wynik treningowy i holdout w osobnych sekcjach (REQ-042); liczby holdoutu wyłącznie z zapisu jego jednorazowego otwarcia. Kolejne wykresy (rolling Sharpe, heatmapa miesięczna) w tym samym trybie albo przez matplotlib/plotly, jeśli inline SVG przestanie wystarczać.

## Testy

- Testy jednostkowe bez sieci: dane testowe z `data/fixtures/`.
- Golden-master dla silnika backtestu: syntetyczne serie ze znanym z góry wynikiem (np. stały trend → policzalny z góry Sharpe).
- `tests/test_environment.py` sprawdza importy zależności natywnych (maszyna bez AVX2) — patrz [CLAUDE.md](../CLAUDE.md).

## Zależności opcjonalne (kandydaci)

Każda pozycja wymaga testu importu na tej maszynie przed dodaniem.

| Extra | Kandydaci | Warstwa |
|---|---|---|
| (bazowe) | `numpy`, `pandas`, `duckdb` | core, backtest |
| `stats` | `statsmodels`, `scipy` | validation (kointegracja, testy), risk |
| `ui` | (poza pakietem Python) .NET 10, React | presentation (q7) |
