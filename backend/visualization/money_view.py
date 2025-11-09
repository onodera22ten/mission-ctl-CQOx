"""
Money-View Visualization Utilities - NASA/Google Standard

Purpose: Generate monetary-value overlays for all visualizations
Features:
- Dual-axis charts (metric on left, ¥ on right)
- Automatic value_per_y conversion
- Currency formatting with locale support
- Waterfall charts for ΔProfit decomposition
- S0 vs S1 side-by-side comparison with ¥

Design Principle:
"Every metric must have a monetary interpretation visible to decision-makers"
"""

from __future__ import annotations

from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import json

import numpy as np
import pandas as pd


def format_currency(
    value: float,
    currency: str = "JPY",
    locale: str = "ja_JP"
) -> str:
    """
    Format value as currency with locale-specific formatting

    Args:
        value: Numeric value
        currency: Currency code (JPY, USD, EUR, etc.)
        locale: Locale identifier

    Returns:
        Formatted currency string
    """
    # Simplified formatting (full implementation would use babel)
    if currency == "JPY":
        return f"¥{value:,.0f}"
    elif currency == "USD":
        return f"${value:,.2f}"
    elif currency == "EUR":
        return f"€{value:,.2f}"
    else:
        return f"{currency} {value:,.2f}"


def convert_to_monetary(
    values: np.ndarray,
    value_per_y: float = 1.0,
    costs: Optional[np.ndarray] = None
) -> np.ndarray:
    """
    Convert outcome values to monetary terms

    Args:
        values: Outcome values (e.g., conversions, clicks)
        value_per_y: Monetary value per outcome unit
        costs: Optional cost array to subtract

    Returns:
        Profit array (¥)
    """
    profit = values * value_per_y
    if costs is not None:
        profit = profit - costs
    return profit


def generate_waterfall_data(
    baseline: float,
    components: Dict[str, float],
    scenario_total: float
) -> List[Dict[str, Any]]:
    """
    Generate waterfall chart data for ΔProfit decomposition

    Args:
        baseline: S0 baseline value (¥)
        components: Dictionary of component changes
                   e.g., {"Direct Effect": 1000, "Indirect Effect": 500, "Cost Change": -200}
        scenario_total: S1 total value (¥)

    Returns:
        List of waterfall data points for visualization

    Example:
        >>> data = generate_waterfall_data(
        ...     baseline=10000,
        ...     components={"Direct": 1500, "Indirect": 500, "Cost": -300},
        ...     scenario_total=11700
        ... )
    """
    waterfall_data = []

    # Start with baseline
    waterfall_data.append({
        "category": "S0: Baseline",
        "value": baseline,
        "cumulative": baseline,
        "type": "baseline"
    })

    cumulative = baseline

    # Add components
    for component, delta in components.items():
        cumulative += delta
        waterfall_data.append({
            "category": component,
            "value": delta,
            "cumulative": cumulative,
            "type": "increase" if delta > 0 else "decrease"
        })

    # End with scenario total
    waterfall_data.append({
        "category": "S1: Scenario",
        "value": scenario_total,
        "cumulative": scenario_total,
        "type": "total"
    })

    return waterfall_data


def generate_comparison_table(
    baseline_result: Dict[str, Any],
    scenario_result: Dict[str, Any],
    value_per_y: float = 1.0,
    currency: str = "JPY"
) -> pd.DataFrame:
    """
    Generate S0 vs S1 comparison table with monetary values

    Args:
        baseline_result: S0 evaluation result
        scenario_result: S1 evaluation result
        value_per_y: Monetary value per outcome unit
        currency: Currency code

    Returns:
        Comparison DataFrame with columns [Metric, S0, S1, Δ, Δ%]
    """
    s0_value = baseline_result.get("value", 0.0)
    s1_value = scenario_result.get("value", 0.0)
    delta = s1_value - s0_value
    delta_pct = (delta / abs(s0_value)) * 100 if s0_value != 0 else 0.0

    comparison_data = {
        "Metric": ["Value", "95% CI Lower", "95% CI Upper", "Std Error"],
        "S0 (Baseline)": [
            format_currency(s0_value, currency),
            format_currency(baseline_result.get("ci", [0, 0])[0], currency),
            format_currency(baseline_result.get("ci", [0, 0])[1], currency),
            format_currency(baseline_result.get("std_error", 0.0), currency)
        ],
        "S1 (Scenario)": [
            format_currency(s1_value, currency),
            format_currency(scenario_result.get("ci", [0, 0])[0], currency),
            format_currency(scenario_result.get("ci", [0, 0])[1], currency),
            format_currency(scenario_result.get("std_error", 0.0), currency)
        ],
        "Δ (Change)": [
            format_currency(delta, currency),
            "-",
            "-",
            "-"
        ],
        "Δ% (Pct Change)": [
            f"{delta_pct:+.1f}%",
            "-",
            "-",
            "-"
        ]
    }

    return pd.DataFrame(comparison_data)


