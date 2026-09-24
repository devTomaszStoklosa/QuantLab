# q7-dotnet-react-presentation - Warstwa prezentacji: API ASP.NET Core i aplikacja React nad wynikami silnika

Status: Ready for dev
Owner role: PO
Upstream: docs/adr/0006-dotnet-react-presentation-layer-only.md, presentation/design-system/
Links: docs/ROADMAP.md, docs/ARCHITECTURE.md

## Problem

Wynik każdej hipotezy istnieje dziś w dwóch miejscach: w wydruku `quantlab run` w terminalu i w statycznym tear-sheecie HTML, jednym na hipotezę. Nie da się:

1. **zobaczyć wszystkich hipotez obok siebie** — statusu, stanu holdoutu i dowodów — bez uruchamiania każdej z osobna;
2. **przejrzeć rejestru transakcji** — tear-sheet pokazuje tylko cięcia P&L, a pojedyncze transakcje (setki na przebieg) nie mają filtra ani sortowania;
3. **pokazać kompetencji .NET i React** zapowiedzianych w [ADR-0006](../../adr/0006-dotnet-react-presentation-layer-only.md) — design system QuantForge (`presentation/design-system/`) istnieje, ale nie ma aplikacji, która by go używała.

Do tej pory epik był zablokowany: środowisko chmurowe nie pobierało .NET SDK ze stron Microsoftu. Zmiana z 2026-09-24: .NET 10 SDK (`dotnet-sdk-10.0`, 10.0.1xx) jest w archiwum Ubuntu, dostępnym w tym środowisku — epik da się zbudować i przetestować bez danych rynkowych.

## Outcome

Primary metric: lokalna aplikacja (API ASP.NET Core + React) pokazuje rejestr hipotez, dowody każdej hipotezy (to samo, co tear-sheet) i rejestr transakcji z filtrem i sortowaniem — wyłącznie z wyników zapisanych przez `quantlab`.
Guardrail metric: żadna liczba finansowa nie jest liczona poza Pythonem (testy API porównują odpowiedzi z bezpośrednim odczytem magazynu wyników, liczba w liczbę); bramki Pythona (`ruff`, `pytest`) i wyniki istniejących hipotez bez zmian; żadne surowe ceny ani wyniki na danych rynkowych nie trafiają do repozytorium.

## User story

Jako badacz (i jako recenzent portfolio) chcę przeglądać hipotezy, ich dowody i transakcje w interaktywnej aplikacji, żeby w kilka sekund zobaczyć, co zostało przetestowane, z jakim wynikiem i dlaczego — bez czytania wydruków z terminala, a przy tym bez żadnej liczby policzonej poza silnikiem Pythona.

## Acceptance criteria

- AC-1 (magazyn wyników): Given zakończony `quantlab run`, when przebieg się kończy, then w `results/<hipoteza>/` leżą tabele Parquet z wszystkim, co pokazuje tear-sheet, oraz z rejestrem transakcji — z wersją schematu; odczyt zapisanych tabel daje te same liczby, które policzył przebieg.
- AC-2 (rejestr hipotez): Given zacommitowane definicje w `config/holdout/`, when `quantlab` odświeża rejestr, then `results/hypotheses.parquet` wymienia każdą hipotezę — także bez przebiegu — ze statusem ustalonym przez Pythona, commitem zamrożenia i stanem holdoutu (zapieczętowany albo wynik jednorazowego otwarcia).
- AC-3 (API): Given magazyn wyników, when wołam API, then dostaję rejestr, dowody hipotezy, krzywą kapitału i stronicowany rejestr transakcji z filtrem i sortowaniem — liczby identyczne z magazynem; API tylko czyta; nieznana hipoteza to 404, hipoteza bez przebiegu to jawny stan „brak przebiegu", nie zera.
- AC-4 (rejestr w UI): Given API, when otwieram aplikację, then widzę rejestr hipotez z zakładkami po statusie, stanem pieczęci holdoutu i miniaturą krzywej kapitału — w design systemie QuantForge.
- AC-5 (hipoteza w UI): Given hipoteza z przebiegiem, when ją otwieram, then widzę werdykt albo stan „w toku", metryki per model kosztów, krzywą kapitału z obsunięciem, walk-forward, test permutacyjny, reżimy, wielokrotne testowanie, zapis holdoutu i rejestr transakcji z filtrem i sortowaniem; dane syntetyczne są jawnie oznaczone.
- AC-6 (środowisko): Given świeży klon, when uruchamiam komendy z README, then `dotnet test` i `npm test` przechodzą w chmurze i na maszynie deweloperskiej (Windows 10, bez AVX2), a natywna biblioteka DuckDB w .NET ma test środowiska jak zależności natywne Pythona.

## Out of scope

- **Zapis z UI**: rejestracja hipotezy, uruchamianie przebiegu, otwarcie holdoutu. Definicja hipotezy jest commitem w gicie, a otwarcie holdoutu to jednorazowy zapis commitowany przez CLI — UI pokazuje stan i komendę, nie wykonuje jej. ADR-0006: .NET nie wywołuje Pythona.
- Autoryzacja, wdrożenie, hosting — aplikacja lokalna.
- Sekcja „Inputs" z design systemu (dane i uniwersa, sygnały, modele kosztów) i ekran dziennika badawczego — dziennik zostaje w `docs/RESEARCH_LOG.md`.
- Historia przebiegów — magazyn trzyma ostatni przebieg każdej hipotezy (tak jak tear-sheet).
- Rozkład zerowy testu permutacyjnego jako histogram — walidator go nie zwraca; UI pokazuje liczby, jak tear-sheet.
- Stress test w UI — nie ma go w tear-sheecie; wraca, jeśli okaże się potrzebny.

## Priority

Should have — jedyny epik z niezablokowaną pracą: `q2`, `q3`, `q4` i `q6` czekają na lokalne przebiegi (Binance), `q5` na decyzję o źródle danych akcji.

## Dependencies and risks

- Zależy od `q1` (tear-sheet i jego model danych), `q3`-M1 (definicje w `config/holdout/`), `q4` (diagnostyka par) i `q6` (rejestr prób, PSR, DSR).
- **Dwa nowe stosy na maszynie deweloperskiej**: .NET 10 SDK i Node.js 22 LTS trzeba zainstalować lokalnie. Wsparcie .NET 10 dla Windows 10 (koniec wsparcia systemu w 10.2025) — do potwierdzenia `dotnet --info` i `dotnet test`.
- **Natywna biblioteka DuckDB w .NET** (DuckDB.NET) na maszynie bez AVX2 — ten sam silnik DuckDB co w Pythonie, który już tam działa; test środowiska w projekcie testów .NET, jak `tests/test_environment.py`.
- **Licencja danych**: rejestr transakcji zawiera ceny wejścia i wyjścia z Binance — `results/` jest ignorowany przez gita. Testy .NET i tryb demo UI korzystają z syntetycznego magazynu wygenerowanego z danych syntetycznych, z hipotezami o nazwach `demo_*`, żeby nie dało się go pomylić z wynikiem badania.
- **Dryf kontraktu Python → .NET**: schemat Parquet zmienia się po stronie Pythona, a .NET czyta starą wersję. Wersja schematu w magazynie, test Pythona pilnujący aktualności syntetycznego magazynu i testy .NET na tym samym pliku.

## Open questions

Brak blokujących. Decyzje przyjęte przy pisaniu (do zmiany na prośbę właściciela): .NET 10 LTS, React 18 (wersja, na której zbudowany jest design system), aplikacja tylko do odczytu, `quantlab run` zawsze zapisuje wynik do `results/`.
