# 0003. Ceny i zwroty w silniku: `float64`, nie `Decimal`

Status: Proposed

## Context

Właściciel ma nawyk `Decimal` dla pieniędzy z innych projektów (zasada „pieniądze w Decimal" w innych repozytoriach). Tu silnik wektoryzuje obliczenia na dużych seriach czasowych (numpy/pandas) — `Decimal` nie wektoryzuje się w numpy i jest rzędy wielkości wolniejszy.

## Decision

- Ceny, zwroty, sygnały, metryki portfela w silniku: `float64`.
- `Decimal` dopuszczalny wyłącznie w końcowej księdze P&L pojedynczej transakcji w warstwie raportowania, jeśli potrzebna księgowa ścisłość prezentacji — nigdy w rdzeniu obliczeniowym backtestu.

## Consequences

- Pozytywne: wektoryzacja numpy/pandas działa bez obejść; zgodność z całym ekosystemem quant (numpy, pandas, statsmodels i inne standardowo używają float64).
- Negatywne: błąd zaokrąglenia typu float — akceptowalny, bo rzędy wielkości mniejszy niż szum estymacji statystycznej i szum rynkowy, którymi i tak zdominowane są wyniki backtestu.

## Alternatives considered

- **`Decimal` wszędzie, jak w innych repo właściciela** — wymagałoby rezygnacji z wektoryzacji numpy/pandas albo własnej warstwy konwersji na każdym kroku; koszt niewspółmierny do zysku przy skali danych tego projektu.
