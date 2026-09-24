# q6-advanced-validation-cpcv - Walidacja przy wielu próbach: PSR, deflated Sharpe, PBO i jawny rejestr prób

Status: Ready for dev
Owner role: PO
Upstream: docs/specs/q1-momentum-research-mvp/, docs/specs/q3-mean-reversion-hypothesis/
Links: docs/ROADMAP.md, docs/RESEARCH_LOG.md

## Problem

Każda kolejna hipoteza testowana na tych samych danych zwiększa szansę, że któraś „zadziała" przez przypadek. Na koszyku `mvp-crypto` i okresie 2018–2023 są już dwie: `momentum_v1` (zakończona, `inconclusive`) i `mean_reversion_v1` (zamrożona, czeka na przebieg treningowy). Dziennik i 01-story `q3` odsyłają korektę na wielokrotne testowanie do tego epiku.

Dziś brakuje trzech rzeczy:

1. **Sharpe bez przedziału wiarygodności.** Raport podaje Sharpe z okresu treningowego, ale nie mówi, na ile jest on odróżnialny od zera przy tej długości historii i przy grubych ogonach dziennych zwrotów krypto (skośność, kurtoza).
2. **Liczba prób liczona ręcznie.** REQ-350 z `q3` wymaga podania jej w dzienniku, ale nic jej nie liczy — a próba, której plik ktoś usunie, znika z rachunku.
3. **Brak korekty na wybór najlepszej z N prób.** Najlepszy z N przebiegów bez żadnej przewagi ma dodatni Sharpe w oczekiwaniu; próg „Sharpe > 0" nie uwzględnia N.

## Outcome

Primary metric: dla każdej hipotezy okres treningowy ma w raporcie probabilistic Sharpe ratio (PSR), deflated Sharpe ratio (DSR) z liczbą prób policzoną z historii gita i — gdy prób na tych samych danych jest co najmniej dwie — probability of backtest overfitting (PBO) dla wyboru najlepszej z nich.
Guardrail metric: żaden zamrożony werdykt ani kryterium się nie zmienia — nowe miary są opisowe dla hipotez już zamrożonych i mogą wejść do kryterium sukcesu dopiero hipotezy zamrażanej po tym epiku.

## User story

Jako badacz testujący kolejne hipotezy na tych samych danych chcę, żeby raport sam liczył, ile prób było na tych danych, i pokazywał Sharpe skorygowany o długość historii, kształt rozkładu zwrotów i liczbę prób, żeby wynik jednej z nich nie wyglądał na przewagę tylko dlatego, że była najlepsza z kilku.

## Acceptance criteria

- AC-1 (PSR): Given dzienne zwroty netto przebiegu, when liczę PSR względem progu Sharpe, then wynik uwzględnia długość historii, skośność i kurtozę, a dla zwrotów normalnych (skośność 0, kurtoza 3) sprowadza się do Φ(SR·√(T−1)/√(1 + SR²/2)) — błędu standardowego Sharpe z Lo (2002).
- AC-2 (rejestr prób): Given definicje hipotez w `config/holdout/`, when liczę próby na danych danej hipotezy, then liczą się wszystkie definicje kiedykolwiek zacommitowane (także później usunięte) z tym samym uniwersum i nachodzącym okresem treningowym, a niezacommitowany szkic się nie liczy.
- AC-3 (DSR): Given N prób i dzienne zwroty przebiegu, when liczę DSR, then próg Sharpe to oczekiwane maksimum N prób bez przewagi, a przykład liczbowy z pracy Bailey i López de Prado (2014) daje opublikowany wynik.
- AC-4 (PBO): Given macierz dziennych zwrotów N ≥ 2 konfiguracji na wspólnych datach, when liczę PBO metodą CSCV, then dostaję odsetek podziałów, w których konfiguracja najlepsza in-sample wypada poniżej mediany out-of-sample — ok. 0.5 dla czystego szumu i ok. 0 dla konfiguracji z wyraźną przewagą.
- AC-5 (raport): Given przebieg treningowy hipotezy, when uruchamiam `quantlab run`, then terminal i tear-sheet pokazują PSR, liczbę prób z ich listą, próg Sharpe i DSR — jako opis poza regułami statusu.
- AC-6 (porównanie prób): Given hipoteza, when uruchamiam `quantlab trials`, then dostaję tabelę wszystkich prób na tych samych danych (Sharpe, PSR, DSR) i PBO wyboru najlepszej z nich, liczone tylko na okresach treningowych.

