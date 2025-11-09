"""
g-Computation (Parametric g-formula) - NASA/Google Standard

Purpose: Precise counterfactual policy evaluation using outcome modeling
Methods:
- Parametric g-formula
- ML-based outcome models (Random Forest, Gradient Boosting)
- Bootstrap confidence intervals

Reference: Robins (1986), "A new approach to causal inference in mortality studies"
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import cross_val_predict


@dataclass
class GComputationResult:
    """g-Computation evaluation result"""
    method: str  # "linear", "rf", "gbm"
    value: float  # E[Y(π)]
    std_error: float
    ci_lower: float
    ci_upper: float
    n_samples: int
    r_squared: float  # Model fit quality


class GComputationEvaluator:
    """
    g-Computation Evaluator

    Estimates counterfactual outcomes using parametric outcome models
    """

    def __init__(
        self,
        df: pd.DataFrame,
        treatment_col: str = "treatment",
        outcome_col: str = "y",
        feature_cols: Optional[List[str]] = None,
        cost_col: Optional[str] = None,
        value_per_y: float = 1.0
    ):
        """
        Args:
            df: Training data
            treatment_col: Treatment column name
            outcome_col: Outcome column name
            feature_cols: Feature columns (if None, use all numeric except treatment/outcome)
            cost_col: Cost column (optional)
            value_per_y: Monetary value per outcome unit
        """
        self.df = df.copy()
        self.treatment_col = treatment_col
        self.outcome_col = outcome_col
        self.cost_col = cost_col
        self.value_per_y = value_per_y

        # Auto-detect features if not provided
        if feature_cols is None:
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            exclude = {treatment_col, outcome_col}
            if cost_col:
                exclude.add(cost_col)
            self.feature_cols = [c for c in numeric_cols if c not in exclude and not c.startswith("_")]
        else:
            self.feature_cols = feature_cols

        # Compute profit
        if cost_col and cost_col in df.columns:
            self.df["_profit"] = df[outcome_col] * value_per_y - df[cost_col]
        else:
            self.df["_profit"] = df[outcome_col] * value_per_y

    def fit_outcome_model(
        self,
        method: str = "rf",
        **kwargs
    ) -> None:
        """
        Fit outcome model E[Y|X,A]

        Args:
            method: Model type - "linear", "rf", "gbm"
            **kwargs: Model-specific parameters
        """
        X = pd.concat([
            self.df[self.feature_cols],
            self.df[[self.treatment_col]]
        ], axis=1).fillna(0)
        y = self.df["_profit"].values

        if method == "linear":
            self.model = Ridge(alpha=kwargs.get("alpha", 1.0))
        elif method == "rf":
            self.model = RandomForestRegressor(
                n_estimators=kwargs.get("n_estimators", 100),
                max_depth=kwargs.get("max_depth", 10),
                min_samples_leaf=kwargs.get("min_samples_leaf", 20),
                random_state=kwargs.get("random_state", 42)
            )
        elif method == "gbm":
            self.model = GradientBoostingRegressor(
                n_estimators=kwargs.get("n_estimators", 100),
                max_depth=kwargs.get("max_depth", 5),
                learning_rate=kwargs.get("learning_rate", 0.1),
                random_state=kwargs.get("random_state", 42)
            )
        else:
            raise ValueError(f"Unknown method: {method}")

        self.model.fit(X, y)
        self.method = method

        # Compute R² using cross-validation
        y_pred_cv = cross_val_predict(self.model, X, y, cv=5)
        self.r_squared = 1 - ((y - y_pred_cv) ** 2).sum() / ((y - y.mean()) ** 2).sum()

    def predict_counterfactual(
        self,
        df: pd.DataFrame,
        treatment: int
    ) -> np.ndarray:
        """
        Predict counterfactual outcomes E[Y|X,A=treatment]

        Args:
            df: Data to predict on
            treatment: Treatment value (0 or 1)

        Returns:
            Array of predicted outcomes
        """
        X = pd.concat([
            df[self.feature_cols],
            pd.DataFrame({self.treatment_col: [treatment] * len(df)})
        ], axis=1).fillna(0)

        return self.model.predict(X)

    def evaluate_policy(
        self,
        new_policy: np.ndarray,
        method: str = "rf",
        n_bootstrap: int = 100,
        alpha: float = 0.05
    ) -> GComputationResult:
        """
        Evaluate policy using g-computation

        Args:
            new_policy: New treatment assignments (0/1 array)
            method: Model type
            n_bootstrap: Number of bootstrap samples for CI
            alpha: Significance level

        Returns:
            GComputationResult
        """
        # Fit outcome model
        self.fit_outcome_model(method=method)

        # Predict counterfactual outcomes under new policy
        y_cf = []
        for i, treatment in enumerate(new_policy):
            df_i = self.df.iloc[[i]]
            y_cf.append(self.predict_counterfactual(df_i, treatment)[0])

        y_cf = np.array(y_cf)
        value = y_cf.mean()

        # Bootstrap confidence interval
        n = len(y_cf)
        bootstrap_values = []

        rng = np.random.RandomState(42)
        for _ in range(n_bootstrap):
            idx = rng.choice(n, size=n, replace=True)
            bootstrap_values.append(y_cf[idx].mean())

        bootstrap_values = np.array(bootstrap_values)
        ci_lower = np.percentile(bootstrap_values, alpha / 2 * 100)
        ci_upper = np.percentile(bootstrap_values, (1 - alpha / 2) * 100)
        std_error = bootstrap_values.std()

        return GComputationResult(
            method=method,
            value=value,
            std_error=std_error,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            n_samples=n,
            r_squared=self.r_squared
        )

    def evaluate_coverage(
        self,
        coverage: float,
        score_col: Optional[str] = None,
        method: str = "rf",
        n_bootstrap: int = 100
    ) -> GComputationResult:
        """
        Evaluate policy with given coverage (top k%)

        Args:
            coverage: Coverage rate (0-1)
            score_col: Score column for ranking (if None, use predicted treatment effect)
            method: Model type
            n_bootstrap: Number of bootstrap samples

        Returns:
            GComputationResult
        """
        # Fit outcome model
        self.fit_outcome_model(method=method)

        # Compute scores
        if score_col and score_col in self.df.columns:
            scores = self.df[score_col].values
        else:
            # Use predicted treatment effect: E[Y|X,A=1] - E[Y|X,A=0]
            y1 = self.predict_counterfactual(self.df, treatment=1)
            y0 = self.predict_counterfactual(self.df, treatment=0)
            scores = y1 - y0

        # Top k% policy
        k = int(len(scores) * coverage)
        top_k_idx = np.argsort(scores)[-k:]

        new_policy = np.zeros(len(scores), dtype=int)
        new_policy[top_k_idx] = 1

        return self.evaluate_policy(new_policy, method=method, n_bootstrap=n_bootstrap)

    def compare_ope_gcomp(
        self,
        new_policy: np.ndarray,
        ope_result: Dict,
        method: str = "rf"
    ) -> Dict:
        """
        Compare OPE and g-computation results

        Args:
            new_policy: New treatment assignments
            ope_result: OPE evaluation result
            method: g-computation method

        Returns:
            Comparison dictionary with consistency metrics
        """
        gcomp_result = self.evaluate_policy(new_policy, method=method)

        # Compute rank correlation if multiple policies
        ope_value = ope_result.get("scenario", {}).get("value", 0)
        gcomp_value = gcomp_result.value

        # Check consistency
        ope_ci = ope_result.get("scenario", {}).get("ci", [0, 0])
        gcomp_ci = [gcomp_result.ci_lower, gcomp_result.ci_upper]

        # Check if CIs overlap
        ci_overlap = not (ope_ci[1] < gcomp_ci[0] or gcomp_ci[1] < ope_ci[0])

        # Relative difference
        relative_diff = abs(ope_value - gcomp_value) / (abs(ope_value) + 1e-10)

        return {
            "ope": {
                "value": ope_value,
                "ci": ope_ci
            },
            "gcomp": {
                "value": gcomp_value,
                "ci": gcomp_ci,
                "r_squared": gcomp_result.r_squared
            },
            "consistency": {
                "ci_overlap": ci_overlap,
                "relative_difference": relative_diff,
                "agreement": "high" if relative_diff < 0.1 and ci_overlap else "moderate" if relative_diff < 0.2 else "low"
            }
        }


def evaluate_scenario_gcomp(
    df: pd.DataFrame,
    scenario_spec: Dict,
    mapping: Dict[str, str],
    method: str = "rf",
    n_bootstrap: int = 100
) -> Dict:
    """
    Evaluate ScenarioSpec using g-computation

    Args:
        df: Training data
        scenario_spec: ScenarioSpec dictionary
        mapping: Column mapping
        method: Model type
        n_bootstrap: Number of bootstrap samples

    Returns:
        Dictionary with g-computation results
    """
    # Extract columns
    treatment_col = mapping.get("treatment", "treatment")
    outcome_col = mapping.get("y", "y")
    cost_col = mapping.get("cost")

    # Extract value
    value_per_y = scenario_spec.get("value", {}).get("value_per_y", 1.0)

    # Get feature columns (X_*)
    feature_cols = [c for c in df.columns if c.startswith("X_")]

    # Create evaluator
    evaluator = GComputationEvaluator(
        df=df,
        treatment_col=treatment_col,
        outcome_col=outcome_col,
        feature_cols=feature_cols if feature_cols else None,
        cost_col=cost_col,
        value_per_y=value_per_y
    )

    # Extract intervention parameters
    intervention = scenario_spec.get("intervention", {})
    coverage = intervention.get("coverage", 0.3)

    # Evaluate policy
    result = evaluator.evaluate_coverage(
        coverage=coverage,
        method=method,
        n_bootstrap=n_bootstrap
    )

    # Compute baseline (observed policy value)
    observed_policy = df[treatment_col].values
    baseline = evaluator.evaluate_policy(
        observed_policy,
        method=method,
        n_bootstrap=n_bootstrap
    )

    return {
        "method": f"gcomp_{method}",
        "baseline": {
            "value": baseline.value,
            "ci": [baseline.ci_lower, baseline.ci_upper],
            "std_error": baseline.std_error,
            "r_squared": baseline.r_squared
        },
        "scenario": {
            "value": result.value,
            "ci": [result.ci_lower, result.ci_upper],
            "std_error": result.std_error,
            "r_squared": result.r_squared
        },
        "delta": {
            "value": result.value - baseline.value,
            "ci": [
                result.ci_lower - baseline.ci_upper,  # Conservative
                result.ci_upper - baseline.ci_lower
            ]
        }
    }
