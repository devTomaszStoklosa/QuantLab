# QuantLab

Platforma do prowadzenia systematycznych badań inwestycyjnych: hipoteza, dane, sygnał, backtest, koszty transakcyjne, walidacja out-of-sample, ryzyko i reżimy rynkowe, analiza transakcji. Projekt portfolio pod role Quantitative Developer / Quantitative Analyst / Systematic Trading Research.

Cel nie jest jedna działająca strategia — cel jest pokazanie procesu badawczego: hipoteza, test, walidacja, wniosek, także gdy wniosek to „nie działa".

## Status

MVP zamknięte (`lab-foundation` + `q1-momentum-research-mvp`): pierwsza hipoteza — time-series momentum na BTC-USDT i ETH-USDT — przeszła pełny pipeline (sygnał, silnik wektorowy z testem golden-master, trzy modele kosztów, walk-forward, zamrożony holdout otwarty raz, test permutacyjny, reżimy, stress test, rejestr transakcji, tear-sheet). Wynik: `inconclusive`, opisany w [docs/RESEARCH_LOG.md](docs/RESEARCH_LOG.md).

Rozszerzenia: dwie kolejne hipotezy są zamrożone przed pierwszym przebiegiem i czekają na lokalne przebiegi treningowe — `mean_reversion_v1` (`q3`) i `pairs_v1` (`q4`, pairs trading na kointegracji ETH/BTC). Gotowe są: drugi silnik z egzekucją zleceń (`q2`), PSR, deflated Sharpe i PBO z rejestrem prób liczonym z historii gita (`q6`) oraz warstwa prezentacji (`q7`): API ASP.NET Core i aplikacja React nad magazynem wyników. Szczegóły w [docs/ROADMAP.md](docs/ROADMAP.md).

## Uruchomienie

```bash
uv sync
uv run pytest -q
uv run quantlab run --tear-sheet reports/momentum_v1.html   # okres treningowy; wymaga dostępu do api.binance.com
uv run quantlab open-holdout                                 # holdout już otwarty: pokazuje zapisany wynik
uv run quantlab compare-engines                              # silnik wektorowy vs event-driven, okres treningowy
uv run quantlab trials                                       # wszystkie próby na tych samych danych: PSR, DSR, PBO
uv run quantlab registry                                     # rejestr hipotez w magazynie wyników, bez pobierania danych
```

`quantlab run` zapisuje też dowody hipotezy do magazynu wyników `results/` (Parquet, ignorowany przez gita), z którego czyta warstwa prezentacji (`q7`, [ADR-0008](docs/adr/0008-results-store-parquet-duckdb.md)).

Warstwa prezentacji (`q7`, w toku) — API ASP.NET Core nad magazynem wyników i aplikacja React w design systemie QuantForge; wymaga .NET 10 SDK i Node.js ≥ 22.22:

```bash
dotnet test --solution presentation/QuantLab.Presentation.slnx
(cd presentation/web && npm ci && npm test && npm run build)            # aplikacja do presentation/web/dist, serwowana przez API
dotnet run --project presentation/QuantLab.Api                          # czyta results/ z lokalnych przebiegów; http://localhost:5080/api/hypotheses
dotnet run --project presentation/QuantLab.Api --launch-profile demo    # syntetyczny magazyn demo_* z presentation/fixtures/results; aplikacja: http://localhost:5080
(cd presentation/web && npm run dev)                                    # serwer deweloperski Vite (:5173) z proxy /api do API na :5080
```

Endpointy (tylko odczyt): `GET /api/health`, `/api/hypotheses`, `/api/hypotheses/{id}` (dowody przebiegu), `/api/hypotheses/{id}/equity`, `/api/hypotheses/{id}/trades?instrument=&side=&sort=&order=&offset=&limit=`.

## Stack

Python 3.12 + uv, pandas/numpy, DuckDB + Parquet, statsmodels/scipy, pytest. Warstwa prezentacji (późniejsze rozszerzenie, epik `q7`): ASP.NET Core Web API + React, czytająca wyniki zapisane przez silnik Pythona.

## Dokumentacja

- [docs/PRODUCT.md](docs/PRODUCT.md) — dokumentacja produktowa: czym jest, jakie ma funkcje, jak z nich korzystać.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — warstwy, moduły, model danych, kontrakty.
- [docs/ROADMAP.md](docs/ROADMAP.md) — epiki, slice'y, zakres MVP, rozszerzenia.
- [docs/DATA-SOURCES.md](docs/DATA-SOURCES.md) — źródła danych i licencje.
- [docs/RESEARCH_LOG.md](docs/RESEARCH_LOG.md) — dziennik badawczy: hipotezy, metodologia, wnioski.
- [docs/adr/](docs/adr/) — decyzje architektoniczne z uzasadnieniem.
- [docs/specs/](docs/specs/) — specyfikacje RoleKit per epik (story/spec/design).

## Disclaimer

Wyniki opisują historyczne zachowanie strategii testowych na danych historycznych. To projekt edukacyjny/badawczy, nie porada inwestycyjna.
