# backend/inference/objective_detection.py
"""
Objective Detection Algorithm with Hierarchical Structure
Automatically detect objective from column names and data patterns

階層構造:
- Level 0 (Root): causal_inference
- Level 1 (Abstract): human_behavior, economic_transaction, network_diffusion
- Level 2 (Concrete): education, medical, policy, retail, finance, network
"""
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Tuple
import pandas as pd
import numpy as np
from collections import Counter

from backend.inference.objective_hierarchy import (
    get_objective_hierarchy,
    get_concrete_objectives,
    get_abstract_objectives,
    get_objective_path,
    get_causal_structure,
    OBJECTIVE_HIERARCHY
)

logger = logging.getLogger(__name__)

# Load units ontology for objective-specific keywords
CONFIG_DIR = Path(__file__).resolve().parents[2] / "config" / "ontology"
with open(CONFIG_DIR / "units.json") as f:
    UNITS_ONTOLOGY = json.load(f)

# Objective keywords are now loaded from hierarchy
def _get_objective_keywords() -> Dict[str, List[str]]:
    """階層構造から具体objectiveのキーワードを抽出"""
    hierarchy = get_objective_hierarchy()
    return {
        name: node.keywords
        for name, node in hierarchy.items()
        if node.level == 2  # Concrete objectives only
    }

OBJECTIVE_KEYWORDS = _get_objective_keywords()

class ObjectiveDetector:
    """
    Detect objective from dataframe using:
    1. Column name TF-IDF scoring
    2. Regex pattern matching
    3. Data distribution statistics
    """
    
    def __init__(self):
        self.keywords = OBJECTIVE_KEYWORDS
        
    def detect_objective(self, df: pd.DataFrame) -> Dict[str, any]:
        """
        Detect objective with hierarchical structure

        Returns:
            {
                "objective": "education",  # Concrete objective (Level 2)
                "confidence": 0.73,
                "scores": {"education": 0.73, "medical": 0.15, ...},
                "evidence": ["student", "school", "teacher", ...],

                # 階層情報
                "hierarchy": {
                    "concrete": "education",
                    "abstract": "human_behavior",
                    "root": "causal_inference",
                    "path": ["causal_inference", "human_behavior", "education"],
                    "causal_structure": "tutoring/curriculum → learning → test_score/graduation"
                },

                # 抽象レベルのスコア
                "abstract_scores": {
                    "human_behavior": 0.73,
                    "economic_transaction": 0.20,
                    "network_diffusion": 0.07
                }
            }
        """
        logger.info(f"[ObjectiveDetection] Analyzing dataframe for objective")

        # Collect all text from column names and sample values
        text_corpus = self._extract_text_corpus(df)

        # Calculate TF-IDF scores for each concrete objective
        objective_scores = {}
        objective_evidence = {}

        for objective, keywords in self.keywords.items():
            score, evidence = self._calculate_objective_score(text_corpus, keywords)
            objective_scores[objective] = score
            objective_evidence[objective] = evidence

        # Normalize scores
        total_score = sum(objective_scores.values())
        if total_score > 0:
            objective_scores = {k: v / total_score for k, v in objective_scores.items()}

        # Best concrete objective
        best_objective = max(objective_scores, key=objective_scores.get)
        best_score = objective_scores[best_objective]

        # Calculate abstract objective scores by summing children
        abstract_scores = {}
        for abstract in get_abstract_objectives():
            children = [d for d in objective_scores.keys() if OBJECTIVE_HIERARCHY == abstract]
            abstract_scores[abstract] = sum(objective_scores[c] for c in children)

        # Get hierarchy path
        objective_path = get_objective_path(best_objective)
        abstract_objective = OBJECTIVE_HIERARCHY[best_objective].parent

        logger.info(f"[ObjectiveDetection] Detected: {best_objective} (confidence: {best_score:.2f})")
        logger.info(f"[ObjectiveDetection] Hierarchy: {' → '.join(objective_path)}")

        return {
            "objective": best_objective,
            "confidence": best_score,
            "scores": objective_scores,
            "evidence": objective_evidence[best_objective],

            # Hierarchical information
            "hierarchy": {
                "concrete": best_objective,
                "abstract": abstract_objective,
                "root": "causal_inference",
                "path": objective_path,
                "causal_structure": get_causal_structure(best_objective)
            },

            "abstract_scores": abstract_scores
        }
    
    def _extract_text_corpus(self, df: pd.DataFrame) -> List[str]:
        """Extract text from column names and sample values"""
        corpus = []
        
        # Column names
        for col in df.columns:
            corpus.extend(self._tokenize(col))
        
        # Sample values from object/string columns
        for col in df.select_dtypes(include=['object']).columns:
            sample_values = df[col].dropna().head(100).astype(str)
            for val in sample_values:
                corpus.extend(self._tokenize(val))
        
        return corpus
    
    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into lowercase words"""
        # First split on underscores and other separators
        text_lower = text.lower().replace('_', ' ').replace('-', ' ')
        # Then extract words
        tokens = re.findall(r'\b\w+\b', text_lower)
        return tokens
    
    def _calculate_objective_score(
        self, 
        corpus: List[str], 
        keywords: List[str]
    ) -> Tuple[float, List[str]]:
        """
        Calculate TF-IDF style score for objective
        
        Returns:
            (score, matched_keywords)
        """
        corpus_counter = Counter(corpus)
        total_tokens = len(corpus)
        
        score = 0.0
        evidence = []
        
        for keyword in keywords:
            keyword_lower = keyword.lower()
            count = corpus_counter.get(keyword_lower, 0)
            
            if count > 0:
                # Term frequency
                tf = count / total_tokens if total_tokens > 0 else 0
                
                # IDF approximation (keywords are rare, so boost)
                idf = 2.0
                
                # TF-IDF
                score += tf * idf
                evidence.append(keyword)
        
        return score, evidence[:10]  # Top 10 evidence keywords

def detect_objective_from_dataframe(df: pd.DataFrame) -> Dict:
    """
    Convenience function for objective detection
    
    Usage:
        import pandas as pd
        from backend.inference.objective_detection import detect_objective_from_dataframe
        
        df = pd.read_csv("data.csv")
        result = detect_objective_from_dataframe(df)
        
        print("Detected objective:", result["objective"])
        print("Confidence:", result["confidence"])
        print("Evidence:", result["evidence"])
    """
    detector = ObjectiveDetector()
    return detector.detect_objective(df)
