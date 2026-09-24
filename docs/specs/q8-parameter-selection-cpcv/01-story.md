# q8-parameter-selection-cpcv - Parametr dobierany na danych: selekcja z siatki, re-optymalizacja i CPCV

Status: Ready for dev
Owner role: PO
Upstream: docs/specs/q6-advanced-validation-cpcv/, docs/specs/q1-momentum-research-mvp/
Links: docs/ROADMAP.md, docs/RESEARCH_LOG.md

## Problem

Każda hipoteza w laboratorium ma parametry z literatury, zamrożone przed przebiegiem (`momentum_v1`: lookback 365 dni). W praktyce badawczej parametr często dobiera się na danych — i wtedy ocenić trzeba **procedurę doboru**, nie parametr wybrany po fakcie. Dziś laboratorium nie umie tego wyrazić:

1. **Brak hipotezy z parametrem z danych.** Definicja zamraża wartość, nie regułę wyboru. Nie da się zapisać „lookback z siatki, wybierany co rok po Sharpe netto z przeszłości".
2. **Walk-forward bez re-optymalizacji.** `WalkForwardValidator` tnie jeden przebieg na lata — poprawne dla parametru z literatury, ale parametr dobierany na danych musi być w każdym oknie dobrany na nowo, tylko z danych sprzed okna.
3. **Jedna ścieżka out-of-sample.** Walk-forward daje jeden szereg zwrotów spoza próby — jedną, zaszumioną realizację. CPCV (combinatorial purged cross-validation, López de Prado 2018, rozdz. 12) daje z tych samych danych wiele ścieżek, z purgingiem i embargo przeciw przeciekom na granicach okresu treningowego i testowego. `q6` odłożył CPCV właśnie do pierwszej takiej hipotezy.
4. **Siatka to wiele prób.** Wybór najlepszej z K wartości to K prób w sensie DSR; rejestr `q6` liczy jedną próbę na definicję.

## Outcome

Primary metric: hipoteza z parametrem dobieranym na danych ma jednoznaczny status w `docs/RESEARCH_LOG.md`, a jej wynik zawiera rozkład Sharpe procedury doboru na ścieżkach CPCV, PBO siatki, DSR z liczbą konfiguracji siatki i wynik zamrożonej procedury na holdoucie.
Guardrail metric: wyniki wszystkich zamrożonych hipotez identyczne co do bitu; ich DSR (opisowy) zmienia się tylko przez nowe konfiguracje na tych samych danych — jawnie opisane.

## User story

Jako badacz chcę zamrozić **procedurę** wyboru parametru (siatkę, miarę, harmonogram) zamiast samego parametru i ocenić ją na wielu ścieżkach spoza próby, żeby „najlepszy lookback z perspektywy czasu" nie uchodził za przewagę.

## Acceptance criteria

- AC-1 (selekcja jako strategia): Given zamrożona siatka, miara i harmonogram, when strategia działa, then w każdym dniu ponownego wyboru bierze wartość z najlepszą miarą policzoną wyłącznie na danych sprzed tego dnia, handluje nią do następnego wyboru, a oba silniki widzą jedną strategię (zmiana wartości to handel z kosztami); przed pierwszym wyborem z wystarczającą historią nie ma pozycji.
- AC-2 (podziały CPCV): Given T okresów, N grup i k grup testowych, when dzielę, then jest C(N, k) podziałów i φ = k·C(N, k)/N ścieżek, każda pokrywa każdy okres dokładnie raz, a zbiór treningowy nie zawiera okresów purgingu przed i embargo po każdej grupie testowej.
- AC-3 (ocena CPCV): Given dzienne zwroty netto każdej wartości siatki, when uruchamiam CPCV procedury, then każdy podział wybiera wartość na swoim zbiorze treningowym i bierze jej zwroty na zbiorze testowym; wynik to rozkład Sharpe ścieżek i częstość wyboru każdej wartości — dodatni dla siatki z wyraźnie najlepszą wartością, wokół zera dla czystego szumu.
- AC-4 (przeuczenie): Given hipoteza z siatką, when raportuję wynik, then PBO siatki (CSCV z `q6`) i DSR z liczbą prób liczącą konfiguracje siatki wszystkich prób na tych samych danych.
- AC-5 (raport): Given przebieg treningowy, when uruchamiam `quantlab run`, then terminal, tear-sheet, magazyn wyników i aplikacja pokazują historię wyborów, podsumowanie CPCV i PBO.
- AC-6 (wynik): Given zamrożona definicja i jednorazowo otwarty holdout, when zapisuję wpis w dzienniku, then zawiera status, rozkład CPCV, PBO, DSR i porównanie z parametrem z literatury (`momentum_v1`).

## Out of scope

