# 0007. Binance zamiast Stooq jako pierwszy adapter danych

Status: Accepted

## Context

`docs/DATA-SOURCES.md` i `docs/specs/lab-foundation/` zakładały Stooq (bulk CSV, bez klucza) jako pierwsze źródło danych, pod koszyk ETF/FX. Przy implementacji F-2 (2026-09-23) weryfikacja na żywo pokazała, że `stooq.com/q/d/l/` wymaga rozwiązania klienckiego wyzwania proof-of-work (JavaScript, SHA-256) przed dostępem, a nawet po jego przejściu przez przeglądarkę sam endpoint CSV odpowiada „Access denied" dla zapytania programistycznego. Próba obejścia tej ochrony nie wchodziła w grę.

## Decision

- Pierwszy adapter danych (`DataProvider`) to `BinanceProvider`, korzystający z publicznego REST API (`api.binance.com/api/v3/klines`) — endpoint zaprojektowany pod dostęp programistyczny, bez klucza, bez ochrony antybotowej. Format zweryfikowany na żywo 2026-09-23: tablica świec `[open_time_ms, open, high, low, close, volume, close_time_ms, ...]` (stringi dla cen/wolumenu), błąd nieznanego symbolu to HTTP 400 z ciałem `{"code":-1121,"msg":"..."}`.
- Koszyk MVP (`q1-momentum-research-mvp`) zmienia się z ETF-ów/FX na pary kryptowalutowe notowane na Binance (np. względem USDT). Metodologia hipotezy (time-series momentum, Moskowitz/Ooi/Pedersen 2012) nie zależy od klasy aktywów.
- `Instrument.currency` (ISO 4217) zastąpione przez `Instrument.quote_asset` (dowolny ticker aktywa kwotowania, np. `USDT`) — krypto nie mieści się w ISO 4217.
- Stooq zostaje w `docs/DATA-SOURCES.md` jako źródło odrzucone, z powodem, na wypadek gdyby ktoś wrócił do pomysłu equities/FX w przyszłym rozszerzeniu (np. `q5-equities-cross-section` i tak potrzebuje innego, point-in-time źródła).

## Consequences

- Pozytywne: brak tarcia z ochroną antybotową; dane 24/7 bez przerw sesji giełdowych upraszcza pierwszy przebieg; brak corporate actions (splits/dywidendy) do obsłużenia w MVP.
- Negatywne: koszyk MVP nie reprezentuje już klasycznych instrumentów giełdowych — dla ról celujących w equities/futures trzeba to nazwać wprost w README/case study jako świadomy wybór, nie przeoczenie. Equities/FX jako osobne źródło danych wraca jako otwarty temat przy ewentualnym rozszerzeniu uniwersum (`q5`).

## Alternatives considered

- **Inne darmowe API dla ETF/FX** (Alpha Vantage, NBP) — więcej tarcia: klucz i limity darmowego tieru (Alpha Vantage), albo tylko dzienny kurs referencyjny bez OHLC (NBP) — niewystarczające dla silnika wymagającego pełnych świec.
- **Ręczne pobieranie CSV ze Stooq przez przeglądarkę** — odblokowałoby F-2 doraźnie, ale nie skaluje się i nie daje uczciwego `DataProvider` do testowania — odrzucone.
