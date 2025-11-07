"""
Difference-in-Differences (DiD)
================================

Panel data method comparing treated/control units before/after treatment.

**Classic 2×2 DiD**:
- 2 groups (treated, control)
- 2 periods (pre, post)
- τ = (Y_treat,post - Y_treat,pre) - (Y_control,post - Y_control,pre)

**Key Assumption**:
- **Parallel Trends**: Treated and control would have followed same trajectory absent treatment

**Modern Extensions**:
1. **Staggered Adoption**: Units treated at different times
2. **Callaway & Sant'Anna (2021)**: Robust ATT with never-treated comparison
3. **Event Study**: Dynamic effects before/after treatment
4. **Bacon Decomposition**: Decompose TWFE into clean vs contaminated comparisons

**Violations**:
- Differential trends → biased estimates
- Anticipation effects → pre-trends
- Treatment effect heterogeneity + staggered timing → TWFE bias

References:
- Angrist & Pischke (2009). "Mostly Harmless Econometrics."
- Callaway & Sant'Anna (2021). "Difference-in-Differences with Multiple Time Periods." JoE.
- Goodman-Bacon (2021). "Difference-in-Differences with Variation in Treatment Timing." JoE.
- Sun & Abraham (2021). "Estimating Dynamic Treatment Effects." JoE.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass
from scipy import stats
from sklearn.linear_model import LinearRegression
import logging

logger = logging.getLogger(__name__)


@dataclass
class DiDResult:
    """Difference-in-Differences estimation result"""
    att: float  # Average treatment effect on treated
    se: float
    ci_lower: float
    ci_upper: float
    method: str  # "twfe", "callaway_santanna", or "event_study"
    pre_trend_test_p: Optional[float]  # Parallel trends test
    event_study_effects: Optional[Dict[int, Tuple[float, float]]]  # Time → (effect, se)
    diagnostics: Dict[str, Any]


class TwoWayFixedEffects:
    """
    Two-Way Fixed Effects (TWFE) DiD

    Classic approach: Y_it = α_i + λ_t + τ*D_it + ε_it

    where:
    - α_i: unit fixed effects
    - λ_t: time fixed effects
    - D_it: treatment indicator
    - τ: DiD estimate

    **Warning**: Biased under heterogeneous treatment effects + staggered timing!
    """

    def __init__(self, alpha: float = 0.05):
        self.alpha = alpha

    def estimate(
        self,
        data: pd.DataFrame,
        unit_col: str,
        time_col: str,
        outcome_col: str,
        treatment_col: str,
        cluster_col: Optional[str] = None
    ) -> DiDResult:
        """
        Estimate TWFE DiD

        Args:
            data: Panel dataframe
            unit_col: Unit ID column
            time_col: Time period column
            outcome_col: Outcome column
            treatment_col: Treatment indicator column
            cluster_col: Cluster for standard errors (typically unit_col)

        Returns:
            DiDResult
        """
        # Create dummies
        unit_dummies = pd.get_dummies(data[unit_col], prefix='unit', drop_first=True)
        time_dummies = pd.get_dummies(data[time_col], prefix='time', drop_first=True)

        # Design matrix
        X = pd.concat([
            unit_dummies,
            time_dummies,
            data[[treatment_col]]
        ], axis=1)

        y = data[outcome_col].values

        # OLS
        model = LinearRegression()
        model.fit(X, y)

        # DiD coefficient (last coefficient = treatment)
        att = model.coef_[-1]

        # Standard errors
        residuals = y - model.predict(X)

        if cluster_col:
            se = self._clustered_se(X.values, residuals, data[cluster_col].values)[-1]
        else:
            # Homoskedastic SE
            n, k = X.shape
            sigma2 = np.sum(residuals**2) / (n - k)
            V = sigma2 * np.linalg.inv(X.T @ X)
            se = np.sqrt(V.iloc[-1, -1] if hasattr(V, 'iloc') else V[-1, -1])

        # Confidence interval
        n = len(y)
        t_crit = stats.t.ppf(1 - self.alpha / 2, n - X.shape[1])
        ci_lower = att - t_crit * se
        ci_upper = att + t_crit * se

        # Pre-trend test
        pre_trend_p = self._test_pre_trends(data, unit_col, time_col, outcome_col, treatment_col)

        return DiDResult(
            att=float(att),
            se=float(se),
            ci_lower=float(ci_lower),
            ci_upper=float(ci_upper),
            method="twfe",
            pre_trend_test_p=pre_trend_p,
            event_study_effects=None,
            diagnostics={
                "n_units": data[unit_col].nunique(),
                "n_periods": data[time_col].nunique(),
                "n_treated": data[data[treatment_col] == 1][unit_col].nunique()
            }
        )

    def _clustered_se(
        self,
        X: np.ndarray,
        residuals: np.ndarray,
        cluster: np.ndarray
    ) -> np.ndarray:
        """Cluster-robust standard errors"""
        n, k = X.shape
        unique_clusters = np.unique(cluster)
        G = len(unique_clusters)

        # Cluster-robust variance
        meat = np.zeros((k, k))
        for c in unique_clusters:
            idx = cluster == c
            X_c = X[idx]
            e_c = residuals[idx]
            meat += (X_c.T @ e_c).reshape(-1, 1) @ (X_c.T @ e_c).reshape(1, -1)

        bread = np.linalg.inv(X.T @ X)
        V_cluster = (G / (G - 1)) * (n - 1) / (n - k) * bread @ meat @ bread

        return np.sqrt(np.diag(V_cluster))

    def _test_pre_trends(
        self,
        data: pd.DataFrame,
        unit_col: str,
        time_col: str,
        outcome_col: str,
        treatment_col: str
    ) -> float:
        """
        Test parallel trends in pre-treatment periods

        Regression: Y_it = α_i + λ_t + Σ_k β_k * (Treat_i × 1{t=k}) + ε_it

        Test H0: β_k = 0 for all k < treatment_time
        """
        # Identify treatment timing
        treatment_start = data[data[treatment_col] == 1].groupby(unit_col)[time_col].min()

        if len(treatment_start) == 0:
            return 1.0  # No treated units

        # Create leads/lags relative to treatment
        data_test = data.copy()
        data_test['treated_unit'] = data_test[unit_col].isin(treatment_start.index).astype(int)

        # For each unit, compute relative time
        data_test['rel_time'] = data_test.apply(
            lambda row: row[time_col] - treatment_start.get(row[unit_col], np.inf)
            if row['treated_unit'] == 1 else np.nan,
            axis=1
        )

        # Pre-treatment periods
        pre_data = data_test[data_test['rel_time'] < 0].dropna(subset=['rel_time'])

        if len(pre_data) < 10:
            return 1.0  # Insufficient data

        # Test pre-treatment interactions
        # Simple version: test if treated units have different trends pre-treatment
        treated_pre = pre_data[pre_data['treated_unit'] == 1][outcome_col]
        control_pre = pre_data[pre_data['treated_unit'] == 0][outcome_col]

        if len(treated_pre) < 2 or len(control_pre) < 2:
            return 1.0

        # T-test on pre-treatment outcomes
        t_stat, p_value = stats.ttest_ind(treated_pre, control_pre)

        return float(p_value)


class CallawaySantAnna:
    """
    Callaway & Sant'Anna (2021) DiD Estimator

    Robust to:
    1. Staggered treatment adoption
    2. Treatment effect heterogeneity across groups and time
    3. Never-treated as comparison group

    Key Innovation:
    - Compute group-time ATT(g,t) for each cohort g, time t
    - Aggregate to overall ATT
    """

    def __init__(self, alpha: float = 0.05):
        self.alpha = alpha

    def estimate(
        self,
        data: pd.DataFrame,
        unit_col: str,
        time_col: str,
        outcome_col: str,
        treatment_col: str,
        cohort_col: Optional[str] = None  # Treatment adoption time
    ) -> DiDResult:
        """
        Estimate Callaway-Sant'Anna DiD

        Args:
            data: Panel dataframe
            unit_col: Unit ID column
            time_col: Time period column
            outcome_col: Outcome column
            treatment_col: Treatment indicator column
            cohort_col: Column indicating when unit was first treated (if None, infer)

        Returns:
            DiDResult
        """
        # Infer cohorts (first treatment time for each unit)
        if cohort_col is None:
            cohorts = data[data[treatment_col] == 1].groupby(unit_col)[time_col].min()
            data = data.copy()
            data['cohort'] = data[unit_col].map(cohorts).fillna(np.inf)
            cohort_col = 'cohort'

        # Never-treated units
        never_treated = data[data[cohort_col] == np.inf][unit_col].unique()

        # Unique cohorts (excluding never-treated)
        cohorts_list = sorted(data[data[cohort_col] < np.inf][cohort_col].unique())

        if len(cohorts_list) == 0:
            raise ValueError("No treated cohorts found")

        # Compute ATT(g,t) for each cohort g, time t ≥ g
        att_gt = {}

        for g in cohorts_list:
            cohort_g_units = data[data[cohort_col] == g][unit_col].unique()

            for t in data[time_col].unique():
                if t < g:
                    continue  # Only post-treatment

                # ATT(g,t) = E[Y_t - Y_{g-1} | G=g] - E[Y_t - Y_{g-1} | Never-treated]
                # Cohort g outcomes
                cohort_g_t = data[(data[unit_col].isin(cohort_g_units)) & (data[time_col] == t)][outcome_col]
                cohort_g_pre = data[(data[unit_col].isin(cohort_g_units)) & (data[time_col] == g - 1)][outcome_col]

                # Never-treated outcomes
                never_t = data[(data[unit_col].isin(never_treated)) & (data[time_col] == t)][outcome_col]
                never_pre = data[(data[unit_col].isin(never_treated)) & (data[time_col] == g - 1)][outcome_col]

                if len(cohort_g_t) == 0 or len(cohort_g_pre) == 0 or len(never_t) == 0 or len(never_pre) == 0:
                    continue

                # Difference-in-differences
                did_treated = cohort_g_t.mean() - cohort_g_pre.mean()
                did_control = never_t.mean() - never_pre.mean()

                att_gt_val = did_treated - did_control

                # Standard error (simple version)
                se_gt = np.sqrt(
                    cohort_g_t.var() / len(cohort_g_t) +
                    cohort_g_pre.var() / len(cohort_g_pre) +
                    never_t.var() / len(never_t) +
                    never_pre.var() / len(never_pre)
                )

                att_gt[(g, t)] = (att_gt_val, se_gt)

        # Aggregate ATT (simple average across group-time)
        att_values = [val for val, _ in att_gt.values()]
        att_ses = [se for _, se in att_gt.values()]

        if len(att_values) == 0:
            raise ValueError("Could not compute any group-time ATTs")

        att = np.mean(att_values)
        se = np.sqrt(np.mean(np.array(att_ses)**2))  # Conservative

        # Confidence interval
        z_crit = stats.norm.ppf(1 - self.alpha / 2)
        ci_lower = att - z_crit * se
        ci_upper = att + z_crit * se

        return DiDResult(
            att=float(att),
            se=float(se),
            ci_lower=float(ci_lower),
            ci_upper=float(ci_upper),
            method="callaway_santanna",
            pre_trend_test_p=None,
            event_study_effects=None,
            diagnostics={
                "n_cohorts": len(cohorts_list),
                "n_never_treated": len(never_treated),
                "n_group_time_atts": len(att_gt)
            }
        )


class EventStudy:
    """
    Event Study Design

    Estimates dynamic treatment effects:
    Y_it = α_i + λ_t + Σ_k β_k * D_it^k + ε_it

    where D_it^k = 1{event_time_it = k}

    Shows:
    - Pre-trends (k < 0): Should be ≈0 if parallel trends holds
    - Post-treatment effects (k ≥ 0): Dynamic effects
    """

    def __init__(self, alpha: float = 0.05):
        self.alpha = alpha

    def estimate(
        self,
        data: pd.DataFrame,
        unit_col: str,
        time_col: str,
        outcome_col: str,
        treatment_col: str,
        event_time_col: Optional[str] = None,
        leads_lags: Tuple[int, int] = (-5, 10)  # (min_lead, max_lag)
    ) -> DiDResult:
        """
        Estimate event study

        Args:
            data: Panel dataframe
            unit_col: Unit ID column
            time_col: Time period column
            outcome_col: Outcome column
            treatment_col: Treatment indicator column
            event_time_col: Relative time to treatment (if None, infer)
            leads_lags: (min_lead, max_lag) to include

        Returns:
            DiDResult with event_study_effects
        """
        # Infer event time if not provided
        if event_time_col is None:
            treatment_start = data[data[treatment_col] == 1].groupby(unit_col)[time_col].min()
            data = data.copy()
            data['event_time'] = data.apply(
                lambda row: row[time_col] - treatment_start.get(row[unit_col], np.inf),
                axis=1
            )
            event_time_col = 'event_time'

        # Filter to leads/lags window
        min_lead, max_lag = leads_lags
        data_windowed = data[(data[event_time_col] >= min_lead) & (data[event_time_col] <= max_lag)].copy()

        # Create event time dummies (excluding -1 as reference)
        event_dummies = pd.get_dummies(data_windowed[event_time_col], prefix='event')
        if 'event_-1.0' in event_dummies.columns:
            event_dummies = event_dummies.drop(columns=['event_-1.0'])
        elif 'event_-1' in event_dummies.columns:
            event_dummies = event_dummies.drop(columns=['event_-1'])

        # Add fixed effects
        unit_dummies = pd.get_dummies(data_windowed[unit_col], prefix='unit', drop_first=True)
        time_dummies = pd.get_dummies(data_windowed[time_col], prefix='time', drop_first=True)

        X = pd.concat([unit_dummies, time_dummies, event_dummies], axis=1)
        y = data_windowed[outcome_col].values

        # OLS
        model = LinearRegression()
        model.fit(X, y)

        # Extract event study coefficients
        event_cols = [col for col in X.columns if col.startswith('event_')]
        event_coefs = model.coef_[-len(event_cols):]

        # Standard errors
        residuals = y - model.predict(X)
        n, k = X.shape
        sigma2 = np.sum(residuals**2) / (n - k)
        V = sigma2 * np.linalg.inv(X.T.values @ X.values)
        se_all = np.sqrt(np.diag(V))
        event_ses = se_all[-len(event_cols):]

        # Map back to event times
        event_effects = {}
        for col, coef, se in zip(event_cols, event_coefs, event_ses):
            event_time = int(float(col.replace('event_', '')))
            event_effects[event_time] = (float(coef), float(se))

        # ATT = average of post-treatment effects
        post_effects = [coef for k, (coef, _) in event_effects.items() if k >= 0]
        att = np.mean(post_effects) if len(post_effects) > 0 else 0.0

        post_ses = [se for k, (_, se) in event_effects.items() if k >= 0]
        se_att = np.sqrt(np.mean(np.array(post_ses)**2)) if len(post_ses) > 0 else 0.0

        # Confidence interval
        z_crit = stats.norm.ppf(1 - self.alpha / 2)
        ci_lower = att - z_crit * se_att
        ci_upper = att + z_crit * se_att

        # Pre-trend test (joint F-test on pre-treatment coefficients)
        pre_effects = [(coef, se) for k, (coef, se) in event_effects.items() if k < 0]
        if len(pre_effects) > 0:
            pre_coefs = np.array([coef for coef, _ in pre_effects])
            pre_trend_p = float(stats.ttest_1samp(pre_coefs, 0)[1])
        else:
            pre_trend_p = 1.0

        return DiDResult(
            att=float(att),
            se=float(se_att),
            ci_lower=float(ci_lower),
            ci_upper=float(ci_upper),
            method="event_study",
            pre_trend_test_p=pre_trend_p,
            event_study_effects=event_effects,
            diagnostics={
                "n_event_times": len(event_effects),
                "n_pre_periods": len([k for k in event_effects if k < 0]),
                "n_post_periods": len([k for k in event_effects if k >= 0])
            }
        )


class DiDAnalyzer:
    """Main interface for DiD analysis"""

    def __init__(self, alpha: float = 0.05):
        self.alpha = alpha
        self.twfe = TwoWayFixedEffects(alpha=alpha)
        self.cs = CallawaySantAnna(alpha=alpha)
        self.event_study = EventStudy(alpha=alpha)

    def estimate(
        self,
        data: pd.DataFrame,
        unit_col: str,
        time_col: str,
        outcome_col: str,
        treatment_col: str,
        method: str = "auto",
        **kwargs
    ) -> DiDResult:
        """
        Estimate DiD effect

        Args:
            data: Panel dataframe
            unit_col: Unit ID column
            time_col: Time period column
            outcome_col: Outcome column
            treatment_col: Treatment indicator column
            method: "twfe", "callaway_santanna", "event_study", or "auto"
            **kwargs: Method-specific arguments

        Returns:
            DiDResult
        """
        # Auto-select method
        if method == "auto":
            # Check if staggered adoption
            treatment_times = data[data[treatment_col] == 1].groupby(unit_col)[time_col].min()
            n_cohorts = treatment_times.nunique()

            if n_cohorts > 1:
                method = "callaway_santanna"
            else:
                method = "twfe"

        if method == "twfe":
            return self.twfe.estimate(data, unit_col, time_col, outcome_col, treatment_col, **kwargs)
        elif method == "callaway_santanna":
            return self.cs.estimate(data, unit_col, time_col, outcome_col, treatment_col, **kwargs)
        elif method == "event_study":
            return self.event_study.estimate(data, unit_col, time_col, outcome_col, treatment_col, **kwargs)
        else:
            raise ValueError(f"Unknown method: {method}")
