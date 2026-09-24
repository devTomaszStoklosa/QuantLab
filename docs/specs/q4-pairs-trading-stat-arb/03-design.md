# q4-pairs-trading-stat-arb - Design

Status: Ready for dev
Owner role: Architect
Upstream: 02-spec.md
ADRs: docs/adr/0002-dual-backtest-engine.md, docs/adr/0004-validation-first-frozen-holdout.md

## Context and constraints

- Oba silniki ważą pozycje jedną funkcją `equal_weight_by_sign` (`q2`-E1), wywoływaną na sygnałach, które silnik uznał za wykonalne (bar w dniu decyzji, w silniku wektorowym także w dniu następnym). Para potrzebuje wag z β i reguły „obie nogi albo żadna".
- `Strategy.generate_signals(bars, as_of)` zwraca `Signal(direction, strength)`; `strength` nie jest wagą (niesie surowy zwrot).
- Definicja hipotezy to unia pydantic po polu `strategy` (`q3`-M1); każdy wariant sam buduje swoją strategię.
- Test permutacyjny tasuje dni wspólnie dla wszystkich instrumentów, więc zachowuje korelację nóg — działa dla pary bez zmian. Stress test liczy z wag, więc pokaże neutralność pary.
- Brak statsmodels w zależnościach; maszyna deweloperska bez AVX2 (CLAUDE.md: test importu dla każdej nowej zależności natywnej).

## Quality attribute scenarios

| Source | Stimulus | Response | Measure |
|---|---|---|---|
| Deweloper | zmienia kontrakt wag | wyniki `momentum_v1` i `mean_reversion_v1` bez zmian | zrzut snapshotów identyczny bajt w bajt; parytet silników (q2) zielony |
| Deweloper | dodaje strategię z własnymi wagami | nowy `Sizer` i wariant definicji, silniki bez zmian | 0 gałęzi po typie w silnikach |
| Badacz | uruchamia `pairs_v1` z filtrem kointegracji | przebieg < 1 min | pomiar na danych syntetycznych tej długości |
| Recenzent | pyta, czy para jest kointegrowana | test E-G i półtrwanie w raporcie | jedna sekcja w `quantlab run` |

## Options — skąd silnik bierze wagi

### Option A - `Sizer` wybierany przez definicję hipotezy

Protokół `Sizer.weights(signals) -> dict[str, float]` z implementacjami `EqualWeightBySign` (domyślna, dzisiejsza reguła) i `PairWeights` (wagi z `Signal.weight`, obie nogi albo nic). Definicja buduje swój `Sizer` obok strategii; silniki dostają go parametrem.

### Option B - Strategia zwraca wagi docelowe

`Strategy.target_weights(bars, as_of) -> dict`. Wagi omijają filtr wykonalności silnika (bar jutro, bar dziś), więc para mogłaby wejść jedną nogą, a istniejące strategie trzeba przepisać.

### Option C - Osobny silnik par

Dwa silniki to już dużo (ADR-0002); trzeci podważa wspólny kontrakt.

## Trade-off matrix (1-5)

| Criterion | A | B | C |
|---|---|---|---|
| Zgodność wsteczna (bit w bit) | 5 — domyślny `Sizer` to dzisiejsza funkcja | 3 | 5 |
| „Obie nogi albo nic" po filtrze wykonalności | 5 | 2 | 5 |
| Podstawialność (CLAUDE.md, zasada 9) | 5 | 4 | 1 |
| Złożoność | 4 | 3 | 1 |

## Decision

Recommended: **Option A**. Rezygnujemy z wag zwracanych przez strategię (B) — omijałyby filtr wykonalności silników — i z osobnego silnika (C). Konsekwencja: `Signal` dostaje opcjonalne pole `weight`, a definicja hipotezy metodę `build_sizer()` z domyślnym `EqualWeightBySign`. Revisit if: strategie zaczną potrzebować wag zależnych od stanu portfela (np. target volatility) — wtedy `Sizer` dostanie historię.

Strategia par liczy stan (flat / long / short spread) od nowa przy każdym wywołaniu, z całej historii do `as_of`: β, α i odchylenie reszt kroczącym oknem z sum skumulowanych (O(n) na wywołanie), potem maszyna stanów po ścieżce z-score. Brak stanu między wywołaniami, więc funkcja jest czysta i nie zależy od kolejności wywołań. Test Engle'a-Grangera jest liczony tylko w dniach, w których reguła wejścia otworzyłaby pozycję, i zapamiętywany według zawartości okna — ten sam wynik, bez tysięcy testów na przebieg.

## Diagrams

```
config/holdout/pairs_v1.yaml
  parameters: PairsSpreadParameters (strategy: pairs_spread)
     .build_strategy() -> PairsSpreadReversion(dependent, explanatory, formation_days, entry_z, exit_z, max_coint_p_value)
     .build_sizer()    -> PairWeights()
     .training_diagnostics(bars, start, end) -> Engle-Granger + półtrwanie (opis)

PairsSpreadReversion.generate_signals(bars, as_of)
  wspólne daty obu nóg <= as_of -> log(y), log(x)
  kroczące okno N: β, α, σ(ε) -> z_t
  maszyna stanów (wejście |z| >= entry [+ filtr E-G], wyjście przez exit)
  -> [Signal(y, ±, weight=1/(1+|β|)), Signal(x, ∓, weight=|β|/(1+|β|))] albo []

silniki: sizer.weights(wykonalne sygnały) zamiast equal_weight_by_sign(...)
```

