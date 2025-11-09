"""
Off-Policy Evaluation (OPE) - NASA/Google Standard

Purpose: Fast counterfactual policy evaluation using logged data
Methods:
- IPS (Inverse Propensity Scoring)
- DR (Doubly Robust)
- SNIPS (Self-Normalized IPS)

Reference: Dudík et al. (2014), "Doubly Robust Policy Evaluation and Optimization"
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats


@dataclass
class OPEResult:
    """OPE evaluation result"""
    method: str  # "ips", "dr", "snips"
    value: float  # V(π) - policy value
    std_error: float
    ci_lower: float
    ci_upper: float
    n_samples: int
    effective_sample_size: float  # ESS for importance sampling


class OffPolicyEvaluator:
    """
    Off-Policy Evaluator using logged data

    Evaluates counterfactual policies without running A/B tests
    """

    def __init__(
        self,
        df: pd.DataFrame,
        treatment_col: str = "treatment",
        outcome_col: str = "y",
        propensity_col: str = "log_propensity",
        cost_col: Optional[str] = None,
        value_per_y: float = 1.0
    ):
        """
        Args:
            df: Logged data with treatment, outcome, propensity
            treatment_col: Treatment column name
            outcome_col: Outcome column name
            propensity_col: Log propensity column
            cost_col: Cost column (optional)
            value_per_y: Monetary value per outcome unit
        """
        self.df = df.copy()
        self.treatment_col = treatment_col
        self.outcome_col = outcome_col
        self.propensity_col = propensity_col
        self.cost_col = cost_col
        self.value_per_y = value_per_y

        # Convert log propensity to propensity
        if propensity_col in df.columns:
            self.df["_propensity"] = np.exp(df[propensity_col])
        else:
            raise ValueError(f"Propensity column '{propensity_col}' not found")

        # Compute profit if cost available
        if cost_col and cost_col in df.columns:
            self.df["_profit"] = df[outcome_col] * value_per_y - df[cost_col]
        else:
            self.df["_profit"] = df[outcome_col] * value_per_y

    def evaluate_policy(
        self,
        new_policy: np.ndarray,
        method: str = "dr",
        alpha: float = 0.05
    ) -> OPEResult:
        """
        Evaluate new policy using OPE

        Args:
            new_policy: New treatment assignments (0/1 array)
            method: Evaluation method - "ips", "dr", or "snips"
            alpha: Significance level for CI

        Returns:
            OPEResult with policy value and confidence interval
        """
        if method == "ips":
            return self._evaluate_ips(new_policy, alpha)
        elif method == "snips":
            return self._evaluate_snips(new_policy, alpha)
        elif method == "dr":
            return self._evaluate_dr(new_policy, alpha)
        else:
            raise ValueError(f"Unknown method: {method}")

    def _evaluate_ips(self, new_policy: np.ndarray, alpha: float) -> OPEResult:
        """
        Inverse Propensity Scoring (IPS)

        V(π) = E[Y * π(a) / π₀(a)]

        Args:
            new_policy: New treatment assignments
            alpha: Significance level

        Returns:
            OPEResult
        """
        logged_treatment = self.df[self.treatment_col].values
        outcome = self.df["_profit"].values
        propensity = self.df["_propensity"].values

        # Importance weights
        # w_i = π(a_i|x_i) / π₀(a_i|x_i)
        # For binary treatment: π(a) = π if a=new_policy[i] else (1-π)
        weights = np.where(
            logged_treatment == new_policy,
            1.0 / (propensity + 1e-10),  # Matched
            0.0  # Mismatched
        )

        # IPS estimator
        weighted_outcomes = weights * outcome
        value = weighted_outcomes.mean()

        # Standard error (with Horvitz-Thompson variance)
        n = len(outcome)
        variance = np.var(weighted_outcomes, ddof=1) / n
        std_error = np.sqrt(variance)

        # Confidence interval
        z_score = stats.norm.ppf(1 - alpha / 2)
        ci_lower = value - z_score * std_error
        ci_upper = value + z_score * std_error

        # Effective sample size
        ess = (weights.sum() ** 2) / (weights ** 2).sum() if weights.sum() > 0 else 0

        return OPEResult(
            method="ips",
            value=value,
            std_error=std_error,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            n_samples=n,
            effective_sample_size=ess
        )

    def _evaluate_snips(self, new_policy: np.ndarray, alpha: float) -> OPEResult:
        """
        Self-Normalized IPS (SNIPS)

        V(π) = Σ[Y * w] / Σ[w]

        More stable than IPS for small samples

        Args:
            new_policy: New treatment assignments
            alpha: Significance level

        Returns:
            OPEResult
        """
        logged_treatment = self.df[self.treatment_col].values
        outcome = self.df["_profit"].values
        propensity = self.df["_propensity"].values

        # Importance weights
        weights = np.where(
            logged_treatment == new_policy,
            1.0 / (propensity + 1e-10),
            0.0
        )

        # SNIPS estimator
        value = (weights * outcome).sum() / (weights.sum() + 1e-10)

        # Standard error (delta method)
        n = len(outcome)
        w_sum = weights.sum()
        wy_sum = (weights * outcome).sum()

        # Variance using delta method
        residuals = weights * (outcome - value)
        variance = np.var(residuals, ddof=1) / (n * (w_sum / n) ** 2)
        std_error = np.sqrt(variance)

        # Confidence interval
        z_score = stats.norm.ppf(1 - alpha / 2)
        ci_lower = value - z_score * std_error
        ci_upper = value + z_score * std_error

        # Effective sample size
        ess = (w_sum ** 2) / ((weights ** 2).sum() + 1e-10)

        return OPEResult(
            method="snips",
            value=value,
            std_error=std_error,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            n_samples=n,
            effective_sample_size=ess
        )

    def _evaluate_dr(self, new_policy: np.ndarray, alpha: float) -> OPEResult:
        """
        Doubly Robust (DR) Estimator

        V(π) = E[μ(x,π(x))] + E[(Y - μ(x,a)) * π(a) / π₀(a)]

        Combines outcome modeling with propensity weighting

        Args:
            new_policy: New treatment assignments
            alpha: Significance level

        Returns:
            OPEResult
        """
        # Estimate outcome models μ(x,a) for a=0,1
        # For simplicity, use sample means (in production, use ML models)
        outcome = self.df["_profit"].values
        logged_treatment = self.df[self.treatment_col].values
        propensity = self.df["_propensity"].values

        # Outcome models (conditional expectations)
        mu_0 = outcome[logged_treatment == 0].mean() if (logged_treatment == 0).any() else 0
        mu_1 = outcome[logged_treatment == 1].mean() if (logged_treatment == 1).any() else 0

        # DR estimator components
        # 1. Outcome model prediction
        mu = np.where(new_policy == 1, mu_1, mu_0)

        # 2. Propensity-weighted residual
        weights = np.where(
            logged_treatment == new_policy,
            1.0 / (propensity + 1e-10),
            0.0
        )
        residuals = outcome - np.where(logged_treatment == 1, mu_1, mu_0)
        correction = weights * residuals

        # DR estimate
        dr_values = mu + correction
        value = dr_values.mean()

        # Standard error
        n = len(outcome)
        variance = np.var(dr_values, ddof=1) / n
        std_error = np.sqrt(variance)

        # Confidence interval
        z_score = stats.norm.ppf(1 - alpha / 2)
        ci_lower = value - z_score * std_error
        ci_upper = value + z_score * std_error

        # Effective sample size
        ess = (weights.sum() ** 2) / ((weights ** 2).sum() + 1e-10) if weights.sum() > 0 else n

        return OPEResult(
            method="dr",
            value=value,
            std_error=std_error,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            n_samples=n,
            effective_sample_size=ess
        )

    def evaluate_coverage(
        self,
        coverage: float,
        score_col: Optional[str] = None,
        method: str = "dr"
    ) -> OPEResult:
        """
        Evaluate policy with given coverage (top k%)

        Args:
            coverage: Coverage rate (0-1)
            score_col: Score column for ranking (if None, use propensity)
            method: OPE method

        Returns:
            OPEResult
        """
        if score_col and score_col in self.df.columns:
            scores = self.df[score_col].values
        else:
            scores = self.df["_propensity"].values

        # Top k% policy
        k = int(len(scores) * coverage)
        top_k_idx = np.argsort(scores)[-k:]

        new_policy = np.zeros(len(scores), dtype=int)
        new_policy[top_k_idx] = 1

        return self.evaluate_policy(new_policy, method=method)

    def sweep_coverage(
        self,
        coverage_range: List[float],
        score_col: Optional[str] = None,
        method: str = "dr"
    ) -> pd.DataFrame:
        """
        Sweep coverage rates and evaluate policy value

        Args:
            coverage_range: List of coverage rates (0-1)
            score_col: Score column for ranking
            method: OPE method

        Returns:
            DataFrame with coverage, value, ci_lower, ci_upper
        """
        results = []

        for cov in coverage_range:
            result = self.evaluate_coverage(cov, score_col, method)
            results.append({
                "coverage": cov,
                "value": result.value,
                "std_error": result.std_error,
                "ci_lower": result.ci_lower,
                "ci_upper": result.ci_upper,
                "ess": result.effective_sample_size
            })

        return pd.DataFrame(results)


def evaluate_scenario_ope(
    df: pd.DataFrame,
    scenario_spec: Dict,
    mapping: Dict[str, str],
    method: str = "dr"
) -> Dict:
    """
    Evaluate ScenarioSpec using OPE

    Args:
        df: Logged data
        scenario_spec: ScenarioSpec dictionary
        mapping: Column mapping
        method: OPE method

    Returns:
        Dictionary with OPE results
    """
    # Extract columns
    treatment_col = mapping.get("treatment", "treatment")
    outcome_col = mapping.get("y", "y")
    propensity_col = mapping.get("log_propensity", "log_propensity")
    cost_col = mapping.get("cost")

    # Extract value
    value_per_y = scenario_spec.get("value", {}).get("value_per_y", 1.0)

    # Create evaluator
    evaluator = OffPolicyEvaluator(
        df=df,
        treatment_col=treatment_col,
        outcome_col=outcome_col,
        propensity_col=propensity_col,
        cost_col=cost_col,
        value_per_y=value_per_y
    )

    # Extract intervention parameters
    intervention = scenario_spec.get("intervention", {})
    coverage = intervention.get("coverage", 0.3)

    # Evaluate policy
    result = evaluator.evaluate_coverage(coverage=coverage, method=method)

    # Compute baseline (observed policy value)
    observed_policy = df[treatment_col].values
    baseline = evaluator.evaluate_policy(observed_policy, method=method)

    return {
        "method": method,
        "baseline": {
            "value": baseline.value,
            "ci": [baseline.ci_lower, baseline.ci_upper],
            "std_error": baseline.std_error
        },
        "scenario": {
            "value": result.value,
            "ci": [result.ci_lower, result.ci_upper],
            "std_error": result.std_error,
            "ess": result.effective_sample_size
        },
        "delta": {
            "value": result.value - baseline.value,
            "ci": [
                result.ci_lower - baseline.ci_upper,  # Conservative
                result.ci_upper - baseline.ci_lower
            ]
        }
    }
