# q5-equities-cross-section - Akcje przekrojowo: point-in-time uniwersum, corporate actions i survivorship bias

Status: Ready for dev
Owner role: PO
Upstream: docs/specs/q1-momentum-research-mvp/, docs/specs/q3-mean-reversion-hypothesis/, docs/adr/0007-binance-not-stooq-for-first-adapter.md
Links: docs/ROADMAP.md, docs/DATA-SOURCES.md, docs/RESEARCH_LOG.md

## Problem

Wszystkie dotychczasowe hipotezy grają na dwóch kryptowalutach. Rynek krypto nie ma tego, co w badaniach nad akcjami decyduje o wiarygodności wyniku:

1. **Zmienny skład uniwersum.** Koszyk akcji (np. indeks) zmienia się w czasie. Backtest na dzisiejszym składzie przenosi w przeszłość wiedzę o tym, kto przetrwał — **survivorship bias**, najczęstszy błąd backtestów akcji. `Universe` jest dziś statyczną listą.
2. **Corporate actions.** Splity i dywidendy zmieniają cenę bez zmiany wartości pozycji. Zwroty liczone z surowych cen pokazują fałszywe spadki w dniu splitu i gubią dywidendy. `PriceBar` ma pole `adj_close`, ale nic go nie liczy ani nie używa.
3. **Delisting.** Spółka znika z giełdy (upadłość, przejęcie); jej ostatni zwrot — często mocno ujemny — musi trafić do wyniku portfela. Oba silniki pomijają dziś instrument bez baru, więc pozycja w upadającej spółce „wyparowałaby" bez straty (delisting bias, Shumway 1997).
4. **Strategia przekrojowa.** Wszystkie strategie ważą instrumenty niezależnie (każdy względem własnej historii). Klasyczne anomalie akcyjne — momentum przekrojowe (Jegadeesh i Titman 1993) — rankują instrumenty względem siebie w danym dniu i rebalansują co miesiąc, a nie co dzień.

Brakuje też źródła danych: Stooq odpadł ([ADR-0007](../../adr/0007-binance-not-stooq-for-first-adapter.md)), a darmowe źródła akcji rzadko mają spółki zdjęte z obrotu i historyczne składy indeksów.

## Outcome

Primary metric: hipoteza przekrojowa na point-in-time uniwersum akcji ma jednoznaczny status w `docs/RESEARCH_LOG.md`, a jej wynik uwzględnia spółki zdjęte z obrotu, ich zwroty z delistingu, splity i dywidendy.
Guardrail metric: wyniki wszystkich istniejących hipotez (krypto) są identyczne co do bitu po zmianach w uniwersum, danych i silnikach; test na danych syntetycznych pokazuje wprost, ile survivorship bias zawyżyłby wynik.

## User story

Jako badacz chcę testować hipotezy przekrojowe na akcjach z uniwersum takim, jakie było znane w każdym dniu historii, z cenami skorygowanymi o splity i dywidendy i ze zwrotami ze spółek zdjętych z obrotu, żeby wynik nie był zawyżony wiedzą o tym, kto przetrwał.

## Acceptance criteria

- AC-1 (point-in-time uniwersum): Given uniwersum z okresami członkostwa, when strategia liczy sygnały na dzień t, then widzi wyłącznie instrumenty należące do uniwersum w dniu t; uniwersum statyczne (krypto) zachowuje się dokładnie jak dziś.
- AC-2 (corporate actions): Given surowe ceny i lista splitów oraz dywidend, when koryguję ceny, then zwrot z dnia splitu jest zwrotem ekonomicznym (bez skoku ceny), dywidenda wchodzi do zwrotu całkowitego w dniu ex-dividend, a surowa cena zamknięcia zostaje dostępna do filtrów po poziomie ceny.
- AC-3 (delisting): Given spółka zdjęta z obrotu, when silnik trzyma w niej pozycję, then ostatni okres realizuje zwrot z delistingu (ze źródła albo zamrożone założenie, gdy źródło go nie podaje), a potem pozycja znika; test syntetyczny pokazuje różnicę wyniku z i bez spółek zdjętych z obrotu.
- AC-4 (rebalans): Given strategia z rebalansem miesięcznym, when sygnały nie zmieniają się między dniami, then silnik nie handluje dryfem wag; oba silniki robią to samo (parytet `q2`), a istniejące hipotezy z codziennym rebalansem mają wyniki bez zmian.
- AC-5 (strategia przekrojowa): Given point-in-time uniwersum, when liczę momentum przekrojowe, then ranking używa tylko danych z datą ≤ dnia formacji i tylko członków uniwersum w tym dniu, a portfel to górny (i ewentualnie dolny) kwantyl z równymi wagami.
- AC-6 (źródło danych): Given wybrane źródło, when pobieram dane akcji, then adapter `DataProvider` daje ceny, corporate actions i delistingi z throttlingiem i cache, licencja jest sprawdzona i zapisana w `docs/DATA-SOURCES.md`, a surowe dane nie trafiają do repozytorium.
- AC-7 (wynik): Given zamrożona definicja i jednorazowo otwarty holdout, when zapisuję wpis w dzienniku, then zawiera status, PSR i DSR z liczbą prób na tych danych, oraz wpływ kosztów i delistingów na wynik.

