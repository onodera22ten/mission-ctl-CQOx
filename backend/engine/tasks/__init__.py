"""
Task modules for Objective-Lens architecture (Plan3)

Each task module:
- Declares required_roles() and optional_roles()
- Lists available panels()
- Wraps existing estimation/diagnostic logic
"""

from .base import BaseTask
from .estimation import EstimationTask
from .diagnostics import DiagnosticsTask
from .heterogeneity import HeterogeneityTask
from .timevarying import TimeVaryingTask
from .iv import IVTask
from .robustness import RobustnessTask
from .network import NetworkTask
from .policy import PolicyTask
from .transportability import TransportabilityTask
from .counterfactual import CounterfactualTask

__all__ = [
    "BaseTask",
    "EstimationTask",
    "DiagnosticsTask",
    "HeterogeneityTask",
    "TimeVaryingTask",
    "IVTask",
    "RobustnessTask",
    "NetworkTask",
    "PolicyTask",
    "TransportabilityTask",
    "CounterfactualTask",
]
