"""
Composer - The heart of Objective-Lens architecture

Automatically selects and executes tasks based on available roles and user objectives.
"""

from typing import Dict, List, Any, Set
from pathlib import Path
import pandas as pd
import yaml

from .tasks import (
    EstimationTask,
    DiagnosticsTask,
    HeterogeneityTask,
    TimeVaryingTask,
    IVTask,
    RobustnessTask,
    NetworkTask,
    PolicyTask,
    TransportabilityTask,
    CounterfactualTask,
)


class Composer:
    """
    Composer orchestrates analysis by:
    1. Reading panel catalog
    2. Detecting available roles
    3. Selecting applicable tasks
    4. Generating figures based on gating logic
    """

    TASK_CLASSES = {
        "causal_estimation": EstimationTask,
        "diagnostics": DiagnosticsTask,
        "heterogeneity": HeterogeneityTask,
        "time_varying": TimeVaryingTask,
        "iv": IVTask,
        "robustness": RobustnessTask,
        "network": NetworkTask,
        "policy": PolicyTask,
        "transportability": TransportabilityTask,
        "counterfactual": CounterfactualTask,
    }

    def __init__(self, catalog_path: str = "config/panels/catalog.yaml"):
        """Initialize composer with panel catalog"""
        self.catalog_path = Path(catalog_path)
        self.catalog = self._load_catalog()

    def _load_catalog(self) -> Dict[str, Any]:
        """Load panel catalog YAML"""
        with open(self.catalog_path) as f:
            return yaml.safe_load(f)

    def get_available_panels(self, roles: Dict[str, str]) -> Dict[str, Any]:
        """
        Return list of panels that can be generated given available roles

        Args:
            roles: Dict mapping role -> column name (e.g., {"treatment": "received_tutoring"})

        Returns:
            Dict with:
                - available_panels: List[str] - panel keys that can be generated
                - recommended_panels: List[str] - panels with all recommended roles
                - missing_for_panels: Dict[str, List[str]] - what roles are missing for each unavailable panel
                - tasks: Dict[str, Dict] - which tasks can run and their panels
        """
        available_roles = set(roles.keys())
        panels_config = self.catalog.get("panels", {})

        available_panels = []
        recommended_panels = []
        missing_for_panels = {}

        for panel_key, panel_spec in panels_config.items():
            needs = set(panel_spec.get("needs", []))
            recommends = set(panel_spec.get("recommends", []))

            # Check if can run
            if needs.issubset(available_roles):
                available_panels.append(panel_key)

                # Check if all recommended roles present
                if recommends.issubset(available_roles):
                    recommended_panels.append(panel_key)
            else:
                # What's missing?
                missing = list(needs - available_roles)
                missing_for_panels[panel_key] = missing

        # Organize by tasks
        tasks_info = self._organize_by_tasks(available_panels, available_roles)

        return {
            "available_panels": available_panels,
            "recommended_panels": recommended_panels,
            "missing_for_panels": missing_for_panels,
            "tasks": tasks_info,
        }

    def _organize_by_tasks(self, available_panels: List[str], available_roles: Set[str]) -> Dict[str, Dict]:
        """Organize panels by task categories"""
        panels_config = self.catalog.get("panels", {})
        tasks_config = self.catalog.get("tasks", {})

        tasks_info = {}

        for task_key, task_spec in tasks_config.items():
            task_panels = task_spec.get("panels", [])

            # Filter to available panels
            available_in_task = [p for p in task_panels if p in available_panels]

            # Check if task class can run
            task_class = self.TASK_CLASSES.get(task_key)
            can_run = False
            if task_class:
                can_run = task_class.can_run(available_roles)

            tasks_info[task_key] = {
                "name": task_spec.get("name"),
                "description": task_spec.get("description"),
                "can_run": can_run,
                "available_panels": available_in_task,
                "total_panels": len(task_panels),
            }

        return tasks_info

    def execute_all_tasks(
        self,
        df: pd.DataFrame,
        roles: Dict[str, str],
        output_dir: Path,
        objectives: List[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute all applicable tasks

        Args:
            df: Input dataframe
            roles: Role mapping
            output_dir: Output directory for figures
            objectives: Optional list of specific objectives to run
                       (e.g., ["causal_estimation", "diagnostics"])

        Returns:
            Dict with:
                - estimates: Dict[task_name, Dict] - estimates from each task
                - figures: Dict[panel_key, str] - all generated figures
                - diagnostics: Dict[task_name, Dict] - diagnostics from each task
                - summary: execution summary
        """
        available_roles = set(roles.keys())
        all_estimates = {}
        all_figures = {}
        all_diagnostics = {}
        execution_log = []

        # Determine which tasks to run
        if objectives:
            tasks_to_run = {k: v for k, v in self.TASK_CLASSES.items() if k in objectives}
        else:
            tasks_to_run = self.TASK_CLASSES

        for task_key, task_class in tasks_to_run.items():
            # Check if task can run
            if not task_class.can_run(available_roles):
                execution_log.append({
                    "task": task_key,
                    "status": "skipped",
                    "reason": f"Missing required roles: {task_class.required_roles()}",
                })
                continue

            # Execute task
            try:
                task_output_dir = output_dir / task_key
                task = task_class(df, roles, task_output_dir)
                result = task.execute()

                all_estimates[task_key] = result.get("estimates", {})
                all_figures.update(result.get("figures", {}))
                all_diagnostics[task_key] = result.get("diagnostics", {})

                execution_log.append({
                    "task": task_key,
                    "status": "success",
                    "n_figures": len(result.get("figures", {})),
                })

            except Exception as e:
                execution_log.append({
                    "task": task_key,
                    "status": "error",
                    "error": str(e),
                })

        return {
            "estimates": all_estimates,
            "figures": all_figures,
            "diagnostics": all_diagnostics,
            "summary": {
                "total_tasks": len(tasks_to_run),
                "successful": len([log for log in execution_log if log["status"] == "success"]),
                "skipped": len([log for log in execution_log if log["status"] == "skipped"]),
                "failed": len([log for log in execution_log if log["status"] == "error"]),
                "total_figures": len(all_figures),
            },
            "execution_log": execution_log,
        }

    def get_role_profile(self, df: pd.DataFrame, roles: Dict[str, str]) -> Dict[str, Any]:
        """
        Generate role profile with suggestions for missing roles

        Args:
            df: Input dataframe
            roles: Current role mapping

        Returns:
            Dict with:
                - detected_roles: List of detected roles with confidence
                - missing_high_value: Roles that would unlock many panels
                - alternatives: Suggestions for unmapped columns
        """
        available_roles = set(roles.keys())
        panels_config = self.catalog.get("panels", {})

        # Count how many panels each missing role would unlock
        role_value = {}
        all_possible_roles = set()

        for panel_spec in panels_config.values():
            needs = set(panel_spec.get("needs", []))
            all_possible_roles.update(needs)

            # Check missing roles
            missing = needs - available_roles
            for role in missing:
                role_value[role] = role_value.get(role, 0) + 1

        # Sort by value
        missing_high_value = [
            {"role": role, "would_unlock": count}
            for role, count in sorted(role_value.items(), key=lambda x: -x[1])[:5]
        ]

        # Detect confidence for mapped roles
        detected_roles = [
            {"role": role, "column": col, "confidence": 1.0}
            for role, col in roles.items()
        ]

        return {
            "detected_roles": detected_roles,
            "missing_high_value": missing_high_value,
            "total_possible_roles": len(all_possible_roles),
            "mapped_roles": len(available_roles),
        }


def create_composer() -> Composer:
    """Factory function to create composer instance"""
    return Composer()
