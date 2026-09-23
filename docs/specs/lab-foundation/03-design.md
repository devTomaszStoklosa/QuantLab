# lab-foundation - Design

Status: Ready for dev
Owner role: Architect
Upstream: 02-spec.md
ADRs: docs/adr/0001-python-uv-single-package.md, docs/adr/0007-binance-not-stooq-for-first-adapter.md

## Context and constraints

- Jeden deweloper, projekt portfolio — kod czytelny bardziej niż uniwersalny.
- Python 3.12 + uv; Windows 10; CPU bez AVX2, 8 GB RAM, bez GPU.
- Repo publiczne od startu — brak kluczy API wymaganych w tym epiku upraszcza sprawę.
- RoleKit: bramki wymagają repozytorium git; artefakty w `docs/specs`.

## Quality attribute scenarios

| Source | Stimulus | Response | Measure |
|---|---|---|---|
| Deweloper | woła `DataProvider.fetch` dla znanego instrumentu | lista `PriceBar` w pamięci | bez ręcznego parsowania CSV |
| Deweloper | woła `fetch` drugi raz dla tego samego zakresu | brak nowego żądania HTTP | trafienie w cache |
| Deweloper | `uv run pytest -q` bez sieci | zielone testy | < 30 s |
| Nowy epik (q1) | zapisuje `BacktestRun` | odczyt z powrotem bez utraty precyzji | DuckDB/Parquet round-trip |

## Options

### Option A - DuckDB + Parquet, adapter Binance

`duckdb` jako silnik zapytań i miejsce metadanych przebiegów, pliki Parquet dla surowych serii cenowych, jeden adapter `BinanceProvider` na start ([ADR-0007](../../adr/0007-binance-not-stooq-for-first-adapter.md) — Stooq odrzucony, blokuje dostęp programistyczny), `requests` + cache na dysku, CLI na `typer`.

### Option B - Tylko pliki CSV/Parquet, bez DuckDB

Zapis i odczyt bezpośrednio przez pandas, bez warstwy zapytań SQL.

### Option C - Baza SQL z serwerem (Postgres)

Serwer bazy danych lokalnie dla metadanych i wyników.

## Trade-off matrix (1-5)

| Criterion | A | B | C |
|---|---|---|---|
| Scenario fit | 5 — zapytania SQL nad wynikami wielu przebiegów od razu dostępne | 3 — agregacje ręcznie w pandas | 5 |
| Complexity | 4 — jedna zależność, bez serwera | 5 — najprościej | 2 — serwer do postawienia i utrzymania |
| Delivery time | 4 | 5 | 2 |
| Operating cost | 5 — embedded, brak serwera | 5 | 3 — RAM na serwer bazy, 8 GB budżetu |
| Risk | 4 — DuckDB jest znany jako działający bez AVX2 na tej klasie maszyn | 4 | 3 — kolejny proces w tle na maszynie z 8 GB RAM |
| Reversibility | 4 — Parquet czytelny też bez DuckDB | 5 | 2 — migracja z serwera trudniejsza |

## Decision

Recommended: **Option A**. Rezygnujemy z: gotowego UI administracyjnego bazy danych (DuckDB nie ma go w standardzie, ale nie jest tu potrzebny). Revisit if: liczba równoczesnych przebiegów/użytkowników kiedykolwiek wymaga prawdziwego serwera (mało prawdopodobne w projekcie solo) — wtedy Postgres.

## Diagrams

```
quantlab CLI
  -> core.data.BinanceProvider --(HTTP, throttled)--> Binance public REST
  -> core.data.BinanceProvider --(cache)--> data/cache/
  -> core.storage --(write)--> DuckDB (metadane) + Parquet (serie cenowe)
  -> core.universe.Universe --(read config)--> data/universe/*.yaml
```

## Contracts

### Pliki

```
src/quantlab/
  cli.py                          # typer: --version
  core/
    data/
      provider.py                  # DataProvider (Protocol), PriceBar, DataNotFoundError
      binance.py                   # BinanceProvider
      cache.py                     # cache na dysku, klucz (source, instrument, start, end)
    universe.py                    # Universe, Instrument, load()
    storage.py                     # write_price_bars, read_price_bars (DuckDB/Parquet)
  config/
    universe.yaml                  # definicja uniwersum MVP
tests/
  core/data/test_binance.py        # na nagranej odpowiedzi JSON, bez sieci
  core/test_storage.py
  test_environment.py              # import numpy, pandas, duckdb + jedna operacja
```

