"""Regression Adjustment - 推定器#14"""
import numpy as np
from sklearn.linear_model import LinearRegression

def estimate_ate_regression(X: np.ndarray, y: np.ndarray, treatment: np.ndarray) -> tuple[float, float]:
    """Regression Adjustment ATE推定"""
    # Fit outcome models separately
    X_treated = X[treatment == 1]
    y_treated = y[treatment == 1]
    X_control = X[treatment == 0]
    y_control = y[treatment == 0]
    
    model_1 = LinearRegression().fit(X_treated, y_treated)
    model_0 = LinearRegression().fit(X_control, y_control)
    
    # Predict counterfactuals
    y1_hat = model_1.predict(X)
    y0_hat = model_0.predict(X)
    
    # ATE
    ate = np.mean(y1_hat - y0_hat)
    
    # SE (bootstrap approximation)
    effects = y1_hat - y0_hat
    se = np.std(effects, ddof=1) / np.sqrt(len(effects))
    
    return float(ate), float(se)

