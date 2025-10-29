# backend/inference/estimator_validator.py
"""
Estimator-specific Column Validation
Validates that required columns exist for each estimator and provides fallback logic
"""
from __future__ import annotations
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass


@dataclass
class EstimatorRequirements:
    """Required and optional columns for each estimator"""
    name: str
    required: List[str]  # Must have these columns
    optional: List[str]  # Nice to have (enables extra features)
    fallback: Optional[str] = None  # Fallback estimator if requirements not met


# Estimator specifications
ESTIMATOR_SPECS = {
    "tvce": EstimatorRequirements(
        name="Time-Varying Causal Effects (TVCE)",
        required=["y", "treatment"],
        optional=["time", "unit_id"],
        fallback="simple_diff"
    ),
    "ope": EstimatorRequirements(
        name="Off-Policy Evaluation (OPE/IPW)",
        required=["y", "treatment", "log_propensity"],
        optional=["unit_id"],
        fallback="tvce"
    ),
    "hidden": EstimatorRequirements(
        name="Hidden Confounding (Sensitivity)",
        required=["y", "treatment"],
        optional=["unit_id", "covariates"],
        fallback="tvce"
    ),
    "iv": EstimatorRequirements(
        name="Instrumental Variables (2SLS)",
        required=["y", "treatment", "z"],  # z = instrument
        optional=["unit_id", "covariates"],
        fallback="tvce"
    ),
    "transport": EstimatorRequirements(
        name="Transportability (IPSW)",
        required=["y", "treatment", "domain"],
        optional=["unit_id"],
        fallback="tvce"
    ),
    "proximal": EstimatorRequirements(
        name="Proximal Causal Inference",
        required=["y", "treatment", "w_neg", "z_neg"],
        optional=["unit_id"],
        fallback="tvce"
    ),
    "network": EstimatorRequirements(
        name="Network Effects",
        required=["y", "treatment", "cluster_id", "neighbor_exposure"],
        optional=["unit_id"],
        fallback="tvce"
    ),
}


