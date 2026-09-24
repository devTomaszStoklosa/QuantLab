# q8-parameter-selection-cpcv - Design

Status: Ready for dev
Owner role: Architect
Upstream: 02-spec.md
ADRs: docs/adr/0002-dual-backtest-engine.md, docs/adr/0004-validation-first-frozen-holdout.md

## Context and constraints

- Strategia (`Strategy.generate_signals(bars, as_of)`) jest bezstanowa wobec silnika: silnik wektorowy podaje wszystkie bary (strategia sama nie patrzy w przyszłość), event-driven — historię do dnia `as_of`.
- Definicja hipotezy buduje strategię, sizer i politykę rebalansu (`build_*`), runner nie rozgałęzia się po typie strategii (CLAUDE.md, zasada 9).
- Walidatory, raport, magazyn wyników i aplikacja pracują na jednym `BacktestRun`; status liczy `concluded_status(walk_forward.passed, holdout_passed)`.
- `q6` ma CSCV/PBO na macierzy zwrotów konfiguracji i rejestr prób z historii gita; DSR liczy próby jako `len(trials)`.
- Zamrożone definicje i ich wyniki nie mogą się zmienić (zrzut bajt w bajt).

## Quality attribute scenarios

| Source | Stimulus | Response | Measure |
|---|---|---|---|
| Badacz | wybór wartości w dniu s | tylko dane sprzed s | test: bar z dnia s zmieniony po fakcie nie zmienia wyboru |
| Deweloper | strategia z doborem w obu silnikach | ten sam wynik | parytet < 1e-9 jak w `q2` |
| Badacz | siatka z jedną wyraźnie najlepszą wartością | CPCV wybiera ją i ścieżki są dodatnie | test syntetyczny |
| Badacz | siatka czystego szumu | mediana Sharpe ścieżek ≈ 0, PBO ≈ 0.5 | test syntetyczny na wielu ziarnach |
| Deweloper | hipotezy bez siatki | bez zmian | zrzut `momentum_v1`, `mean_reversion_v1`, `pairs_v1` bajt w bajt |

## Options

### Decyzja 1 — gdzie żyje procedura doboru

- **A. Strategia-opakowanie `SelectedParameter`.** W dniu wyboru uruchamia silnik wektorowy dla każdej wartości siatki na barach sprzed tego dnia (koszty z definicji), liczy miarę, wybiera i od tej chwili deleguje sygnały do strategii z wybraną wartością; wybór zapamiętany na okres harmonogramu. Jedna strategia dla obu silników — zmiana wartości to zmiana celów, handlowana i kosztowana; walidatory, raport, magazyn i aplikacja działają bez zmian.
- B. Sklejanie przebiegów wartości rok po roku w jeden `BacktestRun` — bez kosztów przejść, łamie kontrakt wyniku (przebieg z jednego silnika) i parytet `q2`.
- C. Runner liczy przebiegi wszystkich wartości i podaje zwroty strategii — `if` po typie hipotezy w runnerze i osobna ścieżka dla silnika event-driven.

### Decyzja 2 — na czym liczyć CPCV

- **A. Macierz dziennych zwrotów netto wartości siatki (jeden przebieg na wartość), CPCV jako arytmetyka na macierzy.** Wybór w podziale jest jeden dla całego podziału, więc zwroty wybranej wartości w okresach testowych to dokładnie jej zwroty z przebiegu; 45 podziałów × K wartości to operacje na wektorach.
- B. Przebieg silnika na podział — koszty przejść między grupami, ale 45 × K przebiegów i nieciągłe zbiory testowe, których silnik nie zna.

Koszt 2A: ścieżka skleja grupy z różnych podziałów, być może z różnymi wybranymi wartościami — przejścia między nimi nie są kosztowane (ograniczenie w raporcie, najwyżej N − 1 przejść na ścieżkę).

### Decyzja 3 — jak liczyć próby siatki

- **A. Definicja ma liczbę konfiguracji (rozmiar siatki albo 1), próg DSR liczy ich sumę na tych samych danych.** Rejestr prób bez zmian; `multiple_testing` dostaje liczbę konfiguracji.
- B. Każda wartość siatki jako osobna „próba" w rejestrze — rejestr przestaje odpowiadać plikom definicji (REQ-610 `q6`).

### Decyzja 4 — bramka in-sample

- **A. Kryterium sukcesu nazywa walidację in-sample (`walk_forward` domyślnie, `cpcv`), rejestr nazw w runnerze jak testy istotności (`q5`).** Status bierze wynik nazwanej bramki.
- B. CPCV zawsze opisowo — walk-forward jednej ścieżki zostaje jedyną bramką; niespójne z celem epiku, jeśli Tomasz wybierze CPCV (pytanie 4).

## Trade-off matrix (1-5)

| Criterion | 1A | 1B | 1C | 2A | 2B | 3A | 3B | 4A | 4B |
|---|---|---|---|---|---|---|---|---|---|
| Zgodność wsteczna (bit w bit) | 5 | 5 | 4 | 5 | 5 | 5 | 3 | 5 | 5 |
| Podstawialność, brak `if` po typie | 5 | 3 | 2 | 5 | 4 | 5 | 3 | 5 | 5 |
| Parytet silników | 5 | 1 | 3 | — | — | — | — | — | — |
| Wierność metody | 5 | 3 | 4 | 4 | 5 | 4 | 4 | 5 | 3 |
| Złożoność | 4 | 3 | 2 | 5 | 2 | 5 | 3 | 4 | 5 |

## Decision

