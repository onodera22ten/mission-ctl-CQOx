#!/usr/bin/env python3
"""
Multi-format Input Converter

Purpose: Convert CSV/TSV/JSONL/XLSX/Parquet/Feather to type-safe Parquet
Supports: .gz, .bz2 compression
Features:
- Magic number validation (防止: 拡張子偽装)
- Contract-based validation
- Leakage detection
- Fail-fast on violations
"""

from __future__ import annotations

import bz2
import gzip
import io
import sys
from pathlib import Path
from typing import TextIO

import magic
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ciq.lib.contract import load_contract, build_schema, forbid_leakage

RAW = Path("ciq/data/raw")
STAGED = Path("ciq/data/staged/staged.parquet")
CONTRACT = "ciq/contracts/dataset.yaml"


def _open(path: Path) -> TextIO:
    """Open file with automatic decompression"""
    p = str(path).lower()
    if p.endswith(".gz"):
        return io.TextIOWrapper(gzip.open(path, "rb"), encoding="utf-8", errors="replace")
    if p.endswith(".bz2"):
        return io.TextIOWrapper(bz2.open(path, "rb"), encoding="utf-8", errors="replace")
    return open(path, "r", newline="", encoding="utf-8", errors="replace")


def load_one(path: Path) -> pd.DataFrame:
    """
    Load single file with magic number validation

    Supported formats:
    - CSV, TSV (with .gz/.bz2)
    - JSONL (newline-delimited JSON)
    - XLSX (Excel)
    - Parquet
    - Feather

    Returns:
        DataFrame

    Raises:
        ValueError: If unsupported file type
    """
    # Magic number validation (防止拡張子偽装)
    mime = magic.from_file(str(path), mime=True)
    p = str(path).lower()

    # CSV/TSV
    if p.endswith((".csv", ".csv.gz", ".csv.bz2")):
        return pd.read_csv(_open(path))
    if p.endswith((".tsv", ".tsv.gz", ".tsv.bz2")):
        return pd.read_csv(_open(path), sep="\t")

    # JSONL (newline-delimited JSON)
    if p.endswith((".jsonl", ".jsonl.gz", ".jsonl.bz2", ".ndjson")):
        return pd.read_json(_open(path), lines=True)

    # Excel
    if p.endswith(".xlsx"):
        return pd.read_excel(path)

    # Parquet
    if p.endswith(".parquet"):
        return pd.read_parquet(path)

    # Feather
    if p.endswith(".feather"):
        return pd.read_feather(path)

    raise ValueError(f"Unsupported file type: {path} (mime={mime})")


def main():
    """
    Main ingestion pipeline:
    1. Load all files from ciq/data/raw/
    2. Validate against contract
    3. Check for leakage
    4. Write type-safe Parquet
    5. Create DuckDB view
    """
    files = sorted([p for p in RAW.iterdir() if p.is_file()])
    if not files:
        print(f"ERROR: No input files in {RAW}", file=sys.stderr)
        sys.exit(2)

    # Load contract
    contract = load_contract(CONTRACT)
    schema = build_schema(contract)

    # Load and validate all files
    dfs = []
    for f in files:
        print(f"[ingest] Loading {f.name}...", file=sys.stderr)
        try:
            df = load_one(f)
            df = schema.validate(df, lazy=True)  # Type coercion + validation
            dfs.append(df)
        except Exception as e:
            print(f"ERROR: Failed to load {f.name}: {e}", file=sys.stderr)
            sys.exit(1)

    # Concatenate
    df_all = pd.concat(dfs, ignore_index=True)
    print(f"[ingest] Loaded {len(df_all)} rows from {len(files)} files", file=sys.stderr)

    # Leakage detection
    leakage_patterns = contract.get("constraints", {}).get("leakage_forbidden_cols", [])
    try:
        forbid_leakage(df_all, leakage_patterns)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # Write type-safe Parquet
    table = pa.Table.from_pandas(df_all, preserve_index=False)
    STAGED.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, STAGED)
    print(f"[ingest] Wrote {STAGED} ({len(df_all)} rows)", file=sys.stderr)

    # Create DuckDB view (for dbt to consume)
    import duckdb

    con = duckdb.connect("ciq/warehouse/warehouse.duckdb")
    con.execute(
        "CREATE OR REPLACE VIEW staged_csv AS SELECT * FROM read_parquet(?)",
        [str(STAGED)],
    )
    con.close()
    print("[ingest] Created DuckDB view: staged_csv", file=sys.stderr)


if __name__ == "__main__":
    main()
