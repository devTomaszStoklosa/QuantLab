import numpy as np


def cagr(equity_curve: list[float], periods_per_year: int) -> float:
    if len(equity_curve) < 2:
        raise ValueError("cagr requires at least 2 equity points")
    total_periods = len(equity_curve) - 1
    total_growth = equity_curve[-1] / equity_curve[0]
    if total_growth <= 0:
        raise ValueError("cagr is undefined when total growth is zero or negative")
    return float(total_growth ** (periods_per_year / total_periods) - 1.0)


def sharpe(returns: list[float], periods_per_year: int, risk_free: float = 0.0) -> float:
    """Annualized Sharpe ratio using sample standard deviation (ddof=1).

    The observed returns are treated as a sample from an underlying process
    (consistent with this project's out-of-sample validation premise), so the
    unbiased estimator is used rather than population std (ddof=0).
    """
    if len(returns) < 2:
        raise ValueError("sharpe requires at least 2 return periods")
    excess = np.asarray(returns, dtype=np.float64) - risk_free
    std = excess.std(ddof=1)
    if std == 0.0:
        raise ValueError("sharpe is undefined when returns have zero variance")
    return float(excess.mean() / std * np.sqrt(periods_per_year))


def sortino(returns: list[float], periods_per_year: int, target: float = 0.0) -> float:
    """Annualized Sortino ratio.

    Downside deviation is the lower-partial-standard-deviation form,
    sqrt(mean(min(r - target, 0)**2)) - dividing by the full N, not N-1.
    This differs from sharpe()'s ddof=1 convention deliberately: it's the
    textbook Sortino definition, not an inconsistency.
    """
    if not returns:
        raise ValueError("sortino requires at least 1 return period")
    excess = np.asarray(returns, dtype=np.float64) - target
    downside = np.minimum(excess, 0.0)
    downside_deviation = np.sqrt(np.mean(downside**2))
    if downside_deviation == 0.0:
        raise ValueError("sortino is undefined when there are no returns below target")
    return float(excess.mean() / downside_deviation * np.sqrt(periods_per_year))


def drawdown_series(equity_curve: list[float]) -> list[float]:
    """Decline from the running peak at each point, as a negative fraction (0.0 at a peak)."""
    if not equity_curve:
        raise ValueError("drawdown_series requires at least 1 equity point")
    curve = np.asarray(equity_curve, dtype=np.float64)
    running_peak = np.maximum.accumulate(curve)
    return ((curve - running_peak) / running_peak).tolist()


def max_drawdown(equity_curve: list[float]) -> float:
    """Largest peak-to-trough decline, as a negative fraction (or 0.0 if none)."""
    if not equity_curve:
        raise ValueError("max_drawdown requires at least 1 equity point")
    return float(min(drawdown_series(equity_curve)))


def annualized_turnover(traded: list[float], periods_per_year: int) -> float:
    """Mean weight traded per period, as a multiple of equity per year.

    `traded` holds each period's sum of absolute weight changes, so opening a
    full position and later closing it adds 2.0.
    """
    if not traded:
        raise ValueError("annualized_turnover requires at least 1 period")
    return float(np.mean(traded) * periods_per_year)


def calmar(equity_curve: list[float], periods_per_year: int) -> float:
    drawdown = max_drawdown(equity_curve)
    if drawdown == 0.0:
        raise ValueError("calmar is undefined when there is no drawdown")
    return cagr(equity_curve, periods_per_year) / abs(drawdown)
