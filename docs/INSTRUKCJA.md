# Instrukcja obsługi QuantLab

Ta instrukcja prowadzi krok po kroku przez pracę z gotowym QuantLab na własnym komputerze: instalację, przebiegi treningowe, jednorazowe otwarcia holdoutów, wpisy w dzienniku i przeglądanie wyników w aplikacji. Czym jest produkt i dlaczego działa tak, a nie inaczej, opisuje [PRODUCT.md](PRODUCT.md), a budowę kodu [ARCHITECTURE.md](ARCHITECTURE.md). Tutaj są konkretne komendy i kolejność kroków.

Komendy podane są dla PowerShella na Windows 10, czyli maszyny deweloperskiej. W bashu (Linux, macOS, Git Bash) działają tak samo, poza miejscami opisanymi osobno.

## Ściąga

```powershell
git pull                                  # najnowszy stan repozytorium
uv sync                                   # zależności Pythona
uv run quantlab plan                      # co zostało do zrobienia, w jakiej kolejności i dlaczego
uv run quantlab plan --run                # sprawdzenia środowiska i przebiegi treningowe, po kolei
# przegląd raportów w reports/ albo w aplikacji, potem ręcznie, jedna hipoteza naraz:
uv run quantlab open-holdout <id>         # jednorazowe otwarcie holdoutu
git add config/holdout/<id>.opened.json   # potem git commit i git push
# wpis w docs/RESEARCH_LOG.md, commit, i znów: uv run quantlab plan
```

## 1. Co jest gotowe

Kod wszystkich epików (`lab-foundation`, `q1`–`q12`) jest gotowy i przechodzi testy w CI na Linuksie i Windowsie. Zostały przebiegi na prawdziwych danych: środowisko, w którym powstawał kod, nie ma dostępu do Binance, Tiingo ani Wikipedii, więc te kroki wykonuje się lokalnie.

Hipotezy zamrożone w `config/holdout/`, czyli z parametrami, zakresami dat i kryterium sukcesu zacommitowanymi przed pierwszym przebiegiem:

| Hipoteza | Co testuje | Dane | Trening | Holdout | Stan |
|---|---|---|---|---|---|
| `momentum_v1` | momentum szeregów czasowych, lookback 12 miesięcy | BTC, ETH (Binance) | 2018–2023 | 2024–2025 | zamknięta: `inconclusive`, wpis w dzienniku |
| `mean_reversion_v1` | krótkoterminowe odwrócenie | BTC, ETH | 2018–2023 | 01–08.2026 | czeka na trening |
| `pairs_v1` | pairs trading ETH/BTC na kointegracji | BTC, ETH | 2018–2023 | 01–08.2026 | czeka na trening |
| `momentum_select_v1` | momentum z lookbackiem wybieranym co rok z siatki 30–365 dni, bramka CPCV | BTC, ETH | 2018–2023 | 01–08.2026 | czeka na trening |
| `portfolio_v1` | portfel czterech hipotez krypto ważonych odwrotnością zmienności | BTC, ETH | 2018–2023 | 01–08.2026 | czeka na trening; holdout dopiero po składnikach |
| `momentum_voltarget_v1` | sygnał `momentum_v1` z pozycjami skalowanymi do docelowej zmienności 40% rocznie, bez dźwigni | BTC, ETH | 2018–2023 | 01–08.2026 | czeka na trening |
| `xsmom_v1` | momentum przekrojowe 12-1 | S&P 500 point-in-time (Tiingo, Wikipedia) | 2005–2019 | 2020–2025 | czeka na budowę uniwersum i pobranie cen z Tiingo |
| `momentum_multiasset_v1` | reguła `momentum_v1` (252 sesje, równe wagi po znaku) na zwrotach ponad gotówkę | 10 ETF-ów z pięciu klas aktywów, gotówka BIL (Tiingo) | 07.2008–2017 | 2018–08.2026 | czeka na trening (klucz Tiingo) |
| `momentum_voltarget_multiasset_v1` | ten sam sygnał ze skalowaniem do 10% rocznie na instrument, bez dźwigni | jak wyżej | 07.2008–2017 | 2018–08.2026 | czeka na trening (klucz Tiingo) |

