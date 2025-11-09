"""
Generate Sample Demo Dataset for Counterfactual Evaluation

Required columns for OPE:
- y: Outcome (conversions)
- treatment: Treatment indicator (0/1)
- unit_id: User ID
- time: Timestamp
- cost: Cost per user
- log_propensity: Log propensity score
"""

import numpy as np
import pandas as pd
from pathlib import Path

np.random.seed(42)

def generate_demo_dataset(n_samples=5000):
    """
    Generate realistic demo dataset for counterfactual evaluation

    Scenario: E-commerce marketing campaign with geographic and network effects
    """
    # Generate unit IDs
    unit_ids = [f"user_{i:05d}" for i in range(n_samples)]

    # Generate timestamps (28 days)
    days = pd.date_range('2025-01-01', periods=28, freq='D')
    times = np.random.choice(days, size=n_samples)

    # Generate treatment assignment (30% treatment rate)
    treatment_prob = 0.3
    treatment = np.random.binomial(1, treatment_prob, size=n_samples)

    # Generate propensity scores (with some variation)
    # True propensity with covariates
    X_age = np.random.normal(35, 10, size=n_samples)
    X_income = np.random.normal(50000, 15000, size=n_samples)
    X_region = np.random.choice(['tokyo', 'osaka', 'nagoya', 'fukuoka'], size=n_samples)

    # Propensity model: logit(p) = β0 + β1*age + β2*income + β3*region
    log_odds = -2 + 0.02 * (X_age - 35) + 0.00001 * (X_income - 50000)
    log_odds += np.where(X_region == 'tokyo', 0.5, 0)
    log_odds += np.where(X_region == 'osaka', 0.3, 0)

    propensity = 1 / (1 + np.exp(-log_odds))
    log_propensity = np.log(propensity + 1e-8)  # Add small constant to avoid log(0)

    # Generate outcomes
    # Baseline outcome (control)
    y_control = 10 + 0.1 * (X_age - 35) + 0.0001 * (X_income - 50000)
    y_control += np.random.normal(0, 3, size=n_samples)
    y_control = np.maximum(0, y_control)  # Non-negative

    # Treatment effect (heterogeneous)
    tau = 5 + 0.05 * (X_age - 35) + 0.00005 * (X_income - 50000)
    tau += np.random.normal(0, 2, size=n_samples)

    # Observed outcome
    y = y_control + treatment * tau
    y = np.maximum(0, y)  # Non-negative

    # Generate costs (proportional to treatment)
    cost_control = np.random.uniform(50, 100, size=n_samples)
    cost_treatment = np.random.uniform(200, 300, size=n_samples)
    cost = np.where(treatment == 1, cost_treatment, cost_control)

    # Create DataFrame
    df = pd.DataFrame({
        'unit_id': unit_ids,
        'time': times,
        'treatment': treatment,
        'y': y,
        'cost': cost,
        'log_propensity': log_propensity,
        'X_age': X_age,
        'X_income': X_income,
        'X_region': X_region
    })

    return df


def main():
    # Generate dataset
    print("Generating demo dataset...")
    df = generate_demo_dataset(n_samples=5000)

    # Create output directory
    output_dir = Path('data/demo')
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save as parquet
    output_path = output_dir / 'data.parquet'
    df.to_parquet(output_path, index=False)

    print(f"✓ Dataset saved to: {output_path}")
    print(f"  Rows: {len(df):,}")
    print(f"  Columns: {list(df.columns)}")
    print(f"\nColumn Summary:")
    print(f"  Treatment rate: {df['treatment'].mean():.1%}")
    print(f"  Avg outcome (control): {df[df['treatment']==0]['y'].mean():.2f}")
    print(f"  Avg outcome (treated): {df[df['treatment']==1]['y'].mean():.2f}")
    print(f"  Naive ATE: {df[df['treatment']==1]['y'].mean() - df[df['treatment']==0]['y'].mean():.2f}")
    print(f"  Avg cost (control): ¥{df[df['treatment']==0]['cost'].mean():.0f}")
    print(f"  Avg cost (treated): ¥{df[df['treatment']==1]['cost'].mean():.0f}")


if __name__ == '__main__':
    main()
