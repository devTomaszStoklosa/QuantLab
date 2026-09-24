# Źródła danych

## Zasady

1. **Repo publiczne od początku** — inaczej niż lokalne `data/private/` w projektach z prawdziwymi eksportami brokerów: żadne surowe dane cenowe nie trafiają do repozytorium bez sprawdzonej licencji na redystrybucję, nawet do celów edukacyjnych.
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
| Tiingo (`api.tiingo.com`) | ceny dzienne surowe i skorygowane, dywidendy (`divCash`) i splity (`splitFactor`) w dniu ex-date, metadane z ostatnim dniem notowań (także spółki zdjęte z obrotu); bez zwrotu z delistingu i bez jego przyczyny | tak (darmowy), zmienna `TIINGO_API_KEY` | darmowy tier: limit unikalnych symboli miesięcznie oraz zapytań na godzinę i dzień — przy ok. 1 050 tickerach S&P 500 z lat 2004–2025 pobieranie rozłożone na kilka dni albo miesiąc płatnego tieru | **wybrane**; bez redystrybucji surowych danych (cache i magazyn wyników poza repo); warunki niezweryfikowane |
| Alpha Vantage | lista spółek zdjętych z obrotu; skorygowane dane dzienne w tierze płatnym | tak | 25 zapytań dziennie w darmowym tierze | za wolne na setki spółek |
| Nasdaq Data Link (Sharadar) | pełne delistingi, akcje korporacyjne, point-in-time | tak (płatne) | koszt | poza budżetem projektu portfolio |
| Wikipedia — *List of S&P 500 companies* | bieżący skład i tabela zmian składu, z których odtwarzamy skład wstecz | nie (API MediaWiki, nagłówek `User-Agent`) | CC BY-SA 4.0: plik uniwersum w repo z atrybucją i numerem rewizji; kompletność przed ok. 2000 r. niepewna | **wybrane**; tylko członkostwo, bez cen |
| Yahoo Finance | ceny | nie | warunki użycia zabraniają dostępu programistycznego; brak spółek zdjętych z obrotu | odrzucone |

#### Tiingo lokalnie (`core.data.tiingo.TiingoProvider`, `q5`-X7c)

- Klucz: zmienna środowiskowa `TIINGO_API_KEY`. Bez niej `quantlab run` kończy się przed pobraniem danych.
- Odstęp żądań: domyślnie 90 s (mieści się w limitach darmowego tieru znanych przy pisaniu: ok. 50 zapytań na godzinę i 1 000 dziennie); płatny tier może go skrócić zmienną `TIINGO_REQUEST_INTERVAL_SECONDS`.
- Każdy ticker to dwa zapytania (ceny w zakresie przebiegu, metadane z ostatnim dniem notowań); odpowiedzi trafiają do `data/cache/`, więc przerwane pobieranie wznawia się od miejsca przerwania, a limit zapytań kończy komendę jednym komunikatem, nie wyjątkiem.
- Skala dla `xsmom_v1` (szacunek): trening ok. 875 tickerów członków S&P 500 z lat 2005–2019 plus SPY — ok. 1 750 zapytań, przy 90 s ok. 44 h; holdout ok. 650 tickerów — same ceny, ok. 16 h. Łącznie ok. 1 050 unikalnych tickerów, ponad limit ok. 500 unikalnych symboli miesięcznie w darmowym tierze: pobieranie rozłożone na 2–3 miesiące albo jeden miesiąc płatnego tieru.
- Test bez sieci: odpowiedź w udokumentowanym formacie Tiingo z syntetycznymi liczbami (`tests/core/data/test_tiingo.py`) — środowisko chmurowe nie ma dostępu do API, więc to nie jest nagranie na żywo. Przy pierwszym lokalnym pobraniu warto porównać format z prawdziwą odpowiedzią (pola `date`, `open`, `high`, `low`, `close`, `volume`, `adjClose`, `divCash`, `splitFactor`; metadane `endDate`).

#### Skład S&P 500 lokalnie (`core.sp500`, `quantlab build-universe`, `q5`-X7d)

- Komenda czyta ostatnią rewizję strony *List of S&P 500 companies* sprzed 2026-09-24T00:00Z (API MediaWiki, bez klucza), odtwarza skład wstecz do 2000-01-01 i zapisuje `src/quantlab/config/universes/sp500.yaml` z numerem rewizji i atrybucją CC BY-SA 4.0 w nagłówku (plik jest adaptacją treści Wikipedii i dzieli jej licencję).
- Raport budowy wymienia sprzeczności tabeli zmian; zmiany tickerów (np. `FB` → `META`) trafiają do `sp500-renames.yaml`, po czym budowę się powtarza. Ticker użyty ponownie przez inną spółkę nie jest mapowany — raport pokazuje go jako ticker z kilkoma okresami.
- Oba pliki commitowane przed zamrożeniem `xsmom_v1` (X8): skład jest częścią pre-rejestracji.
- `quantlab run` na uniwersum point-in-time drukuje pokrycie cenami: udział dni członkostwa z ceną i członków bez żadnej ceny w źródle (REQ-554).

Przed pierwszym użyciem źródła: sprawdzić aktualne warunki na stronie dostawcy (ten dokument nie jest źródłem prawdy dla licencji — zmieniają się bez ostrzeżenia), zapisać datę weryfikacji w tej tabeli.

## Nowe źródło — checklista

1. Warunki użycia: nauka / publikacja, atrybucja, zakaz redystrybucji surowych danych.
2. Limity i wymagane nagłówki.
3. Wpis w tabeli powyżej (przez commit, z datą weryfikacji).
4. Klient w `core.data` z throttlingiem i cache.
5. Test bez sieci na nagranej odpowiedzi.

## Wykluczone

Źródła wymagające płatnej licencji na dane rynkowe (np. bezpośrednie feedy giełdowe) — poza zakresem projektu portfolio.

| Źródło | Powód |
|---|---|
| Stooq (`stooq.com/q/d/l/`) | endpoint CSV blokuje zapytania programistyczne (wyzwanie proof-of-work, potem „Access denied" nawet po jego przejściu) — zweryfikowane na żywo 2026-09-23, patrz [ADR-0007](adr/0007-binance-not-stooq-for-first-adapter.md). Wraca jako opcja, jeśli kiedyś potrzebne equities/FX (`q5`) i znajdzie się inny sposób dostępu. |
