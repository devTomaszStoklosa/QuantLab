from itertools import combinations

import numpy as np
from pydantic import BaseModel


class PboResult(BaseModel):
    pbo: float  # share of splits with the in-sample best at or below the out-of-sample median
    n_configurations: int
    n_blocks: int
    n_splits: int
    rows_used: int  # the earliest rows that do not fill a whole block are dropped
    logit_median: float  # median of logit(relative out-of-sample rank of the in-sample best)


def _sharpe(sums: np.ndarray, squares: np.ndarray, count: int) -> np.ndarray:
    """Per-period Sharpe (ddof=1) from sums and sums of squares; 0 without variance."""
    mean = sums / count
    variance = (squares - sums * mean) / (count - 1)
    with np.errstate(divide="ignore", invalid="ignore"):
        sharpe = mean / np.sqrt(variance)
    return np.where(variance > 0.0, sharpe, 0.0)


def _ascending_ranks(values: np.ndarray, column: np.ndarray) -> np.ndarray:
    """Rank (1 = worst) of values[i, column[i]] within row i, ties sharing their average rank."""
    chosen = values[np.arange(len(values)), column][:, None]
    below = (values < chosen).sum(axis=1)
    tied = (values == chosen).sum(axis=1)
    return below + (tied + 1) / 2.0


def probability_of_backtest_overfitting(returns: np.ndarray, n_blocks: int = 16) -> PboResult:
    """PBO by combinatorially symmetric cross-validation (REQ-630..REQ-632).

    Bailey, Borwein, Lopez de Prado and Zhu (2017). `returns` is T x N: the
    per-period returns of N configurations on the same dates. The rows are cut
    into `n_blocks` consecutive blocks; every choice of half of them is the
    in-sample set and the rest out-of-sample. For each split the configuration
    with the best in-sample Sharpe gets its out-of-sample rank, as omega =
    rank / (N + 1); PBO is the share of splits where omega <= 0.5 - picking the
    in-sample winner did no better than the median out of sample.
    """
    matrix = np.asarray(returns, dtype=np.float64)
    if matrix.ndim != 2:
        raise ValueError("returns must be a T x N matrix")
    n_rows, n_configurations = matrix.shape
    if n_configurations < 2:
        raise ValueError("PBO needs at least 2 configurations")
    if n_blocks < 2 or n_blocks % 2:
        raise ValueError("n_blocks must be even and at least 2")
    block_size = n_rows // n_blocks
    if block_size < 1:
        raise ValueError(f"PBO with {n_blocks} blocks needs at least {n_blocks} rows")

    used = matrix[n_rows - block_size * n_blocks :]
    blocks = used.reshape(n_blocks, block_size, n_configurations)
    block_sums = blocks.sum(axis=1)
    block_squares = (blocks**2).sum(axis=1)

    splits = list(combinations(range(n_blocks), n_blocks // 2))
    in_sample = np.zeros((len(splits), n_blocks))
    for row, chosen in enumerate(splits):
        in_sample[row, list(chosen)] = 1.0
    count = block_size * n_blocks // 2

    sums_in, squares_in = in_sample @ block_sums, in_sample @ block_squares
    sums_out = block_sums.sum(axis=0) - sums_in
    squares_out = block_squares.sum(axis=0) - squares_in
    sharpe_in = _sharpe(sums_in, squares_in, count)
    sharpe_out = _sharpe(sums_out, squares_out, count)

    best = sharpe_in.argmax(axis=1)
    omega = _ascending_ranks(sharpe_out, best) / (n_configurations + 1)
    logits = np.log(omega / (1.0 - omega))
    return PboResult(
        pbo=float((logits <= 0.0).mean()),
        n_configurations=n_configurations,
        n_blocks=n_blocks,
        n_splits=len(splits),
        rows_used=block_size * n_blocks,
        logit_median=float(np.median(logits)),
    )
