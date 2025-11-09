"""
Strict Data Contract Validator - NASA/Google Standard

Purpose: Enforce strict schema validation for all 20+ estimators
Features:
- Estimator-specific required column validation
- HTTP 400 error responses (no silent fallbacks)
- Derivation Ledger tracking
- Environment variable controls
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import numpy as np
import pandas as pd
from pydantic import BaseModel


class EstimatorFamily(str, Enum):
    """Estimator families with distinct data requirements"""
    BASIC = "basic"  # Simple ATE (Diff/IPS/DR)
    COVARIATE = "covariate"  # Requires X_*
    IV = "iv"  # Instrumental Variables
    DID = "did"  # Difference-in-Differences
    RD = "rd"  # Regression Discontinuity
    NETWORK = "network"  # Network Effects
    GEOGRAPHIC = "geographic"  # Spatial/Geographic
    TRANSPORT = "transport"  # Domain Shift
    PROXIMAL = "proximal"  # Proximal Causal
    OPE = "ope"  # Off-Policy Evaluation


@dataclass
class ColumnRequirement:
    """Column requirement specification"""
    name: str
    required: bool = True
    alternative: Optional[str] = None  # Alternative column name
    estimators: Set[EstimatorFamily] = field(default_factory=set)
    description: str = ""


# Core schema definition
CORE_COLUMNS = [
    ColumnRequirement("y", required=True, estimators={EstimatorFamily.BASIC}, description="Outcome variable"),
    ColumnRequirement("treatment", required=True, estimators={EstimatorFamily.BASIC}, description="Treatment assignment {0,1}"),
    ColumnRequirement("unit_id", required=True, estimators={EstimatorFamily.BASIC}, description="Unit identifier"),
    ColumnRequirement("time", required=True, estimators={EstimatorFamily.DID}, description="Time period"),
]

EXTENDED_COLUMNS = [
    # Covariates
    ColumnRequirement("X_", required=False, estimators={EstimatorFamily.COVARIATE}, description="Covariate prefix (10-100 columns)"),

    # DiD/Event Study
    ColumnRequirement("treated_time", required=True, estimators={EstimatorFamily.DID}, description="Intervention start time"),
    ColumnRequirement("group", required=False, estimators={EstimatorFamily.DID}, description="Treatment/control group"),

    # Instrumental Variables
    ColumnRequirement("Z_instrument", required=True, estimators={EstimatorFamily.IV}, description="Instrumental variable(s)"),

    # Regression Discontinuity
    ColumnRequirement("r_running", required=True, estimators={EstimatorFamily.RD}, description="Running variable"),
    ColumnRequirement("c_cutoff", required=True, estimators={EstimatorFamily.RD}, description="Cutoff threshold"),

    # Network
    ColumnRequirement("cluster_id", required=True, estimators={EstimatorFamily.NETWORK}, description="Network cluster ID"),
    ColumnRequirement("exposure", required=False, estimators={EstimatorFamily.NETWORK}, alternative="edges", description="Neighborhood treatment rate"),

    # Geographic
    ColumnRequirement("lat", required=True, estimators={EstimatorFamily.GEOGRAPHIC}, alternative="region_id", description="Latitude"),
    ColumnRequirement("lon", required=True, estimators={EstimatorFamily.GEOGRAPHIC}, alternative="region_id", description="Longitude"),
    ColumnRequirement("region_id", required=False, estimators={EstimatorFamily.GEOGRAPHIC}, alternative="lat", description="Region identifier"),

    # Transport/Domain
    ColumnRequirement("domain", required=True, estimators={EstimatorFamily.TRANSPORT}, description="Source/target domain"),

    # Proximal
    ColumnRequirement("Z_proxy", required=True, estimators={EstimatorFamily.PROXIMAL}, description="Treatment proxy prefix"),
    ColumnRequirement("W_proxy", required=True, estimators={EstimatorFamily.PROXIMAL}, description="Outcome proxy prefix"),

    # OPE/Policy
    ColumnRequirement("cost", required=False, estimators={EstimatorFamily.OPE}, description="Treatment cost"),
    ColumnRequirement("log_propensity", required=False, estimators={EstimatorFamily.OPE}, description="Logging policy propensity"),
    ColumnRequirement("value_per_y", required=False, estimators={EstimatorFamily.OPE}, description="Monetary value per outcome unit"),
]


@dataclass
class Derivation:
    """Derivation record for Derivation Ledger"""
    output_column: str
    function: str
    input_columns: List[str]
    rows_affected: int
    null_count: int = 0
    enabled_by_flag: Optional[str] = None


@dataclass
class DerivationLedger:
    """Derivation Ledger - tracks all computed/derived columns"""
    dataset_id: str
    generated_at: str
    derivations: List[Derivation] = field(default_factory=list)

    def add(self, derivation: Derivation):
        """Add derivation to ledger"""
        self.derivations.append(derivation)

    def to_dict(self) -> Dict[str, Any]:
        """Export to dictionary"""
        return {
            "dataset_id": self.dataset_id,
            "generated_at": self.generated_at,
            "derivations": [
                {
                    "output_column": d.output_column,
                    "function": d.function,
                    "input_columns": d.input_columns,
                    "rows_affected": d.rows_affected,
                    "null_count": d.null_count,
                    **({"enabled_by_flag": d.enabled_by_flag} if d.enabled_by_flag else {})
                }
                for d in self.derivations
            ]
        }


class ValidationError(Exception):
    """Validation error with HTTP 400 details"""
    def __init__(self, message: str, available_columns: List[str] = None, missing_columns: List[str] = None):
        self.message = message
        self.available_columns = available_columns or []
        self.missing_columns = missing_columns or []
        super().__init__(self.message)

    def to_http_400(self) -> Dict[str, Any]:
        """Convert to HTTP 400 error response"""
        return {
            "error": "SCHEMA_VALIDATION_FAILED",
            "message": self.message,
            "available_columns": self.available_columns,
            "missing_columns": self.missing_columns,
            "status_code": 400
        }


class StrictDataContract:
    """
    Strict Data Contract Validator

    Design Principle: "No data, no model" - Missing required columns result in HTTP 400 errors,
    never silent fallbacks.
    """

    def __init__(self, dataset_id: str):
        self.dataset_id = dataset_id
        self.ledger = DerivationLedger(
            dataset_id=dataset_id,
            generated_at=datetime.utcnow().isoformat() + "Z"
        )

        # Environment variable controls
        self.strict_mode = os.getenv("STRICT_DATA_CONTRACT", "1") == "1"
        self.allow_mock = os.getenv("ALLOW_MOCK_COUNTERFACTUAL", "0") == "1"
        self.allow_estimate_propensity = os.getenv("ALLOW_ESTIMATE_PROPENSITY", "0") == "1"
        self.require_iv_z = os.getenv("REQUIRE_IV_Z", "1") == "1"
        self.require_rd_cutoff = os.getenv("REQUIRE_RD_CUTOFF", "1") == "1"
        self.require_did_t0 = os.getenv("REQUIRE_DID_T0", "1") == "1"

    def validate(
        self,
        df: pd.DataFrame,
        estimators: List[EstimatorFamily],
        mapping: Optional[Dict[str, str]] = None
    ) -> pd.DataFrame:
        """
        Validate DataFrame against required schema for given estimators

        Args:
            df: Input DataFrame
            estimators: List of estimator families to validate for
            mapping: Optional column name mapping

        Returns:
            Validated DataFrame

        Raises:
            ValidationError: If validation fails (HTTP 400)
        """
        if not self.strict_mode:
            return df

        # Apply mapping if provided
        if mapping:
            df = df.rename(columns={v: k for k, v in mapping.items()})

        available_columns = set(df.columns)
        missing_columns = []

        # Check core columns
        for col_req in CORE_COLUMNS:
            if col_req.required and any(est in estimators for est in col_req.estimators):
                if col_req.name not in available_columns:
                    missing_columns.append(col_req.name)

        # Check extended columns
        for col_req in EXTENDED_COLUMNS:
            if col_req.required and any(est in estimators for est in col_req.estimators):
                # Handle prefix columns (X_, Z_proxy, etc.)
                if col_req.name.endswith("_"):
                    prefix_cols = [c for c in available_columns if c.startswith(col_req.name)]
                    if not prefix_cols:
                        # Check alternative
                        if col_req.alternative and col_req.alternative in available_columns:
                            continue
                        missing_columns.append(col_req.name + "*")
                else:
                    if col_req.name not in available_columns:
                        # Check alternative
                        if col_req.alternative and col_req.alternative in available_columns:
                            continue
                        missing_columns.append(col_req.name)

        # Specific estimator checks
        if EstimatorFamily.IV in estimators and self.require_iv_z:
            if not any(c.startswith("Z_") or c == "Z_instrument" for c in available_columns):
                missing_columns.append("Z_instrument or Z_*")

        if EstimatorFamily.RD in estimators and self.require_rd_cutoff:
            if "r_running" not in available_columns or "c_cutoff" not in available_columns:
                missing_columns.extend(["r_running", "c_cutoff"])

        if EstimatorFamily.DID in estimators and self.require_did_t0:
            if "treated_time" not in available_columns:
                missing_columns.append("treated_time")

        # Raise HTTP 400 if validation fails
        if missing_columns:
            raise ValidationError(
                message=f"Required columns missing for estimators {[e.value for e in estimators]}",
                available_columns=list(available_columns),
                missing_columns=missing_columns
            )

        return df

    def derive_exposure(
        self,
        df: pd.DataFrame,
        edges: pd.DataFrame,
        k: int = 3,
        method: str = "mean"
    ) -> pd.DataFrame:
        """
        Derive exposure from edges table (for network effects)

        Args:
            df: Main DataFrame
            edges: Edges DataFrame with [src, dst, weight]
            k: k-nearest neighbors
            method: Aggregation method

        Returns:
            DataFrame with 'exposure' column added
        """
        # Simplified implementation - compute mean treatment of k-nearest neighbors
        # In production, this should use proper graph algorithms

        exposure = []
        for unit_id in df["unit_id"]:
            # Get neighbors
            neighbors = edges[edges["src"] == unit_id].head(k)
            if len(neighbors) > 0:
                neighbor_ids = neighbors["dst"].values
                neighbor_treatments = df[df["unit_id"].isin(neighbor_ids)]["treatment"]
                exp = neighbor_treatments.mean() if len(neighbor_treatments) > 0 else 0.0
            else:
                exp = 0.0
            exposure.append(exp)

        df["exposure"] = exposure

        # Record in ledger
        self.ledger.add(Derivation(
            output_column="exposure",
            function=f"mean_treatment_neighborhood(k={k})",
            input_columns=["edges.parquet", "treatment"],
            rows_affected=len(df),
            null_count=df["exposure"].isnull().sum()
        ))

        return df

    def derive_propensity(
        self,
        df: pd.DataFrame,
        features: List[str]
    ) -> pd.DataFrame:
        """
        Derive log_propensity from features (if allowed)

        Args:
            df: Main DataFrame
            features: Feature columns for propensity model

        Returns:
            DataFrame with 'log_propensity' column added

        Raises:
            ValidationError: If propensity estimation is not allowed
        """
        if not self.allow_estimate_propensity:
            raise ValidationError(
                message="Propensity estimation not allowed (set ALLOW_ESTIMATE_PROPENSITY=1)",
                available_columns=list(df.columns),
                missing_columns=["log_propensity"]
            )

        # Simplified logistic regression
        from sklearn.linear_model import LogisticRegression

        X = df[features].fillna(0)
        y = df["treatment"]

        model = LogisticRegression(max_iter=1000)
        model.fit(X, y)

        propensity = model.predict_proba(X)[:, 1]
        df["log_propensity"] = np.log(propensity + 1e-10)

        # Record in ledger
        self.ledger.add(Derivation(
            output_column="log_propensity",
            function=f"logit(treatment ~ {' + '.join(features)})",
            input_columns=features,
            rows_affected=len(df),
            null_count=df["log_propensity"].isnull().sum(),
            enabled_by_flag="ALLOW_ESTIMATE_PROPENSITY=1"
        ))

        return df

    def export_ledger(self, output_path: Path):
        """Export Derivation Ledger to JSON"""
        import json

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(self.ledger.to_dict(), f, indent=2)


# Convenience functions

def validate_for_estimators(
    df: pd.DataFrame,
    estimators: List[str],
    dataset_id: str = "unknown",
    mapping: Optional[Dict[str, str]] = None
) -> pd.DataFrame:
    """
    Validate DataFrame for given estimator names

    Args:
        df: Input DataFrame
        estimators: List of estimator names (e.g., ["tvce", "ope", "iv"])
        dataset_id: Dataset identifier
        mapping: Column name mapping

    Returns:
        Validated DataFrame

    Raises:
        ValidationError: If validation fails
    """
    # Map estimator names to families
    estimator_map = {
        "tvce": EstimatorFamily.COVARIATE,
        "ope": EstimatorFamily.OPE,
        "iv": EstimatorFamily.IV,
        "did": EstimatorFamily.DID,
        "rd": EstimatorFamily.RD,
        "network": EstimatorFamily.NETWORK,
        "geographic": EstimatorFamily.GEOGRAPHIC,
        "transport": EstimatorFamily.TRANSPORT,
        "proximal": EstimatorFamily.PROXIMAL,
    }

    families = [estimator_map.get(est, EstimatorFamily.BASIC) for est in estimators]

    validator = StrictDataContract(dataset_id)
    return validator.validate(df, families, mapping)
