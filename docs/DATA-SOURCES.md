# Źródła danych

## Zasady

1. **Tylko darmowe źródła, repozytorium prywatne** (decyzja 2026-09-26, [ADR-0009](adr/0009-private-repo-free-tiingo-plan.md)). Żadnych płatnych planów. Licencje darmowych planów (Tiingo Starter) pozwalają tylko na użytek własny, więc surowe dane nie trafiają do repozytorium, a wyniki z cenami rynkowymi (rejestr transakcji, tear-sheet, aplikacja) nie są publikowane.
2. **Throttling po naszej stronie**, nie przez odpowiedzi z kodem błędu. Każdy klient w `core.data` ma minimalny odstęp między żądaniami.
3. **Cache na dysku** (`data/cache/`, gitignored) — tych samych danych nie pobieramy dwa razy.
4. **Atrybucja** idzie razem z danymi (źródło + URL w metadanych zapisu).
5. **Dane testowe w repo tylko syntetyczne** (`data/fixtures/`) — wygenerowane, nie pobrane.

## Źródła rozważane

| Źródło | Co daje | Klucz | Limit | Licencja / redystrybucja | Epik |
|---|---|---|---|---|---|
| Binance public REST (`api.binance.com/api/v3/klines`) | historyczne świece krypto (OHLCV + timestampy ms), bez klucza dla danych publicznych. Format zweryfikowany na żywo 2026-09-23, patrz [ADR-0007](adr/0007-binance-not-stooq-for-first-adapter.md) | nie | limity wagowe per endpoint, patrz dokumentacja Binance | dane historyczne klines zwykle bez ograniczeń redystrybucji dla non-trading use — do potwierdzenia w aktualnym Terms of Use przed użyciem | lab-foundation, q1 |

### Akcje (`q5`) — wybrane Tiingo i Wikipedia (decyzja 2026-09-24)

Warunki poniżej to stan wiedzy, nie weryfikacja — do sprawdzenia na stronie dostawcy przy pierwszym lokalnym użyciu (środowisko chmurowe nie ma dostępu do tych stron), z datą w kolumnie „Uwagi”. Adaptery powstały na nagranych, syntetycznych odpowiedziach.

