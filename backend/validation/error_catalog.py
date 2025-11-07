# backend/validation/error_catalog.py
"""
Error Catalog (Col1 Specification)

Standardized error codes with actionable suggestions:
- E-ROLE-001: Missing required role
- E-ROLE-002: Ambiguous role mapping
- E-ROLE-003: Invalid data type
- E-ROLE-004: Insufficient data quality
- E-ROLE-005: Structural violation
- E-ROLE-006: Temporal inconsistency
- E-ROLE-007: Identifier issues
"""
from __future__ import annotations
import pandas as pd
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from enum import Enum


class ErrorSeverity(Enum):
    CRITICAL = "critical"  # Blocks analysis
    ERROR = "error"        # Should fix
    WARNING = "warning"    # May affect results
    INFO = "info"          # FYI


@dataclass
class ErrorCode:
    """Standardized error with code, message, and fix suggestions"""
    code: str
    severity: ErrorSeverity
    message: str
    details: Dict[str, Any]
    suggestions: List[str]
    documentation_url: str


class ErrorCatalog:
    """
    Centralized error catalog with actionable suggestions

    All errors follow format: E-ROLE-XXX
    """

    @staticmethod
    def E_ROLE_001(missing_roles: List[str]) -> ErrorCode:
        """Missing required role(s)"""
        return ErrorCode(
            code="E-ROLE-001",
            severity=ErrorSeverity.CRITICAL,
            message=f"Missing required role(s): {', '.join(missing_roles)}",
            details={"missing_roles": missing_roles},
            suggestions=[
                f"Map column to '{role}' role in the UI" for role in missing_roles
            ] + [
                "If column doesn't exist, add it to your dataset",
                "For unit_id: use patient_id, user_id, account_id, or similar unique identifier",
                "For treatment: use treatment, intervention, policy, exposure column",
                "For outcome: use y, outcome, result, score, conversion column",
            ],
            documentation_url="https://docs.cqox.ai/errors/E-ROLE-001"
        )

    @staticmethod
    def E_ROLE_002(role: str, candidates: List[Dict[str, Any]]) -> ErrorCode:
        """Ambiguous role mapping - multiple high-confidence candidates"""
        candidate_names = [c["column"] for c in candidates]
        return ErrorCode(
            code="E-ROLE-002",
            severity=ErrorSeverity.WARNING,
            message=f"Ambiguous mapping for '{role}': multiple candidates with similar confidence",
            details={
                "role": role,
                "candidates": candidates,
            },
            suggestions=[
                f"Review candidates: {', '.join(candidate_names)}",
                "Manually select the correct column in the mapping UI",
                "Consider renaming columns to match standard conventions",
                f"If unsure, use the column with highest confidence: {candidates[0]['column']}",
            ],
            documentation_url="https://docs.cqox.ai/errors/E-ROLE-002"
        )

    @staticmethod
    def E_ROLE_003(column: str, expected_type: str, actual_type: str) -> ErrorCode:
        """Invalid data type for role"""
        return ErrorCode(
            code="E-ROLE-003",
            severity=ErrorSeverity.ERROR,
            message=f"Column '{column}' has type '{actual_type}' but expected '{expected_type}'",
            details={
                "column": column,
                "expected_type": expected_type,
                "actual_type": actual_type,
            },
            suggestions=[
                f"Convert '{column}' to {expected_type}",
                f"For numeric: use pd.to_numeric(df['{column}'], errors='coerce')",
                f"For datetime: use pd.to_datetime(df['{column}'])",
                "Check for non-numeric characters or invalid formats",
                "Consider creating a new derived column with correct type",
            ],
            documentation_url="https://docs.cqox.ai/errors/E-ROLE-003"
        )

    @staticmethod
    def E_ROLE_004(column: str, issue: str, quality_metric: float, threshold: float) -> ErrorCode:
        """Insufficient data quality"""
        return ErrorCode(
            code="E-ROLE-004",
            severity=ErrorSeverity.WARNING,
            message=f"Column '{column}' has insufficient quality: {issue}",
            details={
                "column": column,
                "issue": issue,
                "quality_metric": quality_metric,
                "threshold": threshold,
            },
            suggestions=[
                f"Current {issue}: {quality_metric:.2%}, required: <{threshold:.2%}",
                "Options:",
                "  1. Remove rows with missing/invalid values",
                "  2. Impute missing values (mean, median, or model-based)",
                "  3. Use a different column for this role",
                "  4. Collect more complete data",
            ] + ([
                f"For missing data: df['{column}'].fillna(df['{column}'].median())",
                "For outliers: use winsorization or trimming",
            ] if "missing" in issue.lower() else []),
            documentation_url="https://docs.cqox.ai/errors/E-ROLE-004"
        )

    @staticmethod
    def E_ROLE_005(violation: str, details: Dict[str, Any]) -> ErrorCode:
        """Structural violation (uniqueness, ordering, relationships)"""
        return ErrorCode(
            code="E-ROLE-005",
            severity=ErrorSeverity.ERROR,
            message=f"Structural violation: {violation}",
            details=details,
            suggestions=[
                "Check data structure requirements:",
                "  - unit_id should be unique per row (or unique within time)",
                "  - time should be ordered chronologically",
                "  - treatment should be binary (0/1) or categorical",
                "  - outcome should be numeric",
                "If duplicates exist, consider:",
                "  - Aggregating rows (mean, sum)",
                "  - Keeping only first/last occurrence",
                "  - Adding a sequence number to unit_id",
            ] + (
                ["Use df.drop_duplicates(subset=['unit_id', 'time'])"]
                if "duplicate" in violation.lower()
                else []
            ),
            documentation_url="https://docs.cqox.ai/errors/E-ROLE-005"
        )

    @staticmethod
    def E_ROLE_006(time_column: str, issue: str) -> ErrorCode:
        """Temporal inconsistency"""
        return ErrorCode(
            code="E-ROLE-006",
            severity=ErrorSeverity.WARNING,
            message=f"Temporal inconsistency in '{time_column}': {issue}",
            details={
                "column": time_column,
                "issue": issue,
            },
            suggestions=[
                "Common temporal issues:",
                "  - Future dates (beyond today)",
                "  - Dates before plausible start (e.g., 1900)",
                "  - Irregular gaps in time series",
                "  - Treatment assigned before observation period",
                "Solutions:",
                f"  1. Filter invalid dates: df = df[df['{time_column}'] <= pd.Timestamp.now()]",
                "  2. Align time to treatment assignment date",
                "  3. Fill gaps with forward-fill or interpolation",
                "  4. Check for immortal time bias",
            ],
            documentation_url="https://docs.cqox.ai/errors/E-ROLE-006"
        )

    @staticmethod
    def E_ROLE_007(unit_id_column: str, uniqueness: float, threshold: float = 0.8) -> ErrorCode:
        """Identifier issues (low uniqueness, invalid format)"""
        return ErrorCode(
            code="E-ROLE-007",
            severity=ErrorSeverity.WARNING,
            message=f"Identifier '{unit_id_column}' has low uniqueness: {uniqueness:.2%}",
            details={
                "column": unit_id_column,
                "uniqueness": uniqueness,
                "threshold": threshold,
            },
            suggestions=[
                f"Unit ID should be highly unique (>{threshold:.0%}), found {uniqueness:.2%}",
                "This suggests:",
                "  - Wrong column selected for unit_id",
                "  - Multiple observations per unit (panel data)",
                "  - Duplicate entries",
                "Fixes:",
                "  1. Use a different column with higher uniqueness",
                f"  2. Create composite key: df['unit_id'] = df['{unit_id_column}'] + '_' + df['time'].astype(str)",
                "  3. If panel data, ensure time column is properly mapped",
                "  4. Remove duplicates if they're errors",
            ],
            documentation_url="https://docs.cqox.ai/errors/E-ROLE-007"
        )


