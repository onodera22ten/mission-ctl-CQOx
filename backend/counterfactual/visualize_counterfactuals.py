# backend/counterfactual/visualize_counterfactuals.py
"""
反実仮想パラメータ可視化モジュール

【日本語サマリ】3系統の反実仮想推定結果を比較可視化する。
- なぜ必要か: 異なる仮定下での推定結果の頑健性を確認
- 何をするか: 線形・非線形・MLベースの3系統の結果を並列比較
- どう検証するか: 推定値の分布、処置効果の違い、パラメータの安定性を可視化

【Inputs】
- results: 3系統の CounterfactualResult のリスト
- output_path: 出力先

【Outputs】
- 可視化図のパス（PNG）
"""

from __future__ import annotations
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
from typing import List, Dict, Any
from .counterfactual_systems import CounterfactualResult


def visualize_counterfactual_comparison(
    results: List[CounterfactualResult],
    output_path: Path,
    title: str = "Counterfactual Parameter Systems Comparison"
) -> str:
    """
    反実仮想パラメータ系統の比較可視化

    Args:
        results: 3系統の推定結果リスト
        output_path: 出力ファイルパス
        title: 図のタイトル

    Returns:
        保存された図のパス
    """
    if not results or len(results) == 0:
        raise ValueError("No counterfactual results provided")

    n_systems = len(results)

    # Create figure with 3 rows, 2 columns
    fig = plt.figure(figsize=(16, 12))
    gs = fig.add_gridspec(3, 2, hspace=0.35, wspace=0.3)

    # Color palette for different systems
    colors = ['#3b82f6', '#10b981', '#f59e0b']  # Blue, Green, Orange
    system_names = [r.system_type for r in results]

    # Panel 1: Counterfactual outcome distributions
    ax1 = fig.add_subplot(gs[0, 0])
    for i, result in enumerate(results):
        y0 = result.counterfactual_outcomes
        ax1.hist(y0, bins=30, alpha=0.5, color=colors[i],
                label=f'{result.system_type.capitalize()}', edgecolor='black')
    ax1.set_xlabel('Y(0) - Counterfactual Outcome', fontsize=11, fontweight='bold')
    ax1.set_ylabel('Frequency', fontsize=11, fontweight='bold')
    ax1.set_title('Counterfactual Outcome Distributions (Y₀)', fontsize=12, fontweight='bold')
    ax1.legend(fontsize=10)
    ax1.grid(True, alpha=0.3, axis='y')

    # Panel 2: Treatment effect distributions
    ax2 = fig.add_subplot(gs[0, 1])
    for i, result in enumerate(results):
        te = result.treatment_effect[~np.isnan(result.treatment_effect)]
        ax2.hist(te, bins=30, alpha=0.5, color=colors[i],
                label=f'{result.system_type.capitalize()}: μ={te.mean():.3f}',
                edgecolor='black')
    ax2.set_xlabel('Treatment Effect (τ)', fontsize=11, fontweight='bold')
    ax2.set_ylabel('Frequency', fontsize=11, fontweight='bold')
    ax2.set_title('Treatment Effect Distributions', fontsize=12, fontweight='bold')
    ax2.legend(fontsize=10)
    ax2.grid(True, alpha=0.3, axis='y')
    ax2.axvline(x=0, color='red', linestyle='--', linewidth=1.5, alpha=0.6)

    # Panel 3: System comparison (mean treatment effects)
    ax3 = fig.add_subplot(gs[1, 0])
    mean_effects = []
    std_effects = []
    for result in results:
        te = result.treatment_effect[~np.isnan(result.treatment_effect)]
        mean_effects.append(te.mean())
        std_effects.append(te.std() / np.sqrt(len(te)))  # Standard error

    x_pos = np.arange(n_systems)
    bars = ax3.bar(x_pos, mean_effects, yerr=std_effects,
                   color=colors[:n_systems], alpha=0.7,
                   capsize=5, edgecolor='black', linewidth=1.5)
    ax3.set_xticks(x_pos)
    ax3.set_xticklabels([r.system_type.capitalize() for r in results], fontsize=10)
    ax3.set_ylabel('Average Treatment Effect (ATE)', fontsize=11, fontweight='bold')
    ax3.set_title('ATE Comparison Across Systems', fontsize=12, fontweight='bold')
    ax3.axhline(y=0, color='black', linestyle='-', linewidth=1)
    ax3.grid(True, alpha=0.3, axis='y')

    # Add value labels
    for i, (bar, val) in enumerate(zip(bars, mean_effects)):
        ax3.text(i, val + std_effects[i] + 0.05, f'{val:.3f}',
                ha='center', va='bottom', fontweight='bold', fontsize=10)

    # Panel 4: Model diagnostics (R² scores)
    ax4 = fig.add_subplot(gs[1, 1])
    r2_scores = []
    for result in results:
        r2 = result.diagnostics.get('model_score', result.parameters.get('r_squared', 0.0))
        r2_scores.append(r2)

    bars2 = ax4.barh(system_names, r2_scores, color=colors[:n_systems],
                     alpha=0.7, edgecolor='black', height=0.5)
    ax4.set_xlabel('R² Score', fontsize=11, fontweight='bold')
    ax4.set_title('Model Fit Quality', fontsize=12, fontweight='bold')
    ax4.set_xlim([0, 1])
    ax4.grid(True, alpha=0.3, axis='x')

    # Add value labels
    for i, (bar, val) in enumerate(zip(bars2, r2_scores)):
        ax4.text(val + 0.02, i, f'{val:.3f}', va='center', fontweight='bold', fontsize=10)

    # Panel 5: Parameter summary table
    ax5 = fig.add_subplot(gs[2, :])
    ax5.axis('off')

    # Create parameter summary
    param_summary = []
    for result in results:
        params = result.parameters
        diag = result.diagnostics

        summary_text = f"**{result.system_type.upper()}**\n"
        summary_text += f"  • N(control): {diag.get('n_control', 'N/A')}\n"
        summary_text += f"  • N(treated): {diag.get('n_treated', 'N/A')}\n"
        summary_text += f"  • R²: {params.get('r_squared', diag.get('model_score', 0.0)):.4f}\n"

        if result.system_type == "linear":
            summary_text += f"  • Intercept: {params.get('intercept', 0.0):.3f}\n"
            summary_text += f"  • Coefficients: {len(params.get('coefficients', []))} features\n"
        elif result.system_type == "nonlinear":
            summary_text += f"  • Polynomial degree: {params.get('degree', 2)}\n"
            summary_text += f"  • N features: {params.get('n_features', 'N/A')}\n"
            summary_text += f"  • Regularization α: {params.get('regularization_alpha', 1.0)}\n"
        elif result.system_type == "ml_based":
            summary_text += f"  • Model: {params.get('model_type', 'N/A')}\n"
            if 'n_estimators' in params:
                summary_text += f"  • N estimators: {params['n_estimators']}\n"
            if 'feature_importance' in params:
                top_feat = params.get('top_features', [])
                if top_feat:
                    summary_text += f"  • Top feature: {top_feat[0]} ({params['feature_importance'][0]:.3f})\n"

        param_summary.append(summary_text)

    # Display as text boxes
    box_width = 0.28
    box_height = 0.8
    for i, text in enumerate(param_summary):
        x_pos = 0.05 + i * 0.33
        ax5.text(x_pos, 0.5, text, transform=ax5.transAxes,
                fontsize=9, verticalalignment='center',
                bbox=dict(boxstyle='round', facecolor=colors[i], alpha=0.2,
                         edgecolor=colors[i], linewidth=2),
                family='monospace')

    # Overall title
    fig.suptitle(title, fontsize=15, fontweight='bold', y=0.98)

    # Summary statistics at bottom
    ate_range = max(mean_effects) - min(mean_effects)
    summary = f"ATE Range: {ate_range:.3f}  |  Systems Compared: {n_systems}  |  "
    summary += f"Consensus ATE: {np.mean(mean_effects):.3f} ± {np.std(mean_effects):.3f}"

    fig.text(0.5, 0.02, summary, ha='center', fontsize=10,
             bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.3))

    # Save figure
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=160, bbox_inches='tight')
    plt.close(fig)

    return str(output_path)


