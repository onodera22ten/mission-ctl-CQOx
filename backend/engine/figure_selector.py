# backend/engine/figure_selector.py
"""
Smart Figure Selection System

Automatically determines which domain-specific figures to generate based on:
1. Data availability (required columns exist)
2. Data quality (sufficient non-null values)
3. Data patterns (appropriate distributions for visualization)
"""
from __future__ import annotations
import logging
from typing import Dict, List, Set, Tuple
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class FigureSelector:
    """
    Intelligently selects which domain figures to generate

    Each figure has prerequisites that must be met:
    - Required columns must exist
    - Minimum data quality thresholds
    - Appropriate data distributions
    """

    # Define prerequisites for each domain-specific figure
    FIGURE_REQUIREMENTS = {
        # MEDICAL DOMAIN (6 figures)
        "medical_km_survival": {
            "required_columns": ["y", "treatment"],
            "optional_columns": ["time"],
            "min_rows": 50,
            "description": "KM-style survival curves"
        },
        "medical_dose_response": {
            "required_columns": ["y", "dose"],
            "optional_columns": [],
            "min_rows": 30,
            "min_dose_levels": 3,
            "description": "Dose-response relationship"
        },
        "medical_cluster_effect": {
            "required_columns": ["y", "treatment"],
            "required_one_of": ["cluster_id", "site_id", "hospital_id", "provider_id"],
            "min_rows": 100,
            "min_clusters": 3,
            "description": "Facility/provider cluster effects"
        },
        "medical_adverse_events": {
            "required_columns": ["treatment"],
            "required_one_of": ["adverse_event", "ae", "side_effect"],
            "min_rows": 50,
            "description": "Adverse event risk map"
        },
        "medical_iv_candidates": {
            "required_columns": ["y", "treatment"],
            "optional_columns": ["instrument", "z"],
            "min_rows": 100,
            "description": "IV (Natural Experiment) candidates"
        },
        "medical_sensitivity": {
            "required_columns": ["y", "treatment"],
            "min_rows": 50,
            "description": "Rosenbaum sensitivity analysis"
        },

        # EDUCATION DOMAIN (5 figures)
        "education_gain_distrib": {
            "required_columns": ["y", "treatment"],
            "min_rows": 50,
            "description": "Achievement gain distribution"
        },
        "education_teacher_effect": {
            "required_columns": ["y"],
            "required_one_of": ["teacher_id", "class_id", "instructor_id"],
            "min_rows": 100,
            "min_groups": 5,
            "description": "Teacher/class effect heterogeneity"
        },
        "education_attainment_sankey": {
            "required_columns": ["y"],
            "optional_columns": ["time", "pre_score", "post_score"],
            "min_rows": 50,
            "description": "Achievement level transition Sankey"
        },
        "education_event_study": {
            "required_columns": ["y", "treatment", "time"],
            "min_rows": 100,
            "min_time_periods": 5,
            "description": "Event study around program introduction"
        },
        "education_fairness": {
            "required_columns": ["y", "treatment"],
            "optional_columns": ["gender", "race", "ses", "language"],
            "min_rows": 100,
            "description": "Fairness analysis (subgroup effects)"
        },

        # RETAIL DOMAIN (5 figures)
        "retail_uplift_curve": {
            "required_columns": ["y", "treatment"],
            "min_rows": 100,
            "description": "Uplift curve for targeting"
        },
        "retail_price_iv": {
            "required_columns": ["y"],
            "required_one_of": ["price", "cost", "amount"],
            "min_rows": 50,
            "description": "Price-demand IV analysis"
        },
        "retail_channel_effect": {
            "required_columns": ["y", "treatment"],
            "required_one_of": ["channel", "platform", "source"],
            "min_rows": 100,
            "min_groups": 2,
            "description": "Channel-specific treatment effects"
        },
        "retail_inventory_heat": {
            "required_columns": ["time"],
            "required_one_of": ["inventory", "stock", "quantity"],
            "min_rows": 50,
            "description": "Inventory constraint timeline"
        },
        "retail_spillover": {
            "required_columns": [],
            "optional_columns": ["product_id", "user_id"],
            "min_rows": 50,
            "description": "Network spillover (recommendation graph)"
        },

        # FINANCE DOMAIN (4 figures)
        "finance_pnl": {
            "required_columns": ["y", "treatment"],
            "min_rows": 30,
            "description": "P&L breakdown by treatment"
        },
        "finance_portfolio": {
            "required_columns": [],
            "optional_columns": ["asset_class", "category", "type"],
            "min_rows": 10,
            "description": "Portfolio allocation split"
        },
        "finance_risk_return": {
            "required_columns": ["y"],
            "optional_columns": ["risk", "volatility", "return"],
            "min_rows": 20,
            "description": "Risk-return tradeoff"
        },
        "finance_macro": {
            "required_columns": ["y"],
            "optional_columns": ["interest_rate", "rate", "macro_factor"],
            "min_rows": 30,
            "description": "Macro sensitivity analysis"
        },

        # NETWORK DOMAIN (3 figures)
        "network_spillover_heat": {
            "required_columns": [],
            "optional_columns": ["node_id", "user_id", "unit_id"],
            "min_rows": 50,
            "description": "Network spillover heatmap"
        },
        "network_graph": {
            "required_columns": [],
            "optional_columns": ["node_id", "edge_id", "friend_id"],
            "min_rows": 20,
            "description": "Network graph visualization"
        },
        "network_interference": {
            "required_columns": ["y", "treatment"],
            "optional_columns": ["network_exposure"],
            "min_rows": 100,
            "description": "Interference-adjusted ATE"
        },

        # POLICY DOMAIN (3 figures)
        "policy_did": {
            "required_columns": ["y", "treatment", "time"],
            "min_rows": 100,
            "min_time_periods": 4,
            "description": "Difference-in-Differences panel"
        },
        "policy_rd": {
            "required_columns": ["y"],
            "required_one_of": ["running_variable", "score", "threshold_distance"],
            "min_rows": 100,
            "description": "Regression Discontinuity design"
        },
        "policy_geo": {
            "required_columns": ["y"],
            "required_one_of": ["state", "region", "district", "county", "geo_id"],
            "min_rows": 50,
            "min_groups": 5,
            "description": "Geographic policy impact map"
        },
    }

    def __init__(self, df: pd.DataFrame, mapping: Dict[str, str], domain: str):
        """
        Initialize figure selector

        Args:
            df: Input dataframe
            mapping: Column role mapping
            domain: Detected domain (medical, education, retail, finance, network, policy)
        """
        self.df = df
        self.mapping = mapping
        self.domain = domain
        self.available_columns = set(df.columns)

        # Map role names to actual column names
        self.role_to_column = {
            role: col for role, col in mapping.items() if col
        }

        logger.info(f"[FigureSelector] Initialized for domain: {domain}")
        logger.info(f"[FigureSelector] Available columns: {len(self.available_columns)}")
        logger.info(f"[FigureSelector] Role mapping: {self.role_to_column}")

    def select_figures(self) -> Dict[str, Dict]:
        """
        Select which figures to generate based on data availability

        Returns:
            Dict of figure_name -> selection_info
            {
                "medical_km_survival": {
                    "should_generate": True,
                    "confidence": 0.95,
                    "reason": "All required columns present",
                    "missing": []
                },
                ...
            }
        """
        selections = {}

        # Get figures for this domain
        domain_prefix = f"{self.domain}_"
        domain_figures = {
            name: req for name, req in self.FIGURE_REQUIREMENTS.items()
            if name.startswith(domain_prefix)
        }

        logger.info(f"[FigureSelector] Evaluating {len(domain_figures)} figures for {self.domain} domain")

        for fig_name, requirements in domain_figures.items():
            selection = self._evaluate_figure(fig_name, requirements)
            selections[fig_name] = selection

            if selection["should_generate"]:
                logger.info(f"[FigureSelector] ✓ {fig_name}: {selection['reason']}")
            else:
                logger.info(f"[FigureSelector] ✗ {fig_name}: {selection['reason']}")

        return selections

    def _evaluate_figure(self, fig_name: str, requirements: Dict) -> Dict:
        """
        Evaluate if a figure should be generated

        Returns:
            {
                "should_generate": bool,
                "confidence": float,  # 0.0-1.0
                "reason": str,
                "missing": List[str]
            }
        """
        missing = []
        confidence = 1.0

        # Check minimum rows
        min_rows = requirements.get("min_rows", 10)
        if len(self.df) < min_rows:
            return {
                "should_generate": False,
                "confidence": 0.0,
                "reason": f"Insufficient data: {len(self.df)} rows < {min_rows} required",
                "missing": ["sufficient_data"]
            }

        # Check required columns (from mapping roles)
        required_cols = requirements.get("required_columns", [])
        for role in required_cols:
            col = self.role_to_column.get(role)
            if not col or col not in self.available_columns:
                missing.append(role)

        # Check required_one_of (any one column from list must exist)
        required_one_of = requirements.get("required_one_of", [])
        if required_one_of:
            found_any = any(col in self.available_columns for col in required_one_of)
            if not found_any:
                missing.append(f"one_of[{', '.join(required_one_of)}]")

        # If missing required columns, cannot generate
        if missing:
            return {
                "should_generate": False,
                "confidence": 0.0,
                "reason": f"Missing required: {', '.join(missing)}",
                "missing": missing
            }

        # Check optional quality constraints

        # Check minimum dose levels (for dose-response)
        if "min_dose_levels" in requirements:
            dose_col = self._find_column(["dose"])
            if dose_col:
                n_levels = self.df[dose_col].nunique()
                min_levels = requirements["min_dose_levels"]
                if n_levels < min_levels:
                    confidence *= 0.7

        # Check minimum clusters/groups
        if "min_clusters" in requirements or "min_groups" in requirements:
            min_count = requirements.get("min_clusters") or requirements.get("min_groups")

            # Find cluster column
            cluster_candidates = requirements.get("required_one_of", []) or ["cluster_id", "site_id"]
            cluster_col = self._find_column(cluster_candidates)

            if cluster_col:
                n_clusters = self.df[cluster_col].nunique()
                if n_clusters < min_count:
                    confidence *= 0.8

        # Check minimum time periods
        if "min_time_periods" in requirements:
            time_col = self.role_to_column.get("time")
            if time_col:
                n_periods = self.df[time_col].nunique()
                min_periods = requirements["min_time_periods"]
                if n_periods < min_periods:
                    confidence *= 0.7

        # Generate if confidence is high enough
        should_generate = confidence >= 0.6

        reason = "All requirements met"
        if confidence < 1.0:
            reason = f"Partial requirements (confidence: {confidence:.2f})"

        return {
            "should_generate": should_generate,
            "confidence": confidence,
            "reason": reason,
            "missing": []
        }

    def _find_column(self, candidates: List[str]) -> str:
        """Find first matching column from candidates"""
        for col in candidates:
            if col in self.available_columns:
                return col
        return None

    def get_recommended_figures(self) -> List[str]:
        """
        Get list of recommended figure names to generate

        Returns:
            List of figure names that should be generated
        """
        selections = self.select_figures()
        recommended = [
            fig_name for fig_name, info in selections.items()
            if info["should_generate"]
        ]

        logger.info(f"[FigureSelector] Recommending {len(recommended)} figures for {self.domain} domain")
        return recommended

    def get_selection_report(self) -> Dict:
        """
        Get detailed report of figure selection decisions

        Returns:
            {
                "domain": "medical",
                "total_figures": 6,
                "recommended": 4,
                "skipped": 2,
                "details": {...}
            }
        """
        selections = self.select_figures()
        recommended = [name for name, info in selections.items() if info["should_generate"]]
        skipped = [name for name, info in selections.items() if not info["should_generate"]]

        return {
            "domain": self.domain,
            "total_figures": len(selections),
            "recommended": len(recommended),
            "skipped": len(skipped),
            "recommended_figures": recommended,
            "skipped_figures": skipped,
            "details": selections
        }


def select_domain_figures(
    df: pd.DataFrame,
    mapping: Dict[str, str],
    domain: str
) -> List[str]:
    """
    Convenience function to get recommended figures

    Args:
        df: Input dataframe
        mapping: Column role mapping
        domain: Domain name

    Returns:
        List of figure names to generate

    Example:
        >>> import pandas as pd
        >>> df = pd.read_csv("medical_data.csv")
        >>> mapping = {"y": "outcome", "treatment": "drug"}
        >>> figures = select_domain_figures(df, mapping, "medical")
        >>> print(f"Generating {len(figures)} figures")
    """
    selector = FigureSelector(df, mapping, domain)
    return selector.get_recommended_figures()
