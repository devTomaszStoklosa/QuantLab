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

## 2026-10-02 — momentum_select_v1: momentum z lookbackiem wybieranym na danych, BTC-USDT i ETH-USDT

**Hipoteza:** momentum szeregów czasowych na BTC-USDT i ETH-USDT z lookbackiem wybieranym co roku na danych (siatka 30–365 dni, wybór po Sharpe netto z historii sprzed dnia wyboru) daje dodatni wynik netto po kosztach, a jego timing jest lepszy niż przypadek, także po uwzględnieniu, że parametr dobierano na danych.

**Metodologia:**

- **Dane:** Binance spot, świece dzienne, BTC-USDT i ETH-USDT (uniwersum `mvp-crypto`), te same co w `momentum_v1`. Kontrola danych (`q14`): 0 błędów; 2 ostrzeżenia to skrajne ruchy z 2020-03-12 (BTC −39.5%, ETH −44.6%), czyli prawdziwy krach.
- **Procedura zamiast wartości:** 1 stycznia każdego roku każdy lookback z siatki [30, 60, 90, 180, 270, 365] jest testowany silnikiem wektorowym z modelem realistycznym, wyłącznie na barach sprzed tego dnia i we wspólnym oknie. Na cały rok handlowany jest lookback z najwyższym Sharpe netto (przy remisie krótszy). Zmiana lookbacku jest handlowana i kosztowana. Pierwszy wybór, wymagający 365 dni historii, przypada na 2020, więc pozycje są od 2020-01-02.
- **Koszty:** te same trzy modele co w `momentum_v1`; główny `realistic-10bps-k0.05-vol30d`.
- **Okres treningowy:** 2018-01-01 → 2023-12-31, okres `momentum_v1`; z pozycjami 4 lata (2020–2023).
- **Holdout:** 2026-01-01 → 2026-08-31, zamrożony w [config/holdout/momentum_select_v1.yaml](../config/holdout/momentum_select_v1.yaml) (commit `d7c3d53`) przed jakimkolwiek przebiegiem. Lata 2024–2025 to zużyty holdout `momentum_v1`, więc nie należą do żadnego okresu oceny; wybór lookbacku na 2026 korzysta jednak z całej historii sprzed 2026-01-01, łącznie z nimi.
- **Walidacja:**
  - bramka in-sample: CPCV procedury wyboru (López de Prado 2018, rozdz. 12), 10 grup, z czego 2 testowe (45 podziałów, 9 ścieżek), purging 1 dzień i embargo 1%; zaliczona, gdy mediana Sharpe netto ścieżek > 0. Walk-forward kalendarzowy i PBO siatki są opisowe;
  - test permutacyjny: 10 000 przetasowań dziennych zwrotów względem trzymanych pozycji, seed 0, statystyka: roczny Sharpe zwrotów brutto, α = 0.1;
  - kryterium holdoutu (zamrożone): Sharpe netto (model realistyczny) > 0 i p < 0.1; Sharpe ≤ 0 → `rejected`; Sharpe > 0 i p ≥ 0.1 → `inconclusive`.
- **Wielokrotne testowanie:** 6 prób na `mvp-crypto` 2018–2023 i 11 konfiguracji w progu deflated Sharpe, bo każda z sześciu wartości siatki liczy się osobno.
- **Status końcowy:** jak w `momentum_v1`: `confirmed` tylko przy zaliczonej bramce in-sample i zaliczonym holdoucie; liczy go kod.

**Wynik — okres treningowy 2018–2023** (pozycje od 2020-01-02):

| Metryka | `zero-cost` (brutto) | `naive-10bps` | `realistic` |
|---|---:|---:|---:|
| CAGR | 19.93% | 15.92% | 9.09% |
| Sharpe | 0.61 | 0.55 | 0.44 |
| Sortino | 0.86 | 0.77 | 0.61 |
| Calmar | 0.28 | 0.22 | 0.12 |
| Max drawdown | −72.09% | −72.53% | −73.74% |

- **CPCV: zaliczona.** 9 ścieżek, mediana Sharpe 0.45, zakres 0.23–0.76, wszystkie dodatnie. Ścieżki dzielą dane, więc nie są niezależnymi próbami.
- **Wybrane lookbacki:** 2020 → 60 dni, 2021 → 30, 2022 → 60, 2023 → 30. W podziałach CPCV 30 dni wybrano w 56% przypadków, 60 dni w 38%, 270 dni w 7%, a 90, 180 i 365 dni nigdy. Procedura wybiera więc w praktyce momentum krótkoterminowe (1–2 miesiące), a nie 12-miesięczne z `momentum_v1`.
- **Lata (netto, model realistyczny):** 2020 −18.79%, 2021 +122.85%, 2022 −39.80%, 2023 +54.68%. Dwa z czterech lat są ujemne, a skalę wyniku robi rok 2021.
- **Koszty:** werdykt wrażliwości „cost-dependent” (różnica Sharpe między modelem naiwnym a realistycznym 0.11). Koszty w rejestrze transakcji (0.7635 kapitału startowego) są większe niż P&L netto (+0.6852), czyli realistyczne koszty zabierają ponad połowę wyniku brutto. Krótkie lookbacki to częste zmiany pozycji: 164 transakcje w 4 lata wobec 66 w 5.4 roku `momentum_v1`.
- **Test permutacyjny:** Sharpe brutto 0.61 wobec średniej przetasowań 0.06 (odch. std. 0.41); wyższy niż 91.0% przetasowań; **p = 0.090**, istotny przy α = 0.1. To jedyny istotny timing wśród sześciu prób na tym koszyku (`momentum_v1`: p = 0.140).
- **Wielokrotne testowanie:** Sharpe roczny 0.53, PSR 0.86, próg deflated Sharpe 0.81, DSR 0.29. Po uwzględnieniu 11 konfiguracji wynik nie odróżnia się od najlepszej z 11 prób bez żadnego efektu.
- **Reżimy zmienności** (tercyl 30-dniowej zmienności BTC-USDT wobec ostatnich 365 dni; opisowo): niski CAGR −22.50%, Sharpe −0.17 (561 dni); średni CAGR 58.01%, Sharpe 1.05 (476 dni); wysoki CAGR 31.47%, Sharpe 0.75 (423 dni). Jak w `momentum_v1`, strategia traci przy niskiej zmienności.
- **Transakcje:** 164 (2 otwarte na końcu), 53 z dodatnim P&L netto (32%).

**Obserwacje przed otwarciem holdoutu** (zacommitowane przed uruchomieniem `open-holdout`, więc wynik holdoutu nie mógł na nie wpłynąć):

1. Bramka in-sample przechodzi wyraźnie, a timing jest istotny przy α = 0.1, czego `momentum_v1` nie osiągnęła. Po korekcie na wielokrotne testowanie (DSR 0.29) wynik nie odróżnia się jednak od szczęścia najlepszej z 11 konfiguracji.
2. Wynik jest kruchy w czasie: 4 lata z pozycjami, z czego dwa ujemne, a skalę robi 2021.
3. Koszty zabierają ponad połowę wyniku brutto. Przewaga netto istnieje tylko wtedy, gdy model realistyczny nie zaniża poślizgu.
4. Holdout trwa ok. 8 miesięcy (243 dni), więc test ma bardzo małą moc. Odchylenie rocznego Sharpe z 8 miesięcy to ok. 1/√0.67 ≈ 1.2, więc żeby p spadło poniżej 0.1, potrzebny byłby roczny Sharpe rzędu 1.6. Przy Sharpe takim jak w treningu (0.4–0.6) najbardziej prawdopodobny werdykt to `inconclusive`, a `rejected` (Sharpe ≤ 0) ma szansę ok. 1 do 3 nawet przy prawdziwym efekcie. Brak mocy był zaakceptowany przy zamrażaniu.

