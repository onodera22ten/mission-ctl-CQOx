"""
Counterfactual Scenario Engine (Plan1.pdf準拠)
反実仮想パラメータシステム - Base/CF/Δの3種類のデータを生成
"""
from __future__ import annotations
import pandas as pd
import numpy as np
import yaml
import json
from pathlib import Path
from typing import Dict, Any, Tuple
from dataclasses import dataclass


@dataclass
class ScenarioResult:
    """Counterfactual scenario result"""
    scenario_id: str
    df_base: pd.DataFrame  # ベースラインデータ
    df_cf: pd.DataFrame    # カウンターファクチュアルデータ
    df_delta: pd.DataFrame # 差分データ（CF - Base）
    params: Dict[str, Any] # 適用されたパラメータ


class ScenarioEngine:
    """
    反実仮想シナリオエンジン

    ScenarioSpecを読み込み、Base/CF/Δの3種類のデータセットを生成
    """

    def __init__(self, scenario_path: Path = None, scenario_dict: Dict = None):
        """
        Args:
            scenario_path: YAML file path
            scenario_dict: Scenario dict (if not using file)
        """
        if scenario_path:
            with open(scenario_path) as f:
                self.spec = yaml.safe_load(f)
        elif scenario_dict:
            self.spec = scenario_dict
        else:
            # Default: no counterfactual (identity scenario)
            self.spec = {"scenario_id": "baseline"}

    def apply_scenario(self, df_base: pd.DataFrame, mapping: Dict[str, str]) -> ScenarioResult:
        """
        Apply counterfactual scenario to baseline data

        Args:
            df_base: Baseline dataframe
            mapping: Column role mapping

        Returns:
            ScenarioResult with base/cf/delta dataframes
        """
        df_cf = df_base.copy()

        # === Policy Counterfactuals ===
        if "policy" in self.spec:
            df_cf = self._apply_policy_cf(df_cf, mapping)

        # === Intervention Counterfactuals (do-operator) ===
        if "intervention" in self.spec:
            df_cf = self._apply_intervention_cf(df_cf, mapping)

        # === Generative Model Counterfactuals ===
        if "generative" in self.spec:
            df_cf = self._apply_generative_cf(df_cf, mapping)

        # === Economics Counterfactuals ===
        if "economics" in self.spec:
            df_cf = self._apply_economics_cf(df_cf, mapping)

        # === Compute Delta ===
        df_delta = self._compute_delta(df_base, df_cf, mapping)

        return ScenarioResult(
            scenario_id=self.spec.get("scenario_id", "unknown"),
            df_base=df_base,
            df_cf=df_cf,
            df_delta=df_delta,
            params=self.spec
        )

    def _apply_policy_cf(self, df: pd.DataFrame, mapping: Dict[str, str]) -> pd.DataFrame:
        """Apply policy counterfactuals (budget, threshold)"""
        policy = self.spec["policy"]

        # Budget multiplier
        if "budget_multiplier" in policy:
            # Note: Budget影響は後段の最適化で処理（ここでは記録のみ）
            pass

        # Threshold shift (for binary treatment decisions)
        if "threshold_shift" in policy:
            treatment_col = mapping.get("treatment")
            if treatment_col and "propensity_score" in df.columns:
                shift = policy["threshold_shift"]
                # Shift treatment assignment based on propensity
                new_threshold = 0.5 + shift
                df[treatment_col] = (df["propensity_score"] > new_threshold).astype(int)

        return df

    def _apply_intervention_cf(self, df: pd.DataFrame, mapping: Dict[str, str]) -> pd.DataFrame:
        """Apply intervention counterfactuals (do-operator, geo_quota)"""
        intervention = self.spec["intervention"]
        treatment_col = mapping.get("treatment")

        # do-operator: Force all units to treatment=X
        if "do_treatment" in intervention:
            if treatment_col:
                df[treatment_col] = intervention["do_treatment"]

        # Geographic quota
        if "geo_quota" in intervention:
            geo_col = mapping.get("cluster_id") or mapping.get("region")
            if geo_col and geo_col in df.columns and treatment_col:
                for geo, target_rate in intervention["geo_quota"].items():
                    mask = df[geo_col] == geo
                    n_geo = mask.sum()
                    n_treat = int(n_geo * target_rate)

                    # Randomly assign treatment to meet quota
                    geo_indices = df[mask].index
                    treat_indices = np.random.choice(geo_indices, size=n_treat, replace=False)
                    df.loc[mask, treatment_col] = 0
                    df.loc[treat_indices, treatment_col] = 1

        return df

    def _apply_generative_cf(self, df: pd.DataFrame, mapping: Dict[str, str]) -> pd.DataFrame:
        """Apply generative model counterfactuals (network beta, survival hazard)"""
        generative = self.spec["generative"]

        # Network spillover β
        if "network" in generative and "beta" in generative["network"]:
            beta = generative["network"]["beta"]
            treatment_col = mapping.get("treatment")
            outcome_col = mapping.get("y")

            if treatment_col and outcome_col:
                # Simple spillover: add β * (neighbor_treatment_rate) to outcome
                # NOTE: This is simplified; full implementation needs network graph
                avg_treatment = df[treatment_col].mean()
                spillover_effect = beta * avg_treatment * df[outcome_col].std()
                df[outcome_col] = df[outcome_col] + spillover_effect * df[treatment_col]

        # MMM (Marketing Mix Model)
        if "mmm" in generative:
            # Adstock and saturation effects
            # NOTE: Requires time-series implementation
            pass

        # Survival hazard
        if "survival" in generative:
            hazard_mult = generative["survival"].get("hazard_multiplier", 1.0)
            # NOTE: Requires survival model implementation
            pass

        return df

    def _apply_economics_cf(self, df: pd.DataFrame, mapping: Dict[str, str]) -> pd.DataFrame:
        """Apply economics counterfactuals (cost, value, margin)"""
        economics = self.spec["economics"]

        # Cost multiplier
        if "cost_multiplier" in economics:
            cost_col = mapping.get("cost")
            if cost_col and cost_col in df.columns:
                mult = economics["cost_multiplier"]
                df[cost_col] = df[cost_col] * mult

        # Value per unit multiplier
        if "value_per_unit_multiplier" in economics:
            outcome_col = mapping.get("y")
            if outcome_col:
                mult = economics["value_per_unit_multiplier"]
                df[outcome_col] = df[outcome_col] * mult

        # Margin adjustment
        if "margin_adjustment" in economics:
            # NOTE: Margin影響は収益計算時に適用
            pass

        return df

    def _compute_delta(self, df_base: pd.DataFrame, df_cf: pd.DataFrame,
                      mapping: Dict[str, str]) -> pd.DataFrame:
        """
        Compute delta dataframe (CF - Base)

        Only numeric columns are differenced
        """
        df_delta = df_cf.copy()

        # Difference numeric columns
        numeric_cols = df_base.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            if col in df_cf.columns:
                df_delta[col] = df_cf[col] - df_base[col]

        # Keep categorical columns from CF
        cat_cols = df_base.select_dtypes(exclude=[np.number]).columns
        for col in cat_cols:
            if col in df_cf.columns:
                df_delta[col] = df_cf[col]

        return df_delta


