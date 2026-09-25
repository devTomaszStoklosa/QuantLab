"""What a hypothesis choosing its parameter from a grid shows: choices, PBO, CPCV (q8)."""

from collections.abc import Callable
from datetime import date

from pydantic import BaseModel

from quantlab.research.definition import GridEvidence
from quantlab.validation.base import ValidationResult
from quantlab.validation.cpcv import CpcvResult, CpcvSettings, cpcv_gate, cpcv_of_selection
from quantlab.validation.pbo import PboResult, probability_of_backtest_overfitting


class GridYear(BaseModel):
    """One yearly choice, with every value's Sharpe on the history before it."""

    year: int
    days: int  # calendar days of history evaluated
    sharpes: dict[str, float | None]  # annualized, in grid order
    chosen: str | None  # None: too little history, or no value with a Sharpe


class GridReport(BaseModel):
    """The evidence of a grid over a training period, as printed, stored and shown."""

    labels: list[str]
    start: date  # the window every value can signal in
    end: date
    years: list[GridYear]
    pbo: PboResult | None  # None with too few days for its blocks
    cpcv: CpcvResult


def grid_report(
    grid: GridEvidence, settings: CpcvSettings, periods_per_year: int, pbo_blocks: int
) -> GridReport:
    """Choices, PBO (CSCV) and CPCV of a grid's evidence (REQ-813, REQ-821)."""
    annualize = periods_per_year**0.5
    returns = grid.returns
    return GridReport(
        labels=grid.labels,
        start=grid.start,
        end=grid.end,
        years=[
            GridYear(
                year=record.year,
                days=record.days,
                sharpes={
                    label: None if value is None else value * annualize
                    for label, value in record.sharpes.items()
                },
                chosen=record.chosen,
            )
            for record in grid.history
        ],
        pbo=(
            probability_of_backtest_overfitting(returns, pbo_blocks)
            if len(returns) >= pbo_blocks
            else None
        ),
        cpcv=cpcv_of_selection(returns, grid.labels, settings, periods_per_year),
    )


# The in-sample gate a success criterion names (REQ-830), by name like the
# significance tests: calendar walk-forward, or the CPCV of a parameter grid.
IN_SAMPLE_GATES: dict[str, Callable[[ValidationResult, GridReport | None], bool | None]] = {
    "walk_forward": lambda walk_forward, grid: walk_forward.passed,
    "cpcv": lambda walk_forward, grid: None if grid is None else cpcv_gate(grid.cpcv),
}
GATE_NAMES = {"walk_forward": "walk-forward", "cpcv": "CPCV"}
