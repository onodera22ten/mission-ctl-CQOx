"""
Time-Varying Task (時間変化)

Panels: TVCE Timeseries, Event Study, Sequential Event Study
"""

from typing import List, Dict, Any
import numpy as np
import pandas as pd
from .base import BaseTask


class TimeVaryingTask(BaseTask):
    """Time-varying causal effects (TVCE, DID, Event Study)"""

    @classmethod
    def required_roles(cls) -> List[str]:
        return ["treatment", "y", "time"]

    @classmethod
    def optional_roles(cls) -> List[str]:
        return ["unit_id", "features"]

    @classmethod
    def panels(cls) -> List[str]:
        return [
            "tvce_timeseries",
            "event_study",
            "sequential_event_study",
        ]

    def execute(self) -> Dict[str, Any]:
        """Execute time-varying analysis"""
        figures = {}
        estimates = {}

        # Compute TVCE (time-varying treatment effect)
        tvce_results = self._compute_tvce()
        estimates["tvce"] = tvce_results

        fig_path = self._generate_tvce_plot(tvce_results)
        if fig_path:
            figures["tvce_timeseries"] = str(fig_path)

        # Event study (if treatment timing is available)
        event_study_results = self._compute_event_study()
        if event_study_results:
            estimates["event_study"] = event_study_results
            fig_path = self._generate_event_study_plot(event_study_results)
            if fig_path:
                figures["event_study"] = str(fig_path)

        return {
            "estimates": estimates,
            "figures": figures,
            "diagnostics": {
                "time_periods": int(len(tvce_results["periods"])),
                "effect_variance": float(np.var(tvce_results["effects"])),
            },
        }

    def _compute_tvce(self) -> Dict[str, Any]:
        """Compute time-varying causal effect"""
        t = self.get_column("treatment")
        y = self.get_column("y")
        time = self.get_column("time")

        periods = sorted(time.unique())
        effects = []
        ses = []

        for period in periods:
            mask = time == period
            y_period = y[mask]
            t_period = t[mask]

            if len(y_period[t_period == 1]) > 0 and len(y_period[t_period == 0]) > 0:
                effect = y_period[t_period == 1].mean() - y_period[t_period == 0].mean()
                se = np.sqrt(
                    y_period[t_period == 1].var() / (t_period == 1).sum() +
                    y_period[t_period == 0].var() / (t_period == 0).sum()
                )
            else:
                effect = 0.0
                se = 0.0

            effects.append(float(effect))
            ses.append(float(se))

        return {
            "periods": [str(p) for p in periods],
            "effects": effects,
            "standard_errors": ses,
        }

    def _generate_tvce_plot(self, tvce_results: Dict[str, Any]) -> str:
        """Generate TVCE time series plot"""
        import matplotlib.pyplot as plt

        periods = tvce_results["periods"]
        effects = tvce_results["effects"]
        ses = tvce_results["standard_errors"]

        fig, ax = plt.subplots(figsize=(8, 5), facecolor='black')
        ax.set_facecolor('black')

        x = np.arange(len(periods))
        effects_arr = np.array(effects)
        ses_arr = np.array(ses)

        ax.plot(x, effects_arr, 'o-', linewidth=3, markersize=8,
               color='#3b82f6', markerfacecolor='#8b5cf6', markeredgecolor='white', markeredgewidth=2)
        ax.fill_between(x, effects_arr - 1.96 * ses_arr, effects_arr + 1.96 * ses_arr,
                        alpha=0.3, color='#3b82f6', label='95% CI')

        ax.axhline(0, color='#94a3b8', linestyle='--', linewidth=2, alpha=0.5)

        ax.set_xlabel('Time Period', fontsize=14, color='white', fontweight='bold')
        ax.set_ylabel('Treatment Effect', fontsize=14, color='white', fontweight='bold')
        ax.set_title('Time-Varying Causal Effect (TVCE)', fontsize=16, color='white', fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(periods, rotation=45, ha='right', fontsize=10, color='white')
        ax.legend(fontsize=12, facecolor='#1e293b', edgecolor='white', labelcolor='white')
        ax.tick_params(colors='white', labelsize=12)
        ax.spines['bottom'].set_color('white')
        ax.spines['left'].set_color('white')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(True, alpha=0.2, color='white')

        path = self.output_dir / "tvce_timeseries.png"
        plt.tight_layout()
        plt.savefig(path, dpi=300, facecolor='black')
        plt.close()
        return str(path)

    def _compute_event_study(self) -> Dict[str, Any]:
        """Compute event study coefficients (relative to treatment timing)"""
        t = self.get_column("treatment")
        y = self.get_column("y")
        time = self.get_column("time")

        # Find treatment timing for each unit (if varies)
        treatment_times = time[t == 1].values
        if len(treatment_times) == 0:
            return None

        # For simplicity, assume single treatment event
        treatment_period = np.median(treatment_times)

        # Compute effects at different relative times
        relative_periods = range(-4, 6)  # -4 to +5 periods
        coefficients = []

        for rel_period in relative_periods:
            target_period = treatment_period + rel_period
            mask = time == target_period

            if mask.sum() > 10:
                y_period = y[mask]
                t_period = t[mask]
                if (t_period == 1).sum() > 0 and (t_period == 0).sum() > 0:
                    coef = y_period[t_period == 1].mean() - y_period[t_period == 0].mean()
                else:
                    coef = 0.0
            else:
                coef = 0.0

            coefficients.append(float(coef))

        return {
            "relative_periods": list(relative_periods),
            "coefficients": coefficients,
        }

    def _generate_event_study_plot(self, event_study: Dict[str, Any]) -> str:
        """Generate event study plot"""
        import matplotlib.pyplot as plt

        rel_periods = event_study["relative_periods"]
        coefs = event_study["coefficients"]

        fig, ax = plt.subplots(figsize=(8, 5), facecolor='black')
        ax.set_facecolor('black')

        colors = ['#ef4444' if p < 0 else '#10b981' for p in rel_periods]
        ax.bar(rel_periods, coefs, color=colors, edgecolor='white', linewidth=1.5, alpha=0.8)

        ax.axvline(0, color='#f59e0b', linestyle='--', linewidth=3, label='Treatment Event', alpha=0.8)
        ax.axhline(0, color='#94a3b8', linestyle='-', linewidth=2, alpha=0.5)

        ax.set_xlabel('Periods Relative to Treatment', fontsize=14, color='white', fontweight='bold')
        ax.set_ylabel('Treatment Effect Coefficient', fontsize=14, color='white', fontweight='bold')
        ax.set_title('Event Study Coefficients', fontsize=16, color='white', fontweight='bold')
        ax.legend(fontsize=12, facecolor='#1e293b', edgecolor='white', labelcolor='white')
        ax.tick_params(colors='white', labelsize=12)
        ax.spines['bottom'].set_color('white')
        ax.spines['left'].set_color('white')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(True, alpha=0.2, color='white', axis='y')

        path = self.output_dir / "event_study.png"
        plt.tight_layout()
        plt.savefig(path, dpi=300, facecolor='black')
        plt.close()
        return str(path)
