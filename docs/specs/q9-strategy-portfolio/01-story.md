# q9-strategy-portfolio - Portfel strategii: łączenie hipotez regułą alokacji ryzyka

Status: Ready for dev
Owner role: PO
Upstream: docs/specs/q8-parameter-selection-cpcv/, docs/specs/q6-advanced-validation-cpcv/, docs/specs/q4-pairs-trading-stat-arb/
Links: docs/ROADMAP.md, docs/RESEARCH_LOG.md

## Problem

Laboratorium ma cztery zamrożone hipotezy na tych samych danych (`mvp-crypto`, trening 2018–2023): `momentum_v1`, `mean_reversion_v1`, `pairs_v1`, `momentum_select_v1`. Każda jest oceniana osobno, a pytanie, które w praktyce systematycznego tradingu przychodzi zaraz potem — **co daje ich połączenie** — nie ma w laboratorium formy:

1. **Brak hipotezy o portfelu.** Definicja opisuje jedną strategię. Nie da się zapisać „te cztery strategie, ważone odwrotnością zmienności, rebalans co miesiąc" i przepuścić tego przez walidację, holdout i raport.
2. **Łączenie krzywych kapitału kłamie o kosztach.** Średnia ważona zwrotów strategii zakłada, że każda płaci za swój obrót osobno. Momentum długie na BTC i odwrócenie krótkie na BTC to w portfelu pozycja netto bliska zera — i obrót, którego nie trzeba robić. Uczciwy portfel handluje pozycjami netto.
3. **Alokacja to też dopasowanie.** Wagi z przeszłej zmienności albo kowariancji to parametry liczone na danych; liczone z danymi z przyszłości (choćby o dzień) dają portfel lepszy niż możliwy. Muszą powstawać wyłącznie z historii sprzed dnia rebalansu, jak wybór z siatki w `q8`.
4. **Holdout portfela zdradza holdouty składników.** Trzy z czterech składników mają wspólny, jeszcze nieotwarty holdout 2026-01-01 → 2026-08-31. Otwarcie holdoutu portfela na tym okresie pokazałoby wynik składników przed ich własnym, jednorazowym otwarciem.

## Outcome

Primary metric: hipoteza portfelowa ma jednoznaczny status w `docs/RESEARCH_LOG.md`, a jej wynik zawiera Sharpe netto portfela na holdoucie, korelacje składników, współczynnik dywersyfikacji, historię wag i porównanie z każdym składnikiem oraz z innymi regułami alokacji — opisowo.
Guardrail metric: wyniki wszystkich zamrożonych hipotez identyczne co do bitu; ich holdouty otwierane wyłącznie przez ich własny, jednorazowy `open-holdout`.

## User story

Jako badacz chcę zamrozić **regułę łączenia** zamrożonych strategii (składniki, reguła alokacji ryzyka, okno estymacji, harmonogram rebalansu) i ocenić portfel pozycji netto tym samym pipeline'em co pojedynczą hipotezę, żeby wiedzieć, czy dywersyfikacja między strategiami laboratorium daje coś po kosztach — a nie tylko na wykresie średniej krzywych.

## Acceptance criteria

- AC-1 (reguła alokacji): Given dzienne zwroty netto składników z okna estymacji, when liczę wagi, then równe wagi, odwrotność zmienności i równy wkład w ryzyko (risk parity) dają wagi nieujemne sumujące się do 1, zgodne z wartościami policzalnymi z góry na danych syntetycznych (np. dwa nieskorelowane składniki o zmienności 1 i 2 → 2/3 i 1/3).
- AC-2 (portfel pozycji netto): Given składniki i ich wagi, when portfel działa, then w każdym dniu jego pozycja w instrumencie to suma pozycji składników pomnożonych przez ich wagi; silnik handluje i kosztuje tylko zmianę pozycji netto, a oba silniki widzą jedną strategię (parytet jak w `q2`).
- AC-3 (bez zaglądania w przyszłość): Given dzień rebalansu d, when liczę wagi, then używam wyłącznie barów sprzed d; zmiana baru z dnia d lub późniejszego nie zmienia wag; przed pierwszym rebalansem z wystarczającą historią portfel nie ma pozycji.
- AC-4 (holdout składników): Given portfel ze składnikiem, którego holdout nie jest otwarty, when otwieram holdout portfela nachodzący na holdout składnika, then `open-holdout` odmawia przed pobraniem danych i wskazuje składniki do otwarcia najpierw.
- AC-5 (raport): Given przebieg treningowy portfela, when uruchamiam `quantlab run`, then terminal, tear-sheet, magazyn wyników i aplikacja pokazują korelacje składników, współczynnik dywersyfikacji, wagi (średnie, najniższe, najwyższe) i opisowe porównanie reguł alokacji oraz składników.
- AC-6 (wynik): Given zamrożona definicja i jednorazowo otwarty holdout, when zapisuję wpis w dzienniku, then zawiera status, porównanie z każdym składnikiem i z równymi wagami oraz DSR z próbami na tych samych danych.

## Out of scope

