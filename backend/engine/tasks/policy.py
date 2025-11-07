"""
Policy Optimization Task (方策最適化)

Panels: Cost-Effect Curve, Threshold Optimization, Profit Curve,
        Counterfactual Policy Compare
"""

from typing import List, Dict, Any
import numpy as np
from .base import BaseTask


class PolicyTask(BaseTask):
    """Policy optimization and uplift modeling"""

    @classmethod
    def required_roles(cls) -> List[str]:
        return ["treatment", "y"]

    @classmethod
    def optional_roles(cls) -> List[str]:
        return ["cost", "features"]

    @classmethod
    def panels(cls) -> List[str]:
        return [
            "cost_effect_curve",
            "threshold_optimization",
            "profit_curve",
            "counterfactual_policy_compare",
        ]

    def execute(self) -> Dict[str, Any]:
        """Execute policy optimization"""
        figures = {}
        estimates = {}

        # Basic treatment effect
        ate = self._compute_ate()
        estimates["ate"] = ate

        # Cost-effect analysis
        if self.has_role("cost"):
            cost_effect = self._compute_cost_effect()
            estimates["cost_per_unit_effect"] = cost_effect["cost_per_effect"]

            fig_path = self._generate_cost_effect_curve(cost_effect)
            if fig_path:
                figures["cost_effect_curve"] = str(fig_path)

            # Profit curve
            profit_curve = self._compute_profit_curve()
            estimates["optimal_treatment_rate"] = profit_curve["optimal_rate"]

            fig_path = self._generate_profit_curve(profit_curve)
            if fig_path:
                figures["profit_curve"] = str(fig_path)

        # Threshold optimization (CATE-based targeting)
        if self.has_role("features"):
            threshold_opt = self._compute_threshold_optimization()
            estimates["optimal_threshold"] = threshold_opt["optimal_threshold"]

            fig_path = self._generate_threshold_plot(threshold_opt)
            if fig_path:
                figures["threshold_optimization"] = str(fig_path)

        return {
            "estimates": estimates,
            "figures": figures,
            "diagnostics": {
                "policy_recommendation": self._generate_policy_recommendation(estimates),
            },
        }

    def _compute_ate(self) -> float:
        """Compute ATE"""
        t = self.get_column("treatment")
        y = self.get_column("y")
        return float(y[t == 1].mean() - y[t == 0].mean())

    def _compute_cost_effect(self) -> Dict[str, Any]:
        """Compute cost-effectiveness metrics"""
        cost = self.get_column("cost")
        t = self.get_column("treatment")
        y = self.get_column("y")

        ate = self._compute_ate()
        avg_cost = float(cost[t == 1].mean())

        cost_per_effect = avg_cost / ate if ate != 0 else float('inf')

        return {
            "cost_per_effect": cost_per_effect,
            "avg_cost": avg_cost,
            "ate": ate,
        }

    def _generate_cost_effect_curve(self, cost_effect: Dict[str, Any]) -> str:
        """Generate cost-effectiveness frontier"""
        import matplotlib.pyplot as plt

        # Simulate different policy scenarios
        treatment_rates = np.linspace(0, 1, 20)
        costs = cost_effect["avg_cost"] * treatment_rates
        effects = cost_effect["ate"] * treatment_rates

        fig, ax = plt.subplots(figsize=(8, 5), facecolor='black')
        ax.set_facecolor('black')

        ax.plot(costs, effects, 'o-', linewidth=3, markersize=8,
               color='#3b82f6', markerfacecolor='#8b5cf6', markeredgecolor='white', markeredgewidth=2)

        # Mark current policy
        current_rate = 0.5  # Assume 50% treatment rate
        current_cost = cost_effect["avg_cost"] * current_rate
        current_effect = cost_effect["ate"] * current_rate
        ax.scatter([current_cost], [current_effect], s=200, color='#ef4444',
                  edgecolor='white', linewidth=3, zorder=5, label='Current Policy')

        ax.set_xlabel('Total Cost', fontsize=14, color='white', fontweight='bold')
        ax.set_ylabel('Total Effect', fontsize=14, color='white', fontweight='bold')
        ax.set_title('Cost-Effectiveness Frontier', fontsize=16, color='white', fontweight='bold')
        ax.legend(fontsize=12, facecolor='#1e293b', edgecolor='white', labelcolor='white')
        ax.tick_params(colors='white', labelsize=12)
        ax.spines['bottom'].set_color('white')
        ax.spines['left'].set_color('white')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(True, alpha=0.2, color='white')

        path = self.output_dir / "cost_effect_curve.png"
        plt.tight_layout()
        plt.savefig(path, dpi=300, facecolor='black')
        plt.close()
        return str(path)

    def _compute_profit_curve(self) -> Dict[str, Any]:
        """Compute profit curve across treatment rates"""
        cost = self.get_column("cost")
        t = self.get_column("treatment")
        y = self.get_column("y")

        ate = self._compute_ate()
        avg_cost = float(cost[t == 1].mean())

        # Simulate different treatment rates
        treatment_rates = np.linspace(0, 1, 50)
        profits = []

        for rate in treatment_rates:
            benefit = ate * rate
            cost_total = avg_cost * rate
            profit = benefit - cost_total
            profits.append(profit)

        optimal_idx = np.argmax(profits)
        optimal_rate = float(treatment_rates[optimal_idx])

        return {
            "treatment_rates": treatment_rates.tolist(),
            "profits": profits,
            "optimal_rate": optimal_rate,
            "max_profit": float(profits[optimal_idx]),
        }

    def _generate_profit_curve(self, profit_curve: Dict[str, Any]) -> str:
        """Generate profit curve"""
        import matplotlib.pyplot as plt

        rates = profit_curve["treatment_rates"]
        profits = profit_curve["profits"]
        optimal_rate = profit_curve["optimal_rate"]
        max_profit = profit_curve["max_profit"]

        fig, ax = plt.subplots(figsize=(8, 5), facecolor='black')
        ax.set_facecolor('black')

        ax.plot(rates, profits, linewidth=3, color='#10b981')
        ax.axvline(optimal_rate, color='#ef4444', linestyle='--', linewidth=3,
                  label=f'Optimal Rate: {optimal_rate:.2%}', alpha=0.8)
        ax.axhline(0, color='#94a3b8', linestyle='-', linewidth=2, alpha=0.5)

        ax.scatter([optimal_rate], [max_profit], s=200, color='#ef4444',
                  edgecolor='white', linewidth=3, zorder=5)

        ax.set_xlabel('Treatment Rate', fontsize=14, color='white', fontweight='bold')
        ax.set_ylabel('Profit (Benefit - Cost)', fontsize=14, color='white', fontweight='bold')
        ax.set_title('Profit Curve (Optimal Treatment Allocation)', fontsize=16, color='white', fontweight='bold')
        ax.legend(fontsize=12, facecolor='#1e293b', edgecolor='white', labelcolor='white')
        ax.tick_params(colors='white', labelsize=12)
        ax.spines['bottom'].set_color('white')
        ax.spines['left'].set_color('white')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(True, alpha=0.2, color='white')

        # Format x-axis as percentage
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:.0%}'))

        path = self.output_dir / "profit_curve.png"
        plt.tight_layout()
        plt.savefig(path, dpi=300, facecolor='black')
        plt.close()
        return str(path)

    def _compute_threshold_optimization(self) -> Dict[str, Any]:
        """Compute optimal CATE threshold for treatment assignment"""
        t = self.get_column("treatment")
        y = self.get_column("y")
        feature_cols = [col for col in self.df.columns if col.startswith('x_')]

        if len(feature_cols) == 0:
            return {"optimal_threshold": 0.0, "utilities": []}

        # Estimate CATE (simplified)
        from sklearn.ensemble import RandomForestRegressor

        X = self.df[feature_cols].fillna(0)
        mask_treated = t == 1
        mask_control = t == 0

        rf_treated = RandomForestRegressor(n_estimators=30, max_depth=5, random_state=42)
        rf_control = RandomForestRegressor(n_estimators=30, max_depth=5, random_state=42)

        rf_treated.fit(X[mask_treated], y[mask_treated])
        rf_control.fit(X[mask_control], y[mask_control])

        cate = rf_treated.predict(X) - rf_control.predict(X)

        # Test different thresholds
        thresholds = np.percentile(cate, np.linspace(0, 100, 20))
        utilities = []

        for threshold in thresholds:
            # Assign treatment if CATE > threshold
            would_treat = cate > threshold
            # Utility = sum of positive effects
            utility = np.sum(cate[would_treat])
            utilities.append(float(utility))

        optimal_idx = np.argmax(utilities)
        optimal_threshold = float(thresholds[optimal_idx])

        return {
            "thresholds": thresholds.tolist(),
            "utilities": utilities,
            "optimal_threshold": optimal_threshold,
        }

    def _generate_threshold_plot(self, threshold_opt: Dict[str, Any]) -> str:
        """Generate threshold optimization curve"""
        import matplotlib.pyplot as plt

        thresholds = threshold_opt["thresholds"]
        utilities = threshold_opt["utilities"]
        optimal_threshold = threshold_opt["optimal_threshold"]

        fig, ax = plt.subplots(figsize=(8, 5), facecolor='black')
        ax.set_facecolor('black')

        ax.plot(thresholds, utilities, 'o-', linewidth=3, markersize=6, color='#8b5cf6')
        ax.axvline(optimal_threshold, color='#ef4444', linestyle='--', linewidth=3,
                  label=f'Optimal: {optimal_threshold:.3f}', alpha=0.8)

        ax.set_xlabel('CATE Threshold', fontsize=14, color='white', fontweight='bold')
        ax.set_ylabel('Total Utility', fontsize=14, color='white', fontweight='bold')
        ax.set_title('Threshold Optimization for Treatment Assignment', fontsize=16, color='white', fontweight='bold')
        ax.legend(fontsize=12, facecolor='#1e293b', edgecolor='white', labelcolor='white')
        ax.tick_params(colors='white', labelsize=12)
        ax.spines['bottom'].set_color('white')
        ax.spines['left'].set_color('white')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(True, alpha=0.2, color='white')

        path = self.output_dir / "threshold_optimization.png"
        plt.tight_layout()
        plt.savefig(path, dpi=300, facecolor='black')
        plt.close()
        return str(path)

    def _generate_policy_recommendation(self, estimates: Dict[str, Any]) -> str:
        """Generate policy recommendation text"""
        ate = estimates.get("ate", 0)

        if ate > 0:
            if "optimal_treatment_rate" in estimates:
                return f"Positive effect detected (ATE={ate:.3f}). Optimal treatment rate: {estimates['optimal_treatment_rate']:.1%}"
            else:
                return f"Positive effect detected (ATE={ate:.3f}). Consider expanding treatment."
        else:
            return f"No positive effect detected (ATE={ate:.3f}). Reconsider treatment strategy."
