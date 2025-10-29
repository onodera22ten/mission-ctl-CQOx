#!/usr/bin/env python3
"""
Causal Safety Preparation

Purpose: Compute propensity overlap, SMD, and causal-safe metrics
Features:
- Propensity score estimation (診断目的)
- Overlap detection (0.05 < e(X) < 0.95)
- Standardized Mean Difference (SMD) for balance
- Fail-fast if quality gates violated
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ciq.lib.contract import load_contract

CONTRACT = "ciq/contracts/dataset.yaml"
OUT_PARQUET = Path("ciq/data/processed/causal_ready.parquet")
METRICS_JSON = Path("ciq/artifacts/overlap_metrics.json")


def compute_smd(X_t, X_c):
    """
    Compute Standardized Mean Difference (SMD)

    Formula:
        SMD_j = (mean(X_j | T=1) - mean(X_j | T=0)) / sqrt((var_1 + var_0) / 2)

    Args:
        X_t: Features for treated group (n_t × p)
        X_c: Features for control group (n_c × p)

    Returns:
        Array of SMD values for each feature
    """
    mean_t = np.mean(X_t, axis=0)
    mean_c = np.mean(X_c, axis=0)
    var_t = np.var(X_t, axis=0, ddof=1)
    var_c = np.var(X_c, axis=0, ddof=1)

    pooled_std = np.sqrt((var_t + var_c) / 2)
    pooled_std = np.where(pooled_std < 1e-8, 1.0, pooled_std)  # Prevent division by zero

    smd = (mean_t - mean_c) / pooled_std
    return smd


def main():
    """
    Main causal preparation pipeline:
    1. Load causal_ready table from DuckDB
    2. Estimate propensity scores (diagnostic)
    3. Compute overlap metrics
    4. Compute SMD for balance check
    5. Write processed Parquet + metrics JSON
    6. Fail-fast if quality gates violated
    """
    # Load contract
    contract = load_contract(CONTRACT)
    quality_gates = contract.get("quality_gates", {})
    overlap_threshold = quality_gates.get("overlap_threshold", 0.6)
    max_smd = quality_gates.get("max_smd", 0.1)

    # Load causal_ready table
    con = duckdb.connect("ciq/warehouse/warehouse.duckdb")
    try:
        df = con.execute("SELECT * FROM causal_ready").fetch_df()
    except Exception as e:
        print(f"ERROR: Failed to load causal_ready table: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        con.close()

    print(f"[prepare] Loaded {len(df)} rows from causal_ready", file=sys.stderr)

    # Extract columns from contract
    X_cols = contract["covariate_cols"]
    t_col = contract["treatment_col"]
    y_col = contract["outcome_col"]

    # === 1. Propensity Score Estimation (診断目的) ===
    # Note: This is for overlap diagnosis only, not for actual propensity weighting
    # Actual causal inference should use more sophisticated methods

    # Select numeric columns only
    X_numeric = df[X_cols].select_dtypes(include=[np.number])
    if X_numeric.shape[1] == 0:
        print("WARNING: No numeric covariates for propensity estimation", file=sys.stderr)
        X_numeric = pd.DataFrame(np.zeros((len(df), 1)), columns=["dummy"])

    # Impute missing values (median strategy)
    imputer = SimpleImputer(strategy="median")
    X_imputed = imputer.fit_transform(X_numeric)

    # Standardize
    scaler = StandardScaler(with_mean=True, with_std=True)
    X_scaled = scaler.fit_transform(X_imputed)

    # Logistic regression for propensity score
    lr = LogisticRegression(max_iter=1000, random_state=42)
    lr.fit(X_scaled, df[t_col].values)
    e_hat = lr.predict_proba(X_scaled)[:, 1]  # P(T=1 | X)

    df["ps_hat"] = e_hat

    # === 2. Overlap Diagnostics ===
    # Overlap: Proportion of units with 0.05 < e(X) < 0.95
    overlap_mask = (e_hat > 0.05) & (e_hat < 0.95)
    overlap_ratio = float(overlap_mask.mean())

    # Tail mass (extreme propensities)
    tail_lt_001 = float((e_hat < 0.01).mean())
    tail_gt_099 = float((e_hat > 0.99).mean())

    print(f"[prepare] Overlap ratio: {overlap_ratio:.3f}", file=sys.stderr)
    print(f"[prepare] Tail mass (< 0.01): {tail_lt_001:.4f}", file=sys.stderr)
    print(f"[prepare] Tail mass (> 0.99): {tail_gt_099:.4f}", file=sys.stderr)

    # === 3. Standardized Mean Difference (SMD) ===
    treated_mask = df[t_col] == 1
    control_mask = df[t_col] == 0

    X_t = X_scaled[treated_mask]
    X_c = X_scaled[control_mask]

    if X_t.shape[0] > 0 and X_c.shape[0] > 0:
        smd = compute_smd(X_t, X_c)
        max_smd_value = float(np.max(np.abs(smd)))
        smd_dict = {
            col: float(val) for col, val in zip(X_numeric.columns, smd)
        }
        print(f"[prepare] Max |SMD|: {max_smd_value:.3f}", file=sys.stderr)
    else:
        print("WARNING: Insufficient treated or control units for SMD", file=sys.stderr)
        max_smd_value = 0.0
        smd_dict = {}

    # === 4. Save Processed Data ===
    OUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT_PARQUET, index=False)
    print(f"[prepare] Wrote {OUT_PARQUET}", file=sys.stderr)

    # === 5. Save Metrics ===
    metrics = {
        "overlap": overlap_ratio,
        "tails": {"lt_0_01": tail_lt_001, "gt_0_99": tail_gt_099},
        "smd": smd_dict,
        "max_smd": max_smd_value,
    }

    METRICS_JSON.parent.mkdir(parents=True, exist_ok=True)
    METRICS_JSON.write_text(json.dumps(metrics, indent=2))
    print(f"[prepare] Wrote {METRICS_JSON}", file=sys.stderr)

    # === 6. Quality Gates (Fail-Fast) ===
    violations = []

    if overlap_ratio < overlap_threshold:
        violations.append(
            f"Overlap ratio {overlap_ratio:.3f} < {overlap_threshold} (threshold)"
        )

    if max_smd_value > max_smd:
        violations.append(
            f"Max |SMD| {max_smd_value:.3f} > {max_smd} (threshold)"
        )

    if violations:
        print("ERROR: Quality gate violations:", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        sys.exit(1)

    print("[prepare] ✓ All quality gates passed", file=sys.stderr)


if __name__ == "__main__":
    main()
