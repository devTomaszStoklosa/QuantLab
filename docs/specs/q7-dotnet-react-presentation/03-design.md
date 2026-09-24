# q7-dotnet-react-presentation - Design

Status: Ready for dev
Owner role: Architect
Upstream: 02-spec.md
ADRs: docs/adr/0006-dotnet-react-presentation-layer-only.md, docs/adr/0008-results-store-parquet-duckdb.md

## Context and constraints

- Wszystko, co pokazuje tear-sheet, istnieje już jako modele pydantic (`TearSheet`, `RunMetrics`, `ValidationResult`, `RegimeMetrics`, `MultipleTesting`, `Trade`, `PnlGroup`, `TrainingDiagnostic`, `HoldoutRecord`) — `quantlab run` składa je w jednym miejscu. Magazyn to ich zapis, nie nowe obliczenia (poza miesięcznymi zwrotami, REQ-704).
- ADR-0006: .NET i React tylko czytają wyniki zapisane przez Pythona; żadnego synchronicznego wywołania Pythona.
- Design system QuantForge: 31 komponentów React 18 jako `window.QuantForge` (IIFE czytające `window.React`), typy w `index.d.ts`, tokeny i CSS w `bundle.css`. Język UI produktu: angielski (brand book).
- Środowisko chmurowe: .NET 10 SDK z archiwum Ubuntu (10.0.112), Node 22, dostęp do nuget.org i rejestru npm; bez Binance. Maszyna deweloperska: Windows 10, bez AVX2.
- DuckDB.NET 1.5.5 (ten sam silnik co `duckdb` 1.5.5 w Pythonie) czyta Parquet zapisany przez Pythona — sprawdzone w tym środowisku przed napisaniem tego dokumentu.

## Quality attribute scenarios

| Source | Stimulus | Response | Measure |
|---|---|---|---|
| Recenzent | otwiera aplikację na świeżym klonie bez danych rynkowych | widzi magazyn syntetyczny, jawnie oznaczony | 2 komendy (`dotnet run`, przeglądarka) po `npm run build` |
| Deweloper | zmienia schemat magazynu w Pythonie | test Pythona albo testy .NET są czerwone, zanim UI pokaże złe liczby | test aktualności magazynu syntetycznego + testy .NET na tym samym pliku |
| Badacz | uruchamia `quantlab run` w trakcie, gdy API czyta magazyn | API widzi stary albo nowy komplet tabel hipotezy, nigdy mieszankę | zapis do katalogu tymczasowego i podmiana |
| Deweloper | podmienia źródło wyników (np. inny format) | nowa implementacja `IResultsStore`, endpointy bez zmian | 0 zmian w endpointach |
| Recenzent | sprawdza, czy UI nie liczy metryk | liczby API = liczby magazynu | testy .NET porównujące odpowiedź z bezpośrednim zapytaniem DuckDB |

## Options — jak wyniki przechodzą z Pythona do .NET

### Option A - Tabele Parquet per hipoteza, czytane przez DuckDB.NET

Python zapisuje `results/<hipoteza>/*.parquet` (pyarrow) i `results/hypotheses.parquet`; API odpytuje je SQL-em przez DuckDB.NET (`read_parquet`), połączenie w pamięci na żądanie.

### Option B - Jedna baza DuckDB (`results/quantlab.duckdb`)

Jeden plik z tabelami. DuckDB pozwala otworzyć plik do zapisu tylko jednemu procesowi i blokuje go przed innymi — API trzymające plik blokuje `quantlab run` i odwrotnie (na Windows szczególnie).

### Option C - Dokument JSON per hipoteza

Najprostsze w obu językach, ale bez zapytań (rejestr transakcji filtrowany i sortowany w pamięci) i poza kontraktem „DuckDB/Parquet" z ADR-0006.

### Option D - Parquet czytany przez Parquet.Net (bez natywnej biblioteki)

Brak natywnej zależności w .NET, ale filtr, sortowanie i stronicowanie transakcji ręcznie w LINQ po wczytaniu całości; mapowanie typów Parquet ręcznie.

## Trade-off matrix (1-5)

