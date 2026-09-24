# q6-advanced-validation-cpcv - Specification

Status: Ready for dev
Owner role: BA
Upstream: 01-story.md

## Glossary

| Term | Meaning |
|---|---|
| Próba | hipoteza, której definicja została kiedykolwiek zacommitowana w `config/holdout/` — od tej chwili jej przebieg mógł być oglądany |
| Te same dane | to samo uniwersum i nachodzące na siebie okresy treningowe |
| Sharpe na okres | średnia dziennych zwrotów netto przez ich odchylenie standardowe (ddof = 1), bez annualizacji |
| PSR(SR*) | probabilistic Sharpe ratio: prawdopodobieństwo, że prawdziwy Sharpe przekracza próg SR*, przy danej długości historii, skośności i kurtozie (Bailey, López de Prado 2012) |
| Próg SR₀ | oczekiwane maksimum Sharpe N prób bez żadnej przewagi |
| DSR | deflated Sharpe ratio: PSR(SR₀), czyli PSR względem progu, który uwzględnia liczbę prób (Bailey, López de Prado 2014) |
| CSCV | combinatorially symmetric cross-validation: podział szeregu na S bloków i wszystkie wybory S/2 bloków jako in-sample |
| PBO | probability of backtest overfitting: odsetek podziałów CSCV, w których konfiguracja najlepsza in-sample wypada out-of-sample na pozycji nie wyższej niż mediana (Bailey, Borwein, López de Prado, Zhu 2017) |

## Actors and permissions

| Actor | Action | Allowed |
|---|---|---|
| Rejestr prób | pomija definicję usuniętą z repozytorium | nie (REQ-611) |
| Rejestr prób | liczy niezacommitowany szkic jako próbę | nie (REQ-611) |
| `quantlab trials` | czyta dane z zakresu holdoutu którejkolwiek próby | nie (REQ-641) |
| Kod epiku | zmienia status hipotezy albo zamrożone kryterium na podstawie DSR lub PBO | nie (REQ-650) |

## Functional requirements (EARS)

PSR

- REQ-601 (AC-1): The system shall compute PSR(SR*) = Φ((SR − SR*)·√(T − 1) / √(1 − γ₃·SR + (γ₄ − 1)/4·SR²)) from a series of per-period returns, where SR is the per-period Sharpe, T the number of returns, γ₃ the skewness and γ₄ the (non-excess) kurtosis of the returns.
- REQ-602 (AC-1): When the returns have fewer than 3 observations or zero variance, PSR shall be undefined, not a number.

Rejestr prób

- REQ-610 (AC-2): The trial registry shall read every hypothesis definition ever added to `config/holdout/` in the history of the current commit, at its last committed version.
- REQ-611 (AC-2): A definition deleted from the working tree or from a later commit shall still count as a trial, and a file that was never committed shall not.
- REQ-612 (AC-2): The trials on a hypothesis's data shall be all registered hypotheses with the same universe and a training period overlapping its own, the hypothesis itself included.

DSR

- REQ-620 (AC-3): The system shall compute the threshold SR₀ = √V·((1 − γ)·Φ⁻¹(1 − 1/N) + γ·Φ⁻¹(1 − 1/(N·e))) for N ≥ 2 trials, where γ is the Euler–Mascheroni constant and V the variance of per-period Sharpe ratios across trials; for N = 1, SR₀ = 0.
- REQ-621 (AC-3): In reports, V shall be the variance under the null hypothesis of no edge, 1/(T − 1), where T is the number of returns of the evaluated run.
- REQ-622 (AC-3): DSR shall equal PSR(SR₀) of the evaluated run's returns.

PBO

- REQ-630 (AC-4): Given a T × N matrix of per-period returns with N ≥ 2, the system shall split the rows into S equal consecutive blocks (dropping the earliest T mod S rows), evaluate every choice of S/2 blocks as in-sample with the rest out-of-sample, and report PBO as the share of splits in which the in-sample best column's out-of-sample relative rank ω = rank/(N + 1) is at most 0.5.
- REQ-631 (AC-4): Performance in a split shall be the per-period Sharpe; a column with zero variance in a split shall score 0, and ties shall share their average rank.
- REQ-632 (AC-4): The PBO result shall include N, S, the number of splits and the distribution of logit(ω) (median and share ≤ 0).

Raport

