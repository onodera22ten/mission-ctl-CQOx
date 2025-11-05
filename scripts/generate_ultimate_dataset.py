#!/usr/bin/env python3
"""
Generate ULTIMATE sample dataset for CQOx with ALL visualizations (34+ figures).

This dataset supports:
- All 10 estimators (OPE, TVCE, Hidden, IV, Transport, Proximal, Network, SC, CF, DiD, RD)
- All baseline figures (parallel_trends, event_study, etc.)
- All primitive figures (timeseries, distribution, scatter, etc.)
- All advanced figures (CATE forest, E-value, etc.)
- All finance/network/policy figures
- All objective-specific figures
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

np.random.seed(42)

def generate_ultimate_dataset(n=5000):
    """Generate complete dataset with all required columns for 34+ visualizations."""

    print(f"Generating ultimate dataset with n={n} rows...")

    # ========================================================================
    # 1. TEMPORAL DATA (for TVCE, DiD, Synthetic Control, Event Study)
    # ========================================================================
    dates = pd.date_range(start='2023-01-01', periods=365, freq='D')
    date_idx = np.random.choice(len(dates), n)
    date = dates[date_idx]

    # Create pre/post treatment periods
    treatment_date = pd.Timestamp('2023-07-01')
    post = (date >= treatment_date).astype(int)

    # Time period for panel data (month index: 0-11)
    time_period = np.array([int((d - pd.Timestamp('2023-01-01')).days // 30) for d in date])

    # ========================================================================
    # 2. IDENTIFIERS (for panel data, clustering)
    # ========================================================================
    user_id = np.random.randint(1, 1001, n)  # 1000 unique users
    cluster_id = np.random.randint(1, 51, n)  # 50 clusters

    # ========================================================================
    # 3. COVARIATES (for matching, CATE, RD)
    # ========================================================================
    # Continuous covariates
    age = np.random.normal(45, 15, n).clip(18, 90)
    income = np.random.lognormal(10.5, 0.8, n)
    credit_score = np.random.normal(700, 100, n).clip(300, 850)

    # Running variable for RD (centered at cutoff=0)
    running_variable = np.random.normal(0, 10, n)

    # Categorical covariates
    education = np.random.choice(['high_school', 'bachelors', 'masters', 'phd'],
                                 n, p=[0.3, 0.4, 0.2, 0.1])
    gender = np.random.choice(['M', 'F'], n)
    region = np.random.choice(['north', 'south', 'east', 'west', 'central'],
                              n, p=[0.2, 0.2, 0.25, 0.15, 0.2])

    # Additional covariates for heterogeneity analysis
    risk_score = np.random.beta(2, 5, n)
    engagement_score = np.random.gamma(2, 2, n)

    # ========================================================================
    # 4. INSTRUMENT VARIABLE (for IV)
    # ========================================================================
    z = np.random.binomial(1, 0.5, n)  # Binary instrument

    # ========================================================================
    # 5. PROPENSITY SCORES (for OPE, matching)
    # ========================================================================
    # True propensity based on confounders + instrument
    propensity_logit = (
        -0.5
        + 0.8 * z  # Strong IV
        + 0.02 * (age - 45)
        + 0.00001 * (income - 50000)
        + 0.5 * (education == 'phd')
        + 0.3 * risk_score
        + 0.05 * time_period
        + np.random.normal(0, 0.3, n)
    )
    propensity_score = 1 / (1 + np.exp(-propensity_logit))
    log_propensity = np.log(propensity_score / (1 - propensity_score + 1e-10))

    # ========================================================================
    # 6. TREATMENT ASSIGNMENT
    # ========================================================================
    # RD: sharp design at running_variable=0
    rd_treatment = (running_variable > 0).astype(int)

    # Random treatment (influenced by propensity)
    random_treatment = (np.random.random(n) < propensity_score).astype(int)

    # Combine: use RD near cutoff, random elsewhere
    near_cutoff = np.abs(running_variable) < 5
    treatment = np.where(near_cutoff, rd_treatment, random_treatment)

    # ========================================================================
    # 7. TRANSPORTABILITY (for transport estimator)
    # ========================================================================
    domain = np.random.choice(['source', 'target'], n, p=[0.7, 0.3])

    # ========================================================================
    # 8. NEGATIVE CONTROLS (for proximal inference)
    # ========================================================================
    w_neg = np.random.normal(0, 1, n)  # Negative control for treatment
    z_neg = np.random.normal(0, 1, n)  # Negative control for outcome

    # ========================================================================
    # 9. NETWORK EFFECTS (for network spillover)
    # ========================================================================
    # Neighbor exposure: fraction of neighbors treated
    neighbor_exposure = np.array([
        np.random.binomial(10, treatment[cluster_id == cid].mean()) / 10
        if (cluster_id == cid).sum() > 0 else 0
        for cid in cluster_id
    ])

    # ========================================================================
    # 10. OUTCOMES (heterogeneous treatment effects)
    # ========================================================================
    # Base outcome
    y0 = (
        500  # Baseline
        + 3 * (age - 45)
        + 0.001 * (income - 50000)
        + 100 * (education == 'phd')
        + 50 * risk_score
        + 30 * engagement_score
        + 20 * time_period
    )

    # Heterogeneous treatment effect
    treatment_effect = (
        300  # Base ATE
        + 5 * (age - 45)  # Age heterogeneity
        + 0.002 * (income - 50000)  # Income heterogeneity
        + 50 * (education == 'phd')  # Education heterogeneity
        + 100 * risk_score  # Risk heterogeneity
        + 80 * engagement_score  # Engagement heterogeneity
        + 10 * neighbor_exposure  # Spillover effect
    )

    # Final outcome with noise
    y = y0 + treatment * treatment_effect + np.random.normal(0, 100, n)

    # ========================================================================
    # 11. COSTS (for policy evaluation)
    # ========================================================================
    cost = np.random.gamma(2, 50, n) * treatment + np.random.gamma(1, 20, n)

    # ========================================================================
    # 12. FINANCIAL METRICS (for finance figures)
    # ========================================================================
    revenue = y * 1.5 + np.random.normal(0, 50, n)
    profit = revenue - cost
    roi = (profit / (cost + 1)) * 100

    # ========================================================================
    # 13. POLICY METRICS (for policy figures)
    # ========================================================================
    # Welfare metrics
    welfare = y - 0.5 * cost  # Simple welfare function

    # Counterfactual outcomes (for what-if analysis)
    y_cf_low = y0 + 0.5 * treatment_effect + np.random.normal(0, 100, n)
    y_cf_high = y0 + 1.5 * treatment_effect + np.random.normal(0, 100, n)

    # ========================================================================
    # 14. ADDITIONAL FEATURES (for advanced figures)
    # ========================================================================
    # CATE features
    cate_true = treatment_effect  # True CATE for validation

    # E-value components
    unmeasured_confounder = np.random.normal(0, 1, n)

    # Sensitivity analysis
    hidden_confounder_strength = np.random.uniform(0.1, 2.0, n)

    # Time-varying confounders
    time_varying_conf = np.sin(time_period * 0.5) + np.random.normal(0, 0.1, n)

    # ========================================================================
    # CREATE DATAFRAME
    # ========================================================================
    df = pd.DataFrame({
        # Identifiers
        'user_id': user_id,
        'cluster_id': cluster_id,

        # Temporal
        'date': date,
        'time_period': time_period,
        'post': post,

        # Treatment
        'treatment': treatment,

        # Outcomes
        'y': y,
        'y0': y0,  # Potential outcome under control
        'y_cf_low': y_cf_low,
        'y_cf_high': y_cf_high,

        # Costs
        'cost': cost,

        # Propensity
        'propensity_score': propensity_score,
        'log_propensity': log_propensity,

        # Covariates - Continuous
        'age': age,
        'income': income,
        'credit_score': credit_score,
        'running_variable': running_variable,
        'risk_score': risk_score,
        'engagement_score': engagement_score,

        # Covariates - Categorical
        'education': education,
        'gender': gender,
        'region': region,

        # IV
        'z': z,

        # Transportability
        'domain': domain,

        # Proximal
        'w_neg': w_neg,
        'z_neg': z_neg,

        # Network
        'neighbor_exposure': neighbor_exposure,

        # Financial
        'revenue': revenue,
        'profit': profit,
        'roi': roi,

        # Policy
        'welfare': welfare,

        # Advanced
        'cate_true': cate_true,
        'unmeasured_confounder': unmeasured_confounder,
        'hidden_confounder_strength': hidden_confounder_strength,
        'time_varying_conf': time_varying_conf,
    })

    return df

# ============================================================================
# GENERATE AND SAVE
# ============================================================================
print("="*80)
print("GENERATING ULTIMATE CQOX DATASET")
print("="*80)

df = generate_ultimate_dataset(5000)

# Save as CSV
output_path = 'data/ultimate_sample_5k.csv'
df.to_csv(output_path, index=False)

print(f"\n✅ Created: {output_path}")
print(f"   Shape: {df.shape}")
print(f"   Size: {df.memory_usage(deep=True).sum() / 1024:.1f} KB")
print(f"\n📊 Columns ({len(df.columns)}):")
for i, col in enumerate(df.columns, 1):
    print(f"   {i:2d}. {col}")

print("\n" + "="*80)
print("ESTIMATOR SUPPORT")
print("="*80)
estimators = {
    "OPE": ["log_propensity", "propensity_score"],
    "TVCE": ["date", "treatment", "y"],
    "Hidden": ["treatment", "y"],
    "IV": ["z", "treatment", "y"],
    "Transport": ["domain", "treatment", "y"],
    "Proximal": ["w_neg", "z_neg", "treatment", "y"],
    "Network": ["cluster_id", "neighbor_exposure", "treatment", "y"],
    "Synthetic Control": ["user_id", "date", "treatment", "y"],
    "Causal Forest": ["all covariates", "treatment", "y"],
    "RD": ["running_variable", "treatment", "y"],
    "DiD": ["user_id", "date", "post", "treatment", "y"],
}

for name, cols in estimators.items():
    print(f"✅ {name:20s} → {', '.join(cols)}")

print("\n" + "="*80)
print("VISUALIZATION SUPPORT (34+ figures)")
print("="*80)
viz_categories = {
    "Baseline (13)": [
        "parallel_trends", "event_study", "ate_density", "propensity_overlap",
        "balance_smd", "rosenbaum_gamma", "iv_first_stage", "iv_strength",
        "transport_weights", "tvce_line", "network_spillover",
        "heterogeneity_waterfall", "quality_gates_board", "cas_radar"
    ],
    "Primitives (6)": [
        "timeseries", "distribution", "scatter", "heterogeneity",
        "propensity", "balance"
    ],
    "Advanced (4)": [
        "cate_forest", "evalue_sensitivity", "rd_discontinuity", "uplift_curve"
    ],
    "Finance (4)": [
        "roi_waterfall", "cost_effectiveness", "profit_curve", "breakeven"
    ],
    "Network (3)": [
        "spillover_heatmap", "cluster_effects", "interference_graph"
    ],
    "Policy (4)": [
        "welfare_comparison", "counterfactual_scenarios", "optimal_policy", "cost_benefit"
    ]
}

total_viz = 0
for category, figures in viz_categories.items():
    print(f"\n{category}:")
    for fig in figures:
        print(f"  • {fig}")
    total_viz += len(figures)

print(f"\n{'='*80}")
print(f"TOTAL VISUALIZATIONS: {total_viz}")
print(f"{'='*80}")
print("\n✨ Dataset generation complete! Ready for comprehensive analysis.")
