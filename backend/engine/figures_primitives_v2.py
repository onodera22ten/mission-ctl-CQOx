# backend/engine/figures_primitives_v2.py
"""
Domain-Agnostic Visualization Primitives (Matplotlib version - no hanging)
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
from pathlib import Path
from typing import Dict, Optional

class GenericPrimitives:
    """Domain-agnostic visualization primitives using matplotlib"""

    def __init__(self, df: pd.DataFrame, mapping: Dict[str, str]):
        self.df = df
        self.mapping = mapping
        self.y = mapping.get("y")
        self.t = mapping.get("treatment")
        self.unit_id = mapping.get("unit_id")
        self.time = mapping.get("time")
        mapped_cols = set(mapping.values())
        self.covariates = [c for c in df.columns if c not in mapped_cols and c]

    def generate_all(self, output_dir: Path) -> Dict[str, str]:
        """Generate all domain-agnostic primitives"""
        output_dir.mkdir(parents=True, exist_ok=True)
        figures = {}

        print(f"[primitive] Starting generation in {output_dir}")
        print(f"[primitive] y={self.y}, t={self.t}, time={self.time}")
        print(f"[primitive] covariates: {self.covariates}")

        try:
            if self.time and self.time in self.df.columns:
                print(f"[primitive] Attempting timeseries...")
                path = self._time_series_panel(output_dir)
                if path:
                    figures["primitive_timeseries"] = str(path)
                    print(f"[primitive] ✅ timeseries: {path}")
        except Exception as e:
            print(f"[primitive] ❌ timeseries failed: {e}")
            import traceback
            traceback.print_exc()

        try:
            print(f"[primitive] Attempting distribution...")
            path = self._distribution_compare(output_dir)
            if path:
                figures["primitive_distribution"] = str(path)
                print(f"[primitive] ✅ distribution: {path}")
        except Exception as e:
            print(f"[primitive] ❌ distribution failed: {e}")
            import traceback
            traceback.print_exc()

        try:
            if len(self.covariates) > 0:
                print(f"[primitive] Attempting scatter...")
                path = self._scatter_regression(output_dir)
                if path:
                    figures["primitive_scatter"] = str(path)
                    print(f"[primitive] ✅ scatter: {path}")
        except Exception as e:
            print(f"[primitive] ❌ scatter failed: {e}")
            import traceback
            traceback.print_exc()

        try:
            print(f"[primitive] Attempting heterogeneity...")
            path = self._heterogeneity_forest(output_dir)
            if path:
                figures["primitive_heterogeneity"] = str(path)
                print(f"[primitive] ✅ heterogeneity: {path}")
        except Exception as e:
            print(f"[primitive] ❌ heterogeneity failed: {e}")
            import traceback
            traceback.print_exc()

        try:
            print(f"[primitive] Attempting propensity...")
            path = self._propensity_overlap(output_dir)
            if path:
                figures["primitive_propensity"] = str(path)
                print(f"[primitive] ✅ propensity: {path}")
        except Exception as e:
            print(f"[primitive] ❌ propensity failed: {e}")
            import traceback
            traceback.print_exc()

        try:
            if len(self.covariates) > 0:
                print(f"[primitive] Attempting balance...")
                path = self._covariate_balance(output_dir)
                if path:
                    figures["primitive_balance"] = str(path)
                    print(f"[primitive] ✅ balance: {path}")
        except Exception as e:
            print(f"[primitive] ❌ balance failed: {e}")
            import traceback
            traceback.print_exc()

        print(f"[primitive] Completed. Generated {len(figures)} figures: {list(figures.keys())}")
        return figures

    def _time_series_panel(self, output_dir: Path) -> Optional[Path]:
        """Time series comparison"""
        if not self.time or not self.y or not self.t:
            return None

        agg = self.df.groupby([self.time, self.t])[self.y].agg(['mean', 'std', 'count']).reset_index()
        agg['se'] = agg['std'] / np.sqrt(agg['count'])

        fig, ax = plt.subplots(figsize=(10, 6))

        for treatment_val in [0, 1]:
            subset = agg[agg[self.t] == treatment_val]
            color = 'blue' if treatment_val == 1 else 'red'
            label = "Treated" if treatment_val == 1 else "Control"

            ax.plot(subset[self.time], subset['mean'], 'o-', color=color, label=label, linewidth=2, markersize=8)
            ax.fill_between(subset[self.time],
                           subset['mean'] - 1.96*subset['se'],
                           subset['mean'] + 1.96*subset['se'],
                           alpha=0.2, color=color)

        ax.set_xlabel(self.time.replace('_', ' ').title(), fontsize=12, fontweight='bold')
        ax.set_ylabel(self.y.replace('_', ' ').title(), fontsize=12, fontweight='bold')
        ax.set_title('Time Series: Outcome Trends by Treatment Group', fontsize=14, fontweight='bold')
        ax.legend()
        ax.grid(True, alpha=0.3)

        path = output_dir / "primitive_timeseries.png"
        plt.tight_layout()
        plt.savefig(str(path), dpi=150, bbox_inches='tight')
        plt.close()
        return path

    def _distribution_compare(self, output_dir: Path) -> Optional[Path]:
        """Distribution comparison"""
        if not self.y or not self.t:
            return None

        treated = self.df[self.df[self.t] == 1][self.y].dropna()
        control = self.df[self.df[self.t] == 0][self.y].dropna()

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.hist(control, bins=30, alpha=0.6, color='red', label='Control', edgecolor='black')
        ax.hist(treated, bins=30, alpha=0.6, color='blue', label='Treated', edgecolor='black')

        ax.set_xlabel(self.y.replace('_', ' ').title(), fontsize=12, fontweight='bold')
        ax.set_ylabel('Frequency', fontsize=12, fontweight='bold')
        ax.set_title('Outcome Distribution by Treatment Group', fontsize=14, fontweight='bold')
        ax.legend()
        ax.grid(True, alpha=0.3, axis='y')

        path = output_dir / "primitive_distribution.png"
        plt.tight_layout()
        plt.savefig(str(path), dpi=150, bbox_inches='tight')
        plt.close()
        return path

    def _scatter_regression(self, output_dir: Path) -> Optional[Path]:
        """Scatter plot with regression"""
        if not self.y or not self.t or len(self.covariates) == 0:
            return None

        numeric_covs = [c for c in self.covariates if pd.api.types.is_numeric_dtype(self.df[c])]
        if len(numeric_covs) == 0:
            return None

        cov = numeric_covs[0]

        fig, ax = plt.subplots(figsize=(10, 6))

        for treatment_val in [0, 1]:
            subset = self.df[self.df[self.t] == treatment_val]
            color = 'blue' if treatment_val == 1 else 'red'
            label = "Treated" if treatment_val == 1 else "Control"
            ax.scatter(subset[cov], subset[self.y], alpha=0.5, color=color, label=label, s=50)

            # Simple linear regression
            valid = subset[[cov, self.y]].dropna()
            if len(valid) > 2:
                z = np.polyfit(valid[cov], valid[self.y], 1)
                p = np.poly1d(z)
                x_line = np.linspace(valid[cov].min(), valid[cov].max(), 100)
                ax.plot(x_line, p(x_line), color=color, linewidth=2, linestyle='--')

        ax.set_xlabel(cov.replace('_', ' ').title(), fontsize=12, fontweight='bold')
        ax.set_ylabel(self.y.replace('_', ' ').title(), fontsize=12, fontweight='bold')
        ax.set_title(f'Scatter: {cov.replace("_", " ").title()} vs {self.y.replace("_", " ").title()}',
                    fontsize=14, fontweight='bold')
        ax.legend()
        ax.grid(True, alpha=0.3)

        path = output_dir / "primitive_scatter.png"
        plt.tight_layout()
        plt.savefig(str(path), dpi=150, bbox_inches='tight')
        plt.close()
        return path

    def _heterogeneity_forest(self, output_dir: Path) -> Optional[Path]:
        """Heterogeneity forest"""
        if not self.y or not self.t:
            return None

        numeric_covs = [c for c in self.covariates if pd.api.types.is_numeric_dtype(self.df[c])]
        if len(numeric_covs) == 0:
            return None

        cov = numeric_covs[0]
        try:
            self.df['_subgroup'] = pd.qcut(self.df[cov], q=4, labels=['Q1', 'Q2', 'Q3', 'Q4'], duplicates='drop')
        except:
            return None

        subgroup_effects = []
        for subgroup in ['Q1', 'Q2', 'Q3', 'Q4']:
            subset = self.df[self.df['_subgroup'] == subgroup]
            if len(subset) < 10:
                continue

            treated = subset[subset[self.t] == 1][self.y].dropna()
            control = subset[subset[self.t] == 0][self.y].dropna()

            if len(treated) > 0 and len(control) > 0:
                ate = treated.mean() - control.mean()
                se = np.sqrt(treated.var()/len(treated) + control.var()/len(control))
                subgroup_effects.append({
                    'subgroup': f"{cov} {subgroup}",
                    'ate': ate,
                    'ci_lower': ate - 1.96*se,
                    'ci_upper': ate + 1.96*se
                })

        self.df.drop(columns=['_subgroup'], inplace=True)

        if len(subgroup_effects) == 0:
            return None

        fig, ax = plt.subplots(figsize=(10, 6))

        for i, effect in enumerate(subgroup_effects):
            ax.plot([effect['ci_lower'], effect['ci_upper']], [i, i], 'b-', linewidth=2)
            ax.plot(effect['ate'], i, 'bo', markersize=10)

        ax.axvline(x=0, color='gray', linestyle='--', linewidth=1)
        ax.set_yticks(range(len(subgroup_effects)))
        ax.set_yticklabels([e['subgroup'] for e in subgroup_effects])
        ax.set_xlabel('Average Treatment Effect (ATE)', fontsize=12, fontweight='bold')
        ax.set_ylabel('Subgroup', fontsize=12, fontweight='bold')
        ax.set_title('Treatment Effect Heterogeneity by Subgroup', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='x')

        path = output_dir / "primitive_heterogeneity.png"
        plt.tight_layout()
        plt.savefig(str(path), dpi=150, bbox_inches='tight')
        plt.close()
        return path

    def _propensity_overlap(self, output_dir: Path) -> Optional[Path]:
        """Propensity score overlap"""
        if not self.t or len(self.covariates) == 0:
            return None

        try:
            from sklearn.linear_model import LogisticRegression

            numeric_covs = [c for c in self.covariates if pd.api.types.is_numeric_dtype(self.df[c])]
            if len(numeric_covs) == 0:
                return None

            X = self.df[numeric_covs].fillna(self.df[numeric_covs].mean())
            y = self.df[self.t]

            model = LogisticRegression(max_iter=1000, solver='lbfgs')
            model.fit(X, y)
            propensity = model.predict_proba(X)[:, 1]

            treated_ps = propensity[self.df[self.t] == 1]
            control_ps = propensity[self.df[self.t] == 0]

            fig, ax = plt.subplots(figsize=(10, 6))
            ax.hist(control_ps, bins=30, alpha=0.6, color='red', label='Control', edgecolor='black')
            ax.hist(treated_ps, bins=30, alpha=0.6, color='blue', label='Treated', edgecolor='black')

            ax.set_xlabel('Propensity Score', fontsize=12, fontweight='bold')
            ax.set_ylabel('Frequency', fontsize=12, fontweight='bold')
            ax.set_title('Propensity Score Overlap', fontsize=14, fontweight='bold')
            ax.legend()
            ax.grid(True, alpha=0.3, axis='y')

            path = output_dir / "primitive_propensity.png"
            plt.tight_layout()
            plt.savefig(str(path), dpi=150, bbox_inches='tight')
            plt.close()
            return path

        except Exception as e:
            print(f"[primitive] propensity failed: {e}")
            return None

    def _covariate_balance(self, output_dir: Path) -> Optional[Path]:
        """Love plot: SMD"""
        if not self.t or len(self.covariates) == 0:
            return None

        numeric_covs = [c for c in self.covariates if pd.api.types.is_numeric_dtype(self.df[c])]
        if len(numeric_covs) == 0:
            return None

        smd_values = []
        for cov in numeric_covs[:10]:
            treated = self.df[self.df[self.t] == 1][cov].dropna()
            control = self.df[self.df[self.t] == 0][cov].dropna()

            if len(treated) > 0 and len(control) > 0:
                mean_diff = treated.mean() - control.mean()
                pooled_std = np.sqrt((treated.var() + control.var()) / 2)
                smd = abs(mean_diff / pooled_std) if pooled_std > 0 else 0
                smd_values.append({'covariate': cov, 'smd': smd})

        if len(smd_values) == 0:
            return None

        smd_df = pd.DataFrame(smd_values).sort_values('smd', ascending=True)

        fig, ax = plt.subplots(figsize=(10, 6))
        colors = ['green' if s < 0.1 else 'orange' if s < 0.25 else 'red' for s in smd_df['smd']]
        ax.scatter(smd_df['smd'], range(len(smd_df)), c=colors, s=100, alpha=0.7)

        ax.axvline(x=0.1, color='orange', linestyle='--', linewidth=1, label='Threshold (0.1)')
        ax.set_yticks(range(len(smd_df)))
        ax.set_yticklabels(smd_df['covariate'])
        ax.set_xlabel('Standardized Mean Difference (SMD)', fontsize=12, fontweight='bold')
        ax.set_ylabel('Covariate', fontsize=12, fontweight='bold')
        ax.set_title('Covariate Balance (Love Plot)', fontsize=14, fontweight='bold')
        ax.legend()
        ax.grid(True, alpha=0.3, axis='x')

        path = output_dir / "primitive_balance.png"
        plt.tight_layout()
        plt.savefig(str(path), dpi=150, bbox_inches='tight')
        plt.close()
        return path


def generate_generic_primitives(df: pd.DataFrame, mapping: Dict[str, str], output_dir: Path) -> Dict[str, str]:
    """Generate all domain-agnostic primitives (matplotlib version)"""
    generator = GenericPrimitives(df, mapping)
    return generator.generate_all(output_dir)
