# q6-advanced-validation-cpcv - Design

Status: Ready for dev
Owner role: Architect
Upstream: 02-spec.md
ADRs: docs/adr/0004-validation-first-frozen-holdout.md, docs/adr/0005-descriptive-reports-no-investment-advice.md

## Context and constraints

- Każda hipoteza ma zacommitowaną definicję w `config/holdout/<id>.yaml` (od `q3`-M1 jedyne źródło jej parametrów); `quantlab run` odmawia przebiegu bez niej (REQ-303). Pliki są więc naturalnym zapisem prób.
- Zamrożone kryteria `momentum_v1` i `mean_reversion_v1` nie zawierają DSR ani PBO i nie mogą się zmienić; `concluded_status` zostaje nietknięty.
- Brak scipy w zależnościach; rozkład normalny i jego odwrotność są w bibliotece standardowej (`statistics.NormalDist`), więc epik nie dodaje zależności natywnej.
- Strategie mają parametry z literatury — nie ma czego dopasowywać między foldami, więc CPCV i purged k-fold nie mają tu zastosowania (01-story, Out of scope).
- Przebieg treningowy jednej hipotezy trwa 1–2 s bez testu permutacyjnego; `quantlab trials` może więc liczyć każdą próbę od nowa.

## Quality attribute scenarios

| Source | Stimulus | Response | Measure |
|---|---|---|---|
| Badacz | usuwa plik definicji nieudanej próby | liczba prób się nie zmienia | test z usuniętym plikiem |
| Badacz | ma niezacommitowany szkic nowej hipotezy | szkic nie jest próbą, `run` innej hipotezy działa | test ze szkicem |
| Recenzent | czyta tear-sheet | widzi PSR, N z listą prób, próg i DSR z adnotacją „poza regułami statusu" | jedna sekcja |
| Deweloper | sprawdza DSR | przykład z pracy daje 0.9004 | test liczbowy |

## Options — skąd bierze się liczba prób

### Option A - Historia gita katalogu definicji

Próbą jest każdy plik `*.yaml` kiedykolwiek dodany do `config/holdout/` w historii bieżącego commita, w ostatniej zacommitowanej wersji. Usunięcie pliku nie usuwa próby; szkic bez commita nie jest próbą.

### Option B - Bieżąca zawartość katalogu

Pliki obecne teraz w `config/holdout/`. Najprostsze, ale usunięcie pliku po nieudanym przebiegu po cichu zmniejsza N — dokładnie ten rodzaj ukrytej próby, przed którym epik ma chronić.

### Option C - Ręcznie prowadzony rejestr (`config/trials.yaml`)

Osobny plik dopisywany przy każdej hipotezie. Drugie źródło prawdy obok definicji; łatwo o nim zapomnieć.

## Trade-off matrix (1-5)

| Criterion | A | B | C |
|---|---|---|---|
| Odporność na ukrycie próby | 5 — usunięcie widoczne w historii | 1 | 2 |
| Jedno źródło prawdy | 5 — definicje | 5 | 2 |
| Złożoność | 3 — kilka wywołań `git log`/`git show` | 5 | 4 |
| Działanie bez gita | 1 | 5 | 5 |

## Decision

Recommended: **Option A**. Rezygnujemy z prostoty B (ukryta próba) i z osobnego rejestru C (drugie źródło prawdy). Konsekwencja: rejestr wymaga repozytorium git — jak `load_frozen_holdout` już dziś. Revisit if: próby zaczną powstawać poza `config/holdout/` (np. przeglądy parametrów w notebookach) — wtedy potrzebny jawny dziennik przebiegów.

Wariancja Sharpe między próbami w DSR: pod hipotezą zerową (1/(T − 1)), bo przy dwóch-trzech próbach wariancji empirycznej nie da się oszacować. Pod H₀ wszystkie próby mają zerowy prawdziwy Sharpe, więc rozrzut ich estymat to sam błąd estymacji — dla Sharpe = 0 jego wariancja nie zależy od skośności i kurtozy.

## Diagrams

```
config/holdout/*.yaml w historii gita
  --registered_trials()--> [Trial(hypothesis, universe, training, last_commit, deleted)]
  --trials_on_same_data(h)--> próby na danych h (N, lista)

przebieg treningowy h (model realistyczny)
  --active_returns()--> r_t od pierwszej pozycji
  PSR(0)   = probabilistic_sharpe_ratio(r, 0)
  SR₀      = expected_max_sharpe(N, variance = 1/(T-1))
  DSR      = probabilistic_sharpe_ratio(r, SR₀)
  -> MultipleTesting -> terminal (`quantlab run`) + tear-sheet (sekcja opisowa)

quantlab trials h
  każda próba -> przebieg treningowy -> r_t
  wspólne daty -> macierz T x N -> probability_of_backtest_overfitting(S = 16) -> PBO
```

