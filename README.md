# QuantLab

Platforma do prowadzenia systematycznych badań inwestycyjnych: hipoteza, dane, sygnał, backtest, koszty transakcyjne, walidacja out-of-sample, ryzyko i reżimy rynkowe, analiza transakcji. Projekt portfolio pod role Quantitative Developer / Quantitative Analyst / Systematic Trading Research.

Cel nie jest jedna działająca strategia — cel jest pokazanie procesu badawczego: hipoteza, test, walidacja, wniosek, także gdy wniosek to „nie działa".

## Status

MVP zamknięte (`lab-foundation` + `q1-momentum-research-mvp`): pierwsza hipoteza — time-series momentum na BTC-USDT i ETH-USDT — przeszła pełny pipeline (sygnał, silnik wektorowy z testem golden-master, trzy modele kosztów, walk-forward, zamrożony holdout otwarty raz, test permutacyjny, reżimy, stress test, rejestr transakcji, tear-sheet). Wynik: `inconclusive`, opisany w [docs/RESEARCH_LOG.md](docs/RESEARCH_LOG.md). W toku: `q3-mean-reversion-hypothesis` (druga hipoteza, zamrożona przed pierwszym przebiegiem; czeka na przebieg treningowy) i `q2-event-driven-engine` (drugi silnik z egzekucją zleceń, do opisowego porównania założeń egzekucji), patrz [docs/ROADMAP.md](docs/ROADMAP.md).

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

Warstwa prezentacji (`q7`, w toku) — API ASP.NET Core nad magazynem wyników, wymaga .NET 10 SDK:

```bash
dotnet test --solution presentation/QuantLab.Presentation.slnx
dotnet run --project presentation/QuantLab.Api                          # czyta results/ z lokalnych przebiegów; http://localhost:5080/api/hypotheses
dotnet run --project presentation/QuantLab.Api --launch-profile demo    # syntetyczny magazyn demo_* z presentation/fixtures/results
```

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
