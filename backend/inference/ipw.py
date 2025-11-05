"""Inverse Propensity Weighting - 推定器#13"""
import numpy as np
from sklearn.linear_model import LogisticRegression

def estimate_ate_ipw(X: np.ndarray, y: np.ndarray, treatment: np.ndarray, 
                     trim: float = 0.05) -> tuple[float, float]:
    """IPW ATE推定（trimming付き）"""
    ps_model = LogisticRegression(max_iter=1000)
    ps_model.fit(X, treatment)
    ps = ps_model.predict_proba(X)[:, 1]
    
    # Trimming
    ps = np.clip(ps, trim, 1-trim)
    
    # IPW weights
    w_treated = treatment / ps
    w_control = (1 - treatment) / (1 - ps)
    
    # Stabilized weights
    p_t = np.mean(treatment)
    w_treated = w_treated * p_t
    w_control = w_control * (1 - p_t)
    
    # ATE
    ate = np.mean(w_treated * y) - np.mean(w_control * y)
    
    # Variance (conservative)
    var_treated = np.var(w_treated * y * treatment) / np.sum(treatment)
    var_control = np.var(w_control * y * (1-treatment)) / np.sum(1-treatment)
    se = np.sqrt(var_treated + var_control)
    
    return float(ate), float(se)

