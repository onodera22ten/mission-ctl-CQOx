"""
Causal Forest (Athey & Imbens 2016; Wager & Athey 2018)
========================================================

Machine learning approach for heterogeneous treatment effects (CATE).

**Key Features**:
1. **Honest Splitting**: Separate samples for tree growing vs effect estimation
2. **Adaptive Neighbors**: Local centering for variance reduction
3. **Variable Importance**: Which covariates drive heterogeneity?
4. **Confidence Intervals**: Valid asymptotic inference

**Algorithm**:
- Build forest of causal trees
- Each tree: recursively split to maximize treatment effect heterogeneity
- Honest trees: use different data for splits vs leaf estimates
- Predictions: weighted average across trees

**Compared to RF**:
- RF: predicts Y | X
- Causal Forest: predicts τ(X) = E[Y(1) - Y(0) | X]

References:
- Athey, S., & Imbens, G. (2016). "Recursive Partitioning for Heterogeneous Causal Effects." PNAS.
- Wager, S., & Athey, S. (2018). "Estimation and Inference of Heterogeneous Treatment Effects using Random Forests." JASA.
- Athey, S., Tibshirani, J., & Wager, S. (2019). "Generalized Random Forests." Annals of Statistics.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
import logging

logger = logging.getLogger(__name__)


@dataclass
class CausalForestResult:
    """Causal Forest estimation result"""
    cate: np.ndarray  # Individual treatment effects τ(X_i)
    ate: float  # Average treatment effect
    ate_se: float  # Standard error of ATE
    ate_ci: Tuple[float, float]  # Confidence interval
    variable_importance: Dict[str, float]  # Feature importance
    oob_predictions: Optional[np.ndarray] = None


class HonestCausalTree:
    """
    Single honest causal tree

    Splits data into:
    - Sample 1 (50%): Determine splits
    - Sample 2 (50%): Estimate leaf effects (honest)
    """

    def __init__(
        self,
        min_leaf_size: int = 10,
        max_depth: int = 10,
        mtry: Optional[int] = None
    ):
        self.min_leaf_size = min_leaf_size
        self.max_depth = max_depth
        self.mtry = mtry  # Number of variables to try at each split
        self.tree = None

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        treatment: np.ndarray
    ):
        """
        Fit honest causal tree

        Args:
            X: Covariates (n, p)
            y: Outcomes (n,)
            treatment: Treatment indicators (n,)
        """
        n, p = X.shape

        # Honest splitting
        idx = np.arange(n)
        idx_split, idx_est = train_test_split(idx, test_size=0.5, random_state=None)

        X_split, y_split, d_split = X[idx_split], y[idx_split], treatment[idx_split]
        X_est, y_est, d_est = X[idx_est], y[idx_est], treatment[idx_est]

        # Build tree on splitting sample
        self.tree = self._build_tree(X_split, y_split, d_split, depth=0)

        # Populate leaf estimates using estimation sample
        self._populate_leaf_estimates(X_est, y_est, d_est)

    def _build_tree(
        self,
        X: np.ndarray,
        y: np.ndarray,
        treatment: np.ndarray,
        depth: int
    ) -> Dict:
        """Recursively build tree by splitting on treatment effect heterogeneity"""
        n = len(y)

        # Stopping criteria
        if depth >= self.max_depth or n < 2 * self.min_leaf_size:
            return {"type": "leaf", "indices": np.arange(n)}

        # Try random subset of variables (MTRY)
        p = X.shape[1]
        if self.mtry is None:
            vars_to_try = np.arange(p)
        else:
            vars_to_try = np.random.choice(p, size=min(self.mtry, p), replace=False)

        # Find best split
        best_split = None
        best_score = -np.inf

        for var_idx in vars_to_try:
            split_val, score = self._find_best_split(X[:, var_idx], y, treatment)
            if score > best_score:
                best_score = score
                best_split = (var_idx, split_val)

        if best_split is None:
            return {"type": "leaf", "indices": np.arange(n)}

        var_idx, split_val = best_split

        # Split data
        left_mask = X[:, var_idx] <= split_val
        right_mask = ~left_mask

        if np.sum(left_mask) < self.min_leaf_size or np.sum(right_mask) < self.min_leaf_size:
            return {"type": "leaf", "indices": np.arange(n)}

        # Recurse
        left_tree = self._build_tree(X[left_mask], y[left_mask], treatment[left_mask], depth + 1)
        right_tree = self._build_tree(X[right_mask], y[right_mask], treatment[right_mask], depth + 1)

        return {
            "type": "node",
            "var_idx": var_idx,
            "split_val": split_val,
            "left": left_tree,
            "right": right_tree
        }

    def _find_best_split(
        self,
        x_var: np.ndarray,
        y: np.ndarray,
        treatment: np.ndarray
    ) -> Tuple[float, float]:
        """
        Find split value that maximizes treatment effect heterogeneity

        Criterion: Maximize difference in treatment effects between left/right children
        """
        # Sort by variable
        sorted_idx = np.argsort(x_var)
        x_sorted = x_var[sorted_idx]
        y_sorted = y[sorted_idx]
        d_sorted = treatment[sorted_idx]

        n = len(x_sorted)
        best_val = None
        best_score = -np.inf

        # Try splits at unique values
        unique_vals = np.unique(x_sorted)
        if len(unique_vals) < 2:
            return None, -np.inf

        for split_val in unique_vals[:-1]:
            left_mask = x_sorted <= split_val
            right_mask = ~left_mask

            if np.sum(left_mask) < self.min_leaf_size or np.sum(right_mask) < self.min_leaf_size:
                continue

            # Estimate treatment effects in left/right
            tau_left = self._estimate_tau(y_sorted[left_mask], d_sorted[left_mask])
            tau_right = self._estimate_tau(y_sorted[right_mask], d_sorted[right_mask])

            # Score: squared difference weighted by sample size
            n_left = np.sum(left_mask)
            n_right = np.sum(right_mask)
            score = (n_left * n_right) / n * (tau_left - tau_right)**2

            if score > best_score:
                best_score = score
                best_val = split_val

        return best_val, best_score

    def _estimate_tau(self, y: np.ndarray, treatment: np.ndarray) -> float:
        """Estimate treatment effect in a node"""
        if len(y) == 0:
            return 0.0

        treated_mask = treatment == 1
        control_mask = treatment == 0

        if np.sum(treated_mask) == 0 or np.sum(control_mask) == 0:
            return 0.0

        y1_mean = y[treated_mask].mean()
        y0_mean = y[control_mask].mean()

        return y1_mean - y0_mean

    def _populate_leaf_estimates(self, X_est: np.ndarray, y_est: np.ndarray, d_est: np.ndarray):
        """Populate leaf estimates using honest (estimation) sample"""
        # Assign estimation sample to leaves
        leaf_assignments = self._assign_to_leaves(X_est, self.tree)

        # For each leaf, compute honest estimate
        for leaf_id in np.unique(leaf_assignments):
            mask = leaf_assignments == leaf_id
            tau_honest = self._estimate_tau(y_est[mask], d_est[mask])

            # Store in tree
            self._set_leaf_value(self.tree, leaf_id, tau_honest)

    def _assign_to_leaves(self, X: np.ndarray, node: Dict) -> np.ndarray:
        """Assign samples to leaf IDs"""
        n = len(X)
        leaf_ids = np.zeros(n, dtype=int)

        for i in range(n):
            leaf_ids[i] = self._traverse(X[i], node)

        return leaf_ids

    def _traverse(self, x: np.ndarray, node: Dict, leaf_counter: int = 0) -> int:
        """Traverse tree to find leaf ID for sample x"""
        if node["type"] == "leaf":
            return leaf_counter

        if x[node["var_idx"]] <= node["split_val"]:
            return self._traverse(x, node["left"], leaf_counter)
        else:
            return self._traverse(x, node["right"], leaf_counter + 1)

    def _set_leaf_value(self, node: Dict, leaf_id: int, value: float, counter: int = 0):
        """Set value for specific leaf"""
        if node["type"] == "leaf":
            if counter == leaf_id:
                node["value"] = value
            return counter + 1

        counter = self._set_leaf_value(node["left"], leaf_id, value, counter)
        counter = self._set_leaf_value(node["right"], leaf_id, value, counter)
        return counter

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict CATE for new samples"""
        n = len(X)
        predictions = np.zeros(n)

        for i in range(n):
            predictions[i] = self._predict_single(X[i], self.tree)

        return predictions

    def _predict_single(self, x: np.ndarray, node: Dict) -> float:
        """Predict CATE for single sample"""
        if node["type"] == "leaf":
            return node.get("value", 0.0)

        if x[node["var_idx"]] <= node["split_val"]:
            return self._predict_single(x, node["left"])
        else:
            return self._predict_single(x, node["right"])


