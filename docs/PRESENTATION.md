# Warstwa prezentacji

Rozszerzenie `q7` ([specs/q7-dotnet-react-presentation/](specs/q7-dotnet-react-presentation/)): tylko do odczytu API ASP.NET Core i aplikacja React nad [magazynem wyników](RESULTS-STORE.md). Zgodnie z [ADR-0006](adr/0006-dotnet-react-presentation-layer-only.md) warstwa nie liczy żadnych metryk finansowych: wszystkie liczby przychodzą policzone przez Pythona, a `null` znaczy „nieokreślone", nigdy 0. Warstwa nie wywołuje Pythona.

```
quantlab (Python) --zapis--> results/*.parquet --odczyt DuckDB--> QuantLab.Api --JSON /api--> web (React)
```

## Wymagania

- .NET SDK 10 (`global.json`: `10.0.100`, `rollForward: latestFeature`, runner testów Microsoft.Testing.Platform).
- Node.js ≥ 22.22 (`presentation/web/package.json`).
- Projekty .NET kompilują się z `TreatWarningsAsErrors` i `Nullable` (`presentation/Directory.Build.props`), wersje pakietów są centralne (`Directory.Packages.props`).

## Układ katalogu `presentation/`

| Ścieżka | Zawartość |
|---|---|
| `QuantLab.Api/` | minimalne API: `Program.cs`, `Endpoints/ResultsEndpoints.cs`, `Store/` (odczyt DuckDB) |
| `QuantLab.Api.Tests/` | testy xUnit v3: kontrakt na syntetycznym magazynie, środowisko DuckDB, serwowanie aplikacji |
| `web/` | Vite + React + TypeScript; testy Vitest |
| `design-system/` | QuantForge: tokeny, komponenty, wytyczne, generatory podglądów ([README](../presentation/design-system/README.md)) |
| `fixtures/results/` | syntetyczny magazyn wyników do testów i trybu demo ([README](../presentation/fixtures/README.md)) |
| `QuantLab.Presentation.slnx` | solucja .NET |

## API

Konfiguracja: sekcja `Results` w `appsettings.json`, domyślnie `Results:Path = ../../results` (ścieżka względna liczona od katalogu projektu API). Katalog zbudowanej aplikacji ustawia `Web:Root` (domyślnie `../web/dist`); gdy go nie ma, API działa bez statycznych plików.

| Metoda i ścieżka | Odpowiedź |
|---|---|
| `GET /api/health` | `resultsPath`, `exists`, `schemaVersion`, `compatible` |
| `GET /api/hypotheses` | rejestr: wiersze z `hypotheses.parquet` z nagłówkiem ostatniego przebiegu |
| `GET /api/hypotheses/{id}` | hipoteza z dowodami przebiegu: run, metryki, okna walk-forward, reżimy, zwroty miesięczne i roczne, grupy P&L, diagnostyka, wybór parametru, CPCV, narracja |
| `GET /api/hypotheses/{id}/equity` | krzywa kapitału (punkty w kolejności dat) |
| `GET /api/hypotheses/{id}/trades` | strona rejestru transakcji |

Parametry `/trades`: `instrument`, `side` (`long` albo `short`), `sort` (`entryTs` — domyślnie, `exitTs`, `instrumentId`, `size`, `grossPnl`, `costs`, `netPnl`, `holdingDays`), `order` (`asc` albo `desc`), `offset` (≥ 0), `limit` (1–1000, domyślnie 100). Błędny parametr daje 400 z opisem problemu.

Kody błędów (Problem Details):

| Kod | Kiedy |
|---|---|
| 404 | nieznana hipoteza, albo hipoteza bez przebiegu przy `equity` i `trades` (w szczegółach komenda `uv run quantlab run <id>`) |
| 400 | błędny parametr zapytania |
| 503 | magazyn w niezgodnej wersji schematu; komunikat podaje obie wersje |

Punkty końcowe zależą wyłącznie od interfejsu `IResultsStore`; jedyna implementacja, `DuckDbResultsStore`, czyta pliki Parquet przez DuckDB w pamięci. Modele odczytu to rekordy w `Store/Models.cs`, odwzorowanie wierszy w `Store/Rows.cs`.

## Aplikacja React

- Routing po haszu URL: `#/` (rejestr hipotez) i `#/h/<id>` (ekran hipotezy), dzięki czemu API nie potrzebuje trasy zastępczej dla aplikacji.
- Ekran rejestru pokazuje hipotezy, status, bramki i werdykt holdoutu; bez zapisanego holdoutu napis „No verdict until the frozen holdout is opened".
- Ekran hipotezy składa się z paneli: kapitał netto kosztów, porównanie modeli kosztów, walk-forward, wybór parametru i CPCV (`q8`), reżimy, wielokrotne testowanie (PSR/DSR/PBO), narracja, kontrast, zwroty miesięczne, źródła P&L, zamrożona definicja, wynik holdoutu, metadane przebiegu oraz rejestr transakcji (`TradeBlotter`) ze stronicowaniem.
- Warstwy kodu: `api.ts` (klient i typy odpowiadające JSON API), `resource.ts` (hook stanu ładowania), `route.ts`, `format.ts` (formatowanie liczb), `screens/` (ekrany), `design-system.ts` (adapter do komponentów QuantForge).
- Interfejs jest po angielsku (język produktu w brand booku), a narracja wyniku po polsku, jak raporty laboratorium.

## Uruchomienie

Tryb demo na syntetycznym magazynie (jedna komenda po zbudowaniu aplikacji):

```bash
(cd presentation/web && npm ci && npm run build)
dotnet run --project presentation/QuantLab.Api --launch-profile demo   # http://localhost:5080
```

Profil `demo` ustawia `Results__Path=../fixtures/results`. Profil `http` czyta `results/` w katalogu głównym repozytorium, więc wymaga wcześniejszego `uv run quantlab run <hipoteza>`.

Tryb deweloperski aplikacji (hot reload) z proxy do API:

```bash
dotnet run --project presentation/QuantLab.Api --launch-profile demo   # terminal 1, port 5080
cd presentation/web && npm run dev                                       # terminal 2, port 5173, /api -> 5080
```

## Komendy

| Cel | Komenda |
|---|---|
| testy API | `dotnet test --solution presentation/QuantLab.Presentation.slnx` |
| testy aplikacji | `cd presentation/web && npm test` |
| typecheck i build | `cd presentation/web && npm run build` (wynik w `dist/`) |
| sam typecheck | `cd presentation/web && npm run typecheck` |

## Fixtures

Hipotezy `demo_*` w `presentation/fixtures/results/` powstają z pełnego pipeline'u na danych syntetycznych (źródło danych `synthetic`) i nie są wynikami badań: `demo_momentum`, `demo_pairs`, `demo_xsmom` (momentum przekrojowe na syntetycznym point-in-time uniwersum), `demo_select` (wybór parametru z CPCV), `demo_portfolio` (portfel z zapieczętowanym holdoutem). Regeneracja po zmianie tego, co zapisuje magazyn: `QUANTLAB_UPDATE_FIXTURES=1 uv run pytest tests/test_results_fixture.py`.

## Zmiana kontraktu

1. Zmień schemat po stronie Pythona i podnieś `SCHEMA_VERSION` ([RESULTS-STORE.md](RESULTS-STORE.md)).
2. Dostosuj `StoreSchema.cs`, odczyt w `Store/` i modele; zaktualizuj typy w `web/src/api.ts`.
3. Zregeneruj fixtures i uruchom testy .NET oraz aplikacji.
