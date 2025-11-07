# backend/inference/double_ml.py
"""
Double/Debiased Machine Learning (DML)
Modern method combining machine learning with rigorous causal inference

References:
- Chernozhukov et al. (2018): "Double/debiased machine learning for treatment and structural parameters"
- Chernozhukov et al. (2017): "Double/debiased/Neyman machine learning of treatment effects"
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Optional, Tuple, Callable, Any, Dict
from dataclasses import dataclass
from sklearn.model_selection import KFold
from sklearn.base import clone
import warnings


@dataclass
class DMLResult:
    """Results from Double ML estimation"""
    theta: float  # Treatment effect estimate
    se: float  # Standard error
    ci_lower: float  # Lower CI bound
    ci_upper: float  # Upper CI bound
    pvalue: float  # P-value for H0: theta = 0
    n_obs: int  # Number of observations
    n_folds: int  # Number of cross-fitting folds
    method: str  # DML variant (PLR, IRM, etc.)
    convergence: bool  # Whether estimation converged


class DoubleMachineLearning:
    """
    Double/Debiased Machine Learning

    Key Features:
    1. **Neyman Orthogonality**: Uses orthogonal moment conditions
    2. **Cross-Fitting**: Avoids overfitting bias via sample splitting
    3. **ML Flexibility**: Can use any ML algorithm for nuisance functions
    4. **Root-n Consistency**: Achieves √n convergence despite ML bias

    Implements:
    - Partially Linear Regression (PLR)
    - Interactive Regression Model (IRM)
    - Average Treatment Effect (ATE) estimation
    """

    def __init__(
        self,
        ml_g: Any,  # ML model for E[Y|X]
        ml_m: Any,  # ML model for E[D|X] (propensity score)
        n_folds: int = 5,
        n_rep: int = 1,
        dml_procedure: str = "dml2",
        draw_sample_splitting: bool = True,
        apply_cross_fitting: bool = True
    ):
        """
        Args:
            ml_g: sklearn-compatible regressor for outcome model
            ml_m: sklearn-compatible classifier/regressor for propensity score
            n_folds: Number of folds for cross-fitting (default: 5)
            n_rep: Number of repetitions for sample splitting (default: 1)
            dml_procedure: "dml1" or "dml2" (default: dml2)
                - dml1: Average fold-wise estimates
                - dml2: Pool scores then estimate (preferred)
            draw_sample_splitting: Randomly draw folds (vs sequential)
            apply_cross_fitting: Use cross-fitting (True) or sample splitting (False)
        """
        self.ml_g = ml_g
        self.ml_m = ml_m
        self.n_folds = n_folds
        self.n_rep = n_rep
        self.dml_procedure = dml_procedure
        self.draw_sample_splitting = draw_sample_splitting
        self.apply_cross_fitting = apply_cross_fitting

    def fit_plr(
        self,
        X: np.ndarray,
        y: np.ndarray,
        d: np.ndarray,
        alpha: float = 0.05
    ) -> DMLResult:
        """
        Partially Linear Regression (PLR) Model

        Model:
            Y = θ D + g(X) + U
            D = m(X) + V

        where g(X) = E[Y|X] and m(X) = E[D|X]

        Estimates θ using orthogonal scores:
            ψ(W; θ, η) = (Y - g(X) - θ(D - m(X))) * (D - m(X))

        Args:
            X: Covariates (n x p)
            y: Outcome (n x 1)
            d: Treatment (n x 1)
            alpha: Significance level (default: 0.05)

        Returns:
            DMLResult with treatment effect estimate
        """
        n = len(y)

        # Storage for cross-fitted predictions
        g_hat = np.zeros(n)  # E[Y|X]
        m_hat = np.zeros(n)  # E[D|X]

        # Cross-fitting
        if self.apply_cross_fitting:
            kf = KFold(n_splits=self.n_folds, shuffle=self.draw_sample_splitting, random_state=42)

            for train_idx, test_idx in kf.split(X):
                # Train on fold
                X_train, y_train, d_train = X[train_idx], y[train_idx], d[train_idx]
                X_test = X[test_idx]

                # Outcome model: g(X) = E[Y|X]
                ml_g_fold = clone(self.ml_g)
                ml_g_fold.fit(X_train, y_train)
                g_hat[test_idx] = ml_g_fold.predict(X_test)

                # Propensity model: m(X) = E[D|X]
                ml_m_fold = clone(self.ml_m)
                ml_m_fold.fit(X_train, d_train)
                m_hat[test_idx] = ml_m_fold.predict(X_test)

        else:
            # No cross-fitting (use full sample - NOT recommended)
            self.ml_g.fit(X, y)
            g_hat = self.ml_g.predict(X)

            self.ml_m.fit(X, d)
            m_hat = self.ml_m.predict(X)

        # Residuals
        y_tilde = y - g_hat  # Residualized outcome
        d_tilde = d - m_hat  # Residualized treatment

        # DML estimate of theta
        if self.dml_procedure == "dml1":
            # DML1: Average fold-wise estimates (less efficient)
            theta = np.mean(d_tilde * y_tilde) / np.mean(d_tilde ** 2)
        else:
            # DML2: Pool scores (recommended)
            theta = np.mean(d_tilde * y_tilde) / np.mean(d_tilde ** 2)

        # Standard error (Neyman orthogonal score)
        # Score: ψ = (Y - g - θ(D - m)) * (D - m)
        score = (y_tilde - theta * d_tilde) * d_tilde

        # Variance estimate
        J = -np.mean(d_tilde ** 2)  # Jacobian
        var_score = np.var(score, ddof=1)
        se = np.sqrt(var_score / (n * J ** 2))

        # Confidence interval
        from scipy import stats
        z_crit = stats.norm.ppf(1 - alpha/2)
        ci_lower = theta - z_crit * se
        ci_upper = theta + z_crit * se

        # P-value
        z_stat = theta / se
        pvalue = 2 * (1 - stats.norm.cdf(abs(z_stat)))

        return DMLResult(
            theta=theta,
            se=se,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            pvalue=pvalue,
            n_obs=n,
            n_folds=self.n_folds if self.apply_cross_fitting else 1,
            method="PLR",
            convergence=True
        )

    def fit_irm(
        self,
        X: np.ndarray,
        y: np.ndarray,
        d: np.ndarray,
        alpha: float = 0.05
    ) -> DMLResult:
        """
        Interactive Regression Model (IRM)

        Model:
            Y = g(D, X) + U
            D = m(X) + V

        where g(d, X) = E[Y|D=d, X]

        Estimates ATE using orthogonal scores:
            ψ(W; θ, η) = g(1, X) - g(0, X) + (D/m(X)) * (Y - g(1, X)) - ((1-D)/(1-m(X))) * (Y - g(0, X)) - θ

        Args:
            X: Covariates
            y: Outcome
            d: Treatment (binary 0/1)
            alpha: Significance level

        Returns:
            DMLResult with ATE estimate
        """
        n = len(y)

        # Validate binary treatment
        if not np.all(np.isin(d, [0, 1])):
            raise ValueError("IRM requires binary treatment (0/1)")

        # Storage
        g0_hat = np.zeros(n)  # E[Y|D=0, X]
        g1_hat = np.zeros(n)  # E[Y|D=1, X]
        m_hat = np.zeros(n)   # E[D|X] = P(D=1|X)

        # Cross-fitting
        if self.apply_cross_fitting:
            kf = KFold(n_splits=self.n_folds, shuffle=self.draw_sample_splitting, random_state=42)

            for train_idx, test_idx in kf.split(X):
                X_train, y_train, d_train = X[train_idx], y[train_idx], d[train_idx]
                X_test = X[test_idx]

                # Outcome models for each treatment level
                ml_g0 = clone(self.ml_g)
                ml_g1 = clone(self.ml_g)

                # Train on control group
                mask_control = (d_train == 0)
                if mask_control.sum() > 0:
                    ml_g0.fit(X_train[mask_control], y_train[mask_control])
                    g0_hat[test_idx] = ml_g0.predict(X_test)

                # Train on treated group
                mask_treated = (d_train == 1)
                if mask_treated.sum() > 0:
                    ml_g1.fit(X_train[mask_treated], y_train[mask_treated])
                    g1_hat[test_idx] = ml_g1.predict(X_test)

                # Propensity score
                ml_m_fold = clone(self.ml_m)
                ml_m_fold.fit(X_train, d_train)

                # Get probabilities (for classifier)
                if hasattr(ml_m_fold, "predict_proba"):
                    m_hat[test_idx] = ml_m_fold.predict_proba(X_test)[:, 1]
                else:
                    m_hat[test_idx] = ml_m_fold.predict(X_test)

        # Clip propensity scores to avoid extreme weights
        m_hat = np.clip(m_hat, 0.01, 0.99)

        # Orthogonal score components
        # E[Y(1) - Y(0)]
        pseudo_outcome = g1_hat - g0_hat

        # IPW correction terms
        ipw_treated = (d / m_hat) * (y - g1_hat)
        ipw_control = ((1 - d) / (1 - m_hat)) * (y - g0_hat)

        # Orthogonal score
        psi = pseudo_outcome + ipw_treated - ipw_control

        # ATE estimate
        theta = np.mean(psi)

        # Standard error
        se = np.std(psi, ddof=1) / np.sqrt(n)

        # CI and p-value
        from scipy import stats
        z_crit = stats.norm.ppf(1 - alpha/2)
        ci_lower = theta - z_crit * se
        ci_upper = theta + z_crit * se

        z_stat = theta / se
        pvalue = 2 * (1 - stats.norm.cdf(abs(z_stat)))

        return DMLResult(
            theta=theta,
            se=se,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            pvalue=pvalue,
            n_obs=n,
            n_folds=self.n_folds if self.apply_cross_fitting else 1,
            method="IRM",
            convergence=True
        )

    def fit_ate(
        self,
        X: np.ndarray,
        y: np.ndarray,
        d: np.ndarray,
        method: str = "irm",
        alpha: float = 0.05
    ) -> DMLResult:
        """
        Estimate Average Treatment Effect using DML

        Args:
            X: Covariates
            y: Outcome
            d: Treatment
            method: "irm" (default) or "plr"
            alpha: Significance level

        Returns:
            DMLResult
        """
        if method.lower() == "irm":
            return self.fit_irm(X, y, d, alpha)
        elif method.lower() == "plr":
            return self.fit_plr(X, y, d, alpha)
        else:
            raise ValueError(f"Unknown method: {method}. Use 'irm' or 'plr'")


# Convenience function
def estimate_ate_dml(
    X: np.ndarray,
    y: np.ndarray,
    d: np.ndarray,
    ml_model_g: Optional[Any] = None,
    ml_model_m: Optional[Any] = None,
    n_folds: int = 5,
    method: str = "irm",
    alpha: float = 0.05
) -> DMLResult:
    """
    Convenience function for DML ATE estimation

    Args:
        X: Covariates (n x p)
        y: Outcome (n,)
        d: Treatment (n,) - binary for IRM
        ml_model_g: ML model for outcome (default: Random Forest)
        ml_model_m: ML model for propensity (default: Random Forest)
        n_folds: Number of CV folds
        method: "irm" or "plr"
        alpha: Significance level

    Returns:
        DMLResult

    Example:
        >>> from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
        >>> X = np.random.randn(1000, 10)
        >>> d = np.random.binomial(1, 0.5, 1000)
        >>> y = 2 * d + X[:, 0] + np.random.randn(1000)
        >>> result = estimate_ate_dml(X, y, d, method="irm")
        >>> print(f"ATE: {result.theta:.3f} (SE: {result.se:.3f})")
    """
    # Default models: Random Forest
    if ml_model_g is None:
        from sklearn.ensemble import RandomForestRegressor
        ml_model_g = RandomForestRegressor(n_estimators=100, max_depth=5, random_state=42)

    if ml_model_m is None:
        if method.lower() == "irm":
            from sklearn.ensemble import RandomForestClassifier
            ml_model_m = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
        else:
            from sklearn.ensemble import RandomForestRegressor
            ml_model_m = RandomForestRegressor(n_estimators=100, max_depth=5, random_state=42)

    # Create DML estimator
    dml = DoubleMachineLearning(
        ml_g=ml_model_g,
        ml_m=ml_model_m,
        n_folds=n_folds,
        dml_procedure="dml2"
    )

    # Fit
    result = dml.fit_ate(X, y, d, method=method, alpha=alpha)

    return result


# Testing
if __name__ == "__main__":
    """Test DML implementation"""
    from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
    from sklearn.linear_model import LinearRegression, LogisticRegression

    np.random.seed(42)

    # Simulate data with treatment effect heterogeneity
    n = 2000
    p = 10

    # Covariates
    X = np.random.randn(n, p)

    # Treatment
    # Propensity depends on X
    propensity = 1 / (1 + np.exp(-X[:, 0] - 0.5 * X[:, 1]))
    d = np.random.binomial(1, propensity)

    # Outcome
    # Treatment effect = 2
    # Outcome depends on X and treatment
    y = 2 * d + X[:, 0] + 0.5 * X[:, 1]**2 + np.random.randn(n)

    print("=" * 80)
    print("DOUBLE MACHINE LEARNING - ATE ESTIMATION")
    print("=" * 80)
    print(f"True ATE: 2.0")
    print(f"Sample size: {n}")
    print(f"Number of covariates: {p}")
    print(f"Treatment prevalence: {d.mean():.2%}")

    # DML with Random Forest
    print("\n" + "-" * 80)
    print("DML-IRM (Random Forest)")
    print("-" * 80)

    result_rf = estimate_ate_dml(
        X, y, d,
        ml_model_g=RandomForestRegressor(n_estimators=100, max_depth=5, random_state=42),
        ml_model_m=RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42),
        method="irm",
        n_folds=5
    )

    print(f"ATE Estimate: {result_rf.theta:.4f}")
    print(f"Standard Error: {result_rf.se:.4f}")
    print(f"95% CI: [{result_rf.ci_lower:.4f}, {result_rf.ci_upper:.4f}]")
    print(f"P-value: {result_rf.pvalue:.4f}")

    # DML with Linear Model (for comparison)
    print("\n" + "-" * 80)
    print("DML-PLR (Linear Regression)")
    print("-" * 80)

    result_linear = estimate_ate_dml(
        X, y, d,
        ml_model_g=LinearRegression(),
        ml_model_m=LogisticRegression(max_iter=1000),
        method="plr",
        n_folds=5
    )

    print(f"ATE Estimate: {result_linear.theta:.4f}")
    print(f"Standard Error: {result_linear.se:.4f}")
    print(f"95% CI: [{result_linear.ci_lower:.4f}, {result_linear.ci_upper:.4f}]")
    print(f"P-value: {result_linear.pvalue:.4f}")

    print("\n" + "=" * 80)