def load_scenario(scenario_id: str) -> ScenarioEngine:
    """
    Load scenario by ID

    Args:
        scenario_id: Scenario identifier or path

    Returns:
        ScenarioEngine instance
    """
    # Check if it's a file path
    scenario_path = Path(f"scenarios/{scenario_id}.yaml")
    if scenario_path.exists():
        return ScenarioEngine(scenario_path=scenario_path)

    # Check direct path
    if Path(scenario_id).exists():
        return ScenarioEngine(scenario_path=Path(scenario_id))

    # Return baseline (no CF)
    return ScenarioEngine(scenario_dict={"scenario_id": "baseline"})


# CLI for testing
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python scenario_engine.py <scenario_yaml> [data.csv]")
        sys.exit(1)

    scenario_path = sys.argv[1]
    data_path = sys.argv[2] if len(sys.argv) > 2 else "data/realistic_retail_5k.csv"

    # Load scenario
    engine = ScenarioEngine(scenario_path=Path(scenario_path))
    print(f"✓ Loaded scenario: {engine.spec.get('scenario_id')}")

    # Load data
    df = pd.read_csv(data_path)
    print(f"✓ Loaded data: {df.shape}")

    # Apply scenario
    mapping = {
        "treatment": "treatment",
        "y": "y",
        "cost": "cost",
        "unit_id": "user_id",
        "cluster_id": "region"
    }

    result = engine.apply_scenario(df, mapping)

    print(f"\n=== Scenario: {result.scenario_id} ===")
    print(f"Base outcome mean: {result.df_base['y'].mean():.2f}")
    print(f"CF outcome mean: {result.df_cf['y'].mean():.2f}")
    print(f"Delta outcome mean: {result.df_delta['y'].mean():.2f}")
    print(f"\nTreatment rate - Base: {result.df_base['treatment'].mean():.2%}")
    print(f"Treatment rate - CF: {result.df_cf['treatment'].mean():.2%}")
