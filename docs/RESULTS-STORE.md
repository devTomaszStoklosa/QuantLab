# Magazyn wyników

Magazyn wyników to katalog tabel Parquet, w którym silnik Pythona zapisuje dowody przebiegów, a API .NET je czyta ([ADR-0008](adr/0008-results-store-parquet-duckdb.md)). Jest jedynym kontraktem między warstwą obliczeniową a prezentacją: wszystkie liczby są policzone przed zapisem, a API i aplikacja niczego nie wyprowadzają z innych liczb.

Kod zapisu: [`src/quantlab/reporting/results_store.py`](../src/quantlab/reporting/results_store.py). Wymagania i pierwotny schemat: [specs/q7-dotnet-react-presentation/02-spec.md](specs/q7-dotnet-react-presentation/02-spec.md). Gdy ten dokument i kod się różnią, rozstrzyga kod (`RUN_SCHEMA`, `TABLE_SCHEMAS`, `REGISTRY_SCHEMA`, `NARRATIVE_SCHEMA`).

## Układ katalogu

```
results/                          # gitignored: trade ledger zawiera ceny (ADR-0010)
├── hypotheses.parquet            # rejestr: jeden wiersz na zacommitowaną definicję
└── <hipoteza>/                   # ostatni przebieg treningowy hipotezy
    ├── run.parquet               # jeden wiersz: parametry przebiegu i wszystkie bramki
    ├── metrics.parquet           # metryki pod każdym modelem kosztów
    ├── equity.parquet            # krzywa kapitału i obsunięcie
    ├── walk_forward.parquet      # okna roczne i okno zbiorcze
    ├── regimes.parquet           # metryki warunkowe wg reżimu zmienności
    ├── monthly.parquet           # zwroty miesięczne netto
    ├── yearly.parquet            # zwroty roczne netto
    ├── pnl_groups.parquet        # P&L wg reżimu, czasu trzymania, klasy aktywów, instrumentu
    ├── diagnostics.parquet       # diagnostyka treningowa definicji
    ├── selection.parquet         # (q8) historia wyborów parametru
    ├── cpcv_paths.parquet        # (q8) Sharpe ścieżek CPCV
    ├── cpcv_choices.parquet      # (q8) udział wyborów wartości w ścieżkach
    ├── trades.parquet            # rejestr transakcji
    └── narrative.parquet         # opis wyniku z szablonów (q13)
```

Tabele `selection`, `cpcv_paths` i `cpcv_choices` są puste dla hipotez bez siatki parametrów.

## Zapis i spójność

- `quantlab run` zapisuje przebieg przez `write_run`: tabele trafiają do katalogu tymczasowego `.<hipoteza>.new`, a ten podmienia katalog hipotezy w całości. Czytelnik nie zobaczy tabel dwóch przebiegów naraz.
- Nowy przebieg zastępuje poprzedni; magazyn trzyma tylko najnowszy przebieg każdej hipotezy.
- `quantlab registry`, `run` i `open-holdout` odświeżają `hypotheses.parquet` przez `write_registry` (plik zastępowany atomowo) oraz `narrative.parquet` każdej hipotezy z przebiegiem.
- Wartości nieokreślone (brak wariancji, brak pozycji) zapisuje się jako `NULL`, nigdy jako `NaN` ani nieskończoność.

## Wersja schematu

`SCHEMA_VERSION` (obecnie 3) jest zapisana w kolumnie `schema_version` rejestru i `run.parquet`. Zmiana nazwy lub typu kolumny podnosi wersję; API zgłasza niezgodny magazyn w `GET /api/health` (`compatible`) i odmawia odczytu. Dodanie tabeli, którą czytelnicy traktują jako opcjonalną (jak `narrative`), wersji nie podnosi. Przebieg zapisany w starszym schemacie nie liczy się jako wykonany w `quantlab plan`.

## `hypotheses.parquet` (rejestr)

Jeden wiersz na definicję w `config/holdout/`.

| Grupa | Kolumny |
|---|---|
| tożsamość | `schema_version`, `hypothesis`, `strategy`, `universe`, `cost_model`, `parameters` (JSON) |
| okresy | `training_start`, `training_end`, `holdout_start`, `holdout_end` |
| kryterium | `criterion`, `min_sharpe`, `max_p_value`, `significance_test`, `in_sample_validation`, `configurations` |
| zamrożenie | `frozen_at_commit`, `registered_at`, `trials_on_same_data` |
| stan | `status`, `has_run` |
| holdout (NULL do otwarcia) | `holdout_opened_at`, `holdout_opened_at_commit`, `holdout_cost_model`, `holdout_cagr`, `holdout_sharpe`, `holdout_sortino`, `holdout_calmar`, `holdout_max_drawdown`, `holdout_p_value`, `holdout_verdict` |

Status wynika z zapisanych bramek (`concluded_status`), nie jest ręcznie ustawiany.

## `<hipoteza>/run.parquet`

Jeden wiersz. Główne grupy kolumn:

