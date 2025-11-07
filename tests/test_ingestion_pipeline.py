# tests/test_ingestion_pipeline.py
import pytest
import yaml
import pandas as pd
from pathlib import Path
import json

# Ensure the backend is in the path for imports
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.ingestion.parquet_pipeline import ParquetPipeline


@pytest.fixture
def test_env(tmp_path: Path) -> dict:
    """Create a temporary environment for testing the pipeline."""
    data_dir = tmp_path / "data"
    uploads_dir = data_dir / "uploads"
    uploads_dir.mkdir(parents=True)

    # Create a test contract file
    contract_content = {
        "id_col": "customer_id",
        "treatment_col": "treated",
        "outcome_col": "y",
        "covariate_cols": ["age", "rfm_score"],
        "types": {
            "customer_id": "int64",
            "treated": "int8",
            "y": "float64",
            "age": "int16",
            "rfm_score": "float32",
        },
        "quality_gates": {
            "overlap_threshold": 0.1, # Low threshold for test
            "max_smd": 0.25, # Generous threshold for test
        },
    }
    contract_path = tmp_path / "contract.yaml"
    with open(contract_path, "w") as f:
        yaml.dump(contract_content, f)

    return {"data_dir": data_dir, "uploads_dir": uploads_dir, "contract_path": contract_path}


def test_pipeline_success_case(test_env: dict):
    """Test the pipeline with data that should pass all gates."""
    # Create a "good" sample CSV with balanced covariates
    good_data = pd.DataFrame({
        "customer_id": range(100),
        "treated": [0]*50 + [1]*50,
        "y": [1.0]*100,
        "age": [25, 35]*50, # Perfectly balanced
        "rfm_score": [100, 120]*50, # Perfectly balanced
    })
    good_csv_path = test_env["uploads_dir"] / "good_data.csv"
    good_data.to_csv(good_csv_path, index=False)

    # Initialize and run the pipeline
    pipeline = ParquetPipeline(data_dir=test_env["data_dir"], contract_path=str(test_env["contract_path"]))
    result = pipeline.process_upload(file_path=good_csv_path, dataset_id="dataset_good")

    # --- Assertions ---
    assert result["quality_gates_status"] == "PASSED"
    assert result["max_smd"] < 0.1 # Should be near zero

    packet_path = test_env["data_dir"] / "packets" / "dataset_good"
    assert packet_path.exists()
    assert (packet_path / "data.parquet").exists()
    assert (packet_path / "metadata.json").exists()

    quarantine_path = test_env["data_dir"] / "quarantine" / "dataset_good"
    assert not quarantine_path.exists()


def test_pipeline_quality_gate_failure_case(test_env: dict):
    """Test the pipeline with data that should fail the SMD quality gate."""
    # Create a "bad" sample CSV with severe covariate imbalance
    bad_data = pd.DataFrame({
        "customer_id": range(100),
        "treated": [0]*50 + [1]*50,
        "y": [1.0]*100,
        "age": [20]*50 + [50]*50, # Severe imbalance
        "rfm_score": [100]*50 + [500]*50, # Severe imbalance
    })
    bad_csv_path = test_env["uploads_dir"] / "bad_data.csv"
    bad_data.to_csv(bad_csv_path, index=False)

    # Initialize the pipeline
    pipeline = ParquetPipeline(data_dir=test_env["data_dir"], contract_path=str(test_env["contract_path"]))

    # Run the pipeline and assert that it raises a ValueError for gate failure
    with pytest.raises(ValueError, match="Quality gate\(s\) failed: Max |SMD|") as excinfo:
        pipeline.process_upload(file_path=bad_csv_path, dataset_id="dataset_bad")

    # --- Assertions ---
    assert "is above threshold" in str(excinfo.value)

    # Check that the file was quarantined
    quarantine_path = test_env["data_dir"] / "quarantine" / "dataset_bad"
    assert quarantine_path.exists()
    assert (quarantine_path / "bad_data.csv").exists()
    
    failure_meta_path = quarantine_path / "failure_metadata.json"
    assert failure_meta_path.exists()
    with open(failure_meta_path, "r") as f:
        meta = json.load(f)
        assert meta["dataset_id"] == "dataset_bad"
        assert "Quality gate(s) failed" in meta["reason"]

    # Check that no packet was created
    packet_path = test_env["data_dir"] / "packets" / "dataset_bad"
    assert not packet_path.exists()