- Portfele między klasami aktywów (`xsmom_v1` na S&P 500): inny kalendarz (252 vs 365 sesji), inne okresy treningu — osobne pytanie o wspólny kalendarz.
- Dźwignia i celowanie w zmienność portfela (volatility targeting) — suma wag 1, bez pożyczania.
- Optymalizacja średniej–wariancji z prognozą zwrotów (Markowitz z oczekiwanymi zwrotami) — prognozy zwrotów składników to osobna hipoteza.
- Dobór reguły alokacji na danych (wybór najlepszej z kilku) — reguła jest zamrożona; pozostałe są opisowe.
- Zmiana zamrożonych definicji składników i ich werdyktów.

## Priority

Should have — wybrane przez Tomasza 2026-09-25 jako następny epik po `q1`–`q8`. Kod (reguły alokacji, strategia portfelowa, raport) powstaje na danych syntetycznych; zamrożenie czeka na odpowiedzi poniżej; przebiegi — na lokalny dostęp do Binance, a holdout portfela — na otwarcie holdoutów jego składników.

## Dependencies and risks

- Zależy od `q2` (parytet silników, sizer), `q4` (kontrakt wag), `q6` (rejestr prób, DSR), `q7` (magazyn wyników i aplikacja) i `q8` (zwroty netto przebiegu na obciętej historii, wzorzec zapamiętanego wyboru).
- **Ryzyko: przeciek przez holdouty składników.** Holdout portfela nachodzący na nieotwarty holdout składnika. Mitygacja: `open-holdout` portfela wymaga zapisanych otwarć holdoutów składników (AC-4).
- **Ryzyko: składnik bez pozycji.** `momentum_select_v1` nie ma pozycji przed 2020-01-02 — zerowa zmienność w oknie estymacji. Mitygacja: składnik bez zdefiniowanej zmienności w oknie dostaje wagę 0, reszta jest normalizowana; portfel bez żadnego takiego składnika nie ma pozycji.
- **Ryzyko: składniki silnie skorelowane.** `momentum_v1` i `momentum_select_v1` to obie time-series momentum; odwrotność zmienności ich nie rozróżnia, risk parity tak. Mitygacja: macierz korelacji i współczynnik dywersyfikacji w raporcie, reguła wybrana przed wynikiem (pytanie 2).
- **Ryzyko: wielokrotne testowanie.** Portfel to kolejna próba na `mvp-crypto` 2018–2023 — zaostrza próg DSR pozostałych, zgodnie z prawdą, opisowo.

## Open questions

Blokują zamrożenie (ostatni slice); kod powstaje na danych syntetycznych.

| # | Question | Owner | Due |
|---|---|---|---|
| 1 | Składniki. Propozycja: wszystkie cztery hipotezy krypto — **`momentum_v1`, `mean_reversion_v1`, `pairs_v1`, `momentum_select_v1`** — z ich zamrożonymi parametrami i modelami kosztów. Alternatywa: bez `momentum_select_v1` (to też momentum szeregów czasowych, silnie skorelowane z `momentum_v1`) | Tomasz | przed zamrożeniem |
| 2 | Reguła alokacji. Propozycja: **odwrotność zmienności** (wagi ∝ 1/σ zwrotów netto składnika w oknie estymacji) — odporna przy czterech składnikach, bez odwracania macierzy kowariancji; równe wagi i risk parity (równy wkład w ryzyko) opisowo. Alternatywa: risk parity jako reguła zamrożona (uwzględnia korelacje, np. dwóch momentum) | Tomasz | przed zamrożeniem |
| 3 | Okno i harmonogram. Propozycja: okno estymacji **90 dni** zwrotów netto sprzed dnia rebalansu, rebalans wag **pierwszego dnia każdego miesiąca**, co najmniej **60 dni** ze zmiennością w oknie, żeby składnik dostał wagę; pozycje składników zmieniają się codziennie jak w ich definicjach | Tomasz | przed zamrożeniem |
| 4 | Kryterium i bramka. Propozycja: jak pozostałe hipotezy krypto — walk-forward jako bramka in-sample, na holdoucie Sharpe netto > 0 i p < 0.1 z testu tasowania dni; porównanie z najlepszym składnikiem i z równymi wagami **opisowo**. Alternatywa: kryterium „Sharpe netto portfela > Sharpe najlepszego składnika na holdoucie" (pytanie o przewagę dywersyfikacji, nie o przewagę w ogóle) | Tomasz | przed zamrożeniem |
| 5 | Okresy. Propozycja: trening **2018-01-01 → 2023-12-31** (jak składniki), holdout **2026-01-01 → 2026-08-31**, otwierany dopiero po otwarciu holdoutów `mean_reversion_v1`, `pairs_v1` i `momentum_select_v1` (`momentum_v1` ma już otwarty 2024–2025). Wagi na 2026 z historii do 2025-12-31 | Tomasz | przed zamrożeniem |
| 6 | Liczba prób. Propozycja: portfel to jedna próba i jedna konfiguracja na `mvp-crypto` 2018–2023 (reguły opisowe nie są wybierane, więc nie są próbami): 5 prób, 10 konfiguracji | Tomasz | przed zamrożeniem |
