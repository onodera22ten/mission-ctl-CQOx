"""
Network/Spillover Effects
=========================

Causal inference when units are connected in a network.

**Challenges**:
- **Interference**: Treatment of i affects outcome of j
- **Spillovers**: Direct effects + indirect effects via network
- SUTVA violated!

**Effects to Estimate**:
1. **Direct Effect**: Effect of own treatment
2. **Spillover Effect**: Effect of neighbors' treatment
3. **Total Effect**: Direct + spillover

**Methods**:
1. **Horvitz-Thompson Estimator**
   - Exposure mapping: Define "exposure" based on network
   - Inverse probability weighting

2. **Linear-in-Means Model**
   - Y_i = α + β*D_i + γ*mean(D_neighbors) + ε_i

3. **Randomization Inference**
   - Permute treatment assignments respecting graph structure

References:
- Aronow & Samii (2017). "Estimating Average Causal Effects Under General Interference." AoAS.
- Ogburn et al. (2024). "Causal Inference for Social Network Data." JRSS-B.
- Hudgens & Halloran (2008). "Toward Causal Inference With Interference." JASA.
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
class NetworkResult:
    """Network effects estimation result"""
    direct_effect: float  # Own treatment effect
    spillover_effect: float  # Neighbor treatment effect
    total_effect: float  # Direct + spillover
    direct_se: float
    spillover_se: float
    method: str
    diagnostics: Dict[str, Any]


class HorvitzThompson:
    """
    Horvitz-Thompson Estimator for Network Effects

    Define exposure mappings based on network structure,
    then use IPW to estimate effects.
    """

    def __init__(self, alpha: float = 0.05):
        self.alpha = alpha

    def estimate(
        self,
        y: np.ndarray,
        treatment: np.ndarray,
        adjacency_matrix: np.ndarray,  # (n, n) - 1 if connected
        treatment_probs: Optional[np.ndarray] = None  # P(D_i = 1)
    ) -> NetworkResult:
        """
        Estimate network effects using Horvitz-Thompson

        Args:
            y: Outcomes (n,)
            treatment: Treatment indicators (n,)
            adjacency_matrix: Network adjacency (n, n)
            treatment_probs: Treatment assignment probabilities

        Returns:
            NetworkResult
        """
        n = len(y)

        # Compute exposure: (own treatment, fraction of treated neighbors)
        neighbor_treatment = self._compute_neighbor_treatment(treatment, adjacency_matrix)

        # Define exposure types
        # Simplification: 4 exposure types
        # (own=0, neighbors=0), (own=1, neighbors=0), (own=0, neighbors>0), (own=1, neighbors>0)

        exposure = np.zeros(n, dtype=int)
        exposure[(treatment == 0) & (neighbor_treatment == 0)] = 0  # No exposure
        exposure[(treatment == 1) & (neighbor_treatment == 0)] = 1  # Direct only
        exposure[(treatment == 0) & (neighbor_treatment > 0)] = 2  # Spillover only
        exposure[(treatment == 1) & (neighbor_treatment > 0)] = 3  # Direct + spillover

        # If treatment probs not provided, assume uniform randomization
        if treatment_probs is None:
            p_treat = treatment.mean()
            treatment_probs = np.full(n, p_treat)

        # Horvitz-Thompson weights
        # For simplicity: weight = 1 / P(exposure_i)
        # Proper implementation requires joint assignment probabilities

        # Estimate potential outcomes under each exposure
        y_means = {}
        for exp in range(4):
            mask = exposure == exp
            if mask.sum() > 0:
                # IPW estimate
                weights = 1.0 / (treatment_probs[mask] + 0.01)  # Simplified
                y_means[exp] = np.average(y[mask], weights=weights)
            else:
                y_means[exp] = 0.0

        # Direct effect: compare (1,0) vs (0,0)
        direct_effect = y_means.get(1, 0) - y_means.get(0, 0)

        # Spillover effect: compare (0,1) vs (0,0)  [neighbors treated vs not]
        # Approximation: (1,1) - (1,0)
        spillover_effect = y_means.get(3, 0) - y_means.get(1, 0)

        # Total effect: compare (1,1) vs (0,0)
        total_effect = y_means.get(3, 0) - y_means.get(0, 0)

        # Standard errors (bootstrap-based or analytical)
        # Simplified: use within-group variance
        direct_se = self._compute_se_for_exposure_diff(y, exposure, 1, 0)
        spillover_se = self._compute_se_for_exposure_diff(y, exposure, 3, 1)

        return NetworkResult(
            direct_effect=float(direct_effect),
            spillover_effect=float(spillover_effect),
            total_effect=float(total_effect),
            direct_se=float(direct_se),
            spillover_se=float(spillover_se),
            method="horvitz_thompson",
            diagnostics={
                "n": n,
                "n_edges": int(adjacency_matrix.sum()),
                "avg_degree": float(adjacency_matrix.sum(axis=1).mean()),
                "exposure_counts": {int(k): int((exposure == k).sum()) for k in range(4)}
            }
        )

    def _compute_neighbor_treatment(
        self,
        treatment: np.ndarray,
        adjacency_matrix: np.ndarray
    ) -> np.ndarray:
        """
        Compute fraction of treated neighbors for each unit

        Returns: array of shape (n,) with values in [0, 1]
        """
        n = len(treatment)
        neighbor_treatment = np.zeros(n)

        for i in range(n):
            neighbors = adjacency_matrix[i] > 0
            n_neighbors = neighbors.sum()

            if n_neighbors > 0:
                neighbor_treatment[i] = treatment[neighbors].mean()

        return neighbor_treatment

    def _compute_se_for_exposure_diff(
        self,
        y: np.ndarray,
        exposure: np.ndarray,
        exp1: int,
        exp2: int
    ) -> float:
        """Compute SE for difference between two exposure groups"""
        mask1 = exposure == exp1
        mask2 = exposure == exp2

        if mask1.sum() < 2 or mask2.sum() < 2:
            return 1.0  # Default

        var1 = y[mask1].var()
        var2 = y[mask2].var()
        n1 = mask1.sum()
        n2 = mask2.sum()

        se = np.sqrt(var1 / n1 + var2 / n2)

        return se


class LinearInMeans:
    """
    Linear-in-Means Model for Network Effects

    Y_i = α + β*D_i + γ*D_neighbors_i + X_i'δ + ε_i

    where D_neighbors_i = mean(D_j for j in neighbors(i))
    """

    def __init__(self, alpha: float = 0.05):
        self.alpha = alpha

    def estimate(
        self,
        y: np.ndarray,
        treatment: np.ndarray,
        adjacency_matrix: np.ndarray,
        X: Optional[np.ndarray] = None
    ) -> NetworkResult:
        """
        Estimate network effects using linear-in-means model

        Args:
            y: Outcomes (n,)
            treatment: Treatment (n,)
            adjacency_matrix: Adjacency matrix (n, n)
            X: Covariates (n, p)

        Returns:
            NetworkResult
        """
        n = len(y)

        # Compute neighbor treatment average
        ht_estimator = HorvitzThompson()
        neighbor_treatment = ht_estimator._compute_neighbor_treatment(treatment, adjacency_matrix)

        # Regression: Y ~ D + D_neighbors + X
        if X is not None:
            design_matrix = np.column_stack([treatment, neighbor_treatment, X])
        else:
            design_matrix = np.column_stack([treatment, neighbor_treatment])

        model = LinearRegression()
        model.fit(design_matrix, y)

        # Extract coefficients
        direct_effect = model.coef_[0]
        spillover_effect = model.coef_[1]
        total_effect = direct_effect + spillover_effect

        # Standard errors
        residuals = y - model.predict(design_matrix)
        sigma2 = np.sum(residuals**2) / (n - design_matrix.shape[1])
        V = sigma2 * np.linalg.inv(design_matrix.T @ design_matrix)

        direct_se = np.sqrt(V[0, 0])
        spillover_se = np.sqrt(V[1, 1])

        return NetworkResult(
            direct_effect=float(direct_effect),
            spillover_effect=float(spillover_effect),
            total_effect=float(total_effect),
            direct_se=float(direct_se),
            spillover_se=float(spillover_se),
            method="linear_in_means",
            diagnostics={
                "n": n,
                "r2": float(model.score(design_matrix, y)),
                "n_edges": int(adjacency_matrix.sum()),
                "avg_degree": float(adjacency_matrix.sum(axis=1).mean())
            }
        )


class NetworkAnalyzer:
    """Main interface for network effects analysis"""

    def __init__(self, alpha: float = 0.05):
        self.alpha = alpha
        self.ht = HorvitzThompson(alpha=alpha)
        self.lim = LinearInMeans(alpha=alpha)

    def estimate(
        self,
        y: np.ndarray,
        treatment: np.ndarray,
        adjacency_matrix: np.ndarray,
        X: Optional[np.ndarray] = None,
        method: str = "linear_in_means",
        treatment_probs: Optional[np.ndarray] = None
    ) -> NetworkResult:
        """
        Estimate network effects

        Args:
            y: Outcomes
            treatment: Treatment
            adjacency_matrix: Network structure (n, n)
            X: Covariates
            method: "horvitz_thompson" or "linear_in_means"
            treatment_probs: Treatment assignment probabilities (for HT)

        Returns:
            NetworkResult
        """
        if method == "horvitz_thompson":
            return self.ht.estimate(y, treatment, adjacency_matrix, treatment_probs)
        elif method == "linear_in_means":
            return self.lim.estimate(y, treatment, adjacency_matrix, X)
        else:
            raise ValueError(f"Unknown method: {method}")

    def construct_adjacency_from_distance(
        self,
        coordinates: np.ndarray,  # (n, 2) - lat/lon or x/y
        threshold: float
    ) -> np.ndarray:
        """
        Construct adjacency matrix from spatial coordinates

        Args:
            coordinates: (n, 2) array of coordinates
            threshold: Distance threshold for connection

        Returns:
            Adjacency matrix (n, n)
        """
        from scipy.spatial.distance import cdist

        distances = cdist(coordinates, coordinates)
        adjacency = (distances < threshold) & (distances > 0)  # Exclude self-loops

        return adjacency.astype(int)
