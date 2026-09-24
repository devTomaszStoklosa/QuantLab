import pytest

from quantlab import cli


@pytest.fixture(autouse=True)
def _isolated_results_store(tmp_path_factory, monkeypatch) -> None:
    """No test writes to the real results store, so a local run's results survive pytest."""
    monkeypatch.setattr(cli, "_RESULTS_DIR", tmp_path_factory.mktemp("results"))
