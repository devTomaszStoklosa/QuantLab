# 0004. Walidacja jako warunek „confirmed", zamrożony holdout

Status: Proposed

## Context

Najważniejszy element projektu (patrz README) to proces badawczy, nie pojedyncza działająca strategia. Bez wymuszonej dyscypliny walidacyjnej łatwo o samooszukanie się: wielokrotne zerkanie na wynik testowy i dostrajanie parametrów aż „zadziała" (data snooping).

## Decision

- Status hipotezy w `docs/RESEARCH_LOG.md` może być `confirmed` wyłącznie po przejściu walk-forward i po sprawdzeniu na zamrożonym holdout.
- Holdout: zakres dat i parametry hipotezy zapisane w pliku i commitowane PRZED pierwszym uruchomieniem na tym zakresie — analogicznie do pre-rejestracji badania naukowego.
- `rejected` i `inconclusive` to pełnoprawne, równie starannie opisane wyniki — dziennik badawczy nie jest listą sukcesów.

## Consequences

- Pozytywne: wynik `confirmed` ma realną wartość dowodową, nie jest artefaktem wielokrotnego testowania; mocny argument w rozmowie rekrutacyjnej o rygorze metodologicznym.
- Negatywne: więcej dyscypliny i formalności niż w typowym „pobaw się danymi" podejściu — wolniej dochodzi się do wyniku.

## Alternatives considered

- **Walidacja jako opcjonalny krok na końcu** — łatwo pominąć pod presją czasu, wtedy cały projekt traci swój najmocniejszy argument.
- **Cross-validation bez purge/embargo** — dla szeregów czasowych z nakładającymi się etykietami przecieka informacja między foldami; rozważane jako rozszerzenie (`q6`, CPCV), nie w MVP.
