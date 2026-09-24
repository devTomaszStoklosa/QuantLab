from datetime import date

from pydantic import BaseModel, Field

from quantlab.core.data.provider import PriceBar


class PortfolioSnapshot(BaseModel):
    ts: date
    cash: float
    positions: dict[str, float]
    equity: float
    # Cost charged per instrument in the period ending at ts, as a fraction of
    # the previous snapshot's equity; includes instruments being closed.
    costs: dict[str, float] = Field(default_factory=dict)
    # Absolute weight traded per instrument at the rebalance opening that period,
    # measured against the weights held after the previous period's price moves.
    traded: dict[str, float] = Field(default_factory=dict)


class BacktestRun(BaseModel):
    """Result contract shared by both engines (ADR-0002)."""

    id: str
    strategy_name: str
    strategy_params: dict
    cost_model_name: str
    universe_name: str
    start: date
    end: date
    seed: int
    git_sha: str
    snapshots: list[PortfolioSnapshot]


def trading_dates(bars: dict[str, list[PriceBar]], start: date, end: date) -> list[date]:
    """Every date in [start, end] on which at least one instrument has a bar."""
    dates = {
        bar.ts
        for instrument_bars in bars.values()
        for bar in instrument_bars
        if start <= bar.ts <= end
    }
    return sorted(dates)
