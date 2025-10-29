# backend/inference/role_inference.py
"""
Automatic Column Role Inference
Multi-score algorithm combining:
1. Name matching (50%)
2. Data type (20%)
3. Statistical features (20%)
4. Coherence with other columns (10%)
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# Load ontology dictionaries
CONFIG_DIR = Path(__file__).resolve().parents[2] / "config" / "ontology"
with open(CONFIG_DIR / "columns.json") as f:
    COLUMN_ONTOLOGY = json.load(f)
with open(CONFIG_DIR / "validators.json") as f:
    VALIDATORS = json.load(f)

class RoleInferenceEngine:
    """
    Automatic role inference engine
    
    Score calculation:
    - Name match: 50% (exact: 50, partial: 25, no match: 0)
    - Type match: 20% (correct dtype: 20, convertible: 10, wrong: 0)
    - Statistics: 20% (meets validators: 20, partial: 10, fails: 0)
    - Coherence: 10% (consistent with other inferred roles: 10, neutral: 5, conflict: 0)
    """
    
    def __init__(self):
        self.ontology = COLUMN_ONTOLOGY
        self.validators = VALIDATORS
        
    def infer_roles(self, df: pd.DataFrame, min_confidence: float = 0.3) -> Dict[str, any]:
        """
        Infer column roles with confidence scores
        
        Args:
            df: Input dataframe
            min_confidence: Minimum confidence threshold (0.0-1.0)
            
        Returns:
            {
                "mapping": {"y": "revenue", "treatment": "campaign", ...},
                "candidates": {
                    "y": [
                        {"column": "revenue", "confidence": 0.95, "reasons": [...]},
                        {"column": "profit", "confidence": 0.72, "reasons": [...]}
                    ],
                    ...
                },
                "required_missing": ["unit_id"],  # if any required roles have no candidates
                "confidence": 0.87  # overall confidence
            }
        """
        logger.info(f"[RoleInference] Analyzing {len(df.columns)} columns from dataframe")
        
        # Calculate scores for all (role, column) pairs
        scores = {}
        for role_name, role_spec in self.ontology.items():
            scores[role_name] = []
            for col in df.columns:
                score, reasons = self._calculate_score(role_name, col, df)
                if score >= min_confidence:
                    scores[role_name].append({
                        "column": col,
                        "confidence": score,
                        "reasons": reasons
                    })
            # Sort by confidence descending
            scores[role_name] = sorted(scores[role_name], key=lambda x: x["confidence"], reverse=True)
        
        # Select best mapping (greedy assignment)
        mapping = {}
        used_columns = set()
        
        # Priority order: required roles first, sorted by priority
        roles_by_priority = sorted(
            self.ontology.items(),
            key=lambda x: (-x[1].get("required", False), -x[1].get("priority", 0))
        )
        
        for role_name, role_spec in roles_by_priority:
            candidates = [c for c in scores[role_name] if c["column"] not in used_columns]
            if candidates:
                best = candidates[0]
                mapping[role_name] = best["column"]
                used_columns.add(best["column"])
                logger.info(f"[RoleInference] {role_name} -> {best['column']} (confidence: {best['confidence']:.2f})")
        
        # Check for missing required roles
        required_missing = []
        for role_name, role_spec in self.ontology.items():
            if role_spec.get("required", False) and role_name not in mapping:
                required_missing.append(role_name)
        
        # Calculate overall confidence
        if mapping:
            confidences = [scores[role][0]["confidence"] for role in mapping if scores[role]]
            overall_confidence = np.mean(confidences) if confidences else 0.0
        else:
            overall_confidence = 0.0
        
        return {
            "mapping": mapping,
            "candidates": scores,
            "required_missing": required_missing,
            "confidence": overall_confidence
        }
    
    def _calculate_score(
        self, 
        role_name: str, 
        column: str, 
        df: pd.DataFrame
    ) -> Tuple[float, List[str]]:
        """
        Calculate score for (role, column) pair
        
        Returns:
            (score, reasons) where score is 0.0-1.0
        """
        reasons = []
        total_score = 0.0
        
        role_spec = self.ontology[role_name]
        col_data = df[column]
        
        # 1. Name matching (50%)
        name_score = self._score_name_match(role_spec, column)
        total_score += name_score * 0.5
        if name_score > 0.7:
            reasons.append(f"Name match: {name_score:.0%}")
        
        # 2. Data type (20%)
        type_score = self._score_dtype_match(role_name, col_data)
        total_score += type_score * 0.2
        if type_score > 0.7:
            reasons.append(f"Type match: {type_score:.0%}")
        
        # 3. Statistical features (20%)
        stats_score = self._score_statistics(role_name, col_data, df)
        total_score += stats_score * 0.2
        if stats_score > 0.7:
            reasons.append(f"Stats match: {stats_score:.0%}")
        
        # 4. Coherence (10%) - placeholder for now
        coherence_score = 0.5  # neutral
        total_score += coherence_score * 0.1
        
        return total_score, reasons
    
    def _score_name_match(self, role_spec: Dict, column: str) -> float:
        """Score name similarity"""
        col_lower = column.lower().strip()
        synonyms = role_spec.get("synonyms", [])
        
        # Exact match
        if col_lower in [s.lower() for s in synonyms]:
            return 1.0
        
        # Partial match (contains)
        for syn in synonyms:
            syn_lower = syn.lower()
            if syn_lower in col_lower or col_lower in syn_lower:
                return 0.7
        
        # Prefix match for covariates (x_*)
        if role_spec.get("description", "").startswith("Covariate"):
            if col_lower.startswith("x_") or col_lower.startswith("x"):
                return 0.6
        
        return 0.0
    
    def _score_dtype_match(self, role_name: str, col_data: pd.Series) -> float:
        """Score data type compatibility"""
        validator = self.validators.get(role_name, {})
        expected_dtypes = validator.get("dtype", [])
        
        if not expected_dtypes:
            return 0.5  # neutral
        
        actual_dtype = str(col_data.dtype)
        
        # Exact match
        for expected in expected_dtypes:
            if expected in actual_dtype:
                return 1.0
        
        # Convertible
        if "int" in actual_dtype or "float" in actual_dtype:
            if "int64" in expected_dtypes or "float64" in expected_dtypes:
                return 0.8
        
        if "object" in actual_dtype:
            if "object" in expected_dtypes or "string" in expected_dtypes:
                return 0.8
        
        return 0.2
    
    def _score_statistics(self, role_name: str, col_data: pd.Series, df: pd.DataFrame) -> float:
        """Score statistical properties"""
        validator = self.validators.get(role_name, {})
        score = 0.0
        checks = 0
        
        # Missing rate
        if "missing_rate" in validator:
            missing_rate = col_data.isna().sum() / len(col_data)
            threshold_str = validator["missing_rate"]
            threshold = float(threshold_str.split()[-1])
            if "<" in threshold_str:
                score += 1.0 if missing_rate < threshold else 0.0
            checks += 1
        
        # Uniqueness (for unit_id)
        if "uniqueness" in validator:
            uniqueness = col_data.nunique() / len(col_data)
            threshold_str = validator["uniqueness"]
            threshold = float(threshold_str.split()[-1])
            if ">" in threshold_str:
                score += 1.0 if uniqueness > threshold else 0.5
            checks += 1
        
        # Cardinality (for treatment)
        if "cardinality" in validator:
            cardinality = col_data.nunique()
            threshold_str = validator["cardinality"]
            threshold = int(threshold_str.split()[-1])
            if "<" in threshold_str:
                score += 1.0 if cardinality < threshold else 0.3
            checks += 1
        
        # Variance (for outcome)
        if "variance" in validator:
            try:
                variance = col_data.var()
                if variance > 0:
                    score += 1.0
                checks += 1
            except:
                pass
        
        # Range checks (for cost, weight)
        if "range" in validator:
            try:
                min_val = col_data.min()
                if ">= 0" in validator["range"][0]:
                    score += 1.0 if min_val >= 0 else 0.0
                    checks += 1
            except:
                pass
        
        return score / checks if checks > 0 else 0.5

def infer_roles_from_dataframe(df: pd.DataFrame, min_confidence: float = 0.3) -> Dict:
    """
    Convenience function for role inference
    
    Usage:
        import pandas as pd
        from backend.inference.role_inference import infer_roles_from_dataframe
        
        df = pd.read_csv("data.csv")
        result = infer_roles_from_dataframe(df)
        
        if result["required_missing"]:
            print("Missing required roles:", result["required_missing"])
        else:
            print("Suggested mapping:", result["mapping"])
            print("Confidence:", result["confidence"])
    """
    engine = RoleInferenceEngine()
    return engine.infer_roles(df, min_confidence)
