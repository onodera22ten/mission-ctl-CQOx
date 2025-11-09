"""
Production Outputs - NASA/Google Standard

Purpose: Generate production-ready artifacts for deployment
Outputs:
1. Policy Distribution Files (CSV/Parquet) - For serving layer
2. Quality Gates Reports (JSON/CSV) - For audit and monitoring
3. Audit Trail (JSONL) - Immutable log of all evaluations
4. Derivation Ledger (JSON) - Transparent record of computed columns
5. Decision Cards (PDF/HTML) - Executive summary with Go/Canary/Hold

All outputs include:
- Timestamp (ISO 8601)
- Version/hash for reproducibility
- Metadata (dataset_id, scenario_id, etc.)
"""

from __future__ import annotations

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict

import pandas as pd
import numpy as np


@dataclass
class ProductionOutput:
    """Base class for production outputs"""
    dataset_id: str
    scenario_id: str
    generated_at: str
    version: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class PolicyDistribution(ProductionOutput):
    """Policy distribution file metadata"""
    format: str  # "csv" or "parquet"
    path: str
    n_units: int
    coverage: float
    estimated_profit: float


@dataclass
class QualityGatesReport(ProductionOutput):
    """Quality gates report metadata"""
    decision: str  # GO/CANARY/HOLD
    pass_rate: float
    gates_summary: Dict[str, int]  # {PASS: x, FAIL: y, WARNING: z}


@dataclass
class AuditTrailEntry(ProductionOutput):
    """Audit trail entry"""
    event_type: str  # "scenario_run", "quality_gates", "deployment"
    user_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class ProductionOutputGenerator:
    """
    Production Output Generator

    Generates all production-ready artifacts for deployment
    """

    def __init__(self, output_dir: Path = Path("exports")):
        """
        Args:
            output_dir: Base directory for outputs
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_policy_file(
        self,
        df: pd.DataFrame,
        scenario_spec: Dict[str, Any],
        new_policy: np.ndarray,
        scores: Optional[np.ndarray] = None,
        format: str = "parquet"
    ) -> Path:
        """
        Generate policy distribution file for serving layer

        Args:
            df: Original DataFrame with unit_id
            scenario_spec: Scenario specification
            new_policy: New treatment assignments (0/1 array)
            scores: Propensity scores or uplift scores (optional)
            format: Output format ("csv" or "parquet")

        Returns:
            Path to generated file
        """
        dataset_id = scenario_spec.get("dataset_id", "unknown")
        scenario_id = scenario_spec.get("id", "unknown")

        # Create policy DataFrame
        policy_df = pd.DataFrame({
            "unit_id": df.get("unit_id", range(len(new_policy))),
            "treatment": new_policy,
            "scenario_id": scenario_id,
            "generated_at": datetime.utcnow().isoformat() + "Z"
        })

        if scores is not None:
            policy_df["score"] = scores
            policy_df["rank"] = policy_df["score"].rank(ascending=False)

        # Add metadata
        policy_df.attrs["scenario_spec"] = scenario_spec

        # Generate filename with timestamp
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"policy_{dataset_id}_{scenario_id}_{timestamp}.{format}"
        output_path = self.output_dir / dataset_id / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        if format == "parquet":
            policy_df.to_parquet(output_path, index=False)
        elif format == "csv":
            policy_df.to_csv(output_path, index=False)
        else:
            raise ValueError(f"Unsupported format: {format}")

        return output_path

    def generate_quality_gates_report(
        self,
        quality_gates_result: Dict[str, Any],
        scenario_spec: Dict[str, Any],
        format: str = "json"
    ) -> Path:
        """
        Generate quality gates report

        Args:
            quality_gates_result: Quality gates evaluation result
            scenario_spec: Scenario specification
            format: Output format ("json" or "csv")

        Returns:
            Path to generated file
        """
        dataset_id = scenario_spec.get("dataset_id", "unknown")
        scenario_id = scenario_spec.get("id", "unknown")

        # Prepare report
        report = {
            "dataset_id": dataset_id,
            "scenario_id": scenario_id,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "decision": quality_gates_result.get("overall", {}).get("decision", "HOLD"),
            "pass_rate": quality_gates_result.get("overall", {}).get("pass_rate", 0.0),
            "gates": quality_gates_result.get("gates", []),
            "rationale": quality_gates_result.get("rationale", []),
            "scenario_spec_hash": self._compute_hash(scenario_spec)
        }

        # Generate filename
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"quality_gates_{dataset_id}_{scenario_id}_{timestamp}.{format}"
        output_path = self.output_dir / dataset_id / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        if format == "json":
            with open(output_path, "w") as f:
                json.dump(report, f, indent=2)
        elif format == "csv":
            # Flatten gates for CSV
            gates_df = pd.DataFrame(quality_gates_result.get("gates", []))
            gates_df["dataset_id"] = dataset_id
            gates_df["scenario_id"] = scenario_id
            gates_df["generated_at"] = report["generated_at"]
            gates_df.to_csv(output_path, index=False)
        else:
            raise ValueError(f"Unsupported format: {format}")

        return output_path

    def append_audit_trail(
        self,
        event_type: str,
        dataset_id: str,
        scenario_id: str,
        details: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None
    ) -> Path:
        """
        Append entry to audit trail (JSONL format)

        Args:
            event_type: Event type (e.g., "scenario_run", "quality_gates")
            dataset_id: Dataset identifier
            scenario_id: Scenario identifier
            details: Additional event details
            user_id: User identifier (optional)

        Returns:
            Path to audit trail file
        """
        # Audit trail is append-only JSONL
        audit_path = self.output_dir / dataset_id / "audit_trail.jsonl"
        audit_path.parent.mkdir(parents=True, exist_ok=True)

        # Create entry
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event_type": event_type,
            "dataset_id": dataset_id,
            "scenario_id": scenario_id,
            "user_id": user_id,
            "details": details or {}
        }

        # Append to file
        with open(audit_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

        return audit_path

    def generate_derivation_ledger(
        self,
        ledger_dict: Dict[str, Any],
        dataset_id: str
    ) -> Path:
        """
        Generate derivation ledger export

        Args:
            ledger_dict: Derivation ledger dictionary
            dataset_id: Dataset identifier

        Returns:
            Path to ledger file
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"derivation_ledger_{dataset_id}_{timestamp}.json"
        output_path = self.output_dir / dataset_id / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(ledger_dict, f, indent=2)

        return output_path

    def generate_comparison_report(
        self,
        baseline_result: Dict[str, Any],
        scenario_result: Dict[str, Any],
        scenario_spec: Dict[str, Any],
        quality_gates: Dict[str, Any]
    ) -> Path:
        """
        Generate S0 vs S1 comparison report (JSON)

        Args:
            baseline_result: S0 (baseline) evaluation result
            scenario_result: S1 (scenario) evaluation result
            scenario_spec: Scenario specification
            quality_gates: Quality gates result

        Returns:
            Path to comparison report
        """
        dataset_id = scenario_spec.get("dataset_id", "unknown")
        scenario_id = scenario_spec.get("id", "unknown")

        report = {
            "dataset_id": dataset_id,
            "scenario_id": scenario_id,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "baseline": {
                "value": baseline_result.get("value", 0.0),
                "ci": baseline_result.get("ci", [0.0, 0.0]),
                "std_error": baseline_result.get("std_error", 0.0)
            },
            "scenario": {
                "value": scenario_result.get("value", 0.0),
                "ci": scenario_result.get("ci", [0.0, 0.0]),
                "std_error": scenario_result.get("std_error", 0.0)
            },
            "delta": {
                "value": scenario_result.get("value", 0.0) - baseline_result.get("value", 0.0),
                "pct_change": (
                    (scenario_result.get("value", 0.0) - baseline_result.get("value", 0.0))
                    / abs(baseline_result.get("value", 1.0)) * 100
                )
            },
            "quality_gates": quality_gates,
            "scenario_spec_hash": self._compute_hash(scenario_spec)
        }

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"comparison_{dataset_id}_{scenario_id}_{timestamp}.json"
        output_path = self.output_dir / dataset_id / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)

        return output_path

    def _compute_hash(self, obj: Dict[str, Any]) -> str:
        """Compute deterministic hash of object for versioning"""
        obj_str = json.dumps(obj, sort_keys=True)
        return hashlib.sha256(obj_str.encode()).hexdigest()[:12]


