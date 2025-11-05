"""Mediation Analysis - 推定器#16"""
import numpy as np
from sklearn.linear_model import LinearRegression

def estimate_mediation(X: np.ndarray, y: np.ndarray, treatment: np.ndarray, 
                      mediator: np.ndarray) -> dict:
    """Mediation Analysis (Baron & Kenny 1986)
    
    Total Effect = Direct Effect + Indirect Effect
    Indirect Effect = a * b (treatment→mediator→outcome)
    """
    # Model 1: Treatment → Mediator (a path)
    model_a = LinearRegression().fit(treatment.reshape(-1, 1), mediator)
    a = float(model_a.coef_[0])
    
    # Model 2: Treatment + Mediator → Outcome (b and c' paths)
    X_full = np.column_stack([treatment, mediator])
    model_bc = LinearRegression().fit(X_full, y)
    c_prime = float(model_bc.coef_[0])  # Direct effect
    b = float(model_bc.coef_[1])        # Mediator effect
    
    # Model 3: Treatment → Outcome (c path, total effect)
    model_c = LinearRegression().fit(treatment.reshape(-1, 1), y)
    c = float(model_c.coef_[0])  # Total effect
    
    # Indirect effect
    indirect = a * b
    
    # Proportion mediated
    prop_mediated = indirect / c if c != 0 else 0.0
    
    return {
        'total_effect': c,
        'direct_effect': c_prime,
        'indirect_effect': indirect,
        'prop_mediated': prop_mediated,
        'a_path': a,
        'b_path': b
    }

