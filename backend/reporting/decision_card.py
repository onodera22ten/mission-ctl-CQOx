"""
Decision Card Generator (Plan1.pdf準拠)
A4 PDF with Go/Hold/Redesign recommendation
"""
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
import matplotlib
matplotlib.use('Agg')  # Set backend before importing pyplot
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.patches as mpatches

# Configure matplotlib to use available fonts
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'Liberation Sans', 'sans-serif']
plt.rcParams['pdf.fonttype'] = 42  # TrueType fonts


class DecisionCard:
    """
    Decision Card PDF Generator

    Outputs:
    - Go/Hold/Redesign decision based on CAS score
    - Value/Cost/Break-even analysis
    - Quality gates (p-value, effect size, overlap, robustness)
    - Budget-Profit-Risk curve
    - Sensitivity table (±20% cost variations)
    """

    def __init__(self, job_id: str, objective_spec: Dict[str, Any]):
        self.job_id = job_id
        self.objective_spec = objective_spec

    def generate(
        self,
        cas_overall: float,
        ate: float,
        ate_ci: tuple,
        cost_per_unit: float,
        value_per_unit: float,
        gates: Dict[str, Any],
        output_path: Path
    ) -> str:
        """
        Generate Decision Card PDF

        Args:
            cas_overall: Overall CAS score (0-100)
            ate: Average Treatment Effect
            ate_ci: Confidence interval (lower, upper)
            cost_per_unit: Cost per unit
            value_per_unit: Value per unit (or CPA_max if cost unavailable)
            gates: Quality gates dict
            output_path: Output PDF path

        Returns:
            Path to generated PDF
        """
        with PdfPages(output_path) as pdf:
            # Page 1: Decision Summary
            self._generate_page1_decision(pdf, cas_overall, ate, ate_ci, cost_per_unit, value_per_unit)

            # Page 2: Quality Gates & Sensitivity
            self._generate_page2_quality(pdf, gates, cost_per_unit, value_per_unit, ate)

        return str(output_path)

    def _generate_page1_decision(self, pdf, cas_overall, ate, ate_ci, cost, value):
        """Page 1: Decision Summary"""
        fig, axes = plt.subplots(2, 2, figsize=(11.7, 8.3))  # A4 landscape
        fig.suptitle(f"Decision Card: {self.objective_spec.get('objective_id', 'Unknown')}\n"
                    f"Job ID: {self.job_id} | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                    fontsize=16, fontweight='bold')

        # Top-left: Go/Hold/Redesign Decision
        ax1 = axes[0, 0]
        ax1.axis('off')
        decision, decision_color = self._get_decision(cas_overall)
        ax1.text(0.5, 0.7, f"DECISION: {decision}", ha='center', va='center',
                fontsize=28, weight='bold', color=decision_color)
        ax1.text(0.5, 0.4, f"CAS Score: {cas_overall:.1f}/100", ha='center', va='center',
                fontsize=20)
        ax1.text(0.5, 0.2, self._get_decision_rationale(cas_overall), ha='center', va='center',
                fontsize=12, style='italic', wrap=True)

        # Top-right: Value/Cost/Break-even
        ax2 = axes[0, 1]
        ax2.axis('off')
        roi = ((ate * value) - cost) / cost * 100 if cost > 0 else 0
        breakeven = cost / value if value > 0 else 0

        ax2.text(0.1, 0.85, "Economic Analysis", fontsize=14, weight='bold')
        ax2.text(0.1, 0.70, f"ATE: {ate:.2f} (95% CI: [{ate_ci[0]:.2f}, {ate_ci[1]:.2f}])", fontsize=11)
        ax2.text(0.1, 0.55, f"Value/Unit: ¥{value:,.0f}", fontsize=11)
        ax2.text(0.1, 0.45, f"Cost/Unit: ¥{cost:,.0f}", fontsize=11)
        ax2.text(0.1, 0.30, f"ROI: {roi:.1f}%", fontsize=13, weight='bold',
                color='green' if roi > 0 else 'red')
        ax2.text(0.1, 0.15, f"Break-even ATE: {breakeven:.2f}", fontsize=11)

        # Bottom-left: Budget-Profit Curve (placeholder)
        ax3 = axes[1, 0]
        budgets = [10, 20, 30, 40, 50]
        profits = [ate * b * value - b * cost for b in budgets]
        ax3.plot(budgets, profits, 'o-', linewidth=2, markersize=8)
        ax3.axhline(y=0, color='r', linestyle='--', alpha=0.5)
        ax3.set_xlabel('Budget (Million ¥)', fontsize=10)
        ax3.set_ylabel('Incremental Profit (Million ¥)', fontsize=10)
        ax3.set_title('Budget-Profit Relationship', fontsize=12, weight='bold')
        ax3.grid(alpha=0.3)

        # Bottom-right: CAS Radar (text summary)
        ax4 = axes[1, 1]
        ax4.axis('off')
        ax4.text(0.1, 0.9, "Quality Summary", fontsize=14, weight='bold')
        ax4.text(0.1, 0.75, f"✓ CAS Overall: {cas_overall:.1f}/100", fontsize=11)
        ax4.text(0.1, 0.60, f"✓ Effect Size: {ate:.2f}", fontsize=11)
        ax4.text(0.1, 0.45, "✓ CI excludes zero" if ate_ci[0] > 0 or ate_ci[1] < 0 else "⚠ CI includes zero",
                fontsize=11)
        ax4.text(0.1, 0.30, "See Page 2 for detailed gates", fontsize=10, style='italic')

        plt.tight_layout()
        pdf.savefig(fig, dpi=150)
        plt.close(fig)

    def _generate_page2_quality(self, pdf, gates, cost_per_unit, value_per_unit, ate):
        """Page 2: Quality Gates & Sensitivity"""
        fig, axes = plt.subplots(2, 2, figsize=(11.7, 8.3))  # A4 landscape
        fig.suptitle("Quality Gates & Sensitivity Analysis", fontsize=16, weight='bold')

        # Top-left: Quality Gates Table
        ax1 = axes[0, 0]
        ax1.axis('off')
        ax1.text(0.1, 0.95, "Quality Gates", fontsize=14, weight='bold')

        gate_names = ["p-value < 0.05", "Effect Size > 0.2", "Overlap > 0.5", "SMD < 0.1", "Robustness"]
        gate_values = [
            "✓ Pass" if gates.get("p_value_pass", False) else "✗ Fail",
            "✓ Pass" if gates.get("effect_size_pass", False) else "✗ Fail",
            "✓ Pass" if gates.get("overlap_pass", False) else "✗ Fail",
            "✓ Pass" if gates.get("balance_pass", False) else "✗ Fail",
            "✓ Pass" if gates.get("robustness_pass", False) else "✗ Fail"
        ]

        y_pos = 0.80
        for name, value in zip(gate_names, gate_values):
            color = 'green' if "Pass" in value else 'red'
            ax1.text(0.1, y_pos, name, fontsize=11)
            ax1.text(0.7, y_pos, value, fontsize=11, weight='bold', color=color)
            y_pos -= 0.12

        # Top-right: Sensitivity Table (±20% cost)
        ax2 = axes[0, 1]
        ax2.axis('off')
        ax2.text(0.1, 0.95, "Cost Sensitivity (±20%)", fontsize=14, weight='bold')

        cost_scenarios = [
            ("Base Case", cost_per_unit, ate * value_per_unit - cost_per_unit),
            ("Cost -20%", cost_per_unit * 0.8, ate * value_per_unit - cost_per_unit * 0.8),
            ("Cost +20%", cost_per_unit * 1.2, ate * value_per_unit - cost_per_unit * 1.2)
        ]

        y_pos = 0.80
        ax2.text(0.1, y_pos, "Scenario", fontsize=10, weight='bold')
        ax2.text(0.4, y_pos, "Cost", fontsize=10, weight='bold')
        ax2.text(0.65, y_pos, "Profit/Unit", fontsize=10, weight='bold')
        y_pos -= 0.10

        for scenario, c, profit in cost_scenarios:
            ax2.text(0.1, y_pos, scenario, fontsize=10)
            ax2.text(0.4, y_pos, f"¥{c:,.0f}", fontsize=10)
            color = 'green' if profit > 0 else 'red'
            ax2.text(0.65, y_pos, f"¥{profit:,.0f}", fontsize=10, color=color)
            y_pos -= 0.10

        # Bottom: Risk-Return Plot (placeholder)
        ax3 = axes[1, 0]
        ax3.scatter([cost_per_unit], [ate * value_per_unit], s=200, c='blue', alpha=0.7)
        ax3.set_xlabel('Cost per Unit (¥)', fontsize=10)
        ax3.set_ylabel('Expected Value (¥)', fontsize=10)
        ax3.set_title('Risk-Return Space', fontsize=12, weight='bold')
        ax3.grid(alpha=0.3)

        # Bottom-right: Recommendations
        ax4 = axes[1, 1]
        ax4.axis('off')
        ax4.text(0.1, 0.95, "Recommendations", fontsize=14, weight='bold')
        ax4.text(0.1, 0.80, "• Review quality gates on left", fontsize=11)
        ax4.text(0.1, 0.70, "• Cost sensitivity shows ±20% scenarios", fontsize=11)
        ax4.text(0.1, 0.60, "• Refer to WolframONE visualizations for details", fontsize=11)
        ax4.text(0.1, 0.50, "• Consider counterfactual scenarios", fontsize=11)

        # plt.tight_layout()  # Skip to avoid font issues
        fig.subplots_adjust(left=0.05, right=0.95, top=0.92, bottom=0.08, hspace=0.3, wspace=0.3)
        pdf.savefig(fig, dpi=150)
        plt.close(fig)

    def _get_decision(self, cas_overall: float) -> tuple:
        """Get decision and color based on CAS score"""
        if cas_overall >= 70:
            return "GO", "green"
        elif cas_overall >= 50:
            return "CANARY", "orange"
        else:
            return "HOLD", "red"

    def _get_decision_rationale(self, cas_overall: float) -> str:
        """Get decision rationale text"""
        if cas_overall >= 70:
            return "High confidence. Safe to deploy at scale."
        elif cas_overall >= 50:
            return "Moderate confidence. Consider canary rollout."
        else:
            return "Low confidence. Redesign or gather more data."


# CLI for testing
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python decision_card.py <output.pdf>")
        sys.exit(1)

    output_path = Path(sys.argv[1])

    # Mock data
    objective_spec = {
        "objective_id": "profit_max",
        "description": "Test Decision Card"
    }

    card = DecisionCard("test_job_123", objective_spec)

    gates = {
        "p_value_pass": True,
        "effect_size_pass": True,
        "overlap_pass": True,
        "balance_pass": False,
        "robustness_pass": True
    }

    pdf_path = card.generate(
        cas_overall=75.0,
        ate=250.0,
        ate_ci=(180.0, 320.0),
        cost_per_unit=300.0,
        value_per_unit=1000.0,
        gates=gates,
        output_path=output_path
    )

    print(f"✓ Decision Card generated: {pdf_path}")