| Criterion | A | B | C | D |
|---|---|---|---|---|
| Bezpieczeństwo zapisu i odczytu z dwóch procesów | 5 — niezmienne pliki | 2 | 5 | 5 |
| Zgodność z ADR-0006 (DuckDB/Parquet) | 5 | 5 | 1 | 4 |
| Zapytania (filtr, sortowanie, stronicowanie transakcji) | 5 | 5 | 2 | 2 |
| Ryzyko natywnej zależności (maszyna bez AVX2) | 4 — silnik, który już tam działa w Pythonie | 4 | 5 | 5 |
| Złożoność | 4 | 3 | 5 | 3 |

## Decision

Recommended: **Option A** ([ADR-0008](../../adr/0008-results-store-parquet-duckdb.md)). Rezygnujemy z jednej bazy DuckDB (B) — blokady plików między procesami — i z JSON-a (C), który porzuca kontrakt z ADR-0006. Parquet.Net (D) byłby bez natywnej zależności, ale DuckDB już działa na maszynie deweloperskiej, a SQL po stronie API zastępuje ręczne filtrowanie. Konsekwencja: natywna biblioteka DuckDB w .NET dostaje test środowiska. Revisit if: magazyn ma trzymać historię wielu przebiegów (wtedy partycjonowanie po `run_id`) albo DuckDB.NET nie zadziała na maszynie deweloperskiej (wtedy D, bez zmian w endpointach — `IResultsStore`).

Aplikacja React używa design systemu bez przepisywania: `window.React` ustawione przed importem `bundle.js`, typy z `index.d.ts`. Routing na hashu (`#/`, `#/h/<id>`) bez biblioteki routera — dwa ekrany nie uzasadniają zależności.

## Diagrams

```
quantlab run <h>  ─┐
quantlab open-holdout <h> ─┼─> reporting.results_store
quantlab registry ─┘            write_run(results/<h>/)      (run only; tmp dir + swap)
                                write_registry(results/hypotheses.parquet)
                                        │  Parquet (schema v1)
                                        ▼
presentation/QuantLab.Api (ASP.NET Core 10, minimal API)
  IResultsStore ── DuckDbResultsStore (DuckDB.NET, in-memory connection per request)
  GET /api/health | /api/hypotheses | /api/hypotheses/{id} | /equity | /trades
  static files: presentation/web/dist (SPA fallback)
                                        │  JSON (camelCase)
                                        ▼
presentation/web (Vite, React 18, TypeScript)
  design-system.ts: window.React = React; import bundle.js + bundle.css
  #/ RegistryScreen      #/h/<id> HypothesisScreen (+ TradeBlotter)
```

## Contracts

### Pliki

```
src/quantlab/reporting/metrics.py            # monthly_returns (W1)
src/quantlab/reporting/results_store.py      # write_run, write_registry, registry_rows, SCHEMA_VERSION (W1)
src/quantlab/cli.py                          # run / open-holdout zapisują; komenda registry (W1)
tests/reporting/test_results_store.py        # zapis = odczyt, NULL-e, podmiana (W1)
tests/test_results_fixture.py                # generator i test aktualności magazynu syntetycznego (W1)
presentation/fixtures/results/               # magazyn syntetyczny, commitowany (W1)
global.json                                  # SDK 10.0.100, rollForward latestFeature, runner testów MTP (W2)
presentation/Directory.Build.props           # net10.0, Nullable, TreatWarningsAsErrors (W2)
presentation/Directory.Packages.props        # centralne wersje pakietów (W2)
presentation/QuantLab.Presentation.slnx      # (W2)
presentation/QuantLab.Api/                   # Program.cs, Results/*, Endpoints/* (W2, W3)
presentation/QuantLab.Api.Tests/             # EnvironmentTests, testy endpointów (W2, W3)
presentation/web/                            # Vite + React 18 + TS, vitest (W4, W5)
```

### Kontrakty (sygnatury poglądowe)

```python
# reporting/metrics.py
def monthly_returns(dates: list[date], equity: list[float]) -> list[tuple[int, int, float]]: ...

# reporting/results_store.py
SCHEMA_VERSION = 1
def write_run(store: Path, sheet: TearSheet, trades: list[Trade], pnl_groups: dict[str, dict[str, PnlGroup]],
              diagnostics: list[TrainingDiagnostic], cost_sensitivity: CostSensitivity, data_source: str) -> Path: ...
def write_registry(store: Path, holdout_dir: Path) -> list[RegistryRow]: ...
```

