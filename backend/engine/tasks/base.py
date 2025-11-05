"""
Base class for all Task modules
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Set, Any
from pathlib import Path
import pandas as pd


class BaseTask(ABC):
    """Base class for all causal analysis tasks"""

    def __init__(self, df: pd.DataFrame, roles: Dict[str, str], output_dir: Path):
        """
        Args:
            df: Input dataframe
            roles: Mapping of role -> column name (e.g., {"treatment": "received_tutoring"})
            output_dir: Directory for outputs
        """
        self.df = df
        self.roles = roles
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    @abstractmethod
    def required_roles(cls) -> List[str]:
        """Return list of required roles (e.g., ['treatment', 'y'])"""
        pass

    @classmethod
    @abstractmethod
    def optional_roles(cls) -> List[str]:
        """Return list of optional roles that enhance this task"""
        pass

    @classmethod
    @abstractmethod
    def panels(cls) -> List[str]:
        """Return list of panel keys this task can generate"""
        pass

    @classmethod
    def can_run(cls, available_roles: Set[str]) -> bool:
        """Check if this task can run given available roles"""
        required = set(cls.required_roles())
        return required.issubset(available_roles)

    @abstractmethod
    def execute(self) -> Dict[str, Any]:
        """
        Execute the task and return results

        Returns:
            Dict with keys:
                - estimates: Dict[str, float] - point estimates
                - figures: Dict[str, str] - panel_key -> file_path
                - diagnostics: Dict[str, Any] - diagnostic metrics
        """
        pass

    def get_column(self, role: str) -> pd.Series:
        """Get column for a given role"""
        col_name = self.roles.get(role)
        if col_name is None:
            raise ValueError(f"Role '{role}' not found in roles mapping")
        if col_name not in self.df.columns:
            raise ValueError(f"Column '{col_name}' not found in dataframe")
        return self.df[col_name]

    def has_role(self, role: str) -> bool:
        """Check if a role is available"""
        return role in self.roles and self.roles[role] in self.df.columns
