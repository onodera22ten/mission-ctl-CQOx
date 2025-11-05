"""Conditional Average Treatment Effect (CATE) - 推定器#20"""
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor

def estimate_cate(X: np.ndarray, y: np.ndarray, treatment: np.ndarray) -> dict:
    """CATE推定（Meta-learner: T-learner）"""
    # T-learner: Separate models for treated and control
    X_treated = X[treatment == 1]
    y_treated = y[treatment == 1]
    X_control = X[treatment == 0]
    y_control = y[treatment == 0]
    
    model_1 = GradientBoostingRegressor(n_estimators=100, max_depth=3)
    model_0 = GradientBoostingRegressor(n_estimators=100, max_depth=3)
    
    model_1.fit(X_treated, y_treated)
    model_0.fit(X_control, y_control)
    
    # CATE predictions
    cate = model_1.predict(X) - model_0.predict(X)
    
    # ATE (average of CATE)
    ate = np.mean(cate)
    se = np.std(cate, ddof=1) / np.sqrt(len(cate))
    
    # Heterogeneity metrics
    cate_variance = np.var(cate)
    cate_range = (float(np.min(cate)), float(np.max(cate)))
    
    return {
        'ate': float(ate),
        'se': float(se),
        'cate': cate.tolist()[:100],  # First 100 for space
        'cate_variance': float(cate_variance),
        'cate_range': cate_range
    }