def validate_roles_and_generate_errors(
    df,
    mapping: Dict[str, str],
    role_spec: Dict[str, Any]
) -> List[ErrorCode]:
    """
    Validate role mappings and generate error codes

    Args:
        df: DataFrame
        mapping: Role to column mapping
        role_spec: Role specifications from ontology

    Returns:
        List of ErrorCode objects
    """
    errors = []

    # E-ROLE-001: Check required roles
    required_roles = ["unit_id", "treatment", "y"]
    missing = [r for r in required_roles if r not in mapping or not mapping[r]]
    if missing:
        errors.append(ErrorCatalog.E_ROLE_001(missing))

    # E-ROLE-003: Check data types
    type_mapping = {
        "unit_id": ["object", "int64", "string"],
        "y": ["float64", "int64"],
        "treatment": ["int64", "float64", "object"],
        "time": ["datetime64", "int64", "float64"],
    }

    for role, expected_types in type_mapping.items():
        if role in mapping and mapping[role]:
            col = mapping[role]
            if col in df.columns:
                actual_type = str(df[col].dtype)
                if not any(et in actual_type for et in expected_types):
                    errors.append(ErrorCatalog.E_ROLE_003(
                        col, "/".join(expected_types), actual_type
                    ))

    # E-ROLE-004: Check data quality
    for role, col in mapping.items():
        if col and col in df.columns:
            missing_rate = df[col].isna().mean()
            if missing_rate > 0.3:
                errors.append(ErrorCatalog.E_ROLE_004(
                    col, "excessive missing data", missing_rate, 0.3
                ))

    # E-ROLE-005: Check structural constraints
    if "unit_id" in mapping and mapping["unit_id"]:
        unit_col = mapping["unit_id"]
        if unit_col in df.columns:
            if "time" not in mapping or not mapping["time"]:
                # Cross-sectional: unit_id should be unique
                n_unique = df[unit_col].nunique()
                n_total = len(df)
                if n_unique < n_total:
                    errors.append(ErrorCatalog.E_ROLE_005(
                        "Duplicate unit IDs in cross-sectional data",
                        {"n_unique": n_unique, "n_total": n_total, "duplicates": n_total - n_unique}
                    ))

    # E-ROLE-006: Check temporal consistency
    if "time" in mapping and mapping["time"]:
        time_col = mapping["time"]
        if time_col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[time_col]):
                # Check for future dates
                now = pd.Timestamp.now()
                future_dates = (df[time_col] > now).sum()
                if future_dates > 0:
                    errors.append(ErrorCatalog.E_ROLE_006(
                        time_col, f"{future_dates} future dates detected"
                    ))

    # E-ROLE-007: Check identifier uniqueness
    if "unit_id" in mapping and mapping["unit_id"]:
        unit_col = mapping["unit_id"]
        if unit_col in df.columns:
            uniqueness = df[unit_col].nunique() / len(df)
            if uniqueness < 0.5:  # Very low uniqueness suggests wrong column
                errors.append(ErrorCatalog.E_ROLE_007(unit_col, uniqueness))

    return errors


def format_errors_for_ui(errors: List[ErrorCode]) -> Dict[str, Any]:
    """Format errors for frontend display"""
    return {
        "has_errors": len(errors) > 0,
        "error_count": len(errors),
        "critical_count": sum(1 for e in errors if e.severity == ErrorSeverity.CRITICAL),
        "errors": [
            {
                "code": e.code,
                "severity": e.severity.value,
                "message": e.message,
                "details": e.details,
                "suggestions": e.suggestions,
                "docs": e.documentation_url,
            }
            for e in errors
        ],
    }
