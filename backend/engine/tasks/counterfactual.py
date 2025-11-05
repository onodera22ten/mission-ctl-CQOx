# backend/engine/tasks/counterfactual.py
"""
Counterfactual Parameter Systems Task

反実仮想パラメータ3系統（線形・非線形・ML）の推定と比較可視化を行うタスク
"""

from __future__ import annotations
from typing import Dict, Any, List
from pathlib import Path
import pandas as pd

from ..base_task import BaseTask
from ...counterfactual.counterfactual_systems import (
    LinearCounterfactualSystem,
    NonlinearCounterfactualSystem,
    MLBasedCounterfactualSystem,
    CounterfactualResult
)
from ...counterfactual.visualize_counterfactuals import generate_counterfactual_report


class CounterfactualTask(BaseTask):
    """
    反実仮想パラメータシステムタスク

    3系統で反実仮想を推定し、結果を比較可視化する：
    - 線形システム: LinearCounterfactualSystem
    - 非線形システム: NonlinearCounterfactualSystem
    - 機械学習システム: MLBasedCounterfactualSystem
    """

    def __init__(self):
        super().__init__()
        self.name = "counterfactual"
        self.description = "Counterfactual parameter systems (3 approaches)"

    def can_run(self, roles: Dict[str, str], df: pd.DataFrame) -> bool:
        """
        実行可能条件:
        - outcome (y) が必要
        - treatment (t) が必要
        - 最低1つ以上の共変量が必要
        """
        required = {"outcome", "treatment"}
        has_required = required.issubset(set(roles.keys()))

        if not has_required:
            return False

        # Check for covariates (exclude y, t, unit_id, time)
        exclude_cols = {
            roles.get("outcome"),
            roles.get("treatment"),
            roles.get("unit_id"),
            roles.get("time")
        }

        covariate_cols = [c for c in df.columns
                         if c not in exclude_cols
                         and pd.api.types.is_numeric_dtype(df[c])]

        return len(covariate_cols) >= 1

    def execute(
        self,
        df: pd.DataFrame,
        roles: Dict[str, str],
        output_dir: Path,
        **kwargs
    ) -> Dict[str, Any]:
        """
        反実仮想パラメータ3系統を実行

        Args:
            df: データフレーム
            roles: 役割マッピング
            output_dir: 出力ディレクトリ

        Returns:
            実行結果（図のパス、統計情報など）
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        # Get column names
        y_col = roles.get("outcome")
        t_col = roles.get("treatment")
        unit_id = roles.get("unit_id")
        time_col = roles.get("time")

        # Get covariates
        exclude_cols = {y_col, t_col, unit_id, time_col}
        X_cols = [c for c in df.columns
                 if c not in exclude_cols
                 and pd.api.types.is_numeric_dtype(df[c])]

        if len(X_cols) == 0:
            return {
                "status": "skipped",
                "reason": "No covariates available",
                "figures": {}
            }

        # Limit to reasonable number of covariates
        X_cols = X_cols[:10]

        results: List[CounterfactualResult] = []

        try:
            # System 1: Linear
            linear_sys = LinearCounterfactualSystem()
            linear_result = linear_sys.estimate(df, y_col, t_col, X_cols)
            results.append(linear_result)
        except Exception as e:
            print(f"Linear counterfactual system failed: {e}")

        try:
            # System 2: Nonlinear (polynomial degree 2)
            nonlinear_sys = NonlinearCounterfactualSystem(degree=2)
            nonlinear_result = nonlinear_sys.estimate(df, y_col, t_col, X_cols)
            results.append(nonlinear_result)
        except Exception as e:
            print(f"Nonlinear counterfactual system failed: {e}")

        try:
            # System 3: ML-based (Random Forest)
            ml_sys = MLBasedCounterfactualSystem(model_type="random_forest")
            ml_result = ml_sys.estimate(df, y_col, t_col, X_cols)
            results.append(ml_result)
        except Exception as e:
            print(f"ML counterfactual system failed: {e}")

        if len(results) == 0:
            return {
                "status": "failed",
                "reason": "All counterfactual systems failed",
                "figures": {}
            }

        # Generate comparison report
        try:
            report = generate_counterfactual_report(results, output_dir)

            return {
                "status": "success",
                "n_systems": len(results),
                "figures": {
                    "counterfactual_comparison": report["figure_path"]
                },
                "summary": {
                    "ate_estimates": report["ate_estimates"],
                    "ate_consensus": report["ate_consensus"],
                    "ate_std": report["ate_std"],
                    "ate_range": report["ate_range"],
                    "robustness": report["robustness"]
                },
                "parameters": report["parameters"],
                "diagnostics": report["diagnostics"]
            }
        except Exception as e:
            return {
                "status": "partial",
                "reason": f"Visualization failed: {e}",
                "n_systems": len(results),
                "figures": {}
            }
