# Dziennik badawczy

Chronologiczny zapis hipotez: co testowane, jak, z jakim wynikiem i wnioskiem. Wpis powstaje niezależnie od tego, czy hipoteza się potwierdziła — odrzucona hipoteza opisana rzetelnie jest tu tak samo wartościowa jak potwierdzona.

## Format wpisu

```
## <data> — <nazwa hipotezy>

**Hipoteza:** jedno zdanie, co testujemy.
**Metodologia:** dane, zakres dat, silnik, model kosztów, metoda walidacji, zamrożony holdout (link do commita/pliku z zamrożonymi parametrami).
**Wynik:** kluczowe liczby (Sharpe, max DD, wynik testu istotności) — na okresie treningowym i na holdout.
**Wniosek:** confirmed / rejected / inconclusive, z uzasadnieniem. Co dalej.
```

## Wpisy

## 2026-09-24 — momentum_v1: time-series momentum na BTC-USDT i ETH-USDT

**Hipoteza:** time-series momentum działa na koszyku par kryptowalutowych — pozycja długa lub krótka według znaku własnego zwrotu instrumentu z ostatnich 12 miesięcy (Moskowitz/Ooi/Pedersen 2012) daje dodatni wynik netto po kosztach, a jej wyczucie momentu (timing) jest lepsze niż przypadek.

**Metodologia:**

- **Dane:** Binance spot, świece dzienne (cena zamknięcia), BTC-USDT i ETH-USDT (uniwersum `mvp-crypto`, ustalone przed pierwszym przebiegiem). Dane zaczynają się 2017-08-17; bez luk i duplikatów w obu okresach.
- **Sygnał:** znak zwrotu 365-dniowego, osobno dla każdego instrumentu: long, short albo brak pozycji. Lookback wzięty z literatury, niedopasowywany do danych — nie było czego optymalizować.
- **Silnik:** wektorowy, z testem golden-master (S5). Równe wagi po znaku sygnału między aktywnymi instrumentami, rebalans dzienny na zamknięciu. Sygnał z dnia t decyduje o pozycji na okres t → t+1, więc bez look-ahead.
- **Koszty:** trzy modele na tych samych sygnałach i danych — `zero-cost` (wynik brutto), `naive-10bps` (opłata Binance 0.1%) i `realistic-10bps-k0.05-vol30d` (opłata plus poślizg 0.05 × zmienność 30-dniowa). Model realistyczny jest główny: na nim liczone są walidacja, reżimy, stress test i rejestr transakcji.
- **Okres treningowy:** 2018-01-01 → 2023-12-31; pierwsza pozycja 2018-08-18, po 365 dniach rozgrzewki sygnału.
- **Holdout:** 2024-01-01 → 2025-12-31. Zakres, parametry i kryterium sukcesu zamrożone w [config/holdout/momentum_v1.yaml](../config/holdout/momentum_v1.yaml) (commit `a9cb0b0`) przed jakimkolwiek odczytem danych z tego zakresu. Otwarty dokładnie raz, 2026-09-23 14:01 UTC (commit `ea7be8c`); zapis otwarcia: [config/holdout/momentum_v1.opened.json](../config/holdout/momentum_v1.opened.json) (commit `1daf4f5`).
- **Walidacja:**
  - walk-forward: okna roczne od pierwszej pozycji; reguła ustalona przed wynikami per okno (commit `556dd98`): Sharpe > 0 w co najmniej 2/3 okien i łączny Sharpe > 0;
  - test permutacyjny: 10 000 przetasowań dziennych zwrotów względem faktycznie trzymanych pozycji, seed 0, statystyka: roczny Sharpe zwrotów brutto, α = 0.1;
  - kryterium holdoutu (zamrożone): Sharpe netto (model realistyczny) > 0 i p < 0.1; Sharpe ≤ 0 → `rejected`; Sharpe > 0 i p ≥ 0.1 → `inconclusive`.