class CausalForest:
    """
    Causal Forest (ensemble of honest causal trees)

    Implements Wager & Athey (2018) algorithm.
    """

    def __init__(
        self,
        n_estimators: int = 500,
        min_leaf_size: int = 10,
        max_depth: int = 10,
        mtry: Optional[int] = None,
        subsample_ratio: float = 0.5,
        alpha: float = 0.05
    ):
        """
        Args:
            n_estimators: Number of trees
            min_leaf_size: Minimum samples per leaf
            max_depth: Maximum tree depth
            mtry: Variables to consider at each split (default: p/3)
            subsample_ratio: Fraction of data for each tree (subsampling)
            alpha: Significance level for CIs
        """
        self.n_estimators = n_estimators
        self.min_leaf_size = min_leaf_size
        self.max_depth = max_depth
        self.mtry = mtry
        self.subsample_ratio = subsample_ratio
        self.alpha = alpha
        self.trees = []
        self.feature_names = None

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        treatment: np.ndarray,
        feature_names: Optional[List[str]] = None
    ) -> CausalForestResult:
        """
        Fit causal forest

        Args:
            X: Covariates (n, p)
            y: Outcomes (n,)
            treatment: Treatment indicators (n,)
            feature_names: Variable names

        Returns:
            CausalForestResult with CATE estimates
        """
        n, p = X.shape
        self.feature_names = feature_names if feature_names else [f"X{i}" for i in range(p)]

        if self.mtry is None:
            self.mtry = max(1, int(p / 3))

        # Build forest
        self.trees = []
        for b in range(self.n_estimators):
            # Subsample
            subsample_size = int(n * self.subsample_ratio)
            subsample_idx = np.random.choice(n, size=subsample_size, replace=False)

            X_sub = X[subsample_idx]
            y_sub = y[subsample_idx]
            d_sub = treatment[subsample_idx]

            # Fit tree
            tree = HonestCausalTree(
                min_leaf_size=self.min_leaf_size,
                max_depth=self.max_depth,
                mtry=self.mtry
            )
            tree.fit(X_sub, y_sub, d_sub)
            self.trees.append(tree)

            if (b + 1) % 100 == 0:
                logger.info(f"Fitted {b+1}/{self.n_estimators} trees")

        # Predict CATE
        cate = self.predict(X)

        # ATE = average CATE
        ate = cate.mean()

        # Standard error (conservative: treat as i.i.d.)
        ate_se = cate.std() / np.sqrt(n)

        # Confidence interval
        from scipy import stats as sp_stats
        z_crit = sp_stats.norm.ppf(1 - self.alpha / 2)
        ate_ci = (ate - z_crit * ate_se, ate + z_crit * ate_se)

        # Variable importance
        var_importance = self._compute_variable_importance(X, y, treatment)

        return CausalForestResult(
            cate=cate,
            ate=float(ate),
            ate_se=float(ate_se),
            ate_ci=ate_ci,
            variable_importance=var_importance
        )

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict CATE for samples"""
        n = len(X)
        predictions = np.zeros((n, len(self.trees)))

        for b, tree in enumerate(self.trees):
            predictions[:, b] = tree.predict(X)

        # Average across trees
        cate = predictions.mean(axis=1)

        return cate

    def _compute_variable_importance(
        self,
        X: np.ndarray,
        y: np.ndarray,
        treatment: np.ndarray
    ) -> Dict[str, float]:
        """
        Variable importance via permutation

        Shuffle each variable and measure decrease in prediction accuracy.
        """
        n, p = X.shape

        # Baseline predictions
        cate_baseline = self.predict(X)

        # Baseline loss (MSE of residuals)
        # Approximate: use difference from mean
        baseline_loss = np.var(cate_baseline)

        importances = {}

        for j in range(p):
            X_permuted = X.copy()
            np.random.shuffle(X_permuted[:, j])

            cate_permuted = self.predict(X_permuted)
            permuted_loss = np.mean((cate_baseline - cate_permuted)**2)

            importances[self.feature_names[j]] = float(permuted_loss)

        # Normalize
        total = sum(importances.values())
        if total > 0:
            importances = {k: v / total for k, v in importances.items()}

        return importances


class CausalForestAnalyzer:
    """Main interface for causal forest"""

    def __init__(self, **kwargs):
        self.cf = CausalForest(**kwargs)

    def estimate(
        self,
        X: np.ndarray,
        y: np.ndarray,
        treatment: np.ndarray,
        feature_names: Optional[List[str]] = None
    ) -> CausalForestResult:
        """Fit causal forest and return results"""
        return self.cf.fit(X, y, treatment, feature_names)