def generate_counterfactual_report(
    results: List[CounterfactualResult],
    output_dir: Path
) -> Dict[str, Any]:
    """
    反実仮想パラメータのレポートを生成

    Args:
        results: 3系統の推定結果
        output_dir: 出力ディレクトリ

    Returns:
        レポート情報（可視化パス、統計量など）
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate visualization
    fig_path = output_dir / "counterfactual_comparison.png"
    vis_path = visualize_counterfactual_comparison(results, fig_path)

    # Calculate summary statistics
    ate_estimates = []
    for result in results:
        te = result.treatment_effect[~np.isnan(result.treatment_effect)]
        ate_estimates.append(te.mean())

    report = {
        "figure_path": vis_path,
        "n_systems": len(results),
        "ate_estimates": {
            "linear": ate_estimates[0] if len(ate_estimates) > 0 else None,
            "nonlinear": ate_estimates[1] if len(ate_estimates) > 1 else None,
            "ml_based": ate_estimates[2] if len(ate_estimates) > 2 else None,
        },
        "ate_consensus": float(np.mean(ate_estimates)),
        "ate_std": float(np.std(ate_estimates)),
        "ate_range": float(max(ate_estimates) - min(ate_estimates)),
        "robustness": "high" if np.std(ate_estimates) < 0.05 else "moderate" if np.std(ate_estimates) < 0.1 else "low",
        "systems": [r.system_type for r in results],
        "parameters": [r.parameters for r in results],
        "diagnostics": [r.diagnostics for r in results]
    }

    return report
