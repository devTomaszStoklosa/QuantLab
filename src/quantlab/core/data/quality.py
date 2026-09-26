"""Checks of the bars a run is about to use (q14): read-only, before any backtest.

Each check is a `DataCheck` with a name and a level. Errors (duplicate dates,
non-positive prices) make every statistic computed on the data meaningless, so a
run stops on them; warnings (inconsistent OHLC, missing sessions, stale closes,
extreme moves) are real market events often enough that the run reports them
with their dates and goes on. No check changes, drops or adds a bar (REQ-1404).
The thresholds are the lab's methodology, the same for every hypothesis.
"""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal, Protocol

import numpy as np

from quantlab.core.data.provider import PriceBar
from quantlab.core.universe import Universe

Level = Literal["error", "warning"]

_OHLC_TOLERANCE = 1e-9  # relative: rounding in adjusted prices is not a defect
_STALE_RUN = 5  # consecutive bars with the same close
_EXTREME_DEVIATIONS = 10.0  # robust standard deviations from the median return
_MIN_RETURNS = 20  # fewer and there is no stable scale to measure against
_MAD_TO_STD = 1.4826  # a normal distribution's standard deviation per MAD


@dataclass(frozen=True)
class Finding:
    check: str
    level: Level
    instrument_id: str
    day: date | None
    detail: str


class DataCheck(Protocol):
    name: str
    level: Level

    def findings(
        self, instrument_id: str, bars: list[PriceBar], sessions: list[date]
    ) -> list[Finding]: ...


@dataclass(frozen=True)
class DuplicateDates:
    name: str = "duplicate dates"
    level: Level = "error"

    def findings(
        self, instrument_id: str, bars: list[PriceBar], sessions: list[date]
    ) -> list[Finding]:
        counts = Counter(bar.ts for bar in bars)
        return [
            Finding(self.name, self.level, instrument_id, day, f"{count} bars on {day}")
            for day, count in sorted(counts.items())
            if count > 1
        ]


@dataclass(frozen=True)
class NonPositivePrices:
    name: str = "non-positive prices"
    level: Level = "error"

    def findings(
        self, instrument_id: str, bars: list[PriceBar], sessions: list[date]
    ) -> list[Finding]:
        # A delisting bar is the value holders received, which may be nothing (q5).
        return [
            Finding(
                self.name,
                self.level,
                instrument_id,
                bar.ts,
                f"open {bar.open}, high {bar.high}, low {bar.low}, close {bar.close}",
            )
            for bar in bars
            if not bar.delisting and min(bar.open, bar.high, bar.low, bar.close) <= 0
        ]


@dataclass(frozen=True)
class InconsistentOhlc:
    name: str = "inconsistent OHLC"
    level: Level = "warning"

    def findings(
        self, instrument_id: str, bars: list[PriceBar], sessions: list[date]
    ) -> list[Finding]:
        found = []
        for bar in bars:
            if bar.delisting:
                continue
            slack = _OHLC_TOLERANCE * max(abs(bar.high), abs(bar.low))
            if bar.high + slack < max(bar.open, bar.close, bar.low) or (
                bar.low - slack > min(bar.open, bar.close, bar.high)
            ):
                found.append(
                    Finding(
                        self.name,
                        self.level,
                        instrument_id,
                        bar.ts,
                        f"open {bar.open:.6g}, high {bar.high:.6g}, low {bar.low:.6g}, "
                        f"close {bar.close:.6g}",
                    )
                )
        return found


@dataclass(frozen=True)
class MissingSessions:
    name: str = "missing sessions"
    level: Level = "warning"

    def findings(
        self, instrument_id: str, bars: list[PriceBar], sessions: list[date]
    ) -> list[Finding]:
        if not bars:
            return []
        first, last = bars[0].ts, bars[-1].ts
        present = {bar.ts for bar in bars}
        return [
            Finding(self.name, self.level, instrument_id, day, "no bar on a session of the market")
            for day in sessions
            if first < day < last and day not in present
        ]


