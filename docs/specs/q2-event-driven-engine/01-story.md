# q2-event-driven-engine - Silnik event-driven: egzekucja zleceń za wspólnym kontraktem `BacktestRun`

Status: Ready for dev
Owner role: PO
Upstream: docs/specs/q1-momentum-research-mvp/
Links: docs/ROADMAP.md, docs/adr/0002-dual-backtest-engine.md, docs/RESEARCH_LOG.md

## Problem

Wszystkie wyniki w dzienniku pochodzą z silnika wektorowego, który upraszcza egzekucję trzema założeniami:

1. **Transakcja po cenie, z której liczony jest sygnał.** Sygnał z zamknięcia dnia t wchodzi w pozycję po tej samej cenie zamknięcia. W praktyce zlecenie da się złożyć dopiero po jej poznaniu, więc najwcześniej po następnej dostępnej cenie.
2. **Każde zlecenie wypełnia się w całości.** Silnik liczy na znormalizowanym kapitale (1.0), bez nominału, więc nie wie, czy zlecenie jest małe czy ogromne wobec obrotu rynku.
3. **Wiedza o dostępności danych jutro.** Instrument bez baru na t+1 jest wyłączany z wag już na zamknięciu t — silnik korzysta z informacji, której w chwili decyzji jeszcze nie ma.

Do tego brak look-ahead w silniku wektorowym zależy od dyscypliny strategii: każda dostaje całą historię cen i sama musi odfiltrować bary z datą po `as_of`. Obie dzisiejsze strategie robią to poprawnie, ale nic tego nie wymusza.

Nie wiadomo, ile z wyniku `momentum_v1` (i `mean_reversion_v1`) zależy od tych uproszczeń. [ADR-0002](../../adr/0002-dual-backtest-engine.md) przewiduje drugi silnik za tym samym kontraktem właśnie po to, żeby to sprawdzić na tej samej hipotezie.

## Outcome

Primary metric: tabela porównania silników dla `momentum_v1` na okresie treningowym — wektorowy wobec event-driven w kilku trybach egzekucji — z CAGR, Sharpe, max drawdown, obrotem i kosztami, liczona kodem; do tego kapitał, od którego limit udziału w wolumenie zaczyna ograniczać zlecenia (pojemność strategii).
Guardrail metric: przy tych samych założeniach co silnik wektorowy (egzekucja na zamknięciu, pełne wypełnienia, dane bez luk) oba silniki dają ten sam przebieg — equity, pozycje, koszty i obrót zgodne z tolerancją 1e-12 w każdym dniu. Żaden status w dzienniku nie zmienia się przez ten epik.

## User story

Jako budujący platformę chcę silnik, który przetwarza rynek zdarzenie po zdarzeniu, składa zlecenia i symuluje ich wypełnienie, za tym samym kontraktem co silnik wektorowy, żeby sprawdzić, ile wyniku hipotezy zależy od uproszczeń egzekucji, i żeby brak look-ahead wynikał z konstrukcji silnika, a nie z dyscypliny każdej strategii.

## Acceptance criteria

- AC-1 (parytet): Given te same dane bez luk, strategia i model kosztów, when uruchamiam silnik wektorowy i event-driven z egzekucją na zamknięciu i pełnymi wypełnieniami, then equity, pozycje, koszty i obrót w każdym snapshocie są równe z tolerancją 1e-12.
- AC-2 (look-ahead z konstrukcji): Given silnik event-driven, when strategia liczy sygnał na dzień t, then dostaje wyłącznie bary z datą ≤ t — strategia, która próbuje czytać ostatni bar listy jako „jutro", nie ma do niego dostępu.
- AC-3 (egzekucja na następnym barze): Given tryb „otwarcie t+1" albo „zamknięcie t+1", when sygnał powstaje na zamknięciu t, then zlecenie wypełnia się po cenie otwarcia albo zamknięcia następnego baru, a wynik zgadza się z wyliczonym ręcznie na danych syntetycznych.
- AC-4 (częściowe wypełnienia): Given kapitał nominalny i limit udziału w wolumenie, when zlecenie przekracza limit na barze wypełnienia, then wypełnia się tylko do limitu, reszta jest anulowana, a raport pokazuje liczbę częściowo wypełnionych zleceń i kapitał, od którego limit zaczyna wiązać.
- AC-5 (porównanie): Given zacommitowana definicja hipotezy, when uruchamiam porównanie silników, then dostaję tabelę CAGR, Sharpe, max drawdown, obrotu i kosztów dla każdego trybu, liczoną tylko na okresie treningowym — bez odczytu danych holdoutu.
- AC-6 (wspólny kontrakt): Given przebieg event-driven, when przekazuję go do metryk, porównania kosztów, walk-forward i metryk warunkowych per reżim, then działają bez zmian w ich kodzie.