- Modele uczenia maszynowego i purged k-fold dla klasyfikatorów — w laboratorium nie ma modeli z etykietami o wielodniowym horyzoncie.
- Siatki wielowymiarowe — jeden parametr; wiele parametrów to wykładniczo więcej konfiguracji i osobne pytanie o liczbę prób.
- Dobór kosztów, uniwersum albo reguły wyboru na danych — zamrożone jak dotąd.
- Zmiana zamrożonych definicji i werdyktów.

## Priority

Should have — wybrane przez Tomasza 2026-09-24 jako następny epik po `q1`–`q7`. Kod (strategia z doborem, CPCV, raport) powstaje na danych syntetycznych; zamrożenie czeka na odpowiedzi poniżej, przebiegi — na lokalny dostęp do Binance.

## Dependencies and risks

- Zależy od `q1` (pipeline, walk-forward), `q2` (parytet silników), `q6` (rejestr prób, PSR, DSR, PBO) i `q7` (magazyn wyników i aplikacja).
- **Ryzyko: przeciek w CPCV.** Zbiór treningowy może leżeć po testowym; sygnał z oknem wstecz przenosi informację z okresu testowego do treningowego. Mitygacja: embargo po każdej grupie testowej (i purging przed nią), wielkość zamrożona w definicji.
- **Ryzyko: kosztowna selekcja.** Każdy wybór to K przebiegów na rosnącej historii. Mitygacja: wybór raz na okres harmonogramu, zapamiętany; pomiar czasu.
- **Ryzyko: wielokrotne testowanie rośnie.** Siatka K wartości na `mvp-crypto` 2018–2023 zaostrza próg DSR pozostałych hipotez na tych danych — zgodnie z prawdą, opisowo.
- **Ryzyko: CPCV bez kosztów przejść.** Ścieżka składa grupy testowe z różnych podziałów, być może z różnymi wybranymi wartościami; przejścia między nimi nie są kosztowane. Mitygacja: jawne ograniczenie w raporcie; najwyżej N − 1 przejść na ścieżkę.

## Open questions

Blokują zamrożenie (ostatni slice); kod powstaje na danych syntetycznych.

| # | Question | Owner | Due |
|---|---|---|---|
| 1 | Hipoteza i uniwersum. Propozycja: **`momentum_select_v1`** — time-series momentum na `mvp-crypto` (BTC, ETH), lookback z siatki **30, 60, 90, 180, 270, 365 dni**, jako kontrast z `momentum_v1` (365 z literatury): czy dobór na danych coś daje po uwzględnieniu przeuczenia? Alternatywa: formacja momentum przekrojowego na S&P 500 (3, 6, 9, 12 miesięcy) — cięższe, wymaga Tiingo | Tomasz | przed zamrożeniem |
| 2 | Reguła wyboru. Propozycja: annualizowany Sharpe netto (model realistyczny definicji), historia zakotwiczona (od początku danych do dnia przed wyborem), ponowny wybór w pierwszym dniu notowań każdego roku kalendarzowego, co najmniej 365 dni historii przed pierwszym wyborem (wcześniej brak pozycji), remis — pierwsza wartość siatki | Tomasz | przed zamrożeniem |
| 3 | Ustawienia CPCV. Propozycja: **N = 10** grup, **k = 2** grupy testowe (45 podziałów, 9 ścieżek), purging **1 dzień** przed każdą grupą testową (horyzont zwrotu), embargo **1% okresów** treningu po każdej (López de Prado 2018, ok. 22 dni przy 6 latach) | Tomasz | przed zamrożeniem |
| 4 | Bramka in-sample. Propozycja: **CPCV zamiast walk-forward**: zaliczona, gdy mediana Sharpe netto ścieżek > 0; niezaliczona, gdy ≤ 0; nierozstrzygnięta, gdy mniej niż połowa ścieżek ma zdefiniowany Sharpe. Walk-forward z re-optymalizacją i PBO — opisowo. Alternatywa: walk-forward z re-optymalizacją jako bramka, CPCV opisowo | Tomasz | przed zamrożeniem |
| 5 | Okresy i kryterium holdoutu. Propozycja: trening 2018-01-01 → 2023-12-31 (jak pozostałe hipotezy krypto), holdout **2026-01-01 → 2026-08-31** (ten sam, jeszcze nieotwarty, co `mean_reversion_v1` i `pairs_v1`); kryterium: Sharpe netto > 0 i p < 0.1 z testu tasowania dni (momentum szeregów czasowych to timing); wybór na holdout z całej historii przed 2026-01-01 (także 2024–2025) | Tomasz | przed zamrożeniem |
| 6 | Liczba prób. Propozycja: każda wartość siatki to konfiguracja, a próg DSR liczy konfiguracje wszystkich prób na tych samych danych (dziś 3 definicje → 3 + 6 = 9 konfiguracji na `mvp-crypto` 2018–2023) | Tomasz | przed zamrożeniem |
