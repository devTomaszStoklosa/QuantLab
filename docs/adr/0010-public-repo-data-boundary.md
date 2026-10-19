# 0010. Publiczne repozytorium i granica danych

Status: Accepted

## Context

[ADR-0009](0009-private-repo-free-tiingo-plan.md) uczynił repozytorium prywatnym, bo licencja darmowego planu Tiingo pozwala tylko na użytek własny, a jako odrzuconą alternatywę wskazał publiczne repozytorium z wynikami z cenami. Cel projektu to portfolio pod role Quantitative Developer / Quantitative Analyst: kod, metodologia i wnioski mają być dostępne dla osoby oceniającej, a nie ukryte za logowaniem.

Obie rzeczy da się pogodzić, jeśli publiczne jest tylko to, co nie jest danymi rynkowymi. Ta decyzja wyznacza granicę. Źródło danych, limity i zasada „tylko darmowe" z ADR-0009 pozostają bez zmian.

## Decision

Repozytorium jest publiczne. Granica jest następująca:

| W repozytorium (publiczne) | Poza repozytorium (tylko u badacza) |
|---|---|
| kod, testy, konfiguracja CI | surowe odpowiedzi API i cache (`data/raw/`, `data/cache/`) |
| metodologia, ADR-y, specyfikacje, dziennik badawczy | magazyn wyników z przebiegów na prawdziwych danych (`results/`) |
| syntetyczne fixtures (`data/fixtures/`, `presentation/fixtures/`) | tear-sheety (`reports/`) |
| zagregowane statystyki: Sharpe, CAGR, drawdown, p-value, werdykt, zapisy otwarcia holdoutu | szeregi cen, krzywe kapitału i rejestr transakcji z prawdziwych danych |
| skład indeksów (tylko członkostwo, bez cen) z atrybucją Wikipedii (CC BY-SA 4.0) | klucze API i plik `.env` |

- **Licencja kodu to MIT** (plik `LICENSE`). Nie obejmuje danych rynkowych ani plików składu indeksów, które pozostają na CC BY-SA 4.0.
- **Granicę pilnuje test** `tests/test_public_repo_hygiene.py`, uruchamiany w CI: pliki danych poza dozwolonymi katalogami fixtures, pliki ponad limit rozmiaru i wzorce kluczy API zatrzymują build. `.gitignore` zostaje pierwszą linią obrony, test drugą.
- **Zagregowane statystyki zostają w dzienniku badawczym.** Sharpe, p-value czy werdykt nie pozwalają odtworzyć cen. To ocena ryzyka licencyjnego, nie porada prawna; jeśli dostawca zmieni warunki albo zgłosi zastrzeżenia, wpisy z danych Tiingo są usuwane, a dziennik zachowuje metodologię.
- **Kolejne źródła i zmiany granicy** wymagają nowego ADR-a. Przed zmianą widoczności repozytorium trzeba ponownie przeczytać aktualne warunki Binance i Tiingo.

## Consequences

- Pozytywne:
  - portfolio jest dostępne bez logowania, razem z procesem badawczym, także z hipotezami odrzuconymi;
  - granica jest jawna i sprawdzana maszynowo, więc przypadkowy commit danych kończy się czerwonym buildem;
  - GitHub Actions jest bezpłatne w publicznym repozytorium, więc znika limit minut z ADR-0009.
- Negatywne:
  - forków i klonów po upublicznieniu nie da się cofnąć, więc błąd w granicy jest trwały; stąd test i skan historii przed zmianą widoczności;
  - przebiegi na prawdziwych danych nadal wymagają kluczy i działają tylko lokalnie; osoba z zewnątrz uruchomi testy i tryb demo na danych syntetycznych;
  - ryzyko licencyjne zagregowanych statystyk z Tiingo jest zaakceptowane, nie wyeliminowane.
- [ADR-0005](0005-descriptive-reports-no-investment-advice.md) nadal obowiązuje: raporty są opisowe, bez rekomendacji.

## Alternatives considered

- **Repozytorium prywatne dalej (ADR-0009):** bezpieczne licencyjnie, ale portfolio niewidoczne dla rekrutera bez zaproszenia.
- **Publikacja wyników z cenami:** niezgodna z licencją użytku własnego.
- **Płatny plan Tiingo z prawem redystrybucji:** łamie zasadę „tylko darmowe".
- **Skaner sekretów jako akcja zewnętrzna w CI:** nowa zależność łańcucha dostaw dla trzech prostych reguł; wystarcza własny test oraz natywne skanowanie sekretów GitHuba.
