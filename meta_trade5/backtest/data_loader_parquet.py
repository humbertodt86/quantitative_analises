"""Data loading from partitioned Parquet - high performance tick loading with predicate pushdown.

This module provides functions to load tick data from the partitioned parquet file,
exploiting partition pruning for efficient date range queries.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import polars as pl
import pandas as pd


PARQUET_PATH = Path(__file__).parent.parent / "data" / "raw" / "ticks" / "WIN_merged_all_partitioned"


@dataclass
class BidAskCoverage:
    period: str
    total_ticks: int
    real_bidask_ticks: int
    simulated_bidask_ticks: int
    real_pct: float
    avg_spread: float


def load_parquet_metadata() -> dict:
    """Load parquet metadata without scanning all data."""
    import pyarrow.parquet as pq

    p = PARQUET_PATH
    if not p.exists():
        raise FileNotFoundError(f"Partitioned parquet not found at {p}")

    pf = pq.ParquetDataset(str(p))
    schema = pf.schema_arrow
    metadata = pf.metadata

    return {
        "schema": schema,
        "metadata": metadata,
        "num_row_groups": metadata.num_row_groups if hasattr(metadata, "num_row_groups") else None,
    }


def analyze_bidask_coverage(
    parquet_path: str | Path = PARQUET_PATH,
    hour_min: int = 9,
    hour_max: int = 22,
) -> list[BidAskCoverage]:
    """Analyze bid/ask availability per month.

    Returns list of BidAskCoverage with stats per month.
    """
    p = Path(parquet_path)
    if not p.exists():
        raise FileNotFoundError(f"Parquet not found at {p}")

    df = pl.scan_parquet(str(p) + "/**/*.parquet")

    df_filtered = df.with_columns([
        pl.from_epoch(pl.col("time_msc"), time_unit="ms").alias("dt_ts")
    ]).filter(
        (pl.col("dt_ts").dt.hour() >= hour_min) & (pl.col("dt_ts").dt.hour() <= hour_max)
    )

    df_collected = df_filtered.collect()

    df_collected = df_collected.with_columns([
        pl.col("dt_ts").dt.year().alias("year"),
        pl.col("dt_ts").dt.month().alias("month"),
    ])

    df_collected = df_collected.with_columns([
        (pl.col("ask") - pl.col("bid")).alias("spread"),
        (pl.col("bid") != pl.col("ask")).alias("is_real_bidask"),
    ])

    monthly = df_collected.group_by(["year", "month"]).agg([
        pl.len().alias("total_ticks"),
        pl.col("is_real_bidask").sum().alias("real_bidask_ticks"),
        (pl.col("spread") > 0).sum().alias("positive_spread_ticks"),
        pl.col("spread").mean().alias("avg_spread"),
    ])

    monthly = monthly.with_columns([
        (pl.col("total_ticks") - pl.col("real_bidask_ticks")).alias("simulated_bidask_ticks"),
        (pl.col("real_bidask_ticks") / pl.col("total_ticks") * 100).alias("real_pct"),
    ])

    results = []
    for row in monthly.sort(["year", "month"]).iter_rows():
        results.append(BidAskCoverage(
            period=f"{row[0]}-{row[1]:02d}",
            total_ticks=row[2],
            real_bidask_ticks=row[3],
            simulated_bidask_ticks=row[5],
            real_pct=row[6],
            avg_spread=row[4] if row[4] is not None else 0.0,
        ))

    return results


def load_ticks_parquet(
    date_from: str,
    date_to: str,
    parquet_path: str | Path = PARQUET_PATH,
    hour_min: int = 9,
    hour_max: int = 22,
    include_bidask_flag: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load ticks from partitioned parquet with predicate pushdown.

    Args:
        date_from: Start date (YYYY-MM-DD)
        date_to: End date (YYYY-MM-DD)
        parquet_path: Path to partitioned parquet directory
        hour_min: Minimum hour to include (default 9)
        hour_max: Maximum hour to include (default 22)
        include_bidask_flag: If True, add 'has_real_bidask' column

    Returns:
        Tuple of (ticks_raw, ticks_last):
            ticks_raw: DataFrame with bid, ask, last, volume, dt
            ticks_last: DataFrame with price, volume, dt (last prices only)
    """
    p = Path(parquet_path)
    if not p.exists():
        raise FileNotFoundError(f"Partitioned parquet not found at {p}")

    t0 = int(datetime.strptime(date_from, "%Y-%m-%d").replace(
        hour=0, minute=0, second=0, microsecond=0
    ).timestamp() * 1000)
    t1 = int(datetime.strptime(date_to, "%Y-%m-%d").replace(
        hour=23, minute=59, second=59, microsecond=999999
    ).timestamp() * 1000)

    df = pl.scan_parquet(str(p) + "/**/*.parquet")

    df_filtered = df.filter(
        (pl.col("time_msc") >= t0) &
        (pl.col("time_msc") <= t1)
    )

    df_collected = df_filtered.collect()

    if len(df_collected) == 0:
        raise RuntimeError(f"No ticks found in {date_from}..{date_to}")

    result = df_collected.to_pandas()
    result["dt"] = pd.to_datetime(result["time_msc"], unit="ms")

    result = result[(result["dt"].dt.hour >= hour_min) & (result["dt"].dt.hour <= hour_max)]

    if len(result) == 0:
        raise RuntimeError(f"No ticks found in {date_from}..{date_to} within hours {hour_min}-{hour_max}")

    bid = result["bid"].values.astype(float)
    ask = result["ask"].values.astype(float)
    last = result["last"].values.astype(float)
    time_msc = result["time_msc"].values
    volume = result["volume_real"].values if "volume_real" in result.columns else None

    bid_ok = bid > 0
    ask_ok = ask > 0
    spread_ok = (ask - bid) <= 500

    valid_raw = bid_ok & ask_ok & spread_ok

    bid_valid = bid.copy()
    ask_valid = ask.copy()
    bid_valid[~bid_ok] = last[~bid_ok]
    ask_valid[~ask_ok] = last[~ask_ok]

    last_valid = last.copy()
    last_valid[last <= 0] = (bid_valid[last <= 0] + ask_valid[last <= 0]) / 2

    real_bidask_mask = valid_raw & (bid != ask)

    ticks_raw_dict = {
        "time_msc": time_msc[valid_raw],
        "bid": bid_valid[valid_raw],
        "ask": ask_valid[valid_raw],
        "last": last_valid[valid_raw],
        "volume": volume[valid_raw] if volume is not None else 1.0,
        "dt": pd.to_datetime(time_msc[valid_raw], unit="ms"),
    }
    if include_bidask_flag:
        ticks_raw_dict["has_real_bidask"] = real_bidask_mask[valid_raw]

    ticks_raw = pd.DataFrame(ticks_raw_dict)

    last_only_mask = last > 0
    ticks_last = pd.DataFrame({
        "time_msc": time_msc[last_only_mask],
        "price": last_valid[last_only_mask],
        "volume": volume[last_only_mask] if volume is not None else 1.0,
        "dt": pd.to_datetime(time_msc[last_only_mask], unit="ms"),
    })

    ticks_raw = ticks_raw.sort_values("dt").reset_index(drop=True)
    ticks_last = ticks_last.sort_values("dt").reset_index(drop=True)

    return ticks_raw, ticks_last


