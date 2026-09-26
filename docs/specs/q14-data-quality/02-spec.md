# q14-data-quality - Specification

Status: Ready for dev
Owner role: BA
Upstream: 01-story.md

## Glossary

| Term | Meaning |
|---|---|
| Ustalenie | jedna wada albo podejrzane miejsce: kontrola, instrument, data, opis |
| Błąd | ustalenie, które unieważnia obliczenia; zatrzymuje przebieg |
| Ostrzeżenie | ustalenie do obejrzenia; raportowane, nie zatrzymuje |
| Sesje referencyjne | dni, w które rynek uniwersum notuje: każdy dzień kalendarzowy na rynku notowanym codziennie, inaczej suma dat barów wszystkich instrumentów |

## Functional requirements (EARS)

Kontrole

- REQ-1401 (AC-1): The lab shall check the bars a run uses, after corporate-action and cash adjustments, with these checks:

  | Kontrola | Poziom | Reguła |
  |---|---|---|
  | `duplicate dates` | błąd | two bars of an instrument on one date |
  | `non-positive prices` | błąd | open, high, low or close ≤ 0 on a bar that is not a delisting bar |
  | `inconsistent OHLC` | ostrzeżenie | high < max(open, close, low) or low > min(open, close, high), beyond a relative tolerance of 1e-9 |
  | `missing sessions` | ostrzeżenie | a reference session between the instrument's first and last bar with no bar |
  | `stale closes` | ostrzeżenie | the same close on 5 or more consecutive bars; one finding per run of them, dated at its start |
  | `extreme moves` | ostrzeżenie | a close-to-close return more than 10 robust standard deviations (1.4826 × median absolute deviation) from the instrument's median return, with at least 20 returns |

- REQ-1402 (AC-5): Reference sessions shall be every calendar day of the checked range on a market that trades every day (`periods_per_year` ≥ 365), and otherwise the union of the dates of all fetched instruments, the market proxy included.
- REQ-1403: Each check shall be an implementation of a `DataCheck` interface with its name and level. The report shall run a list of them and never branch on a check's type.
- REQ-1404: The checks shall only read bars; no bar is changed, dropped or added.

Przebieg i holdout

- REQ-1410 (AC-2): `quantlab run` shall check the training data (with the warm-up) before any backtest. With an error, it shall exit with code 1, listing up to 10 errors and naming `quantlab check-data <hipoteza>`.
- REQ-1411 (AC-2): Opening a holdout shall check the holdout data before computing anything. With an error, it shall stop without writing a record and without printing any result.
- REQ-1412 (AC-3): Without errors, `quantlab run` shall report:
  - the number of instruments and bars checked;
  - the count of findings per check;
  - up to 10 warnings with their dates.

  The same counts shall be a training diagnostic titled "Data quality", so the tear-sheet, the results store and the app show them without a schema change.

Komenda

- REQ-1420 (AC-4): `quantlab check-data <hipoteza>` shall fetch the training range with its warm-up (from the cache when present) and print every finding grouped by check. It shall exit with 1 when there is an error and 0 otherwise. It shall never read the holdout range.

Kompatybilność

- REQ-1430: On data without errors, results and verdicts of every hypothesis shall not change: the regression dump stays byte for byte. The new diagnostic rows are descriptive additions.

## Business rules

- Kontrola nie naprawia danych. Wada krytyczna to informacja dla badacza, który poprawia adapter albo źródło, a nie hipotezę.
- Progi (5 sesji, 10 odchyleń odpornych, tolerancja OHLC) są metodologią laboratorium, stałą dla wszystkich hipotez, jak liczba permutacji.
- Skrajne ruchy są często prawdziwe (krachy, dni wyborów). Raport podaje daty do obejrzenia, a nie wyrok.

## Edge and error cases

- Instrument bez barów: brak ustaleń; brak cen raportuje pokrycie (`q5`) albo strategia (brak sygnału).
- Mniej niż 20 zwrotów: bez kontroli skrajnych ruchów dla instrumentu.
- Mediana odchyleń równa zero (stała cena): bez kontroli skrajnych ruchów; zamrożone ceny zgłasza `stale closes`.
- Bar delistingu: pominięty w kontroli cen ≤ 0 i OHLC (wartość delistingu może wynosić 0).

## Non-functional requirements

- Kontrola jest liniowa względem liczby barów. S&P 500 z tysiącem tickerów i piętnastoma latami to kilka sekund.
- Testy bez sieci, na danych syntetycznych z wadami wstawionymi w znane daty.

## Traceability

| AC | REQ |
|---|---|
| AC-1 | REQ-1401, REQ-1403, REQ-1404 |
| AC-2 | REQ-1410, REQ-1411 |
| AC-3 | REQ-1412 |
| AC-4 | REQ-1420 |
| AC-5 | REQ-1402 |
| Guardrail | REQ-1430 |

## Open questions

| # | Question | Owner |
|---|---|---|
| — | Brak | — |