Z czego się korzysta:

- **CLI `quantlab`** liczy wszystko: przebiegi, walidację, holdouty i plan pracy.
- **Magazyn wyników `results/`** to pliki Parquet zapisywane przez `quantlab run` i `open-holdout`. Jest poza gitem, bo rejestr transakcji zawiera ceny rynkowe.
- **Raporty `reports/<id>.html`** (tear-sheet) to jeden samowystarczalny plik HTML na przebieg, do otwarcia w przeglądarce. Też poza gitem.
- **Aplikacja** to API ASP.NET Core z interfejsem React nad magazynem wyników. Tylko odczyt: niczego nie liczy i niczego nie zmienia.

## 2. Przygotowanie komputera (jednorazowo)

### 2.1 Programy

| Program | Po co | Kiedy potrzebny |
|---|---|---|
| Git | repozytorium; rejestr prób czyta historię `config/holdout/` | zawsze |
| uv | Python 3.12 i zależności (uv sam pobiera właściwą wersję Pythona) | zawsze |
| .NET 10 SDK | API aplikacji | tylko do przeglądania wyników w aplikacji |
| Node.js ≥ 22.22 | budowa interfejsu React | tylko do aplikacji |

Na Windows najprościej przez `winget`:

```powershell
winget install Git.Git
winget install astral-sh.uv
winget install Microsoft.DotNet.SDK.10
winget install OpenJS.NodeJS.LTS
```

Po instalacji otwórz nowe okno PowerShella, żeby nowe programy były widoczne na ścieżce.

### 2.2 Repozytorium i zależności

```powershell
git clone https://github.com/devTomaszStoklosa/QuantLab.git
cd QuantLab
uv sync
uv run pytest -q
```

Potrzebny jest pełny klon, bez `--depth`, bo rejestr prób czyta całą historię definicji. Ostatnia komenda uruchamia ok. 700 testów na syntetycznych danych, bez sieci; wszystkie powinny przejść. Jeśli repozytorium już jest na dysku, wystarczą `git pull` i `uv sync`.

### 2.3 Klucz Tiingo (`xsmom_v1` i hipotezy na ETF-ach)

Darmowy klucz daje konto na tiingo.com. Ustawienie:

```powershell
$env:TIINGO_API_KEY = "twój-klucz"     # tylko w bieżącym oknie
setx TIINGO_API_KEY "twój-klucz"       # na stałe; działa w nowo otwartych oknach
```

W bashu: `export TIINGO_API_KEY=twój-klucz`. Klucza nie wpisuj do żadnego pliku w repozytorium.

### 2.4 Pułapki Windows

- PowerShell 5.1 nie zna `&&`. Komendy wpisuj w osobnych liniach albo łącz średnikiem.
- Zawsze używaj `uv run …`, nie `python` ani `py`: launcher `py` uruchamia inną wersję Pythona niż przypięta w repozytorium.
- Pliki, np. dziennik, edytuj w edytorze zapisującym UTF-8 (VS Code, Notatnik). `Set-Content` bez `-Encoding utf8` psuje polskie znaki.

## 3. Pierwsze spojrzenie bez danych: aplikacja w trybie demo

Zanim cokolwiek pobierzesz, możesz zobaczyć, jak wyglądają wyniki. Repozytorium zawiera syntetyczny magazyn (`presentation/fixtures/results/`, hipotezy `demo_*`), wygenerowany tym samym pipeline'em co prawdziwe przebiegi.

```powershell
cd presentation\web
npm ci
npm run build
cd ..\..
dotnet run --project presentation/QuantLab.Api --launch-profile demo
```

Następnie otwórz http://localhost:5080:

- **Hypothesis registry** to lista hipotez ze statusem i stanem holdoutu: zapieczętowany albo otwarty, z werdyktem.
- **Strona hipotezy** zawiera:
  - zamrożoną definicję;
  - krzywą kapitału netto;
  - porównanie modeli kosztów i walk-forward;
  - test istotności i korektę na wielokrotne testowanie;
  - reżimy zmienności i miesięczne zwroty;
  - źródła P&L i rejestr transakcji z filtrami;
  - wynik holdoutu, jeśli został otwarty.

  `demo_select` pokazuje też wybór parametru i CPCV, `demo_portfolio` korelacje i wagi rękawów, a `demo_pairs` diagnostykę kointegracji.