- REQ-640 (AC-5): `quantlab run` shall print, and the tear-sheet shall show, for the realistic-cost training run: PSR(0), the number of trials on the same data with their ids, SR₀ annualized and DSR, marked as descriptive and outside the status rules.
- REQ-641 (AC-6): `quantlab trials [HYPOTHESIS]` shall run every trial on the hypothesis's data over its own training period with its own cost model, print each trial's annualized Sharpe, PSR(0) and DSR, and the PBO of choosing the best of them over the dates common to all trials; it shall fetch no data after any trial's training end.
- REQ-642 (AC-6): When any trial's definition is not committed or has uncommitted changes, `quantlab trials` shall refuse before fetching any data.

Granice

- REQ-650: No requirement of this epic shall change `concluded_status`, a frozen success criterion or a recorded holdout verdict.

## Business rules

Metodologia (stałe laboratorium, jak liczba permutacji)

| Ustawienie | Wartość | Źródło |
|---|---|---|
| Próg PSR | Sharpe 0 | 01-story, decyzja 1 |
| Wariancja Sharpe między próbami w DSR | 1/(T − 1) na okres (hipoteza zerowa) | 01-story, decyzja 2 |
| Bloki CSCV | S = 16, wszystkie 12 870 podziałów | 01-story, decyzja 3 |
| Zwroty do PSR i DSR | dzienne netto modelu realistycznego, od pierwszej trzymanej pozycji | 01-story, decyzja 4 |
| Annualizacja Sharpe w raporcie | × √365 | jak w całym laboratorium |

Interpretacja w raporcie (opisowa, poza regułami statusu)

| Miara | Czytanie |
|---|---|
| PSR(0) | prawdopodobieństwo, że prawdziwy Sharpe > 0 przy tej długości historii i kształcie rozkładu — bez korekty na liczbę prób |
| DSR | to samo względem progu, który osiągnąłby najlepszy z N przebiegów bez przewagi; ≥ 0.95 odpowiada istotności na poziomie 5% po korekcie |
| PBO | jak często wybór najlepszej próby in-sample daje wynik poniżej mediany out-of-sample; 0.5 = wybór nie lepszy niż losowy |

## Data and validation

`Trial` (wpis rejestru)

| Field | Type | Required | Range or format |
|---|---|---|---|
| `hypothesis` | string | tak | identyfikator z definicji; unikalny w rejestrze |
| `universe` | string | tak | nazwa uniwersum z definicji |
| `training_start`, `training_end` | date | tak | z definicji |
| `registered_at` | datetime | tak | czas commita, który pierwszy dodał definicję; porządek prób |
| `last_commit` | string | tak | SHA ostatniego commita, który dodał lub zmienił definicję (jej obowiązująca wersja) |
| `deleted` | bool | tak | plik nie istnieje w bieżącym commicie |

## Edge and error cases

- Dwie definicje (np. po zmianie nazwy pliku) z tym samym `hypothesis` → jedna próba, w wersji z najnowszego commita.
- Zacommitowana definicja, której ostatnia wersja nie parsuje się → błąd z nazwą pliku, nie cicha pominięta próba.
- PSR przy SR tak dużym, że mianownik wychodzi ≤ 0 (skrajna ujemna skośność) → niezdefiniowany.
- CSCV: T < S albo S nieparzyste albo N < 2 → błąd walidacji.
- Próby bez wspólnych dat albo wspólnych dat mniej niż S → PBO niezdefiniowane („—"), reszta tabeli działa.
- Hipoteza bez żadnej pozycji w okresie treningowym → PSR i DSR niezdefiniowane.

## Non-functional requirements

- Performance: PBO dla N ≤ 10 i T ≈ 2 200 poniżej 5 s; `quantlab trials` dla dwóch prób poniżej 1 minuty.
- Reproducibility: wszystkie miary deterministyczne (bez losowości).
- Security and privacy: brak danych osobowych.

## Traceability

| AC | REQ |
|---|---|
| AC-1 | REQ-601, REQ-602 |
| AC-2 | REQ-610, REQ-611, REQ-612 |
| AC-3 | REQ-620, REQ-621, REQ-622 |
| AC-4 | REQ-630, REQ-631, REQ-632 |
| AC-5 | REQ-640 |
| AC-6 | REQ-641, REQ-642 |

REQ-650 wynika z zasady 6 w CLAUDE.md (zamrożony holdout) i z guardrail metric w 01-story.

Test AC-3: przykład liczbowy z Bailey, López de Prado (2014) — N = 100 prób, wariancja rocznego Sharpe między próbami 0.5, T = 1 250 dni (250 dni w roku), roczny Sharpe 2.5, skośność −3, kurtoza 10 — daje SR₀ ≈ 0.1132 na okres i DSR ≈ 0.9004.

## Open questions

Brak. Ustawienia metodologii przyjęte w [01-story.md](01-story.md) (decyzje 1–4).
