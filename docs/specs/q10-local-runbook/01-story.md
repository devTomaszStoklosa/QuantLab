# q10-local-runbook - Plan przebiegów lokalnych: co zostało, w jakiej kolejności, jedną komendą

Status: Ready for dev
Owner role: PO
Upstream: docs/specs/q9-strategy-portfolio/, docs/specs/q5-equities-cross-section/, docs/specs/q7-dotnet-react-presentation/
Links: docs/ROADMAP.md, docs/RESEARCH_LOG.md, README.md

## Problem

Wszystkie epiki `q1`–`q9` mają kod, a to, co zostało, dzieje się na maszynie deweloperskiej: środowisko chmurowe, w którym powstaje kod, nie ma dostępu do Binance, Tiingo ani Wikipedii. Lista kroków rozeszła się po ROADMAP, README i specyfikacjach:

1. **Sześć hipotez czeka na przebieg treningowy.** `momentum_v1` ma przebieg sprzed `q6`–`q9`: jeśli lokalny magazyn powstał przed schematem v3, jest nieczytelny dla aplikacji, a jego opisowy DSR liczy za mało prób na tych danych.
2. **Kolejność ma znaczenie i łatwo ją złamać.** `portfolio_v1` otwiera holdout dopiero po holdoutach trzech składników; `xsmom_v1` czeka na zbudowany i przejrzany `sp500.yaml` oraz klucz Tiingo; holdout otwiera się po przejrzeniu wyników treningu, nie w tej samej komendzie.
3. **Kroki nieodwracalne i ręczne giną wśród automatycznych.** Otwarcie holdoutu jest jednorazowe; zapis otwarcia trzeba zacommitować; wpis w dzienniku pisze badacz. Nic tego nie pilnuje.
4. **Środowisko Windows ma pułapki** (PowerShell 5.1 bez `&&`, DuckDB bez AVX2, `py` z innym Pythonem) — sprawdzane dziś ręcznie albo wcale.

## Outcome

Primary metric: `uv run quantlab plan` pokazuje na maszynie deweloperskiej każdy pozostały krok z jego stanem (zrobiony, do zrobienia, zablokowany — z powodem) i komendą, a `uv run quantlab plan --run` wykonuje wszystkie automatyczne kroki w poprawnej kolejności i zatrzymuje się na pierwszym błędzie.
Guardrail metric: żaden holdout nie zostaje otwarty, żaden plik nie zostaje zacommitowany i żaden wpis w dzienniku nie powstaje bez jawnego działania badacza.

## User story

Jako badacz na maszynie z dostępem do danych chcę jednej komendy, która wie, co już zrobiono i co zostało, żeby przejść od „kod gotowy" do wpisów w dzienniku bez przeglądania pięciu dokumentów i bez złamania kolejności, która chroni holdouty.

## Acceptance criteria

- AC-1 (stan): Given zacommitowane definicje, zapisy otwarć, magazyn wyników i pliki uniwersów, when uruchamiam `quantlab plan`, then widzę dla każdej hipotezy krok treningu, otwarcia holdoutu, commitu zapisu i wpisu w dzienniku ze stanem `done`, `pending` albo `blocked` i powodem blokady.
- AC-2 (kolejność): Given portfel ze składnikami bez otwartych holdoutów, when planuję, then otwarcie holdoutu portfela jest `blocked` z nazwami składników; given `xsmom_v1` bez zacommitowanego `sp500.yaml`, then jego trening jest `blocked` do przeglądu i commitu uniwersum.
- AC-3 (nieaktualne przebiegi): Given przebieg w magazynie ze starszym schematem albo z inną listą prób na tych samych danych, when planuję, then trening jest `pending` z powodem („nowe próby: …" / „schemat v2").
- AC-4 (wykonanie): Given `quantlab plan --run`, when są kroki automatyczne (sprawdzenia środowiska, budowa uniwersum, przebiegi treningowe), then wykonuję je po kolei, zatrzymuję się na pierwszym błędzie z kodem wyjścia 1 i na końcu wypisuję kroki ręczne, które zostały.
- AC-5 (kroki ręczne): Given kroki otwarcia holdoutu, commitu i wpisu w dzienniku, when `--run`, then nie wykonuję ich nigdy — pokazuję komendę i warunek (przejrzany trening).
- AC-6 (środowisko): Given maszyna deweloperska, when planuję, then plan zawiera sprawdzenia: natywne paczki Pythona (DuckDB, statsmodels), DuckDB w .NET (jeśli jest `dotnet`), dostęp do Binance (jeśli jakiś krok go potrzebuje), klucz Tiingo (jeśli jakiś krok go potrzebuje).

## Out of scope

- Automatyczne otwieranie holdoutów, commitowanie i pisanie wpisów w dzienniku (także generowanie ich treści) — decyzje badacza.
- Harmonogram (cron, Task Scheduler) i równoległe przebiegi — kroki idą po kolei na jednej maszynie.
- Zmiana wyników, definicji i werdyktów hipotez.

## Priority

Should have — wybrane przez Tomasza 2026-09-25 jako następny epik po `q1`–`q9`, żeby domknąć przebiegi lokalne.

## Dependencies and risks

- Zależy od rejestru prób (`q6`), magazynu wyników (`q7`), strażnika holdoutu (`q9`), budowy uniwersum (`q5`).
- **Ryzyko: plan uzna nieaktualny przebieg za zrobiony.** Mitygacja: krok treningu jest zrobiony tylko przy aktualnym schemacie i tej samej liście prób na tych samych danych.
- **Ryzyko: `--run` otworzy holdout.** Mitygacja: otwarcie holdoutu nie jest krokiem automatycznym w modelu (osobny rodzaj kroku), test to sprawdza.
- **Ryzyko: testy w CI sięgną do sieci.** Mitygacja: sprawdzenia sieci i wykonawca kroków są wstrzykiwane; testy ich nie wywołują.

## Open questions

Brak — decyzje narzędziowe w 03-design; reguły badawcze (holdout otwiera badacz, po przeglądzie) pozostają bez zmian.
