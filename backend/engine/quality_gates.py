"""
Quality Gates System - NASA/Google Standard

Purpose: Automated quality assessment and Go/Canary/Hold decision logic
Gates:
- Identification (IV F-statistic, Overlap, RD McCrary)
- Precision (SE/ATE ratio, CI width)
- Robustness (Rosenbaum Γ, E-value)
- Decision (ΔProfit, Fairness gap, Constraint compliance)

Output: Go/Canary/Hold recommendation with detailed rationale
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

import numpy as np
import pandas as pd


class GateCategory(str, Enum):
    """Quality gate categories"""
    IDENTIFICATION = "identification"
    PRECISION = "precision"
    ROBUSTNESS = "robustness"
    DECISION = "decision"


class GateStatus(str, Enum):
    """Gate status"""
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    NA = "NA"


@dataclass
class Gate:
    """Individual quality gate"""
    category: GateCategory
    metric: str
    threshold: str  # e.g., ">10", "<0.5"
    s0_value: Optional[float] = None
    s1_value: Optional[float] = None
    status: GateStatus = GateStatus.NA
    reason: str = ""

    def evaluate(self, value: float, scenario: str = "S0") -> GateStatus:
        """
        Evaluate gate against threshold

        Args:
            value: Metric value
            scenario: "S0" or "S1"

        Returns:
            GateStatus
        """
        if scenario == "S0":
            self.s0_value = value
        else:
            self.s1_value = value

        # Parse threshold
        if self.threshold.startswith(">"):
            threshold_val = float(self.threshold[1:])
            self.status = GateStatus.PASS if value > threshold_val else GateStatus.FAIL
            if self.status == GateStatus.FAIL:
                self.reason = f"{value:.3f} ≤ {threshold_val}"
        elif self.threshold.startswith("<"):
            threshold_val = float(self.threshold[1:])
            self.status = GateStatus.PASS if value < threshold_val else GateStatus.FAIL
            if self.status == GateStatus.FAIL:
                self.reason = f"{value:.3f} ≥ {threshold_val}"
        elif self.threshold.startswith("≥"):
            threshold_val = float(self.threshold[1:])
            self.status = GateStatus.PASS if value >= threshold_val else GateStatus.FAIL
        elif self.threshold.startswith("≤"):
            threshold_val = float(self.threshold[1:])
            self.status = GateStatus.PASS if value <= threshold_val else GateStatus.FAIL
        else:
            # Exact match
            threshold_val = float(self.threshold)
            self.status = GateStatus.PASS if abs(value - threshold_val) < 1e-6 else GateStatus.FAIL

        return self.status


@dataclass
class QualityGatesResult:
    """Quality gates evaluation result"""
    gates: List[Gate] = field(default_factory=list)
    pass_count: int = 0
    fail_count: int = 0
    warning_count: int = 0
    na_count: int = 0
    pass_rate: float = 0.0
    decision: str = "HOLD"  # GO, CANARY, HOLD
    rationale: List[str] = field(default_factory=list)

    def add_gate(self, gate: Gate):
        """Add gate to result"""
        self.gates.append(gate)
        self._update_counts()

    def _update_counts(self):
        """Update gate counts and pass rate"""
        self.pass_count = sum(1 for g in self.gates if g.status == GateStatus.PASS)
        self.fail_count = sum(1 for g in self.gates if g.status == GateStatus.FAIL)
        self.warning_count = sum(1 for g in self.gates if g.status == GateStatus.WARNING)
        self.na_count = sum(1 for g in self.gates if g.status == GateStatus.NA)

        total = self.pass_count + self.fail_count + self.warning_count
        self.pass_rate = self.pass_count / total if total > 0 else 0.0

    def to_dict(self) -> Dict:
        """Export to dictionary"""
        return {
            "gates": [
                {
                    "category": g.category.value,
                    "metric": g.metric,
                    "threshold": g.threshold,
                    "s0_value": g.s0_value,
                    "s1_value": g.s1_value,
                    "status": g.status.value,
                    "reason": g.reason
                }
                for g in self.gates
            ],
            "overall": {
                "pass_count": self.pass_count,
                "fail_count": self.fail_count,
                "warning_count": self.warning_count,
                "pass_rate": self.pass_rate,
                "decision": self.decision
            },
            "rationale": self.rationale
        }


class QualityGatesSystem:
    """
    Quality Gates System

    Evaluates identification, precision, robustness, and decision gates
    """

    def __init__(self):
        """Initialize with default gate definitions"""
        self.gates: List[Gate] = [
            # Identification gates
            Gate(GateCategory.IDENTIFICATION, "iv_f_statistic", ">10"),
            Gate(GateCategory.IDENTIFICATION, "overlap_rate", ">0.90"),
            Gate(GateCategory.IDENTIFICATION, "rd_mccrary_p", ">0.05"),

            # Precision gates
            Gate(GateCategory.PRECISION, "se_ate_ratio", "<0.5"),
            Gate(GateCategory.PRECISION, "ci_width", "<2.0"),

            # Robustness gates
            Gate(GateCategory.ROBUSTNESS, "rosenbaum_gamma", ">1.2"),
            Gate(GateCategory.ROBUSTNESS, "evalue", ">2.0"),

            # Decision gates (evaluated per scenario)
            Gate(GateCategory.DECISION, "delta_profit", ">0"),
            Gate(GateCategory.DECISION, "fairness_gap", "≤0.03"),
            Gate(GateCategory.DECISION, "budget_compliance", "≤1.0"),
        ]

    def evaluate(
        self,
        metrics_s0: Dict[str, float],
        metrics_s1: Optional[Dict[str, float]] = None,
        delta_profit: Optional[float] = None,
        constraints: Optional[Dict[str, float]] = None
    ) -> QualityGatesResult:
        """
        Evaluate all quality gates

        Args:
            metrics_s0: S0 (baseline) metrics
            metrics_s1: S1 (scenario) metrics (optional)
            delta_profit: ΔProfit for decision gate
            constraints: Constraint compliance metrics

        Returns:
            QualityGatesResult with Go/Canary/Hold decision
        """
        result = QualityGatesResult()

        # Evaluate S0 gates
        for gate in self.gates:
            metric_key = gate.metric

            # Skip decision gates for S0
            if gate.category == GateCategory.DECISION:
                continue

            if metric_key in metrics_s0:
                gate.evaluate(metrics_s0[metric_key], scenario="S0")
                result.add_gate(gate)

        # Evaluate S1 gates (if provided)
        if metrics_s1:
            for gate in self.gates:
                metric_key = gate.metric

                # Skip decision gates (handled separately)
                if gate.category == GateCategory.DECISION:
                    continue

                if metric_key in metrics_s1:
                    gate.evaluate(metrics_s1[metric_key], scenario="S1")

        # Evaluate decision gates
        if delta_profit is not None:
            profit_gate = Gate(GateCategory.DECISION, "delta_profit", ">0")
            profit_gate.evaluate(delta_profit, scenario="S1")
            result.add_gate(profit_gate)

        if constraints:
            # Fairness gap
            if "fairness_gap" in constraints:
                fairness_gate = Gate(GateCategory.DECISION, "fairness_gap", "≤0.03")
                fairness_gate.evaluate(constraints["fairness_gap"], scenario="S1")
                result.add_gate(fairness_gate)

            # Budget compliance (utilized / cap)
            if "budget_utilization" in constraints:
                budget_gate = Gate(GateCategory.DECISION, "budget_compliance", "≤1.0")
                budget_gate.evaluate(constraints["budget_utilization"], scenario="S1")
                result.add_gate(budget_gate)

        # Make Go/Canary/Hold decision
        result.decision, result.rationale = self._make_decision(result)

        return result

    def _make_decision(self, result: QualityGatesResult) -> tuple[str, List[str]]:
        """
        Make Go/Canary/Hold decision based on gate results

        Logic:
        - GO: pass_rate ≥ 70% AND ΔProfit > 0 AND all constraints satisfied
        - CANARY: 50% ≤ pass_rate < 70% AND ΔProfit > 0
        - HOLD: pass_rate < 50% OR ΔProfit ≤ 0 OR constraint violation

        Args:
            result: QualityGatesResult

        Returns:
            Tuple of (decision, rationale)
        """
        rationale = []

        # Check ΔProfit
        profit_gates = [g for g in result.gates if g.metric == "delta_profit"]
        profit_positive = all(g.status == GateStatus.PASS for g in profit_gates)

        if not profit_positive:
            return "HOLD", ["ΔProfit ≤ 0: No business value"]

        # Check constraints
        constraint_gates = [
            g for g in result.gates
            if g.category == GateCategory.DECISION and g.metric != "delta_profit"
        ]
        constraints_satisfied = all(g.status == GateStatus.PASS for g in constraint_gates)

        if not constraints_satisfied:
            failed = [g.metric for g in constraint_gates if g.status == GateStatus.FAIL]
            return "HOLD", [f"Constraint violations: {', '.join(failed)}"]

        # Check pass rate
        pass_rate = result.pass_rate

        if pass_rate >= 0.70:
            rationale.append(f"Quality gate pass rate: {pass_rate:.1%} (≥70%)")
            rationale.append(f"ΔProfit: Positive")
            rationale.append(f"Constraints: All satisfied")
            return "GO", rationale

        elif pass_rate >= 0.50:
            rationale.append(f"Quality gate pass rate: {pass_rate:.1%} (50-70%)")
            rationale.append(f"ΔProfit: Positive")
            rationale.append(f"Recommendation: Gradual rollout with monitoring")
            return "CANARY", rationale

        else:
            failed_gates = [g.metric for g in result.gates if g.status == GateStatus.FAIL]
            rationale.append(f"Quality gate pass rate: {pass_rate:.1%} (<50%)")
            rationale.append(f"Failed gates: {', '.join(failed_gates[:5])}")
            return "HOLD", rationale


def evaluate_quality_gates(
    estimation_results: Dict,
    delta_profit: float,
    constraints: Optional[Dict[str, float]] = None
) -> Dict:
    """
    Convenience function to evaluate quality gates from estimation results

    Args:
        estimation_results: Dictionary with estimation metrics
        delta_profit: ΔProfit value
        constraints: Constraint compliance metrics

    Returns:
        Quality gates evaluation dictionary
    """
    system = QualityGatesSystem()

    # Extract metrics from estimation results
    metrics_s0 = {
        "overlap_rate": estimation_results.get("overlap", {}).get("rate", 0.0),
        "se_ate_ratio": estimation_results.get("precision", {}).get("se_ate_ratio", 0.0),
        "ci_width": estimation_results.get("precision", {}).get("ci_width", 0.0),
        "rosenbaum_gamma": estimation_results.get("sensitivity", {}).get("gamma", 0.0),
        "evalue": estimation_results.get("sensitivity", {}).get("evalue", 0.0),
    }

    # Add IV F-statistic if available
    if "iv" in estimation_results:
        metrics_s0["iv_f_statistic"] = estimation_results["iv"].get("f_statistic", 0.0)

    # Add RD McCrary if available
    if "rd" in estimation_results:
        metrics_s0["rd_mccrary_p"] = estimation_results["rd"].get("mccrary_p", 0.0)

    result = system.evaluate(
        metrics_s0=metrics_s0,
        delta_profit=delta_profit,
        constraints=constraints
    )

    return result.to_dict()
