# QuantLab

Platforma do prowadzenia systematycznych badań inwestycyjnych: hipoteza, dane, sygnał, backtest, koszty transakcyjne, walidacja out-of-sample, ryzyko i reżimy rynkowe, analiza transakcji. Projekt portfolio pod role Quantitative Developer / Quantitative Analyst / Systematic Trading Research.

Cel nie jest jedna działająca strategia — cel jest pokazanie procesu badawczego: hipoteza, test, walidacja, wniosek, także gdy wniosek to „nie działa".

## Status

Dokumentacja i plan (ADR-y, architektura, roadmap, specyfikacje RoleKit). Kod jeszcze nie istnieje — start od epiku `lab-foundation`, patrz [docs/ROADMAP.md](docs/ROADMAP.md).

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
