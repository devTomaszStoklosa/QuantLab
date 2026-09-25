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

Should have — wybrane przez Tomasza 2026-09-25 jako następny epik po `q1`–`q8`. Kod (reguły alokacji, strategia portfelowa, raport) powstał na danych syntetycznych; definicja zamrożona po decyzjach 1–6 poniżej (P7, 2026-09-25); przebiegi czekają na lokalny dostęp do Binance, a holdout portfela — na otwarcie holdoutów jego składników.

## Dependencies and risks

- Zależy od `q2` (parytet silników, sizer), `q4` (kontrakt wag), `q6` (rejestr prób, DSR), `q7` (magazyn wyników i aplikacja) i `q8` (zwroty netto przebiegu na obciętej historii, wzorzec zapamiętanego wyboru).
- **Ryzyko: przeciek przez holdouty składników.** Holdout portfela nachodzący na nieotwarty holdout składnika. Mitygacja: `open-holdout` portfela wymaga zapisanych otwarć holdoutów składników (AC-4).
- **Ryzyko: składnik bez pozycji.** `momentum_select_v1` nie ma pozycji przed 2020-01-02 — zerowa zmienność w oknie estymacji. Mitygacja: składnik bez zdefiniowanej zmienności w oknie dostaje wagę 0, reszta jest normalizowana; portfel bez żadnego takiego składnika nie ma pozycji.
- **Ryzyko: składniki silnie skorelowane.** `momentum_v1` i `momentum_select_v1` to obie time-series momentum; odwrotność zmienności ich nie rozróżnia, risk parity tak. Mitygacja: macierz korelacji i współczynnik dywersyfikacji w raporcie, reguła wybrana przed wynikiem (pytanie 2).
- **Ryzyko: wielokrotne testowanie.** Portfel to kolejna próba na `mvp-crypto` 2018–2023 — zaostrza próg DSR pozostałych, zgodnie z prawdą, opisowo.

## Decisions

Odpowiedzi na pytania 1–6, przyjęte przez Tomasza 2026-09-25 (wszystkie propozycje); zamrożone w `config/holdout/portfolio_v1.yaml` (P7):

| # | Question | Decision |
|---|---|---|
| 1 | Składniki | **`momentum_v1`, `mean_reversion_v1`, `pairs_v1`, `momentum_select_v1`**, każdy z parametrami, sizerem, polityką rebalansu i modelem kosztów ze swojej zamrożonej definicji |
| 2 | Reguła alokacji | **Odwrotność zmienności** 90-dniowych zwrotów netto rękawu; równe wagi i risk parity opisowo. Pomiar P3 na danych syntetycznych: rękaw pary (zabezpieczony, o niskiej zmienności) dostaje w okresach handlu 0,5–0,65 wagi |
| 3 | Okno i harmonogram | Okno **90 dni**, rebalans wag **1. dnia każdego miesiąca**, rękaw kwalifikowany **60 dni** po pierwszym dniu z pozycją i z wariancją w oknie |
| 4 | Kryterium i bramka | Jak pozostałe hipotezy krypto: **walk-forward** jako bramka in-sample; na holdoucie Sharpe netto > 0 i p < 0.1 z testu tasowania dni; porównanie ze składnikami i z równymi wagami opisowo |
| 5 | Okresy | Trening **2018-01-01 → 2023-12-31**, holdout **2026-01-01 → 2026-08-31**, otwierany dopiero po zapisanych otwarciach holdoutów `mean_reversion_v1`, `pairs_v1` i `momentum_select_v1` (straż `open-holdout`, REQ-930); wagi na 2026 z historii do 2025-12-31 |
| 6 | Liczba prób | Jedna próba i jedna konfiguracja: na `mvp-crypto` 2018–2023 razem 5 prób i 10 konfiguracji |

## Open questions

Brak — wszystkie decyzje potrzebne do zamrożenia (P7) przyjęte.
