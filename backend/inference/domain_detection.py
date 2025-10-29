# backend/inference/domain_detection.py
"""
Domain Detection Algorithm with Hierarchical Structure
Automatically detect domain from column names and data patterns

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

from backend.inference.domain_hierarchy import (
    get_domain_hierarchy,
    get_concrete_domains,
    get_abstract_domains,
    get_domain_path,
    get_causal_structure,
    DOMAIN_HIERARCHY
)

logger = logging.getLogger(__name__)

# Load units ontology for domain-specific keywords
CONFIG_DIR = Path(__file__).resolve().parents[2] / "config" / "ontology"
with open(CONFIG_DIR / "units.json") as f:
    UNITS_ONTOLOGY = json.load(f)

# Domain keywords are now loaded from hierarchy
def _get_domain_keywords() -> Dict[str, List[str]]:
    """階層構造から具体ドメインのキーワードを抽出"""
    hierarchy = get_domain_hierarchy()
    return {
        name: node.keywords
        for name, node in hierarchy.items()
        if node.level == 2  # Concrete domains only
    }

DOMAIN_KEYWORDS = _get_domain_keywords()

class DomainDetector:
    """
    Detect domain from dataframe using:
    1. Column name TF-IDF scoring
    2. Regex pattern matching
    3. Data distribution statistics
    """
    
    def __init__(self):
        self.keywords = DOMAIN_KEYWORDS
        
    def detect_domain(self, df: pd.DataFrame) -> Dict[str, any]:
        """
        Detect domain with hierarchical structure

        Returns:
            {
                "domain": "education",  # Concrete domain (Level 2)
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
        logger.info(f"[DomainDetection] Analyzing dataframe for domain")

        # Collect all text from column names and sample values
        text_corpus = self._extract_text_corpus(df)

        # Calculate TF-IDF scores for each concrete domain
        domain_scores = {}
        domain_evidence = {}

        for domain, keywords in self.keywords.items():
            score, evidence = self._calculate_domain_score(text_corpus, keywords)
            domain_scores[domain] = score
            domain_evidence[domain] = evidence

        # Normalize scores
        total_score = sum(domain_scores.values())
        if total_score > 0:
            domain_scores = {k: v / total_score for k, v in domain_scores.items()}

        # Best concrete domain
        best_domain = max(domain_scores, key=domain_scores.get)
        best_score = domain_scores[best_domain]

        # Calculate abstract domain scores by summing children
        abstract_scores = {}
        for abstract in get_abstract_domains():
            children = [d for d in domain_scores.keys() if DOMAIN_HIERARCHY[d].parent == abstract]
            abstract_scores[abstract] = sum(domain_scores[c] for c in children)

        # Get hierarchy path
        domain_path = get_domain_path(best_domain)
        abstract_domain = DOMAIN_HIERARCHY[best_domain].parent

        logger.info(f"[DomainDetection] Detected: {best_domain} (confidence: {best_score:.2f})")
        logger.info(f"[DomainDetection] Hierarchy: {' → '.join(domain_path)}")

        return {
            "domain": best_domain,
            "confidence": best_score,
            "scores": domain_scores,
            "evidence": domain_evidence[best_domain],

            # Hierarchical information
            "hierarchy": {
                "concrete": best_domain,
                "abstract": abstract_domain,
                "root": "causal_inference",
                "path": domain_path,
                "causal_structure": get_causal_structure(best_domain)
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
    
    def _calculate_domain_score(
        self, 
        corpus: List[str], 
        keywords: List[str]
    ) -> Tuple[float, List[str]]:
        """
        Calculate TF-IDF style score for domain
        
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

def detect_domain_from_dataframe(df: pd.DataFrame) -> Dict:
    """
    Convenience function for domain detection
    
    Usage:
        import pandas as pd
        from backend.inference.domain_detection import detect_domain_from_dataframe
        
        df = pd.read_csv("data.csv")
        result = detect_domain_from_dataframe(df)
        
        print("Detected domain:", result["domain"])
        print("Confidence:", result["confidence"])
        print("Evidence:", result["evidence"])
    """
    detector = DomainDetector()
    return detector.detect_domain(df)
