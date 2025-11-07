# ciq/lib/contract.py
"""
Data Contract Validation Library

Purpose: Load and validate data against YAML contracts using pandera
Features:
- Type coercion
- NOT NULL validation
- Range checks
- Category validation
- Leakage detection (forbidden column patterns)
"""

from __future__ import annotations

import re
import yaml
from pathlib import Path
from typing import Any, Dict

import pandas as pd
import pandera as pa
from pandera import Check, Column, DataFrameSchema


def load_contract(path: str | Path) -> Dict[str, Any]:
    """Load data contract from YAML file"""
    return yaml.safe_load(Path(path).read_text())


def build_schema(contract: Dict[str, Any]) -> DataFrameSchema:
    """
    Build pandera DataFrameSchema from contract

    Returns:
        DataFrameSchema with type coercion, nullable constraints, and checks
    """
    dtype_map = {
        "int8": "Int8",
        "int16": "Int16",
        "int32": "Int32",
        "int64": "Int64",
        "float32": "Float32",
        "float64": "Float64",
        "datetime": "datetime64[ns]",
        "category": "category",
        "bool": "bool",
    }

    columns = {}
    types = contract["types"]
    not_null = set(contract.get("constraints", {}).get("not_null", []))
    ranges = contract.get("constraints", {}).get("ranges", {})
    cats = contract.get("constraints", {}).get("categories", {})

    for col, typ in types.items():
        checks = []

        # Range checks
        if col in ranges:
            lo, hi = ranges[col]
            if lo is not None:
                checks.append(Check.ge(lo))
            if hi is not None:
                checks.append(Check.le(hi))

        # Category checks
        if col in cats:
            checks.append(Check.isin(cats[col]))

        columns[col] = Column(
            dtype_map.get(typ, "object"),
            nullable=(col not in not_null),
            checks=checks,
        )

    return DataFrameSchema(columns, coerce=True)


def forbid_leakage(df: pd.DataFrame, patterns: list[str]) -> None:
    """
    Check for leakage columns based on forbidden patterns

    Args:
        df: DataFrame to check
        patterns: List of patterns (e.g., "future_*", "*_post")

    Raises:
        ValueError: If any leakage columns detected
    """
    for pat in patterns:
        # Convert glob pattern to regex
        rx = re.compile(pat.replace("*", ".*"))
        bad = [c for c in df.columns if rx.fullmatch(c)]
        if bad:
            raise ValueError(f"Leakage columns detected: {bad}")


def validate_dataframe(df: pd.DataFrame, contract_path: str | Path) -> pd.DataFrame:
    """
    Validate DataFrame against contract

    Args:
        df: DataFrame to validate
        contract_path: Path to contract YAML

    Returns:
        Validated and coerced DataFrame

    Raises:
        pandera.errors.SchemaError: If validation fails
        ValueError: If leakage columns detected
    """
    contract = load_contract(contract_path)
    schema = build_schema(contract)

    # Validate with pandera (coerces types)
    df_validated = schema.validate(df, lazy=True)

    # Check for leakage
    leakage_patterns = contract.get("constraints", {}).get("leakage_forbidden_cols", [])
    forbid_leakage(df_validated, leakage_patterns)

    return df_validated
