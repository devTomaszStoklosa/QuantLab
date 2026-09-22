# lab-foundation - Design

Status: Ready for dev
Owner role: Architect
Upstream: 02-spec.md
ADRs: docs/adr/0001-python-uv-single-package.md

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

### Option A - DuckDB + Parquet, adapter Stooq

`duckdb` jako silnik zapytań i miejsce metadanych przebiegów, pliki Parquet dla surowych serii cenowych, jeden adapter `StooqProvider` na start, `requests` + cache na dysku, CLI na `typer`.

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
  -> core.data.StooqProvider --(HTTP, throttled)--> Stooq
  -> core.data.StooqProvider --(cache)--> data/cache/
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
      stooq.py                     # StooqProvider
      cache.py                     # cache na dysku, klucz (source, instrument, start, end)
    universe.py                    # Universe, Instrument, load()
    storage.py                     # write_price_bars, read_price_bars (DuckDB/Parquet)
  config/
    universe.yaml                  # definicja uniwersum MVP
tests/
  core/data/test_stooq.py          # na nagranym CSV, bez sieci
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
    symbol: str
    asset_class: Literal["equity_etf", "fx"]
    currency: str  # ISO 4217

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

Dokładny endpoint i format CSV Stooq (parametry URL, nazwy kolumn) sprawdzić w dokumentacji/na żywo przed implementacją `StooqProvider` — nie zgadywać z pamięci.

### Zależności

Runtime: `duckdb`, `pandas`, `numpy`, `pyarrow` (Parquet), `requests`, `typer`, `pydantic`. Dev: `pytest`, `ruff`. Każda z częścią natywną trafia do `tests/test_environment.py`.

## Rollout and rollback

1. **F-1** `uv init --package`, `uv python pin 3.12`, ruff, pytest, `tests/test_environment.py`, pusty CLI z `--version`.
2. **F-2** `core.data`: `PriceBar`, `Instrument`, `DataProvider`, `StooqProvider`, cache na dysku; testy na nagranej odpowiedzi.
3. **F-3** `core.universe`: `Universe.load` ze statycznego YAML.
4. **F-4** `core.storage`: zapis/odczyt DuckDB + Parquet.

Po F-1: ustaw `gates.dev`/`gates.qa` w `.claude/rolekit.json` (patrz CLAUDE.md).

Rollback: `git revert` — brak migracji, brak stanu zewnętrznego poza cache (bezpiecznie usuwalny).

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `duckdb`/`numpy`/`pandas` nie działają bez AVX2 | niska | wysoki | test środowiska jako pierwszy krok F-1 |
| Stooq zmienia format CSV bez ostrzeżenia | średnia | średni | adapter za interfejsem, test na nagranej odpowiedzi wykryje regresję |
| Przeinżynierowanie fundamentu | średnia | średni | tylko to, co wymaga `q1-momentum-research-mvp`; reszta rośnie z kolejnymi epikami |

## Handoff notes

- Zacznij od F-1 i `tests/test_environment.py` — pierwsze ryzyko na tej maszynie to paczki natywne bez AVX2, nawet jeśli inne repo właściciela już to sprawdziło (inne środowisko `uv`, powtórz test).
- Format CSV Stooq (albo wybranego ostatecznie dostawcy) zweryfikuj na żywo przed pisaniem parsera — nie zgaduj kolumn z pamięci.
- Nie commituj bez prośby właściciela.
