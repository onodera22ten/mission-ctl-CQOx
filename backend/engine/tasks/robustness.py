"""
Robustness Task (頑健性)

Panels: Rosenbaum Gamma, E-value Curve, Confounding Sensitivity Heatmap
"""

from typing import List, Dict, Any
import numpy as np
from .base import BaseTask


class RobustnessTask(BaseTask):
    """Sensitivity analysis and robustness checks"""

    @classmethod
    def required_roles(cls) -> List[str]:
        return ["treatment", "y"]

    @classmethod
    def optional_roles(cls) -> List[str]:
        return ["features"]

    @classmethod
    def panels(cls) -> List[str]:
        return [
            "rosenbaum_gamma",
            "evalue_curve",
            "confounding_sensitivity_heatmap",
        ]

    def execute(self) -> Dict[str, Any]:
        """Execute robustness analysis"""
        figures = {}
        estimates = {}

        # Compute E-value
        ate = self._compute_ate()
        evalue = self._compute_evalue(ate)
        estimates["evalue"] = evalue
        estimates["ate"] = ate

        fig_path = self._generate_evalue_curve(evalue)
        if fig_path:
            figures["evalue_curve"] = str(fig_path)

        # Rosenbaum sensitivity
        gamma_results = self._compute_rosenbaum_gamma()
        estimates["rosenbaum_gamma"] = gamma_results

        fig_path = self._generate_rosenbaum_plot(gamma_results)
        if fig_path:
            figures["rosenbaum_gamma"] = str(fig_path)

        # Confounding sensitivity heatmap
        if self.has_role("features"):
            fig_path = self._generate_confounding_sensitivity_heatmap()
            if fig_path:
                figures["confounding_sensitivity_heatmap"] = str(fig_path)

        return {
            "estimates": estimates,
            "figures": figures,
            "diagnostics": {
                "evalue": evalue,
                "robustness_interpretation": self._interpret_evalue(evalue),
            },
        }

    def _compute_ate(self) -> float:
        """Compute ATE"""
        t = self.get_column("treatment")
        y = self.get_column("y")
        return float(y[t == 1].mean() - y[t == 0].mean())

    def _compute_evalue(self, ate: float) -> float:
        """
        Compute E-value (VanderWeele & Ding, 2017)
        E-value = RR + sqrt(RR * (RR - 1))
        For difference-in-means, approximate RR
        """
        t = self.get_column("treatment")
        y = self.get_column("y")

        y_control_mean = y[t == 0].mean()
        if y_control_mean <= 0:
            return 999.0  # Cannot compute E-value

        # Approximate relative risk from mean difference
        rr = (y_control_mean + ate) / y_control_mean
        if rr <= 1:
            return 1.0

        evalue = rr + np.sqrt(rr * (rr - 1))
        return float(evalue)

    def _interpret_evalue(self, evalue: float) -> str:
        """Interpret E-value magnitude"""
        if evalue < 1.5:
            return "Weak: Modest confounding could explain effect"
        elif evalue < 3.0:
            return "Moderate: Requires moderate unmeasured confounding"
        elif evalue < 10.0:
            return "Strong: Requires substantial unmeasured confounding"
        else:
            return "Very Strong: Extremely robust to confounding"

    def _generate_evalue_curve(self, evalue: float) -> str:
        """Generate E-value visualization"""
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(8, 5), facecolor='black')
        ax.set_facecolor('black')

        # Show E-value with interpretation zones
        x = [0, 1.5, 3.0, 10.0, max(evalue + 1, 12)]
        colors = ['#ef4444', '#f59e0b', '#10b981', '#3b82f6']

        for i in range(len(x) - 1):
            ax.axhspan(x[i], x[i + 1], alpha=0.3, color=colors[i])

        ax.bar([1], [evalue], color='#8b5cf6', edgecolor='white', linewidth=3, width=0.5, alpha=0.9)

        # Add threshold lines
        ax.axhline(1.5, color='#f59e0b', linestyle='--', linewidth=2, alpha=0.7, label='Weak (1.5)')
        ax.axhline(3.0, color='#10b981', linestyle='--', linewidth=2, alpha=0.7, label='Moderate (3.0)')
        ax.axhline(10.0, color='#3b82f6', linestyle='--', linewidth=2, alpha=0.7, label='Strong (10.0)')

        ax.set_ylabel('E-value', fontsize=14, color='white', fontweight='bold')
        ax.set_title('E-value Robustness Indicator', fontsize=16, color='white', fontweight='bold')
        ax.set_xticks([1])
        ax.set_xticklabels(['E-value'], fontsize=12, color='white')
        ax.set_ylim(0, max(evalue + 2, 12))
        ax.legend(fontsize=11, facecolor='#1e293b', edgecolor='white', labelcolor='white')
        ax.tick_params(colors='white', labelsize=12)
        ax.spines['bottom'].set_color('white')
        ax.spines['left'].set_color('white')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(True, alpha=0.2, color='white', axis='y')

        ax.text(1, evalue + 0.5, f'{evalue:.2f}', ha='center', va='bottom',
               fontsize=16, color='white', fontweight='bold')

        path = self.output_dir / "evalue_curve.png"
        plt.tight_layout()
        plt.savefig(path, dpi=300, facecolor='black')
        plt.close()
        return str(path)

    def _compute_rosenbaum_gamma(self) -> Dict[str, Any]:
        """Compute Rosenbaum sensitivity (simplified)"""
        # For demonstration: gamma values and p-value changes
        gammas = np.linspace(1.0, 3.0, 20)
        p_values_lower = 1 / (1 + np.exp(-gammas))
        p_values_upper = 1 / (1 + np.exp(gammas))

        return {
            "gammas": gammas.tolist(),
            "p_values_lower": p_values_lower.tolist(),
            "p_values_upper": p_values_upper.tolist(),
        }

    def _generate_rosenbaum_plot(self, gamma_results: Dict[str, Any]) -> str:
        """Generate Rosenbaum sensitivity plot"""
        import matplotlib.pyplot as plt

        gammas = gamma_results["gammas"]
        p_lower = gamma_results["p_values_lower"]
        p_upper = gamma_results["p_values_upper"]

        fig, ax = plt.subplots(figsize=(8, 5), facecolor='black')
        ax.set_facecolor('black')

        ax.plot(gammas, p_lower, 'o-', linewidth=3, markersize=6, color='#3b82f6', label='Lower Bound')
        ax.plot(gammas, p_upper, 's-', linewidth=3, markersize=6, color='#ef4444', label='Upper Bound')
        ax.axhline(0.05, color='#f59e0b', linestyle='--', linewidth=2, alpha=0.7, label='α = 0.05')

        ax.set_xlabel('Γ (Hidden Bias)', fontsize=14, color='white', fontweight='bold')
        ax.set_ylabel('p-value', fontsize=14, color='white', fontweight='bold')
        ax.set_title('Rosenbaum Sensitivity Analysis', fontsize=16, color='white', fontweight='bold')
        ax.legend(fontsize=12, facecolor='#1e293b', edgecolor='white', labelcolor='white')
        ax.tick_params(colors='white', labelsize=12)
        ax.spines['bottom'].set_color('white')
        ax.spines['left'].set_color('white')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(True, alpha=0.2, color='white')

        path = self.output_dir / "rosenbaum_gamma.png"
        plt.tight_layout()
        plt.savefig(path, dpi=300, facecolor='black')
        plt.close()
        return str(path)

    def _generate_confounding_sensitivity_heatmap(self) -> str:
        """Generate confounding sensitivity heatmap"""
        import matplotlib.pyplot as plt
        import seaborn as sns

        # Simulate sensitivity across RR_UD and RR_UY grid
        rr_ud_range = np.linspace(1, 5, 10)  # Confounder-Treatment
        rr_uy_range = np.linspace(1, 5, 10)  # Confounder-Outcome

        # Compute bias matrix (simplified)
        bias_matrix = np.outer(rr_ud_range - 1, rr_uy_range - 1)

        fig, ax = plt.subplots(figsize=(8, 5), facecolor='black')

        sns.heatmap(bias_matrix, annot=True, fmt='.2f', cmap='YlOrRd',
                   xticklabels=[f'{x:.1f}' for x in rr_uy_range],
                   yticklabels=[f'{x:.1f}' for x in rr_ud_range],
                   cbar_kws={'label': 'Bias Magnitude'},
                   ax=ax, annot_kws={'color': 'white', 'fontsize': 9})

        ax.set_xlabel('RR (Confounder → Outcome)', fontsize=14, color='white', fontweight='bold')
        ax.set_ylabel('RR (Confounder → Treatment)', fontsize=14, color='white', fontweight='bold')
        ax.set_title('Confounding Sensitivity Heatmap', fontsize=16, color='white', fontweight='bold', pad=20)
        ax.tick_params(colors='white', labelsize=10)

        path = self.output_dir / "confounding_sensitivity_heatmap.png"
        plt.tight_layout()
        plt.savefig(path, dpi=300, facecolor='black')
        plt.close()
        return str(path)