## Out of scope

- Fundamenty (wartość, jakość) — wymagają point-in-time danych księgowych z datami publikacji; osobny epik.
- Dane śróddzienne, krótka sprzedaż z kosztem pożyczki i ograniczeniami (short na akcjach opisany jako ograniczenie, jak w `q1`).
- Waluty i wiele giełd naraz — jedno uniwersum w jednej walucie.
- Wybór najlepszej z wielu wariantów strategii — parametry z literatury, zamrożone przed przebiegiem (ukryte próby, `q6`).

## Priority

Should have — ostatni nierozpoczęty epik rozszerzeń. Kod (uniwersum, corporate actions, delisting, rebalans, strategia) powstaje na danych syntetycznych; adapter, zamrożenie i przebiegi czekają na decyzje z tabeli poniżej i na lokalny dostęp do sieci.

## Dependencies and risks

- Zależy od `q1` (pipeline), `q3`-M1 (definicja hipotezy jako zamrożony plik), `q2` (parytet silników), `q6` (rejestr prób) i `q7` (magazyn wyników — akcje trafią tam bez zmian w UI).
- **Ryzyko: brak darmowego źródła z delistingami i historycznym składem.** Bez spółek zdjętych z obrotu test point-in-time jest fikcją. Jeśli źródło ich nie ma, wynik trzeba opisać jako obciążony, a hipotezę co najwyżej jako `inconclusive`.
- **Ryzyko: licencja.** Darmowe tiery zwykle zabraniają redystrybucji — surowe dane i magazyn wyników zostają poza repozytorium (jak dziś), w repo tylko fixtures syntetyczne.
- **Ryzyko: limity darmowych tierów** (np. liczba symboli na miesiąc) przy uniwersum rzędu setek spółek i kilkunastu lat — cache na dysku i pobieranie rozłożone w czasie.
- **Ryzyko: wielokrotne testowanie.** Nowe uniwersum to nowe dane, więc licznik prób zaczyna się od 1 (`q6` liczy próby na tym samym uniwersum i okresie).

## Open questions

Blokują adapter (X7) i zamrożenie (X8); do tego czasu kod powstaje na danych syntetycznych.

| # | Question | Owner | Due |
|---|---|---|---|
| 1 | Źródło danych akcji. Kandydaci (warunki do sprawdzenia na stronie dostawcy przed użyciem): **Tiingo** (darmowy klucz; ceny dzienne z korektami, dywidendy i splity, także spółki zdjęte z obrotu; limit symboli miesięcznie; bez redystrybucji), **Alpha Vantage** (darmowy tier 25 zapytań dziennie; lista spółek zdjętych z obrotu; skorygowane dane dzienne w płatnym tierze), **Sharadar przez Nasdaq Data Link** (płatne; pełne delistingi i akcje korporacyjne), **Yahoo Finance** (odrzucone: warunki użycia i brak spółek zdjętych z obrotu). Propozycja: Tiingo | Tomasz | przed X7 |
| 2 | Uniwersum i historyczny skład. Propozycja: S&P 500 point-in-time ze zmian składu publikowanych w Wikipedii (CC BY-SA 4.0, z atrybucją); alternatywa: mniejszy indeks z pełną historią (np. Dow Jones Industrial Average), ale 30 spółek to za mało na kwantyle | Tomasz | przed X7 |
| 3 | Hipoteza i parametry. Propozycja: momentum przekrojowe 12-1 (Jegadeesh i Titman 1993): formacja 12 miesięcy z pominięciem ostatniego, rebalans miesięczny, long górny decyl i short dolny decyl, równe wagi, pomijane spółki z ceną poniżej 5 USD w dniu formacji | Tomasz | przed X8 |
| 4 | Zwrot z delistingu, gdy źródło go nie podaje. Propozycja: −30% (Shumway 1997, delistingi z przyczyn wynikowych); alternatywa: 0% (neutralne, zaniża bias) | Tomasz | przed X8 |
| 5 | Okres treningowy, holdout i kryterium. Propozycja: trening 2005-01-01 → 2019-12-31, holdout 2020-01-01 → 2025-12-31 (dane nieoglądane w tym projekcie), kryterium jak w pozostałych hipotezach (Sharpe netto > 0 i p < 0.1) | Tomasz | przed X8 |
