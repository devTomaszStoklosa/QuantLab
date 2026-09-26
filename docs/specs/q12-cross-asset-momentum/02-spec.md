# q12-cross-asset-momentum - Specification

Status: Ready for dev
Owner role: BA
Upstream: 01-story.md

## Glossary

| Term | Meaning |
|---|---|
| Sesja | dzień, w którym rynek uniwersum notuje: bar dzienny. Krypto: każdy dzień kalendarzowy; ETF-y w USD: dni sesji NYSE |
| Rozgrzewka | historia potrzebna przed pierwszym dniem okna, żeby sygnał istniał od tego dnia; definicja podaje ją w dniach kalendarzowych |
| Instrument gotówkowy | ETF na krótkoterminowe bony skarbowe, którego skorygowany zwrot całkowity (z dywidendami) jest stopą gotówki uniwersum; nie jest członkiem uniwersum ani nie jest handlowany |
| Zwrot ponad gotówkę | (1 + r) / (1 + r_gotówki) − 1 w danym okresie; w przybliżeniu r − r_gotówki |
| Klasa aktywów | `crypto`, `equity`, `bond`, `commodity`, `currency`, `real_estate`, `cash` |

## Actors and permissions

| Actor | Action | Allowed |
|---|---|---|
| Badacz | ustala koszyk, instrument gotówkowy i klasy aktywów w pliku uniwersum przed pierwszym przebiegiem | tak |
| `quantlab run` | handluje instrumentem gotówkowym | nie |
| `quantlab run` | zmienia ceny barów uniwersum bez instrumentu gotówkowego | nie |

## Functional requirements (EARS)

Rozgrzewka w sesjach

- REQ-1201 (AC-1): A universe shall convert a number of sessions n to calendar days that hold at least n of its sessions:
  - on a market that trades every calendar day (`periods_per_year` ≥ 365): exactly n days;
  - otherwise ⌈1.5 · n⌉ + 10 days: 7/5 for weekends, the rest for exchange holidays and unscheduled closures.
- REQ-1202 (AC-1): A definition shall give its warm-up in bars of its longest window. The runner shall move the fetch start and every first common day back by the universe's calendar days for that many sessions. This applies to time-series momentum, short-term reversal, pairs, momentum with a selected lookback and momentum scaled by volatility. A definition whose windows are calendar months (cross-sectional momentum) shall give its calendar days itself, as today.
- REQ-1203 (AC-1): The warm-up shall be the only thing that changes. Signals, estimators, cost models and regimes keep counting bars.

Gotówka i zwroty ponad nią

- REQ-1210 (AC-2): A universe may name a cash instrument outside its instruments list. It shall never be a member, a signal's instrument or traded. Its id shall differ from every instrument's, and its asset class shall be `cash`.
- REQ-1211 (AC-2): When the universe names a cash instrument, the run shall fetch it from the universe's source over the same range as the other instruments and adjust it for its corporate actions (distributions). Its closes are then a total-return index C.
- REQ-1212 (AC-2): Each instrument's bar dated d, the market proxy's included, shall have its open, high, low and close multiplied by C_last / C(d):
  - C(d) is the cash close of the latest cash bar dated ≤ d;
  - C_last is the last cash close of the fetched range.

  The series thus ends at the market's quote, and its period returns are returns above cash. Volume and the raw close for price-level rules (`unadjusted_close`) shall stay unchanged.
- REQ-1213 (AC-2): A bar dated before the cash instrument's first bar shall be dropped: no return above cash is known for it.
- REQ-1214 (AC-2): The run shall say in the terminal that its returns are above the cash instrument, naming it.
- REQ-1215 (AC-2): Without a cash instrument the bars shall be exactly those of today.

Klasy aktywów i podział P&L

- REQ-1220 (AC-3): An instrument's asset class shall be one of the glossary's classes.
- REQ-1221 (AC-3): The trade ledger shall group net P&L by the asset class of the trade's instrument and by instrument. Each cut shall give the same statistics as the regime and holding-period cuts.
- REQ-1222 (AC-3): The terminal shall print both cuts. With more than 20 instruments, the instrument cut shows the 10 groups with the highest and the 10 with the lowest total net P&L, and says so.
- REQ-1223 (AC-3): The results store and the app shall carry every group of both cuts as new values of the P&L dimension, without a schema change.