## Out of scope

- **Zmiana silnika, na którym walidowane są hipotezy.** Walk-forward, test permutacyjny, holdout i werdykty zostają na silniku wektorowym — zamrożone reguły `momentum_v1` i `mean_reversion_v1` go zakładają. Porównanie silników jest opisowe.
- **Rejestr transakcji i test permutacyjny na przebiegach z egzekucją na następnym barze.** Oba rekonstruują P&L jako wagę razy zwrot zamknięcie-zamknięcie, co jest dokładne tylko przy egzekucji na zamknięciu. Silnik event-driven zapisuje własną listę wypełnień.
- Model market impact (np. pierwiastkowy) — wymaga zmiany interfejsu `CostModel` o nominał i wolumen; osobny krok po tym epiku.
- Dane śróddzienne, arkusz zleceń, zlecenia z limitem ceny, opóźnienia sieciowe.
- Opóźnienie egzekucji dłuższe niż jeden bar jako parametr — każdy dodatkowy tryb to kolejne pokrętło.

## Priority

Should have — następny w kolejności ROADMAP po `q3`, który czeka na lokalny przebieg treningowy (M5). Nie zależy od wyników `q3` i nie dodaje próby do żadnej hipotezy, bo nie zmienia ich parametrów ani werdyktów.

## Dependencies and risks

- Zależy od `q1` (kontrakt `BacktestRun`, interfejsy `Strategy` i `CostModel`, metryki) i od `q3`-M1 (definicja hipotezy jako jedyne źródło parametrów przebiegu).
- **Ryzyko: różnica wyjdzie pomijalna.** Krypto handluje 24/7, więc otwarcie dnia t+1 na Binance to praktycznie ta sama chwila co zamknięcie t. To pełnoprawny wynik: potwierdza, że założenie silnika wektorowego jest dla tego rynku nieszkodliwe. Tryb „zamknięcie t+1" (spóźnienie o dzień) pokazuje za to, jak szybko sygnał traci wartość; dla akcji z lukami nocnymi (`q5`) różnica między zamknięciem a otwarciem będzie istotna.
- **Ryzyko: limit wolumenu nigdy nie wiąże.** Przy BTC i ETH i kapitale badacza indywidualnego to niemal pewne. Dlatego raport podaje kapitał graniczny (pojemność), a nie tylko liczbę częściowych wypełnień.
- **Ryzyko: dwa silniki do utrzymania** ([ADR-0002](../../adr/0002-dual-backtest-engine.md)). Test parytetu pilnuje, żeby się nie rozjechały, a reguła wag (równe wagi po znaku sygnału) ma jedną implementację wspólną dla obu.
- **Ryzyko: pokusa ponownej oceny hipotezy trybem, który wypada lepiej.** Mitygacja: werdykty zostają na silniku wektorowym i zamrożonych regułach; tabela porównania nie ma kolumny statusu.

## Open questions

Brak pytań blokujących. Parametry symulacji to nie parametry hipotezy i nie wpływają na żaden werdykt, więc zostały przyjęte domyślnie (do zmiany przez Tomasza bez skutków dla dziennika):

| # | Decyzja | Uzasadnienie |
|---|---|---|
| 1 | Kapitał nominalny 100 000 USDT | skala badacza indywidualnego; raport podaje też kapitał graniczny, więc wniosek nie zależy od tej liczby |
| 2 | Limit udziału: 2.5% wolumenu baru wypełnienia | domyślna wartość `VolumeShareSlippage` w zipline (Quantopian) — wzięta z narzędzia, nie dobrana do danych |
| 3 | Niewypełniona reszta zlecenia jest anulowana na koniec baru | strategie rebalansują codziennie do wag docelowych, więc następne zlecenie i tak liczy się od faktycznie trzymanych pozycji |
