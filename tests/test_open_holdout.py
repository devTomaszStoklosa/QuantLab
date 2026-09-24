from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

from quantlab.cli import _print_holdout, open_frozen_holdout
from quantlab.core.data.provider import PriceBar, WithoutEvents
from quantlab.core.universe import Instrument
from quantlab.research.definition import PairsSpreadParameters
from quantlab.validation.holdout import (
    FrozenHoldout,
    HoldoutAlreadyOpenedError,
    holdout_verdict,
    parse_holdout_config,
    read_holdout_record,
    write_holdout_record,
)

_FROZEN = FrozenHoldout(
    config=parse_holdout_config(
        Path(__file__).parents[1] / "config" / "holdout" / "momentum_v1.yaml"
    ),
    frozen_at_commit="abc123",
)
_OPENED_AT = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)


class _SyntheticProvider(WithoutEvents):
    """DataProvider test double: a seeded random walk per instrument, records requests."""

    def __init__(self) -> None:
        self.requests: list[tuple[str, date, date]] = []

    def fetch(self, instrument: Instrument, start: date, end: date) -> list[PriceBar]:
        self.requests.append((instrument.id, start, end))
        days = (end - start).days + 1
        rng = np.random.default_rng(len(instrument.id))
        closes = 100.0 * np.exp(np.cumsum(rng.normal(0.001, 0.03, days)))
        return [
            PriceBar(
                instrument_id=instrument.id,
                ts=start + timedelta(days=i),
                open=float(close),
                high=float(close),
                low=float(close),
                close=float(close),
                volume=1.0,
                adj_close=None,
                source="test",
            )
            for i, close in enumerate(closes)
        ]


def _open(provider: _SyntheticProvider, record_path: Path):
    return open_frozen_holdout(
        provider=provider,
        frozen=_FROZEN,
        record_path=record_path,
        n_permutations=50,
        seed=0,
        git_sha="def456",
        opened_at=_OPENED_AT,
    )


def test_opening_uses_only_frozen_parameters_and_records_the_result(tmp_path: Path) -> None:
    provider = _SyntheticProvider()
    record_path = tmp_path / "momentum_v1.opened.json"

    record = _open(provider, record_path)

    # Warm-up from 365 days before the holdout start, nothing after its end.
    assert provider.requests == [
        ("btc-usdt", date(2023, 1, 1), date(2025, 12, 31)),
        ("eth-usdt", date(2023, 1, 1), date(2025, 12, 31)),
    ]
    assert record.cost_model_name == "realistic-10bps-k0.05-vol30d"
    assert (record.start, record.end) == (date(2024, 1, 1), date(2025, 12, 31))
    assert record.frozen_at_commit == "abc123"
    assert record.opened_at_commit == "def456"
    assert record.verdict == holdout_verdict(
        _FROZEN.config.success_criterion, record.sharpe, record.p_value
    )
    assert read_holdout_record(record_path) == record


def test_opening_refuses_without_fetching_when_already_opened(tmp_path: Path) -> None:
    record_path = tmp_path / "momentum_v1.opened.json"
    _open(_SyntheticProvider(), record_path)
    provider = _SyntheticProvider()

    with pytest.raises(HoldoutAlreadyOpenedError):
        _open(provider, record_path)

    assert provider.requests == []


def test_record_is_never_overwritten(tmp_path: Path) -> None:
    record_path = tmp_path / "momentum_v1.opened.json"
    record = _open(_SyntheticProvider(), record_path)

    with pytest.raises(FileExistsError):
        write_holdout_record(record_path, record)


def test_a_holdout_without_positions_is_recorded_as_inconclusive(tmp_path: Path, capsys) -> None:
    # A pair whose cointegration filter never lets it trade on unrelated random walks.
    config = _FROZEN.config.model_copy(
        update={
            "hypothesis": "idle_v1",
            "parameters": PairsSpreadParameters(
                strategy="pairs_spread",
                dependent="eth-usdt",
                explanatory="btc-usdt",
                formation_days=365,
                entry_z=2.0,
                exit_z=0.0,
                max_coint_p_value=1e-12,
                universe="mvp-crypto",
                cost_model=_FROZEN.config.parameters.cost_model,
            ),
        }
    )
    record = open_frozen_holdout(
        provider=_SyntheticProvider(),
        frozen=FrozenHoldout(config=config, frozen_at_commit="abc123"),
        record_path=tmp_path / "idle_v1.opened.json",
        n_permutations=50,
        seed=0,
        git_sha="def456",
        opened_at=_OPENED_AT,
    )

    assert (record.sharpe, record.p_value, record.verdict) == (None, None, "inconclusive")
    assert "reason" in record.permutation
    _print_holdout(record)
    shown = capsys.readouterr().out
    assert "Sharpe (net):        n/a" in shown
    assert "Verdict:        INCONCLUSIVE" in shown
