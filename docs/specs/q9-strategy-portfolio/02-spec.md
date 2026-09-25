# q9-strategy-portfolio - Specification

Status: Ready for dev
Owner role: BA
Upstream: 01-story.md

## Glossary

| Term | Meaning |
|---|---|
| Składnik | zamrożona hipoteza włączona do portfela: jej strategia, sizer, polityka rebalansu i model kosztów z jej definicji |
| Rękaw (sleeve) | przebieg składnika samodzielnie, jak w jego własnym `quantlab run`, na barach sprzed dnia rebalansu portfela |
| Reguła alokacji | funkcja okna dziennych zwrotów netto rękawów → wagi rękawów, nieujemne, sumujące się do 1 |
| Dzień rebalansu | pierwszy dzień handlowy miesiąca; od niego obowiązują nowe wagi rękawów |
| Okno estymacji | ostatnie `window_days` dziennych zwrotów netto rękawa przed dniem rebalansu |
| Rękaw kwalifikowany | rękaw z co najmniej `min_window_days` dziennymi zwrotami od swojego pierwszego niezerowego zwrotu i z niezerową wariancją w oknie; tylko on dostaje wagę |
| Pozycja netto | suma pozycji rękawów w instrumencie pomnożonych przez ich wagi — to, co portfel faktycznie trzyma i czym handluje |
| Wkład w ryzyko | w_i · (Σw)_i / (wᵀΣw): udział rękawu w wariancji portfela; risk parity wyrównuje wkłady |
| Współczynnik dywersyfikacji | (Σ w_i σ_i) / √(wᵀΣw): 1 bez dywersyfikacji, więcej przy nieskorelowanych rękawach |

## Actors and permissions

| Actor | Action | Allowed |
|---|---|---|
| Strategia portfelowa | używa baru z dnia rebalansu lub późniejszego do wag | nie (REQ-913) |
| `open-holdout` portfela | otwiera holdout nachodzący na nieotwarty holdout składnika | nie (REQ-930) |
| Definicja portfela | zmienia parametry składnika albo włącza inny portfel | nie (REQ-920) |
| Kod epiku | zmienia zamrożone definicje albo wyniki hipotez | nie (REQ-960) |

## Functional requirements (EARS)

Reguły alokacji

- REQ-901 (AC-1): An allocation rule shall map a T × K window of the sleeves' daily net returns to K weights, each ≥ 0, summing to 1 over the eligible sleeves and 0 for the others.
- REQ-902 (AC-1): The equal-weight rule shall give each eligible sleeve 1/K', K' being the number of eligible sleeves.
- REQ-903 (AC-1): The inverse-volatility rule shall give each eligible sleeve a weight proportional to 1/σ_i, σ_i the standard deviation (ddof 1) of its returns in the window.
- REQ-904 (AC-1): The risk-parity rule shall give weights whose risk contributions w_i · (Σw)_i are equal across the eligible sleeves to a relative tolerance of 1e-8, Σ the sample covariance of their window returns; with uncorrelated sleeves it shall equal the inverse-volatility weights.
- REQ-905: A sleeve shall be eligible when at least `min_window_days` daily returns have passed since its first non-zero return and its window returns have a non-zero variance; with no eligible sleeve the rule shall give no weights. (A day without a position returns exactly 0: a sleeve that has not traded yet waits, one that trades and is flat for a while — a pair out of its trade — stays eligible.)

Portfel pozycji netto

- REQ-910 (AC-2): On each day the portfolio strategy shall give each instrument the net weight Σ_s w_s · t_{s,i}, w_s the sleeve weights in force and t_{s,i} the target weights sleeve s's own sizer gives its own signals that day; an instrument with net weight 0 shall have no position.
- REQ-911 (AC-2): The portfolio shall be traded by a sizer that keeps the signed net weights its signals carry, so both engines trade and cost only changes of net positions under the portfolio's cost model.
- REQ-912 (AC-2): The vectorized and event-driven engines shall give the same equity for the portfolio within 1e-9, as for single strategies in `q2`.
- REQ-913 (AC-3): The sleeve weights for the month starting on rebalance day d shall come from the frozen allocation rule applied to each sleeve's last `window_days` daily net returns before d, from a standalone run of the sleeve anchored at the definition's `history_start` on bars dated before d only; computed once per month.
- REQ-914 (AC-3): Before the first rebalance day with an eligible sleeve the portfolio shall hold no position.

