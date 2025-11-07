# backend/validation/pipeline.py
"""
Validation Pipeline (Col1 Specification)

Checks:
1. Leakage Detection - Y/future information in covariates
2. VIF (Variance Inflation Factor) - Multicollinearity
3. Missing Data Analysis - Patterns and mechanisms
4. Balance Check - Covariate balance between treatment groups
5. Overlap Check - Common support violations
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass


@dataclass
class LeakageCheck:
    """Leakage detection result"""
    has_leakage: bool
    suspicious_columns: List[str]
    correlations: Dict[str, float]
    severity: str  # "critical", "warning", "ok"
    recommendations: List[str]


@dataclass
class VIFCheck:
    """VIF multicollinearity check result"""
    has_multicollinearity: bool
    vif_scores: Dict[str, float]
    problematic_columns: List[str]
    severity: str
    recommendations: List[str]


@dataclass
class MissingDataCheck:
    """Missing data analysis result"""
    has_issues: bool
    missing_rates: Dict[str, float]
    missing_patterns: Dict[str, Any]
    mechanism: str  # "MCAR", "MAR", "MNAR", "unknown"
    severity: str
    recommendations: List[str]


@dataclass
class BalanceCheck:
    """Covariate balance check result"""
    is_balanced: bool
    smd_scores: Dict[str, float]
    imbalanced_columns: List[str]
    severity: str
    recommendations: List[str]


@dataclass
class OverlapCheck:
    """Common support / overlap check result"""
    has_overlap: bool
    propensity_range: Tuple[float, float]
    trimmed_fraction: float
    severity: str
    recommendations: List[str]


class ValidationPipeline:
    """
    Comprehensive validation pipeline

    Runs all quality checks and provides actionable recommendations
    """

    def __init__(self, df: pd.DataFrame, mapping: Dict[str, str]):
        self.df = df
        self.mapping = mapping
        self.y = mapping.get("y")
        self.treatment = mapping.get("treatment")
        self.unit_id = mapping.get("unit_id")
        self.time = mapping.get("time")

        # Identify covariate columns
        mapped_cols = set(mapping.values())
        self.covariates = [c for c in df.columns if c not in mapped_cols]

    def check_leakage(self) -> LeakageCheck:
        """
        Detect potential data leakage

        Checks:
        - Y correlation with covariates (suspiciously high)
        - Future information (time-based)
        - Perfect predictions
        """
        if not self.y:
            return LeakageCheck(False, [], {}, "ok", [])

        suspicious = []
        correlations = {}
        recommendations = []

        # Get numeric covariates
        numeric_covs = [c for c in self.covariates if pd.api.types.is_numeric_dtype(self.df[c])]

        for cov in numeric_covs:
            corr = self.df[[self.y, cov]].corr().iloc[0, 1]
            correlations[cov] = abs(corr)

            # Suspiciously high correlation
            if abs(corr) > 0.9:
                suspicious.append(cov)
                recommendations.append(
                    f"Remove '{cov}' (correlation={corr:.3f} with outcome, likely leakage)"
                )

        # Time-based leakage check
        if self.time and self.time in self.df.columns:
            # Check for covariates that might contain future information
            for cov in self.covariates:
                if any(kw in cov.lower() for kw in ["future", "post", "after", "result"]):
                    suspicious.append(cov)
                    recommendations.append(
                        f"Suspicious temporal name '{cov}' - verify it doesn't contain future info"
                    )

        has_leakage = len(suspicious) > 0
        severity = "critical" if len(suspicious) >= 3 else ("warning" if len(suspicious) > 0 else "ok")

        return LeakageCheck(
            has_leakage=has_leakage,
            suspicious_columns=suspicious,
            correlations=correlations,
            severity=severity,
            recommendations=recommendations if recommendations else ["No leakage detected"],
        )

    def check_vif(self, threshold: float = 10.0) -> VIFCheck:
        """
        Calculate Variance Inflation Factor for multicollinearity

        VIF = 1 / (1 - R²_j)
        where R²_j is from regressing X_j on all other X

        Threshold:
        - VIF < 5: No multicollinearity
        - 5 <= VIF < 10: Moderate
        - VIF >= 10: High multicollinearity
        """
        numeric_covs = [c for c in self.covariates if pd.api.types.is_numeric_dtype(self.df[c])]

        if len(numeric_covs) < 2:
            return VIFCheck(False, {}, [], "ok", ["Not enough numeric covariates for VIF"])

        vif_scores = {}
        problematic = []
        recommendations = []

        # Calculate VIF for each covariate
        X = self.df[numeric_covs].copy()
        X = X.fillna(X.mean())  # Simple imputation for VIF calculation

        for i, col in enumerate(numeric_covs):
            try:
                # Regress X_i on all other X
                y_temp = X.iloc[:, i].values
                X_temp = X.drop(columns=[col]).values

                # Add intercept
                X_temp = np.column_stack([np.ones(len(X_temp)), X_temp])

                # OLS: β = (X'X)^(-1) X'y
                beta = np.linalg.lstsq(X_temp, y_temp, rcond=None)[0]
                y_pred = X_temp @ beta

                # R²
                ss_res = np.sum((y_temp - y_pred) ** 2)
                ss_tot = np.sum((y_temp - np.mean(y_temp)) ** 2)
                r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

                # VIF
                vif = 1 / (1 - r_squared) if r_squared < 0.9999 else 999

                vif_scores[col] = vif

                if vif >= threshold:
                    problematic.append(col)
                    recommendations.append(
                        f"Remove or combine '{col}' (VIF={vif:.1f}, highly collinear)"
                    )

            except np.linalg.LinAlgError:
                vif_scores[col] = 999
                problematic.append(col)

        has_multicollinearity = len(problematic) > 0
        severity = "warning" if has_multicollinearity else "ok"

        return VIFCheck(
            has_multicollinearity=has_multicollinearity,
            vif_scores=vif_scores,
            problematic_columns=problematic,
            severity=severity,
            recommendations=recommendations if recommendations else ["No multicollinearity detected"],
        )

    def check_missing_data(self, threshold: float = 0.2) -> MissingDataCheck:
        """
        Analyze missing data patterns and mechanisms

        Mechanisms:
        - MCAR (Missing Completely At Random): Missing independent of data
        - MAR (Missing At Random): Missing depends on observed data
        - MNAR (Missing Not At Random): Missing depends on unobserved data
        """
        missing_rates = {}
        for col in self.df.columns:
            missing_rates[col] = self.df[col].isna().mean()

        high_missing = {k: v for k, v in missing_rates.items() if v > threshold}

        # Pattern analysis
        patterns = {}
        if self.treatment and self.treatment in self.df.columns:
            # Check if missing differs by treatment
            for col in high_missing.keys():
                t0_missing = self.df[self.df[self.treatment] == 0][col].isna().mean()
                t1_missing = self.df[self.df[self.treatment] == 1][col].isna().mean()
                patterns[col] = {
                    "control_missing": t0_missing,
                    "treated_missing": t1_missing,
                    "diff": abs(t1_missing - t0_missing),
                }

        # Infer mechanism
        mechanism = "MCAR"  # Default assumption
        if patterns:
            max_diff = max(p["diff"] for p in patterns.values())
            if max_diff > 0.1:
                mechanism = "MAR"  # Missing depends on treatment

        recommendations = []
        for col, rate in high_missing.items():
            recommendations.append(
                f"'{col}' has {rate*100:.1f}% missing - consider imputation or removal"
            )

        if mechanism == "MAR":
            recommendations.append(
                "Missing data pattern differs by treatment - use inverse probability weighting"
            )

        has_issues = len(high_missing) > 0
        severity = "warning" if has_issues else "ok"

        return MissingDataCheck(
            has_issues=has_issues,
            missing_rates=missing_rates,
            missing_patterns=patterns,
            mechanism=mechanism,
            severity=severity,
            recommendations=recommendations if recommendations else ["No significant missing data"],
        )

    def check_balance(self, threshold: float = 0.1) -> BalanceCheck:
        """
        Check covariate balance using Standardized Mean Difference (SMD)

        SMD = (mean_treated - mean_control) / pooled_std

        Threshold:
        - SMD < 0.1: Good balance
        - 0.1 <= SMD < 0.25: Moderate imbalance
        - SMD >= 0.25: Severe imbalance
        """
        if not self.treatment or self.treatment not in self.df.columns:
            return BalanceCheck(True, {}, [], "ok", ["No treatment variable specified"])

        numeric_covs = [c for c in self.covariates if pd.api.types.is_numeric_dtype(self.df[c])]

        smd_scores = {}
        imbalanced = []
        recommendations = []

        for cov in numeric_covs:
            t0_vals = self.df[self.df[self.treatment] == 0][cov].dropna()
            t1_vals = self.df[self.df[self.treatment] == 1][cov].dropna()

            if len(t0_vals) == 0 or len(t1_vals) == 0:
                continue

            mean_diff = t1_vals.mean() - t0_vals.mean()
            pooled_std = np.sqrt((t0_vals.var() + t1_vals.var()) / 2)

            smd = abs(mean_diff / pooled_std) if pooled_std > 0 else 0
            smd_scores[cov] = smd

            if smd >= threshold:
                imbalanced.append(cov)
                recommendations.append(
                    f"Adjust for '{cov}' (SMD={smd:.3f}, imbalanced)"
                )

        is_balanced = len(imbalanced) == 0
        severity = "warning" if len(imbalanced) > 3 else ("ok" if is_balanced else "info")

        return BalanceCheck(
            is_balanced=is_balanced,
            smd_scores=smd_scores,
            imbalanced_columns=imbalanced,
            severity=severity,
            recommendations=recommendations if recommendations else ["Covariates are balanced"],
        )

    def check_overlap(self, propensity_col: Optional[str] = None) -> OverlapCheck:
        """
        Check common support / propensity overlap

        Ensures treated and control have overlapping propensity scores
        """
        if not propensity_col or propensity_col not in self.df.columns:
            return OverlapCheck(
                has_overlap=True,
                propensity_range=(0.0, 1.0),
                trimmed_fraction=0.0,
                severity="ok",
                recommendations=["No propensity scores provided - skipping overlap check"],
            )

        if not self.treatment or self.treatment not in self.df.columns:
            return OverlapCheck(True, (0.0, 1.0), 0.0, "ok", ["No treatment variable"])

        # Get propensity ranges by treatment
        p0 = self.df[self.df[self.treatment] == 0][propensity_col].dropna()
        p1 = self.df[self.df[self.treatment] == 1][propensity_col].dropna()

        overlap_min = max(p0.min(), p1.min())
        overlap_max = min(p0.max(), p1.max())

        # Calculate trimming
        n_total = len(self.df)
        n_in_support = len(self.df[
            (self.df[propensity_col] >= overlap_min) &
            (self.df[propensity_col] <= overlap_max)
        ])
        trimmed_fraction = 1 - (n_in_support / n_total)

        has_overlap = overlap_min < overlap_max
        severity = "warning" if trimmed_fraction > 0.1 else "ok"

        recommendations = []
        if trimmed_fraction > 0.1:
            recommendations.append(
                f"Trim {trimmed_fraction*100:.1f}% of data outside common support [{overlap_min:.3f}, {overlap_max:.3f}]"
            )

        return OverlapCheck(
            has_overlap=has_overlap,
            propensity_range=(overlap_min, overlap_max),
            trimmed_fraction=trimmed_fraction,
            severity=severity,
            recommendations=recommendations if recommendations else ["Good propensity overlap"],
        )

    def run_all(self, propensity_col: Optional[str] = None) -> Dict[str, Any]:
        """Run all validation checks"""
        return {
            "leakage": self.check_leakage(),
            "vif": self.check_vif(),
            "missing": self.check_missing_data(),
            "balance": self.check_balance(),
            "overlap": self.check_overlap(propensity_col),
        }


def validate_dataset(df: pd.DataFrame, mapping: Dict[str, str], propensity_col: Optional[str] = None) -> Dict[str, Any]:
    """Run full validation pipeline"""
    pipeline = ValidationPipeline(df, mapping)
    return pipeline.run_all(propensity_col)
