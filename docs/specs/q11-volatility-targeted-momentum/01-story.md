# q11-volatility-targeted-momentum - Momentum ze skalowaniem pozycji do docelowej zmienności

Status: Ready for dev
Owner role: PO
Upstream: docs/specs/q1-momentum-research-mvp/, docs/specs/q2-event-driven-engine/, docs/specs/q6-advanced-validation-cpcv/
Links: docs/ROADMAP.md, docs/RESEARCH_LOG.md

## Problem

`momentum_v1` (time-series momentum 12 miesięcy na BTC i ETH, równe wagi po znaku sygnału) zakończyła się wynikiem `inconclusive`, a jej wpis w dzienniku wskazuje trzy słabości:

1. **Ryzyko jest skrajne i nierówne w czasie.** Max drawdown −88.7% w treningu. Cały dodatni wynik pochodzi z dni o średniej zmienności; w reżimie wysokiej zmienności strategia traciła. Pozycja ma tę samą wielkość niezależnie od tego, czy dzienna zmienność BTC wynosi 2%, czy 8%.
2. **Literatura skaluje pozycje ryzykiem, laboratorium nie umie.**
   - Moskowitz, Ooi i Pedersen (2012), źródło hipotezy `momentum_v1`, skalują każdą pozycję do docelowej zmienności ex-ante, 40% rocznie, z wykładniczo ważonej wariancji.
   - Barroso i Santa-Clara (2015) oraz Daniel i Moskowitz (2016) pokazują, że krachy momentum przypadają na okresy wysokiej zmienności, a skalowanie zmiennością je łagodzi.
   - Moreira i Muir (2017) opisują wyższy Sharpe portfeli zarządzanych zmiennością.
   - Kim, Tse i Wald (2016) twierdzą przeciwnie: że większość przewagi TSMOM pochodzi właśnie ze skalowania, nie ze znaku sygnału.

   Sizery laboratorium dają dziś równe wagi po znaku albo wagi zadane przez strategię (pary, portfel). Żaden nie zależy od ryzyka instrumentu.
3. **Wariant powstaje po obejrzeniu wyniku.** Pomysł skalowania pojawia się po lekturze wyników `momentum_v1`, więc to nowa hipoteza:
   - kolejna próba na `mvp-crypto` 2018–2023, która obniża próg deflated Sharpe wszystkich prób na tych danych;
   - holdout na danych, których żadna hipoteza na tym uniwersum jeszcze nie oglądała; 2024–2025 jest zużyty przez `momentum_v1`.
4. **Skalowanie w górę wymaga pożyczania.** W spokojnych okresach docelowa zmienność może wymagać pozycji większej niż kapitał. Silniki nie modelują kosztu finansowania, więc dźwignia zawyżyłaby wynik.

## Outcome

Primary metric: hipoteza `momentum_voltarget_v1` ma jednoznaczny status w `docs/RESEARCH_LOG.md`. Wynik zawiera opisowe porównanie z tym samym momentum bez skalowania (Sharpe netto, zmienność, max drawdown, reżimy) i DSR przy wszystkich próbach na tych samych danych.
Guardrail metric: wyniki wszystkich zamrożonych hipotez identyczne co do bitu (zrzut regresji); ich werdykty bez zmian.

## User story

Jako badacz chcę zamrozić momentum, którego pozycje są skalowane do docelowej zmienności ex-ante bez dźwigni, i ocenić je tym samym pipeline'em co `momentum_v1`, żeby wiedzieć, czy zarządzanie ryzykiem pozycji — jedyna różnica między hipotezami — zmienia wynik po kosztach, a nie tylko kształt krzywej kapitału.

## Acceptance criteria

- AC-1 (estymator zmienności): Given dzienne zwroty z okna estymacji, when liczę zmienność instrumentu, then estymator kroczący i wykładniczo ważony dają wartości policzalne z góry na danych syntetycznych, np. zwroty na przemian +x i −x dają odchylenie x z dokładnością do poprawki na liczbę obserwacji.
- AC-2 (bez zaglądania w przyszłość): Given dzień decyzji t, when liczę zmienność i skalę, then używam wyłącznie barów z dni ≤ t. Zmiana baru z dnia późniejszego nie zmienia ani estymaty, ani wagi.
- AC-3 (skala i wagi): Given sygnał i estymata zmienności, when liczę wagę, then:
  - skala to min(limit, docelowa zmienność / roczna zmienność ex-ante);
  - waga to skala podzielona przez liczbę aktywnych, handlowalnych instrumentów, ze znakiem sygnału;
  - suma wartości bezwzględnych wag nie przekracza limitu ≤ 1;
  - instrument bez estymaty nie ma pozycji.
