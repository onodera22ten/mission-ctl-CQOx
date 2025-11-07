#!/usr/bin/env python3
"""
Generate complete sample datasets for CQOx with ALL required columns for every estimator.

This script creates two datasets:
1. complete_healthcare_5k.parquet - Parquet format (requires preprocessing)
2. complete_marketing_5k.tsv - TSV format (requires preprocessing)

Both datasets include ALL columns needed for comprehensive causal analysis:
- Basic: user_id, date, treatment, y, cost
- Propensity: log_propensity, propensity_score
- IV: z (instrument)
- Transport: domain (source/target)
- Proximal: w_neg, z_neg (negative controls)
- Network: cluster_id, neighbor_exposure
- Covariates: age, income, education, region, etc.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

np.random.seed(42)

def generate_complete_dataset(n=5000, domain_name="healthcare"):
    """Generate a complete dataset with all required columns."""

    # Base columns
    dates = [datetime(2024, 1, 1) + timedelta(days=int(x))
             for x in np.random.randint(0, 365, n)]

    user_ids = np.arange(1, n + 1)

    # Covariates (with some missing values for preprocessing challenge)
    age = np.random.normal(45, 15, n).clip(18, 90)
    age[np.random.random(n) < 0.03] = np.nan  # 3% missing

    income = np.random.lognormal(10.5, 0.8, n)
    income[np.random.random(n) < 0.05] = np.nan  # 5% missing

    education_levels = ['high_school', 'bachelors', 'masters', 'phd']
    education = np.random.choice(education_levels, n, p=[0.3, 0.4, 0.2, 0.1])

    regions = ['north', 'south', 'east', 'west', 'central']
    region = np.random.choice(regions, n, p=[0.2, 0.2, 0.25, 0.15, 0.2])

    # Gender (with category encoding challenge)
    gender_raw = np.random.choice(['M', 'F', 'Male', 'Female', 'male', 'female'], n)

    # Instrument variable (IV) - binary instrument
    z = np.random.binomial(1, 0.5, n)

    # Treatment (influenced by instrument and confounders)
    propensity_logit = (
        -0.5
        + 0.8 * z  # Strong instrument
        + 0.02 * (age - 45)
        + 0.00001 * (income - 50000)
        + np.random.normal(0, 0.3, n)
    )
    propensity_score = 1 / (1 + np.exp(-propensity_logit))
    treatment = (np.random.random(n) < propensity_score).astype(int)
    log_propensity = np.log(propensity_score / (1 - propensity_score + 1e-10))

    # Domain (for transportability)
    domain = np.random.choice(['source', 'target'], n, p=[0.7, 0.3])

    # Negative controls (for proximal causal inference)
    w_neg = np.random.normal(0, 1, n)  # Negative control for treatment
    z_neg = np.random.normal(0, 1, n)  # Negative control for outcome

    # Network structure
    cluster_id = np.random.randint(1, 51, n)  # 50 clusters
    neighbor_exposure = np.array([
        np.random.binomial(10, treatment[cluster_id == cid].mean()) / 10
        for cid in cluster_id
    ])

    # Cost (for policy evaluation)
    cost = np.random.gamma(2, 50, n) * treatment + np.random.gamma(1, 20, n)

    # Outcome (with heterogeneous treatment effects)
    treatment_effect = (
        300  # Base ATE
        + 5 * (age - 45)  # Age heterogeneity
        + 0.002 * (income - 50000)  # Income heterogeneity
        + 50 * (education == 'phd')  # Education heterogeneity
    )

    y = (
        500  # Baseline
        + 3 * (age - 45)
        + 0.001 * (income - 50000)
        + 100 * (education == 'phd')
        + treatment * treatment_effect
        + np.random.normal(0, 100, n)
    )

    # Create DataFrame
    df = pd.DataFrame({
        'user_id': user_ids,
        'date': dates,
        'treatment': treatment,
        'y': y,
        'cost': cost,
        'log_propensity': log_propensity,
        'propensity_score': propensity_score,
        'age': age,
        'income': income,
        'education': education,
        'gender_raw': gender_raw,  # Needs preprocessing
        'region': region,
        'z': z,  # Instrument
        'domain': domain,  # Transport
        'w_neg': w_neg,  # Proximal
        'z_neg': z_neg,  # Proximal
        'cluster_id': cluster_id,  # Network
        'neighbor_exposure': neighbor_exposure,  # Network
    })

    return df

# Generate datasets
print("Generating complete healthcare dataset (Parquet)...")
df_healthcare = generate_complete_dataset(5000, "healthcare")
df_healthcare.to_parquet('data/complete_healthcare_5k.parquet', index=False)
print(f"✅ Created: data/complete_healthcare_5k.parquet ({df_healthcare.shape})")
print(f"   Columns: {', '.join(df_healthcare.columns)}")
print(f"   Missing values: age={df_healthcare['age'].isna().sum()}, income={df_healthcare['income'].isna().sum()}")

print("\nGenerating complete marketing dataset (TSV)...")
df_marketing = generate_complete_dataset(5000, "marketing")
df_marketing.to_csv('data/complete_marketing_5k.tsv', sep='\t', index=False)
print(f"✅ Created: data/complete_marketing_5k.tsv ({df_marketing.shape})")
print(f"   Columns: {', '.join(df_marketing.columns)}")
print(f"   Missing values: age={df_marketing['age'].isna().sum()}, income={df_marketing['income'].isna().sum()}")

print("\n" + "="*60)
print("PREPROCESSING REQUIREMENTS:")
print("="*60)
print("1. Missing values: age (3%), income (5%) need imputation")
print("2. Gender encoding: 'M'/'Male'/'male' → 1, 'F'/'Female'/'female' → 0")
print("3. Education: categorical → one-hot or ordinal encoding")
print("4. Region: categorical → one-hot encoding")
print("5. Date: convert to datetime if needed")
print("\n" + "="*60)
print("ESTIMATOR COVERAGE:")
print("="*60)
print("✓ OPE: log_propensity, propensity_score")
print("✓ TVCE: date, treatment, y")
print("✓ Hidden confounding: treatment, y (always available)")
print("✓ IV: z (instrument), treatment, y")
print("✓ Transport: domain, treatment, y")
print("✓ Proximal: w_neg, z_neg, treatment, y")
print("✓ Network: cluster_id, neighbor_exposure, treatment, y")
print("✓ Synthetic control: user_id, date, treatment, y")
print("✓ Causal forest: all covariates")
print("✓ RD: age as running variable")
print("✓ DiD: user_id, date, treatment, y")
