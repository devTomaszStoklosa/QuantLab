"""The public-repository data boundary of ADR-0010, enforced on every build.

The repository is public, but the market data behind the research is licensed
for personal use only. `.gitignore` is the first line of defence; these checks
are the second: they read the files git tracks, so a data file, an oversized
blob or a credential that slipped past the ignore rules turns the build red.

Each rule is a small pure function over plain values, tested on its own with
planted offenders, and applied to the real tracked files by one test per rule.
The planted credentials are assembled at run time, so this file's own text
never matches the rule it tests.
"""

import re
import subprocess
from collections.abc import Iterable, Mapping
from pathlib import Path, PurePosixPath

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Where synthetic data files may live (docs/DATA-SOURCES.md). Anything else
# with a data extension is a candidate market-data leak.
ALLOWED_DATA_DIRS = ("data/fixtures/", "presentation/fixtures/")
DATA_EXTENSIONS = frozenset(
    {".parquet", ".csv", ".tsv", ".duckdb", ".db", ".sqlite", ".sqlite3", ".feather", ".xlsx"}
)
MAX_FILE_BYTES = 500_000

# `name = "value"` where the name says credential and the value looks random:
# 20+ token characters containing both a letter and a digit, so identifiers,
# placeholders and prose do not match.
_SECRET_ASSIGNMENT = re.compile(
    r"""(?ix)
    (?:api[_-]?key|token|secret|passw(?:or)?d)\w*["']?\s*[:=]\s*["']?
    (?=[A-Za-z_\-/+=]*\d)(?=[0-9_\-/+=]*[A-Za-z])
    [A-Za-z0-9_\-/+=]{20,}
    """
)
_SECRET_SHAPES = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bghp_[A-Za-z0-9]{30,}"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
)


def data_files_outside_fixtures(paths: Iterable[str]) -> list[str]:
    return [
        path
        for path in paths
        if PurePosixPath(path).suffix.lower() in DATA_EXTENSIONS
        and not path.startswith(ALLOWED_DATA_DIRS)
    ]


def oversized(sizes: Mapping[str, int], limit: int = MAX_FILE_BYTES) -> list[str]:
    return [path for path, size in sizes.items() if size > limit]


def contains_secret(text: str) -> bool:
    return bool(_SECRET_ASSIGNMENT.search(text)) or any(
        shape.search(text) for shape in _SECRET_SHAPES
    )


def _text_or_none(file: Path) -> str | None:
    try:
        return file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None  # binary: covered by the data-extension and size rules


@pytest.fixture(scope="module")
def tracked() -> list[Path]:
    try:
        listing = subprocess.run(
            ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    names = (name for name in listing.decode().split("\0") if name)
    # A file deleted in the working tree but not yet staged is still listed.
    return [ROOT / name for name in names if (ROOT / name).is_file()]


def _relative(files: Iterable[Path]) -> list[str]:
    return [file.relative_to(ROOT).as_posix() for file in files]


def test_data_file_outside_the_fixtures_is_flagged() -> None:
    paths = [
        "data/raw/btc.parquet",
        "notes/prices.CSV",
        "presentation/fixtures/results/demo_momentum/run.parquet",
        "src/quantlab/core/universe.py",
    ]
    assert data_files_outside_fixtures(paths) == ["data/raw/btc.parquet", "notes/prices.CSV"]


def test_oversized_file_is_flagged() -> None:
    sizes = {"a.txt": MAX_FILE_BYTES, "b.bin": MAX_FILE_BYTES + 1}
    assert oversized(sizes) == ["b.bin"]


@pytest.mark.parametrize(
    "text",
    [
        "TIINGO_API_KEY" + ' = "' + "a1b2c3d4" * 4 + '"',
        "token" + ": " + "0123456789abcdef" * 2,
        "-----BEGIN RSA " + "PRIVATE KEY-----",
        "ghp_" + "a1B2c3D4e5F6" * 3,
        "AKIA" + "ABCDEFGHIJKLMNOP",
    ],
)
def test_secret_is_detected(text: str) -> None:
    assert contains_secret(text)


@pytest.mark.parametrize(
    "text",
    [
        'API_KEY_VARIABLE = "TIINGO_API_KEY"',
        "key = os.environ.get('TIINGO_API_KEY')",
        '$env:TIINGO_API_KEY = "..."',
        "the token_column_for_the_universe_file is plain prose",
    ],
)
def test_plain_code_and_prose_are_not_flagged(text: str) -> None:
    assert not contains_secret(text)


def test_no_market_data_files_outside_the_fixtures(tracked: list[Path]) -> None:
    assert data_files_outside_fixtures(_relative(tracked)) == []


def test_no_oversized_files(tracked: list[Path]) -> None:
    sizes = {file.relative_to(ROOT).as_posix(): file.stat().st_size for file in tracked}
    assert oversized(sizes) == []


def test_no_secrets_in_tracked_files(tracked: list[Path]) -> None:
    leaks = [file for file in tracked if (text := _text_or_none(file)) and contains_secret(text)]
    assert _relative(leaks) == []
