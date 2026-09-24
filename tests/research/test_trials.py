import subprocess
from datetime import date
from pathlib import Path

import pytest

from quantlab.research.trials import (
    Trial,
    TrialRegistryError,
    registered_trials,
    trials_on_same_data,
)

_REAL_DEFINITIONS = Path(__file__).parents[2] / "config" / "holdout"
_TEMPLATE = (_REAL_DEFINITIONS / "momentum_v1.yaml").read_text(encoding="utf-8")


def _definition(
    hypothesis: str,
    universe: str = "mvp-crypto",
    training: tuple[str, str] = ("2018-01-01", "2023-12-31"),
) -> str:
    assert "hypothesis: momentum_v1" in _TEMPLATE
    return (
        _TEMPLATE.replace("hypothesis: momentum_v1", f"hypothesis: {hypothesis}")
        .replace("universe: mvp-crypto", f"universe: {universe}")
        .replace("training_start: 2018-01-01", f"training_start: {training[0]}")
        .replace("training_end: 2023-12-31", f"training_end: {training[1]}")
    )


class _Repo:
    """A throwaway git repo whose definitions live in `definitions/`, like config/holdout."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.definitions = root / "definitions"
        self.definitions.mkdir(parents=True)
        self.git("init", "-q")

    def git(self, *args: str) -> None:
        subprocess.run(
            ["git", "-c", "user.name=test", "-c", "user.email=test@example.com", *args],
            cwd=self.root,
            check=True,
            capture_output=True,
        )

    def write(self, name: str, text: str) -> None:
        (self.definitions / name).write_text(text, encoding="utf-8")

    def commit(self, message: str) -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)


def _ids(trials: list[Trial]) -> list[str]:
    return [trial.hypothesis for trial in trials]


def test_every_committed_definition_is_a_trial_oldest_first(tmp_path) -> None:
    repo = _Repo(tmp_path)
    repo.write("first_v1.yaml", _definition("first_v1"))
    repo.commit("first")
    repo.write("second_v1.yaml", _definition("second_v1"))
    repo.commit("second")

    trials = registered_trials(repo.definitions)

    assert _ids(trials) == ["first_v1", "second_v1"]
    assert trials[0].universe == "mvp-crypto"
    assert trials[0].training_start == date(2018, 1, 1)
    assert not any(trial.deleted for trial in trials)


def test_a_deleted_definition_still_counts(tmp_path) -> None:
    repo = _Repo(tmp_path)
    repo.write("failed_v1.yaml", _definition("failed_v1"))
    repo.commit("freeze failed_v1")
    (repo.definitions / "failed_v1.yaml").unlink()
    repo.commit("delete it")

    trials = registered_trials(repo.definitions)

    assert _ids(trials) == ["failed_v1"]
    assert trials[0].deleted


def test_an_uncommitted_draft_is_not_a_trial_and_edits_do_not_count(tmp_path) -> None:
    repo = _Repo(tmp_path)
    repo.write("kept_v1.yaml", _definition("kept_v1"))
    repo.commit("freeze")
    repo.write("draft_v1.yaml", _definition("draft_v1"))
    repo.write("kept_v1.yaml", _definition("kept_v1", universe="other-universe"))

    trials = registered_trials(repo.definitions)

    assert _ids(trials) == ["kept_v1"]
    assert trials[0].universe == "mvp-crypto"


def test_a_renamed_definition_is_one_trial_at_its_latest_version(tmp_path) -> None:
    repo = _Repo(tmp_path)
    repo.write("old_name.yaml", _definition("renamed_v1"))
    repo.commit("freeze")
    (repo.definitions / "old_name.yaml").unlink()
    repo.write("renamed_v1.yaml", _definition("renamed_v1", universe="wider-universe"))
    repo.commit("rename")

    trials = registered_trials(repo.definitions)

    assert _ids(trials) == ["renamed_v1"]
    assert trials[0].universe == "wider-universe"
    assert not trials[0].deleted


def test_files_other_than_definitions_are_ignored(tmp_path) -> None:
    repo = _Repo(tmp_path)
    repo.write("only_v1.yaml", _definition("only_v1"))
    repo.write("only_v1.opened.json", "{}")
    repo.commit("freeze and open")

    assert _ids(registered_trials(repo.definitions)) == ["only_v1"]


def test_a_committed_definition_that_does_not_parse_is_an_error(tmp_path) -> None:
    repo = _Repo(tmp_path)
    repo.write("broken_v1.yaml", "hypothesis: broken_v1\n")
    repo.commit("broken")

    with pytest.raises(TrialRegistryError, match="broken_v1.yaml"):
        registered_trials(repo.definitions)


def test_trials_on_the_same_data_share_the_universe_and_overlap_in_training(tmp_path) -> None:
    repo = _Repo(tmp_path)
    repo.write("target_v1.yaml", _definition("target_v1"))
    repo.write("overlap_v1.yaml", _definition("overlap_v1", training=("2022-06-01", "2023-06-30")))
    repo.write("earlier_v1.yaml", _definition("earlier_v1", training=("2010-01-01", "2017-12-31")))
    repo.write("elsewhere_v1.yaml", _definition("elsewhere_v1", universe="equities"))
    repo.commit("four definitions")

    same = trials_on_same_data("target_v1", registered_trials(repo.definitions))

    assert sorted(_ids(same)) == ["overlap_v1", "target_v1"]
    with pytest.raises(TrialRegistryError, match="no committed definition"):
        trials_on_same_data("missing_v1", registered_trials(repo.definitions))


def test_both_hypotheses_so_far_were_tried_on_the_same_data() -> None:
    trials = registered_trials(_REAL_DEFINITIONS)

    assert _ids(trials_on_same_data("mean_reversion_v1", trials))[:2] == [
        "momentum_v1",
        "mean_reversion_v1",
    ]
