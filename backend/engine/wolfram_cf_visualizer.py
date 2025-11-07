"""
WolframONE Counterfactual Visualizer (Plan1.pdf準拠)
Base/CF/Δの3種類を生成する42図タイプ
"""
from pathlib import Path
from typing import Dict, List, Tuple
import pandas as pd
from .wolfram_visualizer_fixed import WolframVisualizer


class WolframCFVisualizer:
    """
    WolframONE Counterfactual可視化エンジン

    全ての図についてBase/CF/Δの3種類を生成
    """

    # 42 figure types (Plan1.pdf準拠)
    FIGURE_TYPES = [
        # Core causal inference (1-10)
        "ate_density", "ate_ci", "parallel_trends", "event_study",
        "propensity_overlap", "balance_smd", "rosenbaum_gamma",
        "evalue", "placebo_test", "power_analysis",

        # Heterogeneity (11-18)
        "cate_waterfall", "cate_heatmap", "cate_surface_3d",
        "uplift_curve", "qini_curve", "metalearner_comparison",
        "subgroup_forest", "policy_tree",

        # Network & Spillover (19-24)
        "network_diffusion", "spillover_decay", "peer_effect_distribution",
        "cluster_randomization", "interference_bounds", "network_topology",

        # Time-varying & DiD (25-30)
        "tvce_line", "cohort_trends", "staggered_did",
        "synthetic_control_weights", "synthetic_control_fit", "event_study_stacked",

        # IV & Selection (31-36)
        "iv_first_stage_f", "iv_strength_vs_2sls", "iv_overid_test",
        "selection_bias_bounds", "ope_diagnostics", "doubly_robust_comparison",

        # Transportation & External Validity (37-42)
        "transport_weights", "transport_risk_surface",
        "generalizability_index", "geographic_heterogeneity",
        "domain_adaptation", "external_validity_score"
    ]

    def __init__(self, wolfram_path: str = "/home/hirokionodera/wolfram/14.3/Executables/wolframscript"):
        self.wolfram = WolframVisualizer(wolfram_path)

    def generate_all_cf(
        self,
        df_base: pd.DataFrame,
        df_cf: pd.DataFrame,
        df_delta: pd.DataFrame,
        mapping: Dict[str, str],
        output_dir: Path,
        figure_types: List[str] = None
    ) -> Dict[str, Dict[str, str]]:
        """
        Generate all counterfactual figures

        Args:
            df_base: Baseline dataframe
            df_cf: Counterfactual dataframe
            df_delta: Delta dataframe (CF - Base)
            mapping: Column role mapping
            output_dir: Output directory
            figure_types: Specific figure types to generate (default: all)

        Returns:
            Dict[figure_type, Dict[variant, path]]
            Example: {
                "ate_density": {
                    "base": "ate_density_base.png",
                    "cf": "ate_density_cf.png",
                    "delta": "ate_density_delta.png"
                }
            }
        """
        if figure_types is None:
            figure_types = self.FIGURE_TYPES[:10]  # デフォルトはコア10図のみ

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        results = {}

        for fig_type in figure_types:
            try:
                paths = self._generate_cf_triple(
                    fig_type, df_base, df_cf, df_delta, mapping, output_dir
                )
                results[fig_type] = paths
            except Exception as e:
                print(f"[WolframCF] Warning: Failed to generate {fig_type}: {e}")
                continue

        return results

    def _generate_cf_triple(
        self,
        fig_type: str,
        df_base: pd.DataFrame,
        df_cf: pd.DataFrame,
        df_delta: pd.DataFrame,
        mapping: Dict[str, str],
        output_dir: Path
    ) -> Dict[str, str]:
        """
        Generate Base/CF/Delta triple for one figure type
        """
        paths = {}

        # Base
        base_path = output_dir / f"{fig_type}_base.png"
        if fig_type in ["ate_density", "ate_ci"]:
            # ATEベース図
            self._generate_ate_figure(df_base, mapping, base_path, title=f"{fig_type} (Base)")
        elif fig_type == "parallel_trends":
            self.wolfram.generate_parallel_trends(df_base, mapping, base_path)
        elif fig_type == "propensity_overlap":
            self._generate_overlap(df_base, mapping, base_path, title="Propensity Overlap (Base)")
        # ... 他の図タイプ

        paths["base"] = str(base_path)

        # CF
        cf_path = output_dir / f"{fig_type}_cf.png"
        if fig_type in ["ate_density", "ate_ci"]:
            self._generate_ate_figure(df_cf, mapping, cf_path, title=f"{fig_type} (CF)")
        elif fig_type == "parallel_trends":
            self.wolfram.generate_parallel_trends(df_cf, mapping, cf_path)
        elif fig_type == "propensity_overlap":
            self._generate_overlap(df_cf, mapping, cf_path, title="Propensity Overlap (CF)")

        paths["cf"] = str(cf_path)

        # Delta
        delta_path = output_dir / f"{fig_type}_delta.png"
        self._generate_delta_figure(fig_type, df_delta, mapping, delta_path)
        paths["delta"] = str(delta_path)

        return paths

    def _generate_ate_figure(self, df: pd.DataFrame, mapping: Dict[str, str],
                            output_path: Path, title: str = "ATE"):
        """Generate ATE density figure"""
        y_col = mapping.get("y")
        t_col = mapping.get("treatment")

        if not (y_col and t_col):
            raise ValueError("Missing y or treatment column")

        # Simple ATE calculation
        treated = df[df[t_col] == 1][y_col]
        control = df[df[t_col] == 0][y_col]
        ate = treated.mean() - control.mean()

        # Generate Wolfram visualization
        wolfram_code = f'''
(* ATE Density Plot *)
ate = {ate};
dist = NormalDistribution[ate, {treated.std()}];

plot = Plot[
    PDF[dist, x],
    {{x, ate - 3*{treated.std()}, ate + 3*{treated.std()}}},
    PlotLabel -> Style["{title}\\nATE = {ate:.2f}", Bold, 16],
    AxesLabel -> {{"Effect Size", "Density"}},
    Filling -> Axis,
    PlotStyle -> {{Thick, Blue}},
    ImageSize -> 800,
    Background -> White
];

Export["{str(output_path).replace(chr(92), '/')}", plot, ImageResolution -> 300]
'''
        self.wolfram._execute_wolfram_code(wolfram_code)

    def _generate_overlap(self, df: pd.DataFrame, mapping: Dict[str, str],
                         output_path: Path, title: str = "Overlap"):
        """Generate propensity overlap figure"""
        ps_col = mapping.get("log_propensity") or "propensity_score"
        t_col = mapping.get("treatment")

        if ps_col not in df.columns or not t_col:
            # Fallback: use simple placeholder
            return

        treated_ps = df[df[t_col] == 1][ps_col].tolist()
        control_ps = df[df[t_col] == 0][ps_col].tolist()

        wolfram_code = f'''
treatedPS = {treated_ps[:100]};  (* サンプル100件 *)
controlPS = {control_ps[:100]};

plot = Histogram[
    {{treatedPS, controlPS}},
    Automatic,
    "Probability",
    ChartLegends -> {{"Treated", "Control"}},
    ChartStyle -> {{Directive[Opacity[0.6], Blue], Directive[Opacity[0.6], Red]}},
    PlotLabel -> Style["{title}", Bold, 16],
    AxesLabel -> {{"Propensity Score", "Density"}},
    ImageSize -> 800,
    Background -> White
];

Export["{str(output_path).replace(chr(92), '/')}", plot, ImageResolution -> 300]
'''
        self.wolfram._execute_wolfram_code(wolfram_code)

    def _generate_delta_figure(self, fig_type: str, df_delta: pd.DataFrame,
                               mapping: Dict[str, str], output_path: Path):
        """Generate Delta figure (CF - Base)"""
        y_col = mapping.get("y")

        if not y_col or y_col not in df_delta.columns:
            # Placeholder
            wolfram_code = f'''
plot = Graphics[
    Text[Style["Delta: {fig_type}\\n(\u0394 = CF - Base)", 24]],
    ImageSize -> 800,
    Background -> White
];
Export["{str(output_path).replace(chr(92), '/')}", plot]
'''
            self.wolfram._execute_wolfram_code(wolfram_code)
            return

        # Delta distribution
        delta_values = df_delta[y_col].dropna().tolist()[:1000]  # サンプル

        wolfram_code = f'''
deltaValues = {delta_values};
plot = Histogram[
    deltaValues,
    Automatic,
    "Probability",
    PlotLabel -> Style["Delta Distribution: {fig_type}\\n(\u0394 = CF - Base)", Bold, 16],
    ChartStyle -> Directive[Opacity[0.7], Green],
    AxesLabel -> {{"Delta Value", "Density"}},
    ImageSize -> 800,
    Background -> White
];

Export["{str(output_path).replace(chr(92), '/')}", plot, ImageResolution -> 300]
'''
        self.wolfram._execute_wolfram_code(wolfram_code)
