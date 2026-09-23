from datetime import date, timedelta

import numpy as np
import pytest

from quantlab.core.data.provider import PriceBar
from quantlab.risk.regime import (
    HIGH,
    LOW,
    MEDIUM,
    UNDEFINED,
    VolatilityTercileClassifier,
    label_periods,
)

_FIRST_DAY = date(2020, 1, 1)


def _bars(daily_returns: list[float]) -> list[PriceBar]:
    closes = [100.0]
    for daily_return in daily_returns:
        closes.append(closes[-1] * (1.0 + daily_return))
    return [
        PriceBar(
            instrument_id="a",
            ts=_FIRST_DAY + timedelta(days=i),
            open=close,
            high=close,
            low=close,
            close=close,
            volume=1.0,
            adj_close=None,
            source="test",
        )
        for i, close in enumerate(closes)
    ]


def _last_day(bars: list[PriceBar]) -> date:
    return bars[-1].ts


@pytest.mark.parametrize(
    ("daily_returns", "expected"),
    [
        # vol_window=2 gives volatilities 0.0071, 0.0212 and the current one; the
        # current one ranks lowest, in the middle or highest of the three.
        ([0.0, 0.01, 0.04, 0.041], LOW),
        ([0.0, 0.01, 0.04, 0.02], MEDIUM),
        ([0.0, 0.01, 0.04, -0.04], HIGH),
    ],
)
def test_current_volatility_is_ranked_against_its_trailing_history(
    daily_returns: list[float], expected: str
) -> None:
    bars = _bars(daily_returns)

    label = VolatilityTercileClassifier(vol_window=2, history_days=3).label(bars, _last_day(bars))

    assert label == expected


def test_volatility_spike_after_calm_is_high_and_calm_after_turbulence_is_low() -> None:
    classifier = VolatilityTercileClassifier(vol_window=5, history_days=20)
    spike = _bars([0.001, -0.001] * 20 + [0.05, -0.05] * 5)
    calm = _bars([0.05, -0.05] * 20 + [0.001, -0.001] * 5)

    assert classifier.label(spike, _last_day(spike)) == HIGH
    assert classifier.label(calm, _last_day(calm)) == LOW


def test_label_ignores_everything_after_as_of() -> None:
    rng = np.random.default_rng(0)
    returns = rng.normal(0.0, 0.03, 200).tolist()
    classifier = VolatilityTercileClassifier(vol_window=10, history_days=30)
    as_of = _FIRST_DAY + timedelta(days=100)
    wild_future = returns[:100] + [0.5, -0.5] * 50

    labels = {
        classifier.label(_bars(returns[:100]), as_of),
        classifier.label(_bars(returns), as_of),
        classifier.label(_bars(wild_future), as_of),
    }

    assert len(labels) == 1


def test_flat_market_is_undefined_not_a_forced_tercile() -> None:
    bars = _bars([0.0] * 30)

    label = VolatilityTercileClassifier(vol_window=5, history_days=10).label(bars, _last_day(bars))

    assert label == UNDEFINED


def test_too_little_history_is_undefined() -> None:
    classifier = VolatilityTercileClassifier(vol_window=2, history_days=3)
    # history_days + vol_window closes are needed: 5 bars, i.e. 4 daily returns.
    enough = _bars([0.0, 0.01, 0.04, 0.02])
    too_few = _bars([0.0, 0.01, 0.04])

    assert classifier.label(enough, _last_day(enough)) != UNDEFINED
    assert classifier.label(too_few, _last_day(too_few)) == UNDEFINED


def test_label_periods_labels_each_date() -> None:
    bars = _bars([0.0, 0.01, 0.04, 0.02])
    classifier = VolatilityTercileClassifier(vol_window=2, history_days=3)
    dates = [bar.ts for bar in bars]

    labels = label_periods(classifier, bars, dates)

    assert labels == {as_of: classifier.label(bars, as_of) for as_of in dates}
    assert labels[dates[0]] == UNDEFINED
    assert labels[dates[-1]] == MEDIUM