```csharp
// QuantLab.Api/Results/IResultsStore.cs
public interface IResultsStore
{
    StoreHealth Health();
    IReadOnlyList<HypothesisSummary> Hypotheses();
    HypothesisDetail? Hypothesis(string id);
    IReadOnlyList<EquityPoint>? Equity(string id);          // null: no run
    TradePage? Trades(string id, TradeQuery query);          // null: no run
}
```

```ts
// web/src/api.ts
export function getHypotheses(): Promise<HypothesisSummary[]>;
export function getHypothesis(id: string): Promise<HypothesisDetail>;
export function getEquity(id: string): Promise<EquityPoint[]>;
export function getTrades(id: string, query: TradeQuery): Promise<TradePage>;
```

## Rollout and rollback

Każdy slice z zielonymi testami przed następnym (`uv run ruff check . && uv run pytest -q`; od W2 także `dotnet test --solution presentation/QuantLab.Presentation.slnx`, od W4 `npm test` w `presentation/web`):

1. **W1** magazyn wyników w Pythonie: `monthly_returns`, `results_store`, zapis w `run` i `open-holdout`, komenda `registry`, `results/` w `.gitignore`, magazyn syntetyczny z testem aktualności. Wydruk `run` bez zmian (poza linią o zapisie magazynu).
2. **W2** szkielet .NET: `global.json`, rozwiązanie, `DuckDbResultsStore` z rejestrem i `health`, strażnik wersji schematu, test środowiska DuckDB, testy na magazynie syntetycznym.
3. **W3** endpointy dowodów hipotezy, krzywej kapitału i transakcji (filtr, sortowanie z białej listy, stronicowanie); testy porównujące odpowiedź z bezpośrednim zapytaniem DuckDB.
4. **W4** aplikacja React: Vite, design system, klient API, rejestr hipotez; API serwuje `web/dist`.
5. **W5** ekran hipotezy i rejestr transakcji.
6. **W6** lokalnie: `dotnet test`, `npm test` i przegląd UI na maszynie deweloperskiej; `quantlab run` na danych Binance zapisuje prawdziwy magazyn (razem z przebiegami M5/P6/E6).

Rollback: `git revert` per slice. W1 zmienia `quantlab run` tylko przez dopisanie zapisu magazynu; W2–W5 dotykają wyłącznie `presentation/`.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| DuckDB.NET nie ładuje natywnej biblioteki na maszynie bez AVX2 | niska | średni | test środowiska; w razie porażki Option D za tym samym `IResultsStore` |
| .NET 10 nie wspiera oficjalnie Windows 10 bez ESU | średnia | średni | `global.json` z roll forward; weryfikacja w W6; UI i Python działają niezależnie |
| Dryf schematu Python → .NET | średnia | wysoki | `schema_version`, 503 przy niezgodności, test aktualności magazynu syntetycznego, testy .NET na nim |
| Wynik syntetyczny wzięty za wynik badania | niska | wysoki | hipotezy `demo_*`, `data_source = synthetic`, ostrzeżenie na każdym ekranie (REQ-743) |
| Surowe ceny w repo przez `trades.parquet` | niska | wysoki | `results/` w `.gitignore`; w repo tylko magazyn syntetyczny |
| Dwie kopie React (aplikacja i bundle) | średnia | średni | bundle czyta `window.React` ustawione z tej samej paczki `react` 18, której używa aplikacja |

## Handoff notes

- Kolejność kolumn i nazwy w magazynie to kontrakt; zmiana nazwy albo typu podnosi `SCHEMA_VERSION` i wersję oczekiwaną przez API w tym samym PR.
- Sortowanie transakcji: nazwy kolumn wyłącznie z białej listy w kodzie, wartości filtrów wyłącznie jako parametry SQL.
- Magazyn syntetyczny generuje się pełnym pipeline'em (`quantlab run` na danych syntetycznych), nie ręcznie — inaczej test .NET sprawdzałby własne założenia, a nie kontrakt.