class EstimatorValidator:
    """Validates column requirements for estimators"""

    def __init__(self, df: pd.DataFrame, mapping: Dict[str, str]):
        """
        Args:
            df: Input dataframe
            mapping: User-provided mapping (role -> column name)
        """
        self.df = df
        self.mapping = mapping
        self.available_columns = set(df.columns)

    def validate_estimator(self, estimator: str) -> Dict[str, any]:
        """
        Validate if estimator can run with current data

        Returns:
            Dict with keys:
                - can_run: bool
                - missing_required: List[str]
                - missing_optional: List[str]
                - fallback: Optional[str]
                - message: str
        """
        if estimator not in ESTIMATOR_SPECS:
            return {
                "can_run": False,
                "missing_required": [],
                "missing_optional": [],
                "fallback": None,
                "message": f"Unknown estimator: {estimator}"
            }

        spec = ESTIMATOR_SPECS[estimator]

        # Check required columns
        missing_required = []
        for role in spec.required:
            col = self.mapping.get(role)
            if not col or col not in self.available_columns:
                missing_required.append(role)

        # Check optional columns
        missing_optional = []
        for role in spec.optional:
            col = self.mapping.get(role)
            if not col or col not in self.available_columns:
                missing_optional.append(role)

        can_run = len(missing_required) == 0

        # Generate message
        if can_run:
            message = f"✓ {spec.name} can run"
            if missing_optional:
                message += f" (missing optional: {', '.join(missing_optional)})"
        else:
            message = f"✗ {spec.name} cannot run - missing required: {', '.join(missing_required)}"
            if spec.fallback:
                message += f" (will use fallback: {spec.fallback})"

        return {
            "can_run": can_run,
            "missing_required": missing_required,
            "missing_optional": missing_optional,
            "fallback": spec.fallback if not can_run else None,
            "message": message
        }

    def validate_all(self) -> Dict[str, Dict[str, any]]:
        """Validate all estimators"""
        results = {}
        for estimator in ESTIMATOR_SPECS.keys():
            results[estimator] = self.validate_estimator(estimator)
        return results

    def get_runnable_estimators(self) -> List[str]:
        """Get list of estimators that can run with current data"""
        validation = self.validate_all()
        return [name for name, result in validation.items() if result["can_run"]]

    def auto_detect_missing_columns(self) -> Dict[str, Optional[str]]:
        """
        Attempt to auto-detect missing columns based on heuristics

        Returns:
            Dict mapping role -> detected column name (or None)
        """
        from .column_selection import ColumnSelector

        selector = ColumnSelector(self.df)
        selection = selector.select_columns(confidence_threshold=0.2)

        # Map selection results to role names
        detected = {}

        # Standard roles
        for role in ["y", "treatment", "unit_id", "time"]:
            if role not in self.mapping or not self.mapping[role]:
                detected[role] = selection.get(role)

        # Special columns
        # log_propensity: look for columns with "propensity", "prob", "score"
        if "log_propensity" not in self.mapping or not self.mapping["log_propensity"]:
            propensity_candidates = [
                col for col in self.df.columns
                if any(kw in col.lower() for kw in ["propensity", "prob", "score", "ps"])
            ]
            if propensity_candidates:
                detected["log_propensity"] = propensity_candidates[0]

        # cost: look for "cost", "price", "expense"
        if "cost" not in self.mapping or not self.mapping["cost"]:
            cost_candidates = [
                col for col in self.df.columns
                if any(kw in col.lower() for kw in ["cost", "price", "expense", "spend"])
            ]
            if cost_candidates:
                detected["cost"] = cost_candidates[0]

        # domain: look for "domain", "site", "location"
        if "domain" not in self.mapping or not self.mapping["domain"]:
            domain_candidates = [
                col for col in self.df.columns
                if any(kw in col.lower() for kw in ["domain", "site", "location", "source"])
            ]
            if domain_candidates:
                detected["domain"] = domain_candidates[0]

        # cluster_id: look for "cluster", "group"
        if "cluster_id" not in self.mapping or not self.mapping["cluster_id"]:
            cluster_candidates = [
                col for col in self.df.columns
                if any(kw in col.lower() for kw in ["cluster", "group", "cohort"])
                and col not in [detected.get("unit_id"), self.mapping.get("unit_id")]
            ]
            if cluster_candidates:
                detected["cluster_id"] = cluster_candidates[0]

        # z (instrument): look for "instrument", "z", "iv"
        if "z" not in self.mapping or not self.mapping["z"]:
            iv_candidates = [
                col for col in self.df.columns
                if any(kw in col.lower() for kw in ["instrument", "iv", "z"])
                and col not in [self.mapping.get("treatment")]
            ]
            if iv_candidates:
                detected["z"] = iv_candidates[0]

        return detected

    def suggest_enhanced_mapping(self) -> Dict[str, str]:
        """
        Suggest enhanced mapping with auto-detected columns

        Returns:
            Enhanced mapping dict
        """
        enhanced = self.mapping.copy()
        detected = self.auto_detect_missing_columns()

        for role, col in detected.items():
            if col and (role not in enhanced or not enhanced[role]):
                enhanced[role] = col

        return enhanced

    def get_validation_report(self) -> str:
        """Generate human-readable validation report"""
        lines = ["=" * 80]
        lines.append("ESTIMATOR VALIDATION REPORT")
        lines.append("=" * 80)

        # Current mapping
        lines.append("\nCurrent Mapping:")
        for role, col in self.mapping.items():
            status = "✓" if col and col in self.available_columns else "✗"
            lines.append(f"  {status} {role:20} → {col or '(not set)'}")

        # Validation results
        lines.append("\nEstimator Requirements:")
        validation = self.validate_all()
        for estimator, result in validation.items():
            lines.append(f"\n  {estimator}:")
            lines.append(f"    {result['message']}")

        # Runnable estimators
        runnable = self.get_runnable_estimators()
        lines.append(f"\nRunnable Estimators ({len(runnable)}/{len(ESTIMATOR_SPECS)}):")
        for est in runnable:
            lines.append(f"  ✓ {est}")

        # Suggestions
        detected = self.auto_detect_missing_columns()
        if detected:
            lines.append("\nSuggested Additional Columns:")
            for role, col in detected.items():
                if col:
                    lines.append(f"  → {role:20} → {col}")

        lines.append("\n" + "=" * 80)
        return "\n".join(lines)


def validate_mapping(df: pd.DataFrame, mapping: Dict[str, str]) -> Dict[str, any]:
    """
    Convenience function to validate mapping

    Args:
        df: Input dataframe
        mapping: Role -> column mapping

    Returns:
        Validation results
    """
    validator = EstimatorValidator(df, mapping)
    return {
        "validation": validator.validate_all(),
        "runnable": validator.get_runnable_estimators(),
        "suggestions": validator.auto_detect_missing_columns(),
        "report": validator.get_validation_report()
    }


# CLI for testing
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python estimator_validator.py <csv_path>")
        sys.exit(1)

    csv_path = sys.argv[1]
    df = pd.read_csv(csv_path)

    # Minimal mapping (simulating user input)
    mapping = {
        "y": "y" if "y" in df.columns else None,
        "treatment": "treatment" if "treatment" in df.columns else None,
        "unit_id": "unit_id" if "unit_id" in df.columns else None,
    }

    validator = EstimatorValidator(df, mapping)
    print(validator.get_validation_report())
    print("\nEnhanced Mapping:")
    print(validator.suggest_enhanced_mapping())
