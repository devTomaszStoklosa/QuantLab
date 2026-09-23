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
2. **Research layer** (`quantlab.research`, notebooki) — rejestr `Hypothesis`, eksploracja przed kodem produkcyjnym.
3. **Strategy layer** (`quantlab.strategy`) — interfejs `Strategy.generate_signals`, jedna implementacja per hipoteza.
4. **Backtest engine** (`quantlab.backtest.vectorized`, `quantlab.backtest.event_driven`) — dwa silniki za wspólnym kontraktem `BacktestRun`.
5. **Cost & execution model** (`quantlab.costs`) — interfejs `CostModel`, implementacje naiwna i realistyczna.
6. **Validation layer** (`quantlab.validation`) — interfejs `Validator`: walk-forward, permutacyjny, docelowo purged k-fold/CPCV.
7. **Risk & regime analytics** (`quantlab.risk`) — klasyfikacja reżimów, metryki warunkowe.
8. **Trade & attribution analysis** (`quantlab.attribution`) — rejestr `Trade`, cięcia P&L.
9. **Reporting layer** (`quantlab.reporting`) — tear-sheet z metrykami liczonymi własnym kodem.
10. **Orchestration/CLI** (`quantlab.cli`) — uruchamianie przebiegów, wersjonowanie eksperymentów.
11. **Presentation** (poza pakietem Python, rozszerzenie `q7`) — ASP.NET Core Web API + React, czyta wyniki z DuckDB/Parquet.

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
│   ├── validation/                # Validator + implementacje
│   ├── risk/                      # reżimy, metryki warunkowe
│   ├── attribution/                # Trade ledger, cięcia P&L
│   └── reporting/                 # tear-sheet
├── presentation/                  # rozszerzenie q7: ASP.NET Core + React (nie w MVP)
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

- `DataProvider` (interfejs): `fetch(instrument, start, end) -> list[PriceBar]`. Implementacja: `BinanceProvider` ([ADR-0007](adr/0007-binance-not-stooq-for-first-adapter.md) — Stooq odrzucony, blokuje dostęp programistyczny).
- Kanoniczny schemat `PriceBar`: instrument_id, ts, open, high, low, close, volume, adj_close, source.
- Cache na dysku (`data/cache/`), throttling po stronie klienta, nigdy retry-on-429 jako jedyna ochrona.

### `core.universe`

- `Universe`: nazwa, `asof_date`, lista `Instrument`. MVP: uniwersum statyczne (lista w configu). Point-in-time (zmienny skład w czasie) — rozszerzenie `q5`.

### `backtest` (wspólny kontrakt obu silników)

- Wejście: `StrategyConfig`, `Universe`, zakres dat, `CostModelConfig`, seed.
- Wyjście: `BacktestRun` z referencją do `PortfolioSnapshot[]`, `Trade[]`, `PerformanceMetrics`.
- `BacktestRun` niesie `git_sha` i parametry — reprodukowalność eksperymentu jako wymóg, nie luksus.

### `costs`

- `CostModel` (interfejs): `apply(trade_intent) -> Trade` (z uwzględnieniem spreadu, prowizji, poślizgu).
- Implementacje: `NaiveCostModel` (stałe bps), `RealisticCostModel` (poślizg skalowany zmiennością).

### `validation`

- `Validator` (interfejs): `validate(backtest_run) -> ValidationResult`.
- Implementacje MVP: `WalkForwardValidator`, `PermutationTestValidator`. Docelowo (`q6`): `PurgedKFoldValidator`/CPCV, deflated Sharpe, PBO.
- Holdout: zakres dat i parametry hipotezy zamrożone w pliku commitowanym przed pierwszym uruchomieniem na tym zakresie.

### `risk`

- Klasyfikacja reżimu (`RegimeLabel`) po zmienności zrealizowanej (tercyle) i/lub trend/range.
- Metryki `PerformanceMetrics` liczone warunkowo per reżim.

### `attribution`

- `Trade`: wejście/wyjście, wielkość, P&L brutto/netto, koszty, holding period, reżim w momencie wejścia, siła sygnału.
- Cięcia: po reżimie, holding period, miesiącu, decylu siły sygnału.

### `reporting`

- Metryki własnym kodem: CAGR, Sharpe, Sortino, Calmar, max drawdown, hit rate, profit factor, turnover.
- Wizualizacja (equity curve, drawdown, rolling Sharpe, heatmapa miesięczna) przez matplotlib/plotly — tylko warstwa rysowania.

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
