# backend/inference/domain_hierarchy.py
"""
Domain Hierarchy: Abstract ↔ Concrete Design
抽象↔具体のドメイン階層設計

階層構造:
- Level 0 (Root): 因果推論の根本的構造
- Level 1 (Abstract): 抽象的なメカニズム
- Level 2 (Concrete): 具体的な適用領域
"""
from dataclasses import dataclass
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

@dataclass
class DomainNode:
    """ドメイン階層のノード"""
    name: str
    level: int  # 0=root, 1=abstract, 2=concrete
    parent: Optional[str] = None
    keywords: List[str] = None
    description: str = ""
    causal_structure: str = ""  # 因果構造の特徴

    def __post_init__(self):
        if self.keywords is None:
            self.keywords = []

# ドメイン階層定義
DOMAIN_HIERARCHY = {
    # Level 0: Root
    "causal_inference": DomainNode(
        name="causal_inference",
        level=0,
        parent=None,
        description="因果推論の根本的構造",
        causal_structure="treatment → outcome with confounding",
        keywords=["treatment", "outcome", "effect", "causal", "intervention"]
    ),

    # Level 1: Abstract domains
    "human_behavior": DomainNode(
        name="human_behavior",
        level=1,
        parent="causal_inference",
        description="人間行動への介入効果",
        causal_structure="intervention → behavior_change → outcome",
        keywords=[
            "individual", "person", "participant", "subject", "human",
            "behavior", "action", "decision", "choice", "response",
            "intervention", "program", "training", "treatment", "therapy"
        ]
    ),

    "economic_transaction": DomainNode(
        name="economic_transaction",
        level=1,
        parent="causal_inference",
        description="経済取引における因果効果",
        causal_structure="pricing/promotion → transaction → revenue",
        keywords=[
            "transaction", "purchase", "buy", "sell", "trade",
            "price", "cost", "revenue", "profit", "value",
            "customer", "consumer", "buyer", "seller", "merchant",
            "market", "demand", "supply", "elasticity"
        ]
    ),

    "network_diffusion": DomainNode(
        name="network_diffusion",
        level=1,
        parent="causal_inference",
        description="ネットワーク上の伝播効果",
        causal_structure="seed_node → neighbors → cascade",
        keywords=[
            "network", "graph", "node", "edge", "link",
            "neighbor", "peer", "connection", "relationship",
            "diffusion", "spread", "cascade", "contagion", "viral",
            "influence", "propagation", "transmission"
        ]
    ),

    # Level 2: Concrete domains
    "education": DomainNode(
        name="education",
        level=2,
        parent="human_behavior",
        description="教育介入の効果分析",
        causal_structure="tutoring/curriculum → learning → test_score/graduation",
        keywords=[
            "student", "school", "teacher", "class", "grade", "score", "test",
            "exam", "course", "program", "curriculum", "education", "learning",
            "achievement", "performance", "gpa", "sat", "act", "graduation",
            "dropout", "attendance", "tuition", "scholarship", "university",
            "college", "elementary", "secondary", "academic", "study", "lesson",
            "classroom", "enrolled", "enroll", "ses", "literacy", "math",
            "reading", "science", "homework", "assignment", "diploma", "transcript"
        ]
    ),

    "medical": DomainNode(
        name="medical",
        level=2,
        parent="human_behavior",
        description="医療介入の効果分析",
        causal_structure="drug/surgery → physiology → mortality/recovery",
        keywords=[
            "patient", "hospital", "doctor", "physician", "nurse", "clinic",
            "diagnosis", "disease", "symptom", "treatment", "therapy", "drug",
            "medication", "prescription", "surgery", "procedure", "mortality",
            "survival", "health", "medical", "clinical", "care", "admission",
            "discharge", "vital", "blood", "pressure", "heart", "rate", "mmhg",
            "bpm", "dose", "mg", "mcg", "qaly", "recovery"
        ]
    ),

    "policy": DomainNode(
        name="policy",
        level=2,
        parent="human_behavior",
        description="政策介入の効果分析",
        causal_structure="policy/regulation → population_behavior → societal_outcome",
        keywords=[
            "policy", "regulation", "law", "government", "public", "citizen",
            "population", "region", "district", "state", "county", "city",
            "municipality", "jurisdiction", "program", "subsidy", "tax",
            "welfare", "benefit", "employment", "unemployment", "income",
            "poverty", "inequality", "crime", "education", "health", "infrastructure",
            "intervention", "reform", "legislation", "compliance", "enforcement"
        ]
    ),

    "retail": DomainNode(
        name="retail",
        level=2,
        parent="economic_transaction",
        description="小売マーケティング効果分析",
        causal_structure="promotion/pricing → purchase → revenue/loyalty",
        keywords=[
            "customer", "product", "purchase", "order", "transaction", "sales",
            "revenue", "price", "discount", "promotion", "campaign", "marketing",
            "basket", "cart", "checkout", "conversion", "sku", "inventory",
            "store", "shop", "retail", "ecommerce", "online", "merchant",
            "payment", "shipping", "delivery", "return", "refund", "loyalty",
            "ltv", "cltv", "arpu", "basket_size"
        ]
    ),

    "finance": DomainNode(
        name="finance",
        level=2,
        parent="economic_transaction",
        description="金融投資効果分析",
        causal_structure="investment_strategy → portfolio_allocation → return/risk",
        keywords=[
            "account", "portfolio", "investment", "stock", "bond", "asset",
            "return", "profit", "loss", "revenue", "expense", "balance",
            "transaction", "trade", "position", "hedge", "risk", "volatility",
            "sharpe", "alpha", "beta", "yield", "dividend", "interest",
            "rate", "currency", "forex", "exchange", "market", "financial",
            "capital", "equity", "debt", "credit", "loan", "mortgage"
        ]
    ),

    "network": DomainNode(
        name="network",
        level=2,
        parent="network_diffusion",
        description="ソーシャルネットワーク効果分析",
        causal_structure="seed_user → friends → viral_spread",
        keywords=[
            "node", "edge", "link", "connection", "friend", "follower", "follow",
            "network", "graph", "social", "user", "community", "group",
            "influence", "centrality", "degree", "betweenness", "clustering",
            "diffusion", "cascade", "viral", "spread", "contagion", "peer",
            "neighbor", "adjacent", "connected", "relationship", "interaction",
            "engagement", "share", "like", "comment", "post", "message"
        ]
    ),
}

