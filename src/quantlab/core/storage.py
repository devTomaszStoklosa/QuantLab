from datetime import date
from pathlib import Path

import duckdb
import pandas as pd

from quantlab.core.data.provider import PriceBar

DATA_DIR = Path("data/prices")


def _parquet_path(instrument_id: str) -> Path:
    return DATA_DIR / f"{instrument_id}.parquet"


def write_price_bars(bars: list[PriceBar]) -> None:
    if not bars:
        return
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    by_instrument: dict[str, list[PriceBar]] = {}
    for bar in bars:
        by_instrument.setdefault(bar.instrument_id, []).append(bar)

    for instrument_id, new_bars in by_instrument.items():
        path = _parquet_path(instrument_id)
        new_df = pd.DataFrame([bar.model_dump(mode="json") for bar in new_bars])

        con = duckdb.connect()
        try:
            if path.exists():
                existing_df = con.execute("SELECT * FROM read_parquet(?)", [str(path)]).df()
                combined = pd.concat([existing_df, new_df], ignore_index=True)
            else:
                combined = new_df

            combined["ts"] = pd.to_datetime(combined["ts"]).dt.date
            combined = combined.drop_duplicates(subset="ts", keep="last").sort_values("ts")

            con.register("combined_view", combined)
            con.execute(f"COPY combined_view TO '{path.as_posix()}' (FORMAT PARQUET)")
        finally:
            con.close()


def read_price_bars(instrument_id: str, start: date, end: date) -> list[PriceBar]:
    path = _parquet_path(instrument_id)
    if not path.exists():
        return []

    con = duckdb.connect()
    try:
        rows = con.execute(
            f"SELECT * FROM read_parquet('{path.as_posix()}') "
            "WHERE ts BETWEEN ? AND ? ORDER BY ts",
            [start, end],
        ).df()
    finally:
        con.close()

    return [PriceBar(**row) for row in rows.to_dict(orient="records")]
