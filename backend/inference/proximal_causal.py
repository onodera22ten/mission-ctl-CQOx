"""
Proximal Causal Inference
=========================

Handles unmeasured confounding using **proxy variables**.

**Setup**:
- Treatment D, Outcome Y, Unmeasured Confounder U
- Cannot identify causal effect without U
- BUT: Have proxies W (treatment proxy) and Z (outcome proxy)

**Proxies**:
- W: Correlated with U and affects D (treatment confounding proxy)
- Z: Correlated with U and affects Y (outcome confounding proxy)

**Identification**:
Under completeness + exogeneity conditions, can identify:
τ = E[Y(1) - Y(0)]

**Bridge Functions**:
- h(W, D): E[Y | W, D] (outcome bridge)
- q(Z, D): E[D | Z] (treatment bridge)

References:
- Tchetgen Tchetgen et al. (2020). "An Introduction to Proximal Causal Learning." arXiv.
- Miao et al. (2018). "Identifying Causal Effects with Proxy Variables of an Unmeasured Confounder." Biometrika.
- Cui et al. (2023). "Semiparametric Proximal Causal Inference." JASA.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from scipy import stats
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.ensemble import RandomForestRegressor
import logging

logger = logging.getLogger(__name__)


@dataclass
class ProximalResult:
    """Proximal causal inference result"""
    ate: float
    se: float
    ci_lower: float
    ci_upper: float
    bridge_function_type: str  # "linear" or "flexible"
    diagnostics: Dict[str, Any]


class ProximalCausal:
    """
    Proximal Causal Inference Estimator

    Two-stage approach:
    1. Estimate bridge functions h(W,D) and q(Z,D)
    2. Use bridges to debias effect estimate
    """

    def __init__(
        self,
        bridge_model: str = "linear",  # "linear", "ridge", or "rf"
        alpha: float = 0.05
    ):
        """
        Args:
            bridge_model: Model for bridge functions
            alpha: Significance level
        """
        self.bridge_model = bridge_model
        self.alpha = alpha

    def estimate(
        self,
        y: np.ndarray,
        treatment: np.ndarray,
        W: np.ndarray,  # Treatment confounding proxy (n, p_w)
        Z: np.ndarray,  # Outcome confounding proxy (n, p_z)
        X: Optional[np.ndarray] = None  # Observed covariates
    ) -> ProximalResult:
        """
        Estimate ATE using proximal causal inference

        Args:
            y: Outcome (n,)
            treatment: Treatment (n,)
            W: Treatment proxy variables (n, p_w)
            Z: Outcome proxy variables (n, p_z)
            X: Additional observed covariates (n, p)

        Returns:
            ProximalResult
        """
        n = len(y)

        if W.ndim == 1:
            W = W.reshape(-1, 1)
        if Z.ndim == 1:
            Z = Z.reshape(-1, 1)

        # Combine proxies with covariates if available
        if X is not None:
            W_aug = np.column_stack([W, X])
            Z_aug = np.column_stack([Z, X])
        else:
            W_aug = W
            Z_aug = Z

        # Stage 1: Estimate bridge functions

        # Outcome bridge: h(W, D) = E[Y | W, D]
        h_model = self._get_model()
        WD = np.column_stack([W_aug, treatment])
        h_model.fit(WD, y)
        h_fitted = h_model.predict(WD)

        # Treatment bridge: q(Z, D) = E[D | Z] (simplified: fit D ~ Z)
        q_model = self._get_model()
        q_model.fit(Z_aug, treatment)
        q_fitted = q_model.predict(Z_aug)

        # Stage 2: Debiased effect estimation

        # Proximal approach: Use instrumental-variable-like moment condition
        # τ = Cov(h_fitted, treatment - q_fitted) / Var(treatment - q_fitted)

        treatment_residual = treatment - q_fitted

        # Estimate τ via IV-like regression
        # Regress h_fitted on treatment_residual
        ate = np.cov(h_fitted, treatment_residual)[0, 1] / np.var(treatment_residual)

        # Alternative: Two-stage regression
        # Stage 1: Treatment residualized by proxy
        # Stage 2: Regress outcome bridge on treatment residual

        # Standard error (bootstrap or asymptotic)
        # Simplified: use residual variance
        outcome_residual = y - h_fitted
        residual_var = np.var(outcome_residual)
        treatment_residual_var = np.var(treatment_residual)

        se = np.sqrt(residual_var / (n * treatment_residual_var))

        # Confidence interval
        z_crit = stats.norm.ppf(1 - self.alpha / 2)
        ci_lower = ate - z_crit * se
        ci_upper = ate + z_crit * se

        # Diagnostics
        # Check bridge function fit
        h_r2 = 1 - np.var(y - h_fitted) / np.var(y)
        q_r2 = 1 - np.var(treatment - q_fitted) / np.var(treatment)

        return ProximalResult(
            ate=float(ate),
            se=float(se),
            ci_lower=float(ci_lower),
            ci_upper=float(ci_upper),
            bridge_function_type=self.bridge_model,
            diagnostics={
                "outcome_bridge_r2": float(h_r2),
                "treatment_bridge_r2": float(q_r2),
                "treatment_residual_var": float(treatment_residual_var),
                "n": n
            }
        )

    def _get_model(self):
        """Get bridge function model"""
        if self.bridge_model == "linear":
            return LinearRegression()
        elif self.bridge_model == "ridge":
            return Ridge(alpha=1.0)
        elif self.bridge_model == "rf":
            return RandomForestRegressor(n_estimators=100, max_depth=5, random_state=42)
        else:
            raise ValueError(f"Unknown bridge model: {self.bridge_model}")


class ProximalAnalyzer:
    """Main interface for proximal causal inference"""

    def __init__(self, alpha: float = 0.05):
        self.alpha = alpha

    def estimate(
        self,
        y: np.ndarray,
        treatment: np.ndarray,
        W: np.ndarray,
        Z: np.ndarray,
        X: Optional[np.ndarray] = None,
        bridge_model: str = "linear"
    ) -> ProximalResult:
        """
        Estimate causal effect with proximal variables

        Args:
            y: Outcome
            treatment: Treatment
            W: Treatment confounding proxy
            Z: Outcome confounding proxy
            X: Observed covariates
            bridge_model: "linear", "ridge", or "rf"

        Returns:
            ProximalResult
        """
        estimator = ProximalCausal(bridge_model=bridge_model, alpha=self.alpha)
        return estimator.estimate(y, treatment, W, Z, X)