| Źródło | Co daje | Klucz | Ograniczenia | Uwagi |
|---|---|---|---|---|
| Tiingo (`api.tiingo.com`) | ceny dzienne surowe i skorygowane, dywidendy (`divCash`) i splity (`splitFactor`) w dniu ex-date, metadane z nazwą spółki oraz pierwszym i ostatnim dniem notowań (także spółki zdjęte z obrotu); bez zwrotu z delistingu i bez jego przyczyny; pod tickerem przejętym przez inną spółkę ceny tamtej spółki (#104) | tak: darmowe konto, plan Starter ($0), zmienna `TIINGO_API_KEY` | plan Starter według opisów z 2026-09-26: 500 różnych tickerów miesięcznie, 50 zapytań na godzinę, 1 000 dziennie, ponad 30 lat historii. Ok. 1 050 tickerów S&P 500 z lat 2004–2025 to pobieranie w trzech miesiącach kalendarzowych | **wybrane** ([ADR-0009](adr/0009-private-repo-free-tiingo-plan.md)); licencja tylko na użytek własny, więc repozytorium prywatne, bez redystrybucji danych i bez publikacji wyników z cenami; warunki do potwierdzenia przy zakładaniu konta |
| Alpha Vantage | lista spółek zdjętych z obrotu; skorygowane dane dzienne opisane jako premium | tak | 25 zapytań dziennie w darmowym planie | za wolne na setki spółek |
| Nasdaq Data Link (Sharadar) | pełne delistingi, akcje korporacyjne, point-in-time | tak (płatne) | koszt | odrzucone: tylko darmowe źródła |
| EODHD | ceny dzienne, spółki zdjęte z obrotu w planach płatnych | tak | 20 zapytań dziennie w darmowym planie | odrzucone: za mało zapytań, delistingi płatne |
| Polygon (Massive) | ceny dzienne | tak | darmowy plan: ok. 1–2 lat historii | odrzucone: za krótka historia |
| Wikipedia — *List of S&P 500 companies* i *Historical components of the S&P 500* | bieżący skład (pierwsza strona) i tabela zmian składu (druga; przeniesiona tam z listy 2026-08-11), z których odtwarzamy skład wstecz | nie (API MediaWiki, nagłówek `User-Agent`) | CC BY-SA 4.0: plik uniwersum w repo z atrybucją i numerami rewizji obu stron; kompletność przed ok. 2000 r. niepewna | **wybrane**; tylko członkostwo, bez cen |
| Yahoo Finance | ceny | nie | warunki użycia zabraniają dostępu programistycznego; brak spółek zdjętych z obrotu | odrzucone |

#### Tiingo lokalnie (`core.data.tiingo.TiingoProvider`, `q5`-X7c)

- Klucz: zmienna środowiskowa `TIINGO_API_KEY`. Bez niej `quantlab run` kończy się przed pobraniem danych.
- Odstęp żądań: domyślnie 90 s, co mieści się w limitach planu Starter: 50 zapytań na godzinę i 1 000 dziennie. Zmienna `TIINGO_REQUEST_INTERVAL_SECONDS` jest tylko na wypadek zmiany limitów planu.
- Limit miesięczny: adapter liczy tickery, o które pytał w danym miesiącu (według czasu Eastern, jak Tiingo). Przed 501. zatrzymuje przebieg komunikatem `rerun next month`, zamiast trafić na błąd Tiingo w połowie pobierania. Odpowiedzi z cache się nie liczą. Zmienna `TIINGO_MONTHLY_SYMBOLS` (domyślnie 500) jest tylko na wypadek zmiany limitów planu.
- Przed każdym zapytaniem `run` wypisuje na stderr linię z godziną, tickerem, zakresem i numerem tickera w miesiącu. Odpowiedzi z cache niczego nie wypisują.
- Każdy ticker to dwa zapytania (ceny w zakresie przebiegu, metadane z ostatnim dniem notowań), zadawane jedno po drugim, zanim przebieg przejdzie do następnego tickera. Przebieg zatrzymany limitem miesięcznym nie zostawia więc na następny miesiąc metadanych tickerów policzonych w bieżącym, a żaden ticker jednego przebiegu nie liczy się w dwóch miesiącach. Odpowiedzi trafiają do `data/cache/`, więc przerwane pobieranie wznawia się od miejsca przerwania, a limit zapytań kończy komendę jednym komunikatem, nie wyjątkiem.
- Skala dla `xsmom_v1` (według `sp500.yaml`): trening to 737 członków S&P 500 z lat 2005–2019 i SPY, czyli 738 tickerów, ok. 1 480 zapytań i ok. 37 h przy 90 s. Holdout (2020–2025) to 610 tickerów: ceny w nowym zakresie, a metadane tylko dla 95 spółek spoza treningu (reszta jest w cache), razem ok. 700 zapytań i ok. 18 h. Limit liczy tickery w każdym miesiącu od nowa, więc holdout liczy swoje 610 niezależnie od treningu. Razem to ok. 1 350 tickerów przy 500 na miesiąc, czyli pobieranie w trzech miesiącach kalendarzowych. Adapter sam zatrzymuje się na limicie, a kolejny miesiąc wznawia z cache.
- Skala dla ETF-ów (`q12`, uniwersum `multiasset-etf`): 10 ETF-ów i gotówka BIL, każdy po dwa zapytania na okno pobierania, czyli ok. 22 zapytania i ok. 35 min przy 90 s na trening i tyle samo na holdout. Dwie hipotezy na tym samym oknie czytają ten sam cache. ETF-y są w danych dziennych Tiingo na tych samych warunkach co akcje (bez redystrybucji surowych danych).
- Test bez sieci: odpowiedź w udokumentowanym formacie Tiingo z syntetycznymi liczbami (`tests/core/data/test_tiingo.py`) — środowisko chmurowe nie ma dostępu do API, więc to nie jest nagranie na żywo. Przy pierwszym lokalnym pobraniu warto porównać format z prawdziwą odpowiedzią (pola `date`, `open`, `high`, `low`, `close`, `volume`, `adjClose`, `divCash`, `splitFactor`; metadane `endDate`).

#### Tickery przejęte przez inne spółki (`quantlab audit-tickers`, #104)

- Tiingo trzyma pod tickerem jedną spółkę, zwykle ostatnią, która go używa, z całą jej historią cen. Wcześniejsza spółka z tym tickerem nie dostaje więc pustej serii, tylko wiarygodnie wyglądające ceny innej spółki. Nie wychwyci ich ani raport pokrycia, ani `check-data`. Metadane pobrane 2026-10-02 to potwierdziły:
  - pod `MIL` jest MFC Industrial zamiast Millipore;
  - pod `LSI` jest Life Storage zamiast LSI Corp;
  - pod `GENZ` jest ETF VanEck zamiast Genzyme;
  - pod `EP` jest Empire Petroleum zamiast El Paso;
  - `NVLS` nosi nazwę ETF-u Defiance, ale ceny z dni członkostwa należą do Novellusa (przegląd 2026-10-18), więc zostaje.
- Dokumentacja cen dziennych nie opisuje dostępu do wcześniejszej spółki pod tym samym tickerem. Stały identyfikator `permaTicker` jest opisany tylko dla danych fundamentalnych, a te są darmowe wyłącznie dla spółek DOW 30. Dlatego takich cen nie odzyskujemy (decyzja z 2026-10-02).
- Takie spółki trafiają na listę `not_in_source` w `sp500-renames.yaml`, a `build-universe` przepisuje ją do `sp500.yaml`. Laboratorium nie pyta o nie Tiingo. Zostają członkami bez cen, strategia ich nie widzi, a `run` wymienia je w raporcie pokrycia osobno, jako wykluczone celowo. Przegląd audytu `xsmom_v1` (2026-10-18) wykluczył siedem tickerów: `AA`, `DISCA`, `EP`, `GENZ`, `LSI`, `MIL` i `SUN`. Dowody są w komentarzach `sp500-renames.yaml`, a uzasadnienie i udział wykluczonych dni członkostwa w [dzienniku](RESEARCH_LOG.md).
- To ograniczenie, nie naprawa. Wykluczone spółki to zwykle spółki przejęte, często z premią, więc ich brak zmienia przekrój tak samo jak każdy brak cen w źródle. Wpis w dzienniku podaje, które spółki wykluczono i jaki to udział dni członkostwa.
- `quantlab audit-tickers <id>` sprawdza każdego byłego członka S&P 500 w oknie hipotezy (trening i holdout). Porównuje nazwy spółki z tabeli zmian Wikipedii (przypięta rewizja) z tym, co Tiingo trzyma pod tickerem: nazwą, pierwszym i ostatnim dniem notowań oraz opisem. Oznacza:
  - nazwę bez wspólnego słowa (`name differs`) albo częściowo inną (`name partly differs`);
  - ceny, które zaczynają się po początku członkostwa;
  - ceny, które kończą się ponad tydzień przed końcem członkostwa;
  - ticker nieznany Tiingo.
- Audyt dokłada medianę ceny i obrotu w dniach członkostwa, wyłącznie z cen treningowych z cache; cen holdoutu nie czyta. Tabelę zapisuje w `results/ticker-audit-<id>.csv` (poza repozytorium, bo mediany pochodzą z cen Tiingo), z oznaczonymi tickerami na początku.
- Audyt niczego nie rozstrzyga. Spółka po zmianie nazwy też ma inną nazwę, a nazwa w metadanych Tiingo potrafi nie zgadzać się z opisem (`LSI`: nazwa Life Storage, opis LSI Logic). Każdy oznaczony ticker przegląda się ręcznie, a potwierdzone przypadki trafiają do `not_in_source` z dowodem w komentarzu. Przypadki niejednoznaczne wykluczamy zachowawczo: brak danych szkodzi mniej niż ceny nieznanej spółki.
- Koszt: jedno zapytanie o metadane na ticker. Cache metadanych trzyma nazwę, pierwszy dzień notowań i opis obok ostatniego dnia notowań. Wpisy zapisane przed #104 miały tylko ostatni dzień, więc audyt pyta o nie ponownie, ale bierze z odpowiedzi tylko nazwę, pierwszy dzień i opis. Ostatni dzień notowań i dzień pobrania zostają z cache, bo od nich przebieg datuje delisting, a odpowiedź Tiingo mogła się od tego czasu zmienić (ticker nieznany albo przejęty przez inny papier, #126). Kolumna „source last price” pokazuje więc przy takim wpisie dzień z pierwszego zapytania. Dla `xsmom_v1` to 343 byłych członków, ok. 8,6 h przy 90 s, a każdy ticker liczy się do limitu miesięcznego.

#### Skład S&P 500 lokalnie (`core.sp500`, `quantlab build-universe`, `q5`-X7d)

- Komenda czyta dwie strony, każdą w ostatniej rewizji sprzed 2026-09-24T00:00Z (API MediaWiki, bez klucza): *List of S&P 500 companies* (bieżący skład) i *Historical components of the S&P 500* (tabela zmian). Tabela zmian była częścią listy do 2026-08-11, kiedy przeniesiono ją na osobną stronę bez zmiany formatu. Komenda odtwarza skład wstecz do 2000-01-01 i zapisuje `src/quantlab/config/universes/sp500.yaml` z numerami obu rewizji i atrybucją CC BY-SA 4.0 w nagłówku (plik jest adaptacją treści Wikipedii i dzieli jej licencję).
- Raport budowy wymienia sprzeczności tabeli zmian z nazwami spółek. Zmiany tickerów (np. `FB` → `META`) trafiają do `renames` w `sp500-renames.yaml`. Ticker, którego używała też inna spółka, trafia do `dated_renames` z zakresem dat, np. `UA` → `UAA` do 2016-04-07 (Under Armour kl. A, zanim `UA` przejęła klasa C). Potem budowę się powtarza.
- Zasady odtwarzania, ustalone przy przeglądzie pierwszej budowy (2026-09-28):
  - Tabela zmian nie ma wiersza dodania części spółek; w pierwszej budowie dotyczyło to 99 obecnych członków. Obecny okres członkostwa zaczyna się więc w dniu „date added” z listy spółek, chyba że ta data wypada we wcześniejszym okresie tego samego tickera. Członkostwo sprzed wejścia do indeksu zawyżałoby momentum, bo spółki trafiają do indeksu po silnych wzrostach. Raport wymienia każdą tak ustaloną datę.
  - Kilka dat na liście wygląda na błędne (np. D 2016, SRE 2017, TROW 2019). Te spółki wypadają z uniwersum na część lat, co jest mniej szkodliwe dla testu momentum niż członkostwo przed wejściem do indeksu; wpis w dzienniku to opisuje.
  - Przylegające okresy jednego tickera zostają osobne. Tak wygląda zmiana tickera zapisana w tabeli jako dodanie i usunięcie (np. WLTW → WTW), ale też ticker, którym dwie spółki wymieniły się jednego dnia (FOXA: 21st Century Fox do 2019-03-18, Fox Corp od 2019-03-19). Data z listy równa początkowi przylegających okresów jest spójna i nie trafia do raportu.
- Znane ograniczenia po pierwszej budowie: stare AT&T Corp (`T` do 2005) i Allergan Inc (`AGN` do 2015) mają tickery przejęte przez inne spółki, więc nie mają własnego okresu. Starsze spółki tickerów z kilkoma okresami (np. `Q`: Qwest do 2011) mogą nie mieć cen w Tiingo, co pokaże raport pokrycia w `run` (REQ-554). Mogą też mieć ceny innej spółki, co pokaże dopiero audyt tickerów (#104, patrz wyżej).
- Oba pliki commitowane przed zamrożeniem `xsmom_v1` (X8): skład jest częścią pre-rejestracji.
- `quantlab run` na uniwersum point-in-time drukuje pokrycie cenami: udział dni członkostwa z ceną i członków bez żadnej ceny w źródle (REQ-554), a wśród nich osobno członków z listy `not_in_source`.

Przed pierwszym użyciem źródła: sprawdzić aktualne warunki na stronie dostawcy (ten dokument nie jest źródłem prawdy dla licencji — zmieniają się bez ostrzeżenia), zapisać datę weryfikacji w tej tabeli.

## Nowe źródło — checklista

1. Warunki użycia: nauka / publikacja, atrybucja, zakaz redystrybucji surowych danych.
2. Limity i wymagane nagłówki.
3. Wpis w tabeli powyżej (przez commit, z datą weryfikacji).
4. Klient w `core.data` z throttlingiem i cache.
5. Test bez sieci na nagranej odpowiedzi.

## Wykluczone

Źródła wymagające płatnej licencji na dane rynkowe (np. bezpośrednie feedy giełdowe) i płatne plany dostawców są poza zakresem: tylko darmowe źródła ([ADR-0009](adr/0009-private-repo-free-tiingo-plan.md)).

| Źródło | Powód |
|---|---|
| Stooq (`stooq.com/q/d/l/`) | endpoint CSV blokuje zapytania programistyczne (wyzwanie proof-of-work, potem „Access denied" nawet po jego przejściu) — zweryfikowane na żywo 2026-09-23, patrz [ADR-0007](adr/0007-binance-not-stooq-for-first-adapter.md). Wraca jako opcja, jeśli kiedyś potrzebne equities/FX (`q5`) i znajdzie się inny sposób dostępu. |