- **Status końcowy** (reguły z 02-spec): `confirmed` tylko przy zaliczonym walk-forward i zaliczonym holdoucie (REQ-090); niezaliczona bramka → `rejected`; pozostałe przypadki → `inconclusive`. Liczy go kod: `research.hypothesis.concluded_status`.

**Wynik — okres treningowy 2018–2023** (liczby opisowe dla tego okresu, bez holdoutu):

| Metryka | `zero-cost` (brutto) | `naive-10bps` | `realistic` |
|---|---:|---:|---:|
| CAGR | 13.01% | 10.78% | 6.50% |
| Sharpe | 0.52 | 0.49 | 0.43 |
| Sortino | 0.72 | 0.68 | 0.59 |
| Calmar | 0.15 | 0.12 | 0.07 |
| Max drawdown | −86.70% | −87.32% | −88.74% |

- **Koszty:** różnica Sharpe między modelem naiwnym a realistycznym to 0.06, więc według reguły wynik jest „robust" — ale tylko w tym sensie, że założenia kosztowe nie zmieniają jakościowego wniosku. Realistyczne koszty zmniejszają CAGR o połowę względem wyniku brutto; są małe jedynie wobec ogromnej zmienności strategii.
- **Walk-forward (realistic): zaliczony**, 5 z 6 okien ze Sharpe > 0.

  | Okno | CAGR | Sharpe | Max drawdown |
  |---|---:|---:|---:|
  | 2018-08-18 → 2018-12-31 (niepełny rok) | 16.43% | 0.58 | −34.15% |
  | 2019 | −63.32% | −1.71 | −68.32% |
  | 2020 | 18.47% | 0.65 | −71.63% |
  | 2021 | 194.53% | 1.66 | −52.06% |
  | 2022 | 16.88% | 0.56 | −44.43% |
  | 2023 | −7.88% | 0.01 | −49.49% |
  | Łącznie | 7.28% | 0.45 | −88.74% |

  Zaliczenie jest na granicy: rok 2023 liczy się jako dodatni przy Sharpe 0.01 i CAGR −7.88%; bez niepełnego roku 2018 i przy 2023 uznanym za niedodatni reguła nie byłaby spełniona (3 z 5). O skali wyniku decyduje rok 2021.
- **Test permutacyjny:** Sharpe brutto 0.52 wobec średniej przetasowań 0.08 (odch. std. 0.41); wyższy niż 86.0% przetasowań; **p = 0.140**, nieistotny przy α = 0.1.
- **Reżimy zmienności** (tercyl 30-dniowej zmienności BTC-USDT wobec ostatnich 365 dni; opisowe, poza regułami): cały dodatni wynik pochodzi z dni o średniej zmienności (CAGR 164.55%, Sharpe 1.81). W reżimie niskim (CAGR −32.09%, Sharpe −0.36) i wysokim (CAGR −16.25%, Sharpe 0.15) strategia traciła.
- **Transakcje:** 66 transakcji, 30.3% z dodatnim P&L netto; suma P&L netto transakcji (+0.4590 przy kapitale startowym 1.00) równa się zmianie kapitału. 9 transakcji trzymanych ponad 90 dni dało +0.94, pozostałe 57 łącznie −0.48; jedna transakcja przyniosła +0.82. To profil trend-following: wiele małych strat i kilka dużych zysków, ale oparty na garstce transakcji.
- **Stress test** (pozycje z 2023-12-31, obie długie): natychmiastowy spadek o 20% → −20.00% kapitału; powtórka najgorszego dnia BTC w okresie (2020-03-12: BTC −39.5%, ETH −44.6%) → −42.05%.

**Wynik — holdout 2024–2025** (jednorazowe otwarcie, model realistyczny; liczby z zapisu otwarcia, nie łączone z treningiem):

| Metryka | Holdout |
|---|---:|
| CAGR | 6.45% |
| Sharpe netto | 0.37 |
| Sortino | 0.54 |
| Calmar | 0.13 |
| Max drawdown | −48.35% |
| p (test permutacyjny) | 0.614 |

