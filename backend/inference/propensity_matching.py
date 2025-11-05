"""Propensity Score Matching - 推定器#12"""
import numpy as np
from scipy.spatial.distance import cdist
from typing import Tuple

def estimate_ate_matching(X: np.ndarray, y: np.ndarray, treatment: np.ndarray, 
                          method: str = 'nearest', caliper: float = 0.1) -> Tuple[float, float]:
    """Propensity Score Matching ATE推定"""
    from sklearn.linear_model import LogisticRegression
    
    # Propensity score
    ps_model = LogisticRegression(max_iter=1000)
    ps_model.fit(X, treatment)
    ps = ps_model.predict_proba(X)[:, 1]
    
    treated_idx = np.where(treatment == 1)[0]
    control_idx = np.where(treatment == 0)[0]
    
    matched_pairs = []
    
    for t_idx in treated_idx:
        distances = np.abs(ps[control_idx] - ps[t_idx])
        min_dist_idx = np.argmin(distances)
        
        if distances[min_dist_idx] < caliper:
            c_idx = control_idx[min_dist_idx]
            matched_pairs.append((t_idx, c_idx))
    
    if len(matched_pairs) == 0:
        return 0.0, 999.0
    
    effects = [y[t] - y[c] for t, c in matched_pairs]
    ate = np.mean(effects)
    se = np.std(effects, ddof=1) / np.sqrt(len(effects))
    
    return float(ate), float(se)