Definicja

- REQ-920: A portfolio definition shall name at least two distinct components by hypothesis id; each shall be a committed, unchanged frozen definition (as for any run) on the portfolio's universe, and none shall itself be a portfolio.
- REQ-921: The portfolio shall fetch bars from the earliest day any sleeve run needs: `history_start` less the longest warm-up among the components' own fetch starts.
- REQ-922: A portfolio definition shall count as one trial with one configuration on its universe and training period (REQ-820 `q8`).
- REQ-923: Each sleeve's standalone returns shall use the component's own cost model, sizer and rebalance policy; the portfolio's cost model shall apply to its net trades.

Holdout

- REQ-930 (AC-4): When the holdout of a portfolio overlaps the holdout of a component whose one-time opening is not recorded, `open-holdout` shall refuse before fetching any data, naming the components to open first.

Raport

- REQ-940 (AC-5): `quantlab run` on a portfolio shall print and store, as training diagnostics, the correlation of every pair of sleeves' daily net returns over the training period, the median diversification ratio over rebalance days, and each sleeve's mean, lowest and highest weight.
- REQ-941 (AC-5): It shall also report, descriptively, the training net Sharpe of the portfolio under each allocation rule (equal weight, inverse volatility, risk parity) and of each sleeve alone.
- REQ-942 (AC-5): The tear-sheet shall show them in a section of its own, and the results store and the app through their existing diagnostics, without a schema change.
- REQ-943: The synthetic results store shall hold a demonstration portfolio of the synthetic crypto demos.

Pre-rejestracja i wynik

- REQ-950 (AC-6): The definition shall be committed before any run of it reads market data, with the answers to the story's open questions 1–6.
- REQ-951 (AC-6): The research log entry shall state the status, the portfolio's holdout Sharpe against each component's and against equal weights, the correlations, the diversification ratio and DSR with trials and configurations.
- REQ-960: Results of every frozen hypothesis shall be bit-identical before and after each slice (snapshot dump, as in `q5` and `q8`).

## Business rules

- Portfel handluje pozycjami netto: przeciwne pozycje rękawów w tym samym instrumencie znoszą się, zanim powstanie zlecenie. Oszczędność na kosztach to część efektu dywersyfikacji, a nie błąd pomiaru.
- Wagi rękawów są estymowane na zwrotach samodzielnych rękawów (z ich własnymi kosztami), nie na zwrotach portfela: waga nie zależy od siebie samej.
- Reguła alokacji jest zamrożona; pozostałe są pokazywane opisowo, jak modele kosztów w porównaniu — nie są wybierane, więc nie są próbami.
- Holdout składnika otwiera wyłącznie jego własny `open-holdout`. Portfel może patrzeć na okres holdoutu składnika dopiero po zapisanym otwarciu.
- Status portfela liczy się jak każdej hipotezy: bramka in-sample z definicji i werdykt holdoutu.

## Data and validation

Definicja (propozycja, do zamrożenia po pytaniach 1–6):

```yaml
parameters:
  strategy: strategy_portfolio
  components: [momentum_v1, mean_reversion_v1, pairs_v1, momentum_select_v1]
  allocation: inverse_volatility      # equal_weight | inverse_volatility | risk_parity
  window_days: 90
  min_window_days: 60
  history_start: 2018-01-01
  universe: mvp-crypto
  cost_model: {name: realistic, fee_bps: 10, k: 0.05, vol_window: 30}
```

| Field | Validation |
|---|---|
| `components` | ≥ 2, bez powtórzeń, bez id samego portfela; każdy musi mieć zacommitowaną, niezmienioną definicję na tym samym uniwersum, niebędącą portfelem (sprawdzane przy wczytaniu, przed pobraniem danych) |
| `allocation` | nazwa z rejestru reguł alokacji |
| `window_days` | ≥ 2 |
| `min_window_days` | ≥ 2 |
| `history_start` | data; kotwica przebiegów rękawów |

Diagnostyka treningu (tabela `diagnostics` magazynu, bez zmiany schematu v3):

| Title | Labels |
|---|---|
| Korelacje rękawów | `<a> ~ <b>` dla każdej pary, w kolejności składników |
| Wagi rękawów | `<sleeve> mean`, `<sleeve> min`, `<sleeve> max`; `diversification ratio (median)` |
| Sharpe netto: reguły i rękawy | `equal_weight`, `inverse_volatility`, `risk_parity`, `<sleeve>` (każdy rękaw sam) |