Test permutacyjny na holdoucie: Sharpe brutto 0.42 wobec średniej przetasowań 0.56 (odch. std. 0.51) — faktyczny timing wypadł **gorzej** niż przeciętne losowe sparowanie tych samych pozycji z tymi samymi zwrotami (wyższy niż tylko 38.7% przetasowań). Strategia miała pozycję we wszystkich 730 dniach holdoutu, więc wynik nie ma flagi niskiej wiarygodności. **Werdykt holdoutu: `inconclusive`** (Sharpe 0.37 > 0, ale p ≥ 0.1).

**Wniosek: `inconclusive`.**

Status wynika mechanicznie z reguł zapisanych przed wynikami: walk-forward zaliczony, holdout `inconclusive` → `inconclusive`. `confirmed` wymagałby zaliczenia obu bramek.

Co mówią liczby poza samym słowem werdyktu:

1. **Nie ma dowodu na efekt timingu.** Na treningu p = 0.14; na holdoucie p = 0.61, a Sharpe brutto jest niższy od średniej przetasowań. Dodatni wynik holdoutu wynika z przewagi pozycji długich w latach wzrostów 2024–2025, nie z trafnego wyczucia momentu. Kryterium zamrożone przed otwarciem rezerwuje `rejected` dla Sharpe ≤ 0, więc hipoteza formalnie nie jest odrzucona — ale dane nie dają podstaw, by twierdzić, że momentum 12-miesięczne ma na tym koszyku przewagę nad przypadkiem.
2. **Wynik treningowy jest kruchy.** Opiera się na kilku długich transakcjach, na jednym roku (2021) i na jednym reżimie zmienności; walk-forward przechodzi na granicy reguły.
3. **Ryzyko jest skrajne.** Max drawdown −88.7% w treningu i −48.4% w holdoucie; w każdym roku treningowym obsunięcie przekroczyło 34%.

Ograniczenia tego badania:

- Tylko dwa, silnie skorelowane instrumenty, więc mało niezależnych sygnałów; to dokładnie warunek „Revisit if" z [03-design](specs/q1-momentum-research-mvp/03-design.md).
- Krótka historia: ok. 5.4 roku od pierwszej pozycji w treningu i 2 lata holdoutu, więc testy mają małą moc — co było wiadome przy zamrażaniu kryterium.
- Część reguły walk-forward (łączny Sharpe > 0) była już znana w chwili jej ustalania, bo pełny wynik treningowy z kosztami powstał wcześniej (S8). Niezależna od wyniku była tylko część dotycząca okien.
- Koszty bez market impact (silnik liczy na znormalizowanym kapitale, bez nominału); egzekucja po cenie zamknięcia, bez częściowych wypełnień — to zakres silnika event-driven (`q2`).
- Liczby treningowe pochodzą z przebiegów `uv run quantlab run` na danych Binance, zapisanych w PR [#18](https://github.com/devTomaszStoklosa/QuantLab/pull/18), [#20](https://github.com/devTomaszStoklosa/QuantLab/pull/20), [#23](https://github.com/devTomaszStoklosa/QuantLab/pull/23), [#25](https://github.com/devTomaszStoklosa/QuantLab/pull/25), [#26](https://github.com/devTomaszStoklosa/QuantLab/pull/26) i [#27](https://github.com/devTomaszStoklosa/QuantLab/pull/27); od S8 silnik liczy tak samo. Pełny tear-sheet: `uv run quantlab run --tear-sheet reports/momentum_v1.html`.

Co dalej:

- `momentum_v1` jest zamknięta, a holdout 2024–2025 zużyty. Każdy wariant — inny lookback, filtr reżimu średniej zmienności, szerszy koszyk — byłby nową hipotezą, z nowym zamrożonym holdoutem i z korektą na wielokrotne testowanie (`q6`: deflated Sharpe), bo powstałby po obejrzeniu tych wyników.
- Zgodnie z [ROADMAP](ROADMAP.md): momentum nie przeszło walidacji, więc priorytet dostaje `q3` (mean reversion) jako kontrast na tym samym pipeline'ie — najlepiej na szerszym koszyku, który usuwa główne ograniczenie tego badania.
