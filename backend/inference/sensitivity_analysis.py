"""
Sensitivity Analysis for Hidden Confounding
============================================

Implements multiple robust methods to assess the impact of unobserved confounding:

1. **Rosenbaum Bounds** (Rosenbaum 2002)
   - Assess how strong confounding would need to be to overturn conclusions
   - Gamma parameter: degree of hidden bias

2. **Oster's Delta Method** (Oster 2019)
   - Compares controlled vs uncontrolled estimates
   - Delta: proportion of selection on unobservables vs observables

3. **E-values** (VanderWeele & Ding 2017)
   - Minimum strength of association required to explain away effect
   - Intuitive risk ratio scale

4. **Partial Identification** (Manski bounds)
   - Worst-case bounds without assumptions

References:
- Rosenbaum, P. R. (2002). Observational Studies. Springer.
- Oster, E. (2019). "Unobservable Selection and Coefficient Stability." JPE.
- VanderWeele, T. J., & Ding, P. (2017). "Sensitivity Analysis in Observational Research." AIM.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from scipy import stats
from scipy.optimize import brentq
import logging

logger = logging.getLogger(__name__)


@dataclass
class SensitivityResult:
    """Sensitivity analysis results"""
    method: str
    metric_value: float  # Gamma, Delta, or E-value
    interpretation: str
    robust: bool  # True if result survives sensitivity analysis
    details: Dict[str, Any]


class RosenbaumBounds:
    """
    Rosenbaum's Sensitivity Analysis for Hidden Bias

    Assesses how large hidden bias (Gamma) would need to be to change conclusions.
    Gamma = 1: no hidden bias
    Gamma = 2: matched pairs could differ by 2x in odds of treatment
    """

    def __init__(self, alpha: float = 0.05):
        self.alpha = alpha

    def compute(
        self,
        y_treated: np.ndarray,
        y_control: np.ndarray,
        gamma_range: np.ndarray = np.arange(1.0, 5.0, 0.1)
    ) -> SensitivityResult:
        """
        Compute Rosenbaum bounds for matched pairs

        Args:
            y_treated: Outcomes for treated units
            y_control: Outcomes for control units (matched)
            gamma_range: Range of Gamma values to test

        Returns:
            SensitivityResult with critical Gamma value
        """
        if len(y_treated) != len(y_control):
            raise ValueError("Treated and control samples must have same size (matched pairs)")

        # Compute signed ranks of differences
        diffs = y_treated - y_control
        abs_diffs = np.abs(diffs)
        ranks = stats.rankdata(abs_diffs)
        signed_ranks = ranks * np.sign(diffs)

        # Wilcoxon signed rank statistic
        T_plus = np.sum(signed_ranks[signed_ranks > 0])
        n = len(diffs)

        # Find critical Gamma
        critical_gamma = None
        p_values = []

        for gamma in gamma_range:
            # Upper bound p-value under Gamma-level bias
            p_upper = self._rosenbaum_p_upper(T_plus, n, gamma)
            p_values.append(p_upper)

            if p_upper > self.alpha and critical_gamma is None:
                critical_gamma = gamma

        if critical_gamma is None:
            critical_gamma = gamma_range[-1]
            robust = True
            interpretation = f"結果はΓ={gamma_range[-1]:.1f}まで頑健（非常に強い）"
        else:
            robust = critical_gamma > 2.0
            interpretation = f"結果はΓ={critical_gamma:.2f}で覆る可能性あり（{'頑健' if robust else '脆弱'}）"

        return SensitivityResult(
            method="rosenbaum_bounds",
            metric_value=critical_gamma,
            interpretation=interpretation,
            robust=robust,
            details={
                "gamma_range": gamma_range.tolist(),
                "p_values": p_values,
                "critical_gamma": critical_gamma,
                "wilcoxon_statistic": float(T_plus),
                "n_pairs": n,
                "mean_diff": float(np.mean(diffs)),
                "alpha": self.alpha
            }
        )

    def _rosenbaum_p_upper(self, T_plus: float, n: int, gamma: float) -> float:
        """Compute upper bound p-value under Gamma-level bias"""
        # Expectation and variance under worst-case scenario
        p_plus = gamma / (1 + gamma)

        E_T = n * (n + 1) / 4 * (1 + p_plus)
        Var_T = n * (n + 1) * (2 * n + 1) / 24 * p_plus * (1 - p_plus)

        # Normal approximation
        z = (T_plus - E_T) / np.sqrt(Var_T)
        p_upper = 1 - stats.norm.cdf(z)

        return p_upper


class OsterDelta:
    """
    Oster's Delta Method for Coefficient Stability

    Compares:
    - Uncontrolled estimate (short regression)
    - Controlled estimate (long regression with covariates)

    Delta = how much stronger selection on unobservables vs observables
            would need to be to drive estimate to zero
    """

    def compute(
        self,
        y: np.ndarray,
        treatment: np.ndarray,
        X_short: Optional[np.ndarray] = None,  # Basic controls
        X_long: Optional[np.ndarray] = None,   # + additional controls
        R_max: float = 1.0  # Maximum possible R²
    ) -> SensitivityResult:
        """
        Compute Oster's delta

        Args:
            y: Outcome variable
            treatment: Treatment indicator
            X_short: Basic controls (can be None for uncontrolled)
            X_long: Extended controls (required)
            R_max: Maximum R² if all confounders observed (default 1.0)

        Returns:
            SensitivityResult with delta value
        """
        from sklearn.linear_model import LinearRegression

        # Short regression (uncontrolled or basic)
        if X_short is None:
            X_short_reg = treatment.reshape(-1, 1)
        else:
            X_short_reg = np.column_stack([treatment, X_short])

        model_short = LinearRegression()
        model_short.fit(X_short_reg, y)
        beta_short = model_short.coef_[0]  # Treatment coefficient
        R2_short = model_short.score(X_short_reg, y)

        # Long regression (controlled)
        if X_long is None:
            raise ValueError("X_long (controlled covariates) required for Oster method")

        X_long_reg = np.column_stack([treatment, X_long])
        model_long = LinearRegression()
        model_long.fit(X_long_reg, y)
        beta_long = model_long.coef_[0]  # Treatment coefficient
        R2_long = model_long.score(X_long_reg, y)

        # Compute delta
        if abs(beta_short - beta_long) < 1e-10:
            delta = np.inf
            interpretation = "係数が完全に安定（δ=∞）→ 非常に頑健"
            robust = True
        else:
            delta = (beta_long * (R2_short - R_max)) / ((beta_short - beta_long) * (R2_long - R2_short))

            # Interpretation
            if abs(delta) > 1.0:
                interpretation = f"δ={delta:.2f}>1: 未観測交絡が観測交絡より{abs(delta):.1f}倍強くても結果維持（頑健）"
                robust = True
            else:
                interpretation = f"δ={delta:.2f}<1: 未観測交絡が観測交絡と同程度で結果が覆る（脆弱）"
                robust = False

        return SensitivityResult(
            method="oster_delta",
            metric_value=float(delta) if delta != np.inf else 999.0,
            interpretation=interpretation,
            robust=robust,
            details={
                "beta_short": float(beta_short),
                "beta_long": float(beta_long),
                "R2_short": float(R2_short),
                "R2_long": float(R2_long),
                "R2_max": R_max,
                "delta": float(delta) if delta != np.inf else 999.0
            }
        )


class EValue:
    """
    E-value for Sensitivity Analysis

    E-value = minimum strength of association (risk ratio scale) that
              unmeasured confounder would need with both treatment and outcome
              to explain away observed effect

    Interpretation:
    - E-value = 1.5: Weak confounding could explain effect
    - E-value = 3.0: Moderate-strong confounding needed
    - E-value = 5.0+: Very strong confounding needed (robust)
    """

    def compute(
        self,
        point_estimate: float,
        ci_lower: Optional[float] = None,
        outcome_type: str = "continuous"  # or "binary"
    ) -> SensitivityResult:
        """
        Compute E-value

        Args:
            point_estimate: Observed effect (risk ratio, OR, or standardized mean diff)
            ci_lower: Lower confidence bound (for robustness check)
            outcome_type: "continuous" or "binary"

        Returns:
            SensitivityResult with E-value
        """
        if outcome_type == "continuous":
            # Convert to approximate risk ratio
            rr = np.exp(0.91 * point_estimate)
        else:
            # Already risk ratio or OR
            rr = point_estimate

        # Compute E-value
        if rr >= 1:
            evalue = rr + np.sqrt(rr * (rr - 1))
        else:
            # For protective effects (RR < 1)
            evalue = 1 / rr + np.sqrt(1 / rr * (1 / rr - 1))

        # E-value for CI lower bound
        if ci_lower is not None:
            if outcome_type == "continuous":
                rr_lower = np.exp(0.91 * ci_lower)
            else:
                rr_lower = ci_lower

            if rr_lower >= 1:
                evalue_ci = rr_lower + np.sqrt(rr_lower * (rr_lower - 1))
            else:
                evalue_ci = 1 / rr_lower + np.sqrt(1 / rr_lower * (1 / rr_lower - 1))
        else:
            evalue_ci = None

        # Interpretation
        if evalue >= 5.0:
            interpretation = f"E-value={evalue:.2f}: 極めて強い交絡が必要（非常に頑健）"
            robust = True
        elif evalue >= 3.0:
            interpretation = f"E-value={evalue:.2f}: 中〜強い交絡が必要（頑健）"
            robust = True
        elif evalue >= 2.0:
            interpretation = f"E-value={evalue:.2f}: 中程度の交絡で説明可能（やや頑健）"
            robust = False
        else:
            interpretation = f"E-value={evalue:.2f}: 弱い交絡で説明可能（脆弱）"
            robust = False

        return SensitivityResult(
            method="evalue",
            metric_value=float(evalue),
            interpretation=interpretation,
            robust=robust,
            details={
                "evalue_point": float(evalue),
                "evalue_ci": float(evalue_ci) if evalue_ci else None,
                "risk_ratio": float(rr),
                "original_estimate": float(point_estimate)
            }
        )


class ManskiBounds:
    """
    Manski Partial Identification Bounds

    Worst-case bounds without untestable assumptions.
    """

    def compute(
        self,
        y: np.ndarray,
        treatment: np.ndarray,
        outcome_bounds: Tuple[float, float] = (0, 1)
    ) -> SensitivityResult:
        """
        Compute Manski bounds on ATE

        Args:
            y: Observed outcomes
            treatment: Treatment indicator
            outcome_bounds: (min, max) possible outcome values

        Returns:
            SensitivityResult with bound interval
        """
        y_min, y_max = outcome_bounds

        # Observed averages
        y1_obs = y[treatment == 1].mean()
        y0_obs = y[treatment == 0].mean()

        p_treated = treatment.mean()

        # Worst-case bounds
        # Upper bound: assume missing y(0) for treated = y_max
        ate_upper = y1_obs - (p_treated * y_min + (1 - p_treated) * y0_obs)

        # Lower bound: assume missing y(0) for treated = y_min
        ate_lower = y1_obs - (p_treated * y_max + (1 - p_treated) * y0_obs)

        # Check if bounds exclude zero
        robust = (ate_lower > 0 and ate_upper > 0) or (ate_lower < 0 and ate_upper < 0)

        width = ate_upper - ate_lower

        interpretation = f"ATE ∈ [{ate_lower:.3f}, {ate_upper:.3f}] (幅={width:.3f})"
        if robust:
            interpretation += " ゼロを含まない（頑健）"
        else:
            interpretation += " ゼロを含む（不確実）"

        return SensitivityResult(
            method="manski_bounds",
            metric_value=width,
            interpretation=interpretation,
            robust=robust,
            details={
                "ate_lower": float(ate_lower),
                "ate_upper": float(ate_upper),
                "width": float(width),
                "y1_observed": float(y1_obs),
                "y0_observed": float(y0_obs)
            }
        )


class SensitivityAnalyzer:
    """Main interface for all sensitivity analysis methods"""

    def __init__(self, alpha: float = 0.05):
        self.rosenbaum = RosenbaumBounds(alpha=alpha)
        self.oster = OsterDelta()
        self.evalue = EValue()
        self.manski = ManskiBounds()

    def analyze(
        self,
        method: str,
        **kwargs
    ) -> SensitivityResult:
        """
        Run sensitivity analysis

        Args:
            method: "rosenbaum", "oster", "evalue", or "manski"
            **kwargs: Method-specific parameters

        Returns:
            SensitivityResult
        """
        if method == "rosenbaum":
            return self.rosenbaum.compute(**kwargs)
        elif method == "oster":
            return self.oster.compute(**kwargs)
        elif method == "evalue":
            return self.evalue.compute(**kwargs)
        elif method == "manski":
            return self.manski.compute(**kwargs)
        else:
            raise ValueError(f"Unknown method: {method}")

    def comprehensive_analysis(
        self,
        y: np.ndarray,
        treatment: np.ndarray,
        X: Optional[np.ndarray] = None,
        point_estimate: Optional[float] = None,
        ci_lower: Optional[float] = None,
        matched_pairs: bool = False,
        y_control: Optional[np.ndarray] = None
    ) -> Dict[str, SensitivityResult]:
        """
        Run all applicable sensitivity analyses

        Returns:
            Dictionary of results by method
        """
        results = {}

        # E-value (always computable if point estimate provided)
        if point_estimate is not None:
            try:
                results["evalue"] = self.evalue.compute(
                    point_estimate=point_estimate,
                    ci_lower=ci_lower
                )
            except Exception as e:
                logger.error(f"E-value failed: {e}")

        # Rosenbaum bounds (requires matched pairs)
        if matched_pairs and y_control is not None:
            try:
                y_treated = y[treatment == 1]
                results["rosenbaum"] = self.rosenbaum.compute(
                    y_treated=y_treated,
                    y_control=y_control
                )
            except Exception as e:
                logger.error(f"Rosenbaum bounds failed: {e}")

        # Oster's delta (requires covariates)
        if X is not None:
            try:
                # Split X into "short" (first half) and "long" (all)
                n_half = X.shape[1] // 2
                if n_half > 0:
                    X_short = X[:, :n_half]
                    X_long = X
                    results["oster"] = self.oster.compute(
                        y=y,
                        treatment=treatment,
                        X_short=X_short,
                        X_long=X_long
                    )
            except Exception as e:
                logger.error(f"Oster delta failed: {e}")

        # Manski bounds (always computable)
        try:
            results["manski"] = self.manski.compute(
                y=y,
                treatment=treatment
            )
        except Exception as e:
            logger.error(f"Manski bounds failed: {e}")

        return results
