"""
Transportability Task (転移/運搬性)

Panels: Transport Weights, Transport Validity
"""

from typing import List, Dict, Any
import numpy as np
from .base import BaseTask


class TransportabilityTask(BaseTask):
    """External validity and transportability analysis"""

    @classmethod
    def required_roles(cls) -> List[str]:
        return ["treatment", "y", "domain"]

    @classmethod
    def optional_roles(cls) -> List[str]:
        return ["features"]

    @classmethod
    def panels(cls) -> List[str]:
        return [
            "transport_weights",
            "transport_validity",
        ]

    def execute(self) -> Dict[str, Any]:
        """Execute transportability analysis"""
        figures = {}
        estimates = {}

        # Compute transport weights
        weights = self._compute_transport_weights()
        estimates["transport_weights"] = weights

        fig_path = self._generate_transport_weights_plot()
        if fig_path:
            figures["transport_weights"] = str(fig_path)

        # Transport validity diagnostics
        if self.has_role("features"):
            validity = self._compute_transport_validity()
            estimates["transport_validity"] = validity

            fig_path = self._generate_transport_validity_plot(validity)
            if fig_path:
                figures["transport_validity"] = str(fig_path)

        return {
            "estimates": estimates,
            "figures": figures,
            "diagnostics": {
                "domains": list(self.get_column("domain").unique()),
                "transportable": estimates.get("transport_validity", {}).get("ks_statistic", 1.0) < 0.2,
            },
        }

    def _compute_transport_weights(self) -> Dict[str, Any]:
        """Compute inverse odds weights for transportability"""
        from sklearn.linear_model import LogisticRegression

        domain = self.get_column("domain")
        feature_cols = [col for col in self.df.columns if col.startswith('x_')]

        if len(feature_cols) == 0:
            # No features - uniform weights
            weights = np.ones(len(self.df))
            return {
                "weights": weights.tolist(),
                "mean_weight": 1.0,
                "max_weight": 1.0,
            }

        # Binary indicator: source (1) vs target (0)
        # Assume first domain is source
        domains = domain.unique()
        source_domain = domains[0]
        is_source = (domain == source_domain).astype(int)

        X = self.df[feature_cols].fillna(0)

        # Fit propensity model for domain membership
        lr = LogisticRegression(max_iter=1000, random_state=42)
        lr.fit(X, is_source)
        p_source = lr.predict_proba(X)[:, 1]

        # Transport weights: p(target) / p(source) = (1-p) / p
        weights = (1 - p_source) / (p_source + 1e-6)
        weights = np.clip(weights, 0, 10)  # Trim extreme weights

        return {
            "weights": weights.tolist(),
            "mean_weight": float(np.mean(weights)),
            "max_weight": float(np.max(weights)),
        }

    def _generate_transport_weights_plot(self) -> str:
        """Generate transport weights distribution"""
        import matplotlib.pyplot as plt

        domain = self.get_column("domain")
        weights_dict = self._compute_transport_weights()
        weights = np.array(weights_dict["weights"])

        fig, ax = plt.subplots(figsize=(8, 5), facecolor='black')
        ax.set_facecolor('black')

        domains = domain.unique()
        for dom in domains:
            mask = domain == dom
            ax.hist(weights[mask], bins=30, alpha=0.6, label=str(dom), edgecolor='white')

        ax.axvline(1, color='#94a3b8', linestyle='--', linewidth=2, alpha=0.7, label='Weight = 1')

        ax.set_xlabel('Transport Weight', fontsize=14, color='white', fontweight='bold')
        ax.set_ylabel('Frequency', fontsize=14, color='white', fontweight='bold')
        ax.set_title('Transport Weights Distribution by Domain', fontsize=16, color='white', fontweight='bold')
        ax.legend(fontsize=12, facecolor='#1e293b', edgecolor='white', labelcolor='white')
        ax.tick_params(colors='white', labelsize=12)
        ax.spines['bottom'].set_color('white')
        ax.spines['left'].set_color('white')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(True, alpha=0.2, color='white')

        path = self.output_dir / "transport_weights.png"
        plt.tight_layout()
        plt.savefig(path, dpi=300, facecolor='black')
        plt.close()
        return str(path)

    def _compute_transport_validity(self) -> Dict[str, Any]:
        """Compute transport validity diagnostics (KS test, balance)"""
        from scipy.stats import ks_2samp

        domain = self.get_column("domain")
        feature_cols = [col for col in self.df.columns if col.startswith('x_')]

        if len(feature_cols) == 0:
            return {"ks_statistic": 0.0, "balance_smd": {}}

        domains = domain.unique()
        if len(domains) < 2:
            return {"ks_statistic": 0.0, "balance_smd": {}}

        source_domain = domains[0]
        target_domain = domains[1]

        mask_source = domain == source_domain
        mask_target = domain == target_domain

        # KS test for covariate distribution differences
        ks_stats = []
        balance_smd = {}

        for col in feature_cols:
            if pd.api.types.is_numeric_dtype(self.df[col]):
                source_vals = self.df.loc[mask_source, col].dropna()
                target_vals = self.df.loc[mask_target, col].dropna()

                if len(source_vals) > 0 and len(target_vals) > 0:
                    ks_stat, _ = ks_2samp(source_vals, target_vals)
                    ks_stats.append(ks_stat)

                    # SMD
                    diff = source_vals.mean() - target_vals.mean()
                    pooled_std = np.sqrt((source_vals.var() + target_vals.var()) / 2)
                    smd = diff / pooled_std if pooled_std > 0 else 0
                    balance_smd[col] = float(abs(smd))

        max_ks = float(max(ks_stats)) if ks_stats else 0.0

        return {
            "ks_statistic": max_ks,
            "balance_smd": balance_smd,
        }

    def _generate_transport_validity_plot(self, validity: Dict[str, Any]) -> str:
        """Generate transport validity diagnostics plot"""
        import matplotlib.pyplot as plt

        balance_smd = validity["balance_smd"]
        ks_stat = validity["ks_statistic"]

        if not balance_smd:
            return None

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 5), facecolor='black')
        for ax in [ax1, ax2]:
            ax.set_facecolor('black')

        # SMD balance plot
        vars = list(balance_smd.keys())
        smds = list(balance_smd.values())

        colors = ['#10b981' if abs(smd) < 0.1 else '#f59e0b' if abs(smd) < 0.2 else '#ef4444'
                 for smd in smds]

        ax1.barh(vars, smds, color=colors, edgecolor='white', linewidth=1.5)
        ax1.axvline(0.1, color='#f59e0b', linestyle='--', linewidth=2, alpha=0.7, label='SMD = 0.1')
        ax1.set_xlabel('SMD', fontsize=13, color='white', fontweight='bold')
        ax1.set_title('Domain Balance (SMD)', fontsize=15, color='white', fontweight='bold')
        ax1.legend(fontsize=11, facecolor='#1e293b', edgecolor='white', labelcolor='white')
        ax1.tick_params(colors='white', labelsize=10)
        ax1.spines['bottom'].set_color('white')
        ax1.spines['left'].set_color('white')
        ax1.spines['top'].set_visible(False)
        ax1.spines['right'].set_visible(False)
        ax1.grid(True, alpha=0.2, color='white', axis='x')

        # KS statistic
        ax2.bar([0], [ks_stat], color='#10b981' if ks_stat < 0.2 else '#ef4444',
               edgecolor='white', linewidth=2, alpha=0.8, width=0.5)
        ax2.axhline(0.2, color='#f59e0b', linestyle='--', linewidth=3,
                   label='Threshold (0.2)', alpha=0.8)
        ax2.set_ylabel('KS Statistic', fontsize=13, color='white', fontweight='bold')
        ax2.set_title('Distribution Similarity (KS Test)', fontsize=15, color='white', fontweight='bold')
        ax2.set_xticks([0])
        ax2.set_xticklabels(['Max KS'], fontsize=11, color='white')
        ax2.legend(fontsize=11, facecolor='#1e293b', edgecolor='white', labelcolor='white')
        ax2.tick_params(colors='white', labelsize=11)
        ax2.spines['bottom'].set_color('white')
        ax2.spines['left'].set_color('white')
        ax2.spines['top'].set_visible(False)
        ax2.spines['right'].set_visible(False)
        ax2.grid(True, alpha=0.2, color='white', axis='y')

        ax2.text(0, ks_stat, f'{ks_stat:.3f}', ha='center', va='bottom',
                fontsize=13, color='white', fontweight='bold')

        path = self.output_dir / "transport_validity.png"
        plt.tight_layout()
        plt.savefig(path, dpi=300, facecolor='black')
        plt.close()
        return str(path)
