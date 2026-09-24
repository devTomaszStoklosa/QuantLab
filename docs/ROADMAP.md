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

**Po `q4`-P5 (2026-09-24):** `q2`, `q3`, `q4` i `q6` czekają na lokalne przebiegi (Binance), `q5` na decyzję o źródle danych akcji. Odblokował się `q7-dotnet-react-presentation`: .NET 10 SDK jest w archiwum Ubuntu, dostępnym w środowisku chmurowym. Epik nie zależy od danych rynkowych — API i UI testowane są na syntetycznym magazynie wyników wygenerowanym pełnym pipeline'em.

**Po `q7`-W5 (2026-09-24):** jedyny nierozpoczęty epik to `q5-equities-cross-section`. Kod niezależny od źródła danych (point-in-time uniwersum, corporate actions, delisting, polityka rebalansu, momentum przekrojowe) powstaje na danych syntetycznych; adapter i zamrożenie hipotezy czekają na decyzje o źródle danych, uniwersum i parametrach (pytania w [01-story](specs/q5-equities-cross-section/01-story.md)).

**Po decyzjach `q5` 1–5 (2026-09-24):** adapter X7 dzieli się na cztery części na danych syntetycznych i nagranych odpowiedziach (kalendarz i źródło w pliku uniwersum, test losowych portfeli, Tiingo, budowa składu S&P 500). Zamrożenie `xsmom_v1` czeka na dwa pytania, które wynikły z wyboru źródła: zwrot z delistingu (Tiingo go nie podaje, a w S&P 500 delisting członka to prawie zawsze przejęcie) i model kosztów dla akcji. Budowa pliku uniwersum, pobranie cen i przebiegi — lokalnie.

**Po `q5`-X8 (2026-09-24):** `xsmom_v1` zamrożona po decyzjach 1–7: momentum 12-1 na S&P 500 point-in-time (Tiingo, Wikipedia), trening 2005–2019, holdout 2020–2025, kryterium z testem losowych portfeli. Cały kod epiku gotowy; reszta wymaga sieci i dzieje się lokalnie, w tej kolejności: `uv run quantlab build-universe` (poprawki tickerów tylko z raportu budowy, potem commit `sp500.yaml` i `sp500-renames.yaml`), `uv run quantlab run xsmom_v1` z kluczem `TIINGO_API_KEY` (pobieranie rozłożone w czasie, patrz DATA-SOURCES), `uv run quantlab open-holdout xsmom_v1`, wpis w dzienniku (REQ-562). Wszystkie epiki mają już kod; otwarte są tylko przebiegi lokalne (`q2`–`q6` na Binance, `q5` na Tiingo) i weryfikacja `q7` na Windows.

