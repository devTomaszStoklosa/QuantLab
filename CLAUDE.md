# CLAUDE.md

Przewodnik dla Claude Code w tym repozytorium.

## Czym jest to repo

Platforma do systematycznych badań inwestycyjnych (hipoteza, dane, sygnał, backtest, koszty, walidacja, ryzyko, atrybucja, wniosek), budowana jako projekt portfolio pod role Quantitative Developer / Quantitative Analyst / Systematic Trading Research. Najważniejsze: proces badawczy, nie jedna działająca strategia — odrzucona hipoteza opisana rzetelnie jest tak samo wartościowym wynikiem jak potwierdzona.

## Konwencje językowe

- Dokumentacja, dziennik badawczy, raporty — **polski**.
- Kod, identyfikatory, komentarze w kodzie, commit messages — **angielski**.

## Praca z RoleKit

- Plugin leży w `C:\Users\Tomasz\Desktop\AI Lab\rolekit`, nie jest zainstalowany globalnie. Start sesji: `claude --plugin-dir "C:\Users\Tomasz\Desktop\AI Lab\rolekit"`.
- Konfiguracja: `.claude/rolekit.json`. Artefakty: `docs/specs/<epik>/01-story.md`, `02-spec.md`, `03-design.md`. ADR-y: `docs/adr/NNNN-tytul.md`.
- Linię `Status:` w nagłówku artefaktu czyta skrypt RoleKit — nie zmieniaj jej formatu.
- `gates.dev` i `gates.qa` są `null`, dopóki epik `lab-foundation` nie doda pierwszego testu. Potem ustaw: dev = `uv run ruff check . && uv run pytest -q`, qa = `uv run pytest -q`.
- Bramki RoleKit wymagają repozytorium git (odcisk `git status` + `git diff`).

## Komendy (obowiązują od epiku lab-foundation)

| Cel | Komenda |
|---|---|
| Zależności | `uv sync` |
| Testy | `uv run pytest -q` |
| Lint | `uv run ruff check .` |
| Formatowanie | `uv run ruff format .` |
| CLI | `uv run quantlab <komenda>` |
| Testy API .NET (`q7`) | `dotnet test --solution presentation/QuantLab.Presentation.slnx` |
| API na syntetycznym magazynie | `dotnet run --project presentation/QuantLab.Api --launch-profile demo` |
| UI React (`q7`, w `presentation/web`) | `npm ci`, `npm test`, `npm run build` (typecheck + build do `dist/`) |

## Twarde zasady

1. **Walidacja przed wnioskiem.** Hipoteza nie jest „confirmed" bez walk-forward i bez zamrożonego holdoutu ustalonego przed uruchomieniem na danych testowych. „Rejected" i „inconclusive" to pełnoprawne wyniki, opisywane równie starannie.
2. **Ceny i zwroty w silniku: `float64` (numpy), nie `Decimal`.** Wektoryzacja na dużych seriach wymaga float64; błąd zaokrąglenia jest pomijalny wobec szumu rynkowego. `Decimal` tylko w końcowej księdze P&L pojedynczej transakcji, jeśli potrzebna księgowa ścisłość na poziomie raportu.
3. **Kod liczy, model objaśnia — jeśli LLM zostanie dodany (rozszerzenie, nie MVP).** Żadnych obliczeń finansowych w LLM; narracja nad liczbami policzonymi kodem.
4. **Bez rekomendacji inwestycyjnych.** Raporty opisują wyniki historyczne, ekspozycje i ryzyko — nie mówią „kup / sprzedaj / zwiększ".
5. **Dane cenowe:** licencja sprawdzona przed commitem do publicznego repo. Surowe dane nie trafiają do repo (gitignored), tylko syntetyczne fixtures do testów. Patrz [docs/DATA-SOURCES.md](docs/DATA-SOURCES.md).
6. **Zamrożony holdout.** Parametry hipotezy i zakres dat testowych commitowane przed pierwszym spojrzeniem na wynik na holdout — dyscyplina analogiczna do pre-rejestracji badania.
7. **Testy silnika backtestu obowiązkowe.** Golden-master na syntetycznych danych ze znanym z góry wynikiem (np. stały trend → policzalny z góry Sharpe), zanim wynik na realnych danych zyska wiarygodność.
8. **.NET i React tylko w warstwie prezentacji/orkiestracji** (czytają wyniki zapisane przez silnik Pythona z DuckDB/Parquet), nigdy w rdzeniu obliczeniowym — tam liczy się biegłość w pandas/numpy/statsmodels, nie w C#.
9. **SOLID** w kodzie, który piszesz — szczególnie interfejsy `Strategy`, `CostModel`, `Validator`, `DataProvider` jako podstawialne implementacje, nie rozrastające się `if`/`switch` po typie.

## Maszyna deweloperska

Fizycznie ta sama maszyna co pozostałe repozytoria właściciela: Intel i5-2500K (**bez AVX2**), 8 GB RAM, **bez GPU NVIDIA**, Windows 10. Środowisko `uv` tego repo jest jednak nowe i osobne — nie zakładaj, że wynik testu importu paczki natywnej w innym repo przenosi się tutaj; powtórz test importu dla każdej nowej zależności natywnej w `tests/test_environment.py`. Fine-tuning/trening ciężkich modeli — tylko w chmurze, jeśli w ogóle się pojawi (poza zakresem MVP).

## Windows

- PowerShell 5.1 nie ma `&&`; `Set-Content` domyślnie nie zapisuje UTF-8 — dodawaj `-Encoding utf8`.
- Duże heredoki w Git Bash kończą się błędem „unexpected EOF" — zapisz skrypt do pliku i uruchom.
- Launcher `py` domyślnie startuje inną wersję Pythona niż przypięta w repo — używaj `uv run`.

## Gdzie szukać

| Jeśli pracujesz nad… | Czytaj… |
|---|---|
| opisem produktu, funkcji, sposobu użycia | [docs/PRODUCT.md](docs/PRODUCT.md) |
| architekturą, modułami, modelem danych | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| kolejnością epików, zakresem MVP | [docs/ROADMAP.md](docs/ROADMAP.md) |
| źródłem danych, licencją | [docs/DATA-SOURCES.md](docs/DATA-SOURCES.md) |
| decyzjami architektonicznymi | [docs/adr/](docs/adr/) |
| konkretnym epikiem | `docs/specs/<epik>/` |
| wynikiem hipotezy | [docs/RESEARCH_LOG.md](docs/RESEARCH_LOG.md) |
