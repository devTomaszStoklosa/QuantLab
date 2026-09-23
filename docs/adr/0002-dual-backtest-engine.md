# 0002. Dwa silniki backtestu: wektorowy i event-driven

Status: Proposed

## Context

Szybka iteracja po wielu hipotezach i metodach walidacji (Monte Carlo, testy permutacyjne — tysiące powtórzeń) wymaga silnika liczącego na całych seriach naraz. Ale sam wektorowy silnik nie demonstruje zrozumienia systemów transakcyjnych: kolejności zdarzeń, look-ahead bias, częściowych wypełnień — a to część sygnału dla ról Quantitative Developer / Systematic Trading.

## Decision

- MVP (`q1-momentum-research-mvp`) używa wyłącznie silnika wektorowego (`quantlab.backtest.vectorized`, pandas/numpy).
- Event-driven silnik (`quantlab.backtest.event_driven`) to osobny epik (`q2`), za tym samym kontraktem wejścia/wyjścia (`BacktestRun`), żeby wyniki obu dało się porównać na tej samej hipotezie.

## Consequences

- Pozytywne: MVP dowozi się szybciej; rozszerzenie dokłada realizm bez przepisywania warstwy strategii/kosztów/walidacji.
- Negatywne: dwa silniki do utrzymania; kontrakt `BacktestRun` musi być zaprojektowany pod oba od początku, inaczej q2 wymusi przeróbki w q1.

## Alternatives considered

- **Tylko event-driven od startu** — realistyczny, ale za wolny do walidacji wymagającej tysięcy powtórzeń (Monte Carlo, permutacje) i wolniejszy do dowiezienia MVP.
- **Tylko wektorowy, bez rozszerzenia** — nie demonstruje warstwy systemów transakcyjnych, słabszy sygnał dla Quantitative Developer/Systematic Trading.
