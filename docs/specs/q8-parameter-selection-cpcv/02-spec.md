# q8-parameter-selection-cpcv - Specification

Status: Ready for dev
Owner role: BA
Upstream: 01-story.md

## Glossary

| Term | Meaning |
|---|---|
| Siatka | zamrożona lista wartości jednego parametru strategii (np. lookback 30, 60, …, 365 dni); każda wartość to konfiguracja |
| Procedura doboru | reguła wyboru wartości z siatki: miara, historia, harmonogram, minimalna historia, rozstrzyganie remisów — to ją zamraża definicja, nie wartość |
| Dzień wyboru | dzień, od którego obowiązuje nowo wybrana wartość; wybór korzysta wyłącznie z danych sprzed tego dnia |
| Historia zakotwiczona | okno do wyboru od początku dostępnych danych do dnia przed dniem wyboru |
| Grupa | jeden z N ciągłych, prawie równych odcinków okresu treningowego w CPCV |
| Podział | wybór k grup jako zbioru testowego; reszta, bez purgingu i embargo, to zbiór treningowy |
| Purging | usunięcie ze zbioru treningowego okresów tuż przed grupą testową, których zwrot sięga w nią |
| Embargo | usunięcie ze zbioru treningowego okresów tuż po grupie testowej, których sygnał liczony jest z danych z niej |
| Ścieżka | pełny szereg zwrotów spoza próby zbudowany z grup testowych różnych podziałów, każdy okres dokładnie raz |

## Actors and permissions

| Actor | Action | Allowed |
|---|---|---|
| Strategia z doborem | używa baru z dnia wyboru lub późniejszego do wyboru wartości | nie (REQ-802) |
| CPCV | wybiera wartość na zbiorze zawierającym okresy purgingu, embargo albo testowe | nie (REQ-811, REQ-813) |
| Kod epiku | zmienia zamrożone definicje albo wyniki hipotez bez siatki | nie (REQ-860) |

## Functional requirements (EARS)

Procedura doboru

