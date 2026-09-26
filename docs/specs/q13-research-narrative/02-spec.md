# q13-research-narrative - Specification

Status: Ready for dev
Owner role: BA
Upstream: 01-story.md

## Glossary

| Term | Meaning |
|---|---|
| Fakty | liczby i etykiety jednej hipotezy odczytane z magazynu wyników (`run`, `metrics`, `walk_forward`, `regimes`, `pnl_groups`) i z rejestru (definicja, status, zapis otwarcia holdoutu) |
| Narrator | składa z faktów sekcje tekstu po polsku; implementacja z szablonów (`TemplateNarrator`) |
| Sekcja | nagłówek, akapity i opcjonalna tabela |
| Szkic wpisu | sekcje w Markdownie w formacie `docs/RESEARCH_LOG.md`, z miejscem na interpretację badacza |

## Actors and permissions

| Actor | Action | Allowed |
|---|---|---|
| Badacz | generuje szkic, uzupełnia interpretację, commituje wpis | tak |
| `quantlab narrate` | zapisuje do `docs/RESEARCH_LOG.md` | nie |
| Narrator | liczy nowe statystyki | nie: tylko formatuje i porównuje z progami z definicji |

## Functional requirements (EARS)

Fakty

- REQ-1301 (AC-2): The lab shall read a hypothesis's facts only from the results store and the registry: its training run's summary, metrics per cost model, walk-forward windows, regimes, P&L by asset class, and its definition, status and holdout record. It shall read no market data.
- REQ-1302 (AC-2): Facts of a hypothesis without a stored run, or with a run of another schema version, shall be refused with the command that writes one (`quantlab run <hipoteza>`).

Narrator

- REQ-1310 (AC-1): The narrator shall give, in Polish, the sections of a research-log entry:
  - **Hipoteza**: strategy, parameters, universe;
  - **Metodologia**: data source and universe, training and holdout ranges, the cost models, the in-sample gate, the significance test, the holdout criterion, and the commits of freezing and opening;
  - **Wynik — okres treningowy**: a table of CAGR, Sharpe, Sortino, Calmar and max drawdown per cost model, then:
    - cost sensitivity;
    - the walk-forward windows and the rule's count;
    - the significance test;
    - PSR, DSR and the trials on the same data;
    - the regimes;
    - P&L by asset class;
    - the trades;
  - **Wynik — holdout**: the record's metrics and verdict, or that it is not opened;
  - **Wniosek**: the status the code computed, and a placeholder for the researcher's interpretation.
- REQ-1311 (AC-2): Every number in the text shall be a fact formatted as the log formats it: percentages to two decimals, ratios and p-values as the terminal prints them. The narrator shall compare facts only with thresholds of the definition or of the lab's rules (e.g. p against α, Sharpe against `min_sharpe`), never compute a statistic.
- REQ-1312 (AC-3): The text shall describe historical results only, with no recommendation. A list of forbidden phrases is checked by a test on every template.
- REQ-1313 (AC-4): Without a holdout record, the holdout section shall say it is sealed and name `quantlab open-holdout <hipoteza>`, and the conclusion shall say there is no verdict yet.
- REQ-1314: The narrator shall be an implementation of a `Narrator` interface. The command and the store call the interface and never branch on its implementation.

Szkic wpisu

- REQ-1320 (AC-1): `quantlab narrate <hipoteza>` shall print the draft in Markdown. With `--output <plik>` it shall write the draft to that file instead, refusing to overwrite an existing one.
- REQ-1321 (AC-1): The draft's heading shall be `## <data dziś> — <hipoteza>`, the form `quantlab plan` recognizes as a logged hypothesis once it is committed to the log.

Magazyn i aplikacja

- REQ-1330 (AC-5): Every refresh of the registry (`run`, `open-holdout`, `registry`) shall write the narrative of each hypothesis with a run as a table `narrative` in its directory (position, section, text), so it follows the holdout record.
- REQ-1331 (AC-5): The API shall return the narrative with the hypothesis's detail, and an empty one when the table is missing (stores written before this epic). The app shall show it as a panel.
- REQ-1332 (AC-5): The store's schema version shall not change: the table is an addition that readers treat as optional.

Plan

- REQ-1340 (AC-6): The plan's research-log step shall name the command `quantlab narrate <hipoteza> --output reports/<hipoteza>-log.md`.

Kompatybilność

- REQ-1350: Definitions, results and verdicts of every hypothesis shall not change: the regression dump stays byte for byte.

## Business rules

- Opis jest pomocą, nie źródłem prawdy. Źródłem są magazyn wyników i zapis otwarcia holdoutu, a wpis w dzienniku zatwierdza badacz.
- Szablon nie ocenia: nie pisze „dobry wynik" ani „słaba strategia". Pisze, co przeszło, co nie przeszło i o ile względem progu.
- Status końcowy w opisie to zawsze status z rejestru. Narrator go nie wylicza.

## Data and validation

Tabela `narrative` w katalogu hipotezy w magazynie:

| Field | Type | Validation |
|---|---|---|
| `position` | int | kolejność akapitu |
| `section` | string | nagłówek sekcji |
| `text` | string | akapit po polsku, bez Markdownu tabel |

## Edge and error cases

- Hipoteza bez przebiegu: `narrate` kończy się komunikatem z komendą `quantlab run <hipoteza>`, a rejestr nie zapisuje dla niej opisu.
- Metryka niezdefiniowana (np. Sharpe bez pozycji): w tekście „n/a", tak jak w terminalu.
- Brak P&L per klasa aktywów (magazyn sprzed `q12`): akapit pominięty.
- Holdout bez pozycji albo bez testu (p = None): opis mówi to wprost, werdykt z zapisu.

## Non-functional requirements

- `narrate` nie pobiera danych i trwa poniżej sekundy.
- Testy na magazynie syntetycznym (`presentation/fixtures/results`) i na faktach budowanych w teście.

## Traceability

| AC | REQ |
|---|---|
| AC-1 | REQ-1310, REQ-1320, REQ-1321 |
| AC-2 | REQ-1301, REQ-1302, REQ-1311 |
| AC-3 | REQ-1312 |
| AC-4 | REQ-1313 |
| AC-5 | REQ-1330, REQ-1331, REQ-1332 |
| AC-6 | REQ-1340 |
| Guardrail | REQ-1314, REQ-1350 |

## Open questions

| # | Question | Owner |
|---|---|---|
| — | Brak | — |
