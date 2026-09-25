# q10-local-runbook - Specification

Status: Ready for dev
Owner role: BA
Upstream: 01-story.md

## Glossary

| Term | Meaning |
|---|---|
| Krok | jedna pozycja planu: klucz, tytuł, rodzaj, stan, powód, komenda |
| Rodzaj kroku | `check` (sprawdzenie środowiska), `auto` (wykonywany przez `--run`: budowa uniwersum, przebieg treningowy), `manual` (tylko badacz: otwarcie holdoutu, commit, przegląd uniwersum, wpis w dzienniku) |
| Stan | `done` (zrobiony), `pending` (do zrobienia teraz), `blocked` (czeka na inny krok albo warunek; z powodem) |
| Przebieg aktualny | przebieg w magazynie wyników z bieżącym schematem i tą samą listą prób na tych samych danych co dziś |

## Actors and permissions

| Actor | Action | Allowed |
|---|---|---|
| `quantlab plan` | czyta definicje, zapisy otwarć, magazyn, uniwersa, status gita, dziennik | tak, bez sieci i bez zmian w plikach |
| `quantlab plan --run` | wykonuje kroki `check` i `auto` | tak |
| `quantlab plan --run` | otwiera holdout, commituje, pisze w dzienniku, przegląda raport uniwersum | nie (REQ-1021) |

## Functional requirements (EARS)

Plan

- REQ-1001 (AC-1): `quantlab plan` shall list, for every committed definition not deleted, in registration order: its training run, its holdout opening, the commit of its opening record and its research-log entry, each with a state and, when not done, a reason and the command or action that does it.
- REQ-1002 (AC-1): A training run shall be `done` when the results store holds a current run of the hypothesis (REQ-1003), `pending` otherwise, and `blocked` when its universe is not available (REQ-1005).
- REQ-1003 (AC-3): A stored run shall be current when its schema version is the store's and its list of trials equals today's trials on the same data; otherwise the step shall name the reason (another schema version, or the trials added or removed).
- REQ-1004 (AC-2): A holdout opening shall be `done` when its record exists; `blocked` while the training run is not done, or while `holdout_prerequisites` names hypotheses without a record (named in the reason); `pending` otherwise, as a manual step to take after reviewing the training results.
- REQ-1005 (AC-2): A hypothesis on a universe whose file does not exist shall have its training run `blocked`, with a `universe` step before it: `auto` build (`quantlab build-universe`) when the universe has a builder, then `manual` review and commit of the built file while it is not committed.
- REQ-1006 (AC-1): The commit of an opening record shall be `pending` while the record is untracked or modified in git, `done` once committed, `blocked` while there is no record.
- REQ-1007 (AC-1): The research-log entry shall be `done` when `docs/RESEARCH_LOG.md` has an entry heading naming the hypothesis (`## <date> — <hypothesis>…`), `blocked` while the holdout is not opened, `pending` otherwise.

Środowisko

- REQ-1010 (AC-6): The plan shall start with checks: Python native packages (DuckDB and statsmodels import and compute), DuckDB in .NET (`dotnet test … --filter-class QuantLab.Api.Tests.EnvironmentTests`, only if `dotnet` is on the path), Binance reachable (only if a pending step reads Binance), `TIINGO_API_KEY` set (only if a pending step reads Tiingo).
- REQ-1011: `quantlab plan` without `--run` shall not use the network; network checks shall appear as `pending` checks.

Wykonanie

- REQ-1020 (AC-4): `quantlab plan --run` shall execute the `check` and `auto` steps that are `pending`, in plan order, each as its own `quantlab` (or `dotnet`) process; it shall stop at the first failing step with exit code 1, naming it, and after the last step print the manual steps that remain.
- REQ-1021 (AC-5): `--run` shall never execute a `manual` step: holdout openings, commits, universe reviews and research-log entries.
- REQ-1022: A training run executed by `--run` shall write the tear-sheet to `reports/<hypothesis>.html` (git-ignored) besides the results store.
- REQ-1023: After a step succeeds, the plan shall be recomputed before the next one, so a step unblocked by it (e.g. training after a universe build that needs no review) is seen in its new state.

Kompatybilność

- REQ-1030: The epic shall not change any hypothesis's definitions, results or verdicts (regression dump byte for byte).

## Business rules

- Holdout otwiera wyłącznie badacz, po przejrzeniu wyników treningu (zasada 1 i 6 z CLAUDE.md, `q1` REQ-041): plan pokazuje komendę, nie wykonuje jej.
- Plan nie zapisuje niczego sam: jest funkcją stanu repozytorium i magazynu; wykonanie kroków robi `--run`, każdy krok jako zwykła komenda `quantlab`.
- Kolejność planu: sprawdzenia środowiska, uniwersa, przebiegi treningowe (kolejność rejestracji), otwarcia holdoutów, commity zapisów, wpisy w dzienniku.

## Data and validation

Krok (model):

| Field | Type | Meaning |
|---|---|---|
| `key` | str | np. `train:momentum_v1`, `holdout:portfolio_v1`, `check:binance` |
| `title` | str | opis dla człowieka |
| `kind` | `check` \| `auto` \| `manual` | kto wykonuje |
| `state` | `done` \| `pending` \| `blocked` | |
| `reason` | str \| None | dlaczego nie zrobiony albo zablokowany |
| `command` | list[str] \| None | argumenty komendy (`quantlab …`, `dotnet …`, `git …`) |

## Edge and error cases

- Brak magazynu wyników → wszystkie przebiegi `pending` („brak przebiegu").
- Definicja usunięta → nie ma jej w planie (ale liczy się jako próba, więc zmienia aktualność przebiegów innych).
- Składnik portfela zmieniony po zamrożeniu → trening portfela `blocked` z komunikatem wczytania.
- Brak `dotnet` → sprawdzenie .NET pominięte z powodem, nie błąd.
- Brak klucza Tiingo przy `--run` → krok `check:tiingo` kończy się błędem i zatrzymuje wykonanie przed przebiegiem akcji.
- Krok `auto` kończy się błędem (sieć, dane) → `--run` zatrzymuje się, kod wyjścia 1, poprzednie kroki zostają zrobione (magazyn zapisuje przebiegi atomowo, `q7`).

## Non-functional requirements

- `quantlab plan` bez `--run`: < 5 s (bez sieci, bez przebiegów).
- Testy: bez sieci; wykonawca procesów i sprawdzenia sieci wstrzykiwane.

## Traceability

| AC | REQ |
|---|---|
| AC-1 | REQ-1001, REQ-1002, REQ-1006, REQ-1007 |
| AC-2 | REQ-1004, REQ-1005 |
| AC-3 | REQ-1003 |
| AC-4 | REQ-1020, REQ-1022, REQ-1023 |
| AC-5 | REQ-1021 |
| AC-6 | REQ-1010, REQ-1011 |
| Guardrail | REQ-1030 |

## Open questions

| # | Question | Owner |
|---|---|---|
| — | Brak | — |
