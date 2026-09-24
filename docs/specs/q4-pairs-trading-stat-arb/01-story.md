# q4-pairs-trading-stat-arb - Trzecia rodzina hipotez: pairs trading na kointegracji (stat arb)

Status: Ready for dev
Owner role: PO
Upstream: docs/specs/q1-momentum-research-mvp/, docs/specs/q3-mean-reversion-hypothesis/, docs/specs/q6-advanced-validation-cpcv/
Links: docs/ROADMAP.md, docs/RESEARCH_LOG.md

## Problem

Obie dotychczasowe hipotezy grają na kierunek pojedynczych instrumentów: `momentum_v1` na trend, `mean_reversion_v1` na jego krótkie odwrócenie. Obie są więc wystawione na ruch całego rynku krypto. Pairs trading (statistical arbitrage) gra na coś innego — na względną cenę dwóch instrumentów: gdy ich kointegrowany spread odjedzie od średniej, pozycja długa w jednym i krótka w drugim zakłada jego powrót. Ekspozycja na rynek jest z założenia bliska zeru.

Tego nie da się dziś przetestować z dwóch powodów:

1. **Silniki ważą pozycje tylko równo po znaku sygnału.** Para potrzebuje wag w proporcji współczynnika zabezpieczenia (hedge ratio) i obu nóg naraz — albo żadnej.
2. **Brak narzędzi kointegracji.** Test Engle'a-Grangera, współczynnik zabezpieczenia i okres półtrwania spreadu trzeba policzyć kodem, zanim ktokolwiek zinterpretuje wynik.

To trzecia hipoteza na tych samych danych (`mvp-crypto`, 2018–2023), więc liczba prób w DSR (`q6`) wzrośnie do 3.

## Outcome

Primary metric: hipoteza `pairs_v1` (spread ETH-USDT względem BTC-USDT) ma jednoznaczny status w `docs/RESEARCH_LOG.md`, poparty walk-forward, zamrożonym holdoutem, testem kointegracji na okresie treningowym i DSR z N = 3.
Guardrail metric: dla strategii istniejących po zmianie kontraktu wag wyniki obu silników są identyczne co do bitu; parametry `pairs_v1` są zamrożone, zanim jakikolwiek jej przebieg przeczyta dane rynkowe.

## User story

Jako badacz chcę przetestować strategię rynkowo neutralną — pairs trading na kointegrowanym spreadzie — tym samym pipeline'em, żeby sprawdzić, czy względna wycena BTC i ETH daje przewagę, której nie dały strategie kierunkowe, i żeby platforma obsługiwała strategie z wagami innymi niż równe.

## Acceptance criteria

- AC-1 (kointegracja): Given dwa szeregi cen, when liczę test Engle'a-Grangera, then dostaję współczynnik zabezpieczenia, statystykę testu, p-value (MacKinnon) i okres półtrwania spreadu — na parze syntetycznej kointegrowanej ze znanym β i znanym półtrwaniem wyniki zgadzają się z nimi, a dla dwóch niezależnych błądzeń losowych test zwykle nie odrzuca braku kointegracji.
- AC-2 (kontrakt wag): Given strategia z własnymi wagami, when uruchamiam dowolny silnik, then pozycje mają wagi z sygnałów strategii; dla strategii istniejących (równe wagi po znaku) oba silniki dają wynik identyczny jak przed zmianą, a parytet silników (q2) trwa.
- AC-3 (sygnał pary): Given historia obu nóg, when strategia liczy pozycję na dzień t, then używa tylko danych z datą ≤ t: β i z-score spreadu z ostatnich N dni, wejście przy |z| ≥ progu wejścia, wyjście przy przekroczeniu progu wyjścia; obie nogi naraz albo żadna.
- AC-4 (diagnostyka): Given przebieg treningowy hipotezy par, when uruchamiam `quantlab run`, then raport pokazuje test Engle'a-Grangera i półtrwanie spreadu na okresie treningowym — opisowo, poza regułami statusu.
- AC-5 (pre-rejestracja): Given odpowiedzi na pytania z tego dokumentu, when zamrażam `config/holdout/pairs_v1.yaml`, then commit powstaje przed pierwszym przebiegiem tej hipotezy na danych rynkowych, a rejestr prób (`q6`) liczy ją jako trzecią na tych danych.
- AC-6 (wynik): Given przebieg treningowy i jednorazowo otwarty holdout, when zapisuję wpis w dzienniku, then zawiera status końcowy, test kointegracji, PSR, DSR z N = 3, PBO trzech prób i korelację z obiema wcześniejszymi hipotezami.

## Out of scope

