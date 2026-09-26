# q11-volatility-targeted-momentum - Design

Status: Ready for dev
Owner role: Architect
Upstream: 02-spec.md
ADRs: docs/adr/0002-dual-backtest-engine.md, docs/adr/0003-float-not-decimal-core-engine.md, docs/adr/0004-validation-first-frozen-holdout.md

## Context and constraints

- **Kontrakt z silnikami.** Silnik bierze od strategii sygnały, od sizera wagi docelowe (`Sizer.weights(signals)`, tylko sygnały, bez barów), a od polityki rebalansu decyzję, czy handlować. Oba silniki dzielą te obiekty (parytet `q2`). Sygnał może nieść wielkość wagi (`Signal.weight`, `q4`).
- **Filtr handlowalności.** Silnik przekazuje sizerowi tylko sygnały instrumentów handlowalnych w danym okresie. Równe wagi dzielą się więc przez liczbę handlowalnych sygnałów, nie wszystkich.
- **Dźwignia i finansowanie.** Silnik wektorowy dopuszcza sumę |wag| > 1 (ujemna gotówka), ale nie nalicza za nią kosztu finansowania.
- **Rozgrzewka.** Runner pobiera dane od początku okresu minus `warm_up_days` definicji. Holdout zaczyna się więc od krótszej historii niż trening.
- **Diagnostyka treningu.** `TrainingDiagnostic` przechodzi do terminala, tear-sheetu, magazynu (tabela `diagnostics`) i aplikacji bez zmiany schematu.
- **Zgodność wsteczna.** Zamrożone definicje i ich wyniki nie mogą się zmienić (zrzut bajt w bajt).

## Quality attribute scenarios

| Source | Stimulus | Response | Measure |
|---|---|---|---|
| Badacz | estymata na dzień t | tylko bary ≤ t | test: bar z dnia > t zmieniony po fakcie nie zmienia estymaty ani wagi |
| Badacz | stała zmienność syntetyczna | znana skala | test: zwroty ±x → σ̂ = x·√(n/(n−1)) (kroczący), skala policzona z góry |
| Deweloper | hipoteza w obu silnikach | ten sam wynik | parytet < 1e-9 |
| Badacz | pierwszy dzień holdoutu | ta sama estymata co przy dłuższej historii | test: obcięcie historii do rozgrzewki nie zmienia wag |
| Deweloper | hipotezy bez skalowania | bez zmian | zrzut regresji bajt w bajt |

## Options

### Decyzja 1 — gdzie żyje skalowanie

- **A. Opakowanie strategii `VolatilityTargeted` + sizer `ScaledEqualWeight`.** Opakowanie bierze sygnały dowolnej strategii i nadaje każdemu niepłaskiemu sygnałowi wagę-skalę z estymaty do dnia decyzji. Sizer dzieli skale przez liczbę handlowalnych sygnałów, z ich znakiem. Silniki bez zmian, parytet z konstrukcji; instrument wypadający z okresu jest traktowany jak przy równych wagach.
- B. Sizer z dostępem do barów — zmiana protokołu `Sizer` w obu silnikach i wszystkich sizerach, żeby jeden sizer mógł czytać ceny.
- C. Nakładka ryzyka w silniku — trzecia rzecz, którą oba silniki musiałyby implementować identycznie; poza wspólnym kontraktem strategia–sizer–rebalans.

### Decyzja 2 — skalowanie per instrument czy portfela

- **A. Per instrument**, jak u Moskowitza, Ooi i Pedersena: skala zależy tylko od zmienności instrumentu. Wagi dzielą się równo między aktywne instrumenty.
- B. Zmienność portfela z kowariancji: więcej estymacji (korelacja BTC–ETH), inne pytanie badawcze. Poza zakresem.

### Decyzja 3 — dźwignia

- **A. Limit skali w (0, 1]**, sprawdzany przy wczytaniu definicji. Suma |wag| ≤ 1, więc brak pożyczania, którego silniki nie kosztują.
- B. Dźwignia z kosztem finansowania — nowy składnik modelu kosztów i dane o stopach pożyczania, poza zakresem. Wraca, jeśli pytanie badawcze będzie dotyczyć pełnego celowania w zmienność.

### Decyzja 4 — estymator zmienności

