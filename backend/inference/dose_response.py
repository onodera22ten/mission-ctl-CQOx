"""Dose-Response / Continuous Treatment - 推定器#17"""
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge

def estimate_dose_response(X: np.ndarray, y: np.ndarray, dose: np.ndarray, 
                           n_points: int = 20) -> dict:
    """Dose-Response Function推定（連続treatment）"""
    # GPS (Generalized Propensity Score) - dose distribution
    from sklearn.neighbors import KernelDensity
    kde = KernelDensity(bandwidth=0.5).fit(dose.reshape(-1, 1))
    gps = np.exp(kde.score_samples(dose.reshape(-1, 1)))
    
    # Outcome model with GPS weighting
    X_full = np.column_stack([dose, X])
    weights = 1.0 / (gps + 1e-6)
    weights = weights / weights.sum() * len(weights)  # Normalize
    
    model = Ridge(alpha=1.0)
    model.fit(X_full, y, sample_weight=weights)
    
    # Dose-response curve
    dose_grid = np.linspace(dose.min(), dose.max(), n_points)
    X_mean = np.mean(X, axis=0)
    X_grid = np.tile(X_mean, (n_points, 1))
    X_eval = np.column_stack([dose_grid, X_grid])
    
    response = model.predict(X_eval)
    
    # ATE-like: effect of moving from min to max dose
    ate = float(response[-1] - response[0])
    
    return {
        'dose_grid': dose_grid.tolist(),
        'response': response.tolist(),
        'ate_min_to_max': ate,
        'model_coef': float(model.coef_[0])  # Linear dose effect
    }

