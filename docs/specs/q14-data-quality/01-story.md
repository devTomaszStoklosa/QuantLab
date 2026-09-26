# q14-data-quality - Kontrola jakości danych przed przebiegiem

Status: Ready for dev
Owner role: PO
Upstream: docs/specs/q5-equities-cross-section/, docs/specs/q10-local-runbook/, docs/specs/q12-cross-asset-momentum/
Links: docs/ROADMAP.md, docs/DATA-SOURCES.md, docs/INSTRUKCJA.md

## Problem

Osiem zamrożonych hipotez czeka na pierwszy przebieg na prawdziwych danych: Binance (krypto), Tiingo (ETF-y i S&P 500 z tysiącem tickerów, korektami o splity i dywidendy). Silnik ufa danym bez sprawdzenia:

1. **Wada danych daje fałszywy wynik po cichu.** Zduplikowana data, cena zero albo ujemna, dziura w sesjach, cena zamrożona przez tygodnie albo źle zastosowany split (skok −75% w dniu, w którym nic się nie stało) zmieniają zwroty, sygnały i wszystkie statystyki. Nic tego nie zgłasza.
2. **Holdout otwiera się raz.** Wada wykryta po otwarciu oznacza wynik na złych danych, którego nie da się uczciwie powtórzyć.
3. **Wpis `momentum_v1` sprawdzał dane ręcznie** („bez luk i duplikatów w obu okresach"). Przy S&P 500 ręczne sprawdzenie tysiąca tickerów jest niewykonalne.

## Outcome

Primary metric: każdy przebieg treningowy i każde otwarcie holdoutu zaczyna się od kontroli danych. Wady krytyczne zatrzymują przebieg przed backtestem, a pozostałe są raportowane w terminalu, tear-sheecie, magazynie i aplikacji.
Guardrail metric: dane się nie zmieniają (kontrola tylko czyta); wyniki i werdykty hipotez na poprawnych danych identyczne co do bitu (zrzut regresji).

## User story

Jako badacz chcę, żeby laboratorium sprawdziło pobrane dane, zanim policzy na nich wynik. Wady, które unieważniają obliczenia, mają zatrzymać przebieg z jasną informacją. Podejrzane miejsca mają trafić do raportu z datami, żebym mógł je obejrzeć przed otwarciem holdoutu.

## Acceptance criteria

- AC-1 (kontrole): Given bary instrumentów po korektach, when uruchamiam kontrolę, then dostaję ustalenia z nazwą kontroli, instrumentem, datą i opisem:
  - zduplikowane daty;
  - ceny ≤ 0 (poza barem delistingu);
  - niespójne OHLC (high poniżej open/close/low albo low powyżej open/close/high);
  - brakujące sesje;
  - cena zamknięcia bez zmian przez wiele sesji;
  - skrajne ruchy względem zwykłej zmienności instrumentu.
- AC-2 (błędy zatrzymują): Given ustalenie krytyczne (zduplikowana data, cena ≤ 0), when uruchamiam `quantlab run` albo `open-holdout`, then:
  - przebieg kończy się przed backtestem komunikatem z listą wad i komendą `quantlab check-data`;
  - holdout nie zostaje otwarty ani zapisany.
- AC-3 (ostrzeżenia raportują): Given ustalenia niekrytyczne, when uruchamiam `quantlab run`, then:
  - terminal pokazuje podsumowanie i do 10 przykładów;
  - tear-sheet, magazyn wyników i aplikacja pokazują liczby ustaleń per kontrola jako diagnostykę „Data quality";
  - wynik i werdykt się nie zmieniają.
- AC-4 (komenda): Given hipoteza, when uruchamiam `quantlab check-data <hipoteza>`, then:
  - dostaję pełną listę ustaleń dla danych okresu treningowego (z rozgrzewką);
  - danych holdoutu komenda nie czyta.
- AC-5 (kalendarz): Given rynek notowany codziennie (krypto), when szukam brakujących sesji, then każdy dzień kalendarzowy jest sesją. Given rynek z weekendami i świętami, then sesjami są dni, w które notuje którykolwiek instrument uniwersum, więc święta nie są brakami.

## Out of scope

- Poprawianie danych (uzupełnianie luk, usuwanie skoków). Kontrola tylko czyta; decyzja o danych należy do badacza, a zmiana źródła albo reguły czyszczenia byłaby nową hipotezą.
- Kontrola danych holdoutu poza otwarciem. Oglądanie danych holdoutu przed otwarciem łamałoby pre-rejestrację.
- Porównanie dwóch źródeł tej samej ceny.

## Priority

Should have. Następny epik po `q13` (2026-09-26), przed pierwszymi lokalnymi przebiegami ośmiu hipotez. Całość na danych syntetycznych z wadami wstawionymi celowo.

## Dependencies and risks

- Zależy od `q5` (korekty o akcje korporacyjne, delisting), `q7` (diagnostyka treningu w magazynie i aplikacji), `q10` (plan) i `q12` (kalendarz sesji uniwersum).
- **Ryzyko: prawdziwy krach wygląda jak wada.** Skrajny ruch (np. 2020-03-12 w krypto) jest prawdziwy. Mitygacja: skrajne ruchy to ostrzeżenia z datą, nigdy błędy.
- **Ryzyko: zatrzymanie zmienia zachowanie zamrożonych hipotez.** Mitygacja: zatrzymanie nie zmienia żadnej liczby. Na danych bez wad krytycznych przebieg jest identyczny (zrzut regresji), a na danych z wadami wynik i tak byłby nieważny.
- **Ryzyko: fałszywe braki sesji w uniwersum point-in-time.** Instrument poza członkostwem nie ma barów. Mitygacja: braki liczone tylko między pierwszym a ostatnim barem instrumentu.

## Open questions

Brak. Progi kontroli są metodologią laboratorium, wspólną dla wszystkich hipotez i opisaną w specyfikacji; nie są parametrami hipotez.
