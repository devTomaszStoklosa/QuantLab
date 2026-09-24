from datetime import date

from quantlab.backtest.event_driven.feed import BarFeed
from quantlab.backtest.event_driven.orders import Execution, Order, OrderRecord
from quantlab.backtest.run import PortfolioSnapshot
from quantlab.costs.base import CostModel

# Orders worth less than this fraction of equity are floating-point residue of
# re-targeting the same weight, not trades; skipping them keeps the engine at
# parity with the vectorized one. Unrelated to any exchange's minimum order.
_DUST = 1e-12


class Portfolio:
    """Cash and instrument quantities, in currency, with the snapshot contract.

    Orders are sized at the decision close from its equity (REQ-222); fills
    move cash and quantities and are charged through the cost model at the
    decision date (REQ-240). Snapshots follow the shared semantics of the
    02-spec business rules, normalized to the starting capital.
    """

    def __init__(self, capital: float, cost_model: CostModel, feed: BarFeed) -> None:
        if capital <= 0:
            raise ValueError("Starting capital must be positive")
        self.capital = capital
        self.cost_model = cost_model
        self.feed = feed
        self.cash = capital
        self.quantities: dict[str, float] = {}
        self.snapshots: list[PortfolioSnapshot] = []
        self.records: list[OrderRecord] = []
        self._decision_equity: float | None = None
        self._decision_prices: dict[str, float] = {}
        self._snapshot_equity = capital
        self._period_costs: dict[str, float] = {}
        self._period_traded: dict[str, float] = {}

    def equity(self) -> float:
        """Cash plus every holding at its last known close."""
        return self.cash + sum(
            quantity * self.feed.last_close(instrument_id)
            for instrument_id, quantity in sorted(self.quantities.items())
        )

    def snapshot(self, ts: date) -> None:
        equity = self.equity()
        positions = {}
        if self._decision_equity is not None:
            positions = {
                instrument_id: quantity
                * self._decision_prices[instrument_id]
                / self._decision_equity
                for instrument_id, quantity in sorted(self.quantities.items())
            }
        normalized = equity / self.capital
        invested = sum(abs(weight) for weight in positions.values())
        self.snapshots.append(
            PortfolioSnapshot(
                ts=ts,
                cash=normalized * (1.0 - invested),
                positions=positions,
                equity=normalized,
                costs={
                    instrument_id: cost / self._snapshot_equity
                    for instrument_id, cost in self._period_costs.items()
                },
                traded=self._period_traded,
            )
        )
        self._snapshot_equity = equity
        self._period_costs = {}
        self._period_traded = {}

    def rebalance(self, weights: dict[str, float], ts: date) -> list[Order]:
        """Orders moving holdings to `weights` of the current equity.

        Instruments with a target weight must have a bar today; everything held
        but not targeted is closed to exactly zero.
        """
        equity = self.equity()
        self._decision_equity = equity
        self._decision_prices = {
            instrument_id: close
            for instrument_id in sorted(self.quantities.keys() | weights.keys())
            if (close := self.feed.last_close(instrument_id)) is not None
        }
        orders = []
        for instrument_id, price in self._decision_prices.items():
            held = self.quantities.get(instrument_id, 0.0)
            target = weights.get(instrument_id, 0.0) * equity / price
            quantity = target - held if instrument_id in weights else -held
            if abs(quantity) * price / equity < _DUST:
                continue
            orders.append(
                Order(
                    instrument_id=instrument_id,
                    decision_ts=ts,
                    quantity=quantity,
                    decision_equity=equity,
                )
            )
        return orders

    def apply(self, executions: list[Execution]) -> None:
        for execution in executions:
            order = execution.order
            instrument_id = order.instrument_id
            cost = 0.0
            if execution.filled_quantity != 0.0:
                traded_weight = (
                    abs(execution.filled_quantity) * execution.fill_price / order.decision_equity
                )
                cost = (
                    self.cost_model.cost(
                        self.feed.instrument_history(instrument_id),
                        order.decision_ts,
                        traded_weight,
                    )
                    * order.decision_equity
                )
                held = self.quantities.get(instrument_id, 0.0) + execution.filled_quantity
                if held == 0.0:
                    self.quantities.pop(instrument_id, None)
                else:
                    self.quantities[instrument_id] = held
                self.cash -= execution.filled_quantity * execution.fill_price + cost
                self._period_costs[instrument_id] = (
                    self._period_costs.get(instrument_id, 0.0) + cost
                )
                self._period_traded[instrument_id] = (
                    self._period_traded.get(instrument_id, 0.0) + traded_weight
                )
            self.records.append(
                OrderRecord(
                    instrument_id=instrument_id,
                    decision_ts=order.decision_ts,
                    quantity=order.quantity,
                    decision_equity=order.decision_equity,
                    filled_quantity=execution.filled_quantity,
                    fill_ts=execution.fill_ts,
                    fill_price=execution.fill_price,
                    cost=cost,
                )
            )
