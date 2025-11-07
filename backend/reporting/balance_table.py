# backend/reporting/balance_table.py
"""
Balance Tables for Causal Inference
Generate covariate balance tables (treated vs control)
Essential for RCTs and observational studies
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from scipy import stats


@dataclass
class BalanceResult:
    """Results from balance test for a single covariate"""
    variable: str
    mean_treated: float
    mean_control: float
    diff: float  # Treated - Control
    std_treated: float
    std_control: float
    smd: float  # Standardized mean difference
    t_stat: float
    p_value: float
    n_treated: int
    n_control: int


class BalanceTable:
    """
    Generate covariate balance tables

    Reports:
    - Mean by treatment group
    - Difference in means
    - Standardized mean difference (SMD)
    - t-statistics and p-values
    - Sample sizes

    References:
    - Austin (2009): "Balance diagnostics for comparing the distribution of baseline covariates"
    - Stuart (2010): "Matching methods for causal inference: A review"
    """

    def __init__(self, data: pd.DataFrame, treatment_col: str, covariates: List[str],
                 weights: Optional[np.ndarray] = None):
        """
        Args:
            data: DataFrame with treatment and covariates
            treatment_col: Name of treatment column (must be binary 0/1)
            covariates: List of covariate column names
            weights: Optional weights (e.g., IPW weights)
        """
        self.data = data
        self.treatment_col = treatment_col
        self.covariates = covariates
        self.weights = weights

        # Validate treatment is binary
        unique_vals = data[treatment_col].dropna().unique()
        if not set(unique_vals).issubset({0, 1}):
            raise ValueError(f"Treatment must be binary (0/1), got: {unique_vals}")

    def compute_balance(self) -> List[BalanceResult]:
        """
        Compute balance statistics for all covariates

        Returns:
            List of BalanceResult objects
        """
        results = []

        for var in self.covariates:
            # Skip if variable has missing values
            valid_mask = self.data[[var, self.treatment_col]].notna().all(axis=1)
            if valid_mask.sum() == 0:
                continue

            data_valid = self.data[valid_mask]

            treated_mask = data_valid[self.treatment_col] == 1
            control_mask = data_valid[self.treatment_col] == 0

            treated_vals = data_valid.loc[treated_mask, var].values
            control_vals = data_valid.loc[control_mask, var].values

            # Apply weights if provided
            if self.weights is not None:
                weights_valid = self.weights[valid_mask]
                treated_weights = weights_valid[treated_mask]
                control_weights = weights_valid[control_mask]

                mean_treated = np.average(treated_vals, weights=treated_weights)
                mean_control = np.average(control_vals, weights=control_weights)

                std_treated = np.sqrt(np.average((treated_vals - mean_treated)**2, weights=treated_weights))
                std_control = np.sqrt(np.average((control_vals - mean_control)**2, weights=control_weights))
            else:
                mean_treated = np.mean(treated_vals)
                mean_control = np.mean(control_vals)
                std_treated = np.std(treated_vals, ddof=1)
                std_control = np.std(control_vals, ddof=1)

            # Difference in means
            diff = mean_treated - mean_control

            # Standardized mean difference (SMD)
            # SMD = (mean_treated - mean_control) / pooled_std
            pooled_std = np.sqrt((std_treated**2 + std_control**2) / 2)
            smd = diff / pooled_std if pooled_std > 0 else 0.0

            # t-test
            if self.weights is None:
                t_stat, p_value = stats.ttest_ind(treated_vals, control_vals, equal_var=False)
            else:
                # Weighted t-test approximation
                se_treated = std_treated / np.sqrt(len(treated_vals))
                se_control = std_control / np.sqrt(len(control_vals))
                se_diff = np.sqrt(se_treated**2 + se_control**2)
                t_stat = diff / se_diff if se_diff > 0 else 0.0

                # Welch-Satterthwaite df approximation
                df = ((se_treated**2 + se_control**2)**2 /
                      (se_treated**4 / (len(treated_vals) - 1) +
                       se_control**4 / (len(control_vals) - 1)))
                p_value = 2 * (1 - stats.t.cdf(abs(t_stat), df=df))

            result = BalanceResult(
                variable=var,
                mean_treated=mean_treated,
                mean_control=mean_control,
                diff=diff,
                std_treated=std_treated,
                std_control=std_control,
                smd=smd,
                t_stat=t_stat,
                p_value=p_value,
                n_treated=len(treated_vals),
                n_control=len(control_vals)
            )

            results.append(result)

        return results

    def to_dataframe(self, results: Optional[List[BalanceResult]] = None) -> pd.DataFrame:
        """Convert results to pandas DataFrame"""
        if results is None:
            results = self.compute_balance()

        rows = []
        for r in results:
            rows.append({
                'Variable': r.variable,
                'Mean (Treated)': r.mean_treated,
                'Mean (Control)': r.mean_control,
                'Difference': r.diff,
                'SMD': r.smd,
                't-stat': r.t_stat,
                'p-value': r.p_value,
                'N (Treated)': r.n_treated,
                'N (Control)': r.n_control
            })

        return pd.DataFrame(rows)

    def to_latex(
        self,
        results: Optional[List[BalanceResult]] = None,
        caption: str = "Covariate Balance Table",
        label: str = "tab:balance",
        decimal_places: int = 3,
        include_t_stat: bool = True,
        include_pval: bool = True,
        smd_threshold: float = 0.1
    ) -> str:
        """
        Generate LaTeX balance table

        Args:
            results: BalanceResult list (computed if None)
            caption: Table caption
            label: LaTeX label
            decimal_places: Number of decimal places
            include_t_stat: Include t-statistic column
            include_pval: Include p-value column
            smd_threshold: Threshold for flagging imbalance (default: 0.1)

        Returns:
            LaTeX code
        """
        if results is None:
            results = self.compute_balance()

        lines = []

        # Begin table
        lines.append("\\begin{table}[htbp]")
        lines.append("\\centering")
        lines.append("\\small")
        lines.append(f"\\caption{{{caption}}}")
        lines.append(f"\\label{{{label}}}")

        # Column specification
        col_spec = "l" + "c" * (6 + int(include_t_stat) + int(include_pval))
        lines.append(f"\\begin{{tabular}}{{{col_spec}}}")
        lines.append("\\hline\\hline")

        # Header
        header_cols = ["Variable", "Mean\\\\(Treated)", "Mean\\\\(Control)", "Difference", "SMD"]
        if include_t_stat:
            header_cols.append("t-stat")
        if include_pval:
            header_cols.append("p-value")
        header_cols.extend(["N\\\\(Treated)", "N\\\\(Control)"])

        header = " & ".join(header_cols) + " \\\\"
        lines.append(header)
        lines.append("\\hline")

        # Data rows
        for r in results:
            row_vals = [
                self._format_variable_name(r.variable),
                f"{r.mean_treated:.{decimal_places}f}",
                f"{r.mean_control:.{decimal_places}f}",
                f"{r.diff:.{decimal_places}f}",
                self._format_smd(r.smd, smd_threshold, decimal_places)
            ]

            if include_t_stat:
                row_vals.append(f"{r.t_stat:.{decimal_places}f}")

            if include_pval:
                pval_str = f"{r.p_value:.{decimal_places}f}" if r.p_value >= 0.001 else "$<0.001$"
                # Add stars for significance
                stars = ""
                if r.p_value < 0.01:
                    stars = "***"
                elif r.p_value < 0.05:
                    stars = "**"
                elif r.p_value < 0.10:
                    stars = "*"
                row_vals.append(f"{pval_str}{stars}")

            row_vals.extend([str(r.n_treated), str(r.n_control)])

            row = " & ".join(row_vals) + " \\\\"
            lines.append(row)

        # Footer
        lines.append("\\hline\\hline")
        lines.append("\\end{tabular}")

        # Notes
        lines.append("\\vspace{0.2cm}")
        lines.append("\\begin{minipage}{\\linewidth}")
        lines.append("\\footnotesize")
        notes = [
            "\\textit{Notes:} SMD = Standardized Mean Difference.",
            f"Variables with $|\\text{{SMD}}| > {smd_threshold}$ are flagged with $\\dagger$.",
        ]
        if include_pval:
            notes.append("Significance levels: * $p<0.10$, ** $p<0.05$, *** $p<0.01$.")
        lines.append(" ".join(notes))
        lines.append("\\end{minipage}")

        lines.append("\\end{table}")

        return "\n".join(lines)

    def _format_variable_name(self, name: str) -> str:
        """Format variable name for LaTeX"""
        # Replace underscores with spaces and capitalize
        name = name.replace("_", " ").title()
        return name

    def _format_smd(self, smd: float, threshold: float, decimal_places: int) -> str:
        """Format SMD with warning flag if exceeds threshold"""
        smd_str = f"{smd:.{decimal_places}f}"

        # Flag if exceeds threshold
        if abs(smd) > threshold:
            smd_str += "$^\\dagger$"

        return smd_str

    def plot_love_plot(self, results: Optional[List[BalanceResult]] = None,
                      smd_threshold: float = 0.1) -> None:
        """
        Generate Love plot (SMD plot)

        Args:
            results: BalanceResult list
            smd_threshold: Vertical line at threshold
        """
        if results is None:
            results = self.compute_balance()

        try:
            import matplotlib.pyplot as plt
        except ImportError:
            print("Matplotlib required for Love plot")
            return

        # Sort by absolute SMD
        results_sorted = sorted(results, key=lambda x: abs(x.smd), reverse=True)

        variables = [r.variable for r in results_sorted]
        smds = [r.smd for r in results_sorted]

        # Plot
        fig, ax = plt.subplots(figsize=(10, len(variables) * 0.4))

        colors = ['red' if abs(smd) > smd_threshold else 'green' for smd in smds]
        ax.scatter(smds, range(len(smds)), c=colors, s=100, alpha=0.7)

        # Threshold lines
        ax.axvline(x=smd_threshold, color='gray', linestyle='--', linewidth=1, label=f'Threshold ({smd_threshold})')
        ax.axvline(x=-smd_threshold, color='gray', linestyle='--', linewidth=1)
        ax.axvline(x=0, color='black', linestyle='-', linewidth=1)

        ax.set_yticks(range(len(variables)))
        ax.set_yticklabels(variables)
        ax.set_xlabel('Standardized Mean Difference (SMD)', fontsize=12, fontweight='bold')
        ax.set_title('Covariate Balance (Love Plot)', fontsize=14, fontweight='bold')
        ax.legend()
        ax.grid(True, alpha=0.3, axis='x')

        plt.tight_layout()
        return fig


# Convenience function
def create_balance_table(
    data: pd.DataFrame,
    treatment_col: str,
    covariates: List[str],
    output_format: str = "latex",
    **kwargs
) -> str:
    """
    Convenience function to create balance table

    Args:
        data: DataFrame
        treatment_col: Treatment column name
        covariates: List of covariate names
        output_format: "latex", "dataframe", or "markdown"
        **kwargs: Additional arguments for formatting

    Returns:
        Formatted table (string or DataFrame)

    Example:
        >>> data = pd.DataFrame({
        ...     'treatment': [0,1,0,1,0,1],
        ...     'age': [25,30,28,32,26,29],
        ...     'income': [50,55,48,60,52,58]
        ... })
        >>> table = create_balance_table(data, 'treatment', ['age', 'income'])
    """
    balance = BalanceTable(data, treatment_col, covariates)

    if output_format == "latex":
        return balance.to_latex(**kwargs)
    elif output_format == "dataframe":
        return balance.to_dataframe()
    elif output_format == "markdown":
        df = balance.to_dataframe()
        return df.to_markdown(index=False)
    else:
        raise ValueError(f"Unknown format: {output_format}")


# Testing
if __name__ == "__main__":
    """Test balance table generation"""
    np.random.seed(42)

    # Simulate RCT data
    n = 500
    treatment = np.random.binomial(1, 0.5, n)

    # Simulate covariates with slight imbalance
    age = 30 + 5 * np.random.randn(n) + 1 * treatment  # Slight imbalance
    income = 50 + 10 * np.random.randn(n) + 0.5 * treatment
    education = 12 + 2 * np.random.randn(n)  # Perfectly balanced
    female = np.random.binomial(1, 0.5, n)

    data = pd.DataFrame({
        'treatment': treatment,
        'age': age,
        'income': income,
        'education': education,
        'female': female
    })

    covariates = ['age', 'income', 'education', 'female']

    # Create balance table
    print("=" * 80)
    print("BALANCE TABLE (DATAFRAME)")
    print("=" * 80)

    balance = BalanceTable(data, 'treatment', covariates)
    results = balance.compute_balance()

    df_balance = balance.to_dataframe(results)
    print(df_balance.to_string(index=False))

    print("\n" + "=" * 80)
    print("BALANCE TABLE (LATEX)")
    print("=" * 80)

    latex_table = balance.to_latex(
        results,
        caption="Baseline Covariate Balance",
        label="tab:balance_baseline",
        smd_threshold=0.1
    )
    print(latex_table)

    # Check for imbalance
    print("\n" + "=" * 80)
    print("IMBALANCE SUMMARY")
    print("=" * 80)

    imbalanced = [r for r in results if abs(r.smd) > 0.1]
    if imbalanced:
        print(f"Found {len(imbalanced)} imbalanced covariates (|SMD| > 0.1):")
        for r in imbalanced:
            print(f"  - {r.variable}: SMD = {r.smd:.3f}")
    else:
        print("No significant imbalance detected (all |SMD| <= 0.1)")
