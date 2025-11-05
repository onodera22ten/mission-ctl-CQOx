"""
Instrumental Variables Task (IV)

Panels: IV First Stage, IV Second Stage, Weak IV Diagnostics
"""

from typing import List, Dict, Any
import numpy as np
from .base import BaseTask


class IVTask(BaseTask):
    """Instrumental Variable estimation"""

    @classmethod
    def required_roles(cls) -> List[str]:
        return ["treatment", "y", "instrument"]

    @classmethod
    def optional_roles(cls) -> List[str]:
        return ["features"]

    @classmethod
    def panels(cls) -> List[str]:
        return [
            "iv_first_stage",
            "iv_second_stage",
            "weak_iv_diagnostics",
        ]

    def execute(self) -> Dict[str, Any]:
        """Execute IV analysis"""
        figures = {}
        estimates = {}

        # First stage
        first_stage = self._compute_first_stage()
        estimates["first_stage_f_stat"] = first_stage["f_stat"]
        estimates["first_stage_r2"] = first_stage["r2"]

        fig_path = self._generate_first_stage_plot()
        if fig_path:
            figures["iv_first_stage"] = str(fig_path)

        # Second stage (2SLS estimate)
        second_stage = self._compute_second_stage()
        estimates["iv_estimate"] = second_stage["tau"]
        estimates["iv_se"] = second_stage["se"]

        fig_path = self._generate_second_stage_plot(second_stage)
        if fig_path:
            figures["iv_second_stage"] = str(fig_path)

        # Weak IV diagnostics
        fig_path = self._generate_weak_iv_diagnostics(first_stage)
        if fig_path:
            figures["weak_iv_diagnostics"] = str(fig_path)

        return {
            "estimates": estimates,
            "figures": figures,
            "diagnostics": {
                "first_stage_f": first_stage["f_stat"],
                "weak_iv_warning": first_stage["f_stat"] < 10,
            },
        }

    def _compute_first_stage(self) -> Dict[str, Any]:
        """Compute first stage: regress treatment on instrument"""
        from sklearn.linear_model import LinearRegression

        z = self.get_column("instrument").values.reshape(-1, 1)
        t = self.get_column("treatment").values

        lr = LinearRegression()
        lr.fit(z, t)
        t_pred = lr.predict(z)

        # F-statistic approximation
        residuals = t - t_pred
        ss_res = np.sum(residuals ** 2)
        ss_tot = np.sum((t - t.mean()) ** 2)
        r2 = 1 - (ss_res / ss_tot)

        n = len(t)
        k = 1  # Number of instruments
        f_stat = (r2 / k) / ((1 - r2) / (n - k - 1))

        return {
            "f_stat": float(f_stat),
            "r2": float(r2),
            "coef": float(lr.coef_[0]),
        }

    def _generate_first_stage_plot(self) -> str:
        """Generate first stage scatter plot"""
        import matplotlib.pyplot as plt

        z = self.get_column("instrument")
        t = self.get_column("treatment")

        fig, ax = plt.subplots(figsize=(8, 5), facecolor='black')
        ax.set_facecolor('black')

        ax.scatter(z, t, alpha=0.6, color='#3b82f6', edgecolor='white', s=50)

        # Fit line
        coeffs = np.polyfit(z, t, 1)
        z_line = np.linspace(z.min(), z.max(), 100)
        t_line = coeffs[0] * z_line + coeffs[1]
        ax.plot(z_line, t_line, 'r-', linewidth=3, label='First Stage Fit')

        ax.set_xlabel('Instrument (Z)', fontsize=14, color='white', fontweight='bold')
        ax.set_ylabel('Treatment (T)', fontsize=14, color='white', fontweight='bold')
        ax.set_title('IV First Stage: Z → T', fontsize=16, color='white', fontweight='bold')
        ax.legend(fontsize=12, facecolor='#1e293b', edgecolor='white', labelcolor='white')
        ax.tick_params(colors='white', labelsize=12)
        ax.spines['bottom'].set_color('white')
        ax.spines['left'].set_color('white')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(True, alpha=0.2, color='white')

        path = self.output_dir / "iv_first_stage.png"
        plt.tight_layout()
        plt.savefig(path, dpi=300, facecolor='black')
        plt.close()
        return str(path)

    def _compute_second_stage(self) -> Dict[str, Any]:
        """Compute 2SLS estimate"""
        from sklearn.linear_model import LinearRegression

        z = self.get_column("instrument").values.reshape(-1, 1)
        t = self.get_column("treatment").values
        y = self.get_column("y").values

        # First stage
        lr_first = LinearRegression()
        lr_first.fit(z, t)
        t_hat = lr_first.predict(z)

        # Second stage
        lr_second = LinearRegression()
        lr_second.fit(t_hat.reshape(-1, 1), y)
        tau = float(lr_second.coef_[0])

        # Standard error (simplified)
        residuals = y - lr_second.predict(t_hat.reshape(-1, 1))
        se = float(np.std(residuals) / np.sqrt(len(y)))

        return {
            "tau": tau,
            "se": se,
            "ci_lower": tau - 1.96 * se,
            "ci_upper": tau + 1.96 * se,
        }

    def _generate_second_stage_plot(self, second_stage: Dict[str, Any]) -> str:
        """Generate 2SLS estimate with CI"""
        import matplotlib.pyplot as plt

        tau = second_stage["tau"]
        se = second_stage["se"]

        fig, ax = plt.subplots(figsize=(8, 5), facecolor='black')
        ax.set_facecolor('black')

        ax.bar([0], [tau], yerr=[1.96 * se], capsize=10,
              color='#8b5cf6', edgecolor='white', linewidth=2, alpha=0.8)

        ax.axhline(0, color='#94a3b8', linestyle='--', linewidth=2, alpha=0.5)
        ax.set_ylabel('IV Estimate (2SLS)', fontsize=14, color='white', fontweight='bold')
        ax.set_title('Instrumental Variable Estimate with 95% CI', fontsize=16, color='white', fontweight='bold')
        ax.set_xticks([0])
        ax.set_xticklabels(['IV Estimate'], fontsize=12, color='white')
        ax.tick_params(colors='white', labelsize=12)
        ax.spines['bottom'].set_color('white')
        ax.spines['left'].set_color('white')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(True, alpha=0.2, color='white')

        ax.text(0, tau, f'{tau:.3f}', ha='center', va='bottom',
               fontsize=14, color='white', fontweight='bold')

        path = self.output_dir / "iv_second_stage.png"
        plt.tight_layout()
        plt.savefig(path, dpi=300, facecolor='black')
        plt.close()
        return str(path)

    def _generate_weak_iv_diagnostics(self, first_stage: Dict[str, Any]) -> str:
        """Generate weak IV diagnostic plot"""
        import matplotlib.pyplot as plt

        f_stat = first_stage["f_stat"]

        fig, ax = plt.subplots(figsize=(8, 5), facecolor='black')
        ax.set_facecolor('black')

        # Show F-statistic with threshold lines
        ax.bar([0], [f_stat], color='#10b981' if f_stat >= 10 else '#ef4444',
              edgecolor='white', linewidth=2, alpha=0.8, width=0.5)

        ax.axhline(10, color='#f59e0b', linestyle='--', linewidth=3,
                  label='Weak IV Threshold (F=10)', alpha=0.8)
        ax.axhline(20, color='#10b981', linestyle='--', linewidth=2,
                  label='Strong IV Threshold (F=20)', alpha=0.6)

        ax.set_ylabel('F-Statistic', fontsize=14, color='white', fontweight='bold')
        ax.set_title('Weak IV Diagnostics (First-Stage F-Test)', fontsize=16, color='white', fontweight='bold')
        ax.set_xticks([0])
        ax.set_xticklabels(['First Stage F'], fontsize=12, color='white')
        ax.legend(fontsize=11, facecolor='#1e293b', edgecolor='white', labelcolor='white')
        ax.tick_params(colors='white', labelsize=12)
        ax.spines['bottom'].set_color('white')
        ax.spines['left'].set_color('white')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(True, alpha=0.2, color='white', axis='y')

        ax.text(0, f_stat, f'F = {f_stat:.2f}', ha='center', va='bottom',
               fontsize=14, color='white', fontweight='bold')

        path = self.output_dir / "weak_iv_diagnostics.png"
        plt.tight_layout()
        plt.savefig(path, dpi=300, facecolor='black')
        plt.close()
        return str(path)