Liczby w trybie demo są syntetyczne i aplikacja je tak oznacza. API zatrzymuje się klawiszami Ctrl+C.

## 4. Praca na prawdziwych danych: `quantlab plan`

### 4.1 Plan

`uv run quantlab plan` pokazuje wszystko, co zostało do zrobienia na tym komputerze, w jedynej kolejności, która nie psuje holdoutów. Nie używa sieci, niczego nie zmienia i trwa kilka sekund. Przy każdym wywołaniu plan liczony jest od nowa z bieżącego stanu repozytorium:

- zacommitowanych definicji i zapisów otwarć holdoutów;
- magazynu wyników i plików uniwersów;
- stanu gita i dziennika badawczego.

Niczego nie trzeba odhaczać ręcznie.

Fragment wyniku na repozytorium z 2026-09-25, jeszcze bez magazynu wyników:

```
Plan: 9 pending, 17 blocked, 3 done
  1  pending check   check:python                Native Python packages load and compute (DuckDB, statsmodels; no AVX2)
                                                 $ uv run pytest -q tests/test_environment.py
  ...
  4  pending auto    universe:sp500              Build the sp500 universe
                                                 src/quantlab/config/universes/sp500.yaml does not exist
                                                 $ uv run quantlab build-universe
  5  blocked manual  review:sp500                Review the sp500 build report, then commit the universe
                                                 waits for universe:sp500
  6  pending auto    train:momentum_v1           Training run of momentum_v1
                                                 no run in the results store
                                                 $ uv run quantlab run momentum_v1 --tear-sheet reports/momentum_v1.html
  ...
 12  done    manual  holdout:momentum_v1         Open the holdout of momentum_v1
 13  blocked manual  holdout:mean_reversion_v1   Open the holdout of mean_reversion_v1
                                                 waits for train:mean_reversion_v1
```

Każdy wiersz zawiera numer, stan, rodzaj, klucz i opis kroku. Pod spodem jest powód, gdy krok nie jest zrobiony, oraz komenda, gdy można ją teraz wykonać.

| Stan | Znaczenie |
|---|---|
| `done` | zrobione |
| `pending` | do zrobienia teraz |
| `blocked` | czeka na inny krok albo warunek; powód mówi na co |

| Rodzaj | Kto wykonuje |
|---|---|
| `check` | sprawdzenie środowiska; wykonuje je `plan --run` |
| `auto` | budowa uniwersum albo przebieg treningowy; wykonuje je `plan --run` |
| `manual` | otwarcie holdoutu, commit, przegląd uniwersum, wpis w dzienniku; **tylko Ty** |

Kolejność: sprawdzenia, uniwersa, przebiegi treningowe, otwarcia holdoutów, commity zapisów otwarć, wpisy w dzienniku.

**Kiedy przebieg treningowy jest zrobiony.** Tylko wtedy, gdy magazyn ma go w bieżącym schemacie i z tą samą listą prób na tych samych danych co dziś. Każda nowa hipoteza na tych samych danych to kolejna próba, a od liczby prób zależy deflated Sharpe. Dlatego wcześniejsze przebiegi wracają do stanu `pending` z powodem, np. `new trials on its data: portfolio_v1` albo `stored with schema v2, the store is v3`. To zamierzone działanie, nie błąd: `plan --run` je powtórzy. Dotyczy to także zamkniętej `momentum_v1`. Nowy przebieg obejmuje wyłącznie okres treningowy, a holdout i jego zapis zostają nietknięte.

### 4.2 Wykonanie: `plan --run`

```powershell
uv run quantlab plan --run
```

