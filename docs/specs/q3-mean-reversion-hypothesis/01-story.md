# q3-mean-reversion-hypothesis - Druga rodzina hipotez: krótkoterminowe odwrócenie (mean reversion)

Status: Draft
Owner role: PO
Upstream: docs/specs/q1-momentum-research-mvp/
Links: docs/ROADMAP.md, docs/RESEARCH_LOG.md

## Problem

MVP (`q1`) przeprowadziło jedną hipotezę przez pełny pipeline i zakończyło się wynikiem `inconclusive`: momentum 12-miesięczne na BTC-USDT i ETH-USDT nie ma przewagi timingu odróżnialnej od przypadku (p = 0.14 na treningu, 0.61 na holdoucie). Dwie rzeczy pozostają niesprawdzone:

1. **Czy platforma jest ogólna, a nie „skryptem do jednej hipotezy".** `quantlab run` i `quantlab open-holdout` mają dziś parametry momentum wpisane w stałe CLI. Druga hipoteza pokaże, czy `Strategy`, `CostModel` i `Validator` są naprawdę podstawialne (CLAUDE.md, zasada 9).
2. **Czy na tym rynku istnieje efekt przeciwny.** Krótkoterminowe odwrócenie (Jegadeesh 1990, Lehmann 1990) to naturalny kontrast dla momentum: zakłada, że ostatnie krótkie ruchy częściowo się cofają. ROADMAP przewiduje ten kontrast wprost na wypadek, gdy momentum nie przejdzie walidacji.

To także druga hipoteza testowana na tych samych danych, więc od tego epiku liczba prób ma znaczenie dla interpretacji wyników (korekta na wielokrotne testowanie: `q6`).

## Outcome

Primary metric: hipoteza `mean_reversion_v1` ma jednoznaczny status (`confirmed` / `rejected` / `inconclusive`) w `docs/RESEARCH_LOG.md`, poparty walk-forward i zamrożonym holdoutem, z jawnym porównaniem do `momentum_v1`.
Guardrail metric: parametry, reguła walk-forward, kryterium sukcesu i zakres holdoutu `mean_reversion_v1` są zacommitowane, zanim jakikolwiek przebieg tej hipotezy przeczyta dane rynkowe; wyniki `momentum_v1` po uogólnieniu runnera są identyczne co do liczby.

## User story

Jako budujący platformę chcę przetestować drugą, przeciwstawną rodzinę hipotez (krótkoterminowe odwrócenie) tym samym pipeline'em, bez kopiowania kodu pod nową hipotezę, żeby pokazać, że proces badawczy jest ogólny, i żeby sprawdzić, czy na koszyku, na którym momentum nie dało przewagi, działa efekt przeciwny.

## Acceptance criteria

- AC-1: Given uogólniony runner, when uruchamiam `momentum_v1`, then każdy snapshot i każda metryka są identyczne jak przed zmianą, a zamrożony plik `config/holdout/momentum_v1.yaml` pozostaje niezmieniony bajt w bajt.
- AC-2: Given historia cen, when `ShortTermReversal.generate_signals` liczy sygnał na dzień t, then używa tylko danych z datą ≤ t, a kierunek jest przeciwny do znaku zwrotu z okresu formacji (zwrot zerowy → brak pozycji, za krótka historia → brak sygnału).
- AC-3: Given nowa hipoteza, when zapisuję jej definicję, then jeden plik zawiera strategię z parametrami, uniwersum, model kosztów, okres treningowy, zakres holdoutu i kryterium sukcesu — i `quantlab run` odmawia przebiegu hipotezy, której plik nie jest zacommitowany.
- AC-4: Given przebieg treningowy, when porównuję modele kosztów, then raport pokazuje także roczny obrót (turnover), bo przy krótkim horyzoncie to on decyduje o koszcie.
- AC-5: Given przebieg treningowy `mean_reversion_v1`, when generuję raport, then zawiera te same elementy co dla `momentum_v1`: walk-forward, test permutacyjny, reżimy, stress test, rejestr transakcji i tear-sheet — bez kodu specyficznego dla tej hipotezy poza strategią.
- AC-6: Given przebiegi treningowe obu hipotez na tym samym koszyku, when je porównuję, then raport pokazuje korelację ich dziennych zwrotów netto.
- AC-7: Given zamrożony holdout, when otwieram go dokładnie raz, then zapis otwarcia jest commitowany, a wpis w dzienniku zawiera status końcowy, porównanie z `momentum_v1` i liczbę hipotez przetestowanych dotąd na tym koszyku.

