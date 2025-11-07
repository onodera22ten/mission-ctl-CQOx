"""
ScenarioSpec DSL Parser - NASA-Level反実仮想シナリオ定義

Purpose: YAML形式の反実仮想シナリオを厳密にパース・検証
Spec: 反実仮想.pdf - ScenarioSpec (最小SSOT)
"""

from typing import Dict, List, Optional, Any, Literal
from pydantic import BaseModel, Field, validator
import yaml
from pathlib import Path


class InterventionSpec(BaseModel):
    """介入仕様"""
    type: Literal["policy", "do", "intensity", "spend"] = Field(
        ..., description="介入タイプ: policy(ルールベース), do(直接設定), intensity(強度), spend(予算)"
    )
    rule: Optional[str] = Field(None, description="ポリシールール例: 'score > 0.72'")
    coverage: Optional[float] = Field(None, ge=0.0, le=1.0, description="カバレッジ (0-1)")
    value: Optional[float] = Field(None, description="直接設定値 (do介入)")
    intensity_multiplier: Optional[float] = Field(None, gt=0, description="強度倍率")


class ConstraintsSpec(BaseModel):
    """制約条件"""
    budget: Optional[Dict[str, Any]] = Field(None, description="予算制約: {cap, unit_cost_col}")
    fairness: Optional[Dict[str, Any]] = Field(None, description="公平性制約: {group_col, max_gap}")


class GeographySpec(BaseModel):
    """地理条件"""
    include_regions: Optional[List[str]] = Field(None, description="対象地域")
    exclude_regions: Optional[List[str]] = Field(None, description="除外地域")
    geo_multiplier: Optional[float] = Field(1.0, gt=0, description="地域効果倍率")


class NetworkSpec(BaseModel):
    """ネットワーク条件"""
    seed_size: Optional[float] = Field(0.0, ge=0.0, le=1.0, description="シード集団サイズ")
    neighbor_boost: Optional[float] = Field(0.0, ge=0.0, description="近隣ブースト")


class TimeSpec(BaseModel):
    """時間条件"""
    start: str = Field(..., description="開始日 (YYYY-MM-DD)")
    horizon_days: int = Field(..., gt=0, description="予測期間（日数）")


class ValueSpec(BaseModel):
    """価値設定"""
    value_per_y: float = Field(..., description="アウトカム1単位あたりの価値（円）")


class ScenarioSpec(BaseModel):
    """反実仮想シナリオ仕様（SSOT）"""
    id: str = Field(..., description="シナリオID (例: S1_geo_budget)")
    label: str = Field(..., description="シナリオラベル (例: '予算+20% × 首都圏')")

    intervention: InterventionSpec
    constraints: Optional[ConstraintsSpec] = None
    geography: Optional[GeographySpec] = None
    network: Optional[NetworkSpec] = None
    time: TimeSpec
    value: ValueSpec

    @validator("id")
    def validate_id(cls, v):
        """IDは S1_, S2_ 等で開始すること"""
        if not v.startswith("S") or not v[1:].split("_")[0].isdigit():
            raise ValueError(f"Scenario ID must start with S<number>_ (e.g., S1_geo_budget), got: {v}")
        return v


def parse_scenario_yaml(yaml_path: str | Path) -> ScenarioSpec:
    """
    YAMLファイルをScenarioSpecにパース

    Args:
        yaml_path: YAMLファイルパス

    Returns:
        ScenarioSpec: 検証済みシナリオ仕様

    Raises:
        FileNotFoundError: ファイルが存在しない
        ValueError: YAML形式エラー、スキーマ違反
    """
    path = Path(yaml_path)
    if not path.exists():
        raise FileNotFoundError(f"Scenario YAML not found: {yaml_path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data:
        raise ValueError(f"Empty or invalid YAML: {yaml_path}")

    try:
        spec = ScenarioSpec(**data)
        return spec
    except Exception as e:
        raise ValueError(f"ScenarioSpec validation failed for {yaml_path}: {e}")


def parse_scenario_dict(data: Dict[str, Any]) -> ScenarioSpec:
    """
    辞書形式をScenarioSpecにパース（API経由用）

    Args:
        data: シナリオ辞書

    Returns:
        ScenarioSpec: 検証済みシナリオ仕様
    """
    return ScenarioSpec(**data)


# サンプルシナリオ（テスト/ドキュメント用）
SAMPLE_SCENARIO_YAML = """
id: S1_geo_budget
label: "予算+20% × 首都圏"
intervention:
  type: policy
  rule: "score > 0.72"
  coverage: 0.30
constraints:
  budget:
    cap: 12000000
    unit_cost_col: "cost"
  fairness:
    group_col: "segment"
    max_gap: 0.03
geography:
  include_regions: ["Kanto"]
  geo_multiplier: 1.15
network:
  seed_size: 0.01
  neighbor_boost: 0.2
time:
  start: "2025-11-01"
  horizon_days: 28
value:
  value_per_y: 1200
"""


if __name__ == "__main__":
    # Self-test
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(SAMPLE_SCENARIO_YAML)
        temp_path = f.name

    try:
        spec = parse_scenario_yaml(temp_path)
        print("✅ ScenarioSpec validation passed:")
        print(f"   ID: {spec.id}")
        print(f"   Label: {spec.label}")
        print(f"   Intervention: {spec.intervention.type} ({spec.intervention.rule})")
        print(f"   Budget cap: {spec.constraints.budget['cap'] if spec.constraints else 'N/A'}")
        print(f"   Geography: {spec.geography.include_regions if spec.geography else 'N/A'}")
        print(f"   Value per Y: ¥{spec.value.value_per_y}")
    finally:
        Path(temp_path).unlink()
