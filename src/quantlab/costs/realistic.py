from datetime import date

import numpy as np

from quantlab.core.data.provider import PriceBar


class RealisticCostModel:
    """Fee plus slippage scaled by the instrument's recent volatility.

    cost = (fee_bps / 10_000 + k * sigma) * traded_weight, where sigma is the
    sample standard deviation of the last `vol_window` daily returns up to
    as_of. There's no market-impact term: a square-root impact model needs
    order size against traded volume, and the engine works in normalized
    equity with no notional amount.
    """

    def __init__(self, fee_bps: float, k: float, vol_window: int) -> None:
        self.fee_bps = fee_bps
        self.k = k
        self.vol_window = vol_window
        self.name = f"realistic-{fee_bps:g}bps-k{k:g}-vol{vol_window}d"

    def cost(self, instrument_bars: list[PriceBar], as_of: date, traded_weight: float) -> float:
        closes = np.array(
            [
                bar.close
                for bar in sorted(instrument_bars, key=lambda bar: bar.ts)
                if bar.ts <= as_of
            ][-(self.vol_window + 1) :],
            dtype=np.float64,
        )
        returns = closes[1:] / closes[:-1] - 1.0
        if len(returns) < 2:
            raise ValueError(
                f"Need at least 2 daily returns up to {as_of} to estimate volatility"
            )
        sigma = returns.std(ddof=1)
        return (self.fee_bps / 10_000 + self.k * sigma) * traded_weight