- **A. Rejestr modeli parametrów estymatora w definicji** (`volatility.estimator`: `ewma` albo `rolling`), każdy buduje swój estymator. Estymator czyta dokładnie `window_days` ostatnich zwrotów, a rozgrzewka definicji obejmuje okno. Estymata na pierwszy dzień holdoutu jest więc taka sama jak w przebiegu z dłuższą historią. EWMA z oknem skończonym normalizuje wagi w oknie; przy środku masy 60 dni i oknie 365 dni ucięta masa to ok. 0.25%.
- B. EWMA po całej dostępnej historii (jak w artykule): estymata zależałaby od początku pobranych danych, inna w treningu i w holdoucie.
- C. Jeden estymator na sztywno — wybór estymatora to pytanie pre-rejestracji, a dwa znane z literatury (EWMA u Moskowitza, Ooi i Pedersena; zmienność zrealizowana u Barroso i Santa-Clary oraz Moreiry i Muira) kosztują kilkanaście linii.

### Decyzja 5 — jak często zmienia się skala

- **A. Codziennie, razem z estymatą**, przy rebalansie dziennym jak w `momentum_v1`. Jedyna różnica między hipotezami to wielkość pozycji, a koszt zmian nalicza model realistyczny.
- B. Raz w miesiącu (jak w artykule) — druga różnica względem `momentum_v1` (harmonogram), która zaciera porównanie; dodatkowy stan w strategii.

### Decyzja 6 — porównanie ze strategią bez skalowania

- **A. Diagnostyka treningu definicji** liczy w tym samym oknie i przy tym samym modelu kosztów wersję skalowaną i tę samą strategię z równymi wagami po znaku (`net_returns`, `q8`). Do tego statystyki skali per instrument. Opcja `--contrast momentum_v1` nadal daje korelację dziennych zwrotów.
- B. Tylko `--contrast` — korelacja bez Sharpe, zmienności i obsunięcia wersji bez skalowania.

## Trade-off matrix (1-5)

| Criterion | 1A | 1B | 1C | 3A | 3B | 4A | 4B | 5A | 5B | 6A | 6B |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Zgodność wsteczna (bit w bit) | 5 | 3 | 3 | 5 | 4 | 5 | 5 | 5 | 5 | 5 | 5 |
| Podstawialność, brak `if` po typie | 5 | 4 | 2 | 5 | 4 | 5 | 5 | 5 | 4 | 5 | 5 |
| Parytet silników | 5 | 4 | 2 | 5 | 3 | — | — | 5 | 5 | — | — |
| Wierność kosztów i ryzyka | 4 | 4 | 4 | 5 | 3 | 5 | 2 | 4 | 4 | — | — |
| Czystość porównania z `momentum_v1` | 5 | 5 | 5 | 4 | 3 | 5 | 5 | 5 | 2 | 5 | 2 |
| Złożoność | 5 | 2 | 1 | 5 | 2 | 4 | 5 | 5 | 3 | 4 | 5 |

## Decision

Recommended: **1A, 2A, 3A, 4A, 5A, 6A.**

- Skalowanie to opakowanie strategii niosące skalę w sygnale i sizer dzielący ją równo między handlowalne instrumenty. Silniki zostają bez zmian.
- Skala jest per instrument, bez dźwigni, z estymatorem z rejestru czytającym stałe okno.
- Skala zmienia się codziennie, a raport porównuje wersję skalowaną z tą samą strategią bez skalowania.

Revisit if: pytanie przejdzie na pełne celowanie w zmienność z dźwignią (3B z kosztem finansowania) albo na zmienność portfela (2B).

## Diagrams

```
definition (lookback_days, target_volatility, max_scale, volatility{estimator, window_days, ...})
   │ build_strategy
   ▼
VolatilityTargeted(inner = TimeSeriesMomentum(lookback), estimator, target, max_scale, periods_per_year)
   generate_signals(bars, t):
      for s in inner.generate_signals(bars, t):
         flat            -> s
         σ̂ = estimator.daily_volatility(bars[s.instrument], t)   # returns up to t, last window_days
         σ̂ None or 0     -> dropped (no position)
         otherwise       -> s with weight = min(max_scale, target / (σ̂·√ppy))
   │ build_sizer
   ▼
ScaledEqualWeight.weights(tradable signals) = {i: ±weight_i / N}     # N = tradable non-flat signals
   │
   ▼
vectorized.run / event_driven.run   (unchanged; daily rebalance)
```

