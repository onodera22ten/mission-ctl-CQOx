# backend/reporting/latex_tables.py
"""
Publication-Quality LaTeX Regression Tables
Generates camera-ready tables for top economics/statistics journals
Matches output from Stata's estout, R's stargazer/modelsummary
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Union, Tuple
from dataclasses import dataclass
import re


@dataclass
class RegressionResult:
    """Results from a single regression specification"""
    coef: np.ndarray  # Coefficients
    se: np.ndarray  # Standard errors
    pval: np.ndarray  # P-values
    n_obs: int  # Number of observations
    r_squared: Optional[float] = None  # R²
    adj_r_squared: Optional[float] = None  # Adjusted R²
    outcome_var: str = "Y"  # Outcome variable name
    coef_names: Optional[List[str]] = None  # Coefficient names
    se_type: str = "robust"  # Standard error type
    cluster_var: Optional[str] = None  # Cluster variable (if clustered)


class LaTeXRegressionTable:
    """
    Generate publication-quality regression tables in LaTeX

    Supports:
    - Multi-column specifications
    - Stars for significance levels
    - Robust/cluster-robust standard errors
    - Summary statistics
    - AER/QJE/JPE/Econometrica styles
    """

    def __init__(self, results: List[RegressionResult], style: str = "aer"):
        """
        Args:
            results: List of RegressionResult objects (one per specification)
            style: Journal style ("aer", "qje", "jpe", "econometrica", "nber")
        """
        self.results = results
        self.style = style.lower()

        # Style configurations
        self.styles = {
            "aer": {
                "font_size": "\\small",
                "table_env": "table",
                "caption_position": "top",
                "notes_position": "below",
                "stars": True,
                "star_levels": [0.10, 0.05, 0.01],
                "star_symbols": ["*", "**", "***"],
            },
            "qje": {
                "font_size": "\\footnotesize",
                "table_env": "table",
                "caption_position": "top",
                "notes_position": "below",
                "stars": True,
                "star_levels": [0.10, 0.05, 0.01],
                "star_symbols": ["*", "**", "***"],
            },
            "econometrica": {
                "font_size": "\\small",
                "table_env": "table",
                "caption_position": "top",
                "notes_position": "below",
                "stars": False,  # Econometrica prefers t-stats
                "star_levels": None,
                "star_symbols": None,
            },
        }

        self.config = self.styles.get(style, self.styles["aer"])

    def generate(
        self,
        caption: str = "Regression Results",
        label: str = "tab:regression",
        outcome_label: Optional[List[str]] = None,
        include_stats: List[str] = ["n_obs", "r_squared"],
        decimal_places: int = 3,
        se_in_parentheses: bool = True,
        notes: Optional[str] = None,
        additional_rows: Optional[Dict[str, List[str]]] = None
    ) -> str:
        """
        Generate complete LaTeX table

        Args:
            caption: Table caption
            label: LaTeX label for referencing
            outcome_label: Custom labels for outcome variables (column headers)
            include_stats: List of stats to include (n_obs, r_squared, adj_r_squared)
            decimal_places: Number of decimal places for coefficients
            se_in_parentheses: Put standard errors in parentheses
            notes: Table notes (footnote)
            additional_rows: Extra rows to add (e.g., {"Fixed Effects": ["Yes", "Yes", "No"]})

        Returns:
            Complete LaTeX table code
        """
        lines = []

        # Begin table environment
        lines.append("\\begin{table}[htbp]")
        lines.append("\\centering")
        lines.append(self.config["font_size"])

        # Caption
        if self.config["caption_position"] == "top":
            lines.append(f"\\caption{{{caption}}}")
            lines.append(f"\\label{{{label}}}")

        # Begin tabular
        n_specs = len(self.results)
        col_spec = "l" + "c" * n_specs  # Left-align row labels, center data
        lines.append(f"\\begin{{tabular}}{{{col_spec}}}")
        lines.append("\\hline\\hline")

        # Column headers (outcome variables)
        if outcome_label is None:
            outcome_label = [f"({i+1})" for i in range(n_specs)]

        header = " & ".join([""] + outcome_label) + " \\\\"
        lines.append(header)

        # Dependent variable row
        dep_vars = [r.outcome_var for r in self.results]
        dep_var_row = " & ".join(["Dependent Variable:"] + dep_vars) + " \\\\"
        lines.append(dep_var_row)
        lines.append("\\hline")

        # Coefficient rows
        coef_lines = self._format_coefficients(decimal_places, se_in_parentheses)
        lines.extend(coef_lines)

        # Additional rows (e.g., fixed effects)
        if additional_rows:
            lines.append("\\hline")
            for row_label, row_values in additional_rows.items():
                if len(row_values) != n_specs:
                    raise ValueError(f"Additional row '{row_label}' must have {n_specs} values")
                row = " & ".join([row_label] + row_values) + " \\\\"
                lines.append(row)

        # Summary statistics
        lines.append("\\hline")
        if "n_obs" in include_stats:
            n_obs_row = " & ".join(["Observations"] + [str(r.n_obs) for r in self.results]) + " \\\\"
            lines.append(n_obs_row)

        if "r_squared" in include_stats:
            r2_values = []
            for r in self.results:
                if r.r_squared is not None:
                    r2_values.append(f"{r.r_squared:.{decimal_places}f}")
                else:
                    r2_values.append("--")
            r2_row = " & ".join(["R-squared"] + r2_values) + " \\\\"
            lines.append(r2_row)

        if "adj_r_squared" in include_stats:
            adj_r2_values = []
            for r in self.results:
                if r.adj_r_squared is not None:
                    adj_r2_values.append(f"{r.adj_r_squared:.{decimal_places}f}")
                else:
                    adj_r2_values.append("--")
            adj_r2_row = " & ".join(["Adjusted R-squared"] + adj_r2_values) + " \\\\"
            lines.append(adj_r2_row)

        lines.append("\\hline\\hline")
        lines.append("\\end{tabular}")

        # Notes
        if notes or self.config["stars"]:
            notes_text = []

            if self.config["stars"]:
                star_note = self._get_star_note()
                notes_text.append(star_note)

            # SE type note
            se_types = set(r.se_type for r in self.results)
            if len(se_types) == 1:
                se_type = list(se_types)[0]
                if "cluster" in se_type.lower():
                    cluster_vars = [r.cluster_var or "ID" for r in self.results]
                    if len(set(cluster_vars)) == 1:
                        notes_text.append(f"Standard errors clustered by {cluster_vars[0]} in parentheses.")
                    else:
                        notes_text.append(f"Standard errors clustered in parentheses.")
                elif "robust" in se_type.lower():
                    notes_text.append("Robust standard errors in parentheses.")
                else:
                    notes_text.append("Standard errors in parentheses.")

            if notes:
                notes_text.append(notes)

            if notes_text:
                notes_combined = " ".join(notes_text)
                lines.append(f"\\vspace{{0.2cm}}")
                lines.append(f"\\begin{{minipage}}{{\\linewidth}}")
                lines.append(f"\\footnotesize")
                lines.append(f"\\textit{{Notes:}} {notes_combined}")
                lines.append(f"\\end{{minipage}}")

        # Caption (bottom position)
        if self.config["caption_position"] == "bottom":
            lines.append(f"\\caption{{{caption}}}")
            lines.append(f"\\label{{{label}}}")

        lines.append("\\end{table}")

        return "\n".join(lines)

    def _format_coefficients(self, decimal_places: int, se_in_parentheses: bool) -> List[str]:
        """Format coefficient rows with standard errors"""
        lines = []

        # Get all unique coefficient names
        all_coef_names = set()
        for r in self.results:
            if r.coef_names:
                all_coef_names.update(r.coef_names)

        # If no names provided, use generic names
        if not all_coef_names:
            max_k = max(len(r.coef) for r in self.results)
            all_coef_names = [f"X{i+1}" for i in range(max_k)]

        # Order coefficients (constant last)
        coef_order = []
        for name in all_coef_names:
            if name.lower() not in ["const", "constant", "intercept"]:
                coef_order.append(name)

        # Add constant at the end
        for name in all_coef_names:
            if name.lower() in ["const", "constant", "intercept"]:
                coef_order.append(name)

        # Format each coefficient
        for coef_name in coef_order:
            # Coefficient row
            coef_values = []
            se_values = []

            for r in self.results:
                if r.coef_names and coef_name in r.coef_names:
                    idx = r.coef_names.index(coef_name)
                    coef = r.coef[idx]
                    se = r.se[idx]
                    pval = r.pval[idx]

                    # Format coefficient with stars
                    coef_str = f"{coef:.{decimal_places}f}"
                    if self.config["stars"]:
                        stars = self._get_stars(pval)
                        coef_str += stars

                    coef_values.append(coef_str)

                    # Format standard error
                    se_str = f"{se:.{decimal_places}f}"
                    if se_in_parentheses:
                        se_str = f"({se_str})"
                    se_values.append(se_str)
                else:
                    # Coefficient not in this specification
                    coef_values.append("")
                    se_values.append("")

            # Clean coefficient name for display
            display_name = self._format_variable_name(coef_name)

            # Add coefficient row
            coef_row = " & ".join([display_name] + coef_values) + " \\\\"
            lines.append(coef_row)

            # Add SE row
            se_row = " & ".join([""] + se_values) + " \\\\"
            lines.append(se_row)

            # Add spacing
            lines.append("")

        return lines

    def _get_stars(self, pval: float) -> str:
        """Get significance stars based on p-value"""
        if not self.config["stars"]:
            return ""

        stars = ""
        for level, symbol in zip(self.config["star_levels"], self.config["star_symbols"]):
            if pval < level:
                stars = symbol

        return stars

    def _get_star_note(self) -> str:
        """Generate note explaining significance stars"""
        if not self.config["stars"]:
            return ""

        levels = self.config["star_levels"]
        symbols = self.config["star_symbols"]

        parts = []
        for level, symbol in zip(levels, symbols):
            parts.append(f"{symbol} $p<{level}$")

        return "Significance levels: " + ", ".join(parts) + "."

    def _format_variable_name(self, name: str) -> str:
        """Format variable name for display (e.g., replace underscores)"""
        # Convert to title case and replace underscores with spaces
        name = name.replace("_", " ")

        # Special cases
        if name.lower() in ["const", "constant"]:
            return "Constant"

        return name.title()

    def export_to_file(self, filename: str, **kwargs) -> None:
        """Export table to .tex file"""
        latex_code = self.generate(**kwargs)

        with open(filename, 'w') as f:
            f.write(latex_code)

        print(f"LaTeX table exported to: {filename}")


# Convenience function
def create_regression_table(
    results: List[RegressionResult],
    output_path: Optional[str] = None,
    **kwargs
) -> str:
    """
    Convenience function to create regression table

    Args:
        results: List of RegressionResult objects
        output_path: If provided, save to this file
        **kwargs: Additional arguments for generate()

    Returns:
        LaTeX code as string

    Example:
        >>> result1 = RegressionResult(
        ...     coef=np.array([2.5, -1.2, 0.8]),
        ...     se=np.array([0.3, 0.4, 0.2]),
        ...     pval=np.array([0.001, 0.01, 0.05]),
        ...     n_obs=1000,
        ...     r_squared=0.45,
        ...     coef_names=["Treatment", "Age", "Constant"]
        ... )
        >>> table = create_regression_table([result1], caption="My Results")
    """
    latex_table = LaTeXRegressionTable(results)
    latex_code = latex_table.generate(**kwargs)

    if output_path:
        with open(output_path, 'w') as f:
            f.write(latex_code)
        print(f"Table saved to: {output_path}")

    return latex_code


# Testing
if __name__ == "__main__":
    """Test LaTeX table generation"""

    # Create mock regression results
    result1 = RegressionResult(
        coef=np.array([2.5, -1.2, 0.8, 1.0]),
        se=np.array([0.3, 0.4, 0.2, 0.5]),
        pval=np.array([0.001, 0.01, 0.05, 0.10]),
        n_obs=1000,
        r_squared=0.45,
        adj_r_squared=0.43,
        outcome_var="Sales",
        coef_names=["Treatment", "Age", "Income", "Constant"],
        se_type="robust"
    )

    result2 = RegressionResult(
        coef=np.array([2.8, -1.0, 0.9, 0.5, 1.2]),
        se=np.array([0.35, 0.38, 0.25, 0.3, 0.6]),
        pval=np.array([0.001, 0.02, 0.03, 0.15, 0.08]),
        n_obs=1000,
        r_squared=0.52,
        adj_r_squared=0.50,
        outcome_var="Sales",
        coef_names=["Treatment", "Age", "Income", "Education", "Constant"],
        se_type="cluster",
        cluster_var="firm_id"
    )

    result3 = RegressionResult(
        coef=np.array([2.6, -1.1, 0.85, 1.1]),
        se=np.array([0.32, 0.42, 0.22, 0.55]),
        pval=np.array([0.001, 0.01, 0.04, 0.09]),
        n_obs=800,
        r_squared=0.48,
        adj_r_squared=0.46,
        outcome_var="Sales",
        coef_names=["Treatment", "Age", "Income", "Constant"],
        se_type="robust"
    )

    # Create table
    latex_code = create_regression_table(
        [result1, result2, result3],
        caption="Impact of Treatment on Sales",
        label="tab:main_results",
        outcome_label=["(1)", "(2)", "(3)"],
        include_stats=["n_obs", "r_squared", "adj_r_squared"],
        additional_rows={
            "Time Fixed Effects": ["No", "Yes", "No"],
            "Firm Fixed Effects": ["No", "No", "Yes"]
        },
        notes="Sample restricted to firms with more than 50 employees."
    )

    print("=" * 80)
    print("LATEX REGRESSION TABLE (AER STYLE)")
    print("=" * 80)
    print(latex_code)
    print("\n" + "=" * 80)
