# q1-momentum-research-mvp - Pełny pipeline na pierwszej hipotezie (momentum)

Status: Ready for architect
Owner role: PO
Upstream: docs/specs/lab-foundation/
Links: docs/ROADMAP.md

## Problem

Cel platformy nie jest jedna działająca strategia, tylko dowód, że proces badawczy (hipoteza, dane, sygnał, backtest, koszty, walidacja, ryzyko, atrybucja, wniosek) działa end-to-end i jest rzetelny. Bez przejścia całego pipeline'u na choćby jednej hipotezie żaden kolejny epik (event-driven engine, druga hipoteza, pairs trading) nie ma na czym stanąć, i nie ma czym pokazać rekruterowi, że deklarowany proces istnieje naprawdę, a nie tylko w dokumentacji.

## Outcome

Primary metric: hipoteza „time-series momentum działa na koszyku ETF-ów" ma jednoznaczny status (`confirmed` / `rejected` / `inconclusive`) w `docs/RESEARCH_LOG.md`, poparty walidacją out-of-sample i zamrożonym holdout — nie tylko wynikiem na danych treningowych.
Guardrail metric: 0 wniosków „confirmed" bez przejścia walk-forward i zamrożonego holdout (patrz [ADR-0004](../../adr/0004-validation-first-frozen-holdout.md)); silnik backtestu ma testy golden-master zanim jakikolwiek wynik na realnych danych jest uznany za wiarygodny.

## User story

Jako budujący platformę chcę przeprowadzić jedną hipotezę (momentum) przez pełny pipeline — sygnał, backtest wektorowy, dwa modele kosztów, walidację out-of-sample, analizę ryzyka w różnych reżimach i analizę pojedynczych transakcji — i zapisać wniosek w dzienniku badawczym, żeby platforma udowodniła kompletność procesu, niezależnie od tego, czy sama hipoteza się potwierdzi.

## Acceptance criteria

- AC-1: Given rejestr hipotez, when dodaję nową hipotezę, then zapisuje się z tytułem, tezą i statusem początkowym `proposed`.
- AC-2: Given syntetyczne dane ze stałym trendem, when uruchamiam silnik backtestu na strategii kupna i trzymania, then otrzymany Sharpe ratio zgadza się z wartością policzoną z góry analitycznie (test golden-master), z tolerancją numeryczną.
- AC-3: Given koszyk ETF-ów i sygnał momentum (zwrot N-okresowy), when uruchamiam `Strategy.generate_signals`, then dostaję sygnał długi/krótki/neutralny per instrument i data, bez wykorzystania danych z przyszłości względem daty sygnału (brak look-ahead).
- AC-4: Given sygnał i dane, when uruchamiam silnik wektorowy, then otrzymuję `BacktestRun` z `PortfolioSnapshot` per okres i metrykami CAGR, Sharpe, Sortino, Calmar, max drawdown liczonymi własnym kodem.
- AC-5: Given ten sam `BacktestRun`, when porównuję `NaiveCostModel` i `RealisticCostModel`, then raport pokazuje różnicę w wyniku netto przypisaną kosztom, nie szum.
- AC-6: Given szereg dat, when uruchamiam `WalkForwardValidator`, then wynik pokazuje metryki per rolling okno, nie tylko zagregowane za cały zakres.
- AC-7: Given zakres dat holdout, when był on zamrożony (plik z parametrami commitowany) przed uruchomieniem, then raport końcowy jawnie odróżnia wynik na danych treningowych od wyniku na holdout.
- AC-8: Given wynik strategii i wynik losowego przetasowania (permutacja), when porównuję oba, then dostaję p-value albo równoważną miarę odległości od przypadku.
- AC-9: Given historia cen instrumentu, when klasyfikuję reżimy zmienności (tercyle), then metryki wydajności są dostępne warunkowo per reżim.
- AC-10: Given zdefiniowany scenariusz szoku (np. spadek cen akcji o 20%), when uruchamiam stress test, then dostaję wpływ na wartość portfela liczony z wag, bez dodatkowego wywołania modelu ryzyka spoza kodu.
- AC-11: Given zamknięte pozycje z przebiegu, when generuję rejestr transakcji, then każda ma wejście, wyjście, P&L brutto/netto, koszty, holding period i etykietę reżimu w momencie wejścia.
- AC-12: Given rejestr transakcji, when tnę wyniki po reżimie i po buckecie holding period, then dostaję rozkład P&L per grupa, nie tylko sumę całkowitą.
- AC-13: Given kompletny przebieg, when generuję tear-sheet, then raport zawiera equity curve, wykres drawdown, tabelę metryk i tabelę wyników warunkowych per reżim.
- AC-14: Given zakończony przebieg z walidacją, when zapisuję wpis w `docs/RESEARCH_LOG.md`, then wpis zawiera hipotezę, metodologię, wynik i jednoznaczny wniosek (`confirmed`/`rejected`/`inconclusive`).

## Out of scope

- Event-driven silnik (realistyczna egzekucja) — `q2-event-driven-engine`.
- Druga rodzina hipotez (mean reversion) — `q3-mean-reversion-hypothesis`.
- Multi-asset / pairs trading — `q4-pairs-trading-stat-arb`.
- Point-in-time uniwersum equities, survivorship bias — `q5-equities-cross-section`.
- Purged k-fold/CPCV, deflated Sharpe, PBO — `q6-advanced-validation-cpcv` (MVP ma walk-forward i test permutacyjny, nie pełną korektę na multiple testing, bo testowana jest tu tylko jedna hipoteza).
- Warstwa .NET/React — `q7-dotnet-react-presentation`.

## Priority

Must have — to jest granica MVP całego projektu portfolio.

## Dependencies and risks

- Zależy od `lab-foundation` (dostęp do danych, storage, uniwersum).
- Ryzyko: pokusa wielokrotnego zerkania na holdout aż „zadziała" — mitygacja: zamrożenie parametrów w pliku commitowanym przed pierwszym uruchomieniem na holdout (REQ w 02-spec).
- Ryzyko: hipoteza nie działa na wybranym koszyku/okresie — to dopuszczalny, pełnoprawny wynik (`rejected`), nie powód do zmiany kryteriów po fakcie.
- Ryzyko: silnik bez testów golden-master daje wyniki, którym nie można ufać — mitygacja: AC-2 jako pierwszy blokujący krok.

## Open questions

| # | Question | Owner | Due |
|---|---|---|---|
| 1 | Dokładny koszyk instrumentów (które ETF-y/FX) i zakres dat treningowych vs holdout | Tomasz | przed slice S6 |
| 2 | Parametr N (okres lookback) dla sygnału momentum — z literatury (Moskowitz/Ooi/Pedersen) czy dobrany empirycznie na danych treningowych | Tomasz | przed slice S3 |
