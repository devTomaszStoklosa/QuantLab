# 0008. Magazyn wyników: tabele Parquet per hipoteza, czytane w .NET przez DuckDB

Status: Accepted

## Context

[ADR-0006](0006-dotnet-react-presentation-layer-only.md) ustala, że warstwa prezentacji (.NET + React) czyta wyniki zapisane przez Pythona z DuckDB/Parquet, bez wywoływania Pythona. Nie ustala formy tego zapisu. Wyniki jednej hipotezy to kilka tabel o różnym kształcie (jeden wiersz podsumowania, metryki per model kosztów, dzienna krzywa kapitału, setki transakcji), zapisywanych przez `quantlab run` wtedy, gdy API może je właśnie czytać — dwa procesy, na Windows z blokadami plików.

## Decision

- Python zapisuje magazyn wyników w katalogu `results/` (ignorowanym przez gita): `hypotheses.parquet` (rejestr wszystkich zacommitowanych definicji) i `<hipoteza>/*.parquet` (ostatni przebieg główny hipotezy, tabela na rodzaj danych). Schemat w [specs/q7-dotnet-react-presentation/02-spec.md](../specs/q7-dotnet-react-presentation/02-spec.md), z kolumną `schema_version`.
- Tabele hipotezy zapisywane są do katalogu tymczasowego i podmieniane w całości — czytelnik widzi stary albo nowy komplet.
- API ASP.NET Core czyta je przez DuckDB.NET (`read_parquet`) na połączeniu w pamięci otwieranym per żądanie; niczego nie trzyma otwartego i niczego nie zapisuje. Dostęp za interfejsem `IResultsStore`.
- Magazyn syntetyczny (hipotezy `demo_*`, wygenerowany pełnym pipeline'em na danych syntetycznych) jest commitowany w `presentation/fixtures/results/` jako wspólny plik testów Pythona i .NET.

## Consequences

- Pozytywne: niezmienne pliki bez blokad między procesami; SQL po stronie API do filtrowania i stronicowania transakcji; ten sam silnik DuckDB w Pythonie i .NET; kontrakt sprawdzany z obu stron na jednym pliku.
- Negatywne: natywna biblioteka DuckDB także w .NET (test środowiska na maszynie bez AVX2); magazyn trzyma tylko ostatni przebieg hipotezy; zmiana schematu wymaga zmiany w dwóch językach w jednym PR.

## Alternatives considered

- **Jedna baza DuckDB** — prostsza lista tabel, ale plik bazy otwarty do zapisu przez jeden proces blokuje pozostałe; API i `quantlab run` blokowałyby się nawzajem.
- **JSON per hipoteza** — najprostszy, ale bez zapytań i poza kontraktem z ADR-0006.
- **Parquet.Net** (bez natywnej biblioteki) — zostaje jako plan awaryjny za `IResultsStore`, gdyby DuckDB.NET nie działało na maszynie deweloperskiej.