- **Wybór par z szerszego koszyka.** Przeszukiwanie wielu par to ukryte próby i survivorship bias; wymaga point-in-time uniwersum (`q5`). Tu jedna para, ustalona z góry.
- **Test Johansena i koszyki więcej niż dwóch instrumentów.** Przy jednej parze Engle-Granger wystarcza; Johansen wraca z koszykiem.
- **CPCV / purged k-fold.** Współczynnik zabezpieczenia jest estymowany kroczącym oknem z przeszłości, więc strategia jest walk-forward z konstrukcji i nie ma parametru optymalizowanego na danych treningowych, który CPCV miałby ocenić. Wraca, jeśli kiedyś pojawi się hipoteza z parametrami dobieranymi optymalizacją.
- Stop-loss, limity czasu trwania pozycji i inne dodatkowe pokrętła — więcej swobody doboru to więcej ukrytych prób.
- Koszt pożyczki przy krótkiej sprzedaży (short na spocie) — opisany jako ograniczenie, jak w `q1`.

## Priority

Should have — jedyny epik z niezablokowaną pracą: `q2`, `q3` i `q6` czekają na lokalne przebiegi (Binance), `q5` na decyzję o źródle danych akcji, a `q7` wymaga .NET SDK, którego nie da się pobrać w środowisku chmurowym.

## Dependencies and risks

- Zależy od `q1` (pipeline), `q3`-M1 (definicja hipotezy jako zamrożony plik), `q2`-E1 (wspólna reguła wag w obu silnikach) i `q6` (rejestr prób, DSR, PBO).
- **Nowa zależność natywna: statsmodels (i scipy).** Test Engle'a-Grangera z p-value MacKinnona jest w statsmodels; własna implementacja tablic MacKinnona byłaby miejscem na błąd. Maszyna deweloperska nie ma AVX2 — test importu w `tests/test_environment.py` musi przejść lokalnie (CLAUDE.md).
- **Ryzyko: holdout skażony wiedzą.** Lata 2024–2025 były oglądane w `q1` (wiadomo np., że ETH słabło wobec BTC) — nie mogą być holdoutem pary. Holdout z 2026 roku jest czysty tylko wtedy, gdy `pairs_v1` zostanie zamrożona, zanim otwarty zostanie holdout `mean_reversion_v1` (ten sam zakres dat).
- **Ryzyko: BTC i ETH nie są stale kointegrowane.** Filtr kointegracji może zostawić strategię bez pozycji przez większość okresu, a test będzie miał małą moc. Wynik `inconclusive` z tego powodu to pełnoprawny wynik, przyjęty z góry.
- **Ryzyko: wielokrotne testowanie.** Trzecia próba na tych samych danych; DSR i PBO z `q6` liczą ją automatycznie.

## Open questions

Blokują zamrożenie (slice P5); do tego czasu kod powstaje na danych syntetycznych.

| # | Question | Owner | Due |
|---|---|---|---|
| 1 | Para i parametry sygnału. Propozycja: y = ETH-USDT, x = BTC-USDT (BTC jako czynnik rynkowy), okno formacji 365 dni, wejście przy \|z\| ≥ 2, wyjście przy przekroczeniu z = 0 — wszystko z Gatev, Goetzmann, Rouwenhorst (2006) | Tomasz | przed slice P5 |
| 2 | Filtr kointegracji. Propozycja: pozycja tylko wtedy, gdy test Engle'a-Grangera na oknie formacji daje p < 0.05 (podejście kointegracyjne, Vidyamurthy 2004). Alternatywa: bez filtra (więcej transakcji, ale bez warunku, który definiuje stat arb) | Tomasz | przed slice P5 |
| 3 | Zakres holdoutu. Propozycja: 2026-01-01 → 2026-08-31 (te same, jeszcze nieoglądane dane co `mean_reversion_v1`; zamrożenie przed otwarciem jej holdoutu). Alternatywa: przyszłe dane, np. 2026-10-01 → 2027-03-31 (czyste bez warunku, ale trzeba czekać) | Tomasz | przed slice P5 |
| 4 | Kryterium sukcesu. Propozycja: to samo co `momentum_v1` i `mean_reversion_v1` (Sharpe netto > 0 i p < 0.1) | Tomasz | przed slice P5 |

**Rozstrzygnięte 2026-09-24 (Tomasz), zamrożone w [config/holdout/pairs_v1.yaml](../../../config/holdout/pairs_v1.yaml):** wszystkie cztery propozycje przyjęte — y = ETH-USDT, x = BTC-USDT, okno formacji 365 dni, wejście przy |z| ≥ 2, wyjście przy przekroczeniu z = 0; filtr Engle'a-Grangera p < 0.05 (tylko dla wejść); holdout 2026-01-01 → 2026-08-31, zamrożony przed otwarciem holdoutu `mean_reversion_v1`; kryterium jak w `momentum_v1` i `mean_reversion_v1`, z jawnym przypadkiem „brak pozycji → inconclusive". Okres treningowy 2018-01-01 → 2023-12-31, jak dwóch pozostałych hipotez.
