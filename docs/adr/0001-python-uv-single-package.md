# 0001. Python 3.12 + uv, jeden pakiet `quantlab`

Status: Proposed

## Context

Platforma ma wiele warstw (dane, strategie, backtest, walidacja, ryzyko, atrybucja, raportowanie) tworzonych stopniowo, jeden deweloper. Ekosystem quant research (pandas, numpy, statsmodels, scipy) jest przede wszystkim pythonowy; to też język, w którym rekruter na Quantitative Analyst/Research oczekuje biegłości.

## Decision

- Python 3.12, zarządzany przez `uv` (spójne z pozostałymi repozytoriami właściciela).
- Jeden pakiet `quantlab` z podpakietami per warstwa (`core`, `strategy`, `backtest`, `costs`, `validation`, `risk`, `attribution`, `reporting`), nie osobne repozytoria/pakiety per warstwa.

## Consequences

- Pozytywne: jeden `pyproject.toml`, jedno środowisko, łatwe importy między warstwami (`quantlab.validation` importuje `quantlab.backtest` bez zależności międzypakietowych).
- Negatywne: przy bardzo dużym wzroście kodu jeden pakiet może wymagać podziału — akceptowalne ryzyko na skalę projektu portfolio.

## Alternatives considered

- **Osobne pakiety per warstwa** — przedwczesna abstrakcja przy jednym developerze i jednym repo.
- **R zamiast Pythona** — silniejszy w części testów statystycznych, słabszy w warstwie systemowej/inżynieryjnej, którą projekt ma też demonstrować (Quantitative Developer).
