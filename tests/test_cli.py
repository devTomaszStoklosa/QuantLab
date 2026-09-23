import importlib.metadata

from typer.testing import CliRunner

from quantlab.cli import app

runner = CliRunner()


def test_version_flag_prints_installed_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert importlib.metadata.version("quantlab") in result.stdout