@dataclass(frozen=True)
class StaleCloses:
    name: str = "stale closes"
    level: Level = "warning"

    def findings(
        self, instrument_id: str, bars: list[PriceBar], sessions: list[date]
    ) -> list[Finding]:
        found, start = [], 0
        for i in range(1, len(bars) + 1):
            if i < len(bars) and bars[i].close == bars[start].close:
                continue
            if i - start >= _STALE_RUN:
                found.append(
                    Finding(
                        self.name,
                        self.level,
                        instrument_id,
                        bars[start].ts,
                        f"close {bars[start].close:.6g} on {i - start} bars to {bars[i - 1].ts}",
                    )
                )
            start = i
        return found


@dataclass(frozen=True)
class ExtremeMoves:
    name: str = "extreme moves"
    level: Level = "warning"

    def findings(
        self, instrument_id: str, bars: list[PriceBar], sessions: list[date]
    ) -> list[Finding]:
        closes = np.array([bar.close for bar in bars], dtype=np.float64)
        if len(closes) <= _MIN_RETURNS or np.any(closes <= 0):
            return []
        returns = closes[1:] / closes[:-1] - 1.0
        median = np.median(returns)
        scale = _MAD_TO_STD * np.median(np.abs(returns - median))
        if scale == 0:
            return []
        deviations = (returns - median) / scale
        return [
            Finding(
                self.name,
                self.level,
                instrument_id,
                bars[i + 1].ts,
                f"return {returns[i]:+.2%} from {bars[i].ts}, {abs(deviations[i]):.1f} robust "
                "standard deviations from the median",
            )
            for i in np.flatnonzero(np.abs(deviations) > _EXTREME_DEVIATIONS)
        ]


# The lab's checks, in report order: errors first.
CHECKS: tuple[DataCheck, ...] = (
    DuplicateDates(),
    NonPositivePrices(),
    InconsistentOhlc(),
    MissingSessions(),
    StaleCloses(),
    ExtremeMoves(),
)


@dataclass(frozen=True)
class QualityReport:
    instruments: int
    bars: int
    findings: list[Finding]
    checks: tuple[str, ...]

    @property
    def errors(self) -> list[Finding]:
        return [finding for finding in self.findings if finding.level == "error"]

    @property
    def warnings(self) -> list[Finding]:
        return [finding for finding in self.findings if finding.level == "warning"]

    def summary(self) -> dict[str, float | None]:
        """The counts a run stores as its "Data quality" diagnostic (REQ-1412)."""
        counts = Counter(finding.check for finding in self.findings)
        return {
            "instruments checked": float(self.instruments),
            "bars checked": float(self.bars),
            **{check: float(counts[check]) for check in self.checks},
        }


def reference_sessions(universe: Universe, bars: dict[str, list[PriceBar]]) -> list[date]:
    """The market's sessions over the bars' range (REQ-1402): every calendar day where
    the market trades every day, else every date any fetched instrument has a bar on,
    so exchange holidays are not missing sessions."""
    dates = {bar.ts for series in bars.values() for bar in series}
    if not dates:
        return []
    if universe.trades_every_day:
        first, last = min(dates), max(dates)
        return [first + timedelta(days=i) for i in range((last - first).days + 1)]
    return sorted(dates)


def quality_report(
    bars: dict[str, list[PriceBar]],
    sessions: list[date],
    checks: Sequence[DataCheck] = CHECKS,
) -> QualityReport:
    """Every check on every instrument's bars (REQ-1401, REQ-1403); reads only."""
    findings = [
        finding
        for check in checks
        for instrument_id in sorted(bars)
        for finding in check.findings(instrument_id, bars[instrument_id], sessions)
    ]
    return QualityReport(
        instruments=len(bars),
        bars=sum(len(series) for series in bars.values()),
        findings=findings,
        checks=tuple(check.name for check in checks),
    )
