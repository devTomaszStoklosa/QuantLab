# q2-event-driven-engine - Specification

Status: Ready for dev
Owner role: BA
Upstream: 01-story.md

## Glossary

| Term | Meaning |
|---|---|
| Zdarzenie | jednostka pracy silnika: otwarcie rynku w dniu t, zamknięcie rynku w dniu t, zlecenie, wypełnienie |
| Chwila decyzji | zamknięcie dnia t, na którym strategia liczy sygnał i silnik tworzy zlecenia |
| Kapitał decyzji | wartość portfela (w walucie) na zamknięciu dnia decyzji; od niej liczone są ilości w zleceniach |
| Zlecenie | polecenie zmiany ilości instrumentu, z ilością ustaloną w chwili decyzji |
| Wypełnienie | wykonanie (całości lub części) zlecenia po cenie konkretnego baru |
| Tryb egzekucji | reguła, po jakiej cenie wypełnia się zlecenie: zamknięcie t, otwarcie t+1 albo zamknięcie t+1 |
| Limit udziału w wolumenie | maksymalny ułamek wolumenu baru wypełnienia, jaki może zająć jedno zlecenie |
| Kapitał graniczny (pojemność) | najmniejszy kapitał nominalny, przy którym jakieś zlecenie przebiegu bez limitu przekroczyłoby limit udziału |
| Parytet | zgodność przebiegów obu silników przy tych samych założeniach egzekucji |

Terminy z `q1` (`BacktestRun`, `PortfolioSnapshot`, `Strategy`, `CostModel`, obrót) bez zmian — patrz [q1 02-spec](../q1-momentum-research-mvp/02-spec.md) i [q3 02-spec](../q3-mean-reversion-hypothesis/02-spec.md).

## Actors and permissions

| Actor | Action | Allowed |
|---|---|---|
| Strategia | czyta bary z datą późniejszą niż dzień sygnału | nie (REQ-210) |
| Silnik event-driven | wypełnia zlecenie po cenie z baru sprzed chwili decyzji | nie (REQ-212) |
| Porównanie silników | czyta dane z zakresu holdoutu, zmienia status hipotezy, zapisuje otwarcie holdoutu | nie (REQ-253) |
| Porównanie silników | uruchamia hipotezę bez zacommitowanej definicji | nie (REQ-253) |

## Functional requirements (EARS)

Kontrakt

- REQ-201 (AC-6): `BacktestRun` and `PortfolioSnapshot` shall be defined in a module shared by both engines, and metrics, validators, risk, attribution and reporting shall import them from there rather than from either engine.
- REQ-202 (AC-1, AC-6): The event-driven engine shall return a `BacktestRun` whose snapshots follow the snapshot semantics in Business rules.
- REQ-203 (AC-1): Both engines shall size positions with one shared implementation of the weighting rule (equal weight by signal sign among active instruments).

Zdarzenia i brak look-ahead

- REQ-210 (AC-2): When the engine requests signals for date t, it shall pass the strategy only bars with `ts <= t`.
- REQ-211: For each trading date the engine shall process, in this order: fills of orders due at the open; mark-to-market and snapshot at the close; fills of orders due at the close; signals and new orders.
- REQ-212: An order created at the close of t shall never be filled at a price from a bar dated before t, nor at the close of t unless the execution mode is close execution.

Egzekucja

- REQ-220 (AC-1): In close execution mode, an order created at the close of t shall be filled at the close of t.
- REQ-221 (AC-3): In next-bar mode, an order created at the close of t shall be filled at the open (next-open) or the close (next-close) of the instrument's bar on the next trading date of the run; if the instrument has no bar on that date, the order shall be cancelled.
- REQ-222: The order quantity shall be fixed when the order is created: target weight × decision equity / instrument close at t, minus the quantity held.
- REQ-223: Execution mode and fill policy shall be substitutable implementations of `ExecutionModel` and `FillPolicy` chosen by the caller, and the engine shall not branch on their type.

Wypełnienia

- REQ-230 (AC-4): With a volume participation limit p, an order shall fill at most p × the volume of its fill bar, in instrument units, and the remainder shall be cancelled.
- REQ-231 (AC-4): The engine shall record every order with its decision date, ordered quantity, filled quantity, fill date, fill price and cost.
- REQ-232 (AC-4): The capacity estimate shall be the smallest nominal capital at which any order of the run without the limit (full fills, same execution mode) would exceed p × the volume of its fill bar.

Koszty

- REQ-240 (AC-1): The engine shall charge costs through the same `CostModel` as the vectorized engine, called with the order's decision date as `as_of` and the filled weight (|filled quantity| × fill price / decision equity); the cost in currency is the returned fraction times the decision equity.

Porównanie

- REQ-250 (AC-5): `quantlab compare-engines [HYPOTHESIS]` shall run the hypothesis's committed definition on its training range with its cost model in five configurations — vectorized; event-driven close; event-driven next-open; event-driven next-close; event-driven next-open with the participation limit at the nominal capital — and print for each CAGR, Sharpe, max drawdown, annualized turnover, total costs and the number of orders limited by volume.
- REQ-251 (AC-1): The comparison shall print the largest absolute difference in normalized equity between the vectorized run and the event-driven close run.
- REQ-252 (AC-4): The comparison shall print the capacity estimate of the next-open mode.
- REQ-253 (AC-5): When the hypothesis definition is missing, uncommitted or has uncommitted changes, the comparison shall refuse before fetching any data (as REQ-303); it shall fetch no bar dated after the training end, write no holdout record and change no hypothesis status.