## Out of scope

- **CPCV i purged k-fold.** Obie metody oceniają parametry dopasowywane na danych treningowych; strategie w laboratorium mają parametry z literatury, więc każda ścieżka CPCV byłaby tym samym przebiegiem. Wracają z pierwszą hipotezą z parametrami dopasowywanymi (`q4`, np. współczynnik zabezpieczenia w pairs trading). Nazwa epiku zostaje, żeby nie łamać ROADMAP.
- **Zmiana zamrożonych kryteriów lub werdyktów.** `momentum_v1` i `mean_reversion_v1` zachowują swoje kryteria sukcesu; DSR i PBO są przy nich opisowe.
- **DSR z empiryczną wariancją Sharpe między próbami.** Przy 2–3 próbach wariancja z 1–2 stopniami swobody nic nie mówi; wariant empiryczny ma sens przy kilkunastu próbach.
- **Efektywna liczba niezależnych prób** (grupowanie skorelowanych prób). Liczymy wszystkie próby jako niezależne, co zawyża próg — błąd w bezpieczną stronę.

## Priority

Should have — wymieniony wprost w `q3` (01-story, ryzyko wielokrotnego testowania) i we wniosku `momentum_v1`. Kod i testy nie wymagają danych rynkowych; zastosowanie do obu hipotez czeka na lokalne przebiegi (`q3`-M5).

## Dependencies and risks

- Zależy od `q1` (metryki, `BacktestRun`, tear-sheet) i `q3`-M1 (definicje hipotez jako zacommitowane pliki).
- **Ryzyko: miary opisowe potraktowane jak nowe kryterium po fakcie.** Mitygacja: w raporcie są oznaczone „poza regułami statusu"; status nadal liczy `concluded_status` z zamrożonych reguł.
- **Ryzyko: PBO przy N = 2 jest zgrubne.** Z dwiema konfiguracjami PBO to po prostu odsetek podziałów, w których lepsza in-sample jest gorsza out-of-sample. Raport podaje N obok wyniku.
- **Ryzyko: rejestr prób da się obejść** (np. trenując poza `config/holdout/`). Mitygacja częściowa: `quantlab run` nie uruchamia hipotezy bez zacommitowanej definicji (REQ-303), a usunięcie pliku nie zmniejsza liczby prób. Przebiegi poza CLI pozostają kwestią dyscypliny — opisaną w dzienniku.

## Open questions

Brak pytań blokujących. Ustawienia metodologii (stałe dla całego laboratorium, jak liczba permutacji) przyjęte z literatury:

| # | Decyzja | Uzasadnienie |
|---|---|---|
| 1 | Próg PSR: Sharpe 0 | pytanie „czy przewaga w ogóle istnieje", spójne z kryterium holdoutu (Sharpe > 0) |
| 2 | Wariancja Sharpe między próbami w DSR: pod hipotezą zerową, 1/(T−1) na okres | przy wszystkich próbach bez przewagi rozrzut ich Sharpe to błąd estymacji; nie wymaga wielu prób (Out of scope, punkt 3) |
| 3 | CSCV: 16 bloków, wszystkie C(16, 8) = 12 870 podziałów | wartość z przykładu w pracy Bailey, Borwein, López de Prado, Zhu (2017) |
| 4 | Zwroty do PSR/DSR: dzienne netto (model realistyczny) od pierwszej pozycji | jak walk-forward i reżimy — rozgrzewka bez pozycji nie zaniża wariancji |
