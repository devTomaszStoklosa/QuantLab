# lab-foundation - Fundament repo: szkielet, dostęp do danych, storage

Status: Ready for dev
Owner role: PO
Upstream: -
Links: docs/ROADMAP.md

## Problem

Zanim powstanie pierwsza hipoteza (`q1-momentum-research-mvp`), potrzebny jest wspólny fundament: szkielet projektu, sposób pobierania i cache'owania danych rynkowych w kanonicznym schemacie, i miejsce zapisu wyników eksperymentów. Bez tego każdy kolejny epik budowałby własny dostęp do danych i własny format zapisu — wyniki byłyby nieporównywalne.

## Outcome

Primary metric: czas od „chcę dane dla instrumentu X w zakresie dat" do gotowej serii `PriceBar` w pamięci — jedna funkcja, bez ręcznego parsowania CSV za każdym razem.
Guardrail metric: 0 pobrań tych samych danych z sieci przy powtórnym uruchomieniu (cache trafia za każdym razem, gdy zakres już pobrany).

## User story

Jako budujący platformę chcę mieć gotowy dostęp do danych rynkowych w kanonicznym schemacie i miejsce zapisu wyników, żeby epik `q1-momentum-research-mvp` mógł zacząć od razu od sygnału i backtestu, nie od parsowania CSV.

## Acceptance criteria

- AC-1: Given świeży klon repo i zainstalowane `uv`, when uruchamiam `uv sync` i `uv run pytest -q`, then testy przechodzą bez sieci.
- AC-2: Given instrument i zakres dat, when wywołuję `StooqProvider.fetch`, then dostaję listę `PriceBar` w kanonicznym schemacie, posortowaną chronologicznie, bez duplikatów dat.
- AC-3: Given te same instrument i zakres dat wywołane drugi raz, when `StooqProvider.fetch` uruchamia się ponownie, then dane pochodzą z cache na dysku, bez nowego żądania HTTP.
- AC-4: Given nieprawidłowy symbol instrumentu, when wywołuję `fetch`, then dostaję czytelny błąd zamiast wyjątku z biblioteki HTTP.
- AC-5: Given lista `PriceBar`, when zapisuję ją przez `core.storage`, then dane trafiają do DuckDB/Parquet i dają się odczytać z powrotem bez utraty precyzji.
- AC-6: Given statyczna definicja uniwersum w configu, when wywołuję `Universe.load`, then dostaję listę instrumentów z metadanymi (symbol, klasa aktywów, waluta).
- AC-7: Given zależności natywne projektu (numpy, pandas, duckdb), when uruchamiam testy, then test środowiska potwierdza, że każda działa na tej maszynie (bez AVX2).
- AC-8: Given pusty CLI `quantlab`, when uruchamiam `uv run quantlab --version`, then dostaję numer wersji.

## Out of scope

- Jakakolwiek strategia, sygnał czy silnik backtestu — to `q1-momentum-research-mvp`.
- Point-in-time uniwersum (zmienny skład w czasie) — to `q5-equities-cross-section`.
- Drugi dostawca danych (Binance) — dodawany w razie potrzeby przy rozszerzeniu krypto.

## Priority

Must have — blokuje wszystkie kolejne epiki.

## Dependencies and risks

- Ryzyko: paczka natywna (`duckdb`, `numpy`, `pandas`) nie działa bez AVX2 na tej maszynie — mitygacja: test środowiska jako pierwszy krok.
- Ryzyko: Stooq zmienia format CSV albo blokuje zapytania bez ostrzeżenia — dostawca jest nieoficjalny; mitygacja: adapter za interfejsem `DataProvider`, łatwa podmiana.
- Ryzyko: przeinżynierowanie fundamentu przed poznaniem realnych potrzeb `q1` — mitygacja: tylko to, co wymagają AC powyżej, reszta rośnie razem z kolejnymi epikami.

## Open questions

| # | Question | Owner | Due |
|---|---|---|---|
| 1 | Stooq czy inny dostawca EOD jako pierwszy adapter — potwierdzić dostępność i format dla wybranego koszyka ETF/FX przed S2 | Tomasz | przed lab-foundation S2 |
| 2 | Dokładny koszyk instrumentów MVP (które ETF-y/FX) | Tomasz | przed q1-momentum-research-mvp |