Dziennik

- REQ-260: The research log shall record the comparison for `momentum_v1` as a supplement to its entry, stating that the status is unchanged.

## Business rules

Semantyka snapshotu (wspólna dla obu silników; przy egzekucji na zamknięciu i pełnych wypełnieniach silnik event-driven daje dokładnie wartości silnika wektorowego)

| Pole | Znaczenie |
|---|---|
| `ts` | dzień zamknięcia, na którym policzono snapshot |
| `equity` | wartość portfela na zamknięciu `ts` (gotówka + ilości × ostatnia znana cena zamknięcia) podzielona przez kapitał początkowy; pierwszy snapshot = 1.0 |
| `positions` | wagi pozycji, które niosły okres kończący się w `ts`, wycenione po cenach zamknięcia i kapitale decyzji z poprzedniej chwili decyzji; bez instrumentów z zerową ilością |
| `costs` | koszty wypełnień od poprzedniego snapshotu, per instrument, jako ułamek equity poprzedniego snapshotu |
| `traded` | suma wypełnionych wag od poprzedniego snapshotu, per instrument (waga wypełnienia = \|ilość\| × cena wypełnienia / kapitał decyzji) |
| `cash` | część equity niezaangażowana w pozycje: `equity × (1 − Σ|positions|)` — jak w silniku wektorowym |

Tryby egzekucji

| Tryb | Cena wypełnienia zlecenia z zamknięcia t | Po co |
|---|---|---|
| zamknięcie t | zamknięcie t | parytet z silnikiem wektorowym |
| otwarcie t+1 | otwarcie następnego baru | najwcześniejsza cena dostępna po poznaniu sygnału |
| zamknięcie t+1 | zamknięcie następnego baru | spóźnienie o dzień: jak szybko sygnał traci wartość |

Parametry symulacji (stałe metodologii, jak liczba permutacji — nie parametry hipotezy)

| Parametr | Wartość | Źródło |
|---|---|---|
| Kapitał nominalny | 100 000 USDT | 01-story, decyzja 1 |
| Limit udziału w wolumenie | 2.5% wolumenu baru wypełnienia | 01-story, decyzja 2 (domyślna wartość zipline) |
| Reszta zlecenia ponad limit | anulowana | 01-story, decyzja 3 |

## Data and validation

`Order` (zapis każdego zlecenia, REQ-231)

| Field | Type | Required | Range or format |
|---|---|---|---|
| `instrument_id` | string | tak | instrument z uniwersum |
| `decision_ts` | date | tak | dzień decyzji |
| `quantity` | float | tak | ≠ 0; ujemna = sprzedaż |
| `decision_equity` | float | tak | > 0, w walucie |
| `filled_quantity` | float | tak | ten sam znak co `quantity`, \|filled\| ≤ \|quantity\|; 0 = anulowane |
| `fill_ts` | date \| null | tak | ≥ `decision_ts`; null, gdy anulowane w całości |
| `fill_price` | float \| null | tak | > 0; null, gdy anulowane w całości |
| `cost` | float | tak | ≥ 0, w walucie |

## Edge and error cases

- Instrument bez baru w dniu wypełnienia → zlecenie anulowane, pozycja bez zmian, wyceniana po ostatnim znanym zamknięciu (silnik wektorowy w tej sytuacji wyłącza instrument z góry — ta różnica jest zamierzona i opisana w raporcie parytetu).
- Instrument bez baru w dniu decyzji → strategia nie daje sygnału, więc waga docelowa 0; zlecenie zamknięcia czeka na bar wypełnienia jak każde inne.
- Wolumen baru wypełnienia równy 0 przy limicie udziału → nic się nie wypełnia, zlecenie liczy się jako ograniczone limitem.
- Zlecenie o zerowej ilości (pozycja już równa docelowej) → nie powstaje.
- Zamknięcie pozycji do zera → ilość po wypełnieniu dokładnie 0 (bez resztek zmiennoprzecinkowych).
- Brak sygnałów przez cały przebieg → equity stałe 1.0, brak zleceń, kapitał graniczny niezdefiniowany („—").
- Pozycje krótkie → ujemna ilość; sprzedaż zwiększa gotówkę, equity = gotówka + Σ ilość × cena.
- Zakres dat bez żadnego baru → błąd, jak w silniku wektorowym.

## Non-functional requirements

- Performance: jeden przebieg event-driven na okresie treningowym `momentum_v1` (ok. 2 200 dni × 2 instrumenty) poniżej 10 s; całe porównanie (5 przebiegów) poniżej 1 minuty na maszynie deweloperskiej.
- Reproducibility: silnik event-driven jest deterministyczny (bez losowości); ten sam wkład daje identyczny przebieg.
- Security and privacy: brak danych osobowych.

## Traceability

| AC | REQ |
|---|---|
| AC-1 | REQ-202, REQ-203, REQ-220, REQ-240, REQ-251 |
| AC-2 | REQ-210, REQ-211, REQ-212 |
| AC-3 | REQ-221, REQ-222 |
| AC-4 | REQ-230, REQ-231, REQ-232, REQ-252 |
| AC-5 | REQ-250, REQ-253 |
| AC-6 | REQ-201, REQ-202 |

REQ-223 (podstawialność) wynika z zasady 9 w CLAUDE.md; REQ-260 z zasady „odrzucona hipoteza opisana rzetelnie" — uzupełnienie wpisu, nie nowy werdykt.

## Open questions

Brak. Parametry symulacji przyjęte w [01-story.md](01-story.md) (decyzje 1–3).
