"""
Heterogeneity Task (ヘテロ効果探索)

Panels: CATE Histogram, CATE Quantile, Top/Bottom Subgroups, Dose-Response,
        Subgraph CATE, Counterfactual Panel, Importance (SHAP), Fairness
"""

from typing import List, Dict, Any
import numpy as np
import pandas as pd
from .base import BaseTask


class HeterogeneityTask(BaseTask):
    """Conditional Average Treatment Effect (CATE) and heterogeneity analysis"""

    @classmethod
    def required_roles(cls) -> List[str]:
        return ["treatment", "y", "features"]

    @classmethod
    def optional_roles(cls) -> List[str]:
        return ["cluster_id", "unit_id", "dose"]

    @classmethod
    def panels(cls) -> List[str]:
        return [
            "cate_hist",
            "cate_quantile",
            "top_bottom_subgroups",
            "dose_response",
            "subgraph_cate",
            "counterfactual_panel",
            "importance_shap",
            "fairness_counterfactual",
        ]

    def execute(self) -> Dict[str, Any]:
        """Execute heterogeneity analysis"""
        figures = {}
        estimates = {}

        # Compute CATE (simple quantile-based for now)
        cate_scores = self._compute_cate()
        estimates["cate_scores"] = cate_scores.tolist() if isinstance(cate_scores, np.ndarray) else cate_scores

        # CATE distribution
        fig_path = self._generate_cate_histogram(cate_scores)
        if fig_path:
            figures["cate_hist"] = str(fig_path)

        # CATE quantile bars
        fig_path = self._generate_cate_quantile(cate_scores)
        if fig_path:
            figures["cate_quantile"] = str(fig_path)

        # Top/Bottom subgroups
        subgroups = self._identify_subgroups(cate_scores)
        estimates["top_subgroups"] = subgroups["top"]
        estimates["bottom_subgroups"] = subgroups["bottom"]
        fig_path = self._generate_top_bottom_subgroups(subgroups)
        if fig_path:
            figures["top_bottom_subgroups"] = str(fig_path)

        # Dose-response (if dose available)
        if self.has_role("dose"):
            dose_response = self._compute_dose_response()
            estimates["dose_response"] = dose_response
            fig_path = self._generate_dose_response_plot(dose_response)
            if fig_path:
                figures["dose_response"] = str(fig_path)

        return {
            "estimates": estimates,
            "figures": figures,
            "diagnostics": {
                "cate_variance": float(np.var(cate_scores)),
                "cate_iqr": float(np.percentile(cate_scores, 75) - np.percentile(cate_scores, 25)),
            },
        }

    def _compute_cate(self) -> np.ndarray:
        """Compute CATE scores (simplified quantile-based method)"""
        t = self.get_column("treatment")
        y = self.get_column("y")
        feature_cols = [col for col in self.df.columns if col.startswith('x_')]

        if len(feature_cols) == 0:
            # Fallback: return ATE for everyone
            ate = y[t == 1].mean() - y[t == 0].mean()
            return np.full(len(self.df), ate)

        # Simple method: stratify by feature quantiles
        from sklearn.ensemble import RandomForestRegressor

        X = self.df[feature_cols].fillna(0)
        y_treated = y.copy()
        y_treated[t == 0] = np.nan

        y_control = y.copy()
        y_control[t == 1] = np.nan

        # Train models for E[Y|X,T=1] and E[Y|X,T=0]
        rf_treated = RandomForestRegressor(n_estimators=50, max_depth=5, random_state=42)
        rf_control = RandomForestRegressor(n_estimators=50, max_depth=5, random_state=42)

        mask_treated = t == 1
        mask_control = t == 0

        rf_treated.fit(X[mask_treated], y[mask_treated])
        rf_control.fit(X[mask_control], y[mask_control])

        # CATE = E[Y|X,T=1] - E[Y|X,T=0]
        y1_pred = rf_treated.predict(X)
        y0_pred = rf_control.predict(X)
        cate = y1_pred - y0_pred

        return cate

    def _generate_cate_histogram(self, cate_scores: np.ndarray) -> str:
        """Generate CATE distribution histogram"""
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(8, 5), facecolor='black')
        ax.set_facecolor('black')

        ax.hist(cate_scores, bins=40, color='#8b5cf6', edgecolor='white', alpha=0.8)
        ax.axvline(np.mean(cate_scores), color='#3b82f6', linestyle='--',
                  linewidth=3, label=f'Mean CATE: {np.mean(cate_scores):.2f}')
        ax.axvline(0, color='#94a3b8', linestyle='-', linewidth=2, alpha=0.5)

        ax.set_xlabel('Conditional Average Treatment Effect (CATE)', fontsize=14, color='white', fontweight='bold')
        ax.set_ylabel('Frequency', fontsize=14, color='white', fontweight='bold')
        ax.set_title('CATE Distribution (Heterogeneous Treatment Effects)', fontsize=16, color='white', fontweight='bold')
        ax.legend(fontsize=12, facecolor='#1e293b', edgecolor='white', labelcolor='white')
        ax.tick_params(colors='white', labelsize=12)
        ax.spines['bottom'].set_color('white')
        ax.spines['left'].set_color('white')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(True, alpha=0.2, color='white')

        path = self.output_dir / "cate_hist.png"
        plt.tight_layout()
        plt.savefig(path, dpi=300, facecolor='black')
        plt.close()
        return str(path)

    def _generate_cate_quantile(self, cate_scores: np.ndarray) -> str:
        """Generate CATE quantile bars"""
        import matplotlib.pyplot as plt

        quantiles = [0, 0.25, 0.5, 0.75, 1.0]
        q_values = np.percentile(cate_scores, [q * 100 for q in quantiles])

        fig, ax = plt.subplots(figsize=(8, 5), facecolor='black')
        ax.set_facecolor('black')

        labels = ['Min', 'Q25', 'Median', 'Q75', 'Max']
        colors = plt.cm.viridis(np.linspace(0.2, 0.8, len(labels)))

        ax.bar(labels, q_values, color=colors, edgecolor='white', linewidth=2)
        ax.axhline(np.mean(cate_scores), color='#ef4444', linestyle='--',
                  linewidth=3, label=f'Mean: {np.mean(cate_scores):.2f}')

        ax.set_ylabel('CATE Value', fontsize=14, color='white', fontweight='bold')
        ax.set_title('CATE Quantiles', fontsize=16, color='white', fontweight='bold')
        ax.legend(fontsize=12, facecolor='#1e293b', edgecolor='white', labelcolor='white')
        ax.tick_params(colors='white', labelsize=12)
        ax.spines['bottom'].set_color('white')
        ax.spines['left'].set_color('white')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(True, alpha=0.2, color='white', axis='y')

        path = self.output_dir / "cate_quantile.png"
        plt.tight_layout()
        plt.savefig(path, dpi=300, facecolor='black')
        plt.close()
        return str(path)

    def _identify_subgroups(self, cate_scores: np.ndarray) -> Dict[str, Any]:
        """Identify top and bottom subgroups by CATE"""
        n_top = min(5, len(cate_scores) // 10)
        top_idx = np.argsort(cate_scores)[-n_top:][::-1]
        bottom_idx = np.argsort(cate_scores)[:n_top]

        return {
            "top": {"indices": top_idx.tolist(), "cate_values": cate_scores[top_idx].tolist()},
            "bottom": {"indices": bottom_idx.tolist(), "cate_values": cate_scores[bottom_idx].tolist()},
        }

    def _generate_top_bottom_subgroups(self, subgroups: Dict[str, Any]) -> str:
        """Generate top/bottom subgroups comparison"""
        import matplotlib.pyplot as plt

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 5), facecolor='black')
        for ax in [ax1, ax2]:
            ax.set_facecolor('black')

        # Top subgroups
        top_vals = subgroups["top"]["cate_values"]
        ax1.barh(range(len(top_vals)), top_vals, color='#10b981', edgecolor='white', linewidth=2)
        ax1.set_xlabel('CATE Value', fontsize=13, color='white', fontweight='bold')
        ax1.set_ylabel('Unit Index', fontsize=13, color='white', fontweight='bold')
        ax1.set_title('Top Responders (Highest CATE)', fontsize=15, color='white', fontweight='bold')
        ax1.tick_params(colors='white', labelsize=11)
        ax1.spines['bottom'].set_color('white')
        ax1.spines['left'].set_color('white')
        ax1.spines['top'].set_visible(False)
        ax1.spines['right'].set_visible(False)
        ax1.grid(True, alpha=0.2, color='white', axis='x')

        # Bottom subgroups
        bottom_vals = subgroups["bottom"]["cate_values"]
        ax2.barh(range(len(bottom_vals)), bottom_vals, color='#ef4444', edgecolor='white', linewidth=2)
        ax2.set_xlabel('CATE Value', fontsize=13, color='white', fontweight='bold')
        ax2.set_ylabel('Unit Index', fontsize=13, color='white', fontweight='bold')
        ax2.set_title('Bottom Responders (Lowest CATE)', fontsize=15, color='white', fontweight='bold')
        ax2.tick_params(colors='white', labelsize=11)
        ax2.spines['bottom'].set_color('white')
        ax2.spines['left'].set_color('white')
        ax2.spines['top'].set_visible(False)
        ax2.spines['right'].set_visible(False)
        ax2.grid(True, alpha=0.2, color='white', axis='x')

        path = self.output_dir / "top_bottom_subgroups.png"
        plt.tight_layout()
        plt.savefig(path, dpi=300, facecolor='black')
        plt.close()
        return str(path)

    def _compute_dose_response(self) -> Dict[str, Any]:
        """Compute dose-response curve"""
        dose = self.get_column("dose")
        y = self.get_column("y")

        dose_levels = sorted(dose.unique())
        mean_response = [y[dose == d].mean() for d in dose_levels]

        return {
            "dose_levels": [float(d) for d in dose_levels],
            "mean_response": [float(m) for m in mean_response],
        }

    def _generate_dose_response_plot(self, dose_response: Dict[str, Any]) -> str:
        """Generate dose-response curve"""
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(8, 5), facecolor='black')
        ax.set_facecolor('black')

        doses = dose_response["dose_levels"]
        responses = dose_response["mean_response"]

        ax.plot(doses, responses, 'o-', linewidth=3, markersize=10,
               color='#8b5cf6', markerfacecolor='#3b82f6', markeredgecolor='white', markeredgewidth=2)

        ax.set_xlabel('Dose Level', fontsize=14, color='white', fontweight='bold')
        ax.set_ylabel('Mean Outcome', fontsize=14, color='white', fontweight='bold')
        ax.set_title('Dose-Response Curve', fontsize=16, color='white', fontweight='bold')
        ax.tick_params(colors='white', labelsize=12)
        ax.spines['bottom'].set_color('white')
        ax.spines['left'].set_color('white')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(True, alpha=0.2, color='white')

        path = self.output_dir / "dose_response.png"
        plt.tight_layout()
        plt.savefig(path, dpi=300, facecolor='black')
        plt.close()
        return str(path)
