"""
Regression Discontinuity Design (RDD)
======================================

Exploits discontinuities in treatment assignment at a threshold.

**Core Assumption**:
Units just above/below cutoff are similar (as-if randomized).

**Types**:
1. **Sharp RD**: Treatment jumps deterministically at cutoff
   - D = 1{X ≥ c}
   - τ = lim[x→c+] E[Y|X=x] - lim[x→c-] E[Y|X=x]

2. **Fuzzy RD**: Treatment probability jumps (IV-like)
   - P(D=1|X) discontinuous at c
   - τ = [jump in Y] / [jump in D]

**Key Methods**:
- Local polynomial regression (most common: local linear)
- Optimal bandwidth selection (IK, CV)
- Robustness checks (placebo cutoffs, covariates balance)

References:
- Lee & Lemieux (2010). "Regression Discontinuity Designs in Economics." JEL.
- Imbens & Kalyanaraman (2012). "Optimal Bandwidth Choice." REStat.
- Calonico, Cattaneo, & Titiunik (2014). "Robust Nonparametric Confidence Intervals." Econometrica.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass
from scipy import stats
from scipy.optimize import minimize_scalar
from sklearn.linear_model import LinearRegression
import logging

logger = logging.getLogger(__name__)


@dataclass
class RDResult:
    """Regression Discontinuity estimation result"""
    ate: float  # Local treatment effect at cutoff
    se: float
    ci_lower: float
    ci_upper: float
    bandwidth: float
    n_left: int  # Sample size below cutoff
    n_right: int  # Sample size above cutoff
    rd_type: str  # "sharp" or "fuzzy"
    diagnostics: Dict[str, Any]


class SharpRD:
    """
    Sharp Regression Discontinuity

    Treatment assignment: D = 1{X ≥ c}
    """

    def __init__(
        self,
        cutoff: float = 0.0,
        kernel: str = "triangular",  # "triangular", "uniform", or "epanechnikov"
        alpha: float = 0.05
    ):
        self.cutoff = cutoff
        self.kernel = kernel
        self.alpha = alpha

    def estimate(
        self,
        X: np.ndarray,  # Running variable
        y: np.ndarray,  # Outcome
        bandwidth: Optional[float] = None,
        bw_method: str = "ik"  # "ik" (Imbens-Kalyanaraman) or "cv" (cross-validation)
    ) -> RDResult:
        """
        Estimate sharp RD effect

        Args:
            X: Running variable (forcing variable)
            y: Outcome
            bandwidth: Bandwidth (if None, select optimally)
            bw_method: "ik" or "cv"

        Returns:
            RDResult
        """
        # Center running variable at cutoff
        X_centered = X - self.cutoff

        # Select bandwidth
        if bandwidth is None:
            bandwidth = self._select_bandwidth(X_centered, y, method=bw_method)

        # Restrict to bandwidth window
        in_window = np.abs(X_centered) <= bandwidth
        X_win = X_centered[in_window]
        y_win = y[in_window]

        # Split into left (below cutoff) and right (above cutoff)
        left_mask = X_win < 0
        right_mask = X_win >= 0

        X_left = X_win[left_mask]
        y_left = y_win[left_mask]

        X_right = X_win[right_mask]
        y_right = y_win[right_mask]

        # Local linear regression on each side
        # Left: E[Y|X] = α0- + α1- * X
        # Right: E[Y|X] = α0+ + α1+ * X
        # RD effect = α0+ - α0-

        weights_left = self._kernel_weights(X_left, bandwidth)
        weights_right = self._kernel_weights(X_right, bandwidth)

        alpha0_left, alpha1_left = self._weighted_regression(X_left, y_left, weights_left)
        alpha0_right, alpha1_right = self._weighted_regression(X_right, y_right, weights_right)

        # RD estimate
        ate = alpha0_right - alpha0_left

        # Standard error (heteroskedasticity-robust)
        residuals_left = y_left - (alpha0_left + alpha1_left * X_left)
        residuals_right = y_right - (alpha0_right + alpha1_right * X_right)

        var_left = np.sum(weights_left**2 * residuals_left**2) / np.sum(weights_left)**2
        var_right = np.sum(weights_right**2 * residuals_right**2) / np.sum(weights_right)**2

        se = np.sqrt(var_left + var_right)

        # Confidence interval
        t_crit = stats.t.ppf(1 - self.alpha / 2, len(X_win) - 4)
        ci_lower = ate - t_crit * se
        ci_upper = ate + t_crit * se

        # Diagnostics
        diagnostics = {
            "intercept_left": float(alpha0_left),
            "slope_left": float(alpha1_left),
            "intercept_right": float(alpha0_right),
            "slope_right": float(alpha1_right),
            "bandwidth_method": bw_method,
            "kernel": self.kernel
        }

        return RDResult(
            ate=float(ate),
            se=float(se),
            ci_lower=float(ci_lower),
            ci_upper=float(ci_upper),
            bandwidth=float(bandwidth),
            n_left=int(np.sum(left_mask)),
            n_right=int(np.sum(right_mask)),
            rd_type="sharp",
            diagnostics=diagnostics
        )

    def _weighted_regression(
        self,
        X: np.ndarray,
        y: np.ndarray,
        weights: np.ndarray
    ) -> Tuple[float, float]:
        """Weighted linear regression: y = α0 + α1 * X"""
        if len(X) == 0:
            return 0.0, 0.0

        # Weighted least squares
        X_mat = np.column_stack([np.ones(len(X)), X])
        W = np.diag(weights)

        try:
            beta = np.linalg.inv(X_mat.T @ W @ X_mat) @ (X_mat.T @ W @ y)
            return beta[0], beta[1]
        except np.linalg.LinAlgError:
            # Fallback to unweighted
            beta = np.linalg.lstsq(X_mat, y, rcond=None)[0]
            return beta[0], beta[1]

    def _kernel_weights(self, X: np.ndarray, bandwidth: float) -> np.ndarray:
        """Compute kernel weights"""
        u = X / bandwidth

        if self.kernel == "triangular":
            weights = np.maximum(0, 1 - np.abs(u))
        elif self.kernel == "epanechnikov":
            weights = np.maximum(0, 0.75 * (1 - u**2))
        elif self.kernel == "uniform":
            weights = np.ones(len(X))
        else:
            raise ValueError(f"Unknown kernel: {self.kernel}")

        return weights

    def _select_bandwidth(
        self,
        X: np.ndarray,
        y: np.ndarray,
        method: str = "ik"
    ) -> float:
        """Select optimal bandwidth"""
        if method == "ik":
            return self._imbens_kalyanaraman_bandwidth(X, y)
        elif method == "cv":
            return self._cross_validation_bandwidth(X, y)
        else:
            raise ValueError(f"Unknown bandwidth method: {method}")

    def _imbens_kalyanaraman_bandwidth(self, X: np.ndarray, y: np.ndarray) -> float:
        """
        Imbens & Kalyanaraman (2012) optimal bandwidth

        Minimizes MSE of local linear estimator.
        """
        # Pilot bandwidth (rule of thumb)
        h_pilot = 1.06 * np.std(X) * len(X)**(-1/5)

        # Estimate second derivatives using pilot bandwidth
        left_mask = (X < 0) & (np.abs(X) <= h_pilot)
        right_mask = (X >= 0) & (np.abs(X) <= h_pilot)

        if np.sum(left_mask) < 3 or np.sum(right_mask) < 3:
            # Fallback
            return h_pilot

        # Fit quadratic on each side
        X_left = X[left_mask]
        y_left = y[left_mask]
        X_right = X[right_mask]
        y_right = y[right_mask]

        # Second derivative estimates
        m2_left = self._estimate_second_derivative(X_left, y_left)
        m2_right = self._estimate_second_derivative(X_right, y_right)
        m2 = (m2_left + m2_right) / 2

        # Variance estimates
        var_left = np.var(y_left)
        var_right = np.var(y_right)
        sigma2 = (var_left + var_right) / 2

        # IK formula
        n = len(X)
        C_K = 3.4375  # For triangular kernel

        h_ik = C_K * (sigma2 / (n * m2**2))**(1/5)

        # Bound bandwidth (avoid too large or too small)
        h_ik = np.clip(h_ik, 0.01 * np.std(X), 2 * np.std(X))

        return float(h_ik)

    def _estimate_second_derivative(self, X: np.ndarray, y: np.ndarray) -> float:
        """Estimate second derivative via quadratic fit"""
        if len(X) < 3:
            return 1.0  # Default

        X_mat = np.column_stack([np.ones(len(X)), X, X**2])
        try:
            beta = np.linalg.lstsq(X_mat, y, rcond=None)[0]
            m2 = 2 * beta[2]  # Second derivative of quadratic
            return abs(m2) + 1e-10  # Avoid zero
        except:
            return 1.0

    def _cross_validation_bandwidth(self, X: np.ndarray, y: np.ndarray) -> float:
        """Cross-validation bandwidth selection"""
        # Try range of bandwidths
        h_candidates = np.linspace(0.1 * np.std(X), 2 * np.std(X), 20)

        best_h = h_candidates[0]
        best_cv_score = np.inf

        for h in h_candidates:
            cv_score = self._leave_one_out_cv(X, y, h)
            if cv_score < best_cv_score:
                best_cv_score = cv_score
                best_h = h

        return float(best_h)

    def _leave_one_out_cv(self, X: np.ndarray, y: np.ndarray, bandwidth: float) -> float:
        """Leave-one-out cross-validation score"""
        n = len(X)
        errors = []

        for i in range(n):
            # Leave out observation i
            X_train = np.delete(X, i)
            y_train = np.delete(y, i)
            X_test = X[i]
            y_test = y[i]

            # Predict y_test using bandwidth
            in_window = np.abs(X_train) <= bandwidth
            if np.sum(in_window) < 2:
                continue

            X_win = X_train[in_window]
            y_win = y_train[in_window]

            if X_test < 0:
                mask = X_win < 0
            else:
                mask = X_win >= 0

            if np.sum(mask) < 2:
                continue

            weights = self._kernel_weights(X_win[mask] - X_test, bandwidth)
            alpha0, alpha1 = self._weighted_regression(X_win[mask] - X_test, y_win[mask], weights)

            y_pred = alpha0
            errors.append((y_test - y_pred)**2)

        return np.mean(errors) if len(errors) > 0 else np.inf


class FuzzyRD:
    """
    Fuzzy Regression Discontinuity

    Treatment probability (not assignment) discontinuous at cutoff.
    Uses IV approach: instrument = 1{X ≥ c}
    """

    def __init__(self, cutoff: float = 0.0, kernel: str = "triangular", alpha: float = 0.05):
        self.cutoff = cutoff
        self.kernel = kernel
        self.alpha = alpha
        self.sharp_rd = SharpRD(cutoff=cutoff, kernel=kernel, alpha=alpha)

    def estimate(
        self,
        X: np.ndarray,  # Running variable
        y: np.ndarray,  # Outcome
        treatment: np.ndarray,  # Actual treatment status
        bandwidth: Optional[float] = None,
        bw_method: str = "ik"
    ) -> RDResult:
        """
        Estimate fuzzy RD effect

        τ_FRD = [jump in Y] / [jump in D]

        Args:
            X: Running variable
            y: Outcome
            treatment: Actual treatment receipt
            bandwidth: Bandwidth
            bw_method: Bandwidth selection method

        Returns:
            RDResult
        """
        # Reduced form: effect of crossing cutoff on outcome
        reduced_form = self.sharp_rd.estimate(X, y, bandwidth, bw_method)

        # First stage: effect of crossing cutoff on treatment
        first_stage = self.sharp_rd.estimate(X, treatment, bandwidth, bw_method)

        # Fuzzy RD = reduced form / first stage
        if abs(first_stage.ate) < 1e-10:
            raise ValueError("First stage near zero - not a valid fuzzy RD design")

        ate_fuzzy = reduced_form.ate / first_stage.ate

        # Delta method for standard error
        # Var(Y/D) ≈ Var(Y)/E[D]^2 + Var(D)*E[Y]^2/E[D]^4 - 2*Cov(Y,D)*E[Y]/E[D]^3
        # Simplified: se_fuzzy ≈ sqrt((se_Y/D)^2 + (Y*se_D/D^2)^2)
        se_fuzzy = np.sqrt(
            (reduced_form.se / first_stage.ate)**2 +
            (reduced_form.ate * first_stage.se / first_stage.ate**2)**2
        )

        # Confidence interval
        t_crit = stats.t.ppf(1 - self.alpha / 2, reduced_form.n_left + reduced_form.n_right - 4)
        ci_lower = ate_fuzzy - t_crit * se_fuzzy
        ci_upper = ate_fuzzy + t_crit * se_fuzzy

        diagnostics = {
            "reduced_form_effect": float(reduced_form.ate),
            "first_stage_effect": float(first_stage.ate),
            "first_stage_se": float(first_stage.se),
            "compliance_rate": float(first_stage.ate),  # Jump in treatment probability
            **reduced_form.diagnostics
        }

        return RDResult(
            ate=float(ate_fuzzy),
            se=float(se_fuzzy),
            ci_lower=float(ci_lower),
            ci_upper=float(ci_upper),
            bandwidth=reduced_form.bandwidth,
            n_left=reduced_form.n_left,
            n_right=reduced_form.n_right,
            rd_type="fuzzy",
            diagnostics=diagnostics
        )


class RDAnalyzer:
    """Main interface for RD analysis"""

    def __init__(self, cutoff: float = 0.0, alpha: float = 0.05):
        self.cutoff = cutoff
        self.alpha = alpha
        self.sharp = SharpRD(cutoff=cutoff, alpha=alpha)
        self.fuzzy = FuzzyRD(cutoff=cutoff, alpha=alpha)

    def estimate(
        self,
        X: np.ndarray,
        y: np.ndarray,
        treatment: Optional[np.ndarray] = None,
        bandwidth: Optional[float] = None,
        bw_method: str = "ik"
    ) -> RDResult:
        """
        Estimate RD effect (auto-detects sharp vs fuzzy)

        Args:
            X: Running variable
            y: Outcome
            treatment: Actual treatment (None for sharp RD)
            bandwidth: Bandwidth
            bw_method: Bandwidth selection method

        Returns:
            RDResult
        """
        if treatment is None:
            # Sharp RD
            return self.sharp.estimate(X, y, bandwidth, bw_method)
        else:
            # Fuzzy RD
            return self.fuzzy.estimate(X, y, treatment, bandwidth, bw_method)

    def robustness_checks(
        self,
        X: np.ndarray,
        y: np.ndarray,
        treatment: Optional[np.ndarray] = None,
        covariates: Optional[np.ndarray] = None
    ) -> Dict[str, Any]:
        """
        Robustness checks for RD

        1. Placebo cutoffs (should find no effects)
        2. Covariate balance (covariates should be continuous at cutoff)
        3. Density test (McCrary test - no manipulation)

        Returns:
            Dictionary of robustness results
        """
        results = {}

        # 1. Placebo cutoffs
        placebo_cutoffs = [self.cutoff - 0.5 * np.std(X), self.cutoff + 0.5 * np.std(X)]
        placebo_effects = []

        for placebo_c in placebo_cutoffs:
            analyzer = RDAnalyzer(cutoff=placebo_c, alpha=self.alpha)
            try:
                placebo_result = analyzer.estimate(X, y, treatment)
                placebo_effects.append({
                    "cutoff": float(placebo_c),
                    "effect": float(placebo_result.ate),
                    "se": float(placebo_result.se),
                    "significant": abs(placebo_result.ate) > 1.96 * placebo_result.se
                })
            except Exception as e:
                logger.warning(f"Placebo cutoff {placebo_c} failed: {e}")

        results["placebo_tests"] = placebo_effects

        # 2. Covariate balance
        if covariates is not None:
            balance_tests = []
            for j in range(covariates.shape[1]):
                try:
                    balance_result = self.sharp.estimate(X, covariates[:, j])
                    balance_tests.append({
                        "covariate_idx": j,
                        "jump": float(balance_result.ate),
                        "se": float(balance_result.se),
                        "significant": abs(balance_result.ate) > 1.96 * balance_result.se
                    })
                except Exception as e:
                    logger.warning(f"Covariate {j} balance test failed: {e}")

            results["covariate_balance"] = balance_tests

        # 3. Density test (simplified)
        results["density_test"] = self._mccrary_density_test(X)

        return results

    def _mccrary_density_test(self, X: np.ndarray) -> Dict[str, Any]:
        """
        McCrary (2008) density test for manipulation

        Tests if density of running variable is continuous at cutoff.
        """
        # Histogram on each side of cutoff
        X_left = X[X < self.cutoff]
        X_right = X[X >= self.cutoff]

        # Bin counts
        n_bins = 20
        hist_left, _ = np.histogram(X_left, bins=n_bins)
        hist_right, _ = np.histogram(X_right, bins=n_bins)

        # Density at cutoff (last bin on left, first bin on right)
        density_left = hist_left[-1] / len(X_left) if len(X_left) > 0 else 0
        density_right = hist_right[0] / len(X_right) if len(X_right) > 0 else 0

        # Jump in log density
        if density_left > 0 and density_right > 0:
            log_jump = np.log(density_right) - np.log(density_left)
        else:
            log_jump = 0

        # Rough test (proper McCrary test requires more sophistication)
        manipulation_warning = abs(log_jump) > 0.5

        return {
            "log_density_jump": float(log_jump),
            "manipulation_warning": manipulation_warning,
            "n_left": int(len(X_left)),
            "n_right": int(len(X_right))
        }