### Kontrakty (sygnatury poglądowe)

```python
class PriceBar(BaseModel):
    instrument_id: str
    ts: date
    open: float
    high: float
    low: float
    close: float
    volume: float
    adj_close: float | None
    source: str

class Instrument(BaseModel):
    id: str
    symbol: str              # symbol Binance, np. "BTCUSDT"
    asset_class: Literal["crypto"]
    quote_asset: str         # np. "USDT" — nie ISO 4217, patrz ADR-0007

class DataProvider(Protocol):
    def fetch(self, instrument: Instrument, start: date, end: date) -> list[PriceBar]: ...

class DataNotFoundError(Exception): ...

class Universe(BaseModel):
    name: str
    asof_date: date
    instruments: list[Instrument]

    @classmethod
    def load(cls, name: str) -> "Universe": ...

def write_price_bars(bars: list[PriceBar]) -> None: ...
def read_price_bars(instrument_id: str, start: date, end: date) -> list[PriceBar]: ...
```

Format Binance zweryfikowany na żywo 2026-09-23 (`GET https://api.binance.com/api/v3/klines?symbol=<SYMBOL>&interval=1d&limit=<N>`, opcjonalnie `startTime`/`endTime` w ms epoch — parametry zakresu dat do potwierdzenia przy implementacji, reszta kształtu odpowiedzi potwierdzona):

- Odpowiedź: tablica świec, każda jako tablica pozycyjna: `[open_time_ms, open, high, low, close, volume, close_time_ms, quote_asset_volume, num_trades, taker_buy_base_volume, taker_buy_quote_volume, ignore]`. Ceny/wolumen jako stringi — rzutować na `float`.
- Błąd nieznanego symbolu: HTTP 400, ciało `{"code": -1121, "msg": "Invalid symbol."}` — to jest sygnał do `DataNotFoundError`, nie ogólny wyjątek HTTP.
- `adj_close` zawsze `None` dla tego źródła (krypto nie ma corporate actions).

### Zależności

Runtime: `duckdb`, `pandas`, `numpy`, `pyarrow` (Parquet), `requests`, `typer`, `pydantic`, `pyyaml` (config uniwersum, F-3). Dev: `pytest`, `ruff`. Każda z częścią natywną trafia do `tests/test_environment.py`.

## Rollout and rollback

1. **F-1** `uv init --package`, `uv python pin 3.12`, ruff, pytest, `tests/test_environment.py`, pusty CLI z `--version`.
2. **F-2** `core.data`: `PriceBar`, `Instrument`, `DataProvider`, `BinanceProvider`, cache na dysku; testy na nagranej odpowiedzi.
3. **F-3** `core.universe`: `Universe.load` ze statycznego YAML.
4. **F-4** `core.storage`: zapis/odczyt DuckDB + Parquet.

Po F-1: ustaw `gates.dev`/`gates.qa` w `.claude/rolekit.json` (patrz CLAUDE.md).

Rollback: `git revert` — brak migracji, brak stanu zewnętrznego poza cache (bezpiecznie usuwalny).

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `duckdb`/`numpy`/`pandas` nie działają bez AVX2 | niska | wysoki | test środowiska jako pierwszy krok F-1 |
| Binance zmienia format odpowiedzi bez ostrzeżenia | niska | średni | adapter za interfejsem, test na nagranej odpowiedzi wykryje regresję |
| Binance zaostrza rate-limit/blokuje IP | niska | średni | throttling po naszej stronie (REQ-004), cache na dysku ogranicza liczbę żądań |
| Przeinżynierowanie fundamentu | średnia | średni | tylko to, co wymaga `q1-momentum-research-mvp`; reszta rośnie z kolejnymi epikami |

## Handoff notes

- Zacznij od F-1 i `tests/test_environment.py` — pierwsze ryzyko na tej maszynie to paczki natywne bez AVX2, nawet jeśli inne repo właściciela już to sprawdziło (inne środowisko `uv`, powtórz test).
- Format Binance już zweryfikowany na żywo (patrz Contracts powyżej) — parametry zakresu dat (`startTime`/`endTime`) i limit paginacji (max świec per żądanie) potwierdź przy pisaniu `BinanceProvider`, nie zgaduj z pamięci.
- Nie commituj bez prośby właściciela.
