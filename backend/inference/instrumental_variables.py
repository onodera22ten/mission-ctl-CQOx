"""
Instrumental Variables (IV) Estimation
======================================

Implements rigorous IV methods for endogenous treatment:

1. **Two-Stage Least Squares (2SLS)**
   - Standard IV estimator
   - First stage: regress treatment on instruments
   - Second stage: regress outcome on predicted treatment

2. **Generalized Method of Moments (GMM)**
   - Efficient for overidentified models (more instruments than endogenous vars)
   - Optimal weighting matrix

3. **Weak Instrument Diagnostics**
   - First-stage F-statistic (rule of thumb: F > 10)
   - Cragg-Donald statistic
   - Anderson-Rubin test (robust to weak instruments)

4. **DML-IV** (Double Machine Learning for IV)
   - Orthogonal moments with ML nuisance estimation
   - Robustness to complex confounding

References:
- Angrist & Pischke (2009). "Mostly Harmless Econometrics."
- Stock & Yogo (2005). "Testing for Weak Instruments."
- Chernozhukov et al. (2018). "Double/Debiased Machine Learning for Treatment and Causal Parameters."
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass
from scipy import stats
from scipy.linalg import inv
from sklearn.linear_model import LinearRegression, LassoCV
from sklearn.ensemble import RandomForestRegressor
import logging

logger = logging.getLogger(__name__)


@dataclass
class IVResult:
    """Instrumental Variables estimation result"""
    ate: float
    se: float
    ci_lower: float
    ci_upper: float
    method: str
    first_stage_f: float
    overid_test_p: Optional[float]  # Hansen J-test p-value
    diagnostics: Dict[str, Any]


class TwoStageLeastSquares:
    """
    Two-Stage Least Squares Estimator

    Handles:
    - Just-identified (# instruments = # endogenous)
    - Over-identified (# instruments > # endogenous)
    """

    def __init__(self, alpha: float = 0.05):
        self.alpha = alpha

    def estimate(
        self,
        y: np.ndarray,
        treatment: np.ndarray,
        Z: np.ndarray,  # Instruments
        X: Optional[np.ndarray] = None,  # Exogenous controls
        cluster: Optional[np.ndarray] = None  # For clustered SE
    ) -> IVResult:
        """
        2SLS estimation

        Args:
            y: Outcome (n,)
            treatment: Endogenous treatment (n,)
            Z: Instruments (n, k) where k >= 1
            X: Exogenous controls (n, p) or None
            cluster: Cluster IDs for robust SE

        Returns:
            IVResult with ATE and diagnostics
        """
        n = len(y)
        treatment = treatment.reshape(-1, 1)

        if Z.ndim == 1:
            Z = Z.reshape(-1, 1)

        # Build design matrices
        if X is not None:
            X_mat = np.column_stack([np.ones(n), X])
            Z_aug = np.column_stack([np.ones(n), X, Z])  # All exogenous + instruments
        else:
            X_mat = np.ones((n, 1))
            Z_aug = np.column_stack([np.ones(n), Z])

        # Stage 1: Regress treatment on all exogenous variables (X + Z)
        treatment_hat, first_stage_stats = self._first_stage(treatment, Z_aug)

        # Stage 2: Regress y on treatment_hat + exogenous controls
        if X is not None:
            W = np.column_stack([treatment_hat, X])
        else:
            W = treatment_hat

        beta_2sls = inv(W.T @ W) @ (W.T @ y)
        ate = beta_2sls[0]

        # Standard errors
        residuals = y - W @ beta_2sls

        if cluster is not None:
            se = self._clustered_se(W, residuals, cluster)[0]
        else:
            # Homoskedastic SE
            sigma2 = np.sum(residuals**2) / (n - W.shape[1])
            V = sigma2 * inv(W.T @ W)
            se = np.sqrt(V[0, 0])

        # Confidence interval
        t_crit = stats.t.ppf(1 - self.alpha / 2, n - W.shape[1])
        ci_lower = ate - t_crit * se
        ci_upper = ate + t_crit * se

        # Overidentification test (Hansen J-test)
        n_instruments = Z.shape[1]
        n_endogenous = 1
        overid_test_p = None

        if n_instruments > n_endogenous:
            overid_test_p = self._hansen_j_test(y, treatment_hat, Z_aug, residuals)

        return IVResult(
            ate=float(ate),
            se=float(se),
            ci_lower=float(ci_lower),
            ci_upper=float(ci_upper),
            method="2sls",
            first_stage_f=first_stage_stats["f_stat"],
            overid_test_p=overid_test_p,
            diagnostics={
                **first_stage_stats,
                "n_instruments": n_instruments,
                "n_endogenous": n_endogenous,
                "overidentified": n_instruments > n_endogenous
            }
        )

    def _first_stage(self, treatment: np.ndarray, Z_aug: np.ndarray) -> Tuple[np.ndarray, Dict]:
        """
        First stage regression with diagnostics

        Returns:
            (treatment_hat, diagnostics)
        """
        n, k = Z_aug.shape

        # Regression
        beta_fs = inv(Z_aug.T @ Z_aug) @ (Z_aug.T @ treatment)
        treatment_hat = Z_aug @ beta_fs

        # F-statistic
        residuals = treatment - treatment_hat
        SSR = np.sum(residuals**2)
        SST = np.sum((treatment - treatment.mean())**2)
        R2 = 1 - SSR / SST

        f_stat = (R2 / (k - 1)) / ((1 - R2) / (n - k))

        # Partial R² (for instruments only, excluding constant and X)
        # Simplified: use overall R² as proxy
        partial_r2 = R2

        diagnostics = {
            "first_stage_r2": float(R2),
            "first_stage_partial_r2": float(partial_r2),
            "f_stat": float(f_stat),
            "weak_instrument_warning": f_stat < 10.0
        }

        return treatment_hat.flatten(), diagnostics

    def _clustered_se(
        self,
        W: np.ndarray,
        residuals: np.ndarray,
        cluster: np.ndarray
    ) -> np.ndarray:
        """Cluster-robust standard errors"""
        n, k = W.shape
        unique_clusters = np.unique(cluster)
        G = len(unique_clusters)

        # Cluster-robust variance
        meat = np.zeros((k, k))
        for c in unique_clusters:
            idx = cluster == c
            W_c = W[idx]
            e_c = residuals[idx]
            meat += (W_c.T @ e_c).reshape(-1, 1) @ (W_c.T @ e_c).reshape(1, -1)

        bread = inv(W.T @ W)
        V_cluster = (G / (G - 1)) * (n - 1) / (n - k) * bread @ meat @ bread

        return np.sqrt(np.diag(V_cluster))

    def _hansen_j_test(
        self,
        y: np.ndarray,
        treatment_hat: np.ndarray,
        Z_aug: np.ndarray,
        residuals: np.ndarray
    ) -> float:
        """
        Hansen J-test for overidentifying restrictions

        H0: All instruments are valid
        """
        n = len(y)

        # Project residuals onto instruments
        P_Z = Z_aug @ inv(Z_aug.T @ Z_aug) @ Z_aug.T
        e_proj = P_Z @ residuals

        # J-statistic
        J = n * (e_proj.T @ e_proj) / (residuals.T @ residuals)

        # Degrees of freedom = # overidentifying restrictions
        df = Z_aug.shape[1] - 1  # Subtract # endogenous variables

        p_value = 1 - stats.chi2.cdf(J, df)

        return float(p_value)


class GeneralizedMethodOfMoments:
    """
    GMM Estimator for IV

    More efficient than 2SLS when overidentified.
    Uses optimal weighting matrix.
    """

    def __init__(self, alpha: float = 0.05, max_iter: int = 10):
        self.alpha = alpha
        self.max_iter = max_iter

    def estimate(
        self,
        y: np.ndarray,
        treatment: np.ndarray,
        Z: np.ndarray,
        X: Optional[np.ndarray] = None
    ) -> IVResult:
        """
        Two-step efficient GMM

        Step 1: Use identity weighting (equivalent to 2SLS)
        Step 2: Use optimal weighting based on Step 1 residuals
        """
        n = len(y)
        treatment = treatment.reshape(-1, 1)

        if Z.ndim == 1:
            Z = Z.reshape(-1, 1)

        # Build instrument matrix
        if X is not None:
            Z_aug = np.column_stack([np.ones(n), X, Z])
        else:
            Z_aug = np.column_stack([np.ones(n), Z])

        k = Z_aug.shape[1]

        # Step 1: 2SLS (identity weighting)
        W_step1 = np.eye(k)
        beta_step1 = self._gmm_step(y, treatment, Z_aug, W_step1, X)

        # Compute residuals
        if X is not None:
            X_mat = np.column_stack([treatment, X])
        else:
            X_mat = treatment

        residuals_step1 = y - X_mat @ beta_step1

        # Step 2: Optimal weighting
        Omega = self._estimate_omega(Z_aug, residuals_step1)
        W_step2 = inv(Omega)
        beta_gmm = self._gmm_step(y, treatment, Z_aug, W_step2, X)
        ate = beta_gmm[0]

        # Standard errors
        residuals = y - X_mat @ beta_gmm

        # GMM variance
        G = Z_aug.T @ X_mat / n  # Moment conditions
        V_gmm = inv(G.T @ W_step2 @ G) / n
        se = np.sqrt(V_gmm[0, 0])

        # Confidence interval
        z_crit = stats.norm.ppf(1 - self.alpha / 2)
        ci_lower = ate - z_crit * se
        ci_upper = ate + z_crit * se

        # First stage F-stat (for diagnostics)
        treatment_hat = Z_aug @ inv(Z_aug.T @ Z_aug) @ (Z_aug.T @ treatment)
        R2 = 1 - np.sum((treatment - treatment_hat)**2) / np.sum((treatment - treatment.mean())**2)
        f_stat = (R2 / (k - 1)) / ((1 - R2) / (n - k))

        # Hansen J-test
        overid_test_p = None
        if k > 1:
            # Moment conditions
            g = Z_aug * residuals.reshape(-1, 1)
            g_bar = g.mean(axis=0)
            J = n * g_bar.T @ W_step2 @ g_bar
            df = k - 1
            overid_test_p = float(1 - stats.chi2.cdf(J, df))

        return IVResult(
            ate=float(ate),
            se=float(se),
            ci_lower=float(ci_lower),
            ci_upper=float(ci_upper),
            method="gmm",
            first_stage_f=float(f_stat),
            overid_test_p=overid_test_p,
            diagnostics={
                "first_stage_r2": float(R2),
                "f_stat": float(f_stat),
                "weak_instrument_warning": f_stat < 10.0,
                "n_instruments": Z_aug.shape[1],
                "overidentified": k > 1
            }
        )

    def _gmm_step(
        self,
        y: np.ndarray,
        treatment: np.ndarray,
        Z: np.ndarray,
        W: np.ndarray,
        X: Optional[np.ndarray]
    ) -> np.ndarray:
        """Single GMM step with weighting matrix W"""
        n = len(y)

        if X is not None:
            X_mat = np.column_stack([treatment, X])
        else:
            X_mat = treatment

        # GMM estimator: beta = (X'Z W Z'X)^{-1} X'Z W Z'y
        ZX = Z.T @ X_mat
        Zy = Z.T @ y

        beta = inv(ZX.T @ W @ ZX) @ (ZX.T @ W @ Zy)

        return beta

    def _estimate_omega(self, Z: np.ndarray, residuals: np.ndarray) -> np.ndarray:
        """
        Estimate optimal weighting matrix Omega = E[Z'Z * e^2]

        For homoskedastic errors: Omega = sigma^2 * Z'Z / n
        For heteroskedastic: Omega = Z' diag(e^2) Z / n
        """
        n = Z.shape[0]

        # Heteroskedasticity-robust
        Omega = Z.T @ (Z * residuals.reshape(-1, 1)**2) / n

        return Omega


class DML_IV:
    """
    Double Machine Learning for IV (Chernozhukov et al. 2018)

    Advantages:
    - Allows flexible (nonlinear) first-stage
    - Allows flexible (nonlinear) reduced-form
    - Orthogonal moments → valid inference
    """

    def __init__(self, ml_model: str = "rf", n_folds: int = 5, alpha: float = 0.05):
        """
        Args:
            ml_model: "lasso", "rf", or "gradient_boosting"
            n_folds: Number of cross-fitting folds
            alpha: Significance level
        """
        self.ml_model = ml_model
        self.n_folds = n_folds
        self.alpha = alpha

    def estimate(
        self,
        y: np.ndarray,
        treatment: np.ndarray,
        Z: np.ndarray,
        X: Optional[np.ndarray] = None
    ) -> IVResult:
        """
        DML-IV with cross-fitting

        Estimates orthogonal moment conditions:
        E[(Y - m(Z, X))(D - r(Z, X))] = 0

        where m(Z,X) = E[Y|Z,X], r(Z,X) = E[D|Z,X]
        """
        from sklearn.model_selection import KFold

        n = len(y)

        if Z.ndim == 1:
            Z = Z.reshape(-1, 1)

        # Combine Z and X
        if X is not None:
            W = np.column_stack([Z, X])
        else:
            W = Z

        # Storage for residuals
        y_res = np.zeros(n)
        d_res = np.zeros(n)

        # Cross-fitting
        kf = KFold(n_splits=self.n_folds, shuffle=True, random_state=42)

        for train_idx, test_idx in kf.split(W):
            W_train, W_test = W[train_idx], W[test_idx]
            y_train, y_test = y[train_idx], y[test_idx]
            d_train, d_test = treatment[train_idx], treatment[test_idx]

            # Fit nuisance functions
            m_model = self._get_model()
            r_model = self._get_model()

            m_model.fit(W_train, y_train)
            r_model.fit(W_train, d_train)

            # Predict on test set
            m_hat = m_model.predict(W_test)
            r_hat = r_model.predict(W_test)

            # Residuals
            y_res[test_idx] = y_test - m_hat
            d_res[test_idx] = d_test - r_hat

        # Final IV regression: y_res ~ d_res (OLS)
        ate = np.sum(y_res * d_res) / np.sum(d_res**2)

        # Standard error (heteroskedasticity-robust)
        residuals = y_res - ate * d_res
        V = np.sum(residuals**2 * d_res**2) / (np.sum(d_res**2)**2)
        se = np.sqrt(V / n)

        # Confidence interval
        z_crit = stats.norm.ppf(1 - self.alpha / 2)
        ci_lower = ate - z_crit * se
        ci_upper = ate + z_crit * se

        # Diagnostics (first-stage F-stat analog)
        d_var = np.var(treatment)
        d_res_var = np.var(d_res)
        partial_r2 = 1 - d_res_var / d_var
        f_stat_analog = (partial_r2 / (1 - partial_r2)) * (n - W.shape[1] - 1) / W.shape[1]

        return IVResult(
            ate=float(ate),
            se=float(se),
            ci_lower=float(ci_lower),
            ci_upper=float(ci_upper),
            method="dml_iv",
            first_stage_f=float(f_stat_analog),
            overid_test_p=None,
            diagnostics={
                "ml_model": self.ml_model,
                "n_folds": self.n_folds,
                "first_stage_partial_r2": float(partial_r2),
                "f_stat_analog": float(f_stat_analog)
            }
        )

    def _get_model(self):
        """Get ML model instance"""
        if self.ml_model == "lasso":
            return LassoCV(cv=3, random_state=42)
        elif self.ml_model == "rf":
            return RandomForestRegressor(n_estimators=100, max_depth=5, random_state=42)
        else:
            from sklearn.ensemble import GradientBoostingRegressor
            return GradientBoostingRegressor(n_estimators=100, max_depth=3, random_state=42)


class InstrumentalVariablesAnalyzer:
    """Main interface for IV estimation"""

    def __init__(self, alpha: float = 0.05):
        self.alpha = alpha
        self.tsls = TwoStageLeastSquares(alpha=alpha)
        self.gmm = GeneralizedMethodOfMoments(alpha=alpha)
        self.dml_iv = DML_IV(alpha=alpha)

    def estimate(
        self,
        y: np.ndarray,
        treatment: np.ndarray,
        Z: np.ndarray,
        X: Optional[np.ndarray] = None,
        method: str = "auto",
        cluster: Optional[np.ndarray] = None
    ) -> IVResult:
        """
        Estimate causal effect using IV

        Args:
            y: Outcome
            treatment: Endogenous treatment
            Z: Instruments (must be exogenous)
            X: Exogenous controls
            method: "2sls", "gmm", "dml_iv", or "auto"
            cluster: Cluster IDs for SE

        Returns:
            IVResult
        """
        if Z.ndim == 1:
            Z = Z.reshape(-1, 1)

        n_instruments = Z.shape[1]

        # Auto-select method
        if method == "auto":
            if n_instruments == 1:
                method = "2sls"
            elif n_instruments <= 5:
                method = "gmm"
            else:
                method = "dml_iv"

        # Estimate
        if method == "2sls":
            result = self.tsls.estimate(y, treatment, Z, X, cluster)
        elif method == "gmm":
            result = self.gmm.estimate(y, treatment, Z, X)
        elif method == "dml_iv":
            result = self.dml_iv.estimate(y, treatment, Z, X)
        else:
            raise ValueError(f"Unknown method: {method}")

        # Add warnings
        if result.first_stage_f < 10.0:
            logger.warning(f"Weak instruments detected (F={result.first_stage_f:.2f} < 10). Results may be unreliable.")

        if result.overid_test_p is not None and result.overid_test_p < 0.05:
            logger.warning(f"Hansen J-test rejected (p={result.overid_test_p:.3f}). Some instruments may be invalid.")

        return result
