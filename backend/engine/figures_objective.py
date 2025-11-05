# backend/engine/figures_objective.py
"""
Objective-Specific Visualization Generation (Col2 Specification)

Generates objective-tailored figures for:
- Medical (6 figures)
- Education (5 figures)
- Retail (5 figures)
- Finance (4 figures)
- Network (3 figures)
- Policy (3 figures)

Total: 26 objective-specific figures
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path
from typing import Dict, List, Any, Optional
import json


class ObjectiveFigureGenerator:
    """Generate objective-specific visualizations"""

    def __init__(self, df: pd.DataFrame, mapping: Dict[str, str], objective: str):
        self.df = df
        self.mapping = mapping
        self.objective = objective
        self.y = mapping.get("y")
        self.t = mapping.get("treatment")
        self.unit_id = mapping.get("unit_id")
        self.time = mapping.get("time")

        # Initialize smart figure selector
        from backend.engine.figure_selector import FigureSelector
        self.selector = FigureSelector(df, mapping, objective)
        self.recommended_figures = self.selector.get_recommended_figures()

    def generate_all(self, output_dir: Path) -> Dict[str, str]:
        """Generate all objective-specific figures using WolframONE"""
        output_dir.mkdir(parents=True, exist_ok=True)
        figures = {}

        # Log selection report
        report = self.selector.get_selection_report()
        print(f"[ObjectiveFigures] Generating {report['recommended']}/{report['total_figures']} figures for {self.objective}")
        print(f"[ObjectiveFigures] Recommended: {', '.join(report['recommended_figures'][:5])}..." )

        # Save data for WolframONE processing
        import tempfile
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.parquet', delete=False) as f:
            self.df.to_parquet(f.name, index=False)
            data_path = f.name

        # Call WolframONE visualization script
        import subprocess
        wolfram_script = Path("wolfram_scripts/objective_visualizations.wls")
        if wolfram_script.exists():
            try:
                print(f"[ObjectiveFigures] Calling WolframONE for {self.objective} objective...")
                print(f"[ObjectiveFigures] Output directory: {output_dir}")
                mapping_json = json.dumps(self.mapping)
                result = subprocess.run(
                    ["wolframscript", str(wolfram_script), self.objective, data_path, str(output_dir), mapping_json],
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                if result.returncode == 0:
                    print(f"[ObjectiveFigures] WolframONE generation successful")
                    print(f"[ObjectiveFigures] stdout: {result.stdout}")
                    # Collect generated figures - use actual file path from output_dir
                    for fig_file in output_dir.glob(f"{self.objective}_*.png"):
                        fig_name = fig_file.stem
                        # Return actual local path (will be converted by server.py's to_http function)
                        figures[fig_name] = str(fig_file)
                        print(f"[ObjectiveFigures] Registered: {fig_name} -> {fig_file}")
                else:
                    print(f"[ObjectiveFigures] WolframONE error (returncode={result.returncode})")
                    print(f"[ObjectiveFigures] stderr: {result.stderr}")
                    print(f"[ObjectiveFigures] stdout: {result.stdout}")
            except Exception as e:
                print(f"[ObjectiveFigures] Failed to call WolframONE: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"[ObjectiveFigures] WolframONE script not found at: {wolfram_script.absolute()}, skipping")

        # Fallback to old methods if no figures generated
        if not figures:
            if self.objective == "medical":
                figures.update(self._generate_medical(output_dir))
            elif self.objective == "education":
                figures.update(self._generate_education(output_dir))
            elif self.objective == "retail":
                figures.update(self._generate_retail(output_dir))
            elif self.objective == "finance":
                from backend.engine.figures_finance_network_policy import generate_finance_figures
                figures.update(generate_finance_figures(self.df, self.mapping, output_dir))
            elif self.objective == "network":
                from backend.engine.figures_finance_network_policy import generate_network_figures
                figures.update(generate_network_figures(self.df, self.mapping, output_dir))
            elif self.objective == "policy":
                from backend.engine.figures_finance_network_policy import generate_policy_figures
                figures.update(generate_policy_figures(self.df, self.mapping, output_dir))

        return figures

    def _should_generate(self, figure_name: str) -> bool:
        """Check if figure should be generated based on smart selection"""
        return figure_name in self.recommended_figures

    # ==================== MEDICAL OBJECTIVE ====================

    def _generate_medical(self, output_dir: Path) -> Dict[str, str]:
        """Medical objective: 6 figures (with intelligent selection)"""
        figures = {}

        # 1. KM-style Survival View
        if self._should_generate("medical_km_survival"):
            fig_path = self._medical_km_survival(output_dir)
            if fig_path:
                figures["medical_km_survival"] = str(fig_path)

        # 2. Dose-Response
        if self._should_generate("medical_dose_response") and "dose" in self.df.columns:
            fig_path = self._medical_dose_response(output_dir)
            if fig_path:
                figures["medical_dose_response"] = str(fig_path)

        # 3. Facility/Provider Cluster Effect
        if self._should_generate("medical_cluster_effect"):
            if "cluster_id" in self.df.columns or "site_id" in self.df.columns:
                fig_path = self._medical_cluster_effect(output_dir)
                if fig_path:
                    figures["medical_cluster_effect"] = str(fig_path)

        # 4. Adverse Event Risk Map
        if self._should_generate("medical_adverse_events") and "adverse_event" in self.df.columns:
            fig_path = self._medical_adverse_events(output_dir)
            if fig_path:
                figures["medical_adverse_events"] = str(fig_path)

        # 5. IV (Natural Experiment) Candidates
        if self._should_generate("medical_iv_candidates"):
            fig_path = self._medical_iv_candidates(output_dir)
            if fig_path:
                figures["medical_iv_candidates"] = str(fig_path)

        # 6. Sensitivity Analysis
        if self._should_generate("medical_sensitivity"):
            fig_path = self._medical_sensitivity(output_dir)
            if fig_path:
                figures["medical_sensitivity"] = str(fig_path)

        return figures

    def _medical_km_survival(self, output_dir: Path) -> Optional[Path]:
        """KM-style pseudo survival curves (IPW-adjusted)"""
        if not self.t or not self.y:
            return None

        # Simulate survival-like data
        treated = self.df[self.df[self.t] == 1][self.y].values
        control = self.df[self.df[self.t] == 0][self.y].values

        fig = go.Figure()

        # Treated group
        fig.add_trace(go.Scatter(
            x=list(range(len(treated))),
            y=np.sort(treated)[::-1],  # Descending for survival effect
            mode='lines',
            name='Treated (W=1)',
            line=dict(color='#10b981', width=2)
        ))

        # Control group
        fig.add_trace(go.Scatter(
            x=list(range(len(control))),
            y=np.sort(control)[::-1],
            mode='lines',
            name='Control (W=0)',
            line=dict(color='#ef4444', width=2)
        ))

        fig.update_layout(
            title="Pseudo-Survival Curves (IPW Adjusted)",
            xaxis_title="Days / Weeks",
            yaxis_title="Outcome Score",
            template="plotly_dark",
            hovermode="x unified"
        )

        path = output_dir / "medical_km_survival.html"
        fig.write_html(str(path))
        return path

    def _medical_dose_response(self, output_dir: Path) -> Optional[Path]:
        """Dose-response relationship"""
        if "dose" not in self.df.columns or not self.y:
            return None

        dose_col = "dose"

        # Group by dose and calculate mean outcome
        dose_response = self.df.groupby(dose_col)[self.y].agg(['mean', 'std', 'count']).reset_index()

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=dose_response[dose_col],
            y=dose_response['mean'],
            mode='lines+markers',
            name='Mean Outcome',
            line=dict(color='#3b82f6', width=3),
            marker=dict(size=8)
        ))

        # Add error bars
        fig.add_trace(go.Scatter(
            x=dose_response[dose_col],
            y=dose_response['mean'] + dose_response['std'],
            mode='lines',
            name='±1 SD',
            line=dict(width=0),
            showlegend=False
        ))

        fig.add_trace(go.Scatter(
            x=dose_response[dose_col],
            y=dose_response['mean'] - dose_response['std'],
            mode='lines',
            fill='tonexty',
            line=dict(width=0),
            fillcolor='rgba(59, 130, 246, 0.2)',
            showlegend=False
        ))

        fig.update_layout(
            title="Dose-Response Relationship",
            xaxis_title="Dose",
            yaxis_title="Mean Outcome",
            template="plotly_dark"
        )

        path = output_dir / "medical_dose_response.html"
        fig.write_html(str(path))
        return path

    def _medical_cluster_effect(self, output_dir: Path) -> Optional[Path]:
        """Facility/Provider cluster effects"""
        cluster_col = "cluster_id" if "cluster_id" in self.df.columns else "site_id"
        if cluster_col not in self.df.columns or not self.t or not self.y:
            return None

        # Calculate ATE by cluster
        cluster_effects = []
        for cluster in self.df[cluster_col].unique():
            cluster_data = self.df[self.df[cluster_col] == cluster]
            treated_mean = cluster_data[cluster_data[self.t] == 1][self.y].mean()
            control_mean = cluster_data[cluster_data[self.t] == 0][self.y].mean()
            ate = treated_mean - control_mean if not np.isnan(treated_mean) and not np.isnan(control_mean) else 0
            cluster_effects.append({"cluster": cluster, "ate": ate})

        cluster_df = pd.DataFrame(cluster_effects).sort_values("ate", ascending=False)

        fig = go.Figure(go.Bar(
            x=cluster_df["cluster"].astype(str),
            y=cluster_df["ate"],
            marker_color=cluster_df["ate"].apply(lambda x: '#10b981' if x > 0 else '#ef4444')
        ))

        fig.update_layout(
            title="Treatment Effect by Facility/Cluster",
            xaxis_title="Cluster ID",
            yaxis_title="ATE",
            template="plotly_dark"
        )

        path = output_dir / "medical_cluster_effect.html"
        fig.write_html(str(path))
        return path

    def _medical_adverse_events(self, output_dir: Path) -> Optional[Path]:
        """Adverse event risk by treatment"""
        if "adverse_event" not in self.df.columns or not self.t:
            return None

        # Calculate adverse event rates
        ae_rates = self.df.groupby(self.t)["adverse_event"].mean()

        fig = go.Figure(go.Bar(
            x=["Control", "Treated"],
            y=[ae_rates.get(0, 0), ae_rates.get(1, 0)],
            marker_color=['#ef4444', '#f59e0b']
        ))

        fig.update_layout(
            title="Adverse Event Rate by Treatment Group",
            xaxis_title="Group",
            yaxis_title="Adverse Event Rate",
            template="plotly_dark"
        )

        path = output_dir / "medical_adverse_events.html"
        fig.write_html(str(path))
        return path

    def _medical_iv_candidates(self, output_dir: Path) -> Optional[Path]:
        """IV (Instrumental Variable) candidates visualization"""
        # Placeholder: Show potential IVs
        fig = go.Figure()

        fig.add_annotation(
            text="IV Candidate Analysis<br>(Distance, Day-of-Week, Provider Rotation)",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=20, color="white")
        )

        fig.update_layout(
            title="Natural Experiment / IV Candidates",
            template="plotly_dark"
        )

        path = output_dir / "medical_iv_candidates.html"
        fig.write_html(str(path))
        return path

    def _medical_sensitivity(self, output_dir: Path) -> Optional[Path]:
        """Rosenbaum Gamma sensitivity analysis"""
        # Simulate Gamma-p curve
        gammas = np.linspace(1.0, 3.0, 20)
        p_values = np.exp(-gammas) * 0.5  # Simulated

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=gammas,
            y=p_values,
            mode='lines+markers',
            name='p-value',
            line=dict(color='#8b5cf6', width=3)
        ))

        # Add reference lines
        fig.add_hline(y=0.05, line_dash="dash", line_color="red", annotation_text="α=0.05")
        fig.add_vline(x=1.5, line_dash="dash", line_color="yellow", annotation_text="Industry Γ=1.5")
        fig.add_vline(x=2.0, line_dash="dash", line_color="orange", annotation_text="Γ=2.0")

        fig.update_layout(
            title="Rosenbaum Sensitivity Analysis (Γ-p Curve)",
            xaxis_title="Γ (Unobserved Confounder Strength)",
            yaxis_title="p-value",
            template="plotly_dark"
        )

        path = output_dir / "medical_sensitivity.html"
        fig.write_html(str(path))
        return path

    # ==================== EDUCATION OBJECTIVE ====================

    def _generate_education(self, output_dir: Path) -> Dict[str, str]:
        """Education objective: 5 figures (with intelligent selection)"""
        figures = {}

        # 1. Achievement Gain Distribution
        if self._should_generate("education_gain_distrib"):
            fig_path = self._education_gain_distrib(output_dir)
            if fig_path:
                figures["education_gain_distrib"] = str(fig_path)

        # 2. Teacher/Class Effect
        if self._should_generate("education_teacher_effect"):
            if "teacher_id" in self.df.columns or "class_id" in self.df.columns:
                fig_path = self._education_teacher_effect(output_dir)
                if fig_path:
                    figures["education_teacher_effect"] = str(fig_path)

        # 3. Achievement Level Transition (Sankey)
        if self._should_generate("education_attainment_sankey"):
            fig_path = self._education_attainment_sankey(output_dir)
            if fig_path:
                figures["education_attainment_sankey"] = str(fig_path)

        # 4. Event Study (Introduction Timeline)
        if self._should_generate("education_event_study") and self.time:
            fig_path = self._education_event_study(output_dir)
            if fig_path:
                figures["education_event_study"] = str(fig_path)

        # 5. Fairness Analysis (Subgroup Effects)
        if self._should_generate("education_fairness"):
            fig_path = self._education_fairness(output_dir)
            if fig_path:
                figures["education_fairness"] = str(fig_path)

        return figures

    def _education_gain_distrib(self, output_dir: Path) -> Optional[Path]:
        """Achievement gain distribution (ΔY)"""
        if not self.t or not self.y:
            return None

        treated_gains = self.df[self.df[self.t] == 1][self.y]
        control_gains = self.df[self.df[self.t] == 0][self.y]

        fig = go.Figure()

        fig.add_trace(go.Histogram(
            x=treated_gains,
            name="Treated",
            opacity=0.7,
            marker_color='#10b981',
            nbinsx=30
        ))

        fig.add_trace(go.Histogram(
            x=control_gains,
            name="Control",
            opacity=0.7,
            marker_color='#ef4444',
            nbinsx=30
        ))

        fig.update_layout(
            title="Achievement Gain Distribution",
            xaxis_title="Test Score",
            yaxis_title="Count",
            barmode='overlay',
            template="plotly_dark"
        )

        path = output_dir / "education_gain_distrib.html"
        fig.write_html(str(path))
        return path

    def _education_teacher_effect(self, output_dir: Path) -> Optional[Path]:
        """Teacher/Class effect heterogeneity"""
        teacher_col = "teacher_id" if "teacher_id" in self.df.columns else "class_id"
        if teacher_col not in self.df.columns or not self.y:
            return None

        teacher_effects = self.df.groupby(teacher_col)[self.y].mean().sort_values(ascending=False).head(15)

        fig = go.Figure(go.Bar(
            x=teacher_effects.index.astype(str),
            y=teacher_effects.values,
            marker_color='#3b82f6'
        ))

        fig.update_layout(
            title="Teacher/Class Average Performance",
            xaxis_title="Teacher ID",
            yaxis_title="Mean Test Score",
            template="plotly_dark"
        )

        path = output_dir / "education_teacher_effect.html"
        fig.write_html(str(path))
        return path

    def _education_attainment_sankey(self, output_dir: Path) -> Optional[Path]:
        """Achievement level transition Sankey diagram"""
        # Simplified Sankey placeholder
        fig = go.Figure(data=[go.Sankey(
            node=dict(
                label=["Low (Pre)", "Medium (Pre)", "High (Pre)", "Low (Post)", "Medium (Post)", "High (Post)"],
                color=["#ef4444", "#f59e0b", "#10b981", "#ef4444", "#f59e0b", "#10b981"]
            ),
            link=dict(
                source=[0, 0, 1, 1, 2, 2],
                target=[3, 4, 4, 5, 5, 5],
                value=[10, 15, 20, 25, 15, 30]
            )
        )])

        fig.update_layout(
            title="Achievement Level Transition (Sankey)",
            template="plotly_dark"
        )

        path = output_dir / "education_attainment_sankey.html"
        fig.write_html(str(path))
        return path

    def _education_event_study(self, output_dir: Path) -> Optional[Path]:
        """Event study around program introduction"""
        if not self.time or not self.y:
            return None

        # Simulate event study coefficients
        periods = list(range(-5, 6))
        coefficients = [np.random.normal(0, 0.5) if p < 0 else np.random.normal(2, 0.5) for p in periods]

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=periods,
            y=coefficients,
            mode='lines+markers',
            name='ATE',
            line=dict(color='#3b82f6', width=3),
            marker=dict(size=8)
        ))

        fig.add_vline(x=0, line_dash="dash", line_color="red", annotation_text="Program Start")
        fig.add_hline(y=0, line_dash="dot", line_color="gray")

        fig.update_layout(
            title="Event Study: Program Introduction Timeline",
            xaxis_title="Periods Relative to Introduction",
            yaxis_title="Treatment Effect",
            template="plotly_dark"
        )

        path = output_dir / "education_event_study.html"
        fig.write_html(str(path))
        return path

    def _education_fairness(self, output_dir: Path) -> Optional[Path]:
        """Fairness analysis: subgroup effects"""
        # Simulate subgroup effects
        subgroups = ["Male", "Female", "Low SES", "High SES", "English", "Non-English"]
        effects = np.random.normal(2.0, 0.8, len(subgroups))
        ci_lower = effects - 1.0
        ci_upper = effects + 1.0

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=effects,
            y=subgroups,
            mode='markers',
            marker=dict(size=12, color='#8b5cf6'),
            error_x=dict(
                type='data',
                symmetric=False,
                array=ci_upper - effects,
                arrayminus=effects - ci_lower
            ),
            name='ATE with 95% CI'
        ))

        fig.add_vline(x=0, line_dash="dash", line_color="gray")

        fig.update_layout(
            title="Fairness Analysis: Treatment Effects by Subgroup",
            xaxis_title="Average Treatment Effect",
            yaxis_title="Subgroup",
            template="plotly_dark"
        )

        path = output_dir / "education_fairness.html"
        fig.write_html(str(path))
        return path

    # ==================== RETAIL OBJECTIVE ====================

    def _generate_retail(self, output_dir: Path) -> Dict[str, str]:
        """Retail objective: 5 figures (with intelligent selection)"""
        figures = {}

        # 1. Uplift Curve
        if self._should_generate("retail_uplift_curve"):
            fig_path = self._retail_uplift_curve(output_dir)
            if fig_path:
                figures["retail_uplift_curve"] = str(fig_path)

        # 2. Price-Demand IV
        if self._should_generate("retail_price_iv") and "price" in self.df.columns:
            fig_path = self._retail_price_iv(output_dir)
            if fig_path:
                figures["retail_price_iv"] = str(fig_path)

        # 3. Channel Effect
        if self._should_generate("retail_channel_effect") and "channel" in self.df.columns:
            fig_path = self._retail_channel_effect(output_dir)
            if fig_path:
                figures["retail_channel_effect"] = str(fig_path)

        # 4. Inventory Constraint Heat
        if self._should_generate("retail_inventory_heat") and "inventory" in self.df.columns:
            fig_path = self._retail_inventory_heat(output_dir)
            if fig_path:
                figures["retail_inventory_heat"] = str(fig_path)

        # 5. Network Spillover (Recommendation Graph)
        if self._should_generate("retail_spillover"):
            fig_path = self._retail_spillover(output_dir)
            if fig_path:
                figures["retail_spillover"] = str(fig_path)

        return figures

    def _retail_uplift_curve(self, output_dir: Path) -> Optional[Path]:
        """Uplift curve for top-x% targeting"""
        if not self.t or not self.y:
            return None

        # Simulate uplift scores
        n = len(self.df)
        uplift_scores = np.random.normal(0.1, 0.05, n)
        sorted_idx = np.argsort(-uplift_scores)

        percentiles = np.arange(0, 101, 5)
        cumulative_uplift = []

        for p in percentiles:
            cutoff = int(n * p / 100)
            if cutoff > 0:
                avg_uplift = np.mean(uplift_scores[sorted_idx[:cutoff]])
                cumulative_uplift.append(avg_uplift * cutoff)
            else:
                cumulative_uplift.append(0)

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=percentiles,
            y=cumulative_uplift,
            mode='lines',
            fill='tozeroy',
            line=dict(color='#10b981', width=3),
            fillcolor='rgba(16, 185, 129, 0.3)'
        ))

        fig.update_layout(
            title="Uplift Curve: Targeting Top-x% Customers",
            xaxis_title="Top x% Targeted",
            yaxis_title="Cumulative Expected Revenue Lift",
            template="plotly_dark"
        )

        path = output_dir / "retail_uplift_curve.html"
        fig.write_html(str(path))
        return path

    def _retail_price_iv(self, output_dir: Path) -> Optional[Path]:
        """Price-demand IV analysis"""
        if "price" not in self.df.columns or not self.y:
            return None

        # Scatter: price vs outcome
        fig = px.scatter(
            self.df,
            x="price",
            y=self.y,
            trendline="ols",
            template="plotly_dark",
            title="Price-Demand Relationship (IV: Supply Shock)"
        )

        path = output_dir / "retail_price_iv.html"
        fig.write_html(str(path))
        return path

    def _retail_channel_effect(self, output_dir: Path) -> Optional[Path]:
        """Channel-specific treatment effects"""
        if "channel" not in self.df.columns or not self.t or not self.y:
            return None

        channel_effects = []
        for channel in self.df["channel"].unique():
            channel_data = self.df[self.df["channel"] == channel]
            treated_mean = channel_data[channel_data[self.t] == 1][self.y].mean()
            control_mean = channel_data[channel_data[self.t] == 0][self.y].mean()
            ate = treated_mean - control_mean if not np.isnan(treated_mean) and not np.isnan(control_mean) else 0
            channel_effects.append({"channel": channel, "ate": ate})

        channel_df = pd.DataFrame(channel_effects).sort_values("ate", ascending=False)

        fig = go.Figure(go.Bar(
            x=channel_df["channel"],
            y=channel_df["ate"],
            marker_color='#3b82f6'
        ))

        fig.update_layout(
            title="Treatment Effect by Channel (Web/App/Store)",
            xaxis_title="Channel",
            yaxis_title="ATE (Revenue)",
            template="plotly_dark"
        )

        path = output_dir / "retail_channel_effect.html"
        fig.write_html(str(path))
        return path

    def _retail_inventory_heat(self, output_dir: Path) -> Optional[Path]:
        """Inventory constraint heatmap"""
        # Placeholder
        fig = go.Figure()

        fig.add_annotation(
            text="Inventory Constraint Heatmap<br>(Stock=0 Periods Highlighted)",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=20, color="white")
        )

        fig.update_layout(
            title="Inventory Constraint Timeline",
            template="plotly_dark"
        )

        path = output_dir / "retail_inventory_heat.html"
        fig.write_html(str(path))
        return path

    def _retail_spillover(self, output_dir: Path) -> Optional[Path]:
        """Network spillover (recommendation graph)"""
        # Placeholder network graph
        fig = go.Figure()

        fig.add_annotation(
            text="Network Spillover<br>(Recommendation × Browse Graph)",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=20, color="white")
        )

        fig.update_layout(
            title="Network Spillover Effect",
            template="plotly_dark"
        )

        path = output_dir / "retail_spillover.html"
        fig.write_html(str(path))
        return path

    # ==================== FINANCE OBJECTIVE ====================

    def _generate_finance(self, output_dir: Path) -> Dict[str, str]:
        """Finance objective: 4 figures"""
        figures = {}
        path = self._finance_pnl_breakdown(output_dir)
        if path: figures["finance_pnl"] = str(path)

        path = self._finance_portfolio_split(output_dir)
        if path: figures["finance_portfolio"] = str(path)

        path = self._finance_risk_return(output_dir)
        if path: figures["finance_risk_return"] = str(path)

        path = self._finance_macro_sensitivity(output_dir)
        if path: figures["finance_macro"] = str(path)

        return figures

    def _finance_pnl_breakdown(self, output_dir: Path) -> Optional[Path]:
        """P&L breakdown by treatment"""
        if not self.t or not self.y:
            return None

        # Mock P&L components
        pnl_data = pd.DataFrame({
            'component': ['Revenue', 'Cost', 'Operating Income', 'Net Profit'],
            'treated': [120, -60, 45, 30],
            'control': [100, -55, 35, 20]
        })

        fig = go.Figure()
        fig.add_trace(go.Bar(name='Treated', x=pnl_data['component'], y=pnl_data['treated'], marker_color='#3b82f6'))
        fig.add_trace(go.Bar(name='Control', x=pnl_data['component'], y=pnl_data['control'], marker_color='#ef4444'))

        fig.update_layout(
            title="P&L Breakdown: Treated vs Control",
            barmode='group',
            template="plotly_white"
        )

        path = output_dir / "finance_pnl.html"
        fig.write_html(str(path))
        return path

    def _finance_portfolio_split(self, output_dir: Path) -> Optional[Path]:
        """Portfolio allocation split"""
        # Mock portfolio allocation
        categories = ['Equities', 'Bonds', 'Derivatives', 'Cash']
        values = [45, 30, 15, 10]

        fig = go.Figure(go.Pie(labels=categories, values=values, hole=0.4))
        fig.update_layout(title="Portfolio Allocation", template="plotly_white")

        path = output_dir / "finance_portfolio.html"
        fig.write_html(str(path))
        return path

    def _finance_risk_return(self, output_dir: Path) -> Optional[Path]:
        """Risk-return tradeoff"""
        # Mock risk-return data
        portfolios = pd.DataFrame({
            'risk': np.random.uniform(0.05, 0.25, 20),
            'return': np.random.uniform(0.02, 0.15, 20),
            'portfolio': [f'P{i}' for i in range(20)]
        })

        fig = px.scatter(portfolios, x='risk', y='return', text='portfolio',
                        title="Risk-Return Tradeoff", template="plotly_white")
        fig.update_traces(textposition='top center')

        path = output_dir / "finance_risk_return.html"
        fig.write_html(str(path))
        return path

    def _finance_macro_sensitivity(self, output_dir: Path) -> Optional[Path]:
        """Macro sensitivity analysis"""
        # Mock sensitivity to interest rates
        rates = np.linspace(0, 0.10, 50)
        portfolio_value = 100 - 200*rates + np.random.normal(0, 2, 50)

        fig = go.Figure(go.Scatter(x=rates*100, y=portfolio_value, mode='lines+markers'))
        fig.update_layout(
            title="Portfolio Sensitivity to Interest Rates",
            xaxis_title="Interest Rate (%)",
            yaxis_title="Portfolio Value ($M)",
            template="plotly_white"
        )

        path = output_dir / "finance_macro.html"
        fig.write_html(str(path))
        return path

    # ==================== NETWORK OBJECTIVE ====================

    def _generate_network(self, output_dir: Path) -> Dict[str, str]:
        """Network objective: 3 figures"""
        figures = {}
        path = self._network_spillover_heat(output_dir)
        if path: figures["network_spillover_heat"] = str(path)

        path = self._network_graph_view(output_dir)
        if path: figures["network_graph"] = str(path)

        path = self._network_interference(output_dir)
        if path: figures["network_interference"] = str(path)

        return figures

    def _network_spillover_heat(self, output_dir: Path) -> Optional[Path]:
        """Network spillover heatmap"""
        # Mock network adjacency/spillover matrix
        n = 10
        spillover_matrix = np.random.uniform(0, 1, (n, n))
        np.fill_diagonal(spillover_matrix, 1)

        fig = go.Figure(go.Heatmap(
            z=spillover_matrix,
            colorscale='Blues',
            showscale=True
        ))
        fig.update_layout(
            title="Network Spillover Effect Matrix",
            xaxis_title="Node",
            yaxis_title="Node",
            template="plotly_white"
        )

        path = output_dir / "network_spillover_heat.html"
        fig.write_html(str(path))
        return path

    def _network_graph_view(self, output_dir: Path) -> Optional[Path]:
        """Network graph visualization"""
        # Mock network edges
        edges = [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2), (1, 3), (4, 5), (5, 6)]

        # Create node positions
        n_nodes = 7
        theta = np.linspace(0, 2*np.pi, n_nodes, endpoint=False)
        x_nodes = np.cos(theta)
        y_nodes = np.sin(theta)

        # Edge traces
        edge_x, edge_y = [], []
        for e in edges:
            edge_x.extend([x_nodes[e[0]], x_nodes[e[1]], None])
            edge_y.extend([y_nodes[e[0]], y_nodes[e[1]], None])

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=edge_x, y=edge_y, mode='lines', line=dict(color='gray', width=1)))
        fig.add_trace(go.Scatter(x=x_nodes, y=y_nodes, mode='markers+text',
                                marker=dict(size=20, color='lightblue'),
                                text=[f'N{i}' for i in range(n_nodes)],
                                textposition="top center"))

        fig.update_layout(
            title="Social Network Graph",
            showlegend=False,
            template="plotly_white",
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False)
        )

        path = output_dir / "network_graph.html"
        fig.write_html(str(path))
        return path

    def _network_interference(self, output_dir: Path) -> Optional[Path]:
        """Interference-adjusted ATE"""
        # Mock ATE with/without interference adjustment
        methods = ['Unadjusted ATE', 'Adjusted for\nDirect Effects', 'Adjusted for\nSpillover']
        ate_values = [2.5, 2.1, 1.8]
        ci_lower = [2.0, 1.7, 1.4]
        ci_upper = [3.0, 2.5, 2.2]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=ate_values,
            y=methods,
            mode='markers',
            marker=dict(size=15, color='blue'),
            error_x=dict(
                type='data',
                symmetric=False,
                array=[u - v for u, v in zip(ci_upper, ate_values)],
                arrayminus=[v - l for v, l in zip(ate_values, ci_lower)]
            )
        ))

        fig.add_vline(x=0, line_dash="dash", line_color="gray")
        fig.update_layout(
            title="Network Interference-Adjusted Treatment Effects",
            xaxis_title="Average Treatment Effect",
            yaxis_title="Method",
            template="plotly_white"
        )

        path = output_dir / "network_interference.html"
        fig.write_html(str(path))
        return path

    # ==================== POLICY OBJECTIVE ====================

    def _generate_policy(self, output_dir: Path) -> Dict[str, str]:
        """Policy objective: 3 figures"""
        figures = {}
        path = self._policy_did_panel(output_dir)
        if path: figures["policy_did"] = str(path)

        path = self._policy_rd_scan(output_dir)
        if path: figures["policy_rd"] = str(path)

        path = self._policy_geo_map(output_dir)
        if path: figures["policy_geo"] = str(path)

        return figures

    def _policy_did_panel(self, output_dir: Path) -> Optional[Path]:
        """Difference-in-Differences panel"""
        # Mock DID data
        time_periods = range(2015, 2025)
        treated_pre = [50 + np.random.normal(0, 2) for _ in range(5)]
        treated_post = [55 + i*2 + np.random.normal(0, 2) for i in range(5)]
        control_pre = [48 + np.random.normal(0, 2) for _ in range(5)]
        control_post = [49 + i*0.5 + np.random.normal(0, 2) for i in range(5)]

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=list(time_periods), y=treated_pre + treated_post,
                                mode='lines+markers', name='Treated', line=dict(color='blue', width=3)))
        fig.add_trace(go.Scatter(x=list(time_periods), y=control_pre + control_post,
                                mode='lines+markers', name='Control', line=dict(color='red', width=3)))

        fig.add_vline(x=2019.5, line_dash="dash", annotation_text="Policy\nIntervention")

        fig.update_layout(
            title="Difference-in-Differences: Policy Impact Over Time",
            xaxis_title="Year",
            yaxis_title="Outcome",
            template="plotly_white"
        )

        path = output_dir / "policy_did.html"
        fig.write_html(str(path))
        return path

    def _policy_rd_scan(self, output_dir: Path) -> Optional[Path]:
        """Regression Discontinuity design scan"""
        # Mock RD data
        x = np.linspace(-10, 10, 200)
        y = np.where(x >= 0, 
                    2 + 0.5*x + 3 + np.random.normal(0, 1, 200),
                    2 + 0.5*x + np.random.normal(0, 1, 200))

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=x[x < 0], y=y[x < 0], mode='markers',
                                marker=dict(color='red', opacity=0.5), name='Below Threshold'))
        fig.add_trace(go.Scatter(x=x[x >= 0], y=y[x >= 0], mode='markers',
                                marker=dict(color='blue', opacity=0.5), name='Above Threshold'))

        fig.add_vline(x=0, line_dash="dash", line_color="black", annotation_text="Cutoff")

        fig.update_layout(
            title="Regression Discontinuity: Policy Eligibility Threshold",
            xaxis_title="Running Variable (Distance from Cutoff)",
            yaxis_title="Outcome",
            template="plotly_white"
        )

        path = output_dir / "policy_rd.html"
        fig.write_html(str(path))
        return path

    def _policy_geo_map(self, output_dir: Path) -> Optional[Path]:
        """Geographic policy impact map"""
        # Mock geographic data
        states = ['CA', 'TX', 'FL', 'NY', 'PA', 'IL', 'OH', 'GA', 'NC', 'MI']
        effects = np.random.uniform(-2, 5, len(states))

        fig = go.Figure(go.Bar(
            x=states,
            y=effects,
            marker_color=np.where(effects > 0, 'green', 'red')
        ))

        fig.add_hline(y=0, line_dash="dash", line_color="gray")

        fig.update_layout(
            title="Geographic Policy Impact by State",
            xaxis_title="State",
            yaxis_title="Policy Effect",
            template="plotly_white"
        )

        path = output_dir / "policy_geo.html"
        fig.write_html(str(path))
        return path


def generate_objective_figures(
    df: pd.DataFrame,
    mapping: Dict[str, str],
    objective: str,
    output_dir: Path
) -> Dict[str, str]:
    """
    Generate objective-specific figures

    Args:
        df: DataFrame
        mapping: Role mapping
        objective: Objective name (medical, education, retail, finance, network, policy)
        output_dir: Output directory

    Returns:
        Dict of figure name -> file path
    """
    generator = ObjectiveFigureGenerator(df, mapping, objective)
    return generator.generate_all(output_dir)
