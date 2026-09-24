from collections.abc import Callable, Mapping
from datetime import date
from statistics import median
from typing import Literal, Self

from pydantic import BaseModel, model_validator

from quantlab.backtest.vectorized.engine import BacktestRun
from quantlab.core.data.provider import PriceBar

Side = Literal["long", "short"]

HOLDING_PERIOD_BUCKETS = ("1-7d", "8-30d", "31-90d", "91-365d", "366d+")
_HOLDING_PERIOD_LIMITS = ((7, "1-7d"), (30, "8-30d"), (90, "31-90d"), (365, "91-365d"))


class Trade(BaseModel):
    """One stretch of holding an instrument on one side (REQ-060).

    The engine rebalances daily, so a trade opens at the close where a position
    appears or flips and closes at the close where it disappears or flips;
    rebalancing in between adjusts the same trade. P&L is in equity units of a
    portfolio that started at 1.0, so all trades' net P&L sums to the run's
    equity change. `size` is the absolute weight at entry, as a fraction of
    equity: normalized equity has no coin quantities.
    """

    instrument_id: str
    side: Side
    entry_ts: date
    entry_price: float
    exit_ts: date
    exit_price: float
    size: float
    gross_pnl: float
    costs: float
    net_pnl: float
    holding_days: int
    regime_at_entry: str
    open_at_end: bool  # still held when the run ended: closed at the last close, no exit cost

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.exit_ts <= self.entry_ts:
            raise ValueError(f"Trade exit {self.exit_ts} is not after its entry {self.entry_ts}")
        if self.size <= 0 or self.entry_price <= 0 or self.exit_price <= 0:
            raise ValueError("Trade size and prices must be positive")
        return self


class _OpenTrade:
    def __init__(
        self,
        instrument_id: str,
        side: Side,
        entry_ts: date,
        entry_price: float,
        size: float,
        regime: str,
    ) -> None:
        self.instrument_id = instrument_id
        self.side = side
        self.entry_ts = entry_ts
        self.entry_price = entry_price
        self.size = size
        self.regime = regime
        self.gross_pnl = 0.0
        self.costs = 0.0

    def close(self, exit_ts: date, exit_price: float, open_at_end: bool) -> Trade:
        return Trade(
            instrument_id=self.instrument_id,
            side=self.side,
            entry_ts=self.entry_ts,
            entry_price=self.entry_price,
            exit_ts=exit_ts,
            exit_price=exit_price,
            size=self.size,
            gross_pnl=self.gross_pnl,
            costs=self.costs,
            net_pnl=self.gross_pnl - self.costs,
            holding_days=(exit_ts - self.entry_ts).days,
            regime_at_entry=self.regime,
            open_at_end=open_at_end,
        )


def _side(weight: float) -> Side | None:
    if weight > 0:
        return "long"
    if weight < 0:
        return "short"
    return None


def build_trade_ledger(
    run: BacktestRun, bars: dict[str, list[PriceBar]], regime_labels: Mapping[date, str]
) -> list[Trade]:
    """Trades of a run, each with the regime as of its entry close.

    Each day adds equity-at-previous-close * weight * instrument return to the
    trade holding that instrument, and the period's cost for the instrument
    (recorded per instrument by the engine) the same way. A flip costs the
    engine one trade for both legs; it is split between the closing and the
    opening trade in proportion to the weights traded, which is exact for cost
    models linear in traded weight and always keeps the total.
    """
    closes = {instrument_id: {bar.ts: bar.close for bar in b} for instrument_id, b in bars.items()}
    snapshots = run.snapshots
    open_trades: dict[str, _OpenTrade] = {}
    trades: list[Trade] = []

    for k in range(1, len(snapshots)):
        previous, current = snapshots[k - 1], snapshots[k]
        instrument_ids = open_trades.keys() | current.positions.keys() | current.costs.keys()
        for instrument_id in sorted(instrument_ids):
            instrument_closes = closes[instrument_id]
            weight = current.positions.get(instrument_id, 0.0)
            side = _side(weight)
            cost = current.costs.get(instrument_id, 0.0) * previous.equity
            trade = open_trades.get(instrument_id)

            if trade is not None and trade.side != side:
                closing_share = 1.0
                if side is not None:
                    # Flip: the old leg traded is its weight after the last day's drift.
                    before = snapshots[k - 2]
                    held = (
                        previous.positions[instrument_id]
                        * (instrument_closes[previous.ts] / instrument_closes[before.ts])
                        / (previous.equity / before.equity)
                    )
                    closing_share = abs(held) / (abs(held) + abs(weight))
                trade.costs += cost * closing_share
                cost -= cost * closing_share
                trades.append(
                    trade.close(previous.ts, instrument_closes[previous.ts], open_at_end=False)
                )
                del open_trades[instrument_id]
                trade = None

            if side is None:
                continue
            if trade is None:
                if previous.ts not in regime_labels:
                    raise ValueError(f"No regime label for {previous.ts}")
                trade = _OpenTrade(
                    instrument_id,
                    side,
                    previous.ts,
                    instrument_closes[previous.ts],
                    abs(weight),
                    regime_labels[previous.ts],
                )
                open_trades[instrument_id] = trade
            trade.costs += cost
            trade.gross_pnl += (
                previous.equity
                * weight
                * (instrument_closes[current.ts] / instrument_closes[previous.ts] - 1.0)
            )

    last = snapshots[-1].ts
    for instrument_id, trade in open_trades.items():
        trades.append(trade.close(last, closes[instrument_id][last], open_at_end=True))
    return sorted(trades, key=lambda trade: (trade.entry_ts, trade.instrument_id))


class PnlGroup(BaseModel):
    key: str
    trades: int
    win_rate: float
    total_net_pnl: float
    mean_net_pnl: float
    median_net_pnl: float
    worst_net_pnl: float
    best_net_pnl: float
    costs: float


def group_pnl(trades: list[Trade], key: Callable[[Trade], str]) -> dict[str, PnlGroup]:
    """Distribution of net P&L per group, not just its total (REQ-061)."""
    groups: dict[str, list[float]] = {}
    costs: dict[str, float] = {}
    for trade in trades:
        group = key(trade)
        groups.setdefault(group, []).append(trade.net_pnl)
        costs[group] = costs.get(group, 0.0) + trade.costs
    return {
        group: PnlGroup(
            key=group,
            trades=len(pnl),
            win_rate=sum(1 for value in pnl if value > 0) / len(pnl),
            total_net_pnl=sum(pnl),
            mean_net_pnl=sum(pnl) / len(pnl),
            median_net_pnl=median(pnl),
            worst_net_pnl=min(pnl),
            best_net_pnl=max(pnl),
            costs=costs[group],
        )
        for group, pnl in groups.items()
    }


def by_regime(trade: Trade) -> str:
    return trade.regime_at_entry


def by_holding_period(trade: Trade) -> str:
    for max_days, bucket in _HOLDING_PERIOD_LIMITS:
        if trade.holding_days <= max_days:
            return bucket
    return HOLDING_PERIOD_BUCKETS[-1]


def by_exit_month(trade: Trade) -> str:
    return f"{trade.exit_ts:%Y-%m}"
