# ciq/tests/test_contract.py
"""
Contract validation tests

Purpose: Verify contract loading, schema building, and validation
"""

import pandas as pd
import pytest

from ciq.lib.contract import build_schema, forbid_leakage, load_contract


def test_load_contract():
    """Test contract loading"""
    contract = load_contract("ciq/contracts/dataset.yaml")
    assert "types" in contract
    assert "constraints" in contract
    assert contract["treatment_col"] == "treated"


def test_build_schema():
    """Test pandera schema building from contract"""
    contract = load_contract("ciq/contracts/dataset.yaml")
    schema = build_schema(contract)

    # Test with valid data
    df = pd.DataFrame(
        {
            "customer_id": [1],
            "event_time": ["2025-01-01 00:00:00"],
            "treated": [0],
            "y": [0.0],
            "age": [30],
            "gender": ["M"],
            "rfm_score": [100.0],
            "prior_7d_spend": [0.0],
            "web_session_cnt": [0],
        }
    )

    # Should not raise
    validated = schema.validate(df)
    assert len(validated) == 1


def test_forbid_leakage_pass():
    """Test leakage detection - pass"""
    df = pd.DataFrame({"age": [30], "treated": [1], "y": [1.0]})
    patterns = ["future_*", "*_post"]

    # Should not raise
    forbid_leakage(df, patterns)


def test_forbid_leakage_fail():
    """Test leakage detection - fail"""
    df = pd.DataFrame({"age": [30], "treated": [1], "future_outcome": [1.0]})
    patterns = ["future_*", "*_post"]

    # Should raise
    with pytest.raises(ValueError, match="Leakage columns detected"):
        forbid_leakage(df, patterns)


def test_schema_validation_fail_on_missing_required():
    """Test schema validation failure on missing required column"""
    contract = load_contract("ciq/contracts/dataset.yaml")
    schema = build_schema(contract)

    # Missing 'customer_id' (required)
    df = pd.DataFrame(
        {
            "event_time": ["2025-01-01 00:00:00"],
            "treated": [0],
            "y": [0.0],
            "age": [30],
            "gender": ["M"],
            "rfm_score": [100.0],
            "prior_7d_spend": [0.0],
            "web_session_cnt": [0],
        }
    )

    with pytest.raises(Exception):  # pandera.errors.SchemaError
        schema.validate(df)


def test_schema_validation_category():
    """Test category validation"""
    contract = load_contract("ciq/contracts/dataset.yaml")
    schema = build_schema(contract)

    # Invalid gender category
    df = pd.DataFrame(
        {
            "customer_id": [1],
            "event_time": ["2025-01-01 00:00:00"],
            "treated": [0],
            "y": [0.0],
            "age": [30],
            "gender": ["X"],  # Invalid
            "rfm_score": [100.0],
            "prior_7d_spend": [0.0],
            "web_session_cnt": [0],
        }
    )

    with pytest.raises(Exception):  # pandera.errors.SchemaError
        schema.validate(df)
