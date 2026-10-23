# QuantLab

[![CI](https://github.com/devTomaszStoklosa/QuantLab/actions/workflows/ci.yml/badge.svg)](https://github.com/devTomaszStoklosa/QuantLab/actions/workflows/ci.yml)

Platforma do prowadzenia systematycznych badań inwestycyjnych: hipoteza, dane, sygnał, backtest, koszty transakcyjne, walidacja out-of-sample, ryzyko i reżimy rynkowe, analiza transakcji. Projekt portfolio pod role Quantitative Developer / Quantitative Analyst / Systematic Trading Research.

Cel nie jest jedna działająca strategia — cel jest pokazanie procesu badawczego: hipoteza, test, walidacja, wniosek, także gdy wniosek to „nie działa".

## Szybki start (bez kluczy, na danych syntetycznych)

Wymagania: [uv](https://docs.astral.sh/uv/), a dla aplikacji .NET 10 SDK i Node.js ≥ 22.22.

```bash
git clone https://github.com/devTomaszStoklosa/QuantLab.git   # pełny klon: rejestr prób (q6) czyta historię gita
cd QuantLab
uv sync
uv run pytest -q                                               # testy silnika na danych syntetycznych, bez sieci
(cd presentation/web && npm ci && npm run build)
dotnet run --project presentation/QuantLab.Api --launch-profile demo   # aplikacja na syntetycznym magazynie: http://localhost:5080
```

Przebiegi na prawdziwych danych wymagają dostępu do Binance i darmowego klucza Tiingo. Ich ceny, rejestr transakcji i tear-sheety zostają lokalnie; w repozytorium są kod, metodologia i zagregowane statystyki ([ADR-0010](docs/adr/0010-public-repo-data-boundary.md)).

## Status

MVP zamknięte (`lab-foundation` + `q1-momentum-research-mvp`): pierwsza hipoteza — time-series momentum na BTC-USDT i ETH-USDT — przeszła pełny pipeline (sygnał, silnik wektorowy z testem golden-master, trzy modele kosztów, walk-forward, zamrożony holdout otwarty raz, test permutacyjny, reżimy, stress test, rejestr transakcji, tear-sheet). Wynik: `inconclusive`, opisany w [docs/RESEARCH_LOG.md](docs/RESEARCH_LOG.md).

Rozszerzenia (`q2`–`q14`) mają gotowy kod. Osiem kolejnych hipotez zamrożono przed pierwszym przebiegiem, a ich przebiegi na prawdziwych danych zrobiono lokalnie 2026-10-02 (środowisko, w którym powstaje kod, nie ma dostępu do źródeł danych). Żadna hipoteza nie jest `confirmed` i żaden holdout nie pokazał timingu lepszego niż przypadek. Wyniki, razem z obserwacjami zapisanymi przed każdym otwarciem holdoutu, są w [docs/RESEARCH_LOG.md](docs/RESEARCH_LOG.md):

- `mean_reversion_v1` (`q3`), krótkoterminowe odwrócenie na BTC i ETH: **`rejected`**. Strata w każdym roku treningu i w holdoucie (Sharpe netto −1.70), bo ruchy 7-dniowe częściej trwały, niż się odwracały.
- `pairs_v1` (`q4`), pairs trading na kointegracji ETH/BTC: **`inconclusive`**. Jedna pozycja w sześć lat treningu i żadna w holdoucie, bo ETH i BTC nie są stabilnie skointegrowane.
- `xsmom_v1` (`q5`), momentum przekrojowe 12-1 na S&P 500 point-in-time: skład odtwarzany z historii zmian indeksu, spółki zdjęte z obrotu i ich zwroty z delistingu, ceny skorygowane o splity i dywidendy (Tiingo), istotność z testu losowych portfeli z tego samego przekroju. Dla części dawnych członków indeksu Tiingo zwracało ceny innej spółki pod tym samym tickerem. Te tickery są wykluczone, trening powtórzono na poprawionych danych 2026-10-18, a holdout czeka na otwarcie ([#104](https://github.com/devTomaszStoklosa/QuantLab/issues/104)).
- `momentum_select_v1` (`q8`), momentum szeregów czasowych na BTC i ETH z lookbackiem dobieranym co rok z siatki 30–365 dni. Zamrożona jest procedura wyboru, nie wartość, a jej bramką in-sample jest CPCV (wiele ścieżek spoza próby z purgingiem i embargo). Wynik: **`inconclusive`**; CPCV zaliczona, ale po korekcie na wielokrotne testowanie bez przewagi, a w holdoucie Sharpe 0.52 przy p = 0.30.
- `portfolio_v1` (`q9`), portfel czterech hipotez krypto ważonych co miesiąc odwrotnością zmienności, handlujący pozycjami netto: **`rejected`**. Reguła ważenia ryzykiem dała najwięcej wagi najsłabszemu rękawowi.
- `momentum_voltarget_v1` (`q11`), sygnał `momentum_v1` z pozycjami skalowanymi do docelowej zmienności 40% rocznie, bez dźwigni: **`inconclusive`**. W treningu skalowanie obniżyło zmienność i obsunięcie bez utraty Sharpe, a w holdoucie Sharpe wyniósł 0.48 przy p = 0.25.
- `momentum_multiasset_v1` i `momentum_voltarget_multiasset_v1` (`q12`), reguła `momentum_v1` na koszyku ETF z pięciu klas aktywów (Tiingo, zwroty ponad gotówkę BIL), bez skalowania i ze skalowaniem do 10% rocznie: odpowiednio **`rejected`** i **`inconclusive`**. Na ok. 18 latach danych nie ma śladu timingu, a wynik netto jest bliski gotówce. 12-miesięczne momentum nie wykazało przewagi ani na krypto, ani na tym koszyku.

Gotowe są też: drugi silnik z egzekucją zleceń i parytetem z wektorowym (`q2`), PSR, deflated Sharpe i PBO z rejestrem prób liczonym z historii gita (`q6`), dobór parametru z siatki z CPCV (`q8`), portfel strategii z regułami alokacji ryzyka (`q9`), plan przebiegów lokalnych `quantlab plan` (`q10`), skalowanie pozycji do docelowej zmienności (`q11`), rozgrzewka liczona w sesjach rynku i zwroty ponad gotówkę (`q12`), opis wyniku składany z szablonów z policzonych liczb i szkic wpisu do dziennika `quantlab narrate` (`q13`), kontrola danych przed każdym przebiegiem i otwarciem holdoutu (`q14`) oraz warstwa prezentacji (`q7`): API ASP.NET Core i aplikacja React nad magazynem wyników. Szczegóły w [docs/ROADMAP.md](docs/ROADMAP.md).

## Dokumentacja

Indeks całej dokumentacji z ścieżkami czytania: [docs/README.md](docs/README.md). Dla programisty: [przewodnik](docs/DEVELOPER-GUIDE.md), [referencja komend](docs/CLI-REFERENCE.md), [magazyn wyników](docs/RESULTS-STORE.md), [warstwa prezentacji](docs/PRESENTATION.md), [testy i CI](docs/TESTING-AND-CI.md), [słownik pojęć](docs/GLOSSARY.md).

## Uruchomienie

Pełna instrukcja krok po kroku, z instalacją na Windows i rozwiązywaniem problemów: [docs/INSTRUKCJA.md](docs/INSTRUKCJA.md).

### Przebiegi lokalne

To, co zostało do zrobienia na maszynie z dostępem do danych, pokazuje jedna komenda (`q10`): sprawdzenia środowiska (natywne paczki bez AVX2, DuckDB w API .NET, dostęp do Binance i klucz Tiingo — gdy któryś krok ich potrzebuje), budowa uniwersum S&P 500, przebiegi treningowe, otwarcia holdoutów, commity zapisów otwarć i wpisy w dzienniku — każdy krok ze stanem (`done`, `pending`, `blocked` z powodem) i komendą. Przebieg jest zrobiony tylko wtedy, gdy magazyn ma go w bieżącym schemacie i z tą samą listą prób na tych samych danych.

```bash
uv sync
uv run quantlab plan          # stan każdego kroku, bez sieci i bez zmian w plikach
uv run quantlab plan --run    # sprawdzenia i kroki automatyczne po kolei; stop na pierwszym błędzie
```

`--run` nigdy nie otwiera holdoutu, nie commituje i nie pisze w dzienniku: to kroki badacza, wykonywane po przejrzeniu wyników treningu, w kolejności z planu (np. `portfolio_v1` po holdoutach swoich składników).

### Komendy

```bash
uv sync
uv run pytest -q
uv run quantlab run --tear-sheet reports/momentum_v1.html   # okres treningowy; wymaga dostępu do api.binance.com
uv run quantlab open-holdout                                 # holdout już otwarty: pokazuje zapisany wynik
uv run quantlab compare-engines                              # silnik wektorowy vs event-driven, okres treningowy
uv run quantlab trials                                       # wszystkie próby na tych samych danych: PSR, DSR, PBO
uv run quantlab registry                                     # rejestr hipotez w magazynie wyników, bez pobierania danych
uv run quantlab narrate momentum_v1                          # szkic wpisu do dziennika z liczb w magazynie wyników
uv run quantlab check-data momentum_v1                       # kontrola danych treningowych: błędy i ostrzeżenia z datami
uv run quantlab run momentum_select_v1                       # trening 2018-2023: historia wyborów, PBO siatki, CPCV (bramka)
uv run quantlab open-holdout momentum_select_v1             # jednorazowe otwarcie holdoutu 2026-01..08
uv run quantlab run portfolio_v1                             # trening 2018-2023: korelacje i wagi rękawów, Sharpe reguł
uv run quantlab open-holdout portfolio_v1                   # dopiero po holdoutach składników
uv run quantlab run momentum_voltarget_v1                    # trening 2018-2023: skala pozycji i porównanie z wersją bez skalowania
```

Akcje (`q5`): skład S&P 500 buduje się raz z zapisanej rewizji Wikipedii, ceny pobiera adapter Tiingo (darmowy plan Starter, klucz w zmiennej środowiskowej; limit 500 tickerów miesięcznie rozkłada pobieranie S&P 500 na trzy miesiące, a adapter sam go pilnuje). Wszystkie źródła są darmowe ([ADR-0009](docs/adr/0009-private-repo-free-tiingo-plan.md)). Licencja Tiingo pozwala tylko na użytek własny, więc pobrane ceny i wyniki z cenami zostają lokalnie ([ADR-0010](docs/adr/0010-public-repo-data-boundary.md), [docs/DATA-SOURCES.md](docs/DATA-SOURCES.md)):

```bash
uv run quantlab build-universe                               # src/quantlab/config/universes/sp500.yaml + raport sprzeczności
$env:TIINGO_API_KEY = "..."                                  # PowerShell; w bashu: export TIINGO_API_KEY=...
uv run quantlab run xsmom_v1                                 # trening 2005-2019; wznawia pobieranie z cache
uv run quantlab audit-tickers xsmom_v1                       # przed holdoutem: czy Tiingo trzyma pod tickerem tę samą spółkę (#104)
uv run quantlab open-holdout xsmom_v1                        # jednorazowe otwarcie holdoutu 2020-2025
uv run quantlab run momentum_multiasset_v1                   # ETF-y (q12): trening 2008-07..2017, zwroty ponad BIL
uv run quantlab run momentum_voltarget_multiasset_v1         # to samo ze skalowaniem do 10% rocznie
```

`quantlab run` zapisuje też dowody hipotezy do magazynu wyników `results/` (Parquet, ignorowany przez gita), z którego czyta warstwa prezentacji (`q7`, [ADR-0008](docs/adr/0008-results-store-parquet-duckdb.md)).

Warstwa prezentacji (`q7`) — API ASP.NET Core nad magazynem wyników i aplikacja React w design systemie QuantForge; wymaga .NET 10 SDK i Node.js ≥ 22.22:

```bash
dotnet test --solution presentation/QuantLab.Presentation.slnx
(cd presentation/web && npm ci && npm test && npm run build)            # aplikacja do presentation/web/dist, serwowana przez API
dotnet run --project presentation/QuantLab.Api                          # czyta results/ z lokalnych przebiegów; http://localhost:5080/api/hypotheses
dotnet run --project presentation/QuantLab.Api --launch-profile demo    # syntetyczny magazyn demo_* z presentation/fixtures/results; aplikacja: http://localhost:5080
(cd presentation/web && npm run dev)                                    # serwer deweloperski Vite (:5173) z proxy /api do API na :5080
```

Endpointy (tylko odczyt): `GET /api/health`, `/api/hypotheses`, `/api/hypotheses/{id}` (dowody przebiegu), `/api/hypotheses/{id}/equity`, `/api/hypotheses/{id}/trades?instrument=&side=&sort=&order=&offset=&limit=`.

## Stack

Python 3.12 + uv, pandas/numpy, DuckDB + Parquet, statsmodels/scipy, pytest. Warstwa prezentacji (epik `q7`): ASP.NET Core Web API (.NET 10, DuckDB.NET) + React (Vite, TypeScript), czytająca wyniki zapisane przez silnik Pythona. CI (GitHub Actions): ruff i pytest, testy API i aplikacji — na Linuksie i Windowsie.

## Dokumentacja

- [docs/INSTRUKCJA.md](docs/INSTRUKCJA.md) — instrukcja obsługi krok po kroku: instalacja, `quantlab plan`, przebiegi, holdouty, dziennik, aplikacja.
- [docs/PRODUCT.md](docs/PRODUCT.md) — dokumentacja produktowa: czym jest, jakie ma funkcje, jak z nich korzystać.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — warstwy, moduły, model danych, kontrakty.
- [docs/ROADMAP.md](docs/ROADMAP.md) — epiki, slice'y, zakres MVP, rozszerzenia.
- [docs/DATA-SOURCES.md](docs/DATA-SOURCES.md) — źródła danych i licencje.
- [docs/RESEARCH_LOG.md](docs/RESEARCH_LOG.md) — dziennik badawczy: hipotezy, metodologia, wnioski.
- [docs/adr/](docs/adr/) — decyzje architektoniczne z uzasadnieniem.
- [docs/specs/](docs/specs/) — specyfikacje RoleKit per epik (story/spec/design).

## Licencja

Kod i dokumentacja: [MIT](LICENSE). Plik składu S&P 500 (`src/quantlab/config/universes/sp500.yaml`) pochodzi z Wikipedii i jest na licencji CC BY-SA 4.0, z atrybucją w nagłówku. Repozytorium nie zawiera danych rynkowych.

## Disclaimer

Wyniki opisują historyczne zachowanie strategii testowych na danych historycznych. To projekt edukacyjny/badawczy, nie porada inwestycyjna.
