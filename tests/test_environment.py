import duckdb
import numpy as np
import pandas as pd


def test_numpy_import_and_operation() -> None:
    array = np.array([1, 2, 3])
    assert array.sum() == 6


def test_pandas_import_and_operation() -> None:
    frame = pd.DataFrame({"a": [1, 2, 3]})
    assert frame["a"].sum() == 6


def test_duckdb_import_and_operation() -> None:
    con = duckdb.connect(":memory:")
    result = con.execute("SELECT 1 + 1").fetchone()
    assert result[0] == 2
