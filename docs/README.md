# Dokumentacja QuantLab

QuantLab to platforma do systematycznych badań inwestycyjnych: hipoteza, dane, sygnał, backtest, koszty, walidacja poza próbą, ryzyko, atrybucja, wniosek. Cel to rzetelny proces badawczy, nie jedna działająca strategia; odrzucona hipoteza opisana uczciwie jest pełnoprawnym wynikiem.

Ten plik jest wejściem do całej dokumentacji. Dokumenty są po polsku, kod, identyfikatory i komentarze w kodzie po angielsku.

## Ścieżki czytania

| Jesteś… | Zacznij od | Potem |
|---|---|---|
| osobą, która chce zrozumieć, czym jest projekt | [PRODUCT.md](PRODUCT.md) | [ROADMAP.md](ROADMAP.md), [RESEARCH_LOG.md](RESEARCH_LOG.md) |
| badaczem uruchamiającym hipotezy | [INSTRUKCJA.md](INSTRUKCJA.md) | [CLI-REFERENCE.md](CLI-REFERENCE.md), [DATA-SOURCES.md](DATA-SOURCES.md) |
| programistą rozwijającym silnik | [DEVELOPER-GUIDE.md](DEVELOPER-GUIDE.md) | [ARCHITECTURE.md](ARCHITECTURE.md), [TESTING-AND-CI.md](TESTING-AND-CI.md) |
| programistą warstwy prezentacji | [PRESENTATION.md](PRESENTATION.md) | [RESULTS-STORE.md](RESULTS-STORE.md) |
| recenzentem metodologii | [adr/](adr/) | [GLOSSARY.md](GLOSSARY.md), [RESEARCH_LOG.md](RESEARCH_LOG.md) |

## Spis dokumentów

| Dokument | Zawartość |
|---|---|
| [PRODUCT.md](PRODUCT.md) | opis produktu: problem, odbiorcy, funkcje, czego produkt nie robi |
| [INSTRUKCJA.md](INSTRUKCJA.md) | instrukcja obsługi krok po kroku, instalacja na Windows, praca na prawdziwych danych |
| [ARCHITECTURE.md](ARCHITECTURE.md) | zasady, warstwy, układ repozytorium, mapa zależności, kontrakty modułów |
| [DEVELOPER-GUIDE.md](DEVELOPER-GUIDE.md) | przewodnik dla programisty: moduły pakietu `quantlab`, przepływ badania, jak dodać strategię, model kosztów, walidator, źródło danych |
| [CLI-REFERENCE.md](CLI-REFERENCE.md) | wszystkie komendy `quantlab`: argumenty, opcje, skutki uboczne |
| [RESULTS-STORE.md](RESULTS-STORE.md) | magazyn wyników (Parquet): tabele, kolumny, wersjonowanie schematu |
| [PRESENTATION.md](PRESENTATION.md) | warstwa prezentacji: API ASP.NET Core, aplikacja React, tryb demo, fixtures |
| [TESTING-AND-CI.md](TESTING-AND-CI.md) | warstwy testów, CI, konwencje ticketów, branchy i PR |
| [DATA-SOURCES.md](DATA-SOURCES.md) | źródła danych, licencje, granica publicznego repozytorium |
| [ROADMAP.md](ROADMAP.md) | epiki, kolejność, zakres MVP, stan ticketów |
| [RESEARCH_LOG.md](RESEARCH_LOG.md) | dziennik badawczy: wyniki hipotez |
| [GLOSSARY.md](GLOSSARY.md) | słownik pojęć |
| [adr/](adr/) | decyzje architektoniczne (ADR-0001 … ADR-0010) |
| [specs/](specs/) | artefakty epików: `01-story`, `02-spec`, `03-design` |

## Szybki start

```bash
uv sync
uv run pytest -q                                                       # testy silnika, bez sieci
(cd presentation/web && npm ci && npm run build)
dotnet run --project presentation/QuantLab.Api --launch-profile demo   # http://localhost:5080
```

Aplikacja w trybie demo działa na syntetycznym magazynie wyników. Przebiegi na prawdziwych danych opisuje [INSTRUKCJA.md](INSTRUKCJA.md).

## Zasady, które obowiązują w całym projekcie

1. Hipoteza nie jest `confirmed` bez walk-forward i bez zamrożonego holdoutu otwartego raz ([ADR-0004](adr/0004-validation-first-frozen-holdout.md)).
2. Raporty opisują wyniki historyczne, nie rekomendują transakcji ([ADR-0005](adr/0005-descriptive-reports-no-investment-advice.md)).
3. Tylko darmowe źródła danych; ceny i wyniki z cenami zostają poza publicznym repozytorium ([ADR-0009](adr/0009-private-repo-free-tiingo-plan.md), [ADR-0010](adr/0010-public-repo-data-boundary.md)).
4. .NET i React tylko w warstwie prezentacji, rdzeń obliczeniowy to Python ([ADR-0006](adr/0006-dotnet-react-presentation-layer-only.md)).
