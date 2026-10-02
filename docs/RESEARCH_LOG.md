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

**Wynik — holdout 2026-01-01 → 2026-08-31:** _holdout nieotwarty w chwili zapisu obserwacji powyżej._

**Wniosek:** _po otwarciu holdoutu._