## Out of scope

- Strategie z pasmami z-score, progami wejścia/wyjścia i innymi dodatkowymi parametrami — więcej swobody doboru to więcej ukrytych prób.
- Cross-sectional reversal (ranking instrumentów względem siebie) — wymaga szerszego koszyka i point-in-time uniwersum (`q5`).
- Dane śróddzienne i egzekucja poza ceną zamknięcia — silnik event-driven (`q2`).
- Deflated Sharpe i PBO — `q6`; tu tylko jawne zliczenie prób.

## Priority

Should have — pierwsze rozszerzenie po MVP, wybrane regułą z ROADMAP (momentum nie przeszło walidacji → kontrast).

## Dependencies and risks

- Zależy od `q1` (cały pipeline) i `lab-foundation` (dane, uniwersum).
- **Ryzyko: holdout skażony wiedzą.** Wszystkie dane BTC-USDT i ETH-USDT do 2025-12-31 były już oglądane w `q1` (trening i holdout momentum). Wiadomo np., że 2024–2025 to lata wzrostów. Mitygacja: holdout `q3` z danych, których żaden przebieg dotąd nie wczytał (po 2025-12-31) — kosztem krótszego okresu i mniejszej mocy testu, przyjętej z góry.
- **Ryzyko: koszty zjedzą wynik.** Horyzont tygodniowy oznacza wielokrotnie większy obrót niż 12-miesięczne momentum. Wynik `rejected` z powodu kosztów to pełnoprawny wynik, nie powód do zmiany modelu kosztów po fakcie.
- **Ryzyko: wielokrotne testowanie.** Druga hipoteza na tych samych danych zwiększa szansę fałszywie pozytywnego wyniku. Mitygacja: jawna liczba prób w dzienniku; pełna korekta w `q6`.
- **Ryzyko: pokusa „odwrócenia" wyniku momentum.** Reversal nie może być dobrany tak, żeby grał przeciw znanym stratom momentum; parametr formacji pochodzi z literatury, nie z danych.

## Open questions

| # | Question | Owner | Due |
|---|---|---|---|
| 1 | Okres formacji sygnału. Propozycja: 7 dni (odwrócenie tygodniowe, Lehmann 1990; krypto handluje 7 dni w tygodniu), z literatury, bez dopasowania do danych | Tomasz | przed slice M4 (zamrożenie) |
| 2 | Koszyk. Propozycja: ten sam `mvp-crypto` (BTC-USDT + ETH-USDT) — czysty kontrast z `momentum_v1` na identycznych danych; szerszy koszyk jako osobna hipoteza po point-in-time uniwersum (`q5`), żeby nie wprowadzić survivorship bias | Tomasz | przed slice M4 |
| 3 | Zakres holdoutu. Propozycja: 2026-01-01 → 2026-08-31 (dane, których żaden przebieg nie wczytał; ok. 8 miesięcy, mała moc przyjęta z góry). Alternatywa: 2024–2025 (dłuższy, ale już oglądany) | Tomasz | przed slice M4 |
| 4 | Kryterium sukcesu holdoutu. Propozycja: to samo co `momentum_v1` (Sharpe netto > 0 i p < 0.1), dla porównywalności obu hipotez | Tomasz | przed slice M4 |
