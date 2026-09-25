# q10-local-runbook - Design

Status: Ready for dev
Owner role: Architect
Upstream: 02-spec.md
ADRs: docs/adr/0004-validation-first-frozen-holdout.md, docs/adr/0008-results-store-parquet-duckdb.md

## Context and constraints

- Stan badań jest już zapisany: definicje w `config/holdout/` (historia gita: `research.trials`), zapisy otwarć `<id>.opened.json`, magazyn wyników `results/` (rejestr, `run.parquet` z listą prób i wersją schematu), pliki uniwersów, dziennik `docs/RESEARCH_LOG.md`.
- Maszyna deweloperska: Windows 10, PowerShell 5.1 (bez `&&`), i5-2500K bez AVX2; komendy przez `uv run`.
- CLI (`typer`) ma komendy `run`, `open-holdout`, `build-universe`, `registry`; nie ma `__main__`.

## Options

### Decyzja 1 — gdzie żyje runbook

- **A. Komenda `quantlab plan` w Pythonie**: plan jako czysta funkcja stanu (`research.plan`), wykonanie przez procesy `quantlab`. Jedna implementacja na Windows i Linux, testowalna bez sieci.
- B. Skrypt PowerShell — tylko Windows, bez testów w CI, logika stanu w PowerShellu 5.1.
- C. Lista w README — nie wie, co zrobiono; to dzisiejszy problem.

### Decyzja 2 — kiedy przebieg jest zrobiony

- **A. Aktualny przebieg w magazynie (schemat i lista prób)**: magazyn już zapisuje obie rzeczy; nowa próba na tych samych danych zmienia DSR, więc przebieg trzeba powtórzyć.
- B. Dowolny przebieg w magazynie — nieaktualny DSR i przebiegi niewidoczne dla aplikacji po zmianie schematu uchodzą za zrobione.
- C. Przebieg na bieżącym commicie kodu — każda zmiana dokumentacji wymuszałaby powtórkę wszystkiego.

### Decyzja 3 — jak wykonywać kroki

- **A. Każdy krok jako osobny proces (`python -m quantlab …`, `dotnet …`), przez wstrzykiwany wykonawca**; po każdym kroku plan liczony od nowa. Wyjście kroku idzie wprost do terminala; testy podstawiają wykonawcę.
- B. Wywołania funkcji komend w jednym procesie — wspólna pamięć (cache, monkeypatch) między krokami, wyjątki `typer.Exit` jako sterowanie.

### Decyzja 4 — kroki nieodwracalne

- **A. Osobny rodzaj kroku `manual`, którego wykonawca nie przyjmuje** (sprawdzenie w kodzie i test): otwarcie holdoutu, commit, przegląd uniwersum, wpis w dzienniku.
- B. Flaga `--open-holdouts` — jedna flaga od nieodwracalnej operacji na wszystkich hipotezach; wbrew zasadzie przeglądu przed otwarciem.

## Decision

Recommended: **1A, 2A, 3A, 4A.** Revisit if: kroki zaczną wymagać równoległości (długie pobieranie Tiingo obok przebiegów krypto) — wtedy kolejka z zależnościami zamiast listy.

## Diagrams

```
state: definitions (git) ─┐
       opening records ────┤
       results store ──────┼─> research.plan.build_plan(...) -> [Step(key, title, kind, state, reason, command)]
       universe files ─────┤        │
       git status, log ────┘        ├─ quantlab plan        -> table
                                    └─ quantlab plan --run  -> for first pending check/auto step:
                                                                 executor(command) -> ok? rebuild plan : stop (exit 1)
                                                               -> print remaining manual steps
```

## Contracts

```python
# research/plan.py
StepKind = Literal["check", "auto", "manual"]
StepState = Literal["done", "pending", "blocked"]
class Step(BaseModel): key, title, kind, state, reason, command
class RepositoryState(BaseModel): definitions (per hypothesis: config, trials on its data, record exists,
    record committed, stored run (schema, trials) | None, universe available/committed), dotnet on path,
    log headings
def read_state(definitions_dir, store, research_log, ...) -> RepositoryState
def build_plan(state: RepositoryState) -> list[Step]

# cli.py
@app.command("plan") def plan(run: bool = False) -> None
_EXECUTOR: Callable[[list[str]], int]      # subprocess by default, replaced in tests
_NETWORK_CHECKS: dict[str, Callable[[], str | None]]  # None = ok, else the failure
```

Pliki: `src/quantlab/research/plan.py` (stan i plan), `src/quantlab/cli.py` (komenda `plan`), `src/quantlab/__main__.py` (`python -m quantlab`), `tests/research/test_plan.py`, `tests/test_plan_command.py`.

## Rollout and rollback

1. **R1** dokumentacja: 01-story, 02-spec, 03-design, ROADMAP.
2. **R2** stan repozytorium i plan (`research.plan`), `quantlab plan` (bez sieci).
3. **R3** `quantlab plan --run`: sprawdzenia środowiska, wykonawca procesów, zatrzymanie na błędzie, kroki ręczne na końcu.
4. **R4** README: sekcja „Przebiegi lokalne" zamiast rozproszonych list komend; ROADMAP.

Rollback: `git revert` per slice; żaden slice nie zmienia definicji ani wyników hipotez.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Plan uznaje nieaktualny przebieg za zrobiony | średnia | średni | aktualność = schemat i lista prób (REQ-1003); test |
| `--run` wykonuje krok ręczny | niska | wysoki | wykonawca odrzuca rodzaj `manual`; test |
| Testy sięgają do sieci | średnia | niski | sprawdzenia sieci i wykonawca wstrzykiwane |
| Różnice ścieżek Windows/Linux w komendach | średnia | niski | komendy jako listy argumentów, `sys.executable -m quantlab`; CI na obu systemach |

## Handoff notes

- Plan nie zmienia plików; `--run` zmienia tylko to, co zmieniają wykonywane komendy (magazyn, cache, `reports/`, plik uniwersum).