| Grupa | Kolumny |
|---|---|
| przebieg | `run_id`, `strategy`, `universe`, `cost_model`, `strategy_params`, `start`, `end`, `first_position`, `seed`, `git_sha`, `generated_at`, `data_source` |
| koszty | `cost_sensitivity`, `cost_sharpe_difference`, `cost_cagr_sign_flip` |
| walk-forward | `walk_forward_passed`, `walk_forward_rule`, `walk_forward_positive_windows`, `walk_forward_windows_with_sharpe` |
| bramka in-sample | `in_sample_validation`, `in_sample_passed` |
| siatka i CPCV (`q8`, NULL bez siatki) | `grid_start`, `grid_end`, `grid_pbo`, `grid_pbo_blocks`, `grid_pbo_splits`, `cpcv_groups`, `cpcv_test_groups`, `cpcv_purge`, `cpcv_embargo`, `cpcv_splits`, `cpcv_paths`, `cpcv_mean_sharpe`, `cpcv_median_sharpe`, `cpcv_min_sharpe`, `cpcv_max_sharpe`, `cpcv_positive_share`, `cpcv_rule` |
| test istotności | `permutation_passed`, `permutation_test`, `permutation_statistic`, `permutation_count`, `permutation_seed`, `permutation_alpha`, `permutation_active_days`, `permutation_low_confidence`, `permutation_actual`, `permutation_null_mean`, `permutation_null_std`, `permutation_percentile`, `permutation_p_value`, `permutation_reason` |
| wielokrotne testowanie | `trials` (lista), `configurations`, `returns_count`, `sharpe_annualized`, `psr`, `dsr_threshold`, `dsr` |
| kontrast | `contrast_hypothesis`, `contrast_cost_model`, `contrast_correlation` |
| reżimy i transakcje | `regime_method`, `trades`, `trades_open_at_end`, `trades_winning` |

## Tabele przebiegu

| Tabela | Kolumny | Uwagi |
|---|---|---|
| `metrics` | `position`, `cost_model`, `cagr`, `sharpe`, `sortino`, `calmar`, `max_drawdown`, `turnover`, `primary` | wiersz na model kosztów; `primary` wskazuje model przebiegu głównego |
| `equity` | `ts`, `equity`, `drawdown` | kapitał startuje od 1.0 |
| `walk_forward` | `position`, `start`, `end`, `partial`, `aggregate`, `cagr`, `sharpe`, `max_drawdown` | `aggregate` oznacza okno zbiorcze |
| `regimes` | `position`, `regime`, `days`, `share`, `cagr`, `sharpe`, `sortino` | `low`, `medium`, `high`, `undefined` |
| `monthly` | `year`, `month`, `net_return` | |
| `yearly` | `year`, `net_return` | |
| `pnl_groups` | `dimension`, `position`, `key`, `trades`, `win_rate`, `total_net_pnl`, `mean_net_pnl`, `median_net_pnl`, `worst_net_pnl`, `best_net_pnl`, `costs` | `dimension`: `regime`, `holding_period`, `asset_class`, `instrument` |
| `diagnostics` | `position`, `title`, `label`, `value` | wiersze wynikają z definicji (np. skala pozycji, korelacje rękawów) |
| `selection` | `year`, `days`, `position`, `value`, `sharpe`, `chosen` | wartość parametru wybrana w danym roku |
| `cpcv_paths` | `position`, `sharpe` | |
| `cpcv_choices` | `position`, `value`, `share` | |
| `trades` | `trade_id`, `instrument_id`, `side`, `entry_ts`, `entry_price`, `exit_ts`, `exit_price`, `size`, `gross_pnl`, `costs`, `net_pnl`, `holding_days`, `regime_at_entry`, `open_at_end` | zawiera ceny, więc nie jest publiczny |
| `narrative` | `position`, `section`, `text` | akapity `TemplateNarrator` |

## Dane publiczne a lokalne

`results/` jest w `.gitignore`, bo rejestr transakcji niesie ceny rynkowe ([ADR-0010](adr/0010-public-repo-data-boundary.md)). Publiczny jest syntetyczny magazyn `presentation/fixtures/results/` ([PRESENTATION.md](PRESENTATION.md)), generowany pełnym pipeline'em na danych syntetycznych. Granicę pilnuje `tests/test_public_repo_hygiene.py`.

## Zmiana schematu

1. Zmień `RUN_SCHEMA` / `TABLE_SCHEMAS` / `REGISTRY_SCHEMA` i, jeśli kolumna zmienia nazwę lub typ, podnieś `SCHEMA_VERSION`.
2. Zaktualizuj odczyt w `presentation/QuantLab.Api/Store/` i testy kontraktu.
3. Zregeneruj fixtures: `QUANTLAB_UPDATE_FIXTURES=1 uv run pytest tests/test_results_fixture.py` (test jest czerwony, dopóki plik nie jest aktualny).
4. Zaktualizuj ten dokument.