- REQ-801 (AC-1): A hypothesis definition shall be able to replace a strategy parameter with a selection: the grid (at least two distinct ascending values), the selection metric (Sharpe of net daily returns under the definition's realistic cost model), the schedule (a new choice for each calendar year, made on its 1 January), the anchor of the history (`history_start`) and the minimum history before a choice (in days).
- REQ-802 (AC-1): The choice for year Y shall use bars dated before 1 January of Y only. It shall backtest every grid value over one common window, from `history_start` or from the first day on which every value can signal (the latest first bar plus the longest warm-up), whichever is later, to 31 December of Y−1; choose the value with the best metric, ties going to the earlier value in the grid; and signal with it through year Y. With a window shorter than the minimum history, or no value with a defined metric, there shall be no position in year Y.
- REQ-805 (AC-1): A run of a selection hypothesis shall fetch data from the anchor minus the longest warm-up, or from its own start minus that warm-up if earlier, so every choice sees its whole anchored history.
- REQ-803 (AC-1): The selection shall be one strategy for both engines, so a change of value is a change of targets, traded and costed like any other, and engine parity (`q2`) holds.
- REQ-804 (AC-1): The run shall report the selection history: each choice day, every value's metric and the value chosen (or that there was too little history).

CPCV

- REQ-810 (AC-2): Given T periods, N groups and k test groups (1 ≤ k < N ≤ T), the periods shall form N contiguous groups whose sizes differ by at most one (the first T mod N one longer), and every combination of k groups, in lexicographic order, shall be one split: C(N, k) splits.
- REQ-811 (AC-2): A split's training set shall be every period outside its test groups, except the `purge` periods immediately before and the `embargo` periods immediately after each test group.
- REQ-812 (AC-2): There shall be φ = k·C(N, k)/N paths; path j (0-based) shall take each group's periods from the j-th split, in split order, whose test set contains that group, so every path covers every period exactly once.
- REQ-813 (AC-3): The CPCV of a selection procedure shall take one series of net daily returns per grid value over the training period, from one backtest per value (a value's return on a day depends on data up to the day before only). In each split it shall choose the value with the best metric on the split's training periods, ties to the earlier value, and assign that value's returns to the split's test periods.
- REQ-814 (AC-3): The CPCV result shall give each path's annualized Sharpe (undefined without variance), the mean, median, minimum and maximum of the defined ones, the share above zero, and the share of splits choosing each grid value.

Przeuczenie i liczba prób

- REQ-820 (AC-4): Every definition shall have a number of configurations: its grid's size, or 1 without a grid. The DSR threshold shall use the sum of configurations over the trials on the same data, and the report shall show both the trials and that sum.
- REQ-821 (AC-4): For a definition with a grid, the run shall report the PBO (CSCV of `q6`) of the grid's net daily returns over the training period.

Bramka in-sample

- REQ-830 (AC-6): The success criterion shall name its in-sample validation: `walk_forward` (the default, so every frozen definition keeps its meaning) or `cpcv`. With `cpcv` the gate shall pass when the median path Sharpe is above zero, fail when it is at or below zero, and be inconclusive when fewer than half the paths have a defined Sharpe. The status (`concluded_status`) shall take this gate where it took walk-forward.

Raport

- REQ-840 (AC-5): `quantlab run` on a definition with a grid shall print the selection history, the CPCV summary with its settings and the PBO of the grid, and mark as descriptive whatever is not part of the frozen criterion.
- REQ-841 (AC-5): The results store shall hold the selection history and the CPCV paths and summary, and the app shall show them for hypotheses that have them.

Pre-rejestracja i wynik

- REQ-850 (AC-6): The definition shall be committed before any run of it reads market data, with the answers to the story's open questions 1–6.
- REQ-851 (AC-6): The research log entry shall state the status, the CPCV distribution, PBO, DSR with trials and configurations, the selection history, and the comparison with `momentum_v1`.
- REQ-860: Results of every frozen hypothesis without a grid shall be bit-identical before and after each slice (snapshot dump, as in `q5`).

## Business rules

- CPCV ocenia **procedurę** doboru, nie wybraną wartość: ten sam wybór na innym zbiorze treningowym mógłby paść inaczej, i właśnie ten rozrzut jest miarą.
- W CPCV zbiór treningowy może leżeć po testowym — to cecha metody (więcej ścieżek z tych samych danych), a przeciek przez okno sygnału zatrzymuje embargo.
- Selekcja w przebiegu (walk-forward z re-optymalizacją) jest wyłącznie przyczynowa: wybór w dniu s widzi tylko dane sprzed s.
- Liczba konfiguracji jest konserwatywna: wartości siatki są skorelowane, więc liczenie ich jako niezależnych prób zawyża próg DSR — błąd w bezpieczną stronę (jak w `q6`).

## Data and validation

`SelectionParameters` (w definicji hipotezy, wariant strategii z siatką)

| Field | Type | Required | Range or format |
|---|---|---|---|
| `strategy` | enum | tak | np. `time_series_momentum_selected` |
| `lookback_grid` | list[int] | tak | ≥ 2 różne wartości ≥ 1, rosnąco |
| `history_start` | date | tak | początek zakotwiczonej historii wyboru |
| `min_history_days` | int | tak | ≥ 1 |
| `universe`, `cost_model` | — | tak | jak w pozostałych definicjach |

`CpcvSettings` (w definicji hipotezy, gdy bramka `cpcv` albo CPCV opisowo)

| Field | Type | Required | Range or format |
|---|---|---|---|
| `groups` | int | tak | ≥ 3 |
| `test_groups` | int | tak | 1 ≤ `test_groups` < `groups` |
| `purge_days` | int | tak | ≥ 0 |
| `embargo_fraction` | float | tak | [0, 0.1]; embargo = ⌈fraction · T⌉ okresów |

`SuccessCriterion.in_sample_validation`

| Field | Type | Required | Range or format |
|---|---|---|---|
| `in_sample_validation` | enum | nie | `walk_forward` (domyślnie) albo `cpcv` |

## Edge and error cases

- Siatka z powtórzoną wartością albo jedną wartością → błąd walidacji definicji.
- Pierwszy dzień wyboru z historią krótszą niż minimum → brak pozycji do następnego dnia wyboru (nie błąd).
- Wszystkie wartości bez zdefiniowanej miary w dniu wyboru (brak wariancji) → brak pozycji do następnego dnia wyboru.
- T < N → błąd (grupa bez okresów).
- Zbiór treningowy podziału pusty po purgingu i embargo → błąd z nazwą podziału (za duże embargo).
- Wszystkie wartości bez zdefiniowanej miary w zbiorze treningowym podziału → podział bez wyboru; jego okresy testowe liczą się jako brak pozycji (zwrot 0) i raport je wymienia.
- Ścieżka bez wariancji → Sharpe niezdefiniowany, liczony w bramce jako brak.

## Non-functional requirements

- Performance: przebieg `momentum_select_v1` (2 instrumenty × ok. 8 lat, 6 wartości, wybór co rok, CPCV 45 podziałów, 10 000 permutacji) < 2 min na maszynie deweloperskiej. **Pomiar P3 (2026-09-24, dane syntetyczne od 2017-08-17, siatka 30–365):** trzy przebiegi modeli kosztów 5,3 s, porównanie silników (5 przebiegów) 10,0 s, parytet 1,4e-15 — po zamianie sortowania historii przy każdym wywołaniu na wyszukiwanie binarne (przebieg 8 lat: 3,1 → 0,21 s).
- Reproducibility: deterministycznie (remisy po kolejności siatki, CPCV bez losowości).
- Compatibility: hipotezy bez siatki — wyniki co do bitu jak przed epikiem (REQ-860).

## Traceability

| AC | REQ |
|---|---|
| AC-1 | REQ-801, REQ-802, REQ-803, REQ-804, REQ-805 |
| AC-2 | REQ-810, REQ-811, REQ-812 |
| AC-3 | REQ-813, REQ-814 |
| AC-4 | REQ-820, REQ-821 |
| AC-5 | REQ-840, REQ-841 |
| AC-6 | REQ-830, REQ-850, REQ-851 |
| Guardrail | REQ-860 |

## Open questions

| # | Question | Owner |
|---|---|---|
| 1 | Pytania 1–6 z [01-story.md](01-story.md): hipoteza i uniwersum, reguła wyboru, ustawienia CPCV, bramka, okresy, liczba prób | Tomasz |
