"""
Transportability / Generalizability
===================================

Extends causal effects from trial/study population to target population.

**Problem**:
- Effect estimated in Sample S
- Want to generalize to Population T
- Populations differ in covariate distribution

**Solutions**:
1. **IPSW (Inverse Probability of Sampling Weighting)**
   - Reweight sample to match target distribution
   - w_i = P(S=1|X_i) / P(S=0|X_i)

2. **Calibration / Raking**
   - Match known marginal distributions in target
   - Iteratively adjust weights

3. **TATE (Target Average Treatment Effect)**
   - TATE = E_T[τ(X)] where distribution is from target

**Key Assumption**:
- **Conditional Exchangeability**: No unmeasured selection-outcome confounders

**Applications**:
- RCT → real-world
- One site → another site
- Historical study → current population

References:
- Stuart et al. (2011). "The use of propensity scores to assess the generalizability of results from randomized trials." RSS.
- Cole & Stuart (2010). "Generalizing Evidence From Randomized Clinical Trials." Epidemiology.
- Tipton (2013). "Improving Generalizations From Experiments." JRSS-A.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass
from scipy import stats
from sklearn.linear_model import LogisticRegressionCV
from sklearn.ensemble import RandomForestClassifier
import logging

logger = logging.getLogger(__name__)


@dataclass
class TransportResult:
    """Transportability estimation result"""
    tate: float  # Target Average Treatment Effect
    tate_se: float
    tate_ci: Tuple[float, float]
    sate: float  # Sample Average Treatment Effect (for comparison)
    effective_sample_size: float  # ESS after weighting
    max_weight: float  # Maximum weight (for diagnostics)
    diagnostics: Dict[str, Any]


class IPSW:
    """
    Inverse Probability of Sampling Weighting

    Reweights sample to match target population.

    Weight for unit i: w_i = P(S=1|X_i) / [1 - P(S=1|X_i)]
    where S=1 indicates sample membership.
    """

    def __init__(self, alpha: float = 0.05, trim_weights: float = 0.95):
        """
        Args:
            alpha: Significance level
            trim_weights: Trim extreme weights at this quantile
        """
        self.alpha = alpha
        self.trim_weights = trim_weights

    def estimate(
        self,
        X_sample: np.ndarray,  # Covariates in sample
        y_sample: np.ndarray,  # Outcomes in sample
        treatment_sample: np.ndarray,  # Treatment in sample
        X_target: Optional[np.ndarray] = None,  # Covariates in target (if available)
        propensity_model: str = "logistic"  # "logistic" or "rf"
    ) -> TransportResult:
        """
        Estimate TATE using IPSW

        Args:
            X_sample: Sample covariates (n_s, p)
            y_sample: Sample outcomes (n_s,)
            treatment_sample: Sample treatment (n_s,)
            X_target: Target covariates (n_t, p) - if None, assume summary stats
            propensity_model: Model for P(S=1|X)

        Returns:
            TransportResult
        """
        n_s = len(y_sample)

        if X_target is not None:
            # Estimate sampling propensities
            weights = self._compute_ipsw_weights(X_sample, X_target, propensity_model)
        else:
            # Assume uniform weights (no target data available)
            logger.warning("No target data provided. Using uniform weights (no generalization).")
            weights = np.ones(n_s)

        # Trim extreme weights
        if self.trim_weights < 1.0:
            weight_threshold = np.quantile(weights, self.trim_weights)
            weights = np.minimum(weights, weight_threshold)

        # Normalize weights
        weights = weights / weights.sum() * n_s

        # SATE (Sample ATE) - unweighted
        sate = self._compute_ate(y_sample, treatment_sample)

        # TATE (Target ATE) - weighted
        tate = self._compute_weighted_ate(y_sample, treatment_sample, weights)

        # Standard error (weighted)
        tate_se = self._compute_weighted_se(y_sample, treatment_sample, weights)

        # Confidence interval
        z_crit = stats.norm.ppf(1 - self.alpha / 2)
        tate_ci = (tate - z_crit * tate_se, tate + z_crit * tate_se)

        # Diagnostics
        ess = (weights.sum())**2 / (weights**2).sum()  # Effective sample size
        max_weight = weights.max()

        return TransportResult(
            tate=float(tate),
            tate_se=float(tate_se),
            tate_ci=tate_ci,
            sate=float(sate),
            effective_sample_size=float(ess),
            max_weight=float(max_weight),
            diagnostics={
                "n_sample": n_s,
                "n_target": len(X_target) if X_target is not None else None,
                "weight_cv": float(np.std(weights) / np.mean(weights)),
                "propensity_model": propensity_model
            }
        )

    def _compute_ipsw_weights(
        self,
        X_sample: np.ndarray,
        X_target: np.ndarray,
        model_type: str
    ) -> np.ndarray:
        """
        Compute IPSW weights: w_i = P(S=1|X_i) / [1 - P(S=1|X_i)]

        Estimate P(S=1|X) by pooling sample + target and fitting classifier.
        """
        # Pool sample and target
        X_pooled = np.vstack([X_sample, X_target])
        S = np.concatenate([np.ones(len(X_sample)), np.zeros(len(X_target))])

        # Fit propensity model
        if model_type == "logistic":
            model = LogisticRegressionCV(cv=5, random_state=42, max_iter=1000)
        elif model_type == "rf":
            model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
        else:
            raise ValueError(f"Unknown model: {model_type}")

        model.fit(X_pooled, S)

        # Predict P(S=1|X) for sample units
        p_sample = model.predict_proba(X_sample)[:, 1]

        # IPSW weights (odds ratio form)
        # w_i = [P(S=1|X) / P(S=0|X)] = P(S=1|X) / [1 - P(S=1|X)]
        weights = p_sample / (1 - p_sample + 1e-10)

        return weights

    def _compute_ate(self, y: np.ndarray, treatment: np.ndarray) -> float:
        """Unweighted ATE"""
        y1 = y[treatment == 1].mean()
        y0 = y[treatment == 0].mean()
        return y1 - y0

    def _compute_weighted_ate(
        self,
        y: np.ndarray,
        treatment: np.ndarray,
        weights: np.ndarray
    ) -> float:
        """Weighted ATE"""
        treated_mask = treatment == 1
        control_mask = treatment == 0

        y1_weighted = np.average(y[treated_mask], weights=weights[treated_mask])
        y0_weighted = np.average(y[control_mask], weights=weights[control_mask])

        return y1_weighted - y0_weighted

    def _compute_weighted_se(
        self,
        y: np.ndarray,
        treatment: np.ndarray,
        weights: np.ndarray
    ) -> float:
        """Weighted standard error"""
        treated_mask = treatment == 1
        control_mask = treatment == 0

        # Weighted variance
        var1 = np.average((y[treated_mask] - y[treated_mask].mean())**2, weights=weights[treated_mask])
        var0 = np.average((y[control_mask] - y[control_mask].mean())**2, weights=weights[control_mask])

        n1_eff = (weights[treated_mask].sum())**2 / (weights[treated_mask]**2).sum()
        n0_eff = (weights[control_mask].sum())**2 / (weights[control_mask]**2).sum()

        se = np.sqrt(var1 / n1_eff + var0 / n0_eff)

        return se


class Calibration:
    """
    Calibration / Raking

    Adjust weights to match known target population marginals.

    Example:
    - Know target has 60% female, 40% male
    - Sample has 50% female, 50% male
    - Reweight to match

    Uses iterative proportional fitting (raking).
    """

    def __init__(self, alpha: float = 0.05, max_iter: int = 100, tol: float = 1e-4):
        self.alpha = alpha
        self.max_iter = max_iter
        self.tol = tol

    def estimate(
        self,
        y_sample: np.ndarray,
        treatment_sample: np.ndarray,
        X_sample: pd.DataFrame,  # Covariates as dataframe
        target_marginals: Dict[str, Dict[Any, float]]  # {var: {level: proportion}}
    ) -> TransportResult:
        """
        Estimate TATE using calibration weights

        Args:
            y_sample: Sample outcomes
            treatment_sample: Sample treatment
            X_sample: Sample covariates (categorical)
            target_marginals: Target population marginals
                Example: {"gender": {"M": 0.4, "F": 0.6}, "age_group": {"<30": 0.3, "30-50": 0.5, ">50": 0.2}}

        Returns:
            TransportResult
        """
        n = len(y_sample)

        # Initialize weights
        weights = np.ones(n)

        # Iterative proportional fitting (raking)
        for iteration in range(self.max_iter):
            weights_old = weights.copy()

            for var, target_dist in target_marginals.items():
                if var not in X_sample.columns:
                    logger.warning(f"Variable {var} not in sample. Skipping.")
                    continue

                # Current weighted distribution
                for level, target_prop in target_dist.items():
                    mask = X_sample[var] == level
                    if mask.sum() == 0:
                        continue

                    current_prop = (weights[mask].sum()) / weights.sum()

                    if current_prop > 0:
                        # Adjustment factor
                        factor = target_prop / current_prop
                        weights[mask] *= factor

            # Check convergence
            if np.max(np.abs(weights - weights_old)) < self.tol:
                logger.info(f"Calibration converged in {iteration+1} iterations")
                break

        # Normalize
        weights = weights / weights.sum() * n

        # SATE
        sate_val = (y_sample[treatment_sample == 1].mean() -
                    y_sample[treatment_sample == 0].mean())

        # TATE (weighted)
        ipsw = IPSW(alpha=self.alpha)
        tate_val = ipsw._compute_weighted_ate(y_sample, treatment_sample, weights)
        tate_se = ipsw._compute_weighted_se(y_sample, treatment_sample, weights)

        z_crit = stats.norm.ppf(1 - self.alpha / 2)
        tate_ci = (tate_val - z_crit * tate_se, tate_val + z_crit * tate_se)

        ess = (weights.sum())**2 / (weights**2).sum()

        return TransportResult(
            tate=float(tate_val),
            tate_se=float(tate_se),
            tate_ci=tate_ci,
            sate=float(sate_val),
            effective_sample_size=float(ess),
            max_weight=float(weights.max()),
            diagnostics={
                "n_sample": n,
                "n_iterations": iteration + 1,
                "weight_cv": float(np.std(weights) / np.mean(weights))
            }
        )


class TransportabilityAnalyzer:
    """Main interface for transportability analysis"""

    def __init__(self, alpha: float = 0.05):
        self.alpha = alpha
        self.ipsw = IPSW(alpha=alpha)
        self.calibration = Calibration(alpha=alpha)

    def estimate(
        self,
        y_sample: np.ndarray,
        treatment_sample: np.ndarray,
        X_sample: np.ndarray,
        X_target: Optional[np.ndarray] = None,
        target_marginals: Optional[Dict] = None,
        method: str = "auto"
    ) -> TransportResult:
        """
        Estimate transportability

        Args:
            y_sample: Sample outcomes
            treatment_sample: Sample treatment
            X_sample: Sample covariates
            X_target: Target covariates (for IPSW)
            target_marginals: Target marginals (for calibration)
            method: "ipsw", "calibration", or "auto"

        Returns:
            TransportResult
        """
        if method == "auto":
            if X_target is not None:
                method = "ipsw"
            elif target_marginals is not None:
                method = "calibration"
            else:
                raise ValueError("Must provide either X_target or target_marginals")

        if method == "ipsw":
            return self.ipsw.estimate(X_sample, y_sample, treatment_sample, X_target)
        elif method == "calibration":
            if not isinstance(X_sample, pd.DataFrame):
                raise ValueError("Calibration requires X_sample as DataFrame")
            return self.calibration.estimate(y_sample, treatment_sample, X_sample, target_marginals)
        else:
            raise ValueError(f"Unknown method: {method}")
