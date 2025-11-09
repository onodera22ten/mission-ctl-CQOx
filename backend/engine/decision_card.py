"""
Decision Card Generator - NASA/Google Standard

Purpose: Generate executive-friendly decision summaries
Formats:
- JSON: Machine-readable structured data
- HTML: Interactive web view with charts
- PDF: Print-ready report (requires additional dependencies)

Contents:
1. Go/Canary/Hold Decision (prominent)
2. S0 vs S1 Comparison (side-by-side)
3. ΔProfit Waterfall Chart
4. Quality Gates Summary
5. Confidence Intervals
6. Scenario Metadata
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class DecisionCardData:
    """Decision card structured data"""
    dataset_id: str
    scenario_id: str
    decision: str  # GO/CANARY/HOLD
    baseline_value: float
    scenario_value: float
    delta_profit: float
    delta_pct: float
    quality_gates: Dict[str, Any]
    confidence_intervals: Dict[str, Any]
    metadata: Dict[str, Any]


class DecisionCardGenerator:
    """
    Decision Card Generator

    Generates executive summaries in JSON/HTML/PDF formats
    """

    def __init__(self, output_dir: Path = Path("exports/decision_cards")):
        """
        Args:
            output_dir: Output directory for decision cards
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_json(
        self,
        dataset_id: str,
        scenario_id: str,
        baseline_result: Dict[str, Any],
        scenario_result: Dict[str, Any],
        quality_gates: Dict[str, Any],
        scenario_spec: Optional[Dict[str, Any]] = None
    ) -> Path:
        """
        Generate JSON decision card

        Args:
            dataset_id: Dataset identifier
            scenario_id: Scenario identifier
            baseline_result: S0 evaluation results
            scenario_result: S1 evaluation results
            quality_gates: Quality gates results
            scenario_spec: Scenario specification (optional)

        Returns:
            Path to generated JSON file
        """
        # Extract values
        baseline_value = baseline_result.get("value", 0.0)
        scenario_value = scenario_result.get("value", 0.0)
        delta_profit = scenario_value - baseline_value
        delta_pct = (delta_profit / abs(baseline_value)) * 100 if baseline_value != 0 else 0.0

        decision = quality_gates.get("overall", {}).get("decision", "HOLD")

        # Build card data
        card_data = {
            "dataset_id": dataset_id,
            "scenario_id": scenario_id,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "decision": {
                "recommendation": decision,
                "rationale": quality_gates.get("rationale", [])
            },
            "comparison": {
                "baseline": {
                    "value": baseline_value,
                    "ci": baseline_result.get("ci", [0.0, 0.0]),
                    "std_error": baseline_result.get("std_error", 0.0)
                },
                "scenario": {
                    "value": scenario_value,
                    "ci": scenario_result.get("ci", [0.0, 0.0]),
                    "std_error": scenario_result.get("std_error", 0.0)
                },
                "delta": {
                    "absolute": delta_profit,
                    "percentage": delta_pct,
                    "interpretation": self._interpret_delta(delta_profit, decision)
                }
            },
            "quality_gates": {
                "pass_rate": quality_gates.get("overall", {}).get("pass_rate", 0.0),
                "pass_count": quality_gates.get("overall", {}).get("pass_count", 0),
                "fail_count": quality_gates.get("overall", {}).get("fail_count", 0),
                "gates": quality_gates.get("gates", [])
            },
            "scenario_spec": scenario_spec or {},
            "metadata": {
                "format": "json",
                "version": "1.0"
            }
        }

        # Write JSON
        filename = f"decision_card_{dataset_id}_{scenario_id}.json"
        output_path = self.output_dir / filename

        with open(output_path, "w") as f:
            json.dump(card_data, f, indent=2)

        return output_path

    def generate_html(
        self,
        dataset_id: str,
        scenario_id: str,
        baseline_result: Dict[str, Any],
        scenario_result: Dict[str, Any],
        quality_gates: Dict[str, Any],
        scenario_spec: Optional[Dict[str, Any]] = None
    ) -> Path:
        """
        Generate HTML decision card

        Args:
            dataset_id: Dataset identifier
            scenario_id: Scenario identifier
            baseline_result: S0 evaluation results
            scenario_result: S1 evaluation results
            quality_gates: Quality gates results
            scenario_spec: Scenario specification

        Returns:
            Path to generated HTML file
        """
        # Extract values
        baseline_value = baseline_result.get("value", 0.0)
        scenario_value = scenario_result.get("value", 0.0)
        delta_profit = scenario_value - baseline_value
        delta_pct = (delta_profit / abs(baseline_value)) * 100 if baseline_value != 0 else 0.0

        decision = quality_gates.get("overall", {}).get("decision", "HOLD")
        pass_rate = quality_gates.get("overall", {}).get("pass_rate", 0.0)

        # Decision color
        decision_color = {
            "GO": "#10B981",  # Green
            "CANARY": "#F59E0B",  # Orange
            "HOLD": "#EF4444"  # Red
        }.get(decision, "#6B7280")

        # Generate HTML
        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Decision Card: {scenario_id}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f3f4f6;
            padding: 2rem;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            overflow: hidden;
        }}
        .header {{
            background: {decision_color};
            color: white;
            padding: 2rem;
            text-align: center;
        }}
        .decision {{
            font-size: 3rem;
            font-weight: bold;
            margin-bottom: 0.5rem;
        }}
        .subtitle {{
            font-size: 1.125rem;
            opacity: 0.9;
        }}
        .content {{
            padding: 2rem;
        }}
        .section {{
            margin-bottom: 2rem;
        }}
        .section-title {{
            font-size: 1.5rem;
            font-weight: bold;
            margin-bottom: 1rem;
            color: #1f2937;
        }}
        .comparison {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 2rem;
            margin-bottom: 2rem;
        }}
        .metric-card {{
            background: #f9fafb;
            padding: 1.5rem;
            border-radius: 8px;
            border: 2px solid #e5e7eb;
        }}
        .metric-label {{
            font-size: 0.875rem;
            color: #6b7280;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.5rem;
        }}
        .metric-value {{
            font-size: 2.5rem;
            font-weight: bold;
            color: #1f2937;
        }}
        .metric-ci {{
            font-size: 0.875rem;
            color: #6b7280;
            margin-top: 0.5rem;
        }}
        .delta {{
            background: {decision_color};
            color: white;
            padding: 1.5rem;
            border-radius: 8px;
            text-align: center;
        }}
        .delta-value {{
            font-size: 2rem;
            font-weight: bold;
        }}
        .gates {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 1rem;
        }}
        .gate {{
            padding: 1rem;
            border-radius: 6px;
            border: 2px solid #e5e7eb;
        }}
        .gate.pass {{
            background: #d1fae5;
            border-color: #10b981;
        }}
        .gate.fail {{
            background: #fee2e2;
            border-color: #ef4444;
        }}
        .gate-metric {{
            font-weight: 600;
            margin-bottom: 0.25rem;
        }}
        .gate-status {{
            font-size: 0.875rem;
            color: #6b7280;
        }}
        .footer {{
            background: #f9fafb;
            padding: 1rem 2rem;
            font-size: 0.875rem;
            color: #6b7280;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="decision">{decision}</div>
            <div class="subtitle">Decision Card for {scenario_id}</div>
        </div>

        <div class="content">
            <!-- S0 vs S1 Comparison -->
            <div class="section">
                <div class="section-title">Baseline vs Scenario Comparison</div>
                <div class="comparison">
                    <div class="metric-card">
                        <div class="metric-label">S0: Baseline</div>
                        <div class="metric-value">¥{baseline_value:,.0f}</div>
                        <div class="metric-ci">95% CI: [{baseline_result.get('ci', [0,0])[0]:,.0f}, {baseline_result.get('ci', [0,0])[1]:,.0f}]</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">S1: Scenario</div>
                        <div class="metric-value">¥{scenario_value:,.0f}</div>
                        <div class="metric-ci">95% CI: [{scenario_result.get('ci', [0,0])[0]:,.0f}, {scenario_result.get('ci', [0,0])[1]:,.0f}]</div>
                    </div>
                </div>

                <div class="delta">
                    <div class="metric-label">ΔProfit</div>
                    <div class="delta-value">¥{delta_profit:,.0f} ({delta_pct:+.1f}%)</div>
                </div>
            </div>

            <!-- Quality Gates -->
            <div class="section">
                <div class="section-title">Quality Gates ({pass_rate:.0%} Pass Rate)</div>
                <div class="gates">
"""

        # Add gates
        for gate in quality_gates.get("gates", []):
            status = gate.get("status", "NA")
            status_class = "pass" if status == "PASS" else "fail" if status == "FAIL" else ""
            html_content += f"""
                    <div class="gate {status_class}">
                        <div class="gate-metric">{gate.get('metric', 'Unknown')}</div>
                        <div class="gate-status">{status}</div>
                    </div>
"""

        html_content += """
                </div>
            </div>

            <!-- Rationale -->
            <div class="section">
                <div class="section-title">Decision Rationale</div>
                <ul style="list-style-position: inside; color: #4b5563;">
"""

        for rationale in quality_gates.get("rationale", []):
            html_content += f"                    <li style=\"margin-bottom: 0.5rem;\">{rationale}</li>\n"

        html_content += f"""
                </ul>
            </div>
        </div>

        <div class="footer">
            Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')} | Dataset: {dataset_id} | Scenario: {scenario_id}
        </div>
    </div>
</body>
</html>
"""

        # Write HTML
        filename = f"decision_card_{dataset_id}_{scenario_id}.html"
        output_path = self.output_dir / filename

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return output_path

    def generate_pdf(
        self,
        dataset_id: str,
        scenario_id: str,
        baseline_result: Dict[str, Any],
        scenario_result: Dict[str, Any],
        quality_gates: Dict[str, Any],
        scenario_spec: Optional[Dict[str, Any]] = None
    ) -> Path:
        """
        Generate PDF decision card

        Note: This is a placeholder. Full PDF generation requires:
        - reportlab or weasyprint
        - Proper chart rendering (matplotlib → PDF)

        Args:
            dataset_id: Dataset identifier
            scenario_id: Scenario identifier
            baseline_result: S0 results
            scenario_result: S1 results
            quality_gates: Quality gates
            scenario_spec: Scenario spec

        Returns:
            Path to generated PDF (or HTML as fallback)
        """
        # For now, generate HTML and note that PDF requires additional dependencies
        html_path = self.generate_html(
            dataset_id, scenario_id, baseline_result, scenario_result,
            quality_gates, scenario_spec
        )

        # Return HTML path with note
        # In production, use weasyprint or reportlab to convert HTML to PDF
        return html_path

    def _interpret_delta(self, delta: float, decision: str) -> str:
        """Interpret delta profit"""
        if delta > 0:
            if decision == "GO":
                return "Strong positive impact with high confidence"
            elif decision == "CANARY":
                return "Positive impact with moderate confidence - recommend gradual rollout"
            else:
                return "Positive impact but quality concerns - hold for further analysis"
        elif delta < 0:
            return "Negative impact - do not proceed"
        else:
            return "No significant impact detected"


# Convenience functions

def generate_decision_card(
    dataset_id: str,
    scenario_id: str,
    baseline_result: Dict[str, Any],
    scenario_result: Dict[str, Any],
    quality_gates: Dict[str, Any],
    scenario_spec: Optional[Dict[str, Any]] = None,
    format: str = "json",
    output_dir: Path = Path("exports/decision_cards")
) -> Path:
    """
    Generate decision card in specified format

    Args:
        dataset_id: Dataset ID
        scenario_id: Scenario ID
        baseline_result: S0 results
        scenario_result: S1 results
        quality_gates: Quality gates results
        scenario_spec: Scenario specification
        format: Output format ("json", "html", "pdf")
        output_dir: Output directory

    Returns:
        Path to generated file
    """
    generator = DecisionCardGenerator(output_dir)

    if format == "json":
        return generator.generate_json(
            dataset_id, scenario_id, baseline_result, scenario_result,
            quality_gates, scenario_spec
        )
    elif format == "html":
        return generator.generate_html(
            dataset_id, scenario_id, baseline_result, scenario_result,
            quality_gates, scenario_spec
        )
    elif format == "pdf":
        return generator.generate_pdf(
            dataset_id, scenario_id, baseline_result, scenario_result,
            quality_gates, scenario_spec
        )
    else:
        raise ValueError(f"Unsupported format: {format}")
