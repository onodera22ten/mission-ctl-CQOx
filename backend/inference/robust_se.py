# backend/inference/robust_se.py
"""
Robust Standard Errors for Causal Inference
Implements heteroskedasticity-robust and cluster-robust standard errors
Matches Stata's vce(robust) and vce(cluster id) output
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Optional, Union, Tuple
from dataclasses import dataclass


@dataclass
class RobustSEResult:
    """Results from robust standard error calculation"""
    se: np.ndarray  # Robust standard errors
    vcov: np.ndarray  # Variance-covariance matrix
    method: str  # HC0, HC1, HC2, HC3, cluster
    df_adjustment: float  # Degrees of freedom adjustment
    n_clusters: Optional[int] = None  # Number of clusters (if clustered)


class RobustStandardErrors:
    """
    Compute heteroskedasticity-robust and cluster-robust standard errors

    References:
    - White (1980): "A Heteroskedasticity-Consistent Covariance Matrix Estimator"
    - MacKinnon & White (1985): "Some heteroskedasticity-consistent covariance matrix estimators"
    - Cameron, Gelbach & Miller (2011): "Robust Inference with Multi-Way Clustering"
    """

    def __init__(self, X: np.ndarray, y: np.ndarray, residuals: np.ndarray,
                 beta: np.ndarray, cluster_id: Optional[np.ndarray] = None):
        """
        Args:
            X: Design matrix (n x k) including intercept
            y: Outcome vector (n x 1)
            residuals: Residuals from regression (n x 1)
            beta: Coefficient estimates (k x 1)
            cluster_id: Cluster identifiers (n x 1) for cluster-robust SE
        """
        self.X = X
        self.y = y
        self.residuals = residuals.flatten()
        self.beta = beta.flatten()
        self.cluster_id = cluster_id

        self.n = X.shape[0]  # Number of observations
        self.k = X.shape[1]  # Number of parameters
        self.df = self.n - self.k  # Degrees of freedom

        # Pre-compute X'X inverse for efficiency
        self.XtX_inv = np.linalg.inv(X.T @ X)

    def hc0(self) -> RobustSEResult:
        """
        HC0: White's heteroskedasticity-consistent estimator
        V = (X'X)^{-1} X' Ω X (X'X)^{-1}
        where Ω = diag(e_i^2)

        This is the basic robust estimator without small-sample correction.
        """
        # Ω = diag(e^2)
        Omega = np.diag(self.residuals ** 2)

        # Meat matrix: X' Ω X
        meat = self.X.T @ Omega @ self.X

        # Sandwich: (X'X)^{-1} X' Ω X (X'X)^{-1}
        vcov = self.XtX_inv @ meat @ self.XtX_inv

        se = np.sqrt(np.diag(vcov))

        return RobustSEResult(
            se=se,
            vcov=vcov,
            method="HC0",
            df_adjustment=1.0
        )

    def hc1(self) -> RobustSEResult:
        """
        HC1: Degrees of freedom correction
        V = (n/(n-k)) * HC0

        This is Stata's default vce(robust) estimator.
        Provides better small-sample properties than HC0.
        """
        hc0_result = self.hc0()

        # Small-sample adjustment
        adj = self.n / self.df

        vcov = adj * hc0_result.vcov
        se = np.sqrt(np.diag(vcov))

        return RobustSEResult(
            se=se,
            vcov=vcov,
            method="HC1",
            df_adjustment=adj
        )

    def hc2(self) -> RobustSEResult:
        """
        HC2: Leverage-weighted estimator
        V = (X'X)^{-1} X' Ω X (X'X)^{-1}
        where Ω = diag(e_i^2 / (1 - h_i))
        and h_i is the leverage (hat matrix diagonal)

        More robust to high-leverage observations.
        """
        # Compute leverage (hat matrix diagonal)
        # h_i = X_i (X'X)^{-1} X_i'
        leverage = np.sum((self.X @ self.XtX_inv) * self.X, axis=1)

        # Ω = diag(e^2 / (1 - h))
        weights = self.residuals ** 2 / (1 - leverage)
        Omega = np.diag(weights)

        # Sandwich
        meat = self.X.T @ Omega @ self.X
        vcov = self.XtX_inv @ meat @ self.XtX_inv

        se = np.sqrt(np.diag(vcov))

        return RobustSEResult(
            se=se,
            vcov=vcov,
            method="HC2",
            df_adjustment=1.0
        )

    def hc3(self) -> RobustSEResult:
        """
        HC3: Jackknife estimator (most conservative)
        V = (X'X)^{-1} X' Ω X (X'X)^{-1}
        where Ω = diag(e_i^2 / (1 - h_i)^2)

        Recommended for small samples and high leverage points.
        Most conservative HC estimator.
        """
        # Compute leverage
        leverage = np.sum((self.X @ self.XtX_inv) * self.X, axis=1)

        # Ω = diag(e^2 / (1 - h)^2)
        weights = self.residuals ** 2 / (1 - leverage) ** 2
        Omega = np.diag(weights)

        # Sandwich
        meat = self.X.T @ Omega @ self.X
        vcov = self.XtX_inv @ meat @ self.XtX_inv

        se = np.sqrt(np.diag(vcov))

        return RobustSEResult(
            se=se,
            vcov=vcov,
            method="HC3",
            df_adjustment=1.0
        )

    def cluster_robust(self, df_correction: bool = True) -> RobustSEResult:
        """
        Cluster-Robust Standard Errors (one-way clustering)
        V = (X'X)^{-1} (∑_g X_g' e_g e_g' X_g) (X'X)^{-1}
        where g indexes clusters

        Args:
            df_correction: Apply small-sample correction (G/(G-1) * (n-1)/(n-k))
                          Matches Stata's vce(cluster id)

        References:
        - Cameron & Miller (2015): "A Practitioner's Guide to Cluster-Robust Inference"
        """
        if self.cluster_id is None:
            raise ValueError("cluster_id must be provided for cluster-robust SE")

        # Get unique clusters
        unique_clusters = np.unique(self.cluster_id)
        G = len(unique_clusters)  # Number of clusters

        # Compute cluster-robust meat matrix
        meat = np.zeros((self.k, self.k))

        for g in unique_clusters:
            # Get observations in this cluster
            cluster_mask = (self.cluster_id == g)
            X_g = self.X[cluster_mask]
            e_g = self.residuals[cluster_mask].reshape(-1, 1)

            # Add to meat: X_g' e_g e_g' X_g
            meat += (X_g.T @ e_g) @ (e_g.T @ X_g)

        # Small-sample correction (matches Stata)
        if df_correction:
            adj = (G / (G - 1)) * ((self.n - 1) / self.df)
            meat *= adj
        else:
            adj = 1.0

        # Sandwich
        vcov = self.XtX_inv @ meat @ self.XtX_inv

        se = np.sqrt(np.diag(vcov))

        return RobustSEResult(
            se=se,
            vcov=vcov,
            method="cluster",
            df_adjustment=adj if df_correction else 1.0,
            n_clusters=G
        )

    def two_way_cluster(self, cluster_id1: np.ndarray, cluster_id2: np.ndarray) -> RobustSEResult:
        """
        Two-Way Cluster-Robust Standard Errors
        V = V_1 + V_2 - V_12

        Args:
            cluster_id1: First cluster dimension (e.g., firm)
            cluster_id2: Second cluster dimension (e.g., time)

        Reference:
        - Cameron, Gelbach & Miller (2011)
        - Thompson (2011)
        """
        # Compute one-way clustered VCOVs
        se_obj1 = RobustStandardErrors(self.X, self.y, self.residuals, self.beta, cluster_id1)
        vcov1 = se_obj1.cluster_robust(df_correction=False).vcov

        se_obj2 = RobustStandardErrors(self.X, self.y, self.residuals, self.beta, cluster_id2)
        vcov2 = se_obj2.cluster_robust(df_correction=False).vcov

        # Interaction clustering
        interaction_cluster = np.array([f"{c1}_{c2}" for c1, c2 in zip(cluster_id1, cluster_id2)])
        se_obj12 = RobustStandardErrors(self.X, self.y, self.residuals, self.beta, interaction_cluster)
        vcov12 = se_obj12.cluster_robust(df_correction=False).vcov

        # Two-way formula: V = V_1 + V_2 - V_12
        vcov = vcov1 + vcov2 - vcov12

        se = np.sqrt(np.diag(vcov))

        G1 = len(np.unique(cluster_id1))
        G2 = len(np.unique(cluster_id2))

        return RobustSEResult(
            se=se,
            vcov=vcov,
            method="two_way_cluster",
            df_adjustment=1.0,
            n_clusters=min(G1, G2)  # Conservative: use smaller cluster count
        )


def compute_robust_se(X: np.ndarray, y: np.ndarray, beta: np.ndarray,
                     method: str = "HC1", cluster_id: Optional[np.ndarray] = None,
                     cluster_id2: Optional[np.ndarray] = None) -> RobustSEResult:
    """
    Convenience function to compute robust standard errors

    Args:
        X: Design matrix (n x k)
        y: Outcome vector (n x 1)
        beta: Coefficient estimates (k x 1)
        method: "HC0", "HC1", "HC2", "HC3", "cluster", "two_way_cluster"
        cluster_id: Cluster identifiers for one-way clustering
        cluster_id2: Second cluster dimension for two-way clustering

    Returns:
        RobustSEResult with standard errors and variance-covariance matrix

    Example:
        >>> X = np.column_stack([np.ones(100), np.random.randn(100, 3)])
        >>> y = X @ np.array([1, 2, -1, 0.5]) + np.random.randn(100)
        >>> beta = np.linalg.lstsq(X, y, rcond=None)[0]
        >>> result = compute_robust_se(X, y, beta, method="HC1")
        >>> print(result.se)  # Robust standard errors
    """
    # Compute residuals
    residuals = y - X @ beta

    # Create estimator object
    se_obj = RobustStandardErrors(X, y, residuals, beta, cluster_id)

    # Compute requested method
    if method.upper() == "HC0":
        return se_obj.hc0()
    elif method.upper() == "HC1":
        return se_obj.hc1()
    elif method.upper() == "HC2":
        return se_obj.hc2()
    elif method.upper() == "HC3":
        return se_obj.hc3()
    elif method.upper() == "CLUSTER":
        if cluster_id is None:
            raise ValueError("cluster_id required for cluster-robust SE")
        return se_obj.cluster_robust()
    elif method.upper() == "TWO_WAY_CLUSTER":
        if cluster_id is None or cluster_id2 is None:
            raise ValueError("Both cluster_id and cluster_id2 required for two-way clustering")
        return se_obj.two_way_cluster(cluster_id, cluster_id2)
    else:
        raise ValueError(f"Unknown method: {method}. Use HC0, HC1, HC2, HC3, cluster, or two_way_cluster")


def t_test(beta: float, se: float, df: int, null_value: float = 0.0) -> Tuple[float, float]:
    """
    Compute t-statistic and two-sided p-value

    Args:
        beta: Coefficient estimate
        se: Standard error
        df: Degrees of freedom
        null_value: Null hypothesis value (default: 0)

    Returns:
        (t_stat, p_value)
    """
    from scipy import stats

    t_stat = (beta - null_value) / se
    p_value = 2 * (1 - stats.t.cdf(abs(t_stat), df=df))

    return t_stat, p_value


def confidence_interval(beta: float, se: float, df: int, alpha: float = 0.05) -> Tuple[float, float]:
    """
    Compute confidence interval

    Args:
        beta: Coefficient estimate
        se: Standard error
        df: Degrees of freedom
        alpha: Significance level (default: 0.05 for 95% CI)

    Returns:
        (lower, upper) confidence bounds
    """
    from scipy import stats

    t_crit = stats.t.ppf(1 - alpha/2, df=df)
    lower = beta - t_crit * se
    upper = beta + t_crit * se

    return lower, upper


# Testing/validation against Stata
if __name__ == "__main__":
    """
    Test against Stata output

    Stata code:
    ```stata
    sysuse auto, clear
    reg price mpg weight foreign, vce(robust)
    ```
    """
    np.random.seed(42)

    # Simulate data
    n = 100
    X = np.column_stack([
        np.ones(n),  # Intercept
        np.random.randn(n),  # x1
        np.random.randn(n),  # x2
        np.random.binomial(1, 0.5, n)  # x3 (binary)
    ])

    # True coefficients
    true_beta = np.array([1.0, 2.0, -1.5, 0.8])

    # Generate heteroskedastic errors
    sigma = 1 + 0.5 * X[:, 1]**2  # Variance depends on x1
    errors = np.random.randn(n) * sigma

    y = X @ true_beta + errors

    # OLS estimation
    beta_ols = np.linalg.lstsq(X, y, rcond=None)[0]

    # Test all HC methods
    print("=" * 60)
    print("Heteroskedasticity-Robust Standard Errors")
    print("=" * 60)

    for method in ["HC0", "HC1", "HC2", "HC3"]:
        result = compute_robust_se(X, y, beta_ols, method=method)
        print(f"\n{method}:")
        print(f"  Coefficients: {beta_ols}")
        print(f"  Std. Errors:  {result.se}")
        print(f"  DF Adjustment: {result.df_adjustment:.4f}")

    # Test cluster-robust
    print("\n" + "=" * 60)
    print("Cluster-Robust Standard Errors")
    print("=" * 60)

    # Generate cluster structure
    n_clusters = 20
    cluster_id = np.random.randint(0, n_clusters, size=n)

    result_cluster = compute_robust_se(X, y, beta_ols, method="cluster", cluster_id=cluster_id)
    print(f"\nOne-Way Clustering:")
    print(f"  Number of clusters: {result_cluster.n_clusters}")
    print(f"  Std. Errors: {result_cluster.se}")

    # Compute t-statistics and p-values
    print("\n" + "=" * 60)
    print("Inference (HC1)")
    print("=" * 60)

    result_hc1 = compute_robust_se(X, y, beta_ols, method="HC1")
    df = n - X.shape[1]

    for i, (b, se) in enumerate(zip(beta_ols, result_hc1.se)):
        t_stat, p_val = t_test(b, se, df)
        ci_lower, ci_upper = confidence_interval(b, se, df)
        print(f"\nCoef {i}: {b:.4f}")
        print(f"  SE:      {se:.4f}")
        print(f"  t-stat:  {t_stat:.4f}")
        print(f"  p-value: {p_val:.4f}")
        print(f"  95% CI:  [{ci_lower:.4f}, {ci_upper:.4f}]")