## Edge and error cases

- Rękaw bez pozycji w oknie (np. `momentum_select_v1` przed 2020) → zerowa wariancja, niekwalifikowany, waga 0; pozostałe normalizowane.
- Żaden rękaw niekwalifikowany → brak pozycji w tym miesiącu.
- Instrument bez baru na jednym z końców okresu → silnik pomija jego pozycję netto w tym okresie (bez renormalizacji); reguły sizera rękawu (np. „obie nogi pary albo żadna") nie są stosowane ponownie do pozycji netto — ograniczenie opisane w raporcie; na dziennych danych `mvp-crypto` luki są rzadkie.
- Składnik z polityką rebalansu inną niż codzienna (np. `OnSignalChange` z `q5`) → samodzielny rękaw trzyma pozycje dryfujące z cenami, a portfel wraca codziennie do celów netto; pozycje netto odpowiadają wtedy celom, nie pozycjom rękawu. Wszystkie składniki na `mvp-crypto` są codzienne — ograniczenie opisane, nie obsługiwane.
- Składnik usunięty z `config/holdout/` albo zmieniony po zamrożeniu → przebieg portfela odrzucony przed pobraniem danych.
- Składnik na innym uniwersum albo będący portfelem → błąd walidacji definicji.
- Holdout portfela nachodzący na nieotwarty holdout składnika → `open-holdout` odmawia (REQ-930); trening portfela na okresie treningowym składników jest dozwolony.
- Risk parity bez zbieżności w limicie iteracji → błąd z liczbą iteracji i resztą, nie cicha waga.

## Non-functional requirements

- Performance: przebieg treningowy portfela czterech rękawów (72 rebalanse, rękawy zakotwiczone od 2018) z walidacją i 10 000 permutacji < 3 min na maszynie deweloperskiej — pomiar w P3; przekroczenie → pamięć podręczna przebiegów rękawów między miesiącami. **Pomiar P3 (2026-09-25, środowisko chmurowe):** cztery rękawy z zamrożonych definicji krypto na syntetycznych barach 2017-08-17 → 2023-12-31, 72 alokacje: historia rękawów 80 s (ok. 75% to `pairs_v1`, który w każdym wywołaniu przelicza całą historię pary), każdy kolejny przebieg portfela z tą samą historią 3,5 s; szczytowo 200 MB. Historia rękawów jest więc współdzielona przez wszystkie przebiegi jednego `quantlab run` (pamięć kluczowana dniem i treścią barów przed nim); pełny `run` mierzony w P4 — przyspieszenie strategii par dopiero wtedy, pod strażą zrzutu bajt w bajt. **Pomiar P4 (2026-09-25):** pełny `quantlab run` portfela czterech zamrożonych definicji krypto (trening 2018–2023, trzy modele kosztów, walidacja, 10 000 permutacji, rejestr transakcji) na syntetycznych barach od 2017-08-17: 90 s; po przyspieszeniu strategii par (cięcie historii bisekcją, pętla stanów na liczbach Pythona; wyniki `pairs_v1` bajt w bajt jak wcześniej) 64 s, szczytowo 243 MB — na maszynie deweloperskiej ok. 2–3 min.
- Reproducibility: deterministycznie; wagi i przebiegi rękawów nie zależą od kolejności wywołań.
- Compatibility: hipotezy bez portfela — wyniki co do bitu jak przed epikiem (REQ-960); magazyn wyników bez zmiany schematu.

## Traceability

| AC | REQ |
|---|---|
| AC-1 | REQ-901, REQ-902, REQ-903, REQ-904, REQ-905 |
| AC-2 | REQ-910, REQ-911, REQ-912 |
| AC-3 | REQ-913, REQ-914 |
| AC-4 | REQ-930 |
| AC-5 | REQ-940, REQ-941, REQ-942, REQ-943 |
| AC-6 | REQ-950, REQ-951 |
| Definicja | REQ-920, REQ-921, REQ-922, REQ-923 |
| Guardrail | REQ-960 |

## Open questions

| # | Question | Owner |
|---|---|---|
| — | Brak: pytania 1–6 z [01-story.md](01-story.md) rozstrzygnięte 2026-09-25; definicja zamrożona w `config/holdout/portfolio_v1.yaml` | — |