- AC-4 (parytet silników): Given ta sama hipoteza, when uruchamiam silnik wektorowy i event-driven przy pełnym wypełnieniu, then krzywe kapitału są zgodne jak w `q2`.
- AC-5 (raport): Given przebieg treningowy, when uruchamiam `quantlab run`, then terminal, tear-sheet, magazyn wyników i aplikacja pokazują:
  - średnią, najniższą i najwyższą skalę każdego instrumentu oraz udział dni na limicie;
  - Sharpe netto, zmienność i max drawdown wersji skalowanej oraz tego samego momentum z równymi wagami po znaku, na tym samym oknie i przy tym samym modelu kosztów.
- AC-6 (wynik): Given zamrożona definicja i jednorazowo otwarty holdout, when zapisuję wpis w dzienniku, then zawiera status, porównanie z `momentum_v1` i DSR przy próbach na tych samych danych.

## Out of scope

- Dźwignia ponad kapitał i koszt finansowania: limit skali ≤ 1.
- Celowanie w zmienność całego portfela z kowariancją instrumentów: skalowanie jest per instrument, jak u Moskowitza, Ooi i Pedersena.
- Dobór docelowej zmienności albo okna na danych (siatka, CPCV). Parametry są zamrożone, jak w każdej hipotezie z pojedynczą konfiguracją.
- Skalowanie innych zamrożonych hipotez. Opakowanie działa z każdą strategią, ale nowa hipoteza to osobna decyzja.
- Zmiana definicji, wyników i werdyktów zamrożonych hipotez, w tym `momentum_v1`.

## Priority

Should have — następny epik po `q1`–`q10`, rozpoczęty 2026-09-26. Kod (estymatory, opakowanie strategii, sizer, definicja, raport) powstaje na danych syntetycznych. Definicja zamrożona po decyzjach 1–6 poniżej (V4, 2026-09-26); przebiegi czekają na lokalny dostęp do Binance.

## Dependencies and risks

- Zależy od `q1` (sygnał momentum, pipeline), `q2` (parytet silników, sizer), `q6` (rejestr prób, DSR), `q7` (magazyn wyników i aplikacja, diagnostyka treningu), `q10` (plan przebiegów).
- **Ryzyko: estymata zależy od okna pobierania.** Holdout pobiera dane od początku holdoutu minus rozgrzewka. Estymator czytający całą dostępną historię dałby inną wartość w treningu i w holdoucie. Mitygacja: estymator czyta dokładnie `window_days` ostatnich zwrotów, a rozgrzewka definicji to co najmniej to okno.
- **Ryzyko: codzienna zmiana skali to obrót.** Każdy dzień zmienia estymatę, więc i wagę. Mitygacja: koszt drobnych zmian nalicza model realistyczny (opłata i poślizg od przehandlowanej wagi). Raport pokazuje wynik obok wersji bez skalowania przy tym samym modelu kosztów.
- **Ryzyko: wielokrotne testowanie.** Kolejna próba na `mvp-crypto` 2018–2023 (razem 6 prób, 11 konfiguracji) obniża opisowy DSR pozostałych hipotez przy ich następnym przebiegu, zgodnie z prawdą. `quantlab plan` pokaże je jako nieaktualne.
- **Ryzyko: skalowanie tylko w dół.** Przy limicie 1 i zmienności kryptowalut zwykle powyżej 40% rocznie wersja skalowana najczęściej zmniejsza ekspozycję względem `momentum_v1`. Pytanie badawcze to więc „czy zmniejszanie pozycji w okresach wysokiej zmienności pomaga", a nie pełne celowanie w zmienność z dźwignią. Opisane w dzienniku.

## Decisions

Odpowiedzi na pytania 1–6, przyjęte przez Tomasza 2026-09-26 (wszystkie propozycje); zamrożone w `config/holdout/momentum_voltarget_v1.yaml` (V4):

| # | Question | Decision |
|---|---|---|
| 1 | Docelowa zmienność roczna na instrument | 40% (Moskowitz, Ooi, Pedersen 2012) |
| 2 | Estymator zmienności ex-ante | EWMA, środek masy 60 dni, okno 365 zwrotów do dnia decyzji włącznie |
| 3 | Limit skali na instrument | 1.0 — bez dźwigni |
| 4 | Sygnał | znak zwrotu 365-dniowego, rebalans dzienny, jak w `momentum_v1` |
| 5 | Okresy | trening 2018-01-01 → 2023-12-31; holdout 2026-01-01 → 2026-08-31 |
| 6 | Kryterium sukcesu | bramka walk-forward; holdout: Sharpe netto (model realistyczny) > 0 i p < 0.1 z testu permutacyjnego |

## Open questions

Brak — pytania pre-rejestracji rozstrzygnięte (tabela powyżej).
