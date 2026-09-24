# Roadmap

Platforma badawcza budowana epikami. Epik `lab-foundation` jest fundamentem; `q1-momentum-research-mvp` domyka pełny pipeline na jednej hipotezie (granica MVP); `q2`–`q7` to rozszerzenia, kolejność wśród nich może się zmienić w zależności od wniosków z MVP.

## Kolejność i zależności

```
lab-foundation
  -> q1-momentum-research-mvp   (MVP: koniec tu)
       -> q2-event-driven-engine
       -> q3-mean-reversion-hypothesis
       -> q4-pairs-trading-stat-arb
       -> q5-equities-cross-section
       -> q6-advanced-validation-cpcv
       -> q7-dotnet-react-presentation
```

q2–q7 nie mają ustalonej kolejności między sobą — priorytet ustala się po zamknięciu q1, na podstawie tego, co wymaga pogłębienia. Przykład: jeśli momentum nie przejdzie walidacji, `q3` (mean-reversion) zyskuje priorytet jako kontrast; jeśli silnik wektorowy okaże się za wolny do walidacji wymagającej wielu powtórzeń, `q6` (CPCV) wyprzedza `q2`.

**Po zamknięciu q1 (2026-09-24):** hipoteza `momentum_v1` zakończyła się wynikiem `inconclusive` — walk-forward zaliczony, holdout bez istotnego efektu timingu (p = 0.61), patrz [RESEARCH_LOG.md](RESEARCH_LOG.md). Momentum nie przeszło walidacji, więc zgodnie z regułą powyżej następny jest `q3-mean-reversion-hypothesis`. Silnik wektorowy nie okazał się wąskim gardłem (pełny przebieg z 10 000 permutacji ok. 11 s), więc nie ma powodu, by `q6` wyprzedzał kolejkę.

**Po `q3`-M4 (2026-09-24):** `q3` czeka na lokalny przebieg treningowy (M5 — Binance jest zablokowany w środowisku chmurowym), więc równolegle rusza następny w kolejności `q2-event-driven-engine`. Nie zależy od wyników `q3` i nie zmienia parametrów ani werdyktów żadnej hipotezy.

**Po `q2`-E5 (2026-09-24):** `q2` i `q3` czekają na lokalne przebiegi (E6, M5), więc rusza `q6-advanced-validation-cpcv` w zakresie, który nie wymaga danych: PSR, deflated Sharpe z liczbą prób liczoną z historii gita i PBO. CPCV/purged k-fold odłożone do pierwszej hipotezy z parametrami dopasowywanymi na danych (`q4`).

**Po `q6`-V5 (2026-09-24):** jedyny epik z niezablokowaną pracą to `q4-pairs-trading-stat-arb` (`q5` czeka na decyzję o źródle danych akcji, `q7` na .NET SDK, którego środowisko chmurowe nie pobiera). Kod (kointegracja, kontrakt wag, strategia par) powstaje na danych syntetycznych; zamrożenie `pairs_v1` wymaga odpowiedzi na pytania pre-rejestracji. Współczynnik zabezpieczenia jest estymowany kroczącym oknem z przeszłości, więc CPCV nadal nie ma czego oceniać — zostaje odłożone bez epiku docelowego.

## Epiki

### lab-foundation

Szkielet repo, dostęp do danych, testy środowiska. Bez tego nic innego się nie zaczyna. Pełna specyfikacja: [specs/lab-foundation/](specs/lab-foundation/).

Slice'y: F-1 szkielet (uv, ruff, pytest, CLI, test środowiska) · F-2 `core.data` z jednym adapterem (Binance, patrz [ADR-0007](adr/0007-binance-not-stooq-for-first-adapter.md)) i cache · F-3 `core.universe` statyczne · F-4 `core.storage` (DuckDB/Parquet I/O).

### q1-momentum-research-mvp

Pełny pipeline na jednej hipotezie (time-series momentum, Moskowitz/Ooi/Pedersen 2012): sygnał, silnik wektorowy, koszty, walidacja out-of-sample, ryzyko/reżimy, atrybucja transakcji, tear-sheet, wpis w dzienniku badawczym. **Granica MVP.** Pełna specyfikacja: [specs/q1-momentum-research-mvp/](specs/q1-momentum-research-mvp/).

Slice'y: S1 rejestr `Hypothesis` · S2 sygnał momentum · S3 `Strategy` implementacja · S4 silnik wektorowy + `BacktestRun` · S5 metryki własnym kodem + testy golden-master · S6 pierwszy pełny przebieg end-to-end · S7 `NaiveCostModel` · S8 `RealisticCostModel` + porównanie wrażliwości · S9 `WalkForwardValidator` · S10 zamrożony holdout · S11 `PermutationTestValidator` · S12 `RegimeClassifier` + metryki warunkowe · S13 stress test scenariuszowy · S14 `TradeLedger` + cięcia P&L · S15 tear-sheet · S16 wpis w `docs/RESEARCH_LOG.md`.

### q2-event-driven-engine (rozszerzenie, w toku)

Realistyczna egzekucja: symulacja zleceń i częściowych wypełnień, brak look-ahead bias z konstrukcji. Porównanie wyniku z silnikiem wektorowym na tej samej hipotezie; walidacja i werdykty zostają na silniku wektorowym. Pełna specyfikacja: [specs/q2-event-driven-engine/](specs/q2-event-driven-engine/).

