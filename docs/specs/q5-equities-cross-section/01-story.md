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

Should have — ostatni nierozpoczęty epik rozszerzeń. Kod (uniwersum, corporate actions, delisting, rebalans, strategia) powstaje na danych syntetycznych; adaptery (Tiingo, skład S&P 500) na nagranych, syntetycznych odpowiedziach, bo środowisko chmurowe nie ma dostępu do tych źródeł. Zamrożenie czeka na pytania 6–7 poniżej, przebiegi na lokalny dostęp do sieci.

## Dependencies and risks

- Zależy od `q1` (pipeline), `q3`-M1 (definicja hipotezy jako zamrożony plik), `q2` (parytet silników), `q6` (rejestr prób) i `q7` (magazyn wyników — akcje trafią tam bez zmian w UI).
- **Ryzyko: brak darmowego źródła z delistingami i historycznym składem.** Bez spółek zdjętych z obrotu test point-in-time jest fikcją. Jeśli źródło ich nie ma, wynik trzeba opisać jako obciążony, a hipotezę co najwyżej jako `inconclusive`.
- **Ryzyko: licencja.** Darmowe tiery zwykle zabraniają redystrybucji — surowe dane i magazyn wyników zostają poza repozytorium (jak dziś), w repo tylko fixtures syntetyczne.
- **Ryzyko: limity darmowych tierów** (np. liczba symboli na miesiąc) przy uniwersum rzędu setek spółek i kilkunastu lat — cache na dysku i pobieranie rozłożone w czasie.
- **Ryzyko: wielokrotne testowanie.** Nowe uniwersum to nowe dane, więc licznik prób zaczyna się od 1 (`q6` liczy próby na tym samym uniwersum i okresie).

## Decisions

Odpowiedzi na pytania 1–5, przyjęte przez Tomasza 2026-09-24 (wszystkie propozycje):

| # | Question | Decision |
|---|---|---|
| 1 | Źródło danych akcji | **Tiingo** (darmowy klucz; ceny dzienne, dywidendy, splity, spółki zdjęte z obrotu). Warunki i limity do sprawdzenia na stronie dostawcy przy pierwszym lokalnym użyciu, z datą w [DATA-SOURCES](../../DATA-SOURCES.md). Alpha Vantage, Sharadar i Yahoo Finance odrzucone (limity, koszt, warunki użycia) |
| 2 | Uniwersum i historyczny skład | **S&P 500 point-in-time** ze zmian składu w Wikipedii (CC BY-SA 4.0, z atrybucją), z jednej zapisanej rewizji strony |
| 3 | Hipoteza i parametry | **Momentum przekrojowe 12-1** (Jegadeesh i Titman 1993): formacja 12 miesięcy z pominięciem ostatniego, rebalans miesięczny, long górny decyl i short dolny decyl, równe wagi, pomijane spółki z ceną poniżej 5 USD na koniec miesiąca formacji |
| 4 | Zwrot z delistingu, gdy źródło go nie podaje | **−30%** (Shumway 1997) — patrz pytanie 6 |
| 5 | Okresy i kryterium | Trening **2005-01-01 → 2019-12-31**, holdout **2020-01-01 → 2025-12-31**; kryterium: Sharpe netto > 0 i p < 0.1, gdzie p pochodzi z **testu losowych portfeli** z tego samego przekroju (selekcja), nie z tasowania dni z `q1` (timing) |

## Open questions

Blokują zamrożenie (X8). Obie wynikły z decyzji 1–2 po ich przyjęciu.

| # | Question | Owner | Due |
|---|---|---|---|
| 6 | Zwrot z delistingu przy Tiingo i S&P 500. Tiingo nie podaje ani zwrotu z delistingu, ani przyczyny, więc −30% trafiłoby w każdy delisting. Tymczasem spółka zdjęta z obrotu jako członek S&P 500 to prawie zawsze przejęcie: ostatnie zamknięcie leży tuż przy cenie transakcji, zwrot z delistingu ≈ 0. Spółki upadające wypadają z indeksu przed zdjęciem z obrotu, a ich spadek jest w cenach. −30% dopisałoby więc fikcyjną stratę (w nodze long) albo zysk (w nodze short) przy każdym przejęciu. Propozycja: **0%** jako zamrożone założenie, a −30% jako opisowa analiza wrażliwości w wyniku | Tomasz | przed X8 |
| 7 | Model kosztów dla akcji. Propozycja: `fee_bps` **5** (prowizja i połowa spreadu dużych spółek S&P 500 z zapasem na lata 2005–2009), `k` **0.05** (jak w hipotezach krypto: poślizg względem zamknięcia w jednostkach dziennej zmienności), `vol_window` **21** (miesiąc sesji, odpowiednik 30 dni krypto). Koszt pożyczki akcji do shortu poza modelem (ograniczenie opisane w wyniku, jak w `q1`) | Tomasz | przed X8 |
