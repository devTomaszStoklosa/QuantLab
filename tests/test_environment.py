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


def test_scipy_import_and_operation() -> None:
    from scipy import stats

    assert stats.norm.cdf(0.0) == 0.5


def test_statsmodels_import_and_operation() -> None:
    # Native code (Cython, scipy's BLAS/LAPACK); the dev machine has no AVX2.
    from statsmodels.tsa.stattools import adfuller

    rng = np.random.default_rng(0)
    result = adfuller(rng.normal(size=200), result_object=True)
    assert result.statistic < 0
    assert result.pvalue < 0.01
