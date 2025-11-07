# backend/inference/bootstrap.py
"""
Bootstrap Inference for Causal Inference
Implements pairs bootstrap, wild bootstrap, and block bootstrap
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Callable, Optional, Tuple, Dict, Any
from dataclasses import dataclass
from concurrent.futures import ProcessPoolExecutor
import warnings


@dataclass
class BootstrapResult:
    """Results from bootstrap inference"""
    estimate: float  # Point estimate
    se: float  # Bootstrap standard error
    ci_lower: float  # Lower confidence bound
    ci_upper: float  # Upper confidence bound
    ci_method: str  # CI method (percentile, normal, basic, bca)
    bootstrap_dist: np.ndarray  # Bootstrap distribution
    n_boot: int  # Number of bootstrap replications
    alpha: float  # Significance level
    method: str  # Bootstrap method (pairs, wild, block)


class BootstrapInference:
    """
    Bootstrap methods for causal inference

    References:
    - Efron & Tibshirani (1993): "An Introduction to the Bootstrap"
    - Cameron & Trivedi (2005): "Microeconometrics"
    - MacKinnon (2002): "Bootstrap Inference in Econometrics"
    """

    @staticmethod
    def pairs_bootstrap(
        X: np.ndarray,
        y: np.ndarray,
        estimator: Callable,
        n_boot: int = 1000,
        alpha: float = 0.05,
        ci_method: str = "percentile",
        seed: Optional[int] = None,
        parallel: bool = False
    ) -> BootstrapResult:
        """
        Pairs Bootstrap: Resample (X_i, y_i) pairs with replacement

        Most common bootstrap method. Valid under general conditions.
        Preserves relationship between X and y.

        Args:
            X: Covariates (n x k)
            y: Outcome (n x 1)
            estimator: Function that takes (X, y) and returns scalar estimate
            n_boot: Number of bootstrap replications (default: 1000)
            alpha: Significance level for CI (default: 0.05)
            ci_method: "percentile", "normal", "basic", or "bca"
            seed: Random seed for reproducibility
            parallel: Use parallel processing (multiprocessing)

        Returns:
            BootstrapResult with SE and confidence intervals
        """
        if seed is not None:
            np.random.seed(seed)

        n = len(y)

        # Point estimate
        point_estimate = estimator(X, y)

        # Bootstrap replications
        if parallel:
            bootstrap_estimates = BootstrapInference._pairs_bootstrap_parallel(
                X, y, estimator, n_boot, n
            )
        else:
            bootstrap_estimates = np.zeros(n_boot)
            for b in range(n_boot):
                # Resample indices with replacement
                indices = np.random.choice(n, size=n, replace=True)
                X_boot = X[indices]
                y_boot = y[indices]

                # Compute estimate on bootstrap sample
                bootstrap_estimates[b] = estimator(X_boot, y_boot)

        # Bootstrap standard error
        se = np.std(bootstrap_estimates, ddof=1)

        # Confidence intervals
        ci_lower, ci_upper = BootstrapInference._compute_ci(
            point_estimate, bootstrap_estimates, alpha, ci_method, X, y, estimator
        )

        return BootstrapResult(
            estimate=point_estimate,
            se=se,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            ci_method=ci_method,
            bootstrap_dist=bootstrap_estimates,
            n_boot=n_boot,
            alpha=alpha,
            method="pairs"
        )

    @staticmethod
    def _pairs_bootstrap_parallel(X, y, estimator, n_boot, n):
        """Helper for parallel pairs bootstrap"""
        def single_bootstrap(_):
            indices = np.random.choice(n, size=n, replace=True)
            return estimator(X[indices], y[indices])

        with ProcessPoolExecutor() as executor:
            bootstrap_estimates = list(executor.map(single_bootstrap, range(n_boot)))

        return np.array(bootstrap_estimates)

    @staticmethod
    def wild_bootstrap(
        X: np.ndarray,
        y: np.ndarray,
        residuals: np.ndarray,
        beta: np.ndarray,
        n_boot: int = 1000,
        alpha: float = 0.05,
        distribution: str = "rademacher",
        seed: Optional[int] = None
    ) -> Dict[str, BootstrapResult]:
        """
        Wild Bootstrap: Multiply residuals by random weights

        Recommended for heteroskedastic errors. Does not assume IID errors.
        Particularly useful for clustered/panel data.

        y* = X*β + e_i * w_i

        where w_i ~ F (Rademacher or Mammen distribution)

        Args:
            X: Covariates (n x k)
            y: Outcome (n x 1)
            residuals: Residuals from original regression (n x 1)
            beta: Coefficient estimates (k x 1)
            n_boot: Number of bootstrap replications
            alpha: Significance level
            distribution: "rademacher" (default) or "mammen"
            seed: Random seed

        Returns:
            Dict of BootstrapResult for each coefficient

        Reference:
        - Cameron, Gelbach & Miller (2008): "Bootstrap-based improvements for inference"
        """
        if seed is not None:
            np.random.seed(seed)

        n, k = X.shape

        # Bootstrap replications
        beta_boot = np.zeros((n_boot, k))

        for b in range(n_boot):
            # Generate random weights
            if distribution == "rademacher":
                # w_i = +1 or -1 with equal probability
                weights = np.random.choice([-1, 1], size=n)
            elif distribution == "mammen":
                # Two-point distribution (Mammen 1993)
                # w_i = -(√5-1)/2 with prob (√5+1)/(2√5)
                # w_i = (√5+1)/2 with prob (√5-1)/(2√5)
                sqrt5 = np.sqrt(5)
                prob = (sqrt5 + 1) / (2 * sqrt5)
                u = np.random.rand(n)
                weights = np.where(u < prob, -(sqrt5-1)/2, (sqrt5+1)/2)
            else:
                raise ValueError(f"Unknown distribution: {distribution}")

            # Bootstrap sample: y* = Xβ + e*w
            y_boot = X @ beta + residuals * weights

            # Re-estimate on bootstrap sample
            beta_boot[b] = np.linalg.lstsq(X, y_boot, rcond=None)[0]

        # Results for each coefficient
        results = {}
        for j in range(k):
            se = np.std(beta_boot[:, j], ddof=1)

            # Percentile CI
            ci_lower = np.percentile(beta_boot[:, j], 100 * alpha/2)
            ci_upper = np.percentile(beta_boot[:, j], 100 * (1 - alpha/2))

            results[f"coef_{j}"] = BootstrapResult(
                estimate=beta[j],
                se=se,
                ci_lower=ci_lower,
                ci_upper=ci_upper,
                ci_method="percentile",
                bootstrap_dist=beta_boot[:, j],
                n_boot=n_boot,
                alpha=alpha,
                method=f"wild_{distribution}"
            )

        return results

    @staticmethod
    def block_bootstrap(
        X: np.ndarray,
        y: np.ndarray,
        time_var: np.ndarray,
        estimator: Callable,
        block_length: int,
        n_boot: int = 1000,
        alpha: float = 0.05,
        ci_method: str = "percentile",
        seed: Optional[int] = None
    ) -> BootstrapResult:
        """
        Block Bootstrap: Resample contiguous blocks for time series data

        Preserves temporal dependence. Used for time series and panel data.

        Args:
            X: Covariates (n x k)
            y: Outcome (n x 1)
            time_var: Time period identifiers (n x 1)
            estimator: Function that takes (X, y) and returns estimate
            block_length: Length of each block (larger = more dependence preserved)
            n_boot: Number of bootstrap replications
            alpha: Significance level
            ci_method: Confidence interval method
            seed: Random seed

        Returns:
            BootstrapResult

        Reference:
        - Künsch (1989): "The jackknife and the bootstrap for general stationary observations"
        """
        if seed is not None:
            np.random.seed(seed)

        # Sort by time
        sort_idx = np.argsort(time_var)
        X_sorted = X[sort_idx]
        y_sorted = y[sort_idx]

        n = len(y)

        # Point estimate
        point_estimate = estimator(X, y)

        # Number of blocks
        n_blocks = int(np.ceil(n / block_length))

        # Bootstrap replications
        bootstrap_estimates = np.zeros(n_boot)

        for b in range(n_boot):
            # Sample blocks with replacement
            X_boot = []
            y_boot = []

            for _ in range(n_blocks):
                # Random starting point
                start_idx = np.random.randint(0, n - block_length + 1)
                end_idx = start_idx + block_length

                X_boot.append(X_sorted[start_idx:end_idx])
                y_boot.append(y_sorted[start_idx:end_idx])

            X_boot = np.vstack(X_boot)[:n]  # Truncate to original length
            y_boot = np.concatenate(y_boot)[:n]

            bootstrap_estimates[b] = estimator(X_boot, y_boot)

        # Bootstrap SE
        se = np.std(bootstrap_estimates, ddof=1)

        # CI
        ci_lower, ci_upper = BootstrapInference._compute_ci(
            point_estimate, bootstrap_estimates, alpha, ci_method, X, y, estimator
        )

        return BootstrapResult(
            estimate=point_estimate,
            se=se,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            ci_method=ci_method,
            bootstrap_dist=bootstrap_estimates,
            n_boot=n_boot,
            alpha=alpha,
            method=f"block_L{block_length}"
        )

    @staticmethod
    def stratified_bootstrap(
        X: np.ndarray,
        y: np.ndarray,
        strata: np.ndarray,
        estimator: Callable,
        n_boot: int = 1000,
        alpha: float = 0.05,
        seed: Optional[int] = None
    ) -> BootstrapResult:
        """
        Stratified Bootstrap: Preserve stratification structure

        Useful when treatment is assigned within strata (e.g., randomized blocks)

        Args:
            X: Covariates
            y: Outcome
            strata: Stratum identifiers
            estimator: Estimation function
            n_boot: Number of replications
            alpha: Significance level
            seed: Random seed

        Returns:
            BootstrapResult
        """
        if seed is not None:
            np.random.seed(seed)

        n = len(y)
        unique_strata = np.unique(strata)

        # Point estimate
        point_estimate = estimator(X, y)

        # Bootstrap
        bootstrap_estimates = np.zeros(n_boot)

        for b in range(n_boot):
            indices = []

            # Resample within each stratum
            for stratum in unique_strata:
                stratum_mask = (strata == stratum)
                stratum_indices = np.where(stratum_mask)[0]
                n_stratum = len(stratum_indices)

                # Resample with replacement within stratum
                boot_indices = np.random.choice(stratum_indices, size=n_stratum, replace=True)
                indices.extend(boot_indices)

            indices = np.array(indices)

            X_boot = X[indices]
            y_boot = y[indices]

            bootstrap_estimates[b] = estimator(X_boot, y_boot)

        # SE and CI
        se = np.std(bootstrap_estimates, ddof=1)
        ci_lower = np.percentile(bootstrap_estimates, 100 * alpha/2)
        ci_upper = np.percentile(bootstrap_estimates, 100 * (1 - alpha/2))

        return BootstrapResult(
            estimate=point_estimate,
            se=se,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            ci_method="percentile",
            bootstrap_dist=bootstrap_estimates,
            n_boot=n_boot,
            alpha=alpha,
            method="stratified"
        )

    @staticmethod
    def _compute_ci(
        point_estimate: float,
        bootstrap_dist: np.ndarray,
        alpha: float,
        method: str,
        X: Optional[np.ndarray] = None,
        y: Optional[np.ndarray] = None,
        estimator: Optional[Callable] = None
    ) -> Tuple[float, float]:
        """
        Compute confidence interval

        Methods:
        - percentile: θ_lower = F^{-1}(α/2), θ_upper = F^{-1}(1-α/2)
        - normal: θ ± z_{1-α/2} * SE_boot
        - basic: 2θ - F^{-1}(1-α/2), 2θ - F^{-1}(α/2)
        - bca: Bias-corrected and accelerated (requires estimator)
        """
        if method == "percentile":
            ci_lower = np.percentile(bootstrap_dist, 100 * alpha/2)
            ci_upper = np.percentile(bootstrap_dist, 100 * (1 - alpha/2))

        elif method == "normal":
            from scipy import stats
            se = np.std(bootstrap_dist, ddof=1)
            z_crit = stats.norm.ppf(1 - alpha/2)
            ci_lower = point_estimate - z_crit * se
            ci_upper = point_estimate + z_crit * se

        elif method == "basic":
            ci_lower = 2 * point_estimate - np.percentile(bootstrap_dist, 100 * (1 - alpha/2))
            ci_upper = 2 * point_estimate - np.percentile(bootstrap_dist, 100 * alpha/2)

        elif method == "bca":
            # BCa requires jackknife estimates
            if X is None or y is None or estimator is None:
                warnings.warn("BCa requires X, y, estimator. Falling back to percentile.")
                return BootstrapInference._compute_ci(point_estimate, bootstrap_dist, alpha, "percentile")

            n = len(y)

            # Jackknife estimates
            jack_estimates = np.zeros(n)
            for i in range(n):
                mask = np.ones(n, dtype=bool)
                mask[i] = False
                jack_estimates[i] = estimator(X[mask], y[mask])

            # Acceleration
            jack_mean = np.mean(jack_estimates)
            num = np.sum((jack_mean - jack_estimates)**3)
            den = 6 * (np.sum((jack_mean - jack_estimates)**2)**1.5)
            a = num / (den + 1e-10)  # Avoid division by zero

            # Bias correction
            from scipy import stats
            z0 = stats.norm.ppf(np.mean(bootstrap_dist < point_estimate))

            # Adjusted percentiles
            z_alpha = stats.norm.ppf(alpha/2)
            z_1alpha = stats.norm.ppf(1 - alpha/2)

            p_lower = stats.norm.cdf(z0 + (z0 + z_alpha) / (1 - a*(z0 + z_alpha)))
            p_upper = stats.norm.cdf(z0 + (z0 + z_1alpha) / (1 - a*(z0 + z_1alpha)))

            ci_lower = np.percentile(bootstrap_dist, 100 * p_lower)
            ci_upper = np.percentile(bootstrap_dist, 100 * p_upper)

        else:
            raise ValueError(f"Unknown CI method: {method}")

        return ci_lower, ci_upper


# Convenience functions
def bootstrap_ate(
    y: np.ndarray,
    treatment: np.ndarray,
    method: str = "pairs",
    n_boot: int = 1000,
    alpha: float = 0.05,
    cluster_id: Optional[np.ndarray] = None,
    seed: Optional[int] = None
) -> BootstrapResult:
    """
    Bootstrap inference for Average Treatment Effect (ATE)

    Args:
        y: Outcome
        treatment: Treatment indicator (0/1)
        method: "pairs" or "cluster" (cluster bootstrap)
        n_boot: Number of bootstrap replications
        alpha: Significance level
        cluster_id: Cluster identifiers (for cluster bootstrap)
        seed: Random seed

    Returns:
        BootstrapResult with ATE estimate, SE, and CI
    """
    def ate_estimator(X, y):
        """ATE = E[Y|T=1] - E[Y|T=0]"""
        t = X[:, 0]  # Treatment in first column
        return np.mean(y[t==1]) - np.mean(y[t==0])

    X = treatment.reshape(-1, 1)

    if method == "pairs":
        return BootstrapInference.pairs_bootstrap(X, y, ate_estimator, n_boot, alpha, seed=seed)
    elif method == "cluster":
        # Cluster bootstrap: resample clusters, not individuals
        if cluster_id is None:
            raise ValueError("cluster_id required for cluster bootstrap")

        unique_clusters = np.unique(cluster_id)
        G = len(unique_clusters)

        if seed is not None:
            np.random.seed(seed)

        point_estimate = ate_estimator(X, y)
        bootstrap_estimates = np.zeros(n_boot)

        for b in range(n_boot):
            # Resample clusters
            boot_clusters = np.random.choice(unique_clusters, size=G, replace=True)

            # Build bootstrap sample
            boot_indices = []
            for cluster in boot_clusters:
                cluster_indices = np.where(cluster_id == cluster)[0]
                boot_indices.extend(cluster_indices)

            boot_indices = np.array(boot_indices)
            X_boot = X[boot_indices]
            y_boot = y[boot_indices]

            bootstrap_estimates[b] = ate_estimator(X_boot, y_boot)

        se = np.std(bootstrap_estimates, ddof=1)
        ci_lower = np.percentile(bootstrap_estimates, 100 * alpha/2)
        ci_upper = np.percentile(bootstrap_estimates, 100 * (1 - alpha/2))

        return BootstrapResult(
            estimate=point_estimate,
            se=se,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            ci_method="percentile",
            bootstrap_dist=bootstrap_estimates,
            n_boot=n_boot,
            alpha=alpha,
            method="cluster_bootstrap"
        )
    else:
        raise ValueError(f"Unknown method: {method}")


# Testing
if __name__ == "__main__":
    """Test bootstrap methods"""
    np.random.seed(42)

    # Simulate data
    n = 200
    treatment = np.random.binomial(1, 0.5, n)
    y = 2 * treatment + np.random.randn(n) * (1 + 0.5 * treatment)  # Heteroskedastic

    print("=" * 60)
    print("Bootstrap Inference for ATE")
    print("=" * 60)

    # Pairs bootstrap
    result_pairs = bootstrap_ate(y, treatment, method="pairs", n_boot=1000, seed=42)
    print(f"\nPairs Bootstrap:")
    print(f"  ATE:       {result_pairs.estimate:.4f}")
    print(f"  SE:        {result_pairs.se:.4f}")
    print(f"  95% CI:    [{result_pairs.ci_lower:.4f}, {result_pairs.ci_upper:.4f}]")

    # Cluster bootstrap
    cluster_id = np.random.randint(0, 20, n)
    result_cluster = bootstrap_ate(y, treatment, method="cluster", cluster_id=cluster_id, n_boot=1000, seed=42)
    print(f"\nCluster Bootstrap:")
    print(f"  ATE:       {result_cluster.estimate:.4f}")
    print(f"  SE:        {result_cluster.se:.4f}")
    print(f"  95% CI:    [{result_cluster.ci_lower:.4f}, {result_cluster.ci_upper:.4f}]")

    print("\n" + "=" * 60)
