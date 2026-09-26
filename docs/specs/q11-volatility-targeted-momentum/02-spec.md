# q11-volatility-targeted-momentum - Specification

Status: Ready for dev
Owner role: BA
Upstream: 01-story.md

## Glossary

| Term | Meaning |
|---|---|
| Zmienność ex-ante | estymata dziennego odchylenia standardowego zwrotów instrumentu z danych do dnia decyzji włącznie |
| Zmienność roczna | zmienność dzienna × √`periods_per_year` uniwersum (365 dla krypto) |
| Docelowa zmienność | zamrożona zmienność roczna, do której skalowana jest pozycja w instrumencie |
| Skala | min(limit, docelowa zmienność / zmienność roczna ex-ante): ułamek pozycji z równymi wagami po znaku |
| Limit skali | zamrożony górny kres skali, w (0, 1]: bez dźwigni |
| Wersja bez skalowania | ta sama strategia z równymi wagami po znaku (sizer domyślny), liczona opisowo w raporcie |

## Actors and permissions

| Actor | Action | Allowed |
|---|---|---|
| Badacz | zamraża docelową zmienność, estymator, limit i sygnał przed pierwszym przebiegiem | tak |
| `quantlab run` | liczy skalę z danych do dnia decyzji włącznie | tak |
| `quantlab run` | dobiera docelową zmienność albo okno na danych | nie |

## Functional requirements (EARS)

Estymacja zmienności

- REQ-1101 (AC-1): The lab shall estimate an instrument's daily volatility as of day t from the close-to-close returns of its last `window_days` returns up to and including t:
  - `rolling`: the sample standard deviation (ddof = 1);
  - `ewma`: the square root of the exponentially weighted variance around the exponentially weighted mean, with decay δ = c / (1 + c) for a center of mass of c days, weights δ^i on the i-th most recent return normalized to sum to 1 over the window.
- REQ-1102 (AC-2): The estimate as of t shall read only bars dated ≤ t. When there is no bar for t, or fewer than `window_days` returns up to t, there shall be no estimate.
- REQ-1103: The estimator shall be picked by the definition's `volatility.estimator` name from registered parameter models, each building its own estimator; the strategy shall never branch on the estimator's type.

Skalowanie i wagi

- REQ-1110 (AC-3): For each non-flat signal of the wrapped strategy, the scaled strategy shall carry the weight min(`max_scale`, `target_volatility` / (σ̂ · √`periods_per_year`)). A non-flat signal without an estimate, or with σ̂ = 0, shall be dropped, so there is no position in that instrument that day. Flat signals shall pass unchanged.
- REQ-1111 (AC-3): The sizer shall give each non-flat signal the engine found tradable the weight ±scale / N, where N is the number of such signals and the sign is the signal's direction.
- REQ-1112 (AC-3): `max_scale` shall be in (0, 1], so the sum of absolute weights never exceeds 1: the engines model no financing cost.
- REQ-1113 (AC-4): The scaling shall live in the strategy and the sizer both engines share, so the vectorized and the event-driven engine give the same run under full fills (parity below 1e-9).
- REQ-1114: The wrapper shall accept any `Strategy`; the hypothesis wraps time-series momentum with a frozen lookback.

Definicja

- REQ-1120: A definition with `strategy: time_series_momentum_vol_target` shall freeze `lookback_days`, `target_volatility`, `max_scale` and `volatility` (the estimator's name and parameters). Its warm-up shall be max(`lookback_days`, `volatility.window_days`) days.
- REQ-1121: An estimate shall not depend on where a run's fetched data starts: the estimator reads exactly `window_days` returns, all within the warm-up. The first holdout day then has the same estimate as a run with longer history.

Raport

- REQ-1130 (AC-5): The training run shall report, descriptively:
  - per instrument: the mean, minimum and maximum scale over the days it had a non-flat signal, and the share of those days at `max_scale`;
  - the net Sharpe, annualized volatility and max drawdown of the scaled strategy and of the unscaled version. Both are computed over the same window, from the first day every instrument can signal to the end of training, under the definition's cost model.
- REQ-1131: The report shall reach the terminal, the tear-sheet, the results store and the app as training diagnostics, without a schema change.

Walidacja i wynik

- REQ-1140 (AC-6): The hypothesis shall go through the lab's pipeline unchanged:
  - three cost models and the walk-forward gate;
  - the permutation test on the positions actually held (scaled);
  - PSR and DSR with every trial on `mvp-crypto` 2018–2023;
  - regimes, stress test and trade ledger;
  - a frozen holdout opened once.
- REQ-1141: The holdout shall be a range that no opened holdout on `mvp-crypto` covers (not 2024–2025).

Kompatybilność

- REQ-1150: The epic shall not change any frozen hypothesis's definitions, results or verdicts: the regression dump stays byte for byte. On their next run, the trial counts of hypotheses on `mvp-crypto` 2018–2023 grow by one, as the trial registry dictates.

## Business rules

- Jedyna różnica między `momentum_voltarget_v1` a `momentum_v1` to wielkość pozycji. Sygnał, uniwersum, koszty, rebalans dzienny i walidacja są te same, więc porównanie w raporcie izoluje skalowanie.
- Skala zmienia się codziennie razem z estymatą, a koszt każdej zmiany nalicza model kosztów jak każdy obrót.
- Wynik skalowania opisuje się jako redukcję ekspozycji w okresach wysokiej zmienności (limit ≤ 1), nie jako pełne celowanie w zmienność.

## Data and validation

Definicja (`config/holdout/<id>.yaml`, sekcja `parameters`):

| Field | Type | Validation |
|---|---|---|
| `strategy` | `time_series_momentum_vol_target` | |
| `lookback_days` | int | ≥ 1 |
| `target_volatility` | float | > 0 (roczna, np. 0.40) |
| `max_scale` | float | 0 < x ≤ 1 |
| `volatility.estimator` | `ewma` \| `rolling` | |
| `volatility.window_days` | int | ≥ 2 |
| `volatility.center_of_mass_days` | float | > 0, tylko `ewma` |

## Edge and error cases

- Mniej niż `window_days` zwrotów do dnia t: brak estymaty, brak pozycji w instrumencie (tak jak brak sygnału przy zbyt krótkiej historii).
- Zerowa wariancja w oknie (stała cena): brak pozycji; skala byłaby nieskończona.
- Instrument bez baru na końcu okresu: silnik go pomija, a pozostałe instrumenty dzielą się N handlowalnymi sygnałami, jak przy równych wagach.
- `max_scale` > 1 albo ≤ 0: definicja odrzucona przy wczytaniu.
- Brak dni z sygnałem w oknie raportu: wartości raportu `n/a`.

## Non-functional requirements

- Przebieg treningowy nie dłuższy niż dwukrotność przebiegu `momentum_v1` (estymata to jedno okno numpy na instrument i dzień).
- Testy bez sieci, na danych syntetycznych ze znanym wynikiem.

## Traceability

| AC | REQ |
|---|---|
| AC-1 | REQ-1101, REQ-1103 |
| AC-2 | REQ-1102, REQ-1121 |
| AC-3 | REQ-1110, REQ-1111, REQ-1112 |
| AC-4 | REQ-1113 |
| AC-5 | REQ-1130, REQ-1131 |
| AC-6 | REQ-1140, REQ-1141 |
| Guardrail | REQ-1150 |

## Open questions

| # | Question | Owner |
|---|---|---|
| 1–6 | Pytania pre-rejestracji z [01-story](01-story.md) | Tomasz |
