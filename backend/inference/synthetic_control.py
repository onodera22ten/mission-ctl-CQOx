"""
Synthetic Control Method
========================

Implements Abadie et al.'s Synthetic Control for comparative case studies.

**Core Idea**:
When 1 unit receives treatment and N control units do not:
- Create "synthetic" treated unit = weighted average of controls
- Weights chosen to match pre-treatment characteristics
- Post-treatment gap = treatment effect

**Key Steps**:
1. **Donor Pool Selection**: Choose valid control units
2. **Weight Optimization**: Minimize pre-treatment fit
3. **Inference**: Placebo tests, permutation p-values

**Applications**:
- Policy evaluation (e.g., California tobacco tax)
- Event studies (e.g., German reunification)
- Single-unit interventions

References:
- Abadie & Gardeazabal (2003). "The Economic Costs of Conflict"
- Abadie, Diamond, & Hainmueller (2010). "Synthetic Control Methods for Comparative Case Studies." JASA.
- Abadie, Diamond, & Hainmueller (2015). "Comparative Politics and the Synthetic Control Method." AJPS.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass
from scipy.optimize import minimize, nnls
from scipy import stats
import logging

logger = logging.getLogger(__name__)


@dataclass
class SyntheticControlResult:
    """Synthetic control estimation result"""
    ate_post: float  # Average treatment effect in post-period
    weights: Dict[str, float]  # Control unit weights
    pre_rmspe: float  # Pre-treatment root mean squared prediction error
    post_rmspe: float  # Post-treatment RMSPE
    placebo_p_value: Optional[float]  # Permutation test p-value
    synthetic_trajectory: np.ndarray  # Predicted counterfactual
    treated_trajectory: np.ndarray  # Actual treated trajectory
    gap: np.ndarray  # Treatment effect over time
    time_points: np.ndarray


class SyntheticControl:
    """
    Synthetic Control Estimator (Abadie et al.)

    Notation:
    - J+1 units (1 treated, J controls)
    - T time periods (T0 pre-treatment, T1 post-treatment)
    - X: covariates (J+1 x K)
    - Y: outcomes (J+1 x T)
    """

    def __init__(
        self,
        optimization_method: str = "nnls",  # "nnls", "simplex", or "regression"
        matching_vars: Optional[List[str]] = None
    ):
        """
        Args:
            optimization_method:
                - "nnls": Non-negative least squares (fast, standard)
                - "simplex": Simplex with sum-to-one constraint
                - "regression": Regression-based weights
            matching_vars: Variables to match on (if None, use outcomes only)
        """
        self.optimization_method = optimization_method
        self.matching_vars = matching_vars

    def fit(
        self,
        y_treated: np.ndarray,  # (T,) - Treated unit outcomes over time
        y_controls: np.ndarray,  # (J, T) - Control units outcomes
        treatment_time: int,  # Index when treatment begins
        X_treated: Optional[np.ndarray] = None,  # (K,) - Treated covariates
        X_controls: Optional[np.ndarray] = None,  # (J, K) - Control covariates
        control_names: Optional[List[str]] = None,
        time_points: Optional[np.ndarray] = None
    ) -> SyntheticControlResult:
        """
        Fit synthetic control

        Args:
            y_treated: Treated unit outcome trajectory (T,)
            y_controls: Control units outcomes (J, T)
            treatment_time: Time index of treatment (T0)
            X_treated: Additional covariates for treated unit (K,)
            X_controls: Additional covariates for controls (J, K)
            control_names: Names of control units
            time_points: Time labels (e.g., years)

        Returns:
            SyntheticControlResult
        """
        J, T = y_controls.shape
        T0 = treatment_time  # Pre-treatment periods
        T1 = T - T0  # Post-treatment periods

        if time_points is None:
            time_points = np.arange(T)

        if control_names is None:
            control_names = [f"Control_{j}" for j in range(J)]

        # Pre-treatment outcomes
        y_treated_pre = y_treated[:T0]
        y_controls_pre = y_controls[:, :T0]

        # Optimize weights
        if self.matching_vars and X_treated is not None and X_controls is not None:
            # Match on both outcomes and covariates
            weights = self._optimize_weights_with_covariates(
                y_treated_pre, y_controls_pre, X_treated, X_controls
            )
        else:
            # Match on pre-treatment outcomes only
            weights = self._optimize_weights_outcomes_only(y_treated_pre, y_controls_pre)

        # Synthetic control trajectory
        synthetic_trajectory = weights @ y_controls  # (T,)

        # Treatment effect (gap)
        gap = y_treated - synthetic_trajectory

        # ATT (average over post-treatment period)
        ate_post = gap[T0:].mean()

        # RMSPE (fit metric)
        pre_rmspe = np.sqrt(np.mean((y_treated[:T0] - synthetic_trajectory[:T0])**2))
        post_rmspe = np.sqrt(np.mean((y_treated[T0:] - synthetic_trajectory[T0:])**2))

        # Weights dictionary
        weights_dict = {name: float(w) for name, w in zip(control_names, weights) if w > 0.01}

        return SyntheticControlResult(
            ate_post=float(ate_post),
            weights=weights_dict,
            pre_rmspe=float(pre_rmspe),
            post_rmspe=float(post_rmspe),
            placebo_p_value=None,  # Computed separately
            synthetic_trajectory=synthetic_trajectory,
            treated_trajectory=y_treated,
            gap=gap,
            time_points=time_points
        )

    def _optimize_weights_outcomes_only(
        self,
        y_treated_pre: np.ndarray,  # (T0,)
        y_controls_pre: np.ndarray  # (J, T0)
    ) -> np.ndarray:
        """
        Optimize weights to match pre-treatment outcomes

        min_w || y_treated_pre - w' y_controls_pre ||^2
        s.t. w >= 0, sum(w) = 1
        """
        J = y_controls_pre.shape[0]

        if self.optimization_method == "nnls":
            # Non-negative least squares (no sum-to-one constraint)
            weights, residual = nnls(y_controls_pre.T, y_treated_pre)
            # Normalize to sum to 1
            weights = weights / weights.sum() if weights.sum() > 0 else np.ones(J) / J
        else:
            # Constrained optimization
            def objective(w):
                return np.sum((y_treated_pre - w @ y_controls_pre)**2)

            constraints = [
                {"type": "eq", "fun": lambda w: np.sum(w) - 1}  # Sum to 1
            ]
            bounds = [(0, 1) for _ in range(J)]  # Non-negative

            result = minimize(
                objective,
                x0=np.ones(J) / J,
                method="SLSQP",
                bounds=bounds,
                constraints=constraints
            )
            weights = result.x

        return weights

    def _optimize_weights_with_covariates(
        self,
        y_treated_pre: np.ndarray,  # (T0,)
        y_controls_pre: np.ndarray,  # (J, T0)
        X_treated: np.ndarray,  # (K,)
        X_controls: np.ndarray  # (J, K)
    ) -> np.ndarray:
        """
        Optimize weights matching both outcomes and covariates

        min_w || [y_treated_pre; X_treated] - w' [y_controls_pre; X_controls] ||^2
        s.t. w >= 0, sum(w) = 1
        """
        J = y_controls_pre.shape[0]

        # Stack outcomes and covariates
        # Normalize to same scale
        y_treated_scaled = y_treated_pre / (np.std(y_treated_pre) + 1e-10)
        y_controls_scaled = y_controls_pre / (np.std(y_controls_pre, axis=1, keepdims=True) + 1e-10)

        X_treated_scaled = X_treated / (np.std(X_treated) + 1e-10)
        X_controls_scaled = X_controls / (np.std(X_controls, axis=0, keepdims=True) + 1e-10)

        # Concatenate
        target = np.concatenate([y_treated_scaled, X_treated_scaled])
        predictors = np.column_stack([y_controls_scaled.T, X_controls_scaled])  # (T0+K, J)

        # NNLS
        weights, residual = nnls(predictors, target)
        weights = weights / weights.sum() if weights.sum() > 0 else np.ones(J) / J

        return weights

    def placebo_test(
        self,
        y_treated: np.ndarray,
        y_controls: np.ndarray,
        treatment_time: int,
        X_treated: Optional[np.ndarray] = None,
        X_controls: Optional[np.ndarray] = None,
        n_placebos: Optional[int] = None
    ) -> Tuple[float, List[float]]:
        """
        In-space placebo test

        Reassign treatment to each control unit, compute placebo gaps.
        True treatment effect should be larger than most placebos.

        Returns:
            (p_value, placebo_effects)
        """
        J = y_controls.shape[0]

        if n_placebos is None:
            n_placebos = min(J, 100)  # Limit for computational efficiency

        # True effect
        true_result = self.fit(y_treated, y_controls, treatment_time, X_treated, X_controls)
        true_post_gap = true_result.gap[treatment_time:].mean()

        # Placebo effects
        placebo_gaps = []

        for j in range(min(J, n_placebos)):
            # Treat control j as if it received treatment
            y_placebo_treated = y_controls[j]
            y_placebo_controls = np.delete(y_controls, j, axis=0)

            X_placebo_treated = X_controls[j] if X_controls is not None else None
            X_placebo_controls = np.delete(X_controls, j, axis=0) if X_controls is not None else None

            try:
                placebo_result = self.fit(
                    y_placebo_treated,
                    y_placebo_controls,
                    treatment_time,
                    X_placebo_treated,
                    X_placebo_controls
                )
                placebo_gap = placebo_result.gap[treatment_time:].mean()
                placebo_gaps.append(placebo_gap)
            except Exception as e:
                logger.warning(f"Placebo {j} failed: {e}")
                continue

        # Two-sided p-value
        if len(placebo_gaps) > 0:
            p_value = (1 + np.sum(np.abs(placebo_gaps) >= np.abs(true_post_gap))) / (1 + len(placebo_gaps))
        else:
            p_value = None

        return p_value, placebo_gaps

    def in_time_placebo(
        self,
        y_treated: np.ndarray,
        y_controls: np.ndarray,
        treatment_time: int,
        pseudo_treatment_time: int
    ) -> float:
        """
        In-time placebo test

        Pretend treatment occurred earlier (pseudo_treatment_time < treatment_time).
        Should find no effect if assumption of no anticipation holds.

        Returns:
            Pseudo treatment effect
        """
        # Use only data up to actual treatment time
        y_treated_pseudo = y_treated[:treatment_time]
        y_controls_pseudo = y_controls[:, :treatment_time]

        pseudo_result = self.fit(y_treated_pseudo, y_controls_pseudo, pseudo_treatment_time)

        pseudo_effect = pseudo_result.gap[pseudo_treatment_time:].mean()

        return pseudo_effect


class SyntheticControlAnalyzer:
    """Main interface for synthetic control analysis"""

    def __init__(self):
        self.sc = SyntheticControl()

    def analyze(
        self,
        data: pd.DataFrame,
        unit_col: str,
        time_col: str,
        outcome_col: str,
        treated_unit: str,
        treatment_time: Any,  # Value in time_col
        covariate_cols: Optional[List[str]] = None,
        run_placebo: bool = True
    ) -> Dict[str, Any]:
        """
        Full synthetic control analysis from panel data

        Args:
            data: Panel dataframe
            unit_col: Column with unit IDs
            time_col: Column with time periods
            outcome_col: Column with outcomes
            treated_unit: ID of treated unit
            treatment_time: Time when treatment occurred
            covariate_cols: Additional matching variables
            run_placebo: Whether to run placebo tests

        Returns:
            Dictionary with results and plots
        """
        # Pivot to wide format
        outcome_wide = data.pivot(index=unit_col, columns=time_col, values=outcome_col)
        time_points = outcome_wide.columns.values
        treatment_idx = np.where(time_points == treatment_time)[0][0]

        # Treated unit
        y_treated = outcome_wide.loc[treated_unit].values

        # Control units
        control_units = [u for u in outcome_wide.index if u != treated_unit]
        y_controls = outcome_wide.loc[control_units].values
        control_names = control_units

        # Covariates
        X_treated = None
        X_controls = None
        if covariate_cols:
            # Average covariates over pre-treatment period
            pre_treatment_data = data[data[time_col] < treatment_time]
            cov_agg = pre_treatment_data.groupby(unit_col)[covariate_cols].mean()

            X_treated = cov_agg.loc[treated_unit].values
            X_controls = cov_agg.loc[control_units].values

        # Fit
        result = self.sc.fit(
            y_treated, y_controls, treatment_idx,
            X_treated, X_controls, control_names, time_points
        )

        # Placebo test
        if run_placebo:
            p_value, placebo_gaps = self.sc.placebo_test(
                y_treated, y_controls, treatment_idx, X_treated, X_controls
            )
            result.placebo_p_value = p_value
        else:
            placebo_gaps = []

        return {
            "result": result,
            "placebo_gaps": placebo_gaps,
            "treatment_time": treatment_time,
            "treated_unit": treated_unit,
            "control_units": control_names
        }
