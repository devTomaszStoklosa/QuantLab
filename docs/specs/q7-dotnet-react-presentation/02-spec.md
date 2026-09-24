# q7-dotnet-react-presentation - Specification

Status: Ready for dev
Owner role: BA
Upstream: 01-story.md

## Glossary

| Term | Meaning |
|---|---|
| Magazyn wyników | katalog `results/` (konfigurowalny) z tabelami Parquet zapisanymi przez `quantlab`; jedyne źródło danych API |
| Rejestr | `results/hypotheses.parquet` — jeden wiersz na zacommitowaną definicję w `config/holdout/` |
| Przebieg główny | przebieg treningowy pod modelem kosztów z definicji hipotezy (realistycznym) — ten, na którym liczone są walidacja, reżimy i rejestr transakcji, jak w tear-sheecie |
| Wersja schematu | liczba całkowita w rejestrze i w każdym `run.parquet`; zmiana niekompatybilna podnosi ją o 1 |
| Magazyn syntetyczny | magazyn wygenerowany pełnym pipeline'em na danych syntetycznych, z hipotezami `demo_*`, commitowany dla testów .NET i trybu demo UI |

## Actors and permissions

| Actor | Action | Allowed |
|---|---|---|
| `quantlab run`, `quantlab open-holdout`, `quantlab registry` | zapisują magazyn wyników | tak |
| API | czyta magazyn wyników | tak |
| API | zapisuje cokolwiek, wywołuje Pythona, liczy metrykę finansową | nie (REQ-730) |
| UI | liczy metrykę finansową albo status hipotezy | nie (REQ-750) |
| UI | otwiera holdout, rejestruje hipotezę, uruchamia przebieg | nie (poza zakresem; pokazuje komendę CLI) |

## Functional requirements (EARS)

Magazyn wyników (Python)