def get_domain_hierarchy() -> Dict[str, DomainNode]:
    """ドメイン階層を取得"""
    return DOMAIN_HIERARCHY

def get_concrete_domains() -> List[str]:
    """具体ドメイン（Level 2）のリストを取得"""
    return [name for name, node in DOMAIN_HIERARCHY.items() if node.level == 2]

def get_abstract_domains() -> List[str]:
    """抽象ドメイン（Level 1）のリストを取得"""
    return [name for name, node in DOMAIN_HIERARCHY.items() if node.level == 1]

def get_parent_domain(domain: str) -> Optional[str]:
    """ドメインの親を取得"""
    if domain not in DOMAIN_HIERARCHY:
        return None
    return DOMAIN_HIERARCHY[domain].parent

def get_children_domains(domain: str) -> List[str]:
    """ドメインの子を取得"""
    return [
        name for name, node in DOMAIN_HIERARCHY.items()
        if node.parent == domain
    ]

def get_domain_path(domain: str) -> List[str]:
    """ドメインの階層パスを取得 (root → abstract → concrete)"""
    if domain not in DOMAIN_HIERARCHY:
        return []

    path = [domain]
    current = domain
    while DOMAIN_HIERARCHY[current].parent is not None:
        parent = DOMAIN_HIERARCHY[current].parent
        path.insert(0, parent)
        current = parent

    return path

def get_causal_structure(domain: str) -> str:
    """ドメインの因果構造を取得"""
    if domain not in DOMAIN_HIERARCHY:
        return ""
    return DOMAIN_HIERARCHY[domain].causal_structure

def visualize_hierarchy() -> str:
    """階層構造を文字列で可視化"""
    lines = ["Domain Hierarchy (Abstract ↔ Concrete):"]
    lines.append("")

    # Level 0
    root = [n for n, node in DOMAIN_HIERARCHY.items() if node.level == 0][0]
    lines.append(f"[Level 0 - Root] {root}")
    lines.append(f"  └─ {DOMAIN_HIERARCHY[root].description}")
    lines.append("")

    # Level 1
    abstract_domains = get_abstract_domains()
    for i, abstract in enumerate(abstract_domains):
        is_last_abstract = (i == len(abstract_domains) - 1)
        prefix = "└─" if is_last_abstract else "├─"
        lines.append(f"  {prefix} [Level 1 - Abstract] {abstract}")
        lines.append(f"  {'  ' if is_last_abstract else '│ '}  └─ {DOMAIN_HIERARCHY[abstract].description}")

        # Level 2
        concrete_domains = get_children_domains(abstract)
        for j, concrete in enumerate(concrete_domains):
            is_last_concrete = (j == len(concrete_domains) - 1)
            concrete_prefix = "└─" if is_last_concrete else "├─"
            parent_prefix = "  " if is_last_abstract else "│ "
            lines.append(f"  {parent_prefix}     {concrete_prefix} [Level 2 - Concrete] {concrete}")
            lines.append(f"  {parent_prefix}     {'  ' if is_last_concrete else '│ '}  └─ {DOMAIN_HIERARCHY[concrete].description}")

    return "\n".join(lines)

if __name__ == "__main__":
    # Test
    print(visualize_hierarchy())
    print("\n" + "="*80 + "\n")

    # Example: education domain path
    education_path = get_domain_path("education")
    print(f"Education domain path: {' → '.join(education_path)}")
    print(f"Causal structure: {get_causal_structure('education')}")