**Wynik — holdout 2026-01-01 → 2026-08-31** (otwarty dokładnie raz, 2026-10-02 15:21 UTC, przy commicie `1efbf4d` z obserwacjami powyżej; zapis otwarcia: [config/holdout/momentum_select_v1.opened.json](../config/holdout/momentum_select_v1.opened.json), commit `3946763`; model realistyczny; liczby z zapisu otwarcia, nie łączone z treningiem):

| Metryka | Holdout |
|---|---:|
| CAGR | 14.64% |
| Sharpe netto | 0.52 |
| Sortino | 0.79 |
| Calmar | 0.62 |
| Max drawdown | −23.78% |
| p (test permutacyjny) | 0.295 |

Test permutacyjny na holdoucie: Sharpe brutto 0.68 wobec średniej przetasowań 0.04 (odch. std. 1.16); wyższy niż 70.5% przetasowań. Strategia miała pozycję przez 242 dni, mniej niż rok sesji rynku krypto (365), więc kod oznacza wynik flagą niskiej wiarygodności. **Werdykt holdoutu: `inconclusive`** (Sharpe 0.52 > 0, ale p ≥ 0.1).

**Wniosek: `inconclusive`.**

Status wynika mechanicznie z reguł zapisanych przed wynikami: bramka CPCV zaliczona, holdout `inconclusive` → `inconclusive`. `confirmed` wymagałby zaliczenia obu bramek.

Co mówią liczby poza samym słowem werdyktu:

1. **Holdout jest zgodny z treningiem, ale niczego nie rozstrzyga.** Sharpe netto 0.52 mieści się w zakresie ścieżek CPCV (0.23–0.76) i jest bliski treningowemu (0.44). Statystyka testu leży jednak tylko ok. 0.55 odchylenia nad średnią przetasowań. Odchylenie (1.16) jest takie, jak przewidywała obserwacja 4 sprzed otwarcia, więc holdout nie mógł dać istotnego wyniku przy Sharpe tego rzędu.
2. **Nie ma dowodu, że wybór parametru na danych coś dodaje.** To było pytanie kontrastowe tej hipotezy wobec `momentum_v1`. Sharpe netto na tym samym okresie treningowym jest praktycznie taki sam (0.44 wobec 0.43). Istotność timingu w treningu (p = 0.090) znika po korekcie na 11 konfiguracji (DSR 0.29), a holdout jej nie potwierdza. Wybór przesunął strategię na lookbacki 30–60 dni, które oddają ponad połowę wyniku brutto na koszty.
3. **Ryzyko pozostaje duże.** Obsunięcie −23.8% w 8 miesięcy holdoutu, −73.7% w treningu.

Ograniczenia tego badania:

- Tylko dwa, silnie skorelowane instrumenty, jak w `momentum_v1`.
- Krótkie okresy: 4 lata treningu z pozycjami i 8 miesięcy holdoutu. Oba testy mają małą moc, co było wiadome przy zamrażaniu.
- 9 ścieżek CPCV na 4 latach dzieli dane, więc to nie 9 niezależnych potwierdzeń.
- Zapis otwarcia nie przechowuje lookbacku wybranego na 2026, więc ten wpis nie podaje, którą wartością handlowano w holdoucie ([#106](https://github.com/devTomaszStoklosa/QuantLab/issues/106)).
- Koszty bez market impact, egzekucja po cenie zamknięcia, jak w `momentum_v1`.

Co dalej:

- `momentum_select_v1` jest zamknięta, a holdout 2026-01 → 2026-08 został dla niej zużyty. Wariant ze stałym krótkim lookbackiem albo z filtrem reżimu niskiej zmienności byłby nową hipotezą, z nowym zamrożonym holdoutem i z korektą DSR, bo powstałby po obejrzeniu tych wyników.
- Jest to jeden z czterech składników `portfolio_v1`, którego holdout czeka jeszcze na holdouty `mean_reversion_v1` i `pairs_v1`.

## 2026-10-02 — momentum_voltarget_v1: momentum skalowane do docelowej zmienności, BTC-USDT i ETH-USDT

**Hipoteza:** sygnał `momentum_v1` (znak zwrotu 365-dniowego) z pozycjami skalowanymi do docelowej zmienności 40% rocznie na instrument, bez dźwigni, daje na BTC-USDT i ETH-USDT dodatni wynik netto po kosztach, a jego timing jest lepszy niż przypadek.

**Metodologia:**

- **Dane:** Binance spot, świece dzienne, BTC-USDT i ETH-USDT (uniwersum `mvp-crypto`), te same co w `momentum_v1`. Kontrola danych (`q14`): 0 błędów; 2 ostrzeżenia to skrajne ruchy z 2020-03-12, czyli prawdziwy krach.
- **Sygnał i wielkość pozycji:** sygnał `momentum_v1` z rebalansem dziennym; jedyną różnicą jest wielkość pozycji. Udział każdego instrumentu to równa waga pomnożona przez min(1, 0.40 / roczna zmienność ex-ante). Zmienność to EWMA ze środkiem masy 60 dni w oknie 365 dziennych zwrotów do dnia decyzji (Moskowitz, Ooi, Pedersen 2012). Limit 1 oznacza brak dźwigni, więc nie ma kosztu finansowania. Pomysł powstał po obejrzeniu wyników `momentum_v1` (cały zysk w reżimie średniej zmienności, obsunięcie −88.7%), więc to kolejna próba na tych samych danych.
- **Koszty:** te same trzy modele co w `momentum_v1`; główny `realistic-10bps-k0.05-vol30d`.
- **Okres treningowy:** 2018-01-01 → 2023-12-31; pierwsza pozycja 2018-08-18, jak w `momentum_v1`.
- **Holdout:** 2026-01-01 → 2026-08-31, zamrożony w [config/holdout/momentum_voltarget_v1.yaml](../config/holdout/momentum_voltarget_v1.yaml) (commit `ff61e2c`, 2026-09-26) przed jakimkolwiek przebiegiem. Lata 2024–2025 to zużyty holdout `momentum_v1`.
- **Walidacja:**
  - bramka in-sample: walk-forward w oknach rocznych od pierwszej pozycji; zaliczona, gdy Sharpe > 0 w co najmniej 2/3 okien i łączny Sharpe > 0;
  - test permutacyjny: 10 000 przetasowań dziennych zwrotów względem trzymanych pozycji, seed 0, statystyka: roczny Sharpe zwrotów brutto, α = 0.1;
  - kryterium holdoutu (zamrożone): Sharpe netto (model realistyczny) > 0 i p < 0.1; Sharpe ≤ 0 → `rejected`; Sharpe > 0 i p ≥ 0.1 → `inconclusive`.
- **Wielokrotne testowanie:** 6 prób na `mvp-crypto` 2018–2023 i 11 konfiguracji w progu deflated Sharpe.
- **Status końcowy:** jak w `momentum_v1`: `confirmed` tylko przy zaliczonej bramce in-sample i zaliczonym holdoucie; liczy go kod.

**Wynik — okres treningowy 2018–2023:**

| Metryka | `zero-cost` (brutto) | `naive-10bps` | `realistic` |
|---|---:|---:|---:|
| CAGR | 15.82% | 14.53% | 12.33% |
| Sharpe | 0.61 | 0.58 | 0.52 |
| Sortino | 0.85 | 0.80 | 0.72 |
| Calmar | 0.26 | 0.24 | 0.20 |
| Max drawdown | −60.32% | −61.13% | −63.00% |

- **Koszty:** werdykt wrażliwości „robust” (różnica Sharpe między modelem naiwnym a realistycznym 0.06). Koszty w rejestrze transakcji to 0.1837 kapitału startowego przy P&L netto +1.0086.
- **Walk-forward (realistic): zaliczony**, 5 z 6 okien ze Sharpe > 0.

  | Okno | CAGR | Sharpe | Max drawdown |
  |---|---:|---:|---:|
  | 2018-08-18 → 2018-12-31 (niepełny rok) | 39.44% | 1.05 | −16.57% |
  | 2019 | −42.96% | −1.93 | −47.30% |
  | 2020 | 38.87% | 1.04 | −42.52% |
  | 2021 | 70.90% | 1.59 | −23.99% |
  | 2022 | 19.82% | 0.69 | −22.16% |
  | 2023 | 9.30% | 0.43 | −36.71% |
  | Łącznie | 13.85% | 0.55 | −63.00% |

- **Skalowanie a to samo momentum bez skalowania** (to samo okno, netto, model realistyczny; opisowo):

  | | Ze skalowaniem | Bez skalowania |
  |---|---:|---:|
  | Sharpe netto | 0.55 | 0.45 |
  | Zmienność roczna | 35.3% | 66.9% |
  | Max drawdown | −63.0% | −88.7% |

  Średnia skala pozycji wobec równej wagi: BTC-USDT 0.64 (najniższa 0.33, na limicie 5.1% dni), ETH-USDT 0.51 (najniższa 0.26, na limicie 3.8% dni).
- **Test permutacyjny:** Sharpe brutto 0.61 wobec średniej przetasowań 0.10 (odch. std. 0.41); wyższy niż 89.3% przetasowań; **p = 0.107**, nieistotny przy α = 0.1 (`momentum_v1`: p = 0.140).
- **Wielokrotne testowanie:** Sharpe roczny 0.55, PSR 0.89, próg deflated Sharpe 0.70, DSR 0.36.
- **Reżimy zmienności** (tercyl 30-dniowej zmienności BTC-USDT wobec ostatnich 365 dni; opisowo): niski CAGR −12.53%, Sharpe −0.21 (754 dni); średni CAGR 74.77%, Sharpe 1.75 (630 dni); wysoki CAGR 7.69%, Sharpe 0.39 (549 dni); 29 dni bez wyznaczonego reżimu: CAGR −72.03%, Sharpe −3.73.
- **Transakcje:** 66 (2 otwarte na końcu), 22 z dodatnim P&L netto (33%). 9 transakcji trzymanych ponad 90 dni dało +1.29, pozostałe 57 łącznie −0.28; najlepsza transakcja przyniosła +0.58. To ten sam profil trend-following co w `momentum_v1`, bo sygnał jest ten sam.

**Obserwacje przed otwarciem holdoutu** (zacommitowane przed uruchomieniem `open-holdout`, więc wynik holdoutu nie mógł na nie wpłynąć):

1. Bramka in-sample przechodzi wyraźniej niż w `momentum_v1`: rok 2023 ma Sharpe 0.43 zamiast granicznego 0.01. Jedyny ujemny rok to 2019 (−43%).
2. Skalowanie robi to, do czego służy. Na tym samym oknie zmienność spada z 66.9% do 35.3%, obsunięcie z −88.7% do −63.0%, a Sharpe netto rośnie z 0.45 do 0.55. Różnica Sharpe jest opisowa, bez testu istotności.
3. Timing jest na granicy: p = 0.107, tuż nad α = 0.1. Po korekcie na 11 konfiguracji (DSR 0.36) wynik nie odróżnia się od najlepszej z 11 prób bez żadnego efektu.
4. Wynik nadal opiera się na kilku długich transakcjach i na reżimie średniej zmienności. Skalowanie zmniejszyło zależność od 2021 (+70.9% zamiast +194.5% w `momentum_v1`), ale nie zmieniło profilu.
5. Holdout jest ten sam co w `momentum_select_v1`: 8 miesięcy i ta sama mała moc. Do p < 0.1 potrzebny byłby roczny Sharpe rzędu 1.6, więc najbardziej prawdopodobny werdykt to `inconclusive`, a `rejected` ma szansę ok. 1 do 3 nawet przy prawdziwym efekcie. Ceny z tego okresu zostały już odczytane przy otwarciu `momentum_select_v1`, ale ta definicja była zamrożona wcześniej (2026-09-26), więc nic nie mogło zostać do nich dopasowane.

**Wynik — holdout 2026-01-01 → 2026-08-31** (otwarty dokładnie raz, 2026-10-02 15:29 UTC, przy commicie `6672b2d` z obserwacjami powyżej; zapis otwarcia: [config/holdout/momentum_voltarget_v1.opened.json](../config/holdout/momentum_voltarget_v1.opened.json), commit `edfe905`; model realistyczny; liczby z zapisu otwarcia, nie łączone z treningiem):

| Metryka | Holdout |
|---|---:|
| CAGR | 11.58% |
| Sharpe netto | 0.48 |
| Sortino | 0.68 |
| Calmar | 0.38 |
| Max drawdown | −30.76% |
| p (test permutacyjny) | 0.246 |

Test permutacyjny na holdoucie: Sharpe brutto 0.59 wobec średniej przetasowań 0.13 (odch. std. 0.68); wyższy niż 75.5% przetasowań. Strategia miała pozycję przez 242 dni, mniej niż rok sesji rynku krypto (365), więc kod oznacza wynik flagą niskiej wiarygodności. **Werdykt holdoutu: `inconclusive`** (Sharpe 0.48 > 0, ale p ≥ 0.1).

**Wniosek: `inconclusive`.**

Status wynika mechanicznie z reguł zapisanych przed wynikami: walk-forward zaliczony, holdout `inconclusive` → `inconclusive`. `confirmed` wymagałby zaliczenia obu bramek.

Co mówią liczby poza samym słowem werdyktu:

1. **Holdout jest zgodny z treningiem, ale niczego nie rozstrzyga.** Sharpe netto 0.48 jest bliski treningowemu (0.52), a statystyka testu leży ok. 0.68 odchylenia nad średnią przetasowań.
2. **Obserwacja 5 sprzed otwarcia zawyżyła próg istotności.** Zakładała odchylenie rozkładu przetasowań ok. 1.2 i próg rzędu 1.6, a faktyczne odchylenie to 0.68. Do p < 0.1 wystarczał więc Sharpe brutto ok. 1.0 (0.13 + 1.28 × 0.68). Przybliżenie 1/√T pasuje do strategii, która często zmienia znak pozycji, jak `momentum_select_v1` (tam odchylenie 1.16). Sygnał 12-miesięczny zmienia pozycje rzadko, a przy rzadkich zmianach przetasowanie dni rusza wynik mniej. Wniosek o małej mocy zostaje: wynik 0.59 był daleko od progu 1.0.
3. **Holdout nie mówi nic o samym skalowaniu.** `momentum_v1` miała inny holdout (2024–2025), a zapis otwarcia nie zawiera wersji bez skalowania na 2026. Przewaga skalowania (niższa zmienność i obsunięcie przy nie gorszym Sharpe) jest więc pokazana tylko na treningu i tylko opisowo.
4. **Skalowanie nie chroni przed dużym obsunięciem:** −30.8% w 8 miesięcy holdoutu.

Ograniczenia tego badania:

- Tylko dwa, silnie skorelowane instrumenty, jak w `momentum_v1`.
- 8 miesięcy holdoutu i flaga niskiej wiarygodności testu.
- Porównanie ze skalowaniem i bez istnieje tylko dla treningu; zapis otwarcia przechowuje jedynie metryki, test i werdykt ([#106](https://github.com/devTomaszStoklosa/QuantLab/issues/106)).
- Pomysł powstał po obejrzeniu wyników `momentum_v1`, więc to kolejna próba na tych samych danych, policzona w progu deflated Sharpe.
- Koszty bez market impact, egzekucja po cenie zamknięcia.

Co dalej:

- `momentum_voltarget_v1` jest zamknięta, a holdout 2026-01 → 2026-08 został dla niej zużyty. W treningu skalowanie zmniejszyło zmienność i obsunięcie bez utraty Sharpe; to opis wyniku historycznego, nie dowód przewagi sygnału.
- Ta sama konstrukcja na koszyku ETF z pięciu klas aktywów jest już zamrożona jako `momentum_voltarget_multiasset_v1` i czeka na swój holdout.

## 2026-10-02 — momentum_voltarget_multiasset_v1: momentum skalowane do zmienności na koszyku ETF z pięciu klas aktywów

**Hipoteza:** sygnał `momentum_multiasset_v1` (znak nadwyżki ponad gotówkę z 252 sesji) z pozycjami skalowanymi do docelowej zmienności 10% rocznie na instrument, bez dźwigni, daje na koszyku 10 ETF-ów z pięciu klas aktywów dodatni wynik netto ponad gotówkę po kosztach, a jego timing jest lepszy niż przypadek.

**Metodologia:**

- **Dane:** Tiingo, ceny dzienne skorygowane o dywidendy i splity, 10 ETF-ów (uniwersum `multiasset-etf`): akcje SPY, EFA i EEM; obligacje IEF, TLT i LQD; surowce GLD i DBC; dolar UUP; nieruchomości VNQ. Gotówką jest BIL i wszystkie zwroty liczone są ponad nią. Koszyk zamrożono przed pierwszym przebiegiem (2026-09-26); wszystkie ETF-y są notowane do dziś, co jest zastrzeżeniem survivorship. Kontrola danych (`q14`): 0 błędów; 38 ostrzeżeń to skrajne ruchy z okresu 2008-09 → 2009-04, czyli kryzys finansowy.
- **Sygnał i wielkość pozycji:** znak nadwyżki ponad gotówkę z 252 sesji (pozycja długa albo krótka), rebalans dzienny, jak w `momentum_multiasset_v1`. Udział każdego ETF-u to równa waga pomnożona przez min(1, 0.10 / roczna zmienność ex-ante); zmienność to EWMA ze środkiem masy 60 sesji w oknie 252 zwrotów. Cel to 10%, a nie 40% jak u Moskowitza, Ooi i Pedersena (2012), bo bez dźwigni 40% przycinałoby tylko najbardziej zmienne ETF-y. To druga próba na tym uniwersum.
- **Koszty:** `zero-cost`, `naive-3bps` i `realistic-3bps-k0.05-vol21d` (prowizja 3 bps plus poślizg 0.05 × zmienność 21-sesyjna); główny jest model realistyczny. Koszt pożyczki ETF-u przy krótkiej sprzedaży nie jest modelowany.
- **Okres treningowy:** 2008-07-01 → 2017-12-31; pierwsza pozycja 2008-07-02.
- **Holdout:** 2018-01-01 → 2026-08-31, zamrożony w [config/holdout/momentum_voltarget_multiasset_v1.yaml](../config/holdout/momentum_voltarget_multiasset_v1.yaml) (commit `51db59f`, 2026-09-26) przed jakimkolwiek przebiegiem.
- **Walidacja:**
  - bramka in-sample: walk-forward w oknach rocznych od pierwszej pozycji; zaliczona, gdy Sharpe > 0 w co najmniej 2/3 okien i łączny Sharpe > 0;
  - test permutacyjny: 10 000 przetasowań dziennych zwrotów względem trzymanych pozycji, seed 0, statystyka: roczny Sharpe zwrotów brutto, α = 0.1;
  - kryterium holdoutu (zamrożone): Sharpe netto (model realistyczny) > 0 i p < 0.1; Sharpe ≤ 0 → `rejected`; Sharpe > 0 i p ≥ 0.1 → `inconclusive`.
- **Wielokrotne testowanie:** 2 próby na `multiasset-etf` (razem z `momentum_multiasset_v1`) i 2 konfiguracje w progu deflated Sharpe; próby na krypto się tu nie liczą.
- **Status końcowy:** jak w `momentum_v1`: `confirmed` tylko przy zaliczonej bramce in-sample i zaliczonym holdoucie; liczy go kod.

**Wynik — okres treningowy 2008-07 → 2017** (zwroty ponad gotówkę):

| Metryka | `zero-cost` (brutto) | `naive-3bps` | `realistic` |
|---|---:|---:|---:|
| CAGR | 1.47% | 1.15% | 0.70% |
| Sharpe | 0.36 | 0.28 | 0.18 |
| Sortino | 0.49 | 0.39 | 0.25 |
| Calmar | 0.21 | 0.16 | 0.09 |
| Max drawdown | −6.90% | −7.21% | −8.03% |

- **Koszty:** werdykt wrażliwości „cost-dependent” (różnica Sharpe między modelem naiwnym a realistycznym 0.10). Koszty w rejestrze transakcji (0.0750 kapitału startowego) są większe niż P&L netto (+0.0681), czyli zabierają ponad połowę wyniku brutto.
- **Walk-forward (realistic): zaliczony**, 7 z 10 okien ze Sharpe > 0. Kod oznacza na kalendarzu giełdowym każde okno jako niepełne ([#110](https://github.com/devTomaszStoklosa/QuantLab/issues/110)); naprawdę niepełny jest tylko rok 2008.

  | Okno | CAGR | Sharpe | Max drawdown |
  |---|---:|---:|---:|
  | 2008-07-02 → 2008-12-31 (niepełny rok) | 5.41% | 0.64 | −3.18% |
  | 2009 | −2.51% | −0.52 | −6.80% |
  | 2010 | 2.25% | 0.47 | −3.68% |
  | 2011 | −1.14% | −0.25 | −5.79% |
  | 2012 | 0.49% | 0.19 | −4.35% |
  | 2013 | 3.07% | 0.85 | −4.28% |
  | 2014 | 1.93% | 0.59 | −2.25% |
  | 2015 | 0.33% | 0.10 | −4.24% |
  | 2016 | −5.83% | −1.38 | −7.59% |
  | 2017 | 5.84% | 1.84 | −1.27% |
  | Łącznie | 0.70% | 0.18 | −8.03% |

- **Skalowanie a to samo momentum bez skalowania** (`momentum_multiasset_v1`; to samo okno, netto, model realistyczny; opisowo):

  | | Ze skalowaniem | Bez skalowania |
  |---|---:|---:|
  | Sharpe netto | 0.17 | −0.08 |
  | Zmienność roczna | 4.4% | 11.7% |
  | Max drawdown | −8.0% | −32.7% |

  IEF, LQD i UUP są prawie zawsze na limicie (91.8%, 89.3% i 83.1% dni; średnia skala 0.99, 0.95 i 0.97). Najmocniej przycinane są EEM (średnio 0.47, nigdy na limicie), VNQ (0.56), EFA (0.57), GLD i DBC (po 0.61). Skalowanie przesuwa więc ryzyko portfela w stronę obligacji i dolara.
- **Test permutacyjny:** Sharpe brutto 0.36 wobec średniej przetasowań 0.41 (odch. std. 0.27); wyższy niż tylko 42.2% przetasowań; **p = 0.578**, nieistotny przy α = 0.1. Faktyczny timing wypadł gorzej niż przeciętne losowe sparowanie tych samych pozycji z tymi samymi zwrotami.
- **Wielokrotne testowanie:** Sharpe roczny 0.18, PSR 0.71, próg deflated Sharpe 0.17, DSR 0.52.
- **Reżimy zmienności** (tercyl 21-sesyjnej zmienności SPY wobec ostatnich 252 sesji; opisowo): niski CAGR 0.19%, Sharpe 0.07 (970 dni); średni CAGR 2.00%, Sharpe 0.52 (720 dni); wysoki CAGR −0.14%, Sharpe −0.00 (697 dni); 5 dni bez wyznaczonego reżimu.
- **Skąd wynik** (P&L netto transakcji przy kapitale startowym 1.00; opisowo, bez testu per klasa): obligacje +0.0611, akcje +0.0232, nieruchomości +0.0125, surowce +0.0094, dolar −0.0381. Najwięcej dały SPY (+0.043), IEF (+0.028) i LQD (+0.022), najwięcej straciły UUP (−0.038) i EEM (−0.025). Pozycje długie dały łącznie +0.193, krótkie −0.125.
- **Transakcje:** 637 (10 otwartych na końcu), 188 z dodatnim P&L netto (30%). 33 transakcje trzymane ponad rok dały +0.373 (91% z nich zyskownych), wszystkie krótsze łącznie −0.305.

**Obserwacje przed otwarciem holdoutu** (zacommitowane przed uruchomieniem `open-holdout`, więc wynik holdoutu nie mógł na nie wpłynąć):

1. Bramka in-sample przechodzi o jedno okno: 7 z 10, a lata 2012 (Sharpe 0.19) i 2015 (0.10) są dodatnie ledwo. Jedno ujemne okno więcej dałoby 6 z 10, czyli poniżej 2/3.
2. W treningu nie ma śladu timingu: Sharpe brutto 0.36 jest niższy niż średnia przetasowań 0.41 (p = 0.578). Dodatni wynik pochodzi z przeciętnej ekspozycji, a nie z wyczucia momentu.
3. Skalowanie zmienia wynik z ujemnego na dodatni (Sharpe −0.08 → 0.17) głównie przez zmianę składu ryzyka: obligacje i dolar zostają w prawie pełnej wadze, a akcje, surowce i nieruchomości są przycinane. Prawie cały P&L netto pochodzi z obligacji (+0.061 z +0.068), w okresie przeważnie spadających rentowności.
4. Koszty zabierają ponad połowę wyniku brutto, a wynik netto to 0.70% rocznie ponad gotówkę przy zmienności 4.4%.
5. Holdout trwa 8.7 roku, więc test ma dużo większą moc niż holdouty krypto. Po lekcji z `momentum_voltarget_v1` szacuję próg z odchylenia przetasowań w treningu (0.27), a nie z 1/√T. Do p < 0.1 Sharpe brutto musiałby być o ok. 0.35 wyższy niż średnia przetasowań, a w treningu był o 0.05 niższy. Najbardziej prawdopodobny werdykt to więc `inconclusive`; `rejected` (Sharpe netto ≤ 0) ma szansę ok. 30% nawet przy prawdziwym Sharpe 0.18.
6. Lata holdoutu to znana historia rynku, np. 2022, gdy akcje i obligacje spadały razem, a gotówka zaczęła dawać kilka procent rocznie. Definicję zamrożono, zanim kod odczytał te dane, ale nie przed wiedzą badacza o tych latach. Tego ograniczenia zamrożenie nie usuwa.

**Wynik — holdout 2018-01-01 → 2026-08-31** (otwarty dokładnie raz, 2026-10-02 15:39 UTC, przy commicie `10a5f7d` z obserwacjami powyżej; zapis otwarcia: [config/holdout/momentum_voltarget_multiasset_v1.opened.json](../config/holdout/momentum_voltarget_multiasset_v1.opened.json), commit `4870ef0`; model realistyczny, zwroty ponad gotówkę; liczby z zapisu otwarcia, nie łączone z treningiem):

| Metryka | Holdout |
|---|---:|
| CAGR | 0.21% |
| Sharpe netto | 0.07 |
| Sortino | 0.09 |
| Calmar | 0.02 |
| Max drawdown | −13.47% |
| p (test permutacyjny) | 0.554 |

Test permutacyjny na holdoucie: Sharpe brutto 0.26 wobec średniej przetasowań 0.30 (odch. std. 0.31); wyższy niż 44.7% przetasowań. Strategia miała pozycję przez 2176 dni, więc wynik nie ma flagi niskiej wiarygodności. **Werdykt holdoutu: `inconclusive`** (Sharpe 0.07 > 0, ale p ≥ 0.1).

**Wniosek: `inconclusive`.**

Status wynika mechanicznie z reguł zapisanych przed wynikami: walk-forward zaliczony, holdout `inconclusive` → `inconclusive`. `confirmed` wymagałby zaliczenia obu bramek.

Co mówią liczby poza samym słowem werdyktu:

1. **Na ok. 18 latach danych nie ma śladu timingu.** W treningu i w holdoucie faktyczny Sharpe brutto jest niższy niż średnia przetasowań (0.36 wobec 0.41 i 0.26 wobec 0.30). Dodatni wynik w obu okresach daje przeciętna ekspozycja tych samych pozycji, a nie moment ich zmiany. To najmocniejsze ustalenie tego wpisu, bo holdout jest długi i nie ma flagi niskiej wiarygodności.
2. **Wynik netto jest praktycznie równy gotówce.** CAGR 0.21% rocznie ponad BIL i Sharpe netto 0.07. Przy błędzie standardowym Sharpe z 8.7 roku ok. 0.34 nie odróżnia się to od zera, a spadek z 0.18 w treningu mieści się w tym samym szumie.
3. **Przewidywania sprzed otwarcia się sprawdziły.** Odchylenie przetasowań wyszło 0.31 przy szacunku 0.27, więc do p < 0.1 trzeba było ok. 0.40 ponad średnią przetasowań. Wynik był 0.05 poniżej niej, tak jak w treningu. Szacowanie progu z rozkładu przetasowań w treningu zadziałało tu lepiej niż przybliżenie 1/√T przy `momentum_voltarget_v1`.
4. **O samym skalowaniu rozstrzygnie dopiero porównanie z `momentum_multiasset_v1`**, czyli z tym samym sygnałem bez skalowania na tym samym holdoucie. Zapis otwarcia nie ma podziału P&L per klasa aktywów ani per rok, więc nie widać, czy przesunięcie ryzyka w stronę obligacji szkodziło w latach rosnących stóp ([#106](https://github.com/devTomaszStoklosa/QuantLab/issues/106)).

Ograniczenia tego badania:

- 10 ETF-ów wybranych w 2026 spośród notowanych do dziś (survivorship); jeden poziom docelowej zmienności (10%).
- Koszt pożyczki ETF-u przy krótkiej sprzedaży nie jest modelowany. Pozycje krótkie w treningu traciły (−0.125), więc ten koszt jeszcze pogorszyłby wynik.
- Zapis otwarcia nie dzieli holdoutu per klasa aktywów ani per rok (#106).
- Lata holdoutu to znana historia rynku (obserwacja 6).
- Koszty bez market impact, egzekucja po cenie zamknięcia.

Co dalej:

- `momentum_voltarget_multiasset_v1` jest zamknięta. Holdout 2018 → 2026-08 na `multiasset-etf` został dla niej zużyty, a jego wyniki znają już wszystkie kolejne próby na tym uniwersum.
- Następny jest holdout `momentum_multiasset_v1`. Jej bramka walk-forward nie przeszła, więc status będzie `rejected` bez względu na holdout, ale jej wpis porówna ten sam sygnał bez skalowania na tym samym okresie.

## 2026-10-02 — momentum_multiasset_v1: time-series momentum na koszyku ETF z pięciu klas aktywów

**Hipoteza:** reguła `momentum_v1` przeniesiona poza krypto, czyli pozycja długa albo krótka w każdym ETF-ie według znaku jego nadwyżki ponad gotówkę z 252 sesji, z równymi wagami, daje na koszyku 10 ETF-ów z pięciu klas aktywów dodatni wynik netto ponad gotówkę po kosztach, a jej timing jest lepszy niż przypadek.

**Metodologia:**

- **Dane:** te same co w `momentum_voltarget_multiasset_v1`: Tiingo, 10 ETF-ów (uniwersum `multiasset-etf`), gotówka BIL, zwroty ponad nią. Kontrola danych (`q14`): 0 błędów; 38 ostrzeżeń to skrajne ruchy z okresu 2008-09 → 2009-04 (kryzys finansowy).
- **Sygnał:** znak nadwyżki ponad gotówkę z 252 sesji (Moskowitz, Ooi, Pedersen 2012), równe wagi po znaku, rebalans dzienny. Parametry z literatury i z `momentum_v1`, niedopasowywane do tych danych. To pierwsza próba na tym uniwersum; `momentum_voltarget_multiasset_v1` różni się tylko wielkością pozycji.
- **Koszty:** `zero-cost`, `naive-3bps` i `realistic-3bps-k0.05-vol21d`; główny jest model realistyczny. Koszt pożyczki ETF-u przy krótkiej sprzedaży nie jest modelowany.
- **Okres treningowy:** 2008-07-01 → 2017-12-31; pierwsza pozycja 2008-07-02.
- **Holdout:** 2018-01-01 → 2026-08-31, zamrożony w [config/holdout/momentum_multiasset_v1.yaml](../config/holdout/momentum_multiasset_v1.yaml) (commit `51db59f`, 2026-09-26) przed jakimkolwiek przebiegiem.
- **Walidacja:** walk-forward w oknach rocznych (Sharpe > 0 w co najmniej 2/3 okien i łączny Sharpe > 0); test permutacyjny (10 000 przetasowań, seed 0, roczny Sharpe zwrotów brutto, α = 0.1); kryterium holdoutu: Sharpe netto > 0 i p < 0.1; Sharpe ≤ 0 → `rejected`; Sharpe > 0 i p ≥ 0.1 → `inconclusive`.
- **Wielokrotne testowanie:** 2 próby na `multiasset-etf` i 2 konfiguracje w progu deflated Sharpe.
- **Status końcowy:** `confirmed` tylko przy zaliczonej bramce in-sample i zaliczonym holdoucie; niezaliczona bramka daje `rejected`; liczy go kod.

**Wynik — okres treningowy 2008-07 → 2017** (zwroty ponad gotówkę):

| Metryka | `zero-cost` (brutto) | `naive-3bps` | `realistic` |
|---|---:|---:|---:|
| CAGR | −0.23% | −0.69% | −1.54% |
| Sharpe | 0.04 | −0.00 | −0.07 |
| Sortino | 0.05 | −0.00 | −0.10 |
| Calmar | −0.01 | −0.02 | −0.05 |
| Max drawdown | −29.67% | −30.02% | −32.71% |

- **Koszty:** werdykt wrażliwości „robust” (różnica Sharpe między modelem naiwnym a realistycznym 0.07). P&L transakcji jest ujemny już przed kosztami (ok. −0.024 kapitału startowego); koszty (0.1131) pogłębiają go do −0.1373.
- **Walk-forward (realistic): niezaliczony** z dwóch powodów: tylko 6 z 10 okien ma Sharpe > 0, a łączny Sharpe jest ujemny. Kod oznacza każde okno na kalendarzu giełdowym jako niepełne ([#110](https://github.com/devTomaszStoklosa/QuantLab/issues/110)); naprawdę niepełny jest tylko rok 2008.

  | Okno | CAGR | Sharpe | Max drawdown |
  |---|---:|---:|---:|
  | 2008-07-02 → 2008-12-31 (niepełny rok) | 1.91% | 0.23 | −15.36% |
  | 2009 | −14.44% | −0.74 | −27.65% |
  | 2010 | 7.07% | 0.72 | −7.41% |
  | 2011 | −8.50% | −1.02 | −14.91% |
  | 2012 | −0.44% | −0.07 | −7.22% |
  | 2013 | 3.48% | 0.71 | −5.77% |
  | 2014 | 1.29% | 0.35 | −2.81% |
  | 2015 | 0.59% | 0.13 | −5.88% |
  | 2016 | −9.37% | −1.35 | −12.54% |
  | 2017 | 7.19% | 1.94 | −1.41% |
  | Łącznie | −1.54% | −0.07 | −32.71% |

- **Test permutacyjny:** Sharpe brutto 0.04 wobec średniej przetasowań 0.31 (odch. std. 0.29); wyższy niż tylko 17.9% przetasowań; **p = 0.821**. Faktyczny timing wypadł wyraźnie gorzej niż przeciętne losowe sparowanie tych samych pozycji z tymi samymi zwrotami.
- **Wielokrotne testowanie:** Sharpe roczny −0.07, PSR 0.41, próg deflated Sharpe 0.17, DSR 0.23.
- **Reżimy zmienności** (tercyl 21-sesyjnej zmienności SPY; opisowo): niski CAGR −0.95%, Sharpe −0.09 (970 dni); średni CAGR 1.43%, Sharpe 0.21 (720 dni); wysoki CAGR −5.71%, Sharpe −0.24 (697 dni); 5 dni bez wyznaczonego reżimu.
- **Skąd wynik** (P&L netto transakcji przy kapitale startowym 1.00; opisowo): obligacje +0.0577, nieruchomości −0.0220, dolar −0.0380, akcje −0.0637, surowce −0.0712. Zarabiały tylko SPY (+0.039) i trzy ETF-y obligacyjne (IEF +0.026, TLT +0.020, LQD +0.012); najwięcej straciły EEM (−0.080) i DBC (−0.052). Pozycje długie dały łącznie +0.170, krótkie −0.307.
- **Transakcje:** 637 (10 otwartych na końcu), 187 z dodatnim P&L netto (29%). 33 transakcje trzymane ponad rok dały +0.383, wszystkie krótsze łącznie −0.520.
- **Porównanie ze skalowaniem** (diagnostyka `momentum_voltarget_multiasset_v1`, to samo okno): bez skalowania Sharpe netto −0.08, zmienność 11.7%, obsunięcie −32.7%; ze skalowaniem 0.17, 4.4% i −8.0%.

**Obserwacje przed otwarciem holdoutu** (zacommitowane przed uruchomieniem `open-holdout`). Piszę je już po otwarciu holdoutu `momentum_voltarget_multiasset_v1`, czyli tego samego sygnału ze skalowaniem na tym samym okresie (Sharpe netto 0.07, timing poniżej średniej przetasowań), więc nie są od niego niezależne. Definicja tej hipotezy była zamrożona wcześniej, więc nic nie mogło zostać do tego wyniku dopasowane.

1. Bramka in-sample nie przeszła, więc status końcowy będzie `rejected` bez względu na holdout. Otwarcie jest opisowe: daje jedyne porównanie sygnału ze skalowaniem i bez na tym samym okresie poza próbą.
2. Wynik brutto jest ujemny jeszcze przed kosztami, a timing wypada wyraźnie gorzej niż przypadek (p = 0.821). Na tym koszyku i w tym okresie 12-miesięczne momentum nie działało w żadnej formie, którą mierzy ten pipeline.
3. Zarabiały tylko obligacje i długie pozycje; krótkie pozycje straciły łącznie −0.307. Skalowanie w siostrzanej hipotezie poprawiło wynik głównie dlatego, że przycięło tracące klasy (akcje, surowce, nieruchomości), a obligacje zostawiło w pełnej wadze: w treningu te trzy klasy przeszły z −0.157 łącznie na +0.045, a obligacje prawie się nie zmieniły (+0.058 → +0.061).
4. Do p < 0.1 Sharpe brutto na holdoucie musiałby być o ok. 0.37 wyższy niż średnia przetasowań (odchylenie z treningu 0.29), a w treningu był o 0.27 niższy. Przy Sharpe netto −0.07 w treningu werdykt holdoutu `rejected` (Sharpe ≤ 0) jest nieco bardziej prawdopodobny (ok. 60%) niż `inconclusive`.

**Wynik — holdout 2018-01-01 → 2026-08-31** (otwarty dokładnie raz, 2026-10-02 16:13 UTC, przy commicie `20b7b8e` z obserwacjami powyżej; zapis otwarcia: [config/holdout/momentum_multiasset_v1.opened.json](../config/holdout/momentum_multiasset_v1.opened.json), commit `c20919b`; model realistyczny, zwroty ponad gotówkę; liczby z zapisu otwarcia, nie łączone z treningiem):

| Metryka | Holdout |
|---|---:|
| CAGR | −0.09% |
| Sharpe netto | 0.03 |
| Sortino | 0.04 |
| Calmar | −0.00 |
| Max drawdown | −21.12% |
| p (test permutacyjny) | 0.639 |

Test permutacyjny na holdoucie: Sharpe brutto 0.17 wobec średniej przetasowań 0.29 (odch. std. 0.32); wyższy niż 36.1% przetasowań. Strategia miała pozycję przez 2176 dni, więc wynik nie ma flagi niskiej wiarygodności. **Werdykt holdoutu: `inconclusive`** (Sharpe 0.03 > 0, ale p ≥ 0.1). Ujemny CAGR przy dodatnim Sharpe nie jest sprzecznością: Sharpe liczy średnią arytmetyczną dziennych zwrotów, a CAGR geometryczną, niższą mniej więcej o połowę wariancji. Przy średniej bliskiej zera ta różnica zmienia znak.

**Wniosek: `rejected`.**

Status wynika mechanicznie z reguł zapisanych przed wynikami: walk-forward niezaliczony, więc `rejected` bez względu na werdykt holdoutu (`inconclusive`).

Co mówią liczby poza samym słowem werdyktu:

1. **Holdout powtarza obraz z treningu.** Timing jest w obu okresach gorszy niż przeciętne losowe sparowanie (Sharpe brutto 0.04 wobec 0.31 w treningu i 0.17 wobec 0.29 w holdoucie), a wynik netto jest bliski zera. Na ok. 18 latach danych 12-miesięczne momentum na tym koszyku nie wykazało przewagi.
2. **Skalowanie a jego brak na tym samym holdoucie** (oba zapisy otwarcia, ten sam okres i te same sygnały):

   | Holdout 2018 → 2026-08 | Ze skalowaniem (`momentum_voltarget_multiasset_v1`) | Bez skalowania (`momentum_multiasset_v1`) |
   |---|---:|---:|
   | CAGR | 0.21% | −0.09% |
   | Sharpe netto | 0.07 | 0.03 |
   | Max drawdown | −13.47% | −21.12% |
   | Sharpe brutto / średnia przetasowań | 0.26 / 0.30 | 0.17 / 0.29 |
   | p | 0.554 | 0.639 |

   Skalowanie znów zmniejszyło obsunięcie i nieco podniosło Sharpe. Różnica Sharpe netto skurczyła się jednak z 0.25 w treningu (0.17 wobec −0.08) do 0.04, a obie wartości nie odróżniają się od zera. To pasuje do obrazu skalowania jako ograniczenia ryzyka, a nie źródła przewagi.
3. **Prognoza sprzed otwarcia była trafna co do rzędu wielkości, nie co do werdyktu.** Rozrzut przetasowań wyszedł 0.32 przy 0.29 w treningu. Werdyktowi `rejected` dawałem ok. 60%, a wyszedł `inconclusive` przy Sharpe 0.03, czyli tuż nad granicą reguły. Status końcowy i tak jest `rejected`.

Ograniczenia tego badania:

- 10 ETF-ów wybranych w 2026 spośród notowanych do dziś (survivorship).
- Koszt pożyczki ETF-u przy krótkiej sprzedaży nie jest modelowany, a pozycje krótkie w treningu traciły (−0.307), więc ten koszt jeszcze pogorszyłby wynik.
- Zapis otwarcia nie dzieli holdoutu per klasa aktywów ani per rok ([#106](https://github.com/devTomaszStoklosa/QuantLab/issues/106)), więc nie widać, gdzie skalowanie pomogło poza próbą.
- Obserwacje sprzed otwarcia powstały po wyniku holdoutu wersji ze skalowaniem, a lata holdoutu to znana historia rynku.
- Koszty bez market impact, egzekucja po cenie zamknięcia.

Co dalej:

- Obie hipotezy momentum na `multiasset-etf` są zamknięte, a holdout 2018 → 2026-08 na tym uniwersum jest zużyty. Każda kolejna próba na tym koszyku, np. inny lookback albo inna konstrukcja sygnału, potrzebowałaby nowego, nieoglądanego okresu. Dane zaczynają się w 2008, więc zostają tylko przyszłe notowania (od 2026-09) albo inny koszyk.
- Na pytanie z q12, czy reguła jest „pod krypto”, czy działa szerzej: ani na BTC i ETH, ani na koszyku ETF-ów z pięciu klas aktywów 12-miesięczne momentum nie wykazało w holdoucie timingu lepszego niż przypadek.
- Kolejne w planie są holdouty `pairs_v1` i `mean_reversion_v1`, a po nich `portfolio_v1`.

## 2026-10-02 — pairs_v1: pairs trading ETH-USDT / BTC-USDT na kointegracji

**Hipoteza:** handel spreadem ETH-USDT względem BTC-USDT (otwarcie przy odchyleniu o 2 odchylenia standardowe, zamknięcie przy powrocie do średniej, tylko gdy test Engle'a-Grangera z ostatnich 12 miesięcy potwierdza kointegrację) daje dodatni wynik netto po kosztach, a jego timing jest lepszy niż przypadek.

**Metodologia:**

- **Dane:** Binance spot, świece dzienne, BTC-USDT i ETH-USDT (uniwersum `mvp-crypto`), te same co w `momentum_v1`. Kontrola danych (`q14`): 0 błędów; 2 ostrzeżenia to skrajne ruchy z 2020-03-12, czyli prawdziwy krach.
- **Sygnał:** parametry z Gatev, Goetzmann i Rouwenhorst (2006): okno formowania 365 dni, wejście przy |z| ≥ 2, wyjście, gdy spread przetnie średnią. ETH jest regresowane na BTC (BTC jako czynnik rynkowy), a współczynnik zabezpieczenia jest estymowany kroczącym oknem z przeszłości. Filtr Engle'a-Grangera na poziomie 5% (Vidyamurthy 2004) dopuszcza tylko nowe pozycje i nie zamyka otwartych. Wagi nóg wynikają ze współczynnika zabezpieczenia.
- **Koszty:** te same trzy modele co w `momentum_v1`; główny `realistic-10bps-k0.05-vol30d`.
- **Okres treningowy:** 2018-01-01 → 2023-12-31, okres `momentum_v1` i `mean_reversion_v1`, więc wszystkie trzy hipotezy porównuje się na identycznych danych.
- **Holdout:** 2026-01-01 → 2026-08-31, zamrożony w [config/holdout/pairs_v1.yaml](../config/holdout/pairs_v1.yaml) (commit `98bbc2b`, 2026-09-24) przed jakimkolwiek przebiegiem. Lata 2024–2025 to zużyty holdout `momentum_v1`.
- **Walidacja:** walk-forward w oknach rocznych (Sharpe > 0 w co najmniej 2/3 okien z określonym Sharpe i łączny Sharpe > 0; nierozstrzygnięty, gdy takich okien jest mniej niż 3); test permutacyjny (10 000 przetasowań, seed 0, roczny Sharpe zwrotów brutto, α = 0.1); kryterium holdoutu: Sharpe netto > 0 i p < 0.1; Sharpe ≤ 0 → `rejected`; Sharpe > 0 i p ≥ 0.1 → `inconclusive`; brak pozycji (Sharpe nieokreślony) → `inconclusive`.
- **Wielokrotne testowanie:** 6 prób na `mvp-crypto` 2018–2023 i 11 konfiguracji w progu deflated Sharpe.
- **Status końcowy:** `confirmed` tylko przy zaliczonej bramce in-sample i zaliczonym holdoucie; niezaliczona którakolwiek bramka → `rejected`; pozostałe przypadki → `inconclusive`. Liczy go kod.

**Wynik — okres treningowy 2018–2023:**

| Metryka | `zero-cost` (brutto) | `naive-10bps` | `realistic` |
|---|---:|---:|---:|
| CAGR | 0.52% | 0.47% | 0.41% |
| Sharpe | 0.15 | 0.14 | 0.12 |
| Sortino | 0.30 | 0.28 | 0.24 |
| Calmar | 0.08 | 0.07 | 0.06 |
| Max drawdown | −6.69% | −6.73% | −6.77% |

- **Jedna pozycja w sześć lat.** Strategia otworzyła spread raz: długie ETH (waga 0.57) i krótkie BTC (0.43) od 2023-09-11 do 2023-12-07, czyli 87 dni. Noga ETH dała +0.2523, noga BTC −0.2275, razem +0.0248 kapitału startowego netto, przy kosztach 0.0070. Wszystkie metryki powyżej opisują więc tę jedną transakcję rozłożoną na sześć lat.
- **Kointegracja** (cały okres treningowy, 2191 dni; opisowo): współczynnik zabezpieczenia 1.32, statystyka Engle'a-Grangera −2.17 wobec wartości krytycznej −3.34 na poziomie 5% (p = 0.44), czas połowicznego powrotu spreadu 279 dni. Na całym okresie ETH i BTC nie są skointegrowane, a filtr na kroczącym 12-miesięcznym oknie przepuścił tylko jedno wejście.
- **Koszty:** werdykt wrażliwości „robust” (różnica Sharpe między modelem naiwnym a realistycznym 0.02).
- **Walk-forward: nierozstrzygnięty**, bo Sharpe ma tylko jedno okno (2023-09-12 → 2023-12-31: CAGR 8.37%, Sharpe 0.54), a reguła wymaga co najmniej trzech.
- **Test permutacyjny:** Sharpe brutto 0.15 wobec średniej przetasowań 0.09 (odch. std. 0.40); wyższy niż 54.7% przetasowań; **p = 0.453**, nieistotny przy α = 0.1; kod oznacza go flagą niskiej wiarygodności (87 dni z pozycją).
- **Wielokrotne testowanie:** Sharpe roczny 0.54, PSR 0.62, próg deflated Sharpe 2.95, DSR 0.08. Próg jest tak wysoki, bo Sharpe z 87 dni ma ogromny błąd.
- **Reżimy zmienności:** po 36–38 dni w każdym tercylu, więc bez wartości opisowej.

**Obserwacje przed otwarciem holdoutu** (zacommitowane przed uruchomieniem `open-holdout`, więc wynik holdoutu nie mógł na nie wpłynąć):

1. W treningu nie da się niczego ocenić: jedna transakcja, bramka in-sample nierozstrzygnięta, test z flagą niskiej wiarygodności. Status końcowy może więc być co najwyżej `inconclusive`, a przy Sharpe holdoutu ≤ 0 będzie `rejected`.
2. Filtr kointegracji działa zgodnie z zamysłem, czyli rzadko wpuszcza strategię na rynek, bo para ETH/BTC przez większość czasu nie jest skointegrowana. To raczej ustalenie o parze niż o regule handlu.
3. Holdout trwa 8 miesięcy. Przy jednym wejściu na ok. 5.4 roku, w których handel był możliwy, naiwnie liczony brak pozycji w holdoucie ma ok. 90% szans. Kryterium ocenia go jako `inconclusive`. Gdyby pozycja się pojawiła, wynik też będzie opierał się na jednej transakcji.
4. Ceny z tego okresu zostały już odczytane przy otwarciu `momentum_select_v1` i `momentum_voltarget_v1`, ale ta definicja była zamrożona wcześniej (2026-09-24), więc nic nie mogło zostać do nich dopasowane.

**Wynik — holdout 2026-01-01 → 2026-08-31:** _holdout nieotwarty w chwili zapisu obserwacji powyżej._

**Wniosek:** _po otwarciu holdoutu._
