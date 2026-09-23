# lab-foundation - Specification

Status: Ready for dev
Owner role: BA
Upstream: 01-story.md

## Glossary

| Term | Meaning |
|---|---|
| Instrument | pojedynczy aktyw handlowy (para kryptowalutowa na Binance...) z tożsamością (symbol, klasa aktywów, aktyw kwotowania) |
| PriceBar | jeden słupek OHLCV dla instrumentu i znacznika czasu |
| Kanoniczny schemat | wspólny kształt `PriceBar` niezależny od źródła danych |
| Uniwersum | nazwana lista instrumentów używana w przebiegu |
| DataProvider | interfejs pobierania danych; jedna implementacja na dostawcę |
| Cache | zapis na dysku pobranych danych, kluczowany instrumentem i zakresem dat |

## Actors and permissions

| Actor | Action | Allowed |
|---|---|---|
| Kod epiku q1+ | wywołuje `DataProvider.fetch`, `core.storage`, `Universe.load` | tak |
| Kod epiku q1+ | parsuje CSV dostawcy bezpośrednio, z pominięciem `DataProvider` | nie |
| Test bez sieci | wysyła żądania HTTP | nie |

## Functional requirements (EARS)

Dane

- REQ-001 (AC-2): When `DataProvider.fetch(instrument, start, end)` is called, the provider shall return `PriceBar` records sorted chronologically with no duplicate timestamps.
- REQ-002 (AC-3): When the same instrument and date range were already fetched, the provider shall return cached data without issuing a new HTTP request.
- REQ-003 (AC-4): If the instrument symbol is not recognized by the source, then the provider shall raise a `DataNotFoundError` naming the symbol, not the raw HTTP/library exception.
- REQ-004: The provider shall enforce a minimum delay between HTTP requests to the same source (throttling on our side, not relying on 429 responses).
- REQ-005: Cached responses shall be stored on disk keyed by source, instrument and date range.

Storage

- REQ-010 (AC-5): When `core.storage` writes a list of `PriceBar`, the data shall be readable back with no loss of precision (open/high/low/close/volume as float64).
- REQ-011: The storage layer shall use DuckDB and/or Parquet, not a network database server.

Uniwersum

- REQ-020 (AC-6): When `Universe.load(name)` is called for a statically configured universe, the system shall return the list of instruments with symbol, asset class and quote asset.
- REQ-021: If the universe configuration references an unknown instrument, then loading shall fail with an error naming the missing instrument.

Środowisko i CLI

- REQ-030 (AC-7): The test suite shall include an environment test that imports every native dependency (`numpy`, `pandas`, `duckdb`) and performs one operation with it.
- REQ-031 (AC-1): The test suite shall run with no network access.
- REQ-032 (AC-8): The `quantlab` CLI shall expose a `--version` command.

## Business rules

Cache

| Zakres już w cache | Wynik |
|---|---|
| pełny zakres pokryty | dane z cache, brak żądania HTTP |
| częściowe pokrycie | dociągnięcie tylko brakującej części, potem cache aktualizowany |
| brak pokrycia | pełne pobranie, zapis do cache |

## Data and validation

`PriceBar`

| Field | Type | Required | Range or format | Validation message |
|---|---|---|---|---|
| `instrument_id` | string | tak | zgodny z `Universe` | `Unknown instrument '<id>'` |
| `ts` | date | tak | ISO 8601, bez duplikatów per instrument | `Duplicate bar for <id> at <ts>` |
| `open`, `high`, `low`, `close` | float64 | tak | > 0 | `Non-positive price for <id> at <ts>` |
| `volume` | float64 | tak | >= 0 | `Negative volume for <id> at <ts>` |
| `adj_close` | float64 | nie | > 0 jeśli obecne | – |
| `source` | string | tak | nazwa dostawcy | – |

`Universe`

| Field | Type | Required | Range or format |
|---|---|---|---|
| `name` | string | tak | unikalna |
| `asof_date` | date | tak | – |
| `instruments` | list[Instrument] | tak | niepusta |

## Edge and error cases

- Puste dane zwrócone przez dostawcę dla podanego zakresu → pusta lista, nie błąd (zakres mógł po prostu nie mieć sesji handlowych).
- Zakres dat z weekendami/świętami → dostawca zwraca tylko sesje handlowe, brak sztucznego wypełniania dziur na tym etapie.
- Dostawca zwraca dane z inną strefą czasową niż UTC → normalizacja do UTC przy zapisie.
- Klient HTTP nie skleja ścieżek/URL-i przez konkatenację stringów — przenośność, choć obecna ścieżka repo nie ma spacji.
- Dwa równoległe wywołania `fetch` dla tego samego zakresu → cache nie ulega wyścigowi zapisu (zapis atomowy albo zapis do tymczasowego pliku i rename).

## Non-functional requirements

- Performance: `uv run pytest -q` poniżej 30 s bez sieci.
- Security and privacy: brak kluczy API wymaganych w tym epiku (Binance public REST bez klucza); jeśli źródło z kluczem dojdzie później, klucz tylko w `.env`, nigdy w kodzie.
- Audit and logging: każde pobranie z sieci (nie z cache) loguje źródło, instrument i zakres dat.

## Traceability

| AC | REQ |
|---|---|
| AC-1 | REQ-031 |
| AC-2 | REQ-001 |
| AC-3 | REQ-002, REQ-005 |
| AC-4 | REQ-003 |
| AC-5 | REQ-010, REQ-011 |
| AC-6 | REQ-020 |
| AC-7 | REQ-030 |
| AC-8 | REQ-032 |

## Open questions

| # | Question | Owner |
|---|---|---|
| 1 | ~~Format i endpoint dokładny dla pierwszego adaptera~~ Odpowiedź: Binance REST `api.binance.com/api/v3/klines`, format zweryfikowany na żywo 2026-09-23 (patrz 03-design.md Contracts) | Tomasz |
