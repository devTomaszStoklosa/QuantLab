# q12-cross-asset-momentum - Design

Status: Ready for dev
Owner role: Architect
Upstream: 02-spec.md
ADRs: docs/adr/0002-dual-backtest-engine.md, docs/adr/0004-validation-first-frozen-holdout.md, docs/adr/0008-results-store-parquet-duckdb.md

## Context and constraints

- **Dwie jednostki czasu.** Strategie, estymatory, model kosztów i reżimy liczą bary (`trailing_return`, `trailing_returns`, okna `vol_window`). Rozgrzewka definicji (`warm_up_days`) jest odejmowana od dat jako dni kalendarzowe:
  - `fetch_start` wyznacza początek pobierania;
  - `common_start` wyznacza pierwszy wspólny dzień raportów i wyborów `q8`.
- **Łańcuch danych.** `_fetch_market_data` pobiera bary i zdarzenia każdego instrumentu okna, a `with_events` koryguje je o akcje korporacyjne i kończy delistingiem. Wszystko dalej (strategie, oba silniki, testy istotności, rejestr) czyta tylko te bary.
- **Silniki.** Zwrot portfela to suma wag razy zwroty instrumentów. Gotówka nie jest oprocentowana, a Sharpe liczy się bez stopy wolnej od ryzyka.
- **Rejestr transakcji.** `group_pnl(trades, key)` dzieli P&L po dowolnym kluczu; CLI buduje wymiary `regime` i `holding_period`. Magazyn zapisuje je w tabeli `pnl_groups` (`dimension`, `key`, …), API przekazuje je bez interpretacji, a aplikacja rysuje tabelę na każdy znany wymiar.
- **Zgodność wsteczna.** Zamrożone definicje krypto i ich wyniki nie mogą się zmienić (zrzut bajt w bajt).

## Quality attribute scenarios

| Source | Stimulus | Response | Measure |
|---|---|---|---|
| Badacz | lookback 252 sesji na kalendarzu z weekendami i świętami | sygnał od pierwszego dnia okna | test na syntetycznym kalendarzu NYSE-podobnym |
| Deweloper | uniwersum krypto | ta sama rozgrzewka co dziś | test tożsamości; zrzut regresji bajt w bajt |
| Badacz | instrument rosnący jak gotówka | zwrot ponad gotówkę 0, sygnał płaski | test na danych syntetycznych |
| Badacz | pozycja długa i krótka na uniwersum z gotówką | zwrot ± (r − r_gotówki)/(1 + r_gotówki) | test obu silników |
| Deweloper | nowe wymiary P&L | magazyn, API i aplikacja bez zmiany schematu | testy magazynu, API (.NET) i aplikacji |

## Options

### Decyzja 1 — rozgrzewka w sesjach

- **A. Uniwersum przelicza sesje na dni (`Universe.calendar_days`). Definicja podaje rozgrzewkę w barach, a runner przelicza ją uniwersum, które już trzyma (`warm_up_calendar_days(universe)`, `fetch_start(start, universe)`).** Na rynku z 365 sesjami to tożsamość, więc krypto się nie zmienia. Na rynku z weekendami ⌈1.5·n⌉ + 10 dni daje górne ograniczenie. Nadmiar historii nie szkodzi: strategie czytają dokładnie tyle barów, ile potrzebują.
- B. Pobieranie całej dostępnej historii od początku źródła. Zmienia pobieranie krypto i `common_start` wyborów `q8`, co grozi zmianą zamrożonych wyników, a w Tiingo mnoży zapytania.
- C. Kalendarz giełdy z biblioteki (`exchange_calendars`). Dokładny, ale to nowa zależność tylko po to, by znać górne ograniczenie, a ADR-0001 każe testować import każdej zależności natywnej.

### Decyzja 2 — zwroty ponad gotówkę

- **A. Przeliczenie barów przez indeks gotówki w warstwie danych.** Ceny każdego instrumentu dzielone przez skumulowany zwrot gotówki. Silniki, sizery, testy istotności i rejestr zostają bez zmian; parytet wynika z konstrukcji. Sharpe i każda statystyka liczą się na nadwyżce, a sygnał momentum to znak nadwyżki (MOP 2012).
- B. Noga gotówkowa w obu silnikach: oprocentowanie wolnej gotówki i wpływów z krótkiej sprzedaży, Sharpe z odjętą stopą. Zmienia oba silniki, protokół wyniku i wszystkie testy istotności, a sygnał dalej widziałby zwrot całkowity.
- C. Bez gotówki, jako ograniczenie opisane w dzienniku. Na ETF-ach z lat 2008–2026 zawyża Sharpe strategii z przewagą pozycji długich, a sygnał nie jest tym z literatury.

