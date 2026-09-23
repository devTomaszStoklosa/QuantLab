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
