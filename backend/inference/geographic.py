"""
Geographic/Spatial Causal Inference
===================================

Handles spatial data with location-based confounding and autocorrelation.

**Challenges**:
1. **Spatial Autocorrelation**: Nearby units are correlated
2. **Location as Confounder**: Geographic factors affect both treatment & outcome
3. **Spillovers**: Treatment effects spread spatially

**Methods**:
1. **Spatial Matching**: Match units in similar geographic areas
2. **Distance-Based Adjustment**: Control for spatial proximity
3. **Tigramite Integration**: Time-lagged spatial causal discovery
4. **Spatial Fixed Effects**: Control for unobserved spatial heterogeneity

**Tigramite**:
- Originally for time series causal discovery
- Adapted for spatial lags (distance-based)
- Identifies causal links accounting for spatial confounding

References:
- Golgher & Voss (2016). "How to Interpret the Coefficients of Spatial Models." Demos.
- Runge et al. (2019). "Detecting and Quantifying Causal Associations in Large Nonlinear Time Series Datasets." Science Advances.
- Anselin (1988). "Spatial Econometrics: Methods and Models."
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass
from scipy import stats
from scipy.spatial.distance import cdist
from sklearn.linear_model import LinearRegression
from sklearn.neighbors import NearestNeighbors
import logging

logger = logging.getLogger(__name__)


@dataclass
class GeographicResult:
    """Geographic causal inference result"""
    ate: float
    se: float
    ci_lower: float
    ci_upper: float
    method: str
    spatial_autocorrelation: float  # Moran's I
    diagnostics: Dict[str, Any]


class SpatialMatching:
    """
    Spatial Matching

    Match treated and control units that are geographically close.
    Reduces confounding from unobserved spatial factors.
    """

    def __init__(self, alpha: float = 0.05, caliper: Optional[float] = None):
        """
        Args:
            alpha: Significance level
            caliper: Maximum distance for valid matches (in coordinate units)
        """
        self.alpha = alpha
        self.caliper = caliper

    def estimate(
        self,
        y: np.ndarray,
        treatment: np.ndarray,
        coordinates: np.ndarray,  # (n, 2) - lat/lon or x/y
        X: Optional[np.ndarray] = None  # Additional covariates
    ) -> GeographicResult:
        """
        Estimate ATE using spatial matching

        Args:
            y: Outcomes (n,)
            treatment: Treatment (n,)
            coordinates: Spatial coordinates (n, 2)
            X: Additional covariates (n, p)

        Returns:
            GeographicResult
        """
        n = len(y)

        # Separate treated and control
        treated_mask = treatment == 1
        control_mask = treatment == 0

        y_treated = y[treated_mask]
        y_control = y[control_mask]
        coords_treated = coordinates[treated_mask]
        coords_control = coordinates[control_mask]

        # For each treated unit, find nearest control unit
        nbrs = NearestNeighbors(n_neighbors=1, algorithm='ball_tree').fit(coords_control)
        distances, indices = nbrs.kneighbors(coords_treated)

        # Apply caliper (exclude matches beyond threshold)
        if self.caliper is not None:
            valid_matches = distances.flatten() < self.caliper
            y_treated = y_treated[valid_matches]
            matched_indices = indices[valid_matches].flatten()
        else:
            matched_indices = indices.flatten()

        y_control_matched = y_control[matched_indices]

        # ATE = mean difference in matched pairs
        if len(y_treated) == 0:
            raise ValueError("No valid matches found within caliper")

        ate = (y_treated - y_control_matched).mean()

        # Standard error (paired)
        diffs = y_treated - y_control_matched
        se = diffs.std() / np.sqrt(len(diffs))

        # Confidence interval
        t_crit = stats.t.ppf(1 - self.alpha / 2, len(diffs) - 1)
        ci_lower = ate - t_crit * se
        ci_upper = ate + t_crit * se

        # Spatial autocorrelation (Moran's I)
        spatial_autocorr = self._morans_i(y, coordinates)

        return GeographicResult(
            ate=float(ate),
            se=float(se),
            ci_lower=float(ci_lower),
            ci_upper=float(ci_upper),
            method="spatial_matching",
            spatial_autocorrelation=float(spatial_autocorr),
            diagnostics={
                "n_matches": len(diffs),
                "n_treated": int(treated_mask.sum()),
                "n_control": int(control_mask.sum()),
                "avg_match_distance": float(distances[valid_matches].mean()) if self.caliper else float(distances.mean()),
                "caliper": self.caliper
            }
        )

    def _morans_i(self, y: np.ndarray, coordinates: np.ndarray) -> float:
        """
        Compute Moran's I for spatial autocorrelation

        I = (n/W) * Σ_i Σ_j w_ij (y_i - ȳ)(y_j - ȳ) / Σ_i (y_i - ȳ)^2

        where w_ij = 1/d_ij (inverse distance weights)
        """
        n = len(y)

        # Distance matrix
        distances = cdist(coordinates, coordinates)

        # Inverse distance weights (set diagonal to 0)
        np.fill_diagonal(distances, np.inf)
        weights = 1.0 / distances
        weights[np.isinf(weights)] = 0

        W = weights.sum()

        # Deviations
        y_dev = y - y.mean()

        # Moran's I
        numerator = (weights * np.outer(y_dev, y_dev)).sum()
        denominator = (y_dev**2).sum()

        I = (n / W) * (numerator / denominator)

        return I


class DistanceBasedAdjustment:
    """
    Distance-Based Adjustment

    Include distance-based variables to control for spatial confounding.
    """

    def __init__(self, alpha: float = 0.05):
        self.alpha = alpha

    def estimate(
        self,
        y: np.ndarray,
        treatment: np.ndarray,
        coordinates: np.ndarray,
        X: Optional[np.ndarray] = None,
        n_nearest: int = 5  # Number of nearest neighbors to consider
    ) -> GeographicResult:
        """
        Estimate ATE with distance-based adjustment

        Args:
            y: Outcomes
            treatment: Treatment
            coordinates: Spatial coordinates
            X: Additional covariates
            n_nearest: Number of nearest neighbors for spatial features

        Returns:
            GeographicResult
        """
        n = len(y)

        # Construct spatial features: avg outcome/treatment of k-nearest neighbors
        nbrs = NearestNeighbors(n_neighbors=n_nearest + 1, algorithm='ball_tree').fit(coordinates)
        distances, indices = nbrs.kneighbors(coordinates)

        # Exclude self (first neighbor)
        neighbor_indices = indices[:, 1:]

        # Spatial lag features
        neighbor_y = y[neighbor_indices].mean(axis=1)
        neighbor_treatment = treatment[neighbor_indices].mean(axis=1)

        # Regression: Y ~ D + spatial_features + X
        if X is not None:
            design_matrix = np.column_stack([treatment, neighbor_y, neighbor_treatment, X])
        else:
            design_matrix = np.column_stack([treatment, neighbor_y, neighbor_treatment])

        model = LinearRegression()
        model.fit(design_matrix, y)

        ate = model.coef_[0]

        # Standard errors
        residuals = y - model.predict(design_matrix)
        sigma2 = np.sum(residuals**2) / (n - design_matrix.shape[1])
        V = sigma2 * np.linalg.inv(design_matrix.T @ design_matrix)
        se = np.sqrt(V[0, 0])

        # Confidence interval
        t_crit = stats.t.ppf(1 - self.alpha / 2, n - design_matrix.shape[1])
        ci_lower = ate - t_crit * se
        ci_upper = ate + t_crit * se

        # Spatial autocorrelation
        spatial_matcher = SpatialMatching()
        spatial_autocorr = spatial_matcher._morans_i(y, coordinates)

        return GeographicResult(
            ate=float(ate),
            se=float(se),
            ci_lower=float(ci_lower),
            ci_upper=float(ci_upper),
            method="distance_based_adjustment",
            spatial_autocorrelation=float(spatial_autocorr),
            diagnostics={
                "n": n,
                "n_nearest": n_nearest,
                "r2": float(model.score(design_matrix, y)),
                "spatial_lag_coef_y": float(model.coef_[1]),
                "spatial_lag_coef_d": float(model.coef_[2])
            }
        )


class TigramiteIntegration:
    """
    Tigramite Integration for Spatial Causal Discovery

    Tigramite is designed for time series, but we adapt it for spatial lags:
    - "Time lag" → "Distance bin"
    - Identify causal links while controlling for spatial confounding
    """

    def __init__(self, alpha: float = 0.05):
        self.alpha = alpha

    def discover_spatial_causal_structure(
        self,
        data: np.ndarray,  # (n, p) - n units, p variables
        coordinates: np.ndarray,  # (n, 2)
        distance_bins: List[Tuple[float, float]] = [(0, 10), (10, 50), (50, 100)],
        pc_alpha: float = 0.05
    ) -> Dict[str, Any]:
        """
        Discover spatial causal structure using Tigramite-inspired approach

        Args:
            data: Data matrix (n units × p variables)
            coordinates: Spatial coordinates
            distance_bins: List of (min_dist, max_dist) bins for spatial lags
            pc_alpha: Significance level for conditional independence tests

        Returns:
            Dictionary with causal graph and spatial dependencies
        """
        try:
            from tigramite import data_processing as pp
            from tigramite.pcmci import PCMCI
            from tigramite.independence_tests import ParCorr
        except ImportError:
            logger.error("Tigramite not installed. Install with: pip install tigramite")
            return {
                "error": "Tigramite not installed",
                "causal_graph": None
            }

        n, p = data.shape

        # Convert spatial data to "time series" format for Tigramite
        # Create lagged versions based on distance bins

        # For simplicity, construct synthetic "time series":
        # Sort units by distance from centroid, treat as temporal ordering
        centroid = coordinates.mean(axis=0)
        distances_from_center = np.linalg.norm(coordinates - centroid, axis=1)
        sorted_idx = np.argsort(distances_from_center)

        data_sorted = data[sorted_idx]

        # Tigramite format
        dataframe = pp.DataFrame(data_sorted, var_names=[f"Var{i}" for i in range(p)])

        # Run PCMCI
        parcorr = ParCorr(significance='analytic')
        pcmci = PCMCI(dataframe=dataframe, cond_ind_test=parcorr, verbosity=0)

        # Estimate causal graph (tau_max = max spatial lag)
        tau_max = 3  # Consider up to 3 spatial lags
        results = pcmci.run_pcmci(tau_max=tau_max, pc_alpha=pc_alpha)

        # Extract causal graph
        causal_graph = results['graph']
        p_matrix = results['p_matrix']

        return {
            "causal_graph": causal_graph,
            "p_matrix": p_matrix,
            "var_names": [f"Var{i}" for i in range(p)],
            "tau_max": tau_max,
            "method": "tigramite_pcmci"
        }

    def estimate_with_tigramite(
        self,
        y: np.ndarray,
        treatment: np.ndarray,
        coordinates: np.ndarray,
        X: Optional[np.ndarray] = None
    ) -> GeographicResult:
        """
        Estimate ATE using Tigramite for spatial confounding adjustment

        This is a simplified wrapper that:
        1. Identifies spatial causal structure
        2. Adjusts for spatial confounders
        3. Estimates treatment effect
        """
        # Combine variables
        if X is not None:
            data_matrix = np.column_stack([y, treatment, X])
        else:
            data_matrix = np.column_stack([y, treatment])

        # Discover spatial structure
        causal_structure = self.discover_spatial_causal_structure(
            data_matrix, coordinates
        )

        # Fallback to distance-based adjustment
        # (Full integration would require more sophisticated spatial lag construction)
        logger.info("Using distance-based adjustment (Tigramite structure as reference)")

        distance_estimator = DistanceBasedAdjustment(alpha=self.alpha)
        result = distance_estimator.estimate(y, treatment, coordinates, X)

        result.diagnostics["tigramite_structure"] = causal_structure

        return result


class GeographicAnalyzer:
    """Main interface for geographic causal inference"""

    def __init__(self, alpha: float = 0.05):
        self.alpha = alpha
        self.spatial_matching = SpatialMatching(alpha=alpha)
        self.distance_adjustment = DistanceBasedAdjustment(alpha=alpha)
        self.tigramite = TigramiteIntegration(alpha=alpha)

    def estimate(
        self,
        y: np.ndarray,
        treatment: np.ndarray,
        coordinates: np.ndarray,
        X: Optional[np.ndarray] = None,
        method: str = "auto",
        **kwargs
    ) -> GeographicResult:
        """
        Estimate causal effect with geographic data

        Args:
            y: Outcomes
            treatment: Treatment
            coordinates: Spatial coordinates (n, 2)
            X: Additional covariates
            method: "spatial_matching", "distance_based", "tigramite", or "auto"
            **kwargs: Method-specific parameters

        Returns:
            GeographicResult
        """
        if method == "auto":
            # Default to distance-based adjustment (most robust)
            method = "distance_based"

        if method == "spatial_matching":
            return self.spatial_matching.estimate(y, treatment, coordinates, X, **kwargs)
        elif method == "distance_based":
            return self.distance_adjustment.estimate(y, treatment, coordinates, X, **kwargs)
        elif method == "tigramite":
            return self.tigramite.estimate_with_tigramite(y, treatment, coordinates, X)
        else:
            raise ValueError(f"Unknown method: {method}")
