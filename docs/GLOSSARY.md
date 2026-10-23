# Słownik pojęć

Pojęcia używane w kodzie i dokumentach. Definicje opisują, jak QuantLab używa danego terminu; szczegóły metody są w kodzie wskazanym przy haśle.

| Pojęcie | Znaczenie w QuantLab |
|---|---|
| **Hipoteza** | Zamrożona definicja badania: strategia z parametrami, uniwersum, model kosztów, okres treningowy i holdout, kryterium sukcesu. Plik `config/holdout/<id>.yaml`. Status: `proposed`, `testing`, `confirmed`, `rejected`, `inconclusive` (`research/hypothesis.py`). |
| **Trening / holdout** | Okres treningowy służy do wszystkich decyzji. Holdout to okres testowy otwierany jednorazowo komendą `open-holdout`, po zamrożeniu definicji w commicie. |
| **Zamrożenie** | Zacommitowanie definicji hipotezy przed pierwszym spojrzeniem na wynik na holdoucie. `frozen_at_commit` to ostatni commit dotykający pliku definicji. |
| **Zapis otwarcia** | `config/holdout/<id>.opened.json`: wynik holdoutu, commit otwarcia, werdykt. Powstaje raz; ponowne otwarcie pokazuje zapisany wynik (`validation/holdout.py`). |
| **Werdykt holdoutu** | `rejected`, gdy Sharpe netto ≤ progu; `inconclusive`, gdy Sharpe dodatni, ale p ≥ progu (lub brak Sharpe); `passed` w pozostałych przypadkach (`holdout_verdict`). |
| **Walk-forward** | Ocena na rozłącznych oknach roku kalendarzowego (okno niepełne jest oznaczone jako `partial`). Reguła przejścia: Sharpe > 0 w co najmniej 2/3 okien ze zdefiniowanym Sharpe i dodatni Sharpe zbiorczy; `inconclusive` przy mniej niż 3 oknach (`validation/walk_forward.py`). |
| **Test permutacyjny (`day_shuffle`)** | Losowe parowanie zwrotów z pozycjami faktycznie trzymanymi; pyta o timing. P-value to udział permutacji co najmniej tak dobrych jak wynik rzeczywisty. |
| **Test losowych portfeli (`random_portfolio`)** | Losowe portfele z przekroju każdej decyzji rebalansu z tymi samymi wagami i harmonogramem; pyta o selekcję (`q5`). |
| **Sharpe** | Roczny stosunek średniego zwrotu do odchylenia, liczony własnym kodem (`reporting/metrics.py`); okres roczny wynika z uniwersum (`periods_per_year`: 365 dla krypto). |
| **PSR** | Probabilistic Sharpe Ratio: prawdopodobieństwo, że prawdziwy Sharpe przekracza próg, z uwzględnieniem skośności i kurtozy (`validation/sharpe_inference.py`). |
| **DSR** | Deflated Sharpe Ratio: PSR z progiem podniesionym o spodziewane maksimum Sharpe'a z N prób; koryguje wielokrotne testowanie. |
| **Próba (trial)** | Każda hipoteza, której definicja kiedykolwiek trafiła do gita, także usunięta. Liczona z historii gita `config/holdout/` (`research/trials.py`) i zawyża próg DSR. |
| **PBO** | Probability of Backtest Overfitting: jak często konfiguracja najlepsza w próbie jest poniżej mediany poza próbą (`validation/pbo.py`). |
| **CPCV** | Combinatorial Purged Cross-Validation: wiele ścieżek spoza próby z purgingiem i embargo (`validation/cpcv.py`). Bramka `q8`: mediana Sharpe'a ścieżek > 0. |
| **Purging / embargo** | Usunięcie z treningu obserwacji nachodzących na zbiór testowy (purge) i odstęp po nim (embargo), by nie przeciekała informacja. |
| **Point-in-time** | Uniwersum odtwarzane tak, jak wyglądało danego dnia (skład S&P 500 z historii zmian, także spółki wycofane), co ogranicza błąd przeżywalności (`core/universe.py`, `core/sp500.py`). |
| **Delisting** | Zdjęcie z obrotu; ostatni „bar" z wartością dla posiadaczy (`PriceBar.delisting`). Pozycja zamienia się w gotówkę bez kosztu i obrotu. |
| **Look-ahead** | Użycie informacji z przyszłości. Sygnał z dnia *t* decyduje o pozycji od *t* do *t+1*; strategie, modele kosztów i klasyfikatory widzą tylko dane do *t*. |
| **Sygnał (`Signal`)** | Kierunek (`long`, `short`, `flat`) dla instrumentu w danym dniu, wynik `Strategy.generate_signals`. |
| **Sizer** | Reguła zamiany sygnałów na wagi (`backtest/sizing.py`): równe wagi wg znaku, skalowane, przenoszone, wagi pary. |
| **Polityka rebalansu** | `Daily` (domyślnie, wraca do celu co dzień) albo `OnSignalChange` (dryfujące pozycje trzymane bez handlu). |
| **Silnik wektorowy / event-driven** | Dwa silniki za wspólnym kontraktem `BacktestRun` ([ADR-0002](adr/0002-dual-backtest-engine.md)). Walidacja i werdykty działają na wektorowym; event-driven modeluje zlecenia i wypełnienia, a `compare-engines` je porównuje. |
| **Model kosztów** | `zero`, `naive` (stałe bps) i `realistic` (opłata + `k` × zmienność z `vol_window` dni), jako ułamek kapitału (`costs/`). |
| **Reżim** | Tercyl zmienności zrealizowanej: `low`, `medium`, `high`, `undefined` (`risk/regime.py`). |
| **Stress test** | Natychmiastowe szoki cen instrumentów zastosowane do pozycji z ostatniego dnia przebiegu i z każdego dnia (`risk/stress.py`). |
| **Rejestr transakcji (trade ledger)** | Lista transakcji z P&L brutto, kosztami i netto, reżimem przy wejściu (`attribution/trade_ledger.py`). |
| **Rękaw (sleeve)** | Składowa portfela strategii (`q9`): zamrożona hipoteza o wadze liczonej regułą alokacji (równe wagi, odwrotność zmienności, risk parity). |
| **Skalowanie do zmienności** | Skalowanie pozycji do docelowej zmienności rocznej, bez dźwigni (`q11`, `VolatilityTargeted`). |
| **Zwroty ponad gotówkę** | Ceny w jednostkach instrumentu gotówkowego uniwersum (np. BIL), czyli zwroty nadwyżkowe (`q12`, `core/data/cash.py`). |
| **Magazyn wyników** | Tabele Parquet w `results/` zapisane przez Pythona i czytane przez API .NET ([RESULTS-STORE.md](RESULTS-STORE.md)). |
| **Narrator** | Składa opis wyniku z szablonów na podstawie policzonych liczb, bez modelu językowego (`reporting/narrative.py`). |
| **Granica publicznego repo** | Kod, metodologia i zagregowane statystyki są publiczne; ceny, rejestr transakcji, tear-sheety i `results/` zostają lokalnie ([ADR-0010](adr/0010-public-repo-data-boundary.md)). |
