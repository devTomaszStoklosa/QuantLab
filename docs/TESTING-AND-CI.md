# Testy, CI i konwencje pracy

## Warstwy testów

| Warstwa | Gdzie | Co sprawdza | Komenda |
|---|---|---|---|
| Python, jednostkowe i integracyjne | `tests/` (lustro `src/quantlab`) | moduły silnika na syntetycznych świecach budowanych w kodzie testu; bez sieci | `uv run pytest -q` |
| Golden-master silnika | `tests/backtest/vectorized/test_golden_master.py` | wynik znany z góry na danych syntetycznych (np. stały trend), zanim wynik na realnych danych zyska wiarygodność | w `pytest` |
| Parytet silników | `tests/backtest/event_driven/` | silnik event-driven odtwarza wynik wektorowy w przypadkach, w których powinien | w `pytest` |
| Przebiegi end-to-end | `tests/test_*_run.py`, `test_cli.py`, `test_open_holdout.py`, `test_plan_command.py` | pełne ścieżki komend na syntetycznym źródle: gotówka, wiele klas aktywów, portfel, wybór parametru, skalowanie zmienności, jakość danych | w `pytest` |
| Środowisko | `tests/test_environment.py` | import natywnych paczek (bez AVX2), dla każdej nowej zależności natywnej | `uv run pytest -q tests/test_environment.py` |
| Granica publicznego repo | `tests/test_public_repo_hygiene.py` | pliki śledzone przez git: brak plików danych poza `presentation/fixtures/`, brak zbyt dużych plików (limit 500 000 bajtów), brak poświadczeń ([ADR-0010](adr/0010-public-repo-data-boundary.md)) | w `pytest` |
| Fixtures wyników | `tests/test_results_fixture.py` | syntetyczny magazyn w `presentation/fixtures/results/` jest zgodny z tym, co zapisuje kod | `QUANTLAB_UPDATE_FIXTURES=1 uv run pytest tests/test_results_fixture.py` regeneruje |
| API .NET | `presentation/QuantLab.Api.Tests/` | kontrakt API na syntetycznym magazynie, DuckDB w środowisku, serwowanie aplikacji | `dotnet test --solution presentation/QuantLab.Presentation.slnx` |
| Aplikacja React | `presentation/web/src/**/*.test.ts(x)` | formatowanie, routing, ekrany, rejestr transakcji | `cd presentation/web && npm test` |

Zasady:

- Testy Pythona nie używają sieci i nie piszą do prawdziwego magazynu wyników: `tests/conftest.py` podmienia `cli._RESULTS_DIR` na katalog tymczasowy.
- Test rejestru prób (`research/trials.py`) czyta historię gita, więc wymaga pełnego klonu (`fetch-depth: 0` w CI).
- Zmiana rachunku silnika wymaga testu golden-master albo testu o znanym z góry wyniku.

## Lint i formatowanie

```bash
uv run ruff check .
uv run ruff format .          # CI uruchamia: ruff format --check .
```

Konfiguracja w `pyproject.toml`: długość linii 100, cel `py312`.

## CI

Workflow [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) uruchamia się na `push` do `main` i na każdy pull request; ma uprawnienie tylko do odczytu zawartości, a nowszy przebieg tego samego brancha anuluje poprzedni. Każdy job biegnie na `ubuntu-latest` i `windows-latest`.

| Job | Kroki |
|---|---|
| `python` | `uv sync --locked`, `ruff check`, `ruff format --check`, `pytest -q` (pełna historia gita) |
| `dotnet` | SDK z `global.json`, `dotnet test --solution presentation/QuantLab.Presentation.slnx` |
| `web` | Node 22, `npm ci`, `npm test`, `npm run build` w `presentation/web` |

Akcje są przypięte do SHA commitów. Aktualizacje zależności (uv, npm, NuGet, GitHub Actions) zgłasza Dependabot co tydzień, grupowo, z tygodniowym opóźnieniem po wydaniu ([`dependabot.yml`](../.github/dependabot.yml)). CI działa na runnerach z AVX2, a maszyna deweloperska go nie ma, więc przed zmergowaniem PR-a z paczkami natywnymi uruchom lokalnie `tests/test_environment.py` i testy .NET.

## Konwencje pracy

- **Ticket:** zadanie ma GitHub Issue (etykiety z istniejących, np. `bug`, `enhancement`, `documentation`).
- **Branch:** `<typ>/<numer-ticketu>-<krótki-opis>`, typ jak w Conventional Commits (`feat`, `fix`, `refactor`, `docs`, `chore`), z aktualnego `main`. Bez commitów bezpośrednio do `main`.
- **Commity:** komunikaty po angielsku, w stylu Conventional Commits.
- **Pull Request:** opis zawiera, co i dlaczego, jak sprawdzono, co przetestować ręcznie i `Closes #<numer>`. Merge robi właściciel po review; poprawki po review dochodzą kolejnymi commitami.
- **Dane:** nic, co zawiera ceny rynkowe, nie trafia do repozytorium; `data/raw/`, `data/cache/`, `results/` i `reports/` są w `.gitignore`.
- **Holdout:** definicję zamraża się commitem przed pierwszym przebiegiem na danych holdoutu, a plik `<id>.opened.json` commituje się po otwarciu.

## Windows

- PowerShell 5.1 nie ma `&&`; `Set-Content` nie zapisuje domyślnie UTF-8, dodaj `-Encoding utf8`.
- Duże heredoki w Git Bash potrafią kończyć się błędem `unexpected EOF`; zapisz skrypt do pliku i uruchom.
- Uruchamiaj narzędzia Pythona przez `uv run`, nie przez launcher `py`.