Recommended: **1A, 2A, 3A, 4A**. Procedura doboru to strategia (jedna dla obu silników, koszty przejść w przebiegu), CPCV to arytmetyka na macierzy zwrotów siatki (dokładna dla strategii, której jedynym dopasowaniem jest wybór z siatki), konfiguracje siatki liczą się do progu DSR przez liczbę konfiguracji definicji, a bramkę in-sample wybiera zamrożona definicja. Rezygnujemy ze sklejania przebiegów (1B) i z logiki doboru w runnerze (1C); przebieg silnika na podział CPCV (2B) wraca, gdyby przejścia między grupami okazały się istotne. Revisit if: strategia z doborem ma stan dopasowany na danych inny niż wybór wartości (np. model) — wtedy CPCV potrzebuje przebiegu na podział.

## Diagrams

```
definition (grid, min history, cost model) ──> SelectedParameter(variants, cost model, schedule)
   choice day s: for each value v: vectorized.run(variant(v), bars < s) -> net Sharpe -> argmax
   as_of in [s, next s): delegate generate_signals to variant(best)
                                   │
MembersOnly ─> vectorized / event-driven engine ─> BacktestRun (+ selection history)

training period: one vectorized run per grid value -> returns matrix T x K
   CPCV(N, k, purge, embargo): split -> train mask -> argmax Sharpe -> test returns -> paths
   PBO (q6 CSCV) on the same matrix;  DSR with sum of configurations
```

## Contracts

### Pliki

```
src/quantlab/validation/cpcv.py                 # CpcvSplit, splits, paths, cpcv_of_selection (P2)
src/quantlab/strategy/selected_parameter.py     # SelectedParameter, SelectionRecord (P3)
src/quantlab/research/definition.py             # TimeSeriesMomentumSelectedParameters, configurations (P3, P4)
src/quantlab/reporting/multiple_testing.py      # próg DSR z sumy konfiguracji (P4)
src/quantlab/validation/holdout.py              # SuccessCriterion.in_sample_validation, CpcvSettings (P5)
src/quantlab/cli.py                             # raport doboru, CPCV, PBO siatki; rejestr bramek (P4, P5)
src/quantlab/reporting/results_store.py         # tabele selection, cpcv_paths; schemat v3 (P6)
presentation/…                                  # panel CPCV i historii wyborów (P6)
config/holdout/momentum_select_v1.yaml          # zamrożona definicja (P7)
```

### Kontrakty (sygnatury poglądowe)

```python
# validation/cpcv.py
@dataclass(frozen=True)
class CpcvSplit:
    test_groups: tuple[int, ...]; train: np.ndarray  # bool mask over T periods; test: np.ndarray
def cpcv_splits(n_periods: int, groups: int, test_groups: int, purge: int, embargo: int) -> list[CpcvSplit]: ...
def cpcv_paths(n_periods, groups, test_groups) -> list[list[tuple[int, int]]]  # path -> (group, split index)
class CpcvResult(BaseModel):
    path_sharpes: list[float | None]; chosen: list[str | None]; choice_shares: dict[str, float]; ...
def cpcv_of_selection(returns: np.ndarray, labels: list[str], settings: CpcvSettings, periods_per_year: int) -> CpcvResult: ...

# strategy/selected_parameter.py
class SelectedParameter:
    def __init__(self, variants: dict[str, Callable[[], Strategy]], cost_model: CostModel,
                 min_history_days: int, periods_per_year: int) -> None: ...
    def generate_signals(self, bars, as_of) -> list[Signal]: ...
    @property
    def history(self) -> list[SelectionRecord]: ...
```

## Rollout and rollback

Każdy slice z zielonymi bramkami (CI na Linuksie i Windowsie) i zrzutem trzech zamrożonych hipotez krypto identycznym przed i po:

1. **P1** dokumentacja: story, spec, design.
2. **P2** CPCV: podziały, purging, embargo, ścieżki, ocena procedury doboru na macierzy zwrotów; testy syntetyczne (wyraźnie najlepsza wartość, szum).
3. **P3** strategia `SelectedParameter` i wariant definicji `time_series_momentum_selected`; parytet silników; pomiar czasu.
4. **P4** liczba konfiguracji w progu DSR, PBO siatki, raport w `quantlab run`.
5. **P5** bramka in-sample w kryterium (`walk_forward` | `cpcv`), ustawienia CPCV w definicji.
6. **P6** magazyn wyników (schemat v3), API i aplikacja; hipoteza demonstracyjna `demo_select` w syntetycznym magazynie.
7. **P7** zamrożenie `momentum_select_v1` (odpowiedzi 1–6) — osobny commit przed przebiegiem.
8. Lokalnie: przebieg treningowy, holdout, wpis w dzienniku.

Rollback: `git revert` per slice; żaden slice nie zmienia plików w `config/holdout/` poza P7.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Look-ahead w wyborze (silnik wektorowy podaje wszystkie bary) | średnia | wysoki | opakowanie jawnie obcina bary do dat sprzed dnia wyboru; test ze zmienionym przyszłym barem |
| Przeciek przez okno sygnału w CPCV | średnia | średni | embargo po grupie testowej, zamrożone; opis w raporcie |
| Czas wyboru (K przebiegów na rosnącej historii) | niska | średni | wybór raz na rok, zapamiętany; pomiar w P3 |
| Zmiana DSR innych hipotez przez konfiguracje | pewna | niski | opisowe; wyjaśnione w raporcie i dzienniku |

## Handoff notes

- P2–P6 nie wymagają odpowiedzi na pytania z 01-story; P7 wymaga 1–6.
- Nie uruchamiaj `momentum_select_v1` na danych rynkowych przed P7.