- Wykonuje po kolei kroki `check` i `auto` w stanie `pending`. Każdy działa jako osobny proces z wyjściem wprost w terminalu, np. `>>> train:pairs_v1: uv run quantlab run pairs_v1 …`.
- Po każdym kroku liczy plan od nowa.
- Zatrzymuje się na pierwszym błędzie z kodem wyjścia 1 i nazwą kroku, np. `Stopped: check:binance failed (exit code 1).`. Zrobione kroki zostają zrobione. Po usunięciu przyczyny uruchom `plan --run` ponownie: sprawdzenia wykonają się jeszcze raz, a zrobione przebiegi zostaną pominięte.
- Na końcu wypisuje pozostałe kroki ręczne (`Left for you (quantlab never takes these steps):`). Przy tych, które można już wykonać, podaje komendę.
- **Nigdy** nie otwiera holdoutu, nie commituje i nie pisze w dzienniku.

Czas: przebieg treningowy hipotezy krypto to według szacunku od około minuty do kilku minut na tej maszynie. Test istotności liczy 10 000 permutacji, a `portfolio_v1` liczy dodatkowo przebiegi składników, więc trwa najdłużej. Pierwszy przebieg pobiera świece dzienne z Binance, kolejne czytają je z `data/cache/`.

Jeśli budowa uniwersum `sp500` (Wikipedia) się nie powiedzie, `--run` zatrzyma się przed przebiegami krypto. Uruchom je wtedy bezpośrednio komendami z planu (`uv run quantlab run <id> --tear-sheet reports/<id>.html`), a do uniwersum wróć później.

### 4.3 Rytm pracy

1. `uv run quantlab plan --run`: przebiegi treningowe.
2. Przegląd wyników treningu (rozdział 5).
3. Dla jednej hipotezy naraz: otwarcie holdoutu, commit zapisu, wpis w dzienniku (rozdziały 6 i 7).
4. `uv run quantlab plan`: co dalej. Powtarzaj, aż wszystkie kroki będą w stanie `done`.

Dla obecnych hipotez krypto kroki ręczne idą w tej kolejności: najpierw holdouty `mean_reversion_v1`, `pairs_v1` i `momentum_select_v1` (między sobą w dowolnej kolejności), a dopiero potem `portfolio_v1`. Holdout `momentum_voltarget_v1` nie jest składnikiem portfela i nie czeka na żaden inny; tak samo oba holdouty na ETF-ach. Portfel ma ten sam zakres holdoutu co składniki. Otwarty wcześniej zdradziłby coś o wynikach nieotwartych holdoutów składników. `open-holdout portfolio_v1` odmówi, dopóki składniki nie są otwarte, a plan poda, na które czeka.

## 5. Wyniki treningu: co dostajesz i jak je czytać

Każdy przebieg treningowy daje trzy rzeczy:

- podsumowanie w konsoli;
- raport `reports/<id>.html`;
- zapis w magazynie wyników, widoczny w aplikacji.

Przebieg treningowy nigdy nie czyta danych z zakresu holdoutu.

Co jest w wynikach:

