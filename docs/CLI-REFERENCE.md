# Referencja komend `quantlab`

Komendy są zdefiniowane w [`src/quantlab/cli.py`](../src/quantlab/cli.py) (Typer). Wszystkie uruchamia się przez `uv run quantlab <komenda>`; `uv run quantlab --version` wypisuje wersję pakietu, a `--help` opis każdej komendy.

Wspólne zasady:

- `HIPOTEZA` to identyfikator zamrożonej definicji `config/holdout/<id>.yaml`. Komendy odrzucają hipotezę bez zacommitowanej definicji, zanim cokolwiek pobiorą (stąd zakaz „przebiegu bez commitu"). Wartość domyślna to `momentum_v1`.
- Komendy treningowe nigdy nie pobierają danych holdoutu. Robi to wyłącznie `open-holdout`, jednorazowo.
- Źródło danych wynika z pola `source` pliku uniwersum (`binance` albo `tiingo`), nie z klasy aktywów.
- Parametry hipotezy pochodzą tylko z jej definicji; stałe w CLI to metodologia wspólna (ziarno, liczba permutacji, reżimy, scenariusze stress testu).

## Zmienne środowiskowe

| Zmienna | Znaczenie |
|---|---|
| `TIINGO_API_KEY` | klucz darmowego planu Tiingo; wymagany przez hipotezy na akcjach i ETF-ach oraz `check-source tiingo` |
| `TIINGO_REQUEST_INTERVAL_SECONDS` | odstęp między żądaniami do Tiingo (domyślnie 90 s) |
| `TIINGO_MONTHLY_SYMBOLS` | miesięczny limit unikalnych tickerów (domyślnie 500) |
| `QUANTLAB_UPDATE_FIXTURES` | `1` przy `tests/test_results_fixture.py` regeneruje syntetyczny magazyn |

Zmienne Tiingo istnieją na wypadek zmiany limitów planu; adapter sam pilnuje limitów i wznawia pobieranie z cache.

## Komendy badawcze

| Komenda | Co robi | Zapisuje | Sieć |
|---|---|---|---|
| `run [HIPOTEZA]` | przebieg okresu treningowego pod trzema modelami kosztów, walk-forward (albo CPCV w `q8`), test istotności, reżimy, stress test, rejestr transakcji, DSR/PBO | magazyn wyników `results/`, opcjonalnie tear-sheet | tak |
| `open-holdout [HIPOTEZA]` | jednorazowe otwarcie holdoutu, werdykt wg zamrożonego kryterium | `config/holdout/<id>.opened.json`, odświeża rejestr | tak (pierwszy raz) |
| `compare-engines [HIPOTEZA]` | porównanie silnika wektorowego z event-driven na treningu (opisowe) | nic | tak |
| `trials [HIPOTEZA]` | wszystkie próby na tych samych danych: Sharpe, PSR, DSR, PBO | nic | tak |
| `registry` | odświeża rejestr hipotez w magazynie z zacommitowanych definicji | `results/hypotheses.parquet` | nie |
| `narrate [HIPOTEZA]` | szkic wpisu do dziennika z liczb w magazynie i zapisu otwarcia | stdout albo plik z `--output` | nie |
| `check-data [HIPOTEZA]` | kontrola jakości danych treningowych (z rozgrzewką): błędy i ostrzeżenia z datami; kod 1 przy błędzie | nic | z cache, gdy jest; inaczej tak |
| `plan` | stan każdego kroku lokalnego z komendą do wykonania | nic | nie |
| `plan --run` | wykonuje sprawdzenia i kroki automatyczne po kolei | zależnie od kroku | tak |

### `run`

```bash
uv run quantlab run momentum_v1 --tear-sheet reports/momentum_v1.html
uv run quantlab run momentum_v1 --contrast mean_reversion_v1
```

- `--tear-sheet PLIK` zapisuje HTML tear-sheet przebiegu z realistycznymi kosztami.
- `--contrast HIPOTEZA` dodatkowo koreluje dzienne zwroty netto z drugą hipotezą (z jej zacommitowanej definicji).
- Wypisuje metryki pod każdym modelem kosztów, czułość na koszty, wynik walk-forward, test istotności, wielokrotne testowanie (DSR/PBO), podział P&L i diagnostykę treningową.
- Nie zmienia statusu hipotezy poza tym, co wynika z zapisanych bramek.

### `open-holdout`

```bash
uv run quantlab open-holdout momentum_v1
```

- Odmawia przed pobraniem danych, gdy definicja nie jest zamrożona w commicie. Odmawia też (`Error: …`, kod 1), gdy holdout nachodzi na nieotwarty holdout składnika (`holdout_prerequisites`, np. portfel) albo gdy dane holdoutu zawierają błąd jakości (kontrola `q14` biegnie przed jakimkolwiek obliczeniem na tych danych).
- Gdy holdout jest już otwarty, pokazuje zapisany wynik i nie pobiera danych. Zapis powstaje z wyłącznym utworzeniem pliku, więc nie da się go nadpisać.
- Po otwarciu odświeża rejestr w magazynie wyników.
- Trzeba zacommitować plik `.opened.json`; kolejność kroków wskazuje `plan`.

### `trials`, `compare-engines`

Opisowe: nie zmieniają statusów. `trials` liczy próby z historii gita katalogu `config/holdout/`, więc wymaga pełnego klonu repozytorium.

### `narrate`

```bash
uv run quantlab narrate momentum_v1 --output draft.md
```

`TemplateNarrator` składa po polsku sekcje: hipoteza, metodologia, trening, holdout, wniosek. Akapity wymagające interpretacji są oznaczone jako szkic dla badacza. `--output` nigdy nie nadpisuje istniejącego pliku.

### `plan`

Czyta repozytorium i magazyn wyników i wypisuje kroki w kolejności, każdy ze stanem (`done`, `pending`, `blocked` z powodem) i komendą. `--run` wykonuje sprawdzenia środowiska i kroki automatyczne, zatrzymuje się na pierwszym błędzie i nigdy nie otwiera holdoutu, nie commituje ani nie pisze w dzienniku.

## Komendy danych

| Komenda | Co robi |
|---|---|
| `build-universe` | buduje point-in-time skład S&P 500 z zapisanej rewizji Wikipedii do `src/quantlab/config/universes/sp500.yaml` i wypisuje raport sprzeczności |
| `audit-tickers HIPOTEZA [--output PLIK]` | sprawdza, czyjej spółki ceny Tiingo zwraca pod tickerem dawnych członków indeksu (#104); tabela do przeglądu trafia do `results/ticker-audit-<id>.csv` albo pod `--output` |
| `check-source SOURCE` | `binance` albo `tiingo`: czy źródło odpowiada (Tiingo wymaga klucza) |

## Kody wyjścia i błędy

Błąd domenowy (nieznana hipoteza, brak zamrożenia, niedostępne źródło, wyczerpany limit) kończy się komunikatem `Error: …` i kodem 1. Gdy źródło zawiedzie w trakcie pobierania (np. limit Tiingo), to, co pobrano, zostaje w cache `data/cache/` i następny przebieg wznawia pobieranie.
