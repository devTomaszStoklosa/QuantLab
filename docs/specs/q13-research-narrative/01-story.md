# q13-research-narrative - Opis wyniku składany z liczb policzonych kodem

Status: Ready for dev
Owner role: PO
Upstream: docs/specs/q7-dotnet-react-presentation/, docs/specs/q10-local-runbook/
Links: docs/ROADMAP.md, docs/RESEARCH_LOG.md, CLAUDE.md (zasada 3)

## Problem

Każda zamrożona hipoteza kończy się wpisem w `docs/RESEARCH_LOG.md`. Do napisania jest dziewięć takich wpisów, a `quantlab plan` pokazuje je jako kroki ręczne.

1. **Wpis przepisuje się ręcznie z terminala.** Wpis `momentum_v1` ma kilkadziesiąt liczb z pięciu źródeł:
   - metryki trzech modeli kosztów;
   - okna walk-forward;
   - test permutacyjny;
   - reżimy;
   - zapis otwarcia holdoutu.

   Przepisywanie jest żmudne i pozwala na błędy. Pomyłka w liczbie we wpisie dziennika podważa cały proces, który ma być rzetelny.
2. **Aplikacja pokazuje liczby, nie ich sens.** Panele pokazują tabele, ale nie mówią słowami, co z nich wynika: czy bramka przeszła na granicy, ile wyniku zabrały koszty, który reżim dał wynik.
3. **Zasada 3 z CLAUDE.md** mówi: „kod liczy, model objaśnia", jeśli kiedyś pojawi się LLM. Model językowy musiałby jednak być płatny (API) albo lokalny, a lokalny na maszynie deweloperskiej jest za wolny (i5-2500K bez AVX2, 8 GB RAM). Tomasz zdecydował 2026-09-26, że opis ma powstawać z szablonów w kodzie: za darmo, deterministycznie i bez ryzyka zmyślonych liczb.

## Outcome

Primary metric: każdy z dziewięciu wpisów w dzienniku zaczyna się od szkicu wygenerowanego przez `quantlab narrate`, bez ręcznego przepisywania liczb. Aplikacja pokazuje opis wyniku każdej hipotezy z przebiegiem.
Guardrail metric: każda liczba w opisie pochodzi z magazynu wyników albo z zapisu otwarcia holdoutu (test). W opisie nie ma słów rekomendacji ([ADR-0005](../../adr/0005-descriptive-reports-no-investment-advice.md)). Wyniki i werdykty hipotez się nie zmieniają.

## User story

Jako badacz chcę dostać szkic wpisu do dziennika i krótki opis wyniku złożone przez kod z tych samych liczb, które zapisał przebieg i otwarcie holdoutu. Chcę pisać tylko interpretację, a nie przepisywać tabel, i chcę, żeby aplikacja mówiła to samo słowami.

## Acceptance criteria

- AC-1 (szkic wpisu): Given hipoteza z przebiegiem treningowym w magazynie, when uruchamiam `quantlab narrate <hipoteza>`, then dostaję szkic w formacie dziennika: nagłówek `## <data> — <hipoteza>`, **Hipoteza**, **Metodologia**, **Wynik** (trening i holdout) i **Wniosek**. Liczby są w nim sformatowane jak w istniejących wpisach, a akapit interpretacji zostaje do uzupełnienia przez badacza.
- AC-2 (tylko liczby z kodu): Given szkic albo opis, when porównuję liczby w tekście z magazynem wyników i zapisem otwarcia, then każda liczba ma tam źródło. Tekst ze statusem, bramką i werdyktem zgadza się ze statusem liczonym przez kod (`concluded_status`).
- AC-3 (bez rekomendacji): Given dowolne liczby, when narrator składa tekst, then nie ma w nim zaleceń („kup", „sprzedaj", „zwiększ", „warto zainwestować" itp.), tylko opis historycznych wyników.
- AC-4 (holdout): Given hipoteza z otwartym albo zamkniętym holdoutem, when składam opis, then:
  - otwarty holdout daje werdykt z zapisu otwarcia i status końcowy;
  - nieotwarty holdout daje zdanie, że wniosku jeszcze nie ma, i nazwę komendy, która holdout otwiera.
- AC-5 (aplikacja): Given magazyn wyników po `quantlab run` albo `open-holdout`, when otwieram hipotezę w aplikacji, then widzę opis wyniku po polsku, aktualny względem otwarcia holdoutu. Magazyn bez opisu (sprzed tego epiku) nie psuje aplikacji.
- AC-6 (plan): Given krok `log:<hipoteza>` w stanie `pending`, when uruchamiam `quantlab plan`, then krok podaje komendę `quantlab narrate <hipoteza>`.

## Out of scope

- Model językowy, lokalny i przez API. Interfejs `Narrator` pozwala go dodać później jako osobny epik, jeśli szablony okażą się za sztywne.
- Automatyczny zapis do `docs/RESEARCH_LOG.md`. Szkic trafia do terminala albo pliku, a interpretację i commit robi badacz.
- Opis w tear-sheecie. Tear-sheet powstaje w trakcie przebiegu, przed odświeżeniem rejestru; można go dodać później.
- Tłumaczenie opisu na angielski. Raporty są po polsku (CLAUDE.md).

## Priority

Should have: ostatni kandydat z listy po `q12`, rozpoczęty 2026-09-26 („Start NEXT task"). Wybór szablonów zamiast modelu to decyzja Tomasza z 2026-09-26. Całość powstaje na danych syntetycznych (magazyn `demo_*`).

## Dependencies and risks

- Zależy od `q7` (magazyn wyników, rejestr, API, aplikacja), `q10` (plan) i `q12` (P&L per klasa aktywów).
- **Ryzyko: szablon wypaczy sens liczby,** np. „walk-forward zaliczony" bez zastrzeżenia, że na granicy reguły. Mitygacja: szablon opisuje tylko fakty z reguł, np. „5 z 6 okien ze Sharpe > 0, reguła wymaga 2/3". Ocenę zostawia interpretacji badacza.
- **Ryzyko: opis nieaktualny po otwarciu holdoutu.** Mitygacja: opis w magazynie odświeża się przy każdym odświeżeniu rejestru (`run`, `open-holdout`, `registry`).
- **Ryzyko: nowa tabela w magazynie.** Mitygacja: tabela jest dodatkowa, a API traktuje jej brak jak pusty opis, więc wersja schematu się nie zmienia i przebiegi nie stają się nieaktualne.

## Open questions

Brak. Sposób generowania (szablony w kodzie) rozstrzygnięty przez Tomasza 2026-09-26.
