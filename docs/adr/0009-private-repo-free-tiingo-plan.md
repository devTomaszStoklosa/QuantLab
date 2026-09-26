# 0009. Prywatne repozytorium i darmowy plan Tiingo jako źródło akcji i ETF-ów

Status: Accepted

## Context

Tomasz ustalił 2026-09-26, że wszystkie dane mają być darmowe. Wcześniejsze dokumenty dopuszczały „miesiąc płatnego tieru" Tiingo, żeby szybciej pobrać S&P 500 dla `xsmom_v1`. To było z tą zasadą niezgodne.

Źródło akcji i ETF-ów musi mieć:

- ceny dzienne z kilkunastu–kilkudziesięciu lat;
- dywidendy i splity, bo zwroty są całkowite;
- spółki zdjęte z obrotu, bo inaczej `xsmom_v1` ma przeżywalność (`q5`);
- oficjalne API, nie scraping.

Przegląd darmowych planów z 2026-09-26 opiera się na opisach planów w wynikach wyszukiwania. Strony dostawców są zablokowane w środowisku chmurowym, więc warunki trzeba potwierdzić przy zakładaniu konta.

| Źródło | Darmowy plan | Czego brakuje |
|---|---|---|
| **Tiingo, plan Starter** ($0) | 500 różnych tickerów miesięcznie, 50 zapytań na godzinę, 1 000 dziennie, ponad 30 lat historii dziennej, dywidendy i splity, spółki zdjęte z obrotu | licencja tylko na użytek własny: danych nie wolno pokazywać ani udostępniać innym |
| Alpha Vantage | 25 zapytań dziennie | dane skorygowane (`TIME_SERIES_DAILY_ADJUSTED`) opisane jako premium; S&P 500 to ok. 42 dni pobierania |
| EODHD | 20 zapytań dziennie | spółki zdjęte z obrotu i pełna historia w planach płatnych |
| Financial Modeling Prep | 250 zapytań dziennie | historia i zakres w darmowym planie ograniczone |
| Polygon (Massive) | kilka zapytań na minutę | ok. 1–2 lat historii |
| Yahoo Finance, Stooq | bez klucza | warunki użycia zabraniają dostępu programistycznego (Yahoo); blokada dostępu programistycznego (Stooq, [ADR-0007](0007-binance-not-stooq-for-first-adapter.md)) |

## Decision

- **Tylko darmowe źródła.** Binance (krypto, bez klucza) i plan Starter Tiingo (akcje i ETF-y, darmowy klucz). Żaden dokument nie proponuje płatnego planu.
- **Repozytorium jest prywatne.** Licencja darmowego Tiingo pozwala tylko na użytek własny. Surowe dane nadal nie trafiają do repozytorium (`data/cache/`, `results/` i `reports/` są ignorowane przez gita). Wyniki z cenami rynkowymi (rejestr transakcji, tear-sheet, aplikacja) zostają u badacza.
- **Adapter pilnuje limitu miesięcznego.** `TiingoProvider` liczy tickery, o które pytał w danym miesiącu. Przed 501. zatrzymuje przebieg komunikatem „rerun next month", zamiast trafić na błąd Tiingo w połowie pobierania. Miesiąc liczony jest według czasu Eastern, jak u Tiingo. Odpowiedzi z cache nie liczą się do limitu.
- **`xsmom_v1` pobiera się w trzech miesiącach kalendarzowych.** To ok. 1 050 tickerów przy 500 na miesiąc, z wznawianiem z cache. Hipotezy na ETF-ach (`q12`, 11 tickerów) mieszczą się w jednym dniu.

## Consequences

- Pozytywne:
  - zero kosztów danych;
  - jedno źródło akcji i ETF-ów, już zaimplementowane i przetestowane;
  - najdłuższa darmowa historia ze spółkami zdjętymi z obrotu;
  - licencja zgodna z użyciem.
- Negatywne:
  - dane dla `xsmom_v1` spływają trzy miesiące;
  - wyników z cenami nie można publikować. Portfolio pokazuje kod, metodologię i opisowe wnioski, a nie surowe notowania;
  - prywatne repozytorium na darmowym planie GitHuba ma limit minut GitHub Actions (minuty Windows liczone podwójnie).
- [ADR-0005](0005-descriptive-reports-no-investment-advice.md) nadal obowiązuje: raporty są opisowe, bez rekomendacji.

## Alternatives considered

- **Miesiąc płatnego planu Tiingo:** szybciej, ale łamie zasadę „wszystko darmowe".
- **Alpha Vantage albo EODHD za darmo:** za mało zapytań, a spółki zdjęte z obrotu i dane skorygowane są w planach płatnych.
- **Yahoo Finance przez `yfinance`:** darmowe i bez klucza, ale warunki użycia zabraniają dostępu programistycznego, biblioteka jest nieoficjalna i niestabilna, a spółek zdjętych z obrotu brak.
- **Publiczne repozytorium z darmowym Tiingo:** niezgodne z licencją, jeśli wyniki z cenami są w repozytorium albo publikowane.
