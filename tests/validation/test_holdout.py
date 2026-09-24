import subprocess
from pathlib import Path

import pytest

from quantlab import cli
from quantlab.validation.holdout import (
    HoldoutNotFrozenError,
    SuccessCriterion,
    holdout_passed,
    holdout_verdict,
    load_frozen_holdout,
    parse_holdout_config,
)

_FROZEN_CONFIG = Path(__file__).parents[2] / "config" / "holdout" / "momentum_v1.yaml"
_CRITERION = SuccessCriterion(description="d", min_sharpe=0.0, max_p_value=0.1)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.com", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    return tmp_path


def test_frozen_config_matches_the_training_run_parameters() -> None:
    config = parse_holdout_config(_FROZEN_CONFIG)

    assert config.training_start == cli._TRAINING_START
    assert config.training_end == cli._TRAINING_END
    assert config.parameters.universe == cli._UNIVERSE_NAME
    assert config.parameters.lookback_days == cli._LOOKBACK_DAYS
    assert config.parameters.cost_model.fee_bps == cli._COST_BPS
    assert config.parameters.cost_model.k == cli._SLIPPAGE_K
    assert config.parameters.cost_model.vol_window == cli._VOL_WINDOW_DAYS


def test_missing_file_is_a_blocking_error(repo: Path) -> None:
    with pytest.raises(HoldoutNotFrozenError, match="No frozen holdout"):
        load_frozen_holdout(repo / "momentum_v1.yaml")


def test_uncommitted_file_is_refused(repo: Path) -> None:
    path = repo / "momentum_v1.yaml"
    path.write_text(_FROZEN_CONFIG.read_text(encoding="utf-8"), encoding="utf-8")

    with pytest.raises(HoldoutNotFrozenError, match="uncommitted"):
        load_frozen_holdout(path)


def test_committed_file_loads_with_its_commit_hash(repo: Path) -> None:
    path = repo / "momentum_v1.yaml"
    path.write_text(_FROZEN_CONFIG.read_text(encoding="utf-8"), encoding="utf-8")
    _git(repo, "add", path.name)
    _git(repo, "commit", "-q", "-m", "freeze")

    frozen = load_frozen_holdout(path)

    assert frozen.frozen_at_commit == _git(repo, "rev-parse", "HEAD")
    assert frozen.config.hypothesis == "momentum_v1"


def test_edit_after_commit_is_refused(repo: Path) -> None:
    path = repo / "momentum_v1.yaml"
    path.write_text(_FROZEN_CONFIG.read_text(encoding="utf-8"), encoding="utf-8")
    _git(repo, "add", path.name)
    _git(repo, "commit", "-q", "-m", "freeze")
    path.write_text(
        path.read_text(encoding="utf-8").replace("min_sharpe: 0.0", "min_sharpe: -1.0"),
        encoding="utf-8",
    )

    with pytest.raises(HoldoutNotFrozenError, match="uncommitted"):
        load_frozen_holdout(path)


def test_holdout_overlapping_training_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "overlap.yaml"
    path.write_text(
        _FROZEN_CONFIG.read_text(encoding="utf-8").replace(
            "start: 2024-01-01", "start: 2023-06-01"
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="overlaps training"):
        parse_holdout_config(path)


@pytest.mark.parametrize(
    ("sharpe", "p_value", "expected"),
    [
        (-0.2, 0.01, "rejected"),
        (0.0, 0.01, "rejected"),
        (0.5, 0.30, "inconclusive"),
        (0.5, 0.10, "inconclusive"),
        (1.2, 0.05, "passed"),
    ],
)
def test_holdout_verdict_follows_the_frozen_criterion(
    sharpe: float, p_value: float, expected: str
) -> None:
    assert holdout_verdict(_CRITERION, sharpe, p_value) == expected


def test_holdout_passed_uses_validation_result_terms() -> None:
    assert holdout_passed("passed") is True
    assert holdout_passed("rejected") is False
    assert holdout_passed("inconclusive") is None
