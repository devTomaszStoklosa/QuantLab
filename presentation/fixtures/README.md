# Syntetyczny magazyn wyników

`results/` to magazyn wyników w formacie, który zapisuje `quantlab run` ([ADR-0008](../../docs/adr/0008-results-store-parquet-duckdb.md), schemat w [02-spec.md](../../docs/specs/q7-dotnet-react-presentation/02-spec.md)), wygenerowany pełnym pipeline'em na **danych syntetycznych**. Czytają go testy API .NET i tryb demo aplikacji. Hipotezy `demo_*` i źródło danych `synthetic` — to nie są wyniki badań. `demo_xsmom` to momentum przekrojowe na syntetycznym point-in-time uniwersum akcji (dołączający i odchodzący członkowie, split 4:1, dwa delistingi, jeden z założonym zwrotem). `demo_select` (`q8`) to momentum szeregów czasowych z lookbackiem wybieranym co rok z siatki 30/90/180 i CPCV procedury wyboru jako zamrożoną bramką in-sample; jego trzy wartości liczą się jako konfiguracje w progu DSR pozostałych hipotez krypto.

Regeneracja po zmianie tego, co zapisuje magazyn (test `tests/test_results_fixture.py` jest czerwony, dopóki plik nie jest aktualny):

```bash
QUANTLAB_UPDATE_FIXTURES=1 uv run pytest tests/test_results_fixture.py
```
