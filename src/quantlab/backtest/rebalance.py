"""When an engine trades back to the target weights (q5, REQ-530)."""

from typing import Protocol


class RebalancePolicy(Protocol):
    """Asked once per decision: keep the drifted positions instead of trading to `targets`?

    Both engines ask the same object, so they keep parity under any policy (REQ-531).
    """

    def holds(
        self, previous_targets: dict[str, float] | None, targets: dict[str, float]
    ) -> bool: ...


class Daily:
    """Back to the target weights every period: today's rule and the default (REQ-532)."""

    def holds(self, previous_targets: dict[str, float] | None, targets: dict[str, float]) -> bool:
        return False


class OnSignalChange:
    """Trade only when the targets change; otherwise let the positions drift with prices.

    For strategies whose signals change at formation dates only, such as monthly
    cross-sectional momentum: an equal-weight portfolio would otherwise be traded
    back to equal weights every day, paying costs for drift nobody decided.
    """

    def holds(self, previous_targets: dict[str, float] | None, targets: dict[str, float]) -> bool:
        return previous_targets is not None and targets == previous_targets
