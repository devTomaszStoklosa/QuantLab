# q12-cross-asset-momentum - Momentum na koszyku ETF z różnych klas aktywów

Status: Ready for dev
Owner role: PO
Upstream: docs/specs/q1-momentum-research-mvp/, docs/specs/q5-equities-cross-section/, docs/specs/q11-volatility-targeted-momentum/
Links: docs/ROADMAP.md, docs/RESEARCH_LOG.md, docs/DATA-SOURCES.md

## Problem

Wszystkie hipotezy timingu w laboratorium testują dwa silnie skorelowane instrumenty krypto (BTC, ETH) od 2018 r.: `momentum_v1`, `mean_reversion_v1`, `pairs_v1`, `momentum_select_v1`, `portfolio_v1` i `momentum_voltarget_v1`. Tomasz zapytał 2026-09-26, czy budujemy rozwiązanie pod krypto, czy „równie skuteczne dla każdego instrumentu". Pytanie odsłania cztery luki:

1. **Wynik nie przenosi się sam.** Werdykt dotyczy uniwersum i okresu, na których zapadł; na krypto `momentum_v1` jest `inconclusive`. Moskowitz, Ooi i Pedersen (2012) oraz Hurst, Ooi i Pedersen (2017) opisują time-series momentum na kilkudziesięciu rynkach futures z różnych klas aktywów. To jednak cudze wyniki. Laboratorium nie ma ani jednego testu sygnału timingu poza krypto.
2. **Silnik liczy sesje jak dni.** Lookback momentum i okno estymatora zmienności liczą bary. Rozgrzewka liczy natomiast dni kalendarzowe: początek pobierania danych przed oknem i pierwszy wspólny dzień raportów.
   - Na krypto to jedno i to samo, bo rynek ma 365 sesji w roku.
   - Na rynku z 252 sesjami rozgrzewka 252 dni kalendarzowych daje ok. 173 sesje. Strategia z lookbackiem 252 sesji nie ma więc sygnału przez pierwsze ok. 4 miesiące każdego okna, holdoutu też. Nic tego nie zgłasza.
3. **Gotówka nic nie zarabia.** Silniki liczą zwroty pozycji bez oprocentowania gotówki, a Sharpe bez stopy wolnej od ryzyka. Na krypto (USDT) to przyjęte uproszczenie. Na ETF-ach w USD bony skarbowe przynosiły od ok. 0% (2009–2015) do ok. 5% rocznie (2023–2025):
   - zwrot długiej pozycji w ETF zawiera stopę wolną od ryzyka, a Sharpe powinien liczyć tylko nadwyżkę ponad nią;
   - niezainwestowana gotówka i wpływy z krótkiej sprzedaży realnie są oprocentowane, czego silnik nie widzi;
   - sygnał Moskowitza, Ooi i Pedersena to znak nadwyżki zwrotu ponad gotówkę (*excess return*), a nie samego zwrotu.
4. **Nie widać, skąd pochodzi wynik.** Instrument zna tylko klasy `crypto` i `equity`, a rejestr transakcji dzieli P&L wyłącznie po reżimie i czasie trzymania. Na pytanie „czy działa dla każdego instrumentu" trzeba zobaczyć wkład każdej klasy aktywów i każdego instrumentu.

## Outcome

Primary metric: hipotezy momentum na koszyku ETF mają jednoznaczny status w `docs/RESEARCH_LOG.md`. Wpis porównuje je z `momentum_v1` (krypto) i opisowo pokazuje P&L per klasa aktywów i per instrument.
Guardrail metric: wyniki wszystkich zamrożonych hipotez identyczne co do bitu (zrzut regresji); ich werdykty bez zmian.

## User story

Jako badacz chcę przetestować regułę `momentum_v1` na koszyku ETF z różnych klas aktywów: akcji, obligacji, surowców, dolara i nieruchomości. Rozgrzewka ma być liczona w sesjach giełdowych, zwroty ponad gotówkę, a P&L rozbity na klasy aktywów i instrumenty. Chcę wiedzieć, czy efekt timingu jest ogólny, czy wynik na krypto był specyficzny dla tego rynku.

