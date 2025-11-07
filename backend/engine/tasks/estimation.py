"""
Causal Estimation Task (因果推定)

Panels: ATE Bar, ATE Density, Prior vs Posterior, Stratified ATE
"""

from typing import List, Dict, Any
import numpy as np
from .base import BaseTask


class EstimationTask(BaseTask):
    """Average Treatment Effect and causal estimation"""

    @classmethod
    def required_roles(cls) -> List[str]:
        return ["treatment", "y"]

    @classmethod
    def optional_roles(cls) -> List[str]:
        return ["features", "strata", "weight", "log_propensity"]

    @classmethod
    def panels(cls) -> List[str]:
        return [
            "ate_bar",
            "ate_density",
            "prior_vs_posterior",
            "stratified_ate",
        ]

    def execute(self) -> Dict[str, Any]:
        """Execute causal estimation"""
        figures = {}
        estimates = {}

        # Get treatment and outcome
        t = self.get_column("treatment")
        y = self.get_column("y")

        # Basic ATE estimation
        y_treated = y[t == 1]
        y_control = y[t == 0]
        ate = float(y_treated.mean() - y_control.mean())

        # Standard error (simple difference-in-means)
        se = np.sqrt(y_treated.var() / len(y_treated) + y_control.var() / len(y_control))

        estimates["ate"] = ate
        estimates["ate_se"] = float(se)
        estimates["ate_ci_lower"] = float(ate - 1.96 * se)
        estimates["ate_ci_upper"] = float(ate + 1.96 * se)

        # Generate ATE Bar with CI
        fig_path = self._generate_ate_bar(ate, se)
        if fig_path:
            figures["ate_bar"] = str(fig_path)

        # Generate ATE Density
        fig_path = self._generate_ate_density(y_treated, y_control)
        if fig_path:
            figures["ate_density"] = str(fig_path)

        # Stratified ATE if strata available
        if self.has_role("strata"):
            strata_results = self._compute_stratified_ate()
            estimates["stratified_ate"] = strata_results
            fig_path = self._generate_stratified_ate_plot(strata_results)
            if fig_path:
                figures["stratified_ate"] = str(fig_path)

        return {
            "estimates": estimates,
            "figures": figures,
            "diagnostics": {
                "n_treated": int(len(y_treated)),
                "n_control": int(len(y_control)),
                "balance_ratio": float(len(y_treated) / len(y_control)),
            },
        }

    def _generate_ate_bar(self, ate: float, se: float) -> str:
        """Generate ATE bar chart with confidence intervals"""
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(8, 5), facecolor='black')
        ax.set_facecolor('black')

        # Bar with error bars
        ax.bar([0], [ate], yerr=[1.96 * se], capsize=10,
               color='#3b82f6', edgecolor='white', linewidth=2, alpha=0.8)

        ax.axhline(0, color='#94a3b8', linestyle='--', linewidth=2, alpha=0.5)
        ax.set_ylabel('Average Treatment Effect', fontsize=14, color='white', fontweight='bold')
        ax.set_title('ATE with 95% Confidence Interval', fontsize=16, color='white', fontweight='bold')
        ax.set_xticks([0])
        ax.set_xticklabels(['ATE'], fontsize=12, color='white')
        ax.tick_params(colors='white', labelsize=12)
        ax.spines['bottom'].set_color('white')
        ax.spines['left'].set_color('white')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(True, alpha=0.2, color='white')

        # Add value label
        ax.text(0, ate, f'{ate:.3f}', ha='center', va='bottom',
                fontsize=14, color='white', fontweight='bold')

        path = self.output_dir / "ate_bar.png"
        plt.tight_layout()
        plt.savefig(path, dpi=300, facecolor='black')
        plt.close()
        return str(path)

    def _generate_ate_density(self, y_treated, y_control) -> str:
        """Generate outcome density by treatment group"""
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(8, 5), facecolor='black')
        ax.set_facecolor('black')

        ax.hist(y_control, bins=30, alpha=0.6, label='Control', color='#ef4444', edgecolor='white')
        ax.hist(y_treated, bins=30, alpha=0.6, label='Treated', color='#3b82f6', edgecolor='white')

        ax.axvline(y_control.mean(), color='#ef4444', linestyle='--', linewidth=2, label='Control Mean')
        ax.axvline(y_treated.mean(), color='#3b82f6', linestyle='--', linewidth=2, label='Treated Mean')

        ax.set_xlabel('Outcome Value', fontsize=14, color='white', fontweight='bold')
        ax.set_ylabel('Frequency', fontsize=14, color='white', fontweight='bold')
        ax.set_title('Outcome Distribution by Treatment Group', fontsize=16, color='white', fontweight='bold')
        ax.legend(fontsize=12, facecolor='#1e293b', edgecolor='white', labelcolor='white')
        ax.tick_params(colors='white', labelsize=12)
        ax.spines['bottom'].set_color('white')
        ax.spines['left'].set_color('white')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(True, alpha=0.2, color='white')

        path = self.output_dir / "ate_density.png"
        plt.tight_layout()
        plt.savefig(path, dpi=300, facecolor='black')
        plt.close()
        return str(path)

    def _compute_stratified_ate(self) -> Dict[str, float]:
        """Compute ATE within each stratum"""
        strata = self.get_column("strata")
        t = self.get_column("treatment")
        y = self.get_column("y")

        results = {}
        for stratum in strata.unique():
            mask = strata == stratum
            y_t = y[mask & (t == 1)]
            y_c = y[mask & (t == 0)]
            if len(y_t) > 0 and len(y_c) > 0:
                results[str(stratum)] = float(y_t.mean() - y_c.mean())

        return results

    def _generate_stratified_ate_plot(self, strata_results: Dict[str, float]) -> str:
        """Generate stratified ATE plot"""
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(8, 5), facecolor='black')
        ax.set_facecolor('black')

        strata_names = list(strata_results.keys())
        ate_values = list(strata_results.values())

        colors = plt.cm.viridis(np.linspace(0.2, 0.8, len(strata_names)))
        ax.barh(strata_names, ate_values, color=colors, edgecolor='white', linewidth=1.5)

        ax.axvline(0, color='#94a3b8', linestyle='--', linewidth=2, alpha=0.5)
        ax.set_xlabel('Treatment Effect', fontsize=14, color='white', fontweight='bold')
        ax.set_ylabel('Stratum', fontsize=14, color='white', fontweight='bold')
        ax.set_title('Stratified Average Treatment Effects', fontsize=16, color='white', fontweight='bold')
        ax.tick_params(colors='white', labelsize=12)
        ax.spines['bottom'].set_color('white')
        ax.spines['left'].set_color('white')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(True, alpha=0.2, color='white', axis='x')

        path = self.output_dir / "stratified_ate.png"
        plt.tight_layout()
        plt.savefig(path, dpi=300, facecolor='black')
        plt.close()
        return str(path)