### Decyzja 3 — źródło stopy gotówki

- **A. ETF na bony 1–3-miesięczne (BIL) z Tiingo.** To samo źródło, licencja i korekty o dywidendy co reszta koszyka, a zwrot całkowity bez przeliczania rentowności. Minus: opłata za zarządzanie (ok. 0.14% rocznie) zaniża stopę gotówki, więc nadwyżka długich pozycji jest odrobinę zawyżona. Notowania od 2007-05.
- B. Rentowność bonów 3-miesięcznych z FRED (DTB3). Dłuższa historia, ale nowy adapter, przeliczanie rentowności na dzienny zwrot i osobna licencja.
- C. Stała stopa — nieprawdziwa w okresie 0–5%.

### Decyzja 4 — widok „skąd wynik"

- **A. Nowe klucze rejestru transakcji: klasa aktywów i instrument.** Istniejący mechanizm (`group_pnl`), tabela `pnl_groups` i panel aplikacji dostają dwa wymiary, bez zmiany schematu. Działa dla każdej hipotezy, także krypto (BTC vs ETH).
- B. Diagnostyka treningu per klasa (Sharpe „rękawów") tylko w nowych definicjach. Nie ma jej na holdoucie ani w starszych hipotezach, a rękawy liczy się po raz drugi obok silnika.
- C. Osobne hipotezy per klasa aktywów. Mnożą próby w DSR i odpowiadają na inne pytanie.

### Decyzja 5 — koszyk

- **A. Statyczny koszyk szerokich ETF-ów, 1–3 na klasę, notowanych od ≤ 2007.** Plik uniwersum zamrożony jak definicja, przed pierwszym przebiegiem.
- B. Kilkadziesiąt ETF-ów, w tym sektorowe. Silnie skorelowane w klasie, a przy darmowym Tiingo wielokrotnie więcej zapytań.
- C. Futures — poza zakresem (rolowanie, mnożniki, źródło).

## Trade-off matrix (1-5)

| Criterion | 1A | 1B | 1C | 2A | 2B | 2C | 3A | 3B | 4A | 4B |
|---|---|---|---|---|---|---|---|---|---|---|
| Zgodność wsteczna (bit w bit) | 5 | 2 | 5 | 5 | 3 | 5 | — | — | 5 | 5 |
| Parytet silników | — | — | — | 5 | 3 | 5 | — | — | — | — |
| Wierność metodologii (MOP, Sharpe na nadwyżce) | 4 | 4 | 5 | 5 | 4 | 1 | 4 | 5 | — | — |
| Podstawialność, brak `if` po typie | 5 | 5 | 5 | 5 | 4 | 5 | 5 | 4 | 5 | 4 |
| Złożoność | 5 | 4 | 3 | 4 | 2 | 5 | 5 | 3 | 5 | 3 |

## Decision

Recommended: **1A, 2A, 3A, 4A, 5A.**

- Uniwersum przelicza sesje na dni, a definicje liczące bary podają rozgrzewkę przez nie.
- Warstwa danych przelicza bary przez indeks gotówki z ETF-u na bony, pobranego z tego samego źródła.
- Rejestr transakcji dzieli P&L także po klasie aktywów i instrumencie.
- Koszyk to statyczny plik uniwersum zamrożony przed pierwszym przebiegiem.

Revisit if: pojawi się hipoteza wymagająca kosztu pożyczki przy krótkiej sprzedaży albo finansowania dźwigni (wtedy 2B z kosztem ponad stopę gotówki) albo potrzeba dokładnego kalendarza (1C).

## Diagrams

```
universe (source, periods_per_year, market_proxy, cash, instruments[asset_class])
   │
definition.warm_up_days (bars) -> warm_up_calendar_days(universe)      # 365/yr: identity
   │ fetch_start
   ▼
_fetch_market_data:
   bars, events (instruments of the window)        ─┐
   with_events -> adjusted, delisted                │
   cash: fetch + events -> adjust_bars -> index C   │
   above_cash(bars, C): price × C_last / C(d)  <────┘   # no cash: bars unchanged
   ▼
strategies / sizers / engines / tests / ledger  (unchanged)
   ▼
ledger cuts: regime, holding_period, asset_class, instrument  ->  terminal, pnl_groups, app
```

## Contracts

```python
# core/universe.py
AssetClass = Literal["crypto", "equity", "bond", "commodity", "currency", "real_estate", "cash"]
class Instrument(BaseModel): asset_class: AssetClass
class Universe(BaseModel):
    cash: Instrument | None = None          # never a member, never traded
    def calendar_days(self, sessions: int) -> int: ...

# core/data/cash.py
def above_cash(bars: dict[str, list[PriceBar]], cash: list[PriceBar]) -> dict[str, list[PriceBar]]: ...

# research/definition.py
class StudyParametersBase:
    warm_up_days: int                                        # bars of the longest window
    def warm_up_calendar_days(self, universe: Universe) -> int  # universe.calendar_days(warm_up_days)
    def fetch_start(self, start: date, universe: Universe) -> date
class CrossSectionalMomentumParameters:  # months: warm_up_calendar_days = warm_up_days

# attribution/trade_ledger.py
def by_instrument(trade: Trade) -> str
def by_asset_class(universe: Universe) -> Callable[[Trade], str]
```

Pliki:

- `src/quantlab/core/universe.py`, `src/quantlab/core/data/cash.py` (nowy), `src/quantlab/cli.py`, `src/quantlab/research/definition.py`, `src/quantlab/attribution/trade_ledger.py`;
- `presentation/web/src/api.ts`, `presentation/web/src/screens/evidence.tsx` (dwa wymiary P&L); API .NET bez zmian (wymiar jest tekstem);
- `src/quantlab/config/universes/multiasset-etf.yaml` (C5, po pytaniach pre-rejestracji);
- testy: `tests/core/test_universe.py`, `tests/core/data/test_cash.py`, `tests/research/test_warm_up_sessions.py`, `tests/attribution/test_trade_ledger.py`, `tests/test_multiasset_run.py`.

## Rollout and rollback

1. **C1** dokumentacja: 01-story, 02-spec, 03-design, ROADMAP.
2. **C2** rozgrzewka w sesjach (`Universe.calendar_days`, definicje liczące bary) i klasy aktywów; test tożsamości dla krypto; zrzut regresji bez zmian.
3. **C3** instrument gotówkowy i zwroty ponad gotówkę w warstwie danych; testy znanego wyniku i parytetu.
4. **C4** podział P&L per klasa aktywów i instrument: terminal, magazyn, aplikacja.
5. **C5** plik uniwersum ETF i zamrożenie hipotez po odpowiedziach na pytania 1–7; dokumentacja (README, INSTRUKCJA, DATA-SOURCES, ARCHITECTURE). Potem przebiegi lokalne (Tiingo), holdouty i wpis w dzienniku.

Rollback: `git revert` per slice. C2–C4 nie zmieniają wyników zamrożonych hipotez. C5 dodaje definicje: po commicie zostają próbami w rejestrze, zgodnie z `q6`.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Rozgrzewka krypto zmieniona po cichu | niska | wysoki | tożsamość dla ≥ 365 sesji; test; zrzut regresji |
| Za krótka rozgrzewka w latach z mniejszą liczbą sesji | niska | średni | ⌈1.5·n⌉ + 10 dni: zapas ok. 7% ponad weekendy (święta, zamknięcia) plus 10 dni |
| Brak baru gotówki na dzień instrumentu | średnia | niski | ostatni wcześniejszy kurs (zerowy zwrot gotówki tego dnia) |
| Ceny w rejestrze po odjęciu gotówki mylone z notowaniami | średnia | niski | komunikat w terminalu, opis w rejestrze i dzienniku |
| Setki wierszy podziału per instrument na S&P 500 | pewna | niski | terminal: 10 najlepszych i 10 najgorszych; magazyn i aplikacja: wszystkie |

## Handoff notes

- Pytania 1–7 z [01-story](01-story.md) blokują tylko C5. C2–C4 powstają na danych syntetycznych.
- Po C4 przebiegi hipotez krypto pokażą dwa nowe podziały P&L. Ich wyniki i werdykty się nie zmieniają, a `quantlab plan` nie oznacza ich przez to jako nieaktualnych.
