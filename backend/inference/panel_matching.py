"""Panel Matching / Coarsened Exact Matching - 推定器#19"""
import numpy as np
import pandas as pd

def estimate_ate_cem(X: np.ndarray, y: np.ndarray, treatment: np.ndarray, 
                     n_bins: int = 3) -> tuple[float, float]:
    """Coarsened Exact Matching (CEM) ATE推定"""
    # Coarsen covariates into bins
    X_coarse = np.zeros_like(X, dtype=int)
    for j in range(X.shape[1]):
        X_coarse[:, j] = pd.cut(X[:, j], bins=n_bins, labels=False, duplicates='drop')
    
    # Create strata based on coarsened covariates
    strata_ids = [''.join(map(str, row)) for row in X_coarse]
    
    # Match within strata
    effects = []
    for stratum in set(strata_ids):
        mask = np.array([s == stratum for s in strata_ids])
        t_in_stratum = treatment[mask]
        y_in_stratum = y[mask]
        
        if np.sum(t_in_stratum == 1) > 0 and np.sum(t_in_stratum == 0) > 0:
            effect = y_in_stratum[t_in_stratum == 1].mean() - y_in_stratum[t_in_stratum == 0].mean()
            effects.append(effect)
    
    if len(effects) == 0:
        return 0.0, 999.0
    
    ate = np.mean(effects)
    se = np.std(effects, ddof=1) / np.sqrt(len(effects))
    
    return float(ate), float(se)

