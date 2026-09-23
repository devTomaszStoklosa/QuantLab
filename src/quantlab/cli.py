import importlib.metadata

import typer

app = typer.Typer()


def _version_callback(show_version: bool) -> None:
    if show_version:
        typer.echo(importlib.metadata.version("quantlab"))
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True
    ),
) -> None:
    pass