## Acceptance criteria

- AC-1 (rozgrzewka w sesjach): Given uniwersum z 252 sesjami w roku i strategia liczącą okno w sesjach, when pobieram dane do okna od dnia s, then sygnał istnieje od pierwszego dnia okna, o ile dane na to pozwalają. Na uniwersum z 365 sesjami rozgrzewka ma dokładnie tyle dni co dziś: zrzut regresji się nie zmienia.
- AC-2 (zwroty ponad gotówkę): Given uniwersum z instrumentem gotówkowym (ETF na bony skarbowe), when silniki liczą zwroty, then:
  - każdy instrument ma zwrot ponad gotówkę, więc instrument rosnący dokładnie jak gotówka ma zerowy zwrot;
  - niezainwestowana część kapitału zarabia zero ponad gotówkę, a pozycja krótka minus nadwyżkę instrumentu;
  - sygnał widzi te same ceny, więc momentum to znak nadwyżki zwrotu;
  - uniwersum bez instrumentu gotówkowego liczy się jak dziś.
- AC-3 (skąd wynik): Given przebieg z rejestrem transakcji, when uruchamiam `quantlab run`, then terminal, magazyn wyników i aplikacja pokazują P&L netto per klasa aktywów i per instrument. Każda grupa ma liczbę transakcji, udział zyskownych, sumę, medianę, najgorszą i najlepszą transakcję oraz koszty.
- AC-4 (uniwersum ETF): Given plik uniwersum ETF, when go wczytuję, then:
  - ma źródło Tiingo, 252 sesje w roku, proxy rynku i instrument gotówkowy;
  - każdy instrument ma klasę aktywów;
  - instrument gotówkowy nie jest handlowany;
  - `quantlab plan` pokazuje przebiegi czekające na źródło Tiingo.
- AC-5 (pipeline): Given hipoteza na koszyku ETF, when uruchamiam oba silniki, then krzywe kapitału są zgodne jak w `q2`. Hipoteza przechodzi ten sam pipeline co pozostałe: trzy modele kosztów, walk-forward, test permutacyjny, PSR i DSR z próbami na tym uniwersum, reżimy, stres, rejestr transakcji i jednorazowo otwierany holdout.
- AC-6 (wynik): Given zamrożone definicje i jednorazowo otwarte holdouty, when zapisuję wpis w dzienniku, then wpis zawiera:
  - status;
  - porównanie z `momentum_v1`;
  - P&L per klasa aktywów, opisany jako wynik historyczny na tym koszyku, bez uogólnienia na „każdy instrument".

## Out of scope

- Kontrakty futures (rolowanie, mnożniki, depozyt): ETF-y dają ekspozycję na klasy aktywów przez źródło, które laboratorium już obsługuje (Tiingo).
- Koszt pożyczki ETF przy krótkiej sprzedaży i spread finansowania ponad stopę gotówki. To ograniczenie opisane przy wyniku: dla płynnych ETF-ów zwykle ułamek procenta rocznie od krótkiej części portfela.
- Portfel łączący krypto i ETF-y. Wymaga wspólnego kalendarza (365 i 252 sesje), odłożonego od `q9`.
- Test istotności per klasa aktywów albo per instrument. Podział P&L jest opisowy; kilkanaście osobnych testów to wielokrotne testowanie.
- Waluty rozliczenia inne niż USD i dane śróddzienne.
- Zmiana definicji, wyników i werdyktów zamrożonych hipotez.

## Priority

Should have. Następny epik po `q11`, rozpoczęty 2026-09-26 z pytania Tomasza o przenośność wyniku krypto. Kod powstaje na danych syntetycznych: rozgrzewka w sesjach, gotówka, klasy aktywów i podział P&L. Zamrożenie następuje po odpowiedziach na pytania 1–7 poniżej. Przebiegi są lokalne: Tiingo, klucz `TIINGO_API_KEY`.