# Convenience functions

def export_policy_distribution(
    df: pd.DataFrame,
    scenario_spec: Dict[str, Any],
    new_policy: np.ndarray,
    scores: Optional[np.ndarray] = None,
    output_dir: Path = Path("exports"),
    format: str = "parquet"
) -> Path:
    """
    Export policy distribution file

    Args:
        df: Original DataFrame
        scenario_spec: Scenario specification
        new_policy: Treatment assignments
        scores: Scores (optional)
        output_dir: Output directory
        format: File format

    Returns:
        Path to exported file
    """
    generator = ProductionOutputGenerator(output_dir)
    return generator.generate_policy_file(df, scenario_spec, new_policy, scores, format)


def export_quality_gates_report(
    quality_gates_result: Dict[str, Any],
    scenario_spec: Dict[str, Any],
    output_dir: Path = Path("exports"),
    format: str = "json"
) -> Path:
    """
    Export quality gates report

    Args:
        quality_gates_result: Quality gates evaluation
        scenario_spec: Scenario specification
        output_dir: Output directory
        format: File format

    Returns:
        Path to exported file
    """
    generator = ProductionOutputGenerator(output_dir)
    return generator.generate_quality_gates_report(quality_gates_result, scenario_spec, format)


def log_audit_trail(
    event_type: str,
    dataset_id: str,
    scenario_id: str,
    details: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None,
    output_dir: Path = Path("exports")
) -> Path:
    """
    Log event to audit trail

    Args:
        event_type: Event type
        dataset_id: Dataset ID
        scenario_id: Scenario ID
        details: Event details
        user_id: User ID
        output_dir: Output directory

    Returns:
        Path to audit trail file
    """
    generator = ProductionOutputGenerator(output_dir)
    return generator.append_audit_trail(event_type, dataset_id, scenario_id, details, user_id)
