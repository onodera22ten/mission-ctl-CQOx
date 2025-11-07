# backend/counterfactual/counterfactual_systems.py
"""
反実仮想パラメータ設定機能（3系統）

【日本語サマリ】このモジュールは3系統の反実仮想システムを実装する。
- なぜ必要か: 異なる仮定の下での効果推定が必要（Plan1.pdf準拠）
- 何をするか: 線形、非線形、機械学習ベースの3系統を提供
- どう検証するか: 各系統で反実仮想結果を比較検証

【Inputs】
- df: DataFrame（観測データ）
- mapping: 列マッピング
- system_type: "linear", "nonlinear", "ml_based"

【Outputs】
- counterfactual_outcomes: 反実仮想結果
- parameters: 推定パラメータ
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, Tuple, Literal
from dataclasses import dataclass
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.ensemble import RandomForestRegressor
from sklearn.neural_network import MLPRegressor
import logging

logger = logging.getLogger(__name__)


@dataclass
class CounterfactualResult:
    """反実仮想推定結果"""
    system_type: str  # "linear", "nonlinear", "ml_based"
    counterfactual_outcomes: np.ndarray  # Y(0) の推定値
    treatment_outcomes: np.ndarray  # Y(1) の推定値（観測/推定）
    treatment_effect: np.ndarray  # Y(1) - Y(0)
    parameters: Dict[str, Any]  # 推定パラメータ
    diagnostics: Dict[str, Any]  # 診断情報


class LinearCounterfactualSystem:
    """
    系統1: 線形反実仮想システム
    
    Y(0) = α + βX + ε
    
    仮定:
    - 線形関係
    - 共変量Xの線形結合で潜在結果を推定
    """
    
    def __init__(self, alpha: float = 0.05):
        self.alpha = alpha
        self.model = None
        self.params = {}
    
    def estimate(
        self,
        df: pd.DataFrame,
        y_col: str,
        t_col: str,
        X_cols: list[str]
    ) -> CounterfactualResult:
        """
        線形モデルで反実仮想を推定
        
        Args:
            df: データフレーム
            y_col: 結果変数
            t_col: 処置変数
            X_cols: 共変量リスト
            
        Returns:
            CounterfactualResult
        """
        # コントロール群でのみ学習
        control_mask = df[t_col] == 0
        df_control = df[control_mask].copy()
        
        if len(df_control) == 0:
            raise ValueError("No control observations found")
        
        X_control = df_control[X_cols].values
        y_control = df_control[y_col].values
        
        # 線形回帰で学習
        self.model = LinearRegression()
        self.model.fit(X_control, y_control)
        
        # 全データで反実仮想結果を予測
        X_all = df[X_cols].values
        y0_pred = self.model.predict(X_all)
        
        # 処置群の観測結果
        treated_mask = df[t_col] == 1
        y1_observed = df.loc[treated_mask, y_col].values
        y1_pred = np.full(len(df), np.nan)
        y1_pred[treated_mask] = y1_observed
        
        # コントロール群の観測結果で補完
        y1_pred[~treated_mask] = y0_pred[~treated_mask]
        
        # 処置効果
        treatment_effect = y1_pred - y0_pred
        
        # パラメータ
        self.params = {
            "intercept": float(self.model.intercept_),
            "coefficients": self.model.coef_.tolist(),
            "r_squared": float(self.model.score(X_control, y_control))
        }
        
        diagnostics = {
            "n_control": len(df_control),
            "n_treated": int(control_mask.sum()),
            "model_score": self.params["r_squared"],
            "feature_names": X_cols
        }
        
        return CounterfactualResult(
            system_type="linear",
            counterfactual_outcomes=y0_pred,
            treatment_outcomes=y1_pred,
            treatment_effect=treatment_effect,
            parameters=self.params,
            diagnostics=diagnostics
        )


class NonlinearCounterfactualSystem:
    """
    系統2: 非線形反実仮想システム
    
    Y(0) = α + β₁X + β₂X² + β₃X³ + ... + ε
    
    仮定:
    - 非線形関係を多項式で近似
    - より柔軟な関数形式
    """
    
    def __init__(self, degree: int = 2, alpha: float = 0.05):
        self.degree = degree
        self.alpha = alpha
        self.model = None
        self.params = {}
    
    def estimate(
        self,
        df: pd.DataFrame,
        y_col: str,
        t_col: str,
        X_cols: list[str]
    ) -> CounterfactualResult:
        """
        非線形モデル（多項式/Ridge）で反実仮想を推定
        """
        from sklearn.preprocessing import PolynomialFeatures
        
        # コントロール群でのみ学習
        control_mask = df[t_col] == 0
        df_control = df[control_mask].copy()
        
        if len(df_control) == 0:
            raise ValueError("No control observations found")
        
        X_control = df_control[X_cols].values
        y_control = df_control[y_col].values
        
        # 多項式特徴量変換
        poly = PolynomialFeatures(degree=self.degree, include_bias=True)
        X_poly_control = poly.fit_transform(X_control)
        
        # Ridge回帰（正則化）
        self.model = Ridge(alpha=1.0)
        self.model.fit(X_poly_control, y_control)
        
        # 全データで反実仮想結果を予測
        X_all = df[X_cols].values
        X_poly_all = poly.transform(X_all)
        y0_pred = self.model.predict(X_poly_all)
        
        # 処置群の観測結果
        treated_mask = df[t_col] == 1
        y1_observed = df.loc[treated_mask, y_col].values
        y1_pred = np.full(len(df), np.nan)
        y1_pred[treated_mask] = y1_observed
        y1_pred[~treated_mask] = y0_pred[~treated_mask]
        
        # 処置効果
        treatment_effect = y1_pred - y0_pred
        
        self.params = {
            "degree": self.degree,
            "n_features": X_poly_control.shape[1],
            "r_squared": float(self.model.score(X_poly_control, y_control)),
            "regularization_alpha": 1.0
        }
        
        diagnostics = {
            "n_control": len(df_control),
            "n_treated": int(control_mask.sum()),
            "polynomial_degree": self.degree,
            "model_score": self.params["r_squared"]
        }
        
        return CounterfactualResult(
            system_type="nonlinear",
            counterfactual_outcomes=y0_pred,
            treatment_outcomes=y1_pred,
            treatment_effect=treatment_effect,
            parameters=self.params,
            diagnostics=diagnostics
        )


class MLBasedCounterfactualSystem:
    """
    系統3: 機械学習ベース反実仮想システム
    
    Y(0) = f(X; θ)
    
    仮定:
    - 任意の非線形関数を機械学習で近似
    - Random Forest / Neural Network
    """
    
    def __init__(
        self,
        model_type: Literal["random_forest", "neural_network"] = "random_forest",
        alpha: float = 0.05
    ):
        self.model_type = model_type
        self.alpha = alpha
        self.model = None
        self.params = {}
    
    def estimate(
        self,
        df: pd.DataFrame,
        y_col: str,
        t_col: str,
        X_cols: list[str]
    ) -> CounterfactualResult:
        """
        機械学習モデルで反実仮想を推定
        """
        # コントロール群でのみ学習
        control_mask = df[t_col] == 0
        df_control = df[control_mask].copy()
        
        if len(df_control) == 0:
            raise ValueError("No control observations found")
        
        X_control = df_control[X_cols].values
        y_control = df_control[y_col].values
        
        # モデル選択
        if self.model_type == "random_forest":
            self.model = RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                random_state=42,
                n_jobs=-1
            )
        elif self.model_type == "neural_network":
            self.model = MLPRegressor(
                hidden_layer_sizes=(50, 50),
                max_iter=500,
                random_state=42,
                early_stopping=True
            )
        else:
            raise ValueError(f"Unknown model type: {self.model_type}")
        
        # 学習
        self.model.fit(X_control, y_control)
        
        # 全データで反実仮想結果を予測
        X_all = df[X_cols].values
        y0_pred = self.model.predict(X_all)
        
        # 処置群の観測結果
        treated_mask = df[t_col] == 1
        y1_observed = df.loc[treated_mask, y_col].values
        y1_pred = np.full(len(df), np.nan)
        y1_pred[treated_mask] = y1_observed
        y1_pred[~treated_mask] = y0_pred[~treated_mask]
        
        # 処置効果
        treatment_effect = y1_pred - y0_pred
        
        # パラメータ
        if self.model_type == "random_forest":
            feature_importance = self.model.feature_importances_
            self.params = {
                "model_type": "random_forest",
                "n_estimators": 100,
                "max_depth": 10,
                "feature_importance": dict(zip(X_cols, feature_importance.tolist())),
                "r_squared": float(self.model.score(X_control, y_control))
            }
        else:
            self.params = {
                "model_type": "neural_network",
                "hidden_layers": (50, 50),
                "r_squared": float(self.model.score(X_control, y_control))
            }
        
        diagnostics = {
            "n_control": len(df_control),
            "n_treated": int(control_mask.sum()),
            "model_type": self.model_type,
            "model_score": self.params["r_squared"]
        }
        
        return CounterfactualResult(
            system_type="ml_based",
            counterfactual_outcomes=y0_pred,
            treatment_outcomes=y1_pred,
            treatment_effect=treatment_effect,
            parameters=self.params,
            diagnostics=diagnostics
        )


class CounterfactualSystemManager:
    """
    3系統の反実仮想システムを統合管理
    """
    
    def __init__(self):
        self.systems = {
            "linear": LinearCounterfactualSystem(),
            "nonlinear": NonlinearCounterfactualSystem(degree=2),
            "ml_based": MLBasedCounterfactualSystem(model_type="random_forest")
        }
    
    def estimate_all_systems(
        self,
        df: pd.DataFrame,
        y_col: str,
        t_col: str,
        X_cols: list[str]
    ) -> Dict[str, CounterfactualResult]:
        """
        全3系統で反実仮想を推定
        
        Returns:
            各系統の結果を辞書で返す
        """
        results = {}
        
        for system_name, system in self.systems.items():
            try:
                result = system.estimate(df, y_col, t_col, X_cols)
                results[system_name] = result
                logger.info(f"[Counterfactual] {system_name} completed: R²={result.parameters.get('r_squared', 'N/A')}")
            except Exception as e:
                logger.error(f"[Counterfactual] {system_name} failed: {e}")
                results[system_name] = None
        
        return results
    
    def compare_systems(
        self,
        results: Dict[str, CounterfactualResult]
    ) -> Dict[str, Any]:
        """
        3系統の結果を比較
        
        Returns:
            比較統計量
        """
        comparison = {}
        
        for system_name, result in results.items():
            if result is not None:
                comparison[system_name] = {
                    "mean_treatment_effect": float(np.mean(result.treatment_effect)),
                    "std_treatment_effect": float(np.std(result.treatment_effect)),
                    "r_squared": result.parameters.get("r_squared", None),
                    "n_observations": len(result.treatment_effect)
                }
        
        return comparison


# 便利関数
def estimate_counterfactuals(
    df: pd.DataFrame,
    mapping: Dict[str, str],
    systems: Optional[list[str]] = None
) -> Dict[str, CounterfactualResult]:
    """
    反実仮想を推定（簡易インターフェース）
    
    Args:
        df: データフレーム
        mapping: 列マッピング（y, treatment, covariates）
        systems: 使用する系統リスト（Noneなら全3系統）
        
    Returns:
        各系統の結果
    """
    manager = CounterfactualSystemManager()
    
    y_col = mapping.get("y")
    t_col = mapping.get("treatment")
    covariate_cols = mapping.get("covariates", [])
    
    if not y_col or not t_col:
        raise ValueError("y and treatment must be specified in mapping")
    
    if not covariate_cols:
        # 自動的に共変量を抽出
        role_cols = {y_col, t_col, mapping.get("unit_id"), mapping.get("time")}
        covariate_cols = [c for c in df.columns if c not in role_cols and df[c].dtype in ['float64', 'int64']]
    
    if systems is None:
        systems = ["linear", "nonlinear", "ml_based"]
    
    results = {}
    for system_name in systems:
        if system_name in manager.systems:
            try:
                result = manager.systems[system_name].estimate(df, y_col, t_col, covariate_cols)
                results[system_name] = result
            except Exception as e:
                logger.error(f"Counterfactual system {system_name} failed: {e}")
                results[system_name] = None
    
    return results

