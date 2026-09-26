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
       -> q8-parameter-selection-cpcv   (po q1–q7; korzysta z q2, q6, q7)
       -> q9-strategy-portfolio         (po q8; korzysta z q2, q4, q6, q7, q8)
       -> q10-local-runbook             (po q9; plan przebiegów lokalnych)
       -> q11-volatility-targeted-momentum (po q10; skalowanie pozycji zmiennością)
```

q2–q7 nie mają ustalonej kolejności między sobą — priorytet ustala się po zamknięciu q1, na podstawie tego, co wymaga pogłębienia. Przykład: jeśli momentum nie przejdzie walidacji, `q3` (mean-reversion) zyskuje priorytet jako kontrast; jeśli silnik wektorowy okaże się za wolny do walidacji wymagającej wielu powtórzeń, `q6` (CPCV) wyprzedza `q2`.

**Po zamknięciu q1 (2026-09-24):** hipoteza `momentum_v1` zakończyła się wynikiem `inconclusive` — walk-forward zaliczony, holdout bez istotnego efektu timingu (p = 0.61), patrz [RESEARCH_LOG.md](RESEARCH_LOG.md). Momentum nie przeszło walidacji, więc zgodnie z regułą powyżej następny jest `q3-mean-reversion-hypothesis`. Silnik wektorowy nie okazał się wąskim gardłem (pełny przebieg z 10 000 permutacji ok. 11 s), więc nie ma powodu, by `q6` wyprzedzał kolejkę.

**Po `q3`-M4 (2026-09-24):** `q3` czeka na lokalny przebieg treningowy (M5 — Binance jest zablokowany w środowisku chmurowym), więc równolegle rusza następny w kolejności `q2-event-driven-engine`. Nie zależy od wyników `q3` i nie zmienia parametrów ani werdyktów żadnej hipotezy.

**Po `q2`-E5 (2026-09-24):** `q2` i `q3` czekają na lokalne przebiegi (E6, M5), więc rusza `q6-advanced-validation-cpcv` w zakresie, który nie wymaga danych: PSR, deflated Sharpe z liczbą prób liczoną z historii gita i PBO. CPCV/purged k-fold odłożone do pierwszej hipotezy z parametrami dopasowywanymi na danych (`q4`).

**Po `q6`-V5 (2026-09-24):** jedyny epik z niezablokowaną pracą to `q4-pairs-trading-stat-arb` (`q5` czeka na decyzję o źródle danych akcji, `q7` na .NET SDK, którego środowisko chmurowe nie pobiera). Kod (kointegracja, kontrakt wag, strategia par) powstaje na danych syntetycznych; zamrożenie `pairs_v1` wymaga odpowiedzi na pytania pre-rejestracji. Współczynnik zabezpieczenia jest estymowany kroczącym oknem z przeszłości, więc CPCV nadal nie ma czego oceniać — zostaje odłożone bez epiku docelowego.

**Po `q4`-P5 (2026-09-24):** `q2`, `q3`, `q4` i `q6` czekają na lokalne przebiegi (Binance), `q5` na decyzję o źródle danych akcji. Odblokował się `q7-dotnet-react-presentation`: .NET 10 SDK jest w archiwum Ubuntu, dostępnym w środowisku chmurowym. Epik nie zależy od danych rynkowych — API i UI testowane są na syntetycznym magazynie wyników wygenerowanym pełnym pipeline'em.

**Po `q7`-W5 (2026-09-24):** jedyny nierozpoczęty epik to `q5-equities-cross-section`. Kod niezależny od źródła danych (point-in-time uniwersum, corporate actions, delisting, polityka rebalansu, momentum przekrojowe) powstaje na danych syntetycznych; adapter i zamrożenie hipotezy czekają na decyzje o źródle danych, uniwersum i parametrach (pytania w [01-story](specs/q5-equities-cross-section/01-story.md)).

**Po decyzjach `q5` 1–5 (2026-09-24):** adapter X7 dzieli się na cztery części na danych syntetycznych i nagranych odpowiedziach (kalendarz i źródło w pliku uniwersum, test losowych portfeli, Tiingo, budowa składu S&P 500). Zamrożenie `xsmom_v1` czeka na dwa pytania, które wynikły z wyboru źródła: zwrot z delistingu (Tiingo go nie podaje, a w S&P 500 delisting członka to prawie zawsze przejęcie) i model kosztów dla akcji. Budowa pliku uniwersum, pobranie cen i przebiegi — lokalnie.

**Po `q5`-X8 (2026-09-24):** `xsmom_v1` zamrożona po decyzjach 1–7: momentum 12-1 na S&P 500 point-in-time (Tiingo, Wikipedia), trening 2005–2019, holdout 2020–2025, kryterium z testem losowych portfeli. Cały kod epiku gotowy; reszta wymaga sieci i dzieje się lokalnie, w tej kolejności: `uv run quantlab build-universe` (poprawki tickerów tylko z raportu budowy, potem commit `sp500.yaml` i `sp500-renames.yaml`), `uv run quantlab run xsmom_v1` z kluczem `TIINGO_API_KEY` (pobieranie rozłożone w czasie, patrz DATA-SOURCES), `uv run quantlab open-holdout xsmom_v1`, wpis w dzienniku (REQ-562). Wszystkie epiki mają już kod; otwarte są tylko przebiegi lokalne (`q2`–`q6` na Binance, `q5` na Tiingo) i weryfikacja `q7` na Windows.

**Po CI (2026-09-24):** repozytorium ma CI na GitHub Actions (ruff, pytest, testy API .NET, testy i build aplikacji React — na Linuksie i Windowsie), co pokrywa część weryfikacji `q7` na Windows. Wszystkie epiki `q1`–`q7` mają kod; Tomasz wybrał jako następny epik **`q8-parameter-selection-cpcv`**: hipoteza z parametrem dobieranym na danych (siatka, reguła wyboru zamrożona zamiast wartości), walk-forward z re-optymalizacją i CPCV z purgingiem i embargo — odłożone w `q6` do pierwszej takiej hipotezy. Kod na danych syntetycznych, zamrożenie po odpowiedziach na pytania z [01-story](specs/q8-parameter-selection-cpcv/01-story.md), przebiegi lokalnie (Binance).

**Po `q8`-P7 (2026-09-25):** `momentum_select_v1` zamrożona; wszystkie epiki `q1`–`q8` mają kod, otwarte są tylko przebiegi lokalne. Tomasz wybrał jako następny epik **`q9-strategy-portfolio`**: portfel zamrożonych hipotez krypto łączonych regułą alokacji ryzyka (odwrotność zmienności, risk parity, równe wagi) z wagami z historii sprzed rebalansu, handlujący pozycjami netto (kompensacja przeciwnych pozycji rękawów). Holdout portfela nachodzi na nieotwarte holdouty trzech składników, więc otwiera się dopiero po nich. Kod na danych syntetycznych, zamrożenie po odpowiedziach na pytania z [01-story](specs/q9-strategy-portfolio/01-story.md), przebiegi lokalnie (Binance).

**Po `q9`-P7 (2026-09-25):** `portfolio_v1` zamrożony; wszystkie epiki `q1`–`q9` mają kod, a otwarte są przebiegi lokalne: sześć hipotez bez treningu, holdouty w kolejności chroniącej `portfolio_v1`, budowa `sp500.yaml` i pobranie z Tiingo dla `xsmom_v1`, sprawdzenie DuckDB bez AVX2. Tomasz wybrał jako następny epik **`q10-local-runbook`**: `quantlab plan` — stan każdego pozostałego kroku z powodem i komendą — oraz `quantlab plan --run`, który wykonuje kroki automatyczne w poprawnej kolejności, a otwarcia holdoutów, commity i wpisy w dzienniku zostawia badaczowi.

**Po `q10` (2026-09-26):** wszystkie epiki `q1`–`q10` mają kod, a instrukcja obsługi ([INSTRUKCJA.md](INSTRUKCJA.md)) opisuje przebiegi lokalne. Następny z listy kandydatów jest **`q11-volatility-targeted-momentum`**: momentum z pozycjami skalowanymi do docelowej zmienności ex-ante (Moskowitz, Ooi, Pedersen 2012), bez dźwigni, jako nowa hipoteza i kontrast do `momentum_v1` — jedyną różnicą jest wielkość pozycji. Wariant powstaje po obejrzeniu wyniku `momentum_v1`, więc to kolejna próba na `mvp-crypto` 2018–2023 z holdoutem na danych jeszcze nieoglądanych. Kod na danych syntetycznych, zamrożenie po odpowiedziach na pytania z [01-story](specs/q11-volatility-targeted-momentum/01-story.md), przebiegi lokalnie (Binance).

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

### q5-equities-cross-section (rozszerzenie, w toku)

Point-in-time uniwersum, `CorporateAction` i korekta cen, delisting i pomiar survivorship bias, polityka rebalansu, momentum przekrojowe (Jegadeesh i Titman 1993). Pełna specyfikacja: [specs/q5-equities-cross-section/](specs/q5-equities-cross-section/).

Slice'y: X1 point-in-time uniwersum · X2 corporate actions · X3 delisting i survivorship bias · X4 polityka rebalansu · X5 momentum przekrojowe · X6 hipoteza demonstracyjna w magazynie wyników · X7 adapter źródła danych · X8 zamrożenie hipotezy · X9 przebieg treningowy · X10 otwarcie holdoutu · X11 wpis w dzienniku.

### q6-advanced-validation-cpcv (rozszerzenie, w toku)

Probabilistic i deflated Sharpe ratio, Probability of Backtest Overfitting (CSCV) i rejestr prób liczony z historii definicji hipotez — opisowo, bez zmiany zamrożonych kryteriów. Purged k-fold / CPCV wraca z pierwszą hipotezą z parametrami dopasowywanymi na danych — w `q8`. Pełna specyfikacja: [specs/q6-advanced-validation-cpcv/](specs/q6-advanced-validation-cpcv/).

Slice'y: V1 PSR i DSR · V2 rejestr prób z historii gita · V3 PBO (CSCV) · V4 PSR/DSR w `quantlab run` i tear-sheecie · V5 `quantlab trials` · V6 przebiegi lokalne i dziennik.

### q7-dotnet-react-presentation (rozszerzenie, w toku)

ASP.NET Core Web API nad wynikami w DuckDB/Parquet, React: rejestr hipotez, dowody hipotezy i rejestr transakcji, w design systemie QuantForge. Tylko odczyt — liczby wyłącznie z magazynu wyników zapisanego przez Pythona ([ADR-0008](adr/0008-results-store-parquet-duckdb.md)). Pełna specyfikacja: [specs/q7-dotnet-react-presentation/](specs/q7-dotnet-react-presentation/).

Slice'y: W1 magazyn wyników w Pythonie · W2 szkielet API .NET · W3 endpointy dowodów i transakcji · W4 aplikacja React z rejestrem hipotez · W5 ekran hipotezy i rejestr transakcji · W6 weryfikacja lokalna.

### q8-parameter-selection-cpcv (rozszerzenie, w toku)

Hipoteza z parametrem dobieranym na danych: zamrożona procedura doboru (siatka, miara, harmonogram) zamiast wartości, wybór wyłącznie z danych sprzed dnia wyboru (walk-forward z re-optymalizacją) jako strategia dla obu silników, CPCV z purgingiem i embargo (López de Prado 2018) na macierzy zwrotów siatki, PBO siatki i próg DSR liczący konfiguracje. Pełna specyfikacja: [specs/q8-parameter-selection-cpcv/](specs/q8-parameter-selection-cpcv/).

Slice'y: P1 dokumentacja · P2 CPCV · P3 strategia z doborem · P4 konfiguracje w DSR, PBO siatki i raport · P5 bramka in-sample w kryterium · P6 magazyn wyników i aplikacja · P7 zamrożenie `momentum_select_v1` · przebiegi lokalne i dziennik.

**Po zamrożeniu (2026-09-25):** `momentum_select_v1` — momentum szeregów czasowych na BTC i ETH z lookbackiem wybieranym co rok z siatki 30–365 dni po Sharpe netto z historii sprzed wyboru; bramka in-sample: mediana Sharpe ścieżek CPCV > 0; holdout 2026-01-01 → 2026-08-31. Sześć wartości siatki to sześć konfiguracji w progu DSR na `mvp-crypto` 2018–2023 (razem 9), więc opisowy DSR `momentum_v1`, `mean_reversion_v1` i `pairs_v1` spadnie przy ich następnym przebiegu — zgodnie z liczbą prób, bez zmiany ich wyników ani werdyktów. Zostały lokalne przebiegi: `uv run quantlab run momentum_select_v1`, potem jednorazowo `open-holdout`, wpis w dzienniku z porównaniem z `momentum_v1`.

### q9-strategy-portfolio (rozszerzenie, w toku)

Portfel zamrożonych strategii jako hipoteza: zamrożona reguła łączenia (składniki, reguła alokacji ryzyka, okno estymacji, rebalans miesięczny) zamiast pojedynczej strategii, wagi rękawów z ich samodzielnych przebiegów na historii sprzed dnia rebalansu, pozycje netto w jednym przebiegu silnika (obrót i koszty tylko różnic netto), korelacje, współczynnik dywersyfikacji i opisowe porównanie reguł oraz składników. Holdout portfela strzeżony przez otwarcia holdoutów składników. Pełna specyfikacja: [specs/q9-strategy-portfolio/](specs/q9-strategy-portfolio/).

Slice'y: P1 dokumentacja · P2 reguły alokacji · P3 strategia portfelowa i sizer wag netto · P4 definicja portfela i straż holdoutu · P5 raport · P6 `demo_portfolio` w magazynie syntetycznym · P7 zamrożenie `portfolio_v1` · przebiegi lokalne i dziennik.

**Po zamrożeniu (2026-09-25):** `portfolio_v1` — cztery hipotezy krypto (`momentum_v1`, `mean_reversion_v1`, `pairs_v1`, `momentum_select_v1`) ważone co miesiąc odwrotnością zmienności z 90 dni, pozycje netto; bramka walk-forward, holdout 2026-01-01 → 2026-08-31 otwierany dopiero po holdoutach trzech składników. Kolejna próba na `mvp-crypto` 2018–2023 (razem 5 prób, 10 konfiguracji), więc opisowy DSR pozostałych spadnie przy ich następnym przebiegu. Lokalnie, w tej kolejności: przebiegi treningowe i otwarcia holdoutów `mean_reversion_v1`, `pairs_v1`, `momentum_select_v1`; potem `uv run quantlab run portfolio_v1`, `open-holdout portfolio_v1`, wpis w dzienniku z porównaniem ze składnikami.

### q10-local-runbook (narzędzie, w toku)

Plan przebiegów lokalnych liczony ze stanu repozytorium i magazynu wyników: dla każdej zacommitowanej hipotezy przebieg treningowy (zrobiony tylko przy aktualnym schemacie i tej samej liście prób), otwarcie holdoutu (zablokowane do treningu i do holdoutów składników portfela), commit zapisu otwarcia i wpis w dzienniku; przed nimi sprawdzenia środowiska i budowa uniwersów. `--run` wykonuje sprawdzenia i kroki automatyczne po kolei, zatrzymuje się na pierwszym błędzie i nigdy nie wykonuje kroków ręcznych. Pełna specyfikacja: [specs/q10-local-runbook/](specs/q10-local-runbook/).

Slice'y: R1 dokumentacja · R2 stan i `quantlab plan` · R3 `quantlab plan --run` · R4 README „Przebiegi lokalne".

### q11-volatility-targeted-momentum (rozszerzenie, w toku)

Momentum szeregów czasowych z pozycjami skalowanymi do docelowej zmienności ex-ante per instrument: opakowanie dowolnej strategii (`VolatilityTargeted`) nadaje sygnałom skalę min(limit, docelowa / roczna zmienność ex-ante) z estymatora z rejestru (EWMA albo kroczący, stałe okno w rozgrzewce), sizer dzieli ją równo między handlowalne instrumenty; limit ≤ 1, bez dźwigni. Diagnostyka treningu porównuje wersję skalowaną z tym samym momentum bez skalowania. Pełna specyfikacja: [specs/q11-volatility-targeted-momentum/](specs/q11-volatility-targeted-momentum/).

Slice'y: V1 dokumentacja · V2 estymatory zmienności, opakowanie strategii, sizer · V3 definicja i diagnostyka treningu · V4 zamrożenie `momentum_voltarget_v1` · przebiegi lokalne i dziennik.

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
| q4-pairs-trading-stat-arb | Ready for dev | Ready for dev | Ready for dev | P1–P5 gotowe (`pairs_v1` zamrożona); P6 wymaga lokalnego przebiegu (Binance) |
| q5-equities-cross-section | Ready for dev | Ready for dev | Ready for dev | X1–X6 gotowe (point-in-time uniwersum, corporate actions, delisting i survivorship bias, polityka rebalansu, momentum przekrojowe, `demo_xsmom` w magazynie syntetycznym); decyzje 1–5 przyjęte 2026-09-24 (Tiingo, S&P 500 z Wikipedii, 12-1, test losowych portfeli); X7a (źródło i kalendarz w pliku uniwersum, proxy rynku bez członkostwa) i X7b (test losowych portfeli: `demo_xsmom` p = 0.002 wobec 0.99 z tasowania dni) gotowe; X7c (adapter Tiingo na odpowiedziach w udokumentowanym formacie) i X7d (`quantlab build-universe`: skład S&P 500 z zapisanej rewizji Wikipedii, raport sprzeczności, pokrycie cenami w `run`) gotowe — plik `sp500.yaml` do zbudowania lokalnie; pytania 6–7 rozstrzygnięte (zwrot z delistingu 0% z −30% opisowo, koszty 5 bps, k 0.05, 21 sesji); X8 gotowe: `xsmom_v1` zamrożona (`config/holdout/xsmom_v1.yaml`); X9–X11 lokalnie (budowa `sp500.yaml`, pobranie z Tiingo, trening, holdout, wpis w dzienniku) |
| q6-advanced-validation-cpcv | Ready for dev | Ready for dev | Ready for dev | V1–V5 gotowe; V6 wymaga lokalnych przebiegów (Binance) |
| q7-dotnet-react-presentation | Ready for dev | Ready for dev | Ready for dev | W1–W5 gotowe (magazyn wyników, API .NET, aplikacja React); W6: CI na Linuksie i Windowsie zielone; na maszynie deweloperskiej zostaje DuckDB bez AVX2 |
| q8-parameter-selection-cpcv | Ready for dev | Ready for dev | Ready for dev | P1–P7 gotowe (dokumentacja, CPCV, strategia z doborem, konfiguracje w DSR, PBO siatki i raport, bramka CPCV w kryterium, magazyn v3, API, aplikacja i tear-sheet, `demo_select`; decyzje 1–6 przyjęte 2026-09-25, `momentum_select_v1` zamrożona); przebiegi (trening, holdout, dziennik) lokalnie na Binance |
| q9-strategy-portfolio | Ready for dev | Ready for dev | Ready for dev | P1–P7 gotowe (dokumentacja, reguły alokacji, strategia portfelowa z pozycjami netto, definicja ze składnikami i strażą holdoutu, raport w diagnostyce i tear-sheecie, `demo_portfolio`, przyspieszenie strategii par bez zmiany wyników; decyzje 1–6 przyjęte 2026-09-25, `portfolio_v1` zamrożona); przebiegi lokalnie na Binance, holdout po holdoutach składników |
| q10-local-runbook | Ready for dev | Ready for dev | Ready for dev | R1–R4 gotowe (dokumentacja, `quantlab plan`, `plan --run`, `check-source`, README „Przebiegi lokalne"); na maszynie deweloperskiej: `uv run quantlab plan --run` |
| q11-volatility-targeted-momentum | Ready for dev | Ready for dev | Ready for dev | V1–V3 gotowe (dokumentacja, estymatory zmienności EWMA i kroczący, opakowanie `VolatilityTargeted`, sizer `ScaledEqualWeight`, definicja `time_series_momentum_vol_target`, diagnostyka skali i porównanie z wersją bez skalowania; zrzut regresji bez zmian); V4 czeka na pytania pre-rejestracji 1–6 |