Uniwersum ETF

- REQ-1230 (AC-4): The ETF universe file shall:
  - name the source `tiingo` and `periods_per_year: 252`;
  - name the market proxy and the cash instrument;
  - give each instrument's asset class;
  - have no memberships (static).
- REQ-1231 (AC-4): `quantlab plan` shall treat a hypothesis on it like any other on a Tiingo universe: its runs wait for the source check.

Walidacja i wynik

- REQ-1240 (AC-5): A hypothesis on the ETF universe shall go through the lab's pipeline unchanged:
  - three cost models and the walk-forward gate;
  - the permutation test;
  - PSR and DSR with every trial on this universe and overlapping training;
  - regimes, stress test and trade ledger;
  - a frozen holdout opened once;
  - engine parity below 1e-9.
- REQ-1241 (AC-6): The research-log entry shall describe the P&L per asset class as descriptive, without a significance claim per class or per instrument.

Kompatybilność

- REQ-1250: The epic shall not change any frozen hypothesis's definitions, results or verdicts: the regression dump stays byte for byte. The new ledger cuts are descriptive additions to their output.

## Business rules

- Ta sama reguła co `momentum_v1` („znak zwrotu z 12 miesięcy, równe wagi po znaku, rebalans dzienny"). Na koszyku ETF liczy się ją w sesjach (252) i na zwrotach ponad gotówkę. To definicja Moskowitza, Ooi i Pedersena, nie zmiana reguły.
- Krótka pozycja zarabia minus nadwyżkę instrumentu ponad gotówkę: wpływy z krótkiej sprzedaży są oprocentowane stopą gotówki, bez kosztu pożyczki ETF. To ograniczenie jest opisane przy wyniku.
- Klasy aktywów służą tylko opisowi. Żadna strategia ani sizer nie rozgałęzia się po klasie.
- Ceny w rejestrze transakcji uniwersum z gotówką są cenami po odjęciu gotówki. Ich zmiany to zwroty ponad gotówkę, a poziomy nie są notowaniami.

## Data and validation

Plik uniwersum (`src/quantlab/config/universes/<name>.yaml`):

| Field | Type | Validation |
|---|---|---|
| `instruments[].asset_class` | enum | jedna z klas słownika |
| `cash` | Instrument albo brak | id spoza `instruments`; klasa `cash` |
| `periods_per_year` | int | > 0; ≥ 365 oznacza rynek bez dni wolnych |

## Edge and error cases

- Brak baru gotówki na dzień instrumentu (różnica kalendarzy, opóźnienie danych): użyty ostatni wcześniejszy kurs gotówki, więc tego dnia gotówka ma zerowy zwrot.
- Źródło nie zna instrumentu gotówkowego (brak barów): przebieg kończy się błędem przed backtestem. Bez gotówki nie ma zwrotów ponad nią, a cicha zamiana na zwroty całkowite zmieniłaby hipotezę.
- Instrument notowany krócej niż rozgrzewka: brak sygnału do czasu, gdy historii wystarczy, jak dziś.
- Mniej niż 21 instrumentów: podział per instrument w terminalu pokazuje wszystkie grupy.

## Non-functional requirements

- Testy bez sieci, na danych syntetycznych ze znanym wynikiem: instrument rosnący jak gotówka ma zerowy zwrot; rozgrzewka 252 sesji na kalendarzu z weekendami i świętami daje sygnał od pierwszego dnia.
- Konwersja sesji na dni i przeliczenie barów przez gotówkę są liniowe względem liczby barów.

## Traceability

| AC | REQ |
|---|---|
| AC-1 | REQ-1201, REQ-1202, REQ-1203 |
| AC-2 | REQ-1210, REQ-1211, REQ-1212, REQ-1213, REQ-1214, REQ-1215 |
| AC-3 | REQ-1220, REQ-1221, REQ-1222, REQ-1223 |
| AC-4 | REQ-1230, REQ-1231 |
| AC-5 | REQ-1240 |
| AC-6 | REQ-1241 |
| Guardrail | REQ-1250 |

## Open questions

| # | Question | Owner |
|---|---|---|
| 1–7 | Pytania pre-rejestracji z [01-story](01-story.md) (koszyk, hipotezy, lookback, skalowanie, koszty, okresy, kryterium) | Tomasz, przed C5 |
