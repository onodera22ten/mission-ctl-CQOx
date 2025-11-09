"""
Counterfactual API Router - Production Implementation
反実仮想比較エンドポイント（本番実装）
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import pandas as pd
from pathlib import Path
import json

from backend.engine.scenario_spec import parse_scenario_yaml, parse_scenario_dict
from backend.inference.ope import evaluate_scenario_ope
from backend.inference.g_computation import evaluate_scenario_gcomp
from backend.engine.quality_gates import evaluate_quality_gates
from backend.common.schema_validator import validate_for_estimators, ValidationError
from backend.engine.decision_card import generate_decision_card
from backend.engine.production_outputs import ProductionOutputGenerator

router = APIRouter(prefix="/api/scenario", tags=["counterfactual"])


class ScenarioRunRequest(BaseModel):
    """反実仮想シナリオ実行リクエスト"""
    dataset_id: str
    scenario: str  # YAML path or inline dict
    mode: str = "ope"  # "ope" or "gcomp"


class ScenarioRunResponse(BaseModel):
    """反実仮想シナリオ実行レスポンス"""
    status: str
    scenario_id: str
    mode: str
    ate_s0: float  # 観測ATE
    ate_s1: float  # 反実仮想ATE
    delta_ate: float  # ΔATE
    delta_profit: float  # Δ利益
    quality_gates: Optional[Dict[str, Any]] = None  # Quality Gates評価結果
    decision: Optional[str] = None  # GO/CANARY/HOLD
    warnings: List[str] = []
    figures: Dict[str, str] = {}  # {panel_name: url}


class ScenarioBatchRequest(BaseModel):
    """複数シナリオバッチ実行リクエスト"""
    dataset_id: str
    scenarios: List[str]  # List of YAML paths or inline dicts
    mode: str = "ope"  # "ope" for fast screening


class ScenarioBatchResponse(BaseModel):
    """複数シナリオバッチ実行レスポンス"""
    status: str
    dataset_id: str
    results: List[Dict[str, Any]]  # List of scenario results
    ranked_scenarios: List[str]  # Scenarios ranked by ΔProfit


class DecisionCardRequest(BaseModel):
    """Decision Card生成リクエスト"""
    dataset_id: str
    scenario_id: str
    fmt: str = "pdf"  # "pdf" or "html"


@router.post("/run", response_model=ScenarioRunResponse)
async def run_scenario(req: ScenarioRunRequest):
    """
    反実仮想シナリオを実行（OPE/g-comp）

    Production実装: 実際のOPE/g-computation評価
    """
    try:
        # Load scenario specification
        if req.scenario.endswith(".yaml"):
            scenario_spec = parse_scenario_yaml(req.scenario).dict()
        else:
            # Assume inline dict
            scenario_spec = json.loads(req.scenario) if isinstance(req.scenario, str) else req.scenario

        scenario_id = scenario_spec.get("id", "unknown")

        # Load dataset
        data_path = Path(f"data/{req.dataset_id}/data.parquet")
        if not data_path.exists():
            data_path = Path(f"data/{req.dataset_id}.parquet")

        if not data_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dataset not found: {req.dataset_id}"
            )

        df = pd.read_parquet(data_path)

        # Default column mapping
        mapping = {
            "treatment": "treatment",
            "y": "y",
            "unit_id": "unit_id",
            "time": "time",
            "cost": "cost",
            "log_propensity": "log_propensity"
        }

        # Validate schema
        try:
            df = validate_for_estimators(
                df,
                estimators=["ope"],  # OPE requires specific columns
                dataset_id=req.dataset_id,
                mapping=mapping
            )
        except ValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=e.to_http_400()
            )

        # Evaluate using OPE or g-computation
        if req.mode == "ope":
            result = evaluate_scenario_ope(
                df=df,
                scenario_spec=scenario_spec,
                mapping=mapping,
                method="dr"  # Use Doubly Robust as default
            )
        else:  # gcomp
            result = evaluate_scenario_gcomp(
                df=df,
                scenario_spec=scenario_spec,
                mapping=mapping,
                method="rf",  # Use Random Forest as default
                n_bootstrap=100
            )

        # Extract results
        ate_s0 = result["baseline"]["value"]
        ate_s1 = result["scenario"]["value"]
        delta_ate = result["delta"]["value"]
        delta_profit = delta_ate  # Already in profit terms from evaluators

        # Evaluate Quality Gates
        quality_gates_result = evaluate_quality_gates(
            estimation_results=result,
            delta_profit=delta_profit,
            constraints=scenario_spec.get("constraints", {})
        )

        decision = quality_gates_result.get("overall", {}).get("decision", "HOLD")

        # Generate comparison report (for decision card generation)
        output_gen = ProductionOutputGenerator()
        scenario_spec["dataset_id"] = req.dataset_id  # Add dataset_id to spec
        comparison_path = output_gen.generate_comparison_report(
            baseline_result=result["baseline"],
            scenario_result=result["scenario"],
            scenario_spec=scenario_spec,
            quality_gates=quality_gates_result
        )

        # Generate figures (placeholder for now)
        figures = {}

        # In production, generate actual S0/S1 comparison figures here
        # For now, return empty dict

        warnings = []
        if req.mode == "ope":
            ess = result["scenario"].get("ess", 0)
            if ess < 100:
                warnings.append(f"Low effective sample size: {ess:.0f}")

        # Add quality gates warnings
        for rationale in quality_gates_result.get("rationale", []):
            if "Failed" in rationale or "violation" in rationale:
                warnings.append(rationale)

        return ScenarioRunResponse(
            status="completed",
            scenario_id=scenario_id,
            mode=req.mode,
            ate_s0=ate_s0,
            ate_s1=ate_s1,
            delta_ate=delta_ate,
            delta_profit=delta_profit,
            quality_gates=quality_gates_result,
            decision=decision,
            warnings=warnings,
            figures=figures
        )

    except HTTPException:
        raise
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.to_http_400()
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scenario execution failed: {str(e)}"
        )


@router.post("/confirm")
async def confirm_scenario(req: ScenarioRunRequest):
    """
    反実仮想シナリオの確証実行（g-computation）

    OPEで高速スクリーニングした後、上位候補をg-compで精査
    """
    # ope実行と同じロジック（mode="gcomp"で呼び出される想定）
    return await run_scenario(req)


@router.get("/export/decision_card")
async def export_decision_card(
    dataset_id: str,
    scenario_id: str,
    fmt: str = "json"
):
    """
    Decision Card生成（JSON/HTML/PDF）

    横並び可視化 + ΔProfit + Quality Gatesゲート判定

    Note: This endpoint looks for the latest comparison report.
    To generate a fresh decision card, run the scenario first via /run endpoint.
    """
    try:
        if fmt not in ["json", "html", "pdf"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid format: {fmt}. Must be 'json', 'html', or 'pdf'"
            )

        # Look for latest comparison report
        exports_dir = Path("exports") / dataset_id
        if not exports_dir.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No exports found for dataset {dataset_id}. Run scenario first."
            )

        # Find latest comparison report for this scenario
        comparison_files = list(exports_dir.glob(f"comparison_{dataset_id}_{scenario_id}_*.json"))
        if not comparison_files:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No comparison report found for scenario {scenario_id}. Run scenario first."
            )

        # Load latest comparison report
        latest_comparison = sorted(comparison_files, key=lambda p: p.stat().st_mtime, reverse=True)[0]
        with open(latest_comparison) as f:
            comparison_data = json.load(f)

        # Extract data for decision card
        baseline_result = comparison_data.get("baseline", {})
        scenario_result = comparison_data.get("scenario", {})
        quality_gates = comparison_data.get("quality_gates", {})

        # Generate decision card
        card_path = generate_decision_card(
            dataset_id=dataset_id,
            scenario_id=scenario_id,
            baseline_result=baseline_result,
            scenario_result=scenario_result,
            quality_gates=quality_gates,
            scenario_spec=None,  # Not stored in comparison report
            format=fmt,
            output_dir=Path("exports/decision_cards")
        )

        return {
            "status": "completed",
            "path": str(card_path),
            "format": fmt,
            "generated_at": comparison_data.get("generated_at")
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Decision card generation failed: {str(e)}"
        )


@router.post("/run_batch", response_model=ScenarioBatchResponse)
async def run_batch_scenarios(req: ScenarioBatchRequest):
    """
    複数シナリオのバッチ実行（高速スクリーニング）

    OPEで複数のシナリオを素早く評価し、ΔProfitでランク付け
    """
    try:
        # Load dataset once
        data_path = Path(f"data/{req.dataset_id}/data.parquet")
        if not data_path.exists():
            data_path = Path(f"data/{req.dataset_id}.parquet")

        if not data_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dataset not found: {req.dataset_id}"
            )

        df = pd.read_parquet(data_path)

        # Default column mapping
        mapping = {
            "treatment": "treatment",
            "y": "y",
            "unit_id": "unit_id",
            "time": "time",
            "cost": "cost",
            "log_propensity": "log_propensity"
        }

        # Validate schema once
        try:
            df = validate_for_estimators(
                df,
                estimators=["ope"],
                dataset_id=req.dataset_id,
                mapping=mapping
            )
        except ValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=e.to_http_400()
            )

        results = []

        # Evaluate each scenario
        for scenario in req.scenarios:
            try:
                # Load scenario specification
                if scenario.endswith(".yaml"):
                    scenario_spec = parse_scenario_yaml(scenario).dict()
                else:
                    scenario_spec = json.loads(scenario) if isinstance(scenario, str) else scenario

                scenario_id = scenario_spec.get("id", "unknown")

                # Evaluate using OPE (fast)
                result = evaluate_scenario_ope(
                    df=df,
                    scenario_spec=scenario_spec,
                    mapping=mapping,
                    method="dr"
                )

                delta_profit = result["delta"]["value"]

                results.append({
                    "scenario_id": scenario_id,
                    "delta_profit": delta_profit,
                    "ate_s0": result["baseline"]["value"],
                    "ate_s1": result["scenario"]["value"],
                    "ci": result["scenario"]["ci"],
                    "ess": result["scenario"].get("ess", 0)
                })

            except Exception as e:
                # Log error but continue with other scenarios
                results.append({
                    "scenario_id": scenario_id if 'scenario_id' in locals() else "unknown",
                    "error": str(e),
                    "delta_profit": float("-inf")
                })

        # Rank scenarios by ΔProfit
        ranked = sorted(
            [r for r in results if "error" not in r],
            key=lambda x: x["delta_profit"],
            reverse=True
        )
        ranked_scenario_ids = [r["scenario_id"] for r in ranked]

        return ScenarioBatchResponse(
            status="completed",
            dataset_id=req.dataset_id,
            results=results,
            ranked_scenarios=ranked_scenario_ids
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch scenario execution failed: {str(e)}"
        )


@router.get("/list")
async def list_scenarios(dataset_id: str):
    """
    利用可能なシナリオ一覧を取得
    """
    try:
        scenarios_dir = Path("config/scenarios")

        if not scenarios_dir.exists():
            return {"scenarios": [], "count": 0}

        yaml_files = list(scenarios_dir.glob("*.yaml"))
        scenarios = [
            {
                "id": f.stem,
                "path": str(f),
                "label": f.stem.replace("_", " ").title()
            }
            for f in yaml_files
        ]

        return {
            "scenarios": scenarios,
            "count": len(scenarios)
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list scenarios: {str(e)}"
        )
