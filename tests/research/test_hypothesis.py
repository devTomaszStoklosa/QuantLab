import pytest

from quantlab.research.hypothesis import (
    DuplicateHypothesisError,
    HypothesisNotFoundError,
    HypothesisNotValidatedError,
    InvalidStatusTransitionError,
    get,
    register,
    update_status,
)


def test_register_creates_hypothesis_with_proposed_status(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    hypothesis = register("momentum-v1", "Time-series momentum", "Momentum works on crypto pairs")

    assert hypothesis.status == "proposed"
    assert get("momentum-v1") == hypothesis


def test_register_duplicate_id_raises(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    register("momentum-v1", "Title", "Statement")

    with pytest.raises(DuplicateHypothesisError):
        register("momentum-v1", "Title", "Statement")


def test_get_unknown_id_raises(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    with pytest.raises(HypothesisNotFoundError):
        get("does-not-exist")


def test_valid_transition_chain_to_confirmed(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    register("momentum-v1", "Title", "Statement")

    update_status("momentum-v1", "testing")
    confirmed = update_status(
        "momentum-v1", "confirmed", walk_forward_passed=True, holdout_passed=True
    )

    assert confirmed.status == "confirmed"


@pytest.mark.parametrize("target", ["rejected", "inconclusive"])
def test_testing_can_end_without_confirmation(target, tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    register("momentum-v1", "Title", "Statement")
    update_status("momentum-v1", "testing")

    result = update_status("momentum-v1", target)

    assert result.status == target


def test_confirmed_requires_both_walk_forward_and_holdout(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    register("momentum-v1", "Title", "Statement")
    update_status("momentum-v1", "testing")

    with pytest.raises(HypothesisNotValidatedError):
        update_status("momentum-v1", "confirmed", walk_forward_passed=True, holdout_passed=False)


def test_skipping_testing_to_reach_confirmed_is_rejected(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    register("momentum-v1", "Title", "Statement")

    with pytest.raises(InvalidStatusTransitionError):
        update_status("momentum-v1", "confirmed", walk_forward_passed=True, holdout_passed=True)


def test_terminal_status_cannot_transition_further(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    register("momentum-v1", "Title", "Statement")
    update_status("momentum-v1", "testing")
    update_status("momentum-v1", "rejected")

    with pytest.raises(InvalidStatusTransitionError):
        update_status("momentum-v1", "testing")