def load_ticks_parquet_fast(
    date_from: str,
    date_to: str,
    parquet_path: str | Path = PARQUET_PATH,
) -> pd.DataFrame:
    """Fast tick loading returning only essential columns as DataFrame.

    Optimized for cases where we only need bid/ask arrays for engine.
    """
    p = Path(parquet_path)
    if not p.exists():
        raise FileNotFoundError(f"Partitioned parquet not found at {p}")

    t0 = int(datetime.strptime(date_from, "%Y-%m-%d").replace(
        hour=0, minute=0, second=0, microsecond=0
    ).timestamp() * 1000)
    t1 = int(datetime.strptime(date_to, "%Y-%m-%d").replace(
        hour=23, minute=59, second=59, microsecond=999999
    ).timestamp() * 1000)

    df = pl.scan_parquet(str(p) + "/**/*.parquet")

    df_filtered = df.filter(
        (pl.col("time_msc") >= t0) &
        (pl.col("time_msc") <= t1)
    ).select([
        "time_msc", "bid", "ask", "last",
        "volume_real" if "volume_real" in df_filtered.columns else "last"
    ])

    df_collected = df_filtered.collect()

    result = df_collected.to_pandas()
    result["dt"] = pd.to_datetime(result["time_msc"], unit="ms")

    result = result.sort_values("dt").reset_index(drop=True)

    bid = result["bid"].values
    ask = result["ask"].values
    last = result["last"].values

    bid_ok = bid > 0
    ask_ok = ask > 0

    result.loc[~bid_ok, "bid"] = result.loc[~bid_ok, "last"]
    result.loc[~ask_ok, "ask"] = result.loc[~ask_ok, "last"]

    last_zero = last <= 0
    result.loc[last_zero, "last"] = (result.loc[last_zero, "bid"] + result.loc[last_zero, "ask"]) / 2

    if "volume_real" in result.columns:
        result["volume"] = result["volume_real"].fillna(1.0).replace(0, 1.0)
    else:
        result["volume"] = 1.0

    return result[["time_msc", "bid", "ask", "last", "volume", "dt"]]


def get_time_range(parquet_path: str | Path = PARQUET_PATH) -> tuple[datetime, datetime]:
    """Get the full time range of the parquet data."""
    p = Path(parquet_path)
    if not p.exists():
        raise FileNotFoundError(f"Parquet not found at {p}")

    df = pl.scan_parquet(str(p) + "/**/*.parquet").select(["time_msc"])
    df_collected = df.collect()

    t_min = df_collected["time_msc"].min()
    t_max = df_collected["time_msc"].max()

    return (
        datetime.fromtimestamp(t_min / 1000),
        datetime.fromtimestamp(t_max / 1000),
    )


if __name__ == "__main__":
    print("=== Parquet Tick Data Analysis ===\n")

    t0, t1 = get_time_range()
    print(f"Time range: {t0} to {t1}")

    print("\n=== Bid/Ask Coverage by Month ===")
    coverage = analyze_bidask_coverage()
    for c in coverage:
        status = "REAL" if c.real_pct > 1 else "SIM"
        print(f"  {c.period}: {c.total_ticks:>12,} ticks | {status} bid/ask: {c.real_bidask_ticks:>10,} ({c.real_pct:.1f}%) | spread: {c.avg_spread:.2f}")