- **Trzy modele kosztów** na tych samych sygnałach: `zero-cost` (wynik brutto), `naive` (sama prowizja) i `realistic` (prowizja plus poślizg skalowany zmiennością). Główny jest model realistyczny i na nim liczone jest wszystko poniżej.
- **Metryki:** CAGR, Sharpe, Sortino, Calmar, max drawdown.
- **Bramka in-sample** zamrożona w definicji. Zwykle jest to walk-forward w oknach rocznych. W `momentum_select_v1` jest to CPCV: wiele ścieżek spoza próby z purgingiem i embargo.
- **Test istotności.** Test permutacyjny sprawdza, czy wyczucie momentu jest lepsze od losowego sparowania pozycji ze zwrotami. W `xsmom_v1` test losowych portfeli sprawdza, czy selekcja spółek jest lepsza od losowego wyboru z tego samego przekroju.
- **Korekta na wielokrotne testowanie:** PSR, deflated Sharpe (DSR) liczony przy wszystkich próbach na tych samych danych, łącznie z usuniętymi definicjami, oraz PBO.
- **Reżimy zmienności, stress test i rejestr transakcji.** Mają charakter opisowy.
- **Diagnostyka zależna od hipotezy:**
  - `pairs_v1`: kointegracja;
  - `momentum_select_v1`: historia wyboru parametru i PBO siatki;
  - `portfolio_v1`: korelacje i wagi rękawów oraz porównanie reguł alokacji (sekcja „Diagnostyka treningu");
  - `momentum_voltarget_v1` i `momentum_voltarget_multiasset_v1`: skala pozycji każdego instrumentu (średnia, najniższa, najwyższa, udział dni na limicie) i porównanie z tym samym momentum bez skalowania: Sharpe netto, zmienność i max drawdown na tym samym oknie.
- **P&L per klasa aktywów i per instrument** w rejestrze transakcji: skąd pochodzi wynik. Na ETF-ach odpowiada na pytanie, czy efekt działa w każdej klasie, czy tylko w części. Opisowo, bez testu istotności per klasa.
- **Zwroty ponad gotówkę** na uniwersum z instrumentem gotówkowym (`multiasset-etf`, gotówka BIL). Nagłówek przebiegu mówi to wprost (`Returns: above cash (BIL)`). Ceny w rejestrze transakcji są wtedy w jednostkach gotówki, nie notowaniami.

**Na co patrzeć przed otwarciem holdoutu.** Przegląd służy zrozumieniu wyniku i zanotowaniu obserwacji, a nie poprawianiu hipotezy. Definicja jest zamrożona: każda zmiana parametrów po obejrzeniu wyników to nowa hipoteza (rozdział 10). Pytania pomocnicze:

- Czy bramka in-sample przeszła, i jak wyraźnie? Na przykład: ile okien walk-forward jest na granicy?
- Ile wyniku zabierają realistyczne koszty?
- Czy deflated Sharpe jest wyraźnie dodatni po uwzględnieniu wszystkich prób?
- Czy wynik nie opiera się na jednym roku, jednym reżimie albo kilku transakcjach?

Werdykt rozstrzyga zamrożone kryterium, więc przegląd go nie zmienia. Pomaga za to napisać rzetelny wpis w dzienniku. Jeśli bramka in-sample nie przeszła, status końcowy będzie `rejected` bez względu na holdout. Czy mimo to otworzyć holdout, żeby opisać zachowanie strategii poza próbą, decydujesz Ty.

## 6. Otwarcie holdoutu (krok ręczny, jednorazowy)

```powershell
uv run quantlab open-holdout mean_reversion_v1
```

Co się dzieje:

1. Komenda sprawdza, czy definicja jest zacommitowana i niezmieniona. W przypadku portfela sprawdza też, czy holdouty składników są otwarte.
2. Pobiera dane z zakresu holdoutu i liczy wynik z modelem realistycznym oraz test istotności. Potem stosuje zamrożone kryterium.
3. Zapisuje wynik w `config/holdout/<id>.opened.json`, razem z commitem zamrożenia, commitem otwarcia i czasem otwarcia. Odświeża też rejestr w magazynie.
4. Drukuje wynik i werdykt.

Werdykt holdoutu według kryterium wszystkich obecnych hipotez:

- Sharpe netto ≤ 0: `rejected`;
- Sharpe > 0, ale p ≥ 0,1: `inconclusive`;
- Sharpe > 0 i p < 0,1: `passed`.

Status końcowy hipotezy łączy dwie bramki:

- `confirmed` tylko przy zaliczonej bramce in-sample i zaliczonym holdoucie;
- `rejected`, gdy którakolwiek bramka nie przeszła;
- `inconclusive` we wszystkich pozostałych przypadkach.

Status liczy kod, nie badacz.

Holdout otwiera się **dokładnie raz**. Kolejne wywołanie `open-holdout` pokazuje tylko zapisany wynik (`Holdout already opened … not re-running`). Nie usuwaj pliku `.opened.json`, żeby otworzyć holdout ponownie: to unieważnia całą walidację.

Zapis otwarcia commitujesz i wypychasz od razu:

```powershell
git add config/holdout/mean_reversion_v1.opened.json
git commit -m "Record mean_reversion_v1 holdout opening"
git push
```

Opisy commitów są w repozytorium po angielsku, dokumentacja po polsku.

## 7. Wpis w dzienniku badawczym

Każda hipoteza z otwartym holdoutem dostaje wpis w [RESEARCH_LOG.md](RESEARCH_LOG.md), bez względu na wynik. Format jest opisany na początku pliku, a wzorem jest wpis `momentum_v1`.

Nagłówek musi mieć postać `## RRRR-MM-DD — <id hipotezy>…`, z długą pauzą (—) otoczoną spacjami. Po tym nagłówku plan rozpoznaje, że wpis istnieje. Najprościej skopiować nagłówek istniejącego wpisu i podmienić datę oraz nazwę:

```
## 2026-10-01 — mean_reversion_v1: krótkoterminowe odwrócenie na BTC-USDT i ETH-USDT
```

Treść wpisu, po polsku:

- **Hipoteza**: co testujemy.
- **Metodologia**: dane, zakresy dat, koszty, walidacja, linki do zamrożonej definicji i zapisu otwarcia.
- **Wynik**: liczby z treningu i osobno z holdoutu.
- **Wniosek**: `confirmed`, `rejected` albo `inconclusive`, z uzasadnieniem, ograniczeniami i tym, co dalej.

Liczby przepisuj z raportu i zapisu otwarcia, nie licz ich ręcznie. Wpis opisuje wyniki historyczne i ryzyko, bez rekomendacji inwestycyjnych w rodzaju „kup" czy „zwiększ". We wpisie `portfolio_v1` porównaj wynik portfela z wynikami składników.

Na koniec `git add docs/RESEARCH_LOG.md`, `git commit`, `git push` i `uv run quantlab plan`.

## 8. Akcje: `xsmom_v1` (S&P 500)

Ta ścieżka trwa najdłużej, dni albo tygodnie, przez limity darmowego Tiingo. Najlepiej zacząć ją po zamknięciu hipotez krypto. Dopóki plik `sp500.yaml` nie jest zacommitowany, trening `xsmom_v1` jest zablokowany, a `plan --run` robi całą resztę.

1. **Budowa uniwersum** (`universe:sp500`, krok automatyczny; `plan --run` wykonuje go sam):

   ```powershell
   uv run quantlab build-universe
   ```

   Komenda:
   - czyta zapisaną rewizję strony Wikipedii *List of S&P 500 companies*;
   - odtwarza skład indeksu wstecz do 2000 r.;
   - zapisuje `src/quantlab/config/universes/sp500.yaml`;
   - drukuje raport sprzeczności w tabeli zmian składu.

2. **Przegląd raportu** (`review:sp500`, krok ręczny). Zmiany tickerów, np. `FB` → `META`, dopisz do `src/quantlab/config/universes/sp500-renames.yaml` i zbuduj uniwersum ponownie. Poprawiaj **tylko** to, co wskazuje raport budowy. Nie dobieraj spółek pod wynik: skład jest częścią pre-rejestracji.

3. **Commit obu plików**, gdy masz czas na długie pobieranie:

   ```powershell
   git add src/quantlab/config/universes/sp500.yaml src/quantlab/config/universes/sp500-renames.yaml
   git commit -m "Build the S&P 500 point-in-time universe"
   ```

   Od tej chwili trening `xsmom_v1` jest w stanie `pending`, a plan dodaje sprawdzenie `check:tiingo` (klucz i dostęp).

4. **Trening z kluczem Tiingo:** przez `plan --run` albo bezpośrednio `uv run quantlab run xsmom_v1 --tear-sheet reports/xsmom_v1.html`.
   - **Czas pobierania.** Domyślny odstęp między zapytaniami to 90 s, a każdy ticker to dwa zapytania. Około 875 tickerów w treningu daje ok. 44 godzin, holdout dokłada ok. 16 godzin.
   - **Limit darmowego tieru.** Tiingo pozwala na ok. 500 unikalnych symboli miesięcznie, więc całość zajmie 2–3 miesiące. Alternatywą jest jeden miesiąc płatnego tieru; wtedy odstęp skraca się zmienną `TIINGO_REQUEST_INTERVAL_SECONDS`. Szczegóły i zastrzeżenia są w [DATA-SOURCES.md](DATA-SOURCES.md).
   - **Wznawianie.** Przerwane pobieranie (limit, zamknięte okno, restart komputera) wznawia się od miejsca przerwania, bo odpowiedzi są w `data/cache/`. Wyczerpany limit kończy komendę jednym komunikatem; wystarczy uruchomić ją ponownie później.
   - **Pokrycie cenami.** Przebieg drukuje udział dni członkostwa z ceną i członków bez żadnej ceny w źródle.

5. **Holdout, commit i wpis w dzienniku** jak w rozdziałach 6 i 7.

## 9. Wyniki w aplikacji (prawdziwe dane)

```powershell
cd presentation\web
npm ci
npm run build
cd ..\..
dotnet run --project presentation/QuantLab.Api
```

Pod http://localhost:5080 działa ta sama aplikacja co w trybie demo, ale czyta `results/` z Twoich przebiegów. Nowy przebieg widać po odświeżeniu strony, bez restartu API. Hipoteza bez przebiegu pokazuje komunikat „No runs yet" z komendą, która przebieg utworzy.

`npm ci` i `npm run build` trzeba powtarzać tylko po zmianach w `presentation/web`. Przy pracy nad interfejsem wygodniejszy jest `npm run dev` w `presentation\web`: serwer Vite na porcie 5173 z przekierowaniem `/api` do API na 5080.

API udostępnia też endpointy JSON tylko do odczytu: `/api/health`, `/api/hypotheses`, `/api/hypotheses/{id}`, `/api/hypotheses/{id}/equity` i `/api/hypotheses/{id}/trades`.

## 10. Pozostałe komendy

| Komenda | Co robi |
|---|---|
| `uv run quantlab registry` | odświeża rejestr hipotez w magazynie na podstawie definicji i zapisów otwarć, bez pobierania danych; drukuje tabelę statusów |
| `uv run quantlab trials <id>` | wszystkie próby na danych hipotezy: Sharpe, PSR i DSR każdej oraz PBO wyboru jednej z nich; tylko okresy treningowe |
| `uv run quantlab compare-engines <id>` | opisowe porównanie silnika wektorowego z silnikiem event-driven (egzekucja zleceń) na okresie treningowym |
| `uv run quantlab check-source binance` | czy Binance odpowiada z tego komputera |
| `uv run quantlab check-source tiingo` | czy jest klucz Tiingo i czy API odpowiada |
| `uv run quantlab run <id> --contrast <inny_id>` | dodatkowo korelacja dziennych zwrotów netto z inną hipotezą |
| `uv run quantlab --help`, `uv run quantlab <komenda> --help` | opis komend i opcji |

Bez nazwy hipotezy `run`, `open-holdout`, `trials` i `compare-engines` działają na `momentum_v1`.

## 11. Nowa hipoteza

Gdy zechcesz sprawdzić nowy pomysł, także wariant istniejącej hipotezy wymyślony po obejrzeniu jej wyników:

1. Zapisz, co i dlaczego ma działać, zanim spojrzysz na dane.
2. Skopiuj najbliższą definicję z `config/holdout/` pod nową nazwą, np. `momentum_v2.yaml`. Ustaw w niej:
   - `hypothesis`;
   - okres treningowy i zakres holdoutu;
   - parametry;
   - kryterium sukcesu.

   Dostępne strategie: `time_series_momentum`, `short_term_reversal`, `pairs_spread`, `cross_sectional_momentum`, `time_series_momentum_selected`, `strategy_portfolio`, `time_series_momentum_vol_target`.

   Dostępne uniwersa: `mvp-crypto`, `multiasset-etf` (ETF-y, zwroty ponad gotówkę BIL), a po budowie także `sp500`. Okna definicji (`lookback_days`, `window_days` itp.) liczą sesje rynku: 365 w roku na krypto, 252 na ETF-ach i akcjach.
3. Zakres holdoutu wybierz z danych, których w tej sprawie jeszcze nie oglądałeś. Na przykład holdout 2024–2025 na BTC i ETH jest już zużyty przez `momentum_v1`.
4. **Zacommituj definicję przed pierwszym przebiegiem.** `quantlab run` odrzuca definicję niezacommitowaną albo zmienioną po commicie, zanim pobierze jakiekolwiek dane.
5. Uruchom `uv run quantlab plan`: nowa hipoteza pojawi się w planie. Hipotezy na tych samych danych wrócą do stanu `pending` (`new trials on its data: …`), bo nowa próba zmienia ich deflated Sharpe. `plan --run` je przeliczy.

Zamrożonych definicji się nie edytuje: każda zmiana po zamrożeniu to nowa hipoteza. Usunięta definicja nadal liczy się jako próba, bo rejestr prób czyta historię gita. Nowa strategia albo nowe źródło danych to już zmiana kodu (interfejsy `Strategy` i `DataProvider`, patrz [ARCHITECTURE.md](ARCHITECTURE.md)).

## 12. Gdy coś nie działa

| Objaw | Przyczyna i co zrobić |
|---|---|
| `check:python` kończy się błędem | Natywna paczka (DuckDB albo statsmodels) nie działa na tym procesorze, który nie ma AVX2. Nie uruchamiaj przebiegów i zapisz komunikat testu: naprawa wymaga zmiany wersji paczki w repozytorium. |
| `check:dotnet` w stanie `blocked` | `dotnet` nie jest na ścieżce. Jest potrzebny tylko do aplikacji: zainstaluj .NET 10 SDK albo pomiń ten krok. |
| `binance: not reachable - …` | Brak sieci, proxy albo blokada regionalna Binance. Po zmianie sieci sprawdź `uv run quantlab check-source binance`. |
| `tiingo: not reachable - TIINGO_API_KEY is not set` | Ustaw klucz (rozdział 2.3) w tym samym oknie, w którym uruchamiasz plan. |
| `<plik>.yaml has uncommitted changes; commit it first` | Zamrożona definicja w `config/holdout/` ma lokalne zmiany. Przywróć ją komendą `git restore config/holdout/<plik>.yaml`, bo zamrożonych definicji się nie zmienia. Nowa definicja wymaga commitu. |
| Przebieg w stanie `pending`, choć był już uruchamiany | Plan podaje powód: inną wersję schematu magazynu albo nowe próby na tych samych danych. Uruchom `plan --run`. |
| `open-holdout portfolio_v1` odmawia | Holdouty składników nie są jeszcze otwarte; komunikat i plan wymieniają, które. |
| `Holdout already opened … not re-running` | Holdout był już otwarty, więc komenda pokazuje zapisany wynik. Tak ma być. |
| `log:<id>` nadal w stanie `pending` mimo wpisu | Nagłówek wpisu nie ma postaci `## RRRR-MM-DD — <id>`. Sprawdź długą pauzę (—), spacje wokół niej i kodowanie UTF-8. |
| `xsmom_v1` przerwany komunikatem o limicie | Wyczerpany limit Tiingo. Uruchom ponownie później; pobieranie wznowi się z cache. |
| `plan --run` zatrzymuje się na `universe:sp500` | Wikipedia nie odpowiada. Przebiegi krypto uruchom bezpośrednio komendami z planu. |
| API nie startuje na porcie 5080 | Port jest zajęty: zamknij poprzednią instancję API (Ctrl+C w jej oknie). |
| `http://localhost:5080` nie pokazuje aplikacji | Interfejs nie jest zbudowany: uruchom `npm ci` i `npm run build` w `presentation\web`, potem zrestartuj API. |

## 13. Zasady, które chronią wiarygodność wyników

- Nie zmieniaj zamrożonych definicji ani kryteriów po zobaczeniu wyników.
- Każdy holdout otwieraj raz, po przeglądzie treningu, w kolejności z planu.
- Nie usuwaj i nie edytuj plików `.opened.json`.
- Wyniki `rejected` i `inconclusive` opisuj w dzienniku tak samo starannie jak `confirmed`. To pełnoprawne wyniki.
- Nie commituj danych: `data/raw/`, `data/cache/`, `results/` i `reports/` są celowo poza gitem ze względu na licencje źródeł.
- Raporty i wpisy opisują historyczne zachowanie strategii i ryzyko. Nie są poradą inwestycyjną.
