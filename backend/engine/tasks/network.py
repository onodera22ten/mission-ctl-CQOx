"""
Network Task (ネットワーク)

Panels: Network Spillover
"""

from typing import List, Dict, Any
import numpy as np
from .base import BaseTask


class NetworkTask(BaseTask):
    """Network interference and spillover effects"""

    @classmethod
    def required_roles(cls) -> List[str]:
        return ["treatment", "y", "cluster_id"]

    @classmethod
    def optional_roles(cls) -> List[str]:
        return ["neighbor_exposure"]

    @classmethod
    def panels(cls) -> List[str]:
        return ["network_spillover"]

    def execute(self) -> Dict[str, Any]:
        """Execute network analysis"""
        figures = {}
        estimates = {}

        # Compute spillover effects
        spillover = self._compute_spillover()
        estimates["direct_effect"] = spillover["direct"]
        estimates["spillover_effect"] = spillover["spillover"]
        estimates["total_effect"] = spillover["total"]

        fig_path = self._generate_spillover_plot(spillover)
        if fig_path:
            figures["network_spillover"] = str(fig_path)

        return {
            "estimates": estimates,
            "figures": figures,
            "diagnostics": {
                "n_clusters": spillover["n_clusters"],
                "interference_detected": spillover["spillover"] != 0,
            },
        }

    def _compute_spillover(self) -> Dict[str, Any]:
        """Compute direct and spillover effects"""
        t = self.get_column("treatment")
        y = self.get_column("y")
        cluster = self.get_column("cluster_id")

        # Compute cluster-level treatment intensity
        cluster_treatment = self.df.groupby(cluster)[t.name].mean()

        # Direct effect: own treatment
        direct = float(y[t == 1].mean() - y[t == 0].mean())

        # Spillover: effect of neighbors' treatment (pseudo-estimate)
        # For each unit, compute mean treatment of others in cluster
        neighbor_exposure = []
        for idx, row in self.df.iterrows():
            clust = row[cluster.name]
            own_t = row[t.name]
            cluster_mean_t = cluster_treatment[clust]
            # Neighbor exposure excludes self
            n_in_cluster = (cluster == clust).sum()
            if n_in_cluster > 1:
                neighbor_exp = (cluster_mean_t * n_in_cluster - own_t) / (n_in_cluster - 1)
            else:
                neighbor_exp = 0
            neighbor_exposure.append(neighbor_exp)

        # Estimate spillover as correlation between neighbor exposure and outcome
        # (controlling for own treatment)
        from sklearn.linear_model import LinearRegression

        X = np.column_stack([t, neighbor_exposure])
        lr = LinearRegression()
        lr.fit(X, y)

        spillover = float(lr.coef_[1])
        total = direct + spillover

        return {
            "direct": direct,
            "spillover": spillover,
            "total": total,
            "n_clusters": int(cluster.nunique()),
        }

    def _generate_spillover_plot(self, spillover: Dict[str, Any]) -> str:
        """Generate spillover effect comparison"""
        import matplotlib.pyplot as plt

        effects = ['Direct Effect', 'Spillover Effect', 'Total Effect']
        values = [spillover['direct'], spillover['spillover'], spillover['total']]
        colors = ['#3b82f6', '#8b5cf6', '#10b981']

        fig, ax = plt.subplots(figsize=(8, 5), facecolor='black')
        ax.set_facecolor('black')

        bars = ax.bar(effects, values, color=colors, edgecolor='white', linewidth=2, alpha=0.8)

        ax.axhline(0, color='#94a3b8', linestyle='--', linewidth=2, alpha=0.5)

        ax.set_ylabel('Effect Size', fontsize=14, color='white', fontweight='bold')
        ax.set_title('Network Spillover Effects', fontsize=16, color='white', fontweight='bold')
        ax.tick_params(colors='white', labelsize=12)
        ax.spines['bottom'].set_color('white')
        ax.spines['left'].set_color('white')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(True, alpha=0.2, color='white', axis='y')

        # Add value labels
        for bar, val in zip(bars, values):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2, height,
                   f'{val:.3f}', ha='center', va='bottom' if val > 0 else 'top',
                   fontsize=13, color='white', fontweight='bold')

        path = self.output_dir / "network_spillover.png"
        plt.tight_layout()
        plt.savefig(path, dpi=300, facecolor='black')
        plt.close()
        return str(path)