## Dependencies and risks

- Zależy od:
  - `q1`: sygnał momentum, pipeline;
  - `q2`: parytet silników;
  - `q5`: adapter Tiingo, korekty o dywidendy, `periods_per_year`;
  - `q6`: rejestr prób, DSR;
  - `q7`: magazyn wyników i aplikacja;
  - `q10`: plan przebiegów;
  - `q11`: skalowanie zmiennością, jeśli pytanie 2 wybierze wariant ze skalowaniem.
- **Ryzyko: koszyk wybrany z wiedzą o dniu dzisiejszym.** ETF-y dobrane dziś jako płynne i długo notowane przetrwały do dziś (przeżywalność). Mitygacja: jeden–trzy szerokie ETF-y na klasę aktywów, ustalone w pliku uniwersum przed pierwszym przebiegiem, bez doboru po wynikach. Opisane w dzienniku.
- **Ryzyko: ogólna wiedza o okresie holdoutu.** Wiadomo, że trend following zarobił w 2022 r. i słabo radził sobie w latach 2016–2019. Holdout jest „niewidziany" tylko w tym sensie, że nie czytał go żaden przebieg laboratorium. Opisane w dzienniku; reguła i parametry pochodzą z literatury sprzed 2012 r. i z `momentum_v1`.
- **Ryzyko: krótka historia gotówki.** ETF na bony 1–3-miesięczne (BIL) jest notowany od maja 2007 r. Zwroty ponad gotówkę istnieją od tego dnia, więc trening zaczyna się po rozgrzewce, ok. połowy 2008 r.
- **Ryzyko: ceny w rejestrze transakcji.** Ceny po odjęciu gotówki nie są notowaniami rynkowymi. Rejestr i dziennik to opisują.
- **Ryzyko: limity darmowego Tiingo.** 11 tickerów (z gotówką) to ceny i metadane: ok. 22 zapytania na każde nowe okno pobierania, przy odstępie 90 s ok. 35 minut. Cache na dysku, więc przerwane pobieranie wznawia się od miejsca przerwania.
- **Ryzyko: kolejne próby.** Nowe uniwersum zaczyna rejestr prób od zera; każda zamrożona tu hipoteza to jedna próba w DSR pozostałych na tych samych danych.

## Open questions

Pytania pre-rejestracji do rozstrzygnięcia przed zamrożeniem (C5); każde z propozycją:

| # | Question | Proposal |
|---|---|---|
| 1 | Koszyk | 10 ETF-ów: akcje SPY, EFA, EEM; obligacje IEF, TLT, LQD; surowce GLD, DBC; dolar UUP; nieruchomości VNQ. Gotówka BIL, nie handlowana. Proxy rynku SPY |
| 2 | Hipotezy | dwie próby: `momentum_multiasset_v1` (reguła `momentum_v1`: znak nadwyżki 12-miesięcznej, równe wagi po znaku) i `momentum_voltarget_multiasset_v1` (ten sam sygnał ze skalowaniem `q11`) |
| 3 | Lookback | 252 sesje (12 miesięcy, jak 365 dni `momentum_v1` na krypto) |
| 4 | Skalowanie (jeśli wariant) | cel 10% rocznie na instrument (MOP: 40%, ale z dźwignią na futures; bez dźwigni 40% przycina tylko najbardziej zmienne ETF-y), EWMA ze środkiem masy 60 sesji w oknie 252, limit 1 |
| 5 | Koszty | realistyczny: opłata 3 bps (prowizja i połowa spreadu płynnych ETF-ów z zapasem na 2008), k 0.05, zmienność z 21 sesji |
| 6 | Okresy | trening 2008-07-01 → 2017-12-31; holdout 2018-01-01 → 2026-08-31 |
| 7 | Kryterium sukcesu | bramka walk-forward; holdout: Sharpe netto (model realistyczny) > 0 i p < 0.1 z testu permutacyjnego |
