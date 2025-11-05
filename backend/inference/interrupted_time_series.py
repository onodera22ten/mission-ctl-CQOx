"""Interrupted Time Series - 推定器#18"""
import numpy as np
from sklearn.linear_model import LinearRegression

def estimate_its(y: np.ndarray, time: np.ndarray, intervention_time: int) -> dict:
    """Interrupted Time Series分析
    
    y = β0 + β1*time + β2*intervention + β3*(time_after_intervention)
    """
    # Create variables
    intervention = (time >= intervention_time).astype(int)
    time_after = np.maximum(0, time - intervention_time)
    
    X = np.column_stack([
        np.ones(len(time)),  # Intercept
        time,                 # Pre-trend
        intervention,         # Level change
        time_after           # Slope change
    ])
    
    model = LinearRegression(fit_intercept=False)
    model.fit(X, y)
    
    coef = model.coef_
    
    return {
        'level_change': float(coef[2]),      # Immediate effect
        'slope_change': float(coef[3]),      # Long-term effect
        'pre_trend': float(coef[1]),
        'intercept': float(coef[0])
    }

