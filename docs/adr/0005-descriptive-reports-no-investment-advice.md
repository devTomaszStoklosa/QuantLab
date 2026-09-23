# 0005. Raporty opisowe, bez rekomendacji inwestycyjnych

Status: Proposed

## Context

Platforma generuje raporty o wynikach strategii testowych na historycznych danych. Repo jest publiczne od początku (projekt portfolio) — spersonalizowana rekomendacja dotycząca instrumentów finansowych to w UE doradztwo inwestycyjne (MiFID II), w Polsce wymagające zezwolenia KNF.

## Decision

- Raporty (tear-sheet, dziennik badawczy) opisują fakty historyczne: wyniki, ryzyko, ekspozycje, zachowanie w reżimach. Nie mówią „kup", „sprzedaj", „zwiększ", „powinieneś".
- Każdy raport i README niosą stałą informację: wyniki są historyczne i edukacyjne, nie są rekomendacją inwestycyjną.

## Consequences

- Pozytywne: bezpieczna podstawa prawna dla publicznego repo; spójne z tym, jak platforma ma być czytana przez rekrutera — analiza, nie doradztwo.
- Negatywne: raporty mniej „akcyjne" — nie odpowiadają wprost na „co kupić".

## Alternatives considered

- **Rekomendacje z disclaimerem** — disclaimer nie zmienia kwalifikacji prawnej spersonalizowanej rekomendacji.
