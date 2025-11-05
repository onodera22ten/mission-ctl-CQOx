"""Stratification / Subclassification - 推定器#15"""
import numpy as np
from sklearn.linear_model import LogisticRegression

def estimate_ate_stratification(X: np.ndarray, y: np.ndarray, treatment: np.ndarray, 
                                n_strata: int = 5) -> tuple[float, float]:
    """Propensity Score Stratification ATE推定"""
    ps_model = LogisticRegression(max_iter=1000)
    ps_model.fit(X, treatment)
    ps = ps_model.predict_proba(X)[:, 1]
    
    # Create strata based on PS quintiles
    strata = np.digitize(ps, np.percentile(ps, np.linspace(0, 100, n_strata+1)[1:-1]))
    
    # ATE per stratum
    ate_strata = []
    weights = []
    
    for s in range(n_strata):
        mask = (strata == s)
        if np.sum(mask & (treatment==1)) > 0 and np.sum(mask & (treatment==0)) > 0:
            ate_s = y[mask & (treatment==1)].mean() - y[mask & (treatment==0)].mean()
            ate_strata.append(ate_s)
            weights.append(np.sum(mask))
    
    if len(ate_strata) == 0:
        return 0.0, 999.0
    
    # Weighted average
    weights = np.array(weights) / np.sum(weights)
    ate = np.sum(np.array(ate_strata) * weights)
    
    # SE (conservative)
    se = np.std(ate_strata) / np.sqrt(len(ate_strata))
    
    return float(ate), float(se)