## Contracts

### Pliki

```
src/quantlab/strategy/cointegration.py       # hedge_ratio, engle_granger, half_life (P1)
src/quantlab/strategy/signal.py              # Signal.weight (P2)
src/quantlab/backtest/sizing.py              # Sizer, EqualWeightBySign, PairWeights (P2)
src/quantlab/backtest/vectorized/engine.py   # sizer= (P2)
src/quantlab/backtest/event_driven/engine.py # sizer= (P2)
src/quantlab/research/definition.py          # build_sizer(), training_diagnostics(), PairsSpreadParameters (P2, P3, P4)
src/quantlab/strategy/pairs_spread.py        # spread_path, pair_states, PairsSpreadReversion (P3)
src/quantlab/cli.py                          # sizer z definicji; diagnostyka w `run` (P2, P4)
config/holdout/pairs_v1.yaml                 # zamrożona definicja (P5, osobny commit)
tests/test_environment.py                    # import statsmodels i scipy (P1)
```

### Kontrakty (sygnatury poglądowe)

```python
# strategy/cointegration.py
class EngleGranger(BaseModel):
    beta: float; alpha: float; statistic: float; p_value: float
    critical_values: dict[str, float]; half_life: float | None; n_observations: int
def hedge_ratio(y: np.ndarray, x: np.ndarray) -> tuple[float, float]: ...   # (alpha, beta), log ceny
def half_life(spread: np.ndarray) -> float | None: ...
def engle_granger(y: np.ndarray, x: np.ndarray) -> EngleGranger: ...

# backtest/sizing.py
class Sizer(Protocol):
    def weights(self, signals: list[Signal]) -> dict[str, float]: ...
class EqualWeightBySign: ...        # dzisiejsze equal_weight_by_sign
class PairWeights: ...              # wagi z Signal.weight, dokładnie dwie nogi albo {}

# strategy/pairs_spread.py
def spread_path(log_y, log_x, formation_days) -> tuple[np.ndarray, np.ndarray]: ...  # (beta, z) na datę
def pair_states(z, entry_z, exit_z, may_enter: Callable[[int], bool]) -> np.ndarray: ...
class PairsSpreadReversion: ...
```

## Rollout and rollback

Każdy slice z zielonymi testami (`uv run ruff check . && uv run pytest -q`) przed następnym:

1. **P1** `strategy/cointegration.py` na statsmodels; test importu statsmodels i scipy; testy na parze syntetycznej (znane β i półtrwanie) i na niezależnych błądzeniach losowych.
2. **P2** kontrakt wag: `Signal.weight`, `Sizer`, `EqualWeightBySign`, `PairWeights`; oba silniki i CLI biorą `Sizer` z definicji. Zrzut snapshotów obu istniejących strategii identyczny bajt w bajt, parytet silników zielony.
3. **P3** `PairsSpreadReversion` i `PairsSpreadParameters`: brak look-ahead, maszyna stanów, wagi, filtr; pomiar czasu przebiegu.
4. **P4** diagnostyka kointegracji w `quantlab run` dla definicji, które ją mają.
5. **P5** zamrożenie `config/holdout/pairs_v1.yaml` — **osobny commit, przed jakimkolwiek przebiegiem tej hipotezy na danych**, po odpowiedziach na pytania 1–4 z 01-story; najlepiej przed otwarciem holdoutu `mean_reversion_v1`.
6. **P6** przebieg treningowy lokalnie (Binance) z wynikiem w PR, razem z `quantlab trials pairs_v1`.
7. **P7** jednorazowe otwarcie holdoutu, zapis commitowany.
8. **P8** wpis w dzienniku (REQ-441).

Rollback: `git revert` per slice; P2 jest weryfikowany zrzutem bajt w bajt, żaden slice nie dotyka istniejących zamrożonych plików.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| statsmodels/scipy nie importują się na maszynie bez AVX2 | niska | wysoki | test importu w `tests/test_environment.py`; wtedy własny ADF z tablicami MacKinnona |
| Zmiana kontraktu wag cicho zmienia wyniki istniejących hipotez | niska | wysoki | zrzut snapshotów bajt w bajt przed i po; golden-master i parytet |
| Filtr kointegracji prawie nigdy nie przepuszcza wejścia | średnia | średni | przyjęte z góry (01-story); liczba dni z pozycją w raporcie i flaga niskiej wiarygodności testu permutacyjnego |
| Wolny przebieg przez test E-G | średnia | niski | test tylko w dniach kandydatów do wejścia, zapamiętany według okna |
| Holdout 2026 skażony otwarciem holdoutu `mean_reversion_v1` | średnia | wysoki | zamrożenie `pairs_v1` przed M6 `q3`; w przeciwnym razie holdout z danych przyszłych |

## Handoff notes

- P1–P4 nie wymagają odpowiedzi na pytania; P5 wymaga wszystkich czterech.
- Nie uruchamiaj `PairsSpreadReversion` na realnych danych przed P5 — nawet „dla sprawdzenia, czy działa"; dane syntetyczne w testach wystarczą.
