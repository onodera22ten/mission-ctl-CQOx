# backend/inference/column_selection.py
"""
Automatic Column Selection for Causal Inference
Intelligently detects which columns should map to y, treatment, unit_id, time, and covariates
"""
from __future__ import annotations
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import re


class ColumnSelector:
    """Automatic column role detection based on heuristics"""

    # Keyword patterns for each role
    OUTCOME_KEYWORDS = [
        'outcome', 'result', 'y', 'target', 'score', 'value', 'response',
        'sales', 'revenue', 'profit', 'spend', 'days', 'recovery', 'test',
        'grade', 'performance', 'return', 'yield'
    ]

    TREATMENT_KEYWORDS = [
        'treatment', 'treat', 'intervention', 'policy', 'program', 'drug',
        'therapy', 'condition', 'group', 'arm', 'dose', 'campaign', 'promo',
        'portfolio', 'strategy'
    ]

    UNIT_ID_KEYWORDS = [
        'id', 'identifier', 'patient', 'customer', 'student', 'account',
        'user', 'subject', 'person', 'unit', 'entity', 'node', 'region'
    ]

    TIME_KEYWORDS = [
        'time', 'date', 'year', 'month', 'week', 'day', 'period', 'quarter',
        'timestamp', 'datetime', 'when', 'cohort'
    ]

    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.column_scores = self._compute_column_scores()

    def _compute_column_scores(self) -> Dict[str, Dict[str, float]]:
        """Compute scores for each column for each role"""
        scores = {}

        for col in self.df.columns:
            scores[col] = {
                'outcome': self._score_outcome(col),
                'treatment': self._score_treatment(col),
                'unit_id': self._score_unit_id(col),
                'time': self._score_time(col),
            }

        return scores

    def _keyword_match_score(self, col_name: str, keywords: List[str]) -> float:
        """Score based on keyword matching"""
        col_lower = col_name.lower()
        score = 0.0

        for keyword in keywords:
            if keyword in col_lower:
                # Exact match gets higher score
                if col_lower == keyword:
                    score += 1.0
                # Contains keyword gets partial score
                else:
                    score += 0.5

        return min(score, 1.0)  # Cap at 1.0

    def _score_outcome(self, col: str) -> float:
        """Score likelihood of being outcome variable"""
        score = 0.0

        # Keyword matching
        score += self._keyword_match_score(col, self.OUTCOME_KEYWORDS) * 0.6

        # Numeric columns are more likely to be outcomes
        if pd.api.types.is_numeric_dtype(self.df[col]):
            score += 0.3

        # Continuous variables (high cardinality) more likely
        n_unique = self.df[col].nunique()
        if n_unique > 10:
            score += 0.1

        return score

    def _score_treatment(self, col: str) -> float:
        """Score likelihood of being treatment variable"""
        score = 0.0

        # Keyword matching
        score += self._keyword_match_score(col, self.TREATMENT_KEYWORDS) * 0.6

        # Binary or low-cardinality variables are more likely
        n_unique = self.df[col].nunique()
        if n_unique == 2:
            score += 0.3
        elif 2 < n_unique <= 5:
            score += 0.2

        # Categorical data type
        if self.df[col].dtype == 'object' or self.df[col].dtype.name == 'category':
            score += 0.1

        return score

    def _score_unit_id(self, col: str) -> float:
        """Score likelihood of being unit identifier"""
        score = 0.0

        # Keyword matching
        score += self._keyword_match_score(col, self.UNIT_ID_KEYWORDS) * 0.5

        # High uniqueness (close to number of rows)
        uniqueness = self.df[col].nunique() / len(self.df)
        if uniqueness > 0.9:
            score += 0.4
        elif uniqueness > 0.7:
            score += 0.2

        # Integer or string type
        if pd.api.types.is_integer_dtype(self.df[col]) or self.df[col].dtype == 'object':
            score += 0.1

        return score

    def _score_time(self, col: str) -> float:
        """Score likelihood of being time variable"""
        score = 0.0

        # Keyword matching
        score += self._keyword_match_score(col, self.TIME_KEYWORDS) * 0.5

        # Datetime type
        if pd.api.types.is_datetime64_any_dtype(self.df[col]):
            score += 0.4

        # Integer type with reasonable range (could be year)
        if pd.api.types.is_integer_dtype(self.df[col]):
            min_val = self.df[col].min()
            max_val = self.df[col].max()
            # Year-like range (1900-2100)
            if 1900 <= min_val <= 2100 and 1900 <= max_val <= 2100:
                score += 0.3

        # Sorted values suggest time
        if self.df[col].is_monotonic_increasing or self.df[col].is_monotonic_decreasing:
            score += 0.1

        return score

    def select_columns(self, confidence_threshold: float = 0.3) -> Dict[str, any]:
        """
        Automatically select columns for each role

        Returns:
            Dict with keys: y, treatment, unit_id, time, covariates, confidence, alternatives
        """
        result = {
            'y': None,
            'treatment': None,
            'unit_id': None,
            'time': None,
            'covariates': [],
            'confidence': {},
            'alternatives': {}
        }

        # Select best column for each role
        for role in ['outcome', 'treatment', 'unit_id', 'time']:
            ranked = sorted(
                [(col, scores[role]) for col, scores in self.column_scores.items()],
                key=lambda x: x[1],
                reverse=True
            )

            # Get top candidate
            if ranked and ranked[0][1] >= confidence_threshold:
                col, score = ranked[0]

                # Map to output keys
                key_mapping = {
                    'outcome': 'y',
                    'treatment': 'treatment',
                    'unit_id': 'unit_id',
                    'time': 'time'
                }
                output_key = key_mapping[role]

                result[output_key] = col
                result['confidence'][output_key] = float(score)

                # Store alternatives (top 3)
                result['alternatives'][output_key] = [
                    {'column': c, 'score': float(s)}
                    for c, s in ranked[1:4] if s > 0.1
                ]

        # Identify covariates (everything else)
        assigned_cols = {result['y'], result['treatment'], result['unit_id'], result['time']}
        result['covariates'] = [
            col for col in self.df.columns
            if col not in assigned_cols and col is not None
        ]

        return result

    def get_mapping_for_api(self) -> Dict[str, str]:
        """Get mapping in the format expected by /api/analyze/comprehensive"""
        selection = self.select_columns()

        mapping = {}
        if selection['y']:
            mapping['y'] = selection['y']
        if selection['treatment']:
            mapping['treatment'] = selection['treatment']
        if selection['unit_id']:
            mapping['unit_id'] = selection['unit_id']
        if selection['time']:
            mapping['time'] = selection['time']

        return mapping

    def explain_selection(self) -> str:
        """Human-readable explanation of column selection"""
        selection = self.select_columns()

        lines = ["=== Automatic Column Selection ===\n"]

        for role in ['y', 'treatment', 'unit_id', 'time']:
            col = selection[role]
            if col:
                confidence = selection['confidence'][role]
                lines.append(f"{role:12} → {col:20} (confidence: {confidence:.2f})")

                # Show alternatives
                alternatives = selection['alternatives'].get(role, [])
                if alternatives:
                    alt_str = ", ".join([f"{a['column']} ({a['score']:.2f})" for a in alternatives[:2]])
                    lines.append(f"{'':12}   alternatives: {alt_str}")
            else:
                lines.append(f"{role:12} → NOT DETECTED")

        lines.append(f"\nCovariates ({len(selection['covariates'])}): {', '.join(selection['covariates'][:5])}")
        if len(selection['covariates']) > 5:
            lines.append(f"             ... and {len(selection['covariates']) - 5} more")

        return "\n".join(lines)


def auto_select_columns(df: pd.DataFrame, confidence_threshold: float = 0.3) -> Dict[str, any]:
    """
    Convenience function to automatically select columns

    Args:
        df: Input dataframe
        confidence_threshold: Minimum confidence score to assign a role (default: 0.3)

    Returns:
        Dict with selected columns and confidence scores
    """
    selector = ColumnSelector(df)
    return selector.select_columns(confidence_threshold)


def suggest_mapping(csv_path: str) -> Dict[str, str]:
    """
    Load CSV and suggest mapping for API

    Args:
        csv_path: Path to CSV file

    Returns:
        Mapping dict ready for /api/analyze/comprehensive
    """
    df = pd.read_csv(csv_path)
    selector = ColumnSelector(df)
    return selector.get_mapping_for_api()


# CLI interface for testing
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python column_selection.py <csv_path>")
        sys.exit(1)

    csv_path = sys.argv[1]
    df = pd.read_csv(csv_path)

    selector = ColumnSelector(df)
    print(selector.explain_selection())
    print("\nAPI Mapping:")
    print(selector.get_mapping_for_api())