## Contracts

### Pliki

```
src/quantlab/validation/sharpe_inference.py   # PSR, próg SR₀, DSR (V1)
src/quantlab/research/trials.py               # Trial, registered_trials, trials_on_same_data (V2)
src/quantlab/validation/pbo.py                # PboResult, probability_of_backtest_overfitting (V3)
src/quantlab/reporting/multiple_testing.py    # active_returns, MultipleTesting, multiple_testing (V4)
src/quantlab/reporting/tear_sheet.py          # sekcja „Wielokrotne testowanie" (V4)
src/quantlab/cli.py                           # linie w `run` (V4), komenda `trials` (V5)
tests/validation/test_sharpe_inference.py     # redukcja do normalnego, przykład z pracy, N = 1
tests/research/test_trials.py                 # tymczasowe repo: usunięcie, zmiana nazwy, szkic, inne dane
tests/validation/test_pbo.py                  # szum ≈ 0.5, przewaga ≈ 0, N = 2, błędy wejścia
```

### Kontrakty (sygnatury poglądowe)

```python
# validation/sharpe_inference.py
def probabilistic_sharpe_ratio(returns: list[float], benchmark: float = 0.0) -> float | None: ...
def expected_max_sharpe(n_trials: int, variance: float) -> float: ...   # SR₀ na okres
def null_sharpe_variance(n_returns: int) -> float: ...                   # 1 / (T - 1)
def deflated_sharpe_ratio(returns: list[float], n_trials: int) -> float | None: ...

# research/trials.py
class Trial(BaseModel):
    hypothesis: str; universe: str; training_start: date; training_end: date
    last_commit: str; deleted: bool
def registered_trials(definitions_dir: Path) -> list[Trial]: ...
def trials_on_same_data(hypothesis: str, trials: list[Trial]) -> list[Trial]: ...

# validation/pbo.py
class PboResult(BaseModel):
    pbo: float; n_configurations: int; n_blocks: int; n_splits: int
    logit_median: float; rows_used: int
def probability_of_backtest_overfitting(returns: np.ndarray, n_blocks: int = 16) -> PboResult: ...

# reporting/multiple_testing.py
def active_returns(run: BacktestRun) -> list[float]: ...    # od pierwszej pozycji
class MultipleTesting(BaseModel):
    psr: float | None; trials: list[str]; threshold_annualized: float; dsr: float | None
def multiple_testing(run: BacktestRun, trials: list[Trial], periods_per_year: int) -> MultipleTesting: ...
```

CSCV liczy sumy i sumy kwadratów zwrotów per blok i kolumnę raz, a Sharpe każdego podziału składa z sum wybranych bloków — 12 870 podziałów bez ponownego przechodzenia po danych.

## Rollout and rollback

Każdy slice z zielonymi testami (`uv run ruff check . && uv run pytest -q`) przed następnym:

1. **V1** PSR, próg SR₀, DSR — funkcje czyste; test przykładu z pracy.
2. **V2** rejestr prób z historii gita.
3. **V3** PBO metodą CSCV.
4. **V4** `MultipleTesting` w `quantlab run` i w tear-sheecie (sekcja opisowa w części treningowej).
5. **V5** `quantlab trials [HYPOTHESIS]`: tabela prób i PBO; odmowa bez zacommitowanych definicji.
6. **V6** lokalne przebiegi (Binance zablokowany w środowisku chmurowym): uzupełnienie wpisu `momentum_v1` i wpis `mean_reversion_v1` (`q3`-M7) z PSR, DSR, N i PBO.

Rollback: `git revert` per slice; żaden slice nie dotyka zamrożonych plików, zapisów otwarcia ani `concluded_status`.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| DSR odczytany jako nowe kryterium dla zamrożonych hipotez | średnia | wysoki | adnotacja „poza regułami statusu" w terminalu i tear-sheecie; REQ-650 |
| Błąd we wzorze PSR/DSR | niska | wysoki | test przykładu z pracy (0.9004) i redukcji do Φ(SR·√(T−1)) |
| Rejestr zależny od kształtu historii gita (rename, merge) | średnia | średni | próby kluczowane `hypothesis`, nie nazwą pliku; testy na tymczasowym repo |
| PBO przy N = 2 przeinterpretowane | wysoka | niski | raport podaje N i znaczenie przy N = 2 |

## Handoff notes

- V1–V3 to czysta matematyka i git — bez danych rynkowych; testy na danych syntetycznych i przykładach z literatury.
- Nie dodawaj DSR ani PBO do `SuccessCriterion` w tym epiku — pierwsza hipoteza, która może je zamrozić, to następna po `mean_reversion_v1`.