def generate_dual_axis_config(
    metric_name: str,
    metric_unit: str,
    value_per_y: float,
    currency: str = "JPY"
) -> Dict[str, Any]:
    """
    Generate configuration for dual-axis chart (metric + monetary)

    Args:
        metric_name: Name of metric (e.g., "Conversions", "Clicks")
        metric_unit: Unit of metric (e.g., "count", "rate")
        value_per_y: Monetary value per metric unit
        currency: Currency code

    Returns:
        Chart configuration dict for plotting libraries

    Example:
        This can be used with matplotlib, plotly, or other visualization libraries
        to create dual-axis charts where:
        - Left Y-axis: Metric in original units
        - Right Y-axis: Monetary value (¥)
    """
    return {
        "left_axis": {
            "label": f"{metric_name} ({metric_unit})",
            "formatter": lambda x: f"{x:,.0f}"
        },
        "right_axis": {
            "label": f"Monetary Value ({currency})",
            "formatter": lambda x: format_currency(x, currency),
            "conversion": value_per_y
        },
        "title": f"{metric_name} with Monetary Overlay",
        "style": {
            "left_color": "#3B82F6",  # Blue
            "right_color": "#10B981"  # Green (money)
        }
    }


def annotate_with_monetary_value(
    df: pd.DataFrame,
    outcome_col: str,
    value_per_y: float = 1.0,
    cost_col: Optional[str] = None,
    currency: str = "JPY"
) -> pd.DataFrame:
    """
    Add monetary value annotations to DataFrame

    Args:
        df: Input DataFrame
        outcome_col: Outcome column name
        value_per_y: Monetary value per outcome unit
        cost_col: Cost column (optional)
        currency: Currency code

    Returns:
        DataFrame with added columns:
        - _monetary_value: Monetary value (¥)
        - _monetary_value_formatted: Formatted string
    """
    df = df.copy()

    # Compute monetary value
    monetary_value = df[outcome_col] * value_per_y
    if cost_col and cost_col in df.columns:
        monetary_value = monetary_value - df[cost_col]

    df["_monetary_value"] = monetary_value
    df["_monetary_value_formatted"] = df["_monetary_value"].apply(
        lambda x: format_currency(x, currency)
    )

    return df


def create_money_view_summary(
    results: Dict[str, Any],
    value_per_y: float = 1.0,
    currency: str = "JPY"
) -> Dict[str, Any]:
    """
    Create Money-View summary for any evaluation result

    Args:
        results: Evaluation results dictionary
        value_per_y: Monetary value per outcome unit
        currency: Currency code

    Returns:
        Money-View summary with formatted monetary values
    """
    baseline = results.get("baseline", {})
    scenario = results.get("scenario", {})
    delta = results.get("delta", {})

    s0_value = baseline.get("value", 0.0)
    s1_value = scenario.get("value", 0.0)
    delta_value = delta.get("value", 0.0)

    return {
        "currency": currency,
        "value_per_y": value_per_y,
        "baseline": {
            "value": s0_value,
            "formatted": format_currency(s0_value, currency),
            "ci": [format_currency(c, currency) for c in baseline.get("ci", [0, 0])]
        },
        "scenario": {
            "value": s1_value,
            "formatted": format_currency(s1_value, currency),
            "ci": [format_currency(c, currency) for c in scenario.get("ci", [0, 0])]
        },
        "delta": {
            "absolute": delta_value,
            "formatted": format_currency(delta_value, currency),
            "percentage": (delta_value / abs(s0_value)) * 100 if s0_value != 0 else 0.0,
            "interpretation": _interpret_monetary_delta(delta_value, currency)
        }
    }


def _interpret_monetary_delta(delta: float, currency: str) -> str:
    """Interpret monetary delta in human-readable terms"""
    if delta > 0:
        magnitude = "significant" if abs(delta) > 10000 else "modest"
        return f"Positive {magnitude} profit increase: {format_currency(delta, currency)}"
    elif delta < 0:
        magnitude = "significant" if abs(delta) > 10000 else "modest"
        return f"Negative {magnitude} profit decrease: {format_currency(abs(delta), currency)}"
    else:
        return "No significant profit change detected"


# Export utilities

def export_money_view_report(
    results: Dict[str, Any],
    value_per_y: float,
    output_path: Path,
    currency: str = "JPY"
) -> Path:
    """
    Export Money-View report as JSON

    Args:
        results: Evaluation results
        value_per_y: Value per outcome unit
        output_path: Output file path
        currency: Currency code

    Returns:
        Path to exported file
    """
    money_view_summary = create_money_view_summary(results, value_per_y, currency)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(money_view_summary, f, indent=2)

    return output_path