- REQ-701 (AC-1): When `quantlab run` finishes, the system shall write the primary run's evidence to `results/<hypothesis>/` as the Parquet tables of the schema below, replacing the previous run of that hypothesis.
- REQ-702 (AC-1): The stored numbers shall be the numbers the run computed — no rounding — with undefined values stored as NULL, never as NaN, infinity or 0.
- REQ-703 (AC-1): A hypothesis's tables shall be replaced as a whole: a reader shall never see tables from two different runs of one hypothesis once the write has finished.
- REQ-704 (AC-1): Monthly and yearly net returns of the primary run shall be computed in `quantlab.reporting.metrics`: the equity at the period's last snapshot over the equity at the previous period's last snapshot (the run's first snapshot for the first period), minus 1.
- REQ-705 (AC-1): `run.parquet` shall name the source of the bars the run read (`PriceBar.source`), so that synthetic results are distinguishable from market data.

Rejestr

- REQ-710 (AC-2): `quantlab run`, `quantlab open-holdout` and the new `quantlab registry` shall rewrite `results/hypotheses.parquet` from every committed definition in `config/holdout/`, the holdout records next to them and the git history (commit of freezing, registration time, trials on the same data).
- REQ-711 (AC-2): The registry status shall be computed by Python: with an opened holdout, `concluded_status(walk-forward result of the stored run or none, holdout verdict)`; otherwise `testing` if the store holds a run of the hypothesis and `proposed` if not.
- REQ-712 (AC-2): `quantlab registry` shall print one line per hypothesis with its status and holdout state, and shall not fetch any data.

API (ASP.NET Core, tylko odczyt)

- REQ-720 (AC-3): `GET /api/hypotheses` shall return every registry row with its training Sharpe under the primary cost model (or null without a run) and a sparkline: at most 120 equity values of the primary run taken at evenly spaced snapshots, first and last included.
- REQ-721 (AC-3): `GET /api/hypotheses/{id}` shall return the registry row, the run summary, metrics per cost model, walk-forward windows, regimes, monthly returns, P&L groups and training diagnostics; without a run, `run` shall be null and the lists empty.
- REQ-722 (AC-3): `GET /api/hypotheses/{id}/equity` shall return the primary run's snapshots (date, equity, drawdown) in date order.
- REQ-723 (AC-3): `GET /api/hypotheses/{id}/trades` shall return `{ total, offset, limit, items }` with optional `instrument` and `side` filters, `sort` from a fixed list (default `entryTs`), `order` `asc` or `desc`, `offset` ≥ 0 and `limit` 1..1000 (default 100); ties shall be broken by trade id.
- REQ-724 (AC-3): An unknown hypothesis shall give 404; equity or trades of a hypothesis without a run shall give 404; an invalid query parameter shall give 400; every error body shall be `application/problem+json`.
- REQ-725 (AC-3): When the store's schema version differs from the API's, data endpoints shall give 503 naming both versions; `GET /api/health` shall report the store path, whether it exists, its schema version and whether it is compatible. A missing store shall give an empty registry, not an error.
- REQ-726 (AC-3): JSON shall use camelCase names, ISO dates (`yyyy-MM-dd`), ISO 8601 UTC timestamps and `null` for undefined values.

- REQ-730 (AC-3): The API shall not write files, call Python or compute a financial metric; its numbers shall equal the store's.

UI (React)

- REQ-740 (AC-4): The registry screen shall show status tabs with counts, summary tiles counting confirmed, rejected and inconclusive hypotheses, and a table with each hypothesis's id, strategy, status, training Sharpe, sparkline and holdout seal state.
- REQ-741 (AC-5): The hypothesis screen shall show the frozen definition (parameters, training and holdout ranges, criterion, commit of freezing), the holdout seal or the record of its opening, and — with a run — the verdict or "no verdict until the frozen holdout is opened", headline metrics, metrics per cost model, the equity chart with drawdown, walk-forward windows, the permutation test, regimes, multiple testing, training diagnostics, P&L groups, monthly returns and the trade blotter.
- REQ-742 (AC-5): The trade blotter shall filter by instrument and side, sort by a column header and page through trades, through the API's parameters.
- REQ-743 (AC-5): When a run's data source is `synthetic`, every screen showing its numbers shall carry a warning callout that the numbers are synthetic, not a research result.
- REQ-744 (AC-4, AC-5): A hypothesis without a run shall show "No runs yet" and the command that produces one (`uv run quantlab run <id>`), with no zero-filled chart; an API error shall show a `danger` callout with the error's title.
- REQ-750 (AC-4, AC-5): The UI shall only format numbers (design-system rules: Sharpe 2 dp, returns 1 dp %, p-values 3 dp, U+2212 minus, "—" for null) and shall end every screen with the disclaimer that nothing is a recommendation to trade.

Środowisko

- REQ-760 (AC-6): The .NET SDK shall be pinned by `global.json` in the repository root (10.0.100, roll forward within 10.0, tests on Microsoft.Testing.Platform); the .NET test project shall contain an environment test that loads DuckDB's native library and reads a Parquet file.
- REQ-761 (AC-6): The committed synthetic store shall be regenerated by one documented command, and a Python test shall fail when it differs in content from what the current code writes.

## Business rules

- Status hipotezy — wyłącznie z Pythona (`concluded_status`, REQ-711); UI i API go nie wyprowadzają.
- „Descriptive only": PSR, DSR, reżimy, diagnostyka i cięcia P&L są opisowe, jak w tear-sheecie; UI tak je podpisuje.
- Holdout: liczby holdoutu wyłącznie z zapisu jego jednorazowego otwarcia (REQ-042 z `q1`); zapieczętowany holdout nie ma liczb.

## Data and validation

Magazyn wyników, schemat w wersji 2 (wersja 2 od `q5`-X7b: kolumny `significance_test` w rejestrze i `permutation_test` w `run.parquet`; API czytające wersję 1 odpowiada 503 z prośbą o odświeżenie magazynu). Typy Parquet: `DATE` (date32), `TIMESTAMP` (UTC), `DOUBLE`, `INTEGER` (int64), `BOOLEAN`, `VARCHAR`, `VARCHAR[]`. Kolumny oznaczone `?` mogą być NULL.

`results/hypotheses.parquet` — jeden wiersz na definicję

| Column | Type | Meaning |
|---|---|---|
| `schema_version` | INTEGER | 2 |
| `hypothesis` | VARCHAR | id z definicji |
| `strategy`, `universe`, `cost_model` | VARCHAR | nazwa strategii, uniwersum i modelu kosztów przebiegu głównego |
| `parameters` | VARCHAR | JSON parametrów z definicji |
| `training_start`, `training_end`, `holdout_start`, `holdout_end` | DATE | zakresy z definicji |
| `criterion` | VARCHAR | opis kryterium sukcesu |
| `min_sharpe`, `max_p_value` | DOUBLE | progi kryterium |
| `significance_test` | VARCHAR | test, z którego pochodzi p-value kryterium (i holdoutu): `day_shuffle`, `random_portfolio` (`q5`, REQ-563) |
| `frozen_at_commit` | VARCHAR | ostatni commit definicji |
| `registered_at` | TIMESTAMP | pierwszy commit definicji |
| `trials_on_same_data` | INTEGER | liczba prób na tym uniwersum i okresie treningowym, z usuniętymi |
| `status` | VARCHAR | `proposed`, `testing`, `confirmed`, `rejected`, `inconclusive` |
| `has_run` | BOOLEAN | czy magazyn ma przebieg tej hipotezy |
| `holdout_opened_at`? , `holdout_opened_at_commit`? , `holdout_cost_model`? | TIMESTAMP, VARCHAR, VARCHAR | z zapisu otwarcia |
| `holdout_cagr`?, `holdout_sharpe`?, `holdout_sortino`?, `holdout_calmar`?, `holdout_max_drawdown`?, `holdout_p_value`? | DOUBLE | z zapisu otwarcia |
| `holdout_verdict`? | VARCHAR | `passed`, `inconclusive`, `rejected` |

`results/<hipoteza>/run.parquet` — jeden wiersz

| Column | Type | Meaning |
|---|---|---|
| `schema_version` | INTEGER | 2 |
| `hypothesis`, `run_id`, `strategy`, `universe`, `cost_model` | VARCHAR | z `BacktestRun` |
| `strategy_params` | VARCHAR | JSON |
| `start`, `end` | DATE | okres treningowy przebiegu |
| `first_position`? | DATE | pierwszy dzień z pozycją |
| `seed` | INTEGER | |
| `git_sha` | VARCHAR | commit kodu przebiegu |
| `generated_at` | TIMESTAMP | |
| `data_source` | VARCHAR | źródło barów (`binance`, `synthetic`) |
| `cost_sensitivity`, `cost_sharpe_difference`?, `cost_cagr_sign_flip`? | VARCHAR, DOUBLE, BOOLEAN | wrażliwość na koszty (naiwny vs realistyczny) |
| `walk_forward_passed`?, `walk_forward_rule`, `walk_forward_positive_windows`, `walk_forward_windows_with_sharpe` | BOOLEAN, VARCHAR, INTEGER, INTEGER | |
| `permutation_test` | VARCHAR | który test istotności: `day_shuffle` (tasowanie dni) albo `random_portfolio` (losowe portfele) |
| `permutation_passed`?, `permutation_statistic`, `permutation_count`, `permutation_seed`, `permutation_alpha`, `permutation_active_days`, `permutation_low_confidence` | | parametry testu |
| `permutation_actual`?, `permutation_null_mean`?, `permutation_null_std`?, `permutation_percentile`?, `permutation_p_value`?, `permutation_reason`? | DOUBLE, VARCHAR | wynik albo powód braku |
| `trials` | VARCHAR[] | próby na tych samych danych, od najstarszej |
| `returns_count`, `sharpe_annualized`?, `psr`?, `dsr_threshold`?, `dsr`? | INTEGER, DOUBLE | wielokrotne testowanie |
| `contrast_hypothesis`?, `contrast_cost_model`?, `contrast_correlation`? | VARCHAR, DOUBLE | kontrast (`--contrast`) |
| `regime_method` | VARCHAR | opis klasyfikacji reżimów |
| `trades`, `trades_open_at_end`, `trades_winning` | INTEGER | liczności z rejestru transakcji |

Tabele wielowierszowe w `results/<hipoteza>/` (kolumna `position` to kolejność wyświetlania)

| Table | Columns |
|---|---|
| `metrics` | `position`, `cost_model`, `cagr`?, `sharpe`?, `sortino`?, `calmar`?, `max_drawdown`?, `turnover`, `primary` |
| `equity` | `ts`, `equity`, `drawdown` |
| `walk_forward` | `position`, `start`, `end`, `partial`, `aggregate`, `cagr`?, `sharpe`?, `max_drawdown`? |
| `regimes` | `position`, `regime`, `days`, `share`, `cagr`?, `sharpe`?, `sortino`? |
| `monthly` | `year`, `month`, `net_return` |
| `yearly` | `year`, `net_return` (miesiące składają się w rok; liczone w Pythonie, nie w UI) |
| `pnl_groups` | `dimension` (`regime`, `holding_period`), `position`, `key`, `trades`, `win_rate`, `total_net_pnl`, `mean_net_pnl`, `median_net_pnl`, `worst_net_pnl`, `best_net_pnl`, `costs` |
| `diagnostics` | `position`, `title`, `label`, `value`? |
| `trades` | `trade_id`, `instrument_id`, `side`, `entry_ts`, `entry_price`, `exit_ts`, `exit_price`, `size`, `gross_pnl`, `costs`, `net_pnl`, `holding_days`, `regime_at_entry`, `open_at_end` |

Parametry `GET /api/hypotheses/{id}/trades`

| Parameter | Type | Range |
|---|---|---|
| `instrument` | string | dowolny; brak dopasowania → pusta strona |
| `side` | enum | `long`, `short` |
| `sort` | enum | `entryTs`, `exitTs`, `instrumentId`, `size`, `grossPnl`, `costs`, `netPnl`, `holdingDays` |
| `order` | enum | `asc` (domyślnie), `desc` |
| `offset` | int | ≥ 0 |
| `limit` | int | 1..1000, domyślnie 100 |

## Edge and error cases

- Brak katalogu `results/` → pusty rejestr (200), `health` z `exists: false`; UI pokazuje „No hypotheses in the results store" z komendą `uv run quantlab registry`.
- Hipoteza w rejestrze bez przebiegu → `run: null`, UI „No runs yet".
- Przebieg bez żadnej pozycji → metryki NULL („—"), puste transakcje, reżimy z NULL; bez błędu.
- Definicja usunięta z `config/holdout/` → znika z rejestru przy następnym odświeżeniu; jej katalog wyników zostaje, ale API go nie pokazuje (czyta tylko hipotezy z rejestru); nadal liczy się w `trials_on_same_data`.
- Zapis magazynu przerwany w połowie → poprzednie tabele hipotezy zostają (zapis do katalogu tymczasowego i podmiana).
- Rejestr zapisany starszą wersją schematu → 503 z komunikatem, żeby odświeżyć magazyn (`uv run quantlab registry`, ponowny `run`).

## Non-functional requirements

- Performance: odpowiedź API na magazynie z kilkoma hipotezami i 10 000 transakcji < 200 ms lokalnie; zapis magazynu dodaje < 1 s do `quantlab run`.
- Reproducibility: magazyn syntetyczny deterministyczny (stałe ziarno, stały SHA i czas generacji), więc test aktualności porównuje treść.
- Environment: .NET 10 SDK (10.0.1xx), Node.js ≥ 22.22 (wymóg vitest 5 i jsdom 30), `npm ci` z lockfile'em; testy .NET i UI bez sieci (poza `restore`/`npm ci`).
- Accessibility: komponenty design systemu (focus, kontrast 4.5:1, status zawsze z ikoną i słowem).

## Traceability

| AC | REQ |
|---|---|
| AC-1 | REQ-701, REQ-702, REQ-703, REQ-704, REQ-705 |
| AC-2 | REQ-710, REQ-711, REQ-712 |
| AC-3 | REQ-720, REQ-721, REQ-722, REQ-723, REQ-724, REQ-725, REQ-726, REQ-730 |
| AC-4 | REQ-740, REQ-744, REQ-750 |
| AC-5 | REQ-741, REQ-742, REQ-743, REQ-744, REQ-750 |
| AC-6 | REQ-760, REQ-761 |

## Open questions

Brak.
