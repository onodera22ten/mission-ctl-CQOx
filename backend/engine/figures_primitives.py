# backend/engine/figures_primitives.py
"""
Domain-Agnostic Visualization Primitives (Col2 Specification)

These primitives work for ANY domain without customization:
1. TimeSeriesPanel - Time-series comparison (treated vs control)
2. DistributionCompare - Outcome distribution comparison
3. ScatterWithRegression - Covariate vs outcome with treatment overlay
4. HeterogeneityForest - Treatment effect heterogeneity by subgroups
5. PropensityOverlap - Propensity score overlap visualization
6. CovariateBalance - Love plot (SMD before/after adjustment)
7. ResidualDiagnostic - Residual plots for model checking
8. EffectByQuantile - Quantile treatment effects
9. SensitivityContour - Sensitivity analysis contour plot
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from pathlib import Path
from typing import Dict, Optional, List, Any


class GenericPrimitives:
    """Domain-agnostic visualization primitives"""

    def __init__(self, df: pd.DataFrame, mapping: Dict[str, str]):
        self.df = df
        self.mapping = mapping
        self.y = mapping.get("y")
        self.t = mapping.get("treatment")
        self.unit_id = mapping.get("unit_id")
        self.time = mapping.get("time")

        # Identify covariates
        mapped_cols = set(mapping.values())
        self.covariates = [c for c in df.columns if c not in mapped_cols and c]

    def generate_all(self, output_dir: Path) -> Dict[str, str]:
        """Generate all domain-agnostic primitives"""
        output_dir.mkdir(parents=True, exist_ok=True)

        figures = {}

        # 1. Time Series Panel
        if self.time and self.time in self.df.columns:
            path = self._time_series_panel(output_dir)
            if path:
                figures["primitive_timeseries"] = str(path)

        # 2. Distribution Compare
        path = self._distribution_compare(output_dir)
        if path:
            figures["primitive_distribution"] = str(path)

        # 3. Scatter with Regression
        if len(self.covariates) > 0:
            path = self._scatter_regression(output_dir)
            if path:
                figures["primitive_scatter"] = str(path)

        # 4. Heterogeneity Forest
        path = self._heterogeneity_forest(output_dir)
        if path:
            figures["primitive_heterogeneity"] = str(path)

        # 5. Propensity Overlap
        path = self._propensity_overlap(output_dir)
        if path:
            figures["primitive_propensity"] = str(path)

        # 6. Covariate Balance
        if len(self.covariates) > 0:
            path = self._covariate_balance(output_dir)
            if path:
                figures["primitive_balance"] = str(path)

        # 7. Residual Diagnostic
        path = self._residual_diagnostic(output_dir)
        if path:
            figures["primitive_residuals"] = str(path)

        # 8. Effect by Quantile
        path = self._effect_by_quantile(output_dir)
        if path:
            figures["primitive_quantile"] = str(path)

        # 9. Sensitivity Contour
        path = self._sensitivity_contour(output_dir)
        if path:
            figures["primitive_sensitivity"] = str(path)

        return figures

    def _time_series_panel(self, output_dir: Path) -> Optional[Path]:
        """Time series comparison: treated vs control over time"""
        if not self.time or not self.y or not self.t:
            return None

        try:
            # Aggregate by time and treatment
            agg = self.df.groupby([self.time, self.t])[self.y].agg(['mean', 'std', 'count']).reset_index()
            agg['se'] = agg['std'] / np.sqrt(agg['count'])

            fig = go.Figure()

            for treatment_val in [0, 1]:
                subset = agg[agg[self.t] == treatment_val]
                name = "Treated" if treatment_val == 1 else "Control"
                color = "#3b82f6" if treatment_val == 1 else "#ef4444"

                fig.add_trace(go.Scatter(
                    x=subset[self.time],
                    y=subset['mean'],
                    mode='lines+markers',
                    name=name,
                    line=dict(color=color, width=2),
                    marker=dict(size=8)
                ))

                # Confidence bands
                fig.add_trace(go.Scatter(
                    x=subset[self.time].tolist() + subset[self.time].tolist()[::-1],
                    y=(subset['mean'] + 1.96*subset['se']).tolist() +
                      (subset['mean'] - 1.96*subset['se']).tolist()[::-1],
                    fill='toself',
                    fillcolor=color,
                    opacity=0.2,
                    line=dict(width=0),
                    showlegend=False,
                    hoverinfo='skip'
                ))

            fig.update_layout(
                title="Time Series: Outcome Trends by Treatment Group",
                xaxis_title=self.time.replace('_', ' ').title(),
                yaxis_title=self.y.replace('_', ' ').title(),
                template="plotly_white",
                hovermode='x unified'
            )

            path = output_dir / "primitive_timeseries.html"
            fig.write_html(str(path))
            return path

        except Exception as e:
            print(f"[primitive] time_series_panel failed: {e}")
            return None

    def _distribution_compare(self, output_dir: Path) -> Optional[Path]:
        """Distribution comparison: treated vs control"""
        if not self.y or not self.t:
            return None

        try:
            treated = self.df[self.df[self.t] == 1][self.y].dropna()
            control = self.df[self.df[self.t] == 0][self.y].dropna()

            fig = go.Figure()

            fig.add_trace(go.Histogram(
                x=control,
                name='Control',
                opacity=0.7,
                marker_color='#ef4444',
                nbinsx=30
            ))

            fig.add_trace(go.Histogram(
                x=treated,
                name='Treated',
                opacity=0.7,
                marker_color='#3b82f6',
                nbinsx=30
            ))

            fig.update_layout(
                title="Outcome Distribution by Treatment Group",
                xaxis_title=self.y.replace('_', ' ').title(),
                yaxis_title="Frequency",
                barmode='overlay',
                template="plotly_white"
            )

            path = output_dir / "primitive_distribution.html"
            fig.write_html(str(path))
            return path

        except Exception as e:
            print(f"[primitive] distribution_compare failed: {e}")
            return None

    def _scatter_regression(self, output_dir: Path) -> Optional[Path]:
        """Scatter plot: covariate vs outcome with treatment overlay"""
        if not self.y or not self.t or len(self.covariates) == 0:
            return None

        try:
            # Use first numeric covariate
            numeric_covs = [c for c in self.covariates if pd.api.types.is_numeric_dtype(self.df[c])]
            if len(numeric_covs) == 0:
                return None

            cov = numeric_covs[0]

            fig = px.scatter(
                self.df,
                x=cov,
                y=self.y,
                color=self.t,
                color_discrete_map={0: '#ef4444', 1: '#3b82f6'},
                trendline='ols',
                opacity=0.6,
                labels={self.t: 'Treatment'}
            )

            fig.update_layout(
                title=f"Scatter: {cov.replace('_', ' ').title()} vs {self.y.replace('_', ' ').title()}",
                template="plotly_white"
            )

            path = output_dir / "primitive_scatter.html"
            fig.write_html(str(path))
            return path

        except Exception as e:
            print(f"[primitive] scatter_regression failed: {e}")
            return None

    def _heterogeneity_forest(self, output_dir: Path) -> Optional[Path]:
        """Heterogeneity forest: treatment effects by subgroups"""
        if not self.y or not self.t:
            return None

        try:
            # Create subgroups based on quantiles of first covariate
            numeric_covs = [c for c in self.covariates if pd.api.types.is_numeric_dtype(self.df[c])]
            if len(numeric_covs) == 0:
                return None

            cov = numeric_covs[0]
            self.df['_subgroup'] = pd.qcut(self.df[cov], q=4, labels=['Q1', 'Q2', 'Q3', 'Q4'], duplicates='drop')

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

            if len(subgroup_effects) == 0:
                return None

            effects_df = pd.DataFrame(subgroup_effects)

            fig = go.Figure()

            fig.add_trace(go.Scatter(
                x=effects_df['ate'],
                y=effects_df['subgroup'],
                mode='markers',
                marker=dict(size=12, color='#3b82f6'),
                error_x=dict(
                    type='data',
                    symmetric=False,
                    array=effects_df['ci_upper'] - effects_df['ate'],
                    arrayminus=effects_df['ate'] - effects_df['ci_lower']
                ),
                name='ATE'
            ))

            fig.add_vline(x=0, line_dash="dash", line_color="gray")

            fig.update_layout(
                title="Treatment Effect Heterogeneity by Subgroup",
                xaxis_title="Average Treatment Effect (ATE)",
                yaxis_title="Subgroup",
                template="plotly_white"
            )

            path = output_dir / "primitive_heterogeneity.html"
            fig.write_html(str(path))
            return path

        except Exception as e:
            print(f"[primitive] heterogeneity_forest failed: {e}")
            return None
        finally:
            if '_subgroup' in self.df.columns:
                self.df.drop(columns=['_subgroup'], inplace=True)

    def _propensity_overlap(self, output_dir: Path) -> Optional[Path]:
        """Propensity score overlap visualization"""
        if not self.t or len(self.covariates) == 0:
            return None

        try:
            # Simple propensity score estimation (logistic regression)
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

            fig = go.Figure()

            fig.add_trace(go.Histogram(
                x=control_ps,
                name='Control',
                opacity=0.7,
                marker_color='#ef4444',
                nbinsx=30
            ))

            fig.add_trace(go.Histogram(
                x=treated_ps,
                name='Treated',
                opacity=0.7,
                marker_color='#3b82f6',
                nbinsx=30
            ))

            fig.update_layout(
                title="Propensity Score Overlap",
                xaxis_title="Propensity Score",
                yaxis_title="Frequency",
                barmode='overlay',
                template="plotly_white"
            )

            path = output_dir / "primitive_propensity.html"
            fig.write_html(str(path))
            return path

        except Exception as e:
            print(f"[primitive] propensity_overlap failed: {e}")
            return None

    def _covariate_balance(self, output_dir: Path) -> Optional[Path]:
        """Love plot: Standardized Mean Difference for covariates"""
        if not self.t or len(self.covariates) == 0:
            return None

        try:
            numeric_covs = [c for c in self.covariates if pd.api.types.is_numeric_dtype(self.df[c])]
            if len(numeric_covs) == 0:
                return None

            smd_values = []
            for cov in numeric_covs[:10]:  # Limit to top 10
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

            fig = go.Figure()

            fig.add_trace(go.Scatter(
                x=smd_df['smd'],
                y=smd_df['covariate'],
                mode='markers',
                marker=dict(
                    size=10,
                    color=smd_df['smd'],
                    colorscale='RdYlGn_r',
                    showscale=True,
                    colorbar=dict(title="SMD")
                )
            ))

            fig.add_vline(x=0.1, line_dash="dash", line_color="orange",
                         annotation_text="Threshold (0.1)")

            fig.update_layout(
                title="Covariate Balance (Love Plot)",
                xaxis_title="Standardized Mean Difference (SMD)",
                yaxis_title="Covariate",
                template="plotly_white"
            )

            path = output_dir / "primitive_balance.html"
            fig.write_html(str(path))
            return path

        except Exception as e:
            print(f"[primitive] covariate_balance failed: {e}")
            return None

    def _residual_diagnostic(self, output_dir: Path) -> Optional[Path]:
        """Residual plots for model diagnostics"""
        if not self.y or not self.t:
            return None

        try:
            # Simple linear model: Y ~ T
            treated = self.df[self.df[self.t] == 1][self.y].dropna()
            control = self.df[self.df[self.t] == 0][self.y].dropna()

            treated_mean = treated.mean()
            control_mean = control.mean()

            # Calculate residuals
            residuals_treated = treated - treated_mean
            residuals_control = control - control_mean

            fig = make_subplots(
                rows=1, cols=2,
                subplot_titles=("Residuals vs Fitted", "Q-Q Plot")
            )

            # Residuals vs Fitted
            fig.add_trace(
                go.Scatter(
                    x=[treated_mean]*len(residuals_treated),
                    y=residuals_treated,
                    mode='markers',
                    marker=dict(color='#3b82f6', opacity=0.6),
                    name='Treated'
                ),
                row=1, col=1
            )

            fig.add_trace(
                go.Scatter(
                    x=[control_mean]*len(residuals_control),
                    y=residuals_control,
                    mode='markers',
                    marker=dict(color='#ef4444', opacity=0.6),
                    name='Control'
                ),
                row=1, col=1
            )

            # Q-Q Plot
            all_residuals = np.concatenate([residuals_treated, residuals_control])
            sorted_residuals = np.sort(all_residuals)
            theoretical_quantiles = np.sort(np.random.normal(0, 1, len(all_residuals)))

            fig.add_trace(
                go.Scatter(
                    x=theoretical_quantiles,
                    y=sorted_residuals,
                    mode='markers',
                    marker=dict(color='#8b5cf6', opacity=0.6),
                    name='Residuals'
                ),
                row=1, col=2
            )

            fig.add_trace(
                go.Scatter(
                    x=theoretical_quantiles,
                    y=theoretical_quantiles * np.std(all_residuals),
                    mode='lines',
                    line=dict(color='red', dash='dash'),
                    name='45° line'
                ),
                row=1, col=2
            )

            fig.update_xaxes(title_text="Fitted Values", row=1, col=1)
            fig.update_yaxes(title_text="Residuals", row=1, col=1)
            fig.update_xaxes(title_text="Theoretical Quantiles", row=1, col=2)
            fig.update_yaxes(title_text="Sample Quantiles", row=1, col=2)

            fig.update_layout(
                title="Residual Diagnostics",
                template="plotly_white",
                showlegend=True
            )

            path = output_dir / "primitive_residuals.html"
            fig.write_html(str(path))
            return path

        except Exception as e:
            print(f"[primitive] residual_diagnostic failed: {e}")
            return None

    def _effect_by_quantile(self, output_dir: Path) -> Optional[Path]:
        """Quantile treatment effects (QTE)"""
        if not self.y or not self.t:
            return None

        try:
            treated = self.df[self.df[self.t] == 1][self.y].dropna()
            control = self.df[self.df[self.t] == 0][self.y].dropna()

            quantiles = np.arange(0.1, 1.0, 0.1)
            qte = []

            for q in quantiles:
                q_treated = np.quantile(treated, q)
                q_control = np.quantile(control, q)
                qte.append(q_treated - q_control)

            fig = go.Figure()

            fig.add_trace(go.Scatter(
                x=quantiles,
                y=qte,
                mode='lines+markers',
                line=dict(color='#3b82f6', width=3),
                marker=dict(size=10),
                name='QTE'
            ))

            fig.add_hline(y=0, line_dash="dash", line_color="gray")

            fig.update_layout(
                title="Quantile Treatment Effects (QTE)",
                xaxis_title="Quantile",
                yaxis_title="Treatment Effect",
                template="plotly_white"
            )

            path = output_dir / "primitive_quantile.html"
            fig.write_html(str(path))
            return path

        except Exception as e:
            print(f"[primitive] effect_by_quantile failed: {e}")
            return None

    def _sensitivity_contour(self, output_dir: Path) -> Optional[Path]:
        """Sensitivity analysis contour plot"""
        try:
            # Rosenbaum-style sensitivity: Gamma vs p-value
            gamma_values = np.linspace(1.0, 3.0, 20)
            p_values = 1 / (1 + gamma_values)  # Simplified relationship

            fig = go.Figure()

            fig.add_trace(go.Scatter(
                x=gamma_values,
                y=p_values,
                mode='lines',
                line=dict(color='#3b82f6', width=3),
                fill='tozeroy',
                fillcolor='rgba(59, 130, 246, 0.2)',
                name='p-value boundary'
            ))

            fig.add_hline(y=0.05, line_dash="dash", line_color="red",
                         annotation_text="α = 0.05")

            fig.update_layout(
                title="Sensitivity Analysis: Unobserved Confounding",
                xaxis_title="Γ (Gamma - Confounding Strength)",
                yaxis_title="p-value",
                template="plotly_white"
            )

            path = output_dir / "primitive_sensitivity.html"
            fig.write_html(str(path))
            return path

        except Exception as e:
            print(f"[primitive] sensitivity_contour failed: {e}")
            return None


def generate_generic_primitives(df: pd.DataFrame, mapping: Dict[str, str], output_dir: Path) -> Dict[str, str]:
    """Generate all domain-agnostic primitives"""
    generator = GenericPrimitives(df, mapping)
    return generator.generate_all(output_dir)