Slice'y: E1 wspólny kontrakt `BacktestRun` i reguła wag · E2 rdzeń event-driven + parytet z silnikiem wektorowym · E3 egzekucja na następnym barze · E4 limit udziału w wolumenie i kapitał graniczny · E5 `quantlab compare-engines` · E6 przebieg lokalny i uzupełnienie dziennika.

### q3-mean-reversion-hypothesis (rozszerzenie, następne po MVP)

Druga rodzina hipotez — short-term mean reversion — jako kontrast do momentum na tym samym pipeline'ie. Pełna specyfikacja: [specs/q3-mean-reversion-hypothesis/](specs/q3-mean-reversion-hypothesis/).

Slice'y: M1 uogólniony runner (definicja hipotezy = zamrożony plik) · M2 `ShortTermReversal` · M3 obrót i korelacja z `momentum_v1` · M4 zamrożenie `mean_reversion_v1` · M5 przebieg treningowy · M6 otwarcie holdoutu · M7 wpis w dzienniku.

### q4-pairs-trading-stat-arb (rozszerzenie, w toku)

Kointegracja (Engle-Granger), spread trading na parze ETH-USDT / BTC-USDT, wagi z współczynnika zabezpieczenia w obu silnikach. Johansen i wybór par z szerszego koszyka wracają po `q5`. Pełna specyfikacja: [specs/q4-pairs-trading-stat-arb/](specs/q4-pairs-trading-stat-arb/).

Slice'y: P1 narzędzia kointegracji · P2 kontrakt wag (`Sizer`) · P3 strategia par · P4 diagnostyka kointegracji w raporcie · P5 zamrożenie `pairs_v1` · P6 przebieg treningowy · P7 otwarcie holdoutu · P8 wpis w dzienniku.

### q5-equities-cross-section (rozszerzenie, nierozpisane)

Point-in-time uniwersum, `CorporateAction` i korekta cen, obsługa survivorship bias.

### q6-advanced-validation-cpcv (rozszerzenie, w toku)

Probabilistic i deflated Sharpe ratio, Probability of Backtest Overfitting (CSCV) i rejestr prób liczony z historii definicji hipotez — opisowo, bez zmiany zamrożonych kryteriów. Purged k-fold / CPCV wraca z pierwszą hipotezą z parametrami dopasowywanymi na danych (`q4`). Pełna specyfikacja: [specs/q6-advanced-validation-cpcv/](specs/q6-advanced-validation-cpcv/).

Slice'y: V1 PSR i DSR · V2 rejestr prób z historii gita · V3 PBO (CSCV) · V4 PSR/DSR w `quantlab run` i tear-sheecie · V5 `quantlab trials` · V6 przebiegi lokalne i dziennik.

### q7-dotnet-react-presentation (rozszerzenie, nierozpisane)

ASP.NET Core Web API nad wynikami w DuckDB/Parquet, React: eksplorator strategii i blotter transakcji.

## Zakres MVP

Kończy się na `q1-momentum-research-mvp`. Kryteria ukończenia:

- Jedna hipoteza (momentum) przetestowana pełnym pipeline'em, z wynikiem zapisanym w dzienniku badawczym niezależnie od tego, czy się potwierdziła.
- Silnik backtestu z testami golden-master na syntetycznych danych.
- Co najmniej dwa modele kosztów z jawnym porównaniem wpływu na wynik.
- Walk-forward + zamrożony holdout + test permutacyjny.
- Metryki warunkowe na co najmniej dwóch reżimach zmienności.
- Rejestr transakcji z cięciami P&L.
- Jeden pełny tear-sheet z realnego przebiegu.

Orientacyjny czas, solo po godzinach: `lab-foundation` 1–2 tygodnie, `q1-momentum-research-mvp` 5–8 tygodni. Rozszerzenia q2–q7: 2–4 miesiące przyrostowo, po ustaleniu priorytetu.

## Stan ticketów

| Epik | 01-story | 02-spec | 03-design | Kod |
|---|---|---|---|---|
| lab-foundation | Ready for dev | Ready for dev | Ready for dev | gotowe (F-1..F-4) |
| q1-momentum-research-mvp | Ready for architect | Ready for architect | Ready for dev | gotowe (S1..S16), MVP zamknięte: `momentum_v1` inconclusive |
| q2-event-driven-engine | Ready for dev | Ready for dev | Ready for dev | E1–E5 gotowe; E6 wymaga lokalnego przebiegu (Binance) |
| q3-mean-reversion-hypothesis | Ready for dev | Ready for dev | Ready for dev | M1–M4 gotowe; M5 wymaga lokalnego przebiegu (Binance) |
| q4-pairs-trading-stat-arb | Ready for dev | Ready for dev | Ready for dev | P1 gotowe (kointegracja) |
| q5-equities-cross-section | nie napisany | nie napisany | nie napisany | — |
| q6-advanced-validation-cpcv | Ready for dev | Ready for dev | Ready for dev | V1–V5 gotowe; V6 wymaga lokalnych przebiegów (Binance) |
| q7-dotnet-react-presentation | nie napisany | nie napisany | nie napisany | — |