## Contracts

```python
# risk/volatility.py
class VolatilityEstimator(Protocol):
    window_days: int
    def daily_volatility(self, bars: list[PriceBar], as_of: date) -> float | None: ...
class RollingVolatility:  # sample std (ddof=1) of the last window_days returns
class EwmaVolatility:     # EW mean and variance, decay c/(1+c), weights normalized over the window

# strategy/volatility_target.py
class VolatilityTargeted:  # Strategy wrapping any Strategy
    def __init__(self, inner, estimator, target_volatility, max_scale, periods_per_year): ...
    def scale(self, bars: list[PriceBar], as_of: date) -> float | None: ...

# backtest/sizing.py
class ScaledEqualWeight:  # ±signal.weight / N among the tradable non-flat signals

# research/definition.py
class RollingVolatilityParameters(BaseModel): estimator: Literal["rolling"]; window_days
class EwmaVolatilityParameters(BaseModel): estimator: Literal["ewma"]; window_days; center_of_mass_days
VolatilityParameters = Annotated[Rolling… | Ewma…, Field(discriminator="estimator")]
class VolatilityTargetedMomentumParameters(StudyParametersBase):
    strategy: Literal["time_series_momentum_vol_target"]
    lookback_days; target_volatility; max_scale (0 < x <= 1); volatility: VolatilityParameters
    warm_up_days = max(lookback_days, volatility.window_days)
    build_strategy -> VolatilityTargeted(TimeSeriesMomentum(lookback_days), ...)
    build_sizer -> ScaledEqualWeight()
    training_diagnostics -> scale statistics per instrument; scaled vs unscaled (net Sharpe, vol, max DD)
```

Pliki:

- `src/quantlab/risk/volatility.py`, `src/quantlab/strategy/volatility_target.py`;
- `src/quantlab/backtest/sizing.py` (nowy sizer), `src/quantlab/research/definition.py` (nowy wariant definicji);
- `src/quantlab/reporting/volatility_scaling.py` (raport skali i porównania z wersją bez skalowania);
- testy: `tests/risk/test_volatility.py`, `tests/strategy/test_volatility_target.py`, `tests/backtest/test_sizing.py`, `tests/research/test_vol_target_definition.py`, `tests/test_vol_target_run.py`.

## Rollout and rollback

1. **V1** dokumentacja: 01-story, 02-spec, 03-design, ROADMAP.
2. **V2** estymatory zmienności, opakowanie strategii, sizer; testy znanych wartości, braku zaglądania w przyszłość i parytetu silników.
3. **V3** definicja `time_series_momentum_vol_target`, diagnostyka treningu (skala, porównanie z wersją bez skalowania), przebieg CLI na danych syntetycznych, zrzut regresji bez zmian.
4. **V4** zamrożenie `momentum_voltarget_v1` po odpowiedziach na pytania 1–6. Potem przebiegi lokalne (Binance), holdout i wpis w dzienniku.

Rollback: `git revert` per slice. V2 i V3 niczego nie zmieniają w zamrożonych hipotezach. V4 dodaje definicję: po commicie zostaje próbą w rejestrze nawet po usunięciu, zgodnie z `q6`.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Estymata zagląda w przyszłość | niska | wysoki | tylko bary ≤ t; test ze zmianą baru po t |
| Różna estymata w treningu i holdoucie | średnia | średni | stałe okno w rozgrzewce (REQ-1121); test obcięcia historii |
| Dźwignia bez kosztu finansowania | niska | wysoki | limit skali ≤ 1 walidowany w definicji |
| Obrót z codziennej zmiany skali | wysoka | niski | koszt w modelu realistycznym; porównanie z wersją bez skalowania |
| Brak demo w magazynie syntetycznym | — | niski | diagnostyka renderowana generycznie (jak w `pairs_v1`); demo niepotrzebne do weryfikacji aplikacji |

## Handoff notes

- Kolejna próba na `mvp-crypto` 2018–2023: po zamrożeniu `quantlab plan` pokaże przebiegi pozostałych hipotez krypto jako nieaktualne (`new trials on its data: momentum_voltarget_v1`). To oczekiwane.
