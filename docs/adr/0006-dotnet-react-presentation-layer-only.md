# 0006. .NET + React wyłącznie w warstwie prezentacji/orkiestracji

Status: Proposed

## Context

Właściciel ma silne, produkcyjne doświadczenie w ASP.NET Core + React (projekt InvestorSocial). Warto to pokazać, ale rdzeń badawczy (silnik backtestu, walidacja, modele kosztów) musi zostać w Pythonie — to standard branżowy w quant research i to, czego oczekuje rekruter na Quantitative Analyst/Research.

## Decision

- Python pozostaje jedynym miejscem obliczeń: silnik backtestu, walidacja, koszty, ryzyko, atrybucja, metryki.
- Rozszerzenie `q7-dotnet-react-presentation` dokłada ASP.NET Core Web API czytające wyniki (`BacktestRun`, `PerformanceMetrics`, `Trade`) z DuckDB/Parquet zapisanych przez Pythona, i React jako warstwę interaktywną (eksplorator strategii, blotter transakcji).
- Kontrakt Python → .NET: współdzielony odczyt z DuckDB/Parquet, bez synchronicznego wywoływania Pythona z .NET (prostsze, brak potrzeby gRPC/REST między nimi na tym etapie).

## Consequences

- Pozytywne: realny wzorzec branżowy (zespoły research w Pythonie, systemy produkcyjne/UI w C#/Java/C++) jako gotowa narracja rekrutacyjna; reużycie istniejącej, dojrzałej kompetencji zamiast budowania nowej warstwy od zera.
- Negatywne: dwa stacki technologiczne w jednym repo — więcej narzutu operacyjnego (dwa środowiska, dwa zestawy zależności) niż przy jednym.

## Alternatives considered

- **Streamlit** — szybszy do zbudowania solo, ale nie pokazuje kompetencji .NET/React, którą właściciel chce uwzględnić w tym portfolio.
- **.NET/C# także w rdzeniu obliczeniowym** — rozmywa sygnał „quant research w Pythonie" oczekiwany na te role; rozważane tylko jako ewentualny hot-path performance rewrite (nie w MVP, nie w tym ADR).
