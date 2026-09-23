import hashlib
import json
from datetime import date
from pathlib import Path

CACHE_DIR = Path("data/cache")


def _cache_path(source: str, instrument_id: str, start: date, end: date) -> Path:
    raw = f"{source}:{instrument_id}:{start.isoformat()}:{end.isoformat()}"
    key = hashlib.sha256(raw.encode()).hexdigest()
    return CACHE_DIR / f"{key}.json"


def read_cached_bars(
    source: str, instrument_id: str, start: date, end: date
) -> list[dict] | None:
    path = _cache_path(source, instrument_id, start, end)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_cached_bars(
    source: str, instrument_id: str, start: date, end: date, bars: list[dict]
) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(source, instrument_id, start, end)
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(bars), encoding="utf-8")
    tmp_path.replace(path)
