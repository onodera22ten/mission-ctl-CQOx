# backend/gateway/app.py
from __future__ import annotations

import json
import logging
import traceback
import uuid
from pathlib import Path
from typing import Any, Dict

import httpx
import pandas as pd
from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.staticfiles import StaticFiles  # 追加

# Import resilience patterns
try:
    from backend.resilience.circuit_breaker import circuit_breaker
    from backend.resilience.retry import exponential_backoff_retry
    from backend.resilience.timeout import api_timeout
    HAS_RESILIENCE = True
except Exception as e:
    logging.warning(f"Resilience patterns not available: {e}")
    HAS_RESILIENCE = False

ENGINE_URL = Path("./").resolve().joinpath(".engine_url").read_text().strip() if Path(".engine_url").exists() else "http://localhost:8080"
BASE_DIR = Path(__file__).resolve().parents[2]
UPLOAD_DIR = BASE_DIR / "data" / "uploads"
REGISTRY_PATH = BASE_DIR / "data" / "registry.json"
REPORTS_DIR = BASE_DIR / "reports"  # 追加

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger("gateway")

# Setup graceful shutdown
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context for graceful startup/shutdown"""
    logger.info("[Gateway] Starting up...")
    yield
    logger.info("[Gateway] Shutting down gracefully...")

app = FastAPI(title="CQOx Gateway", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# /reports を静的公開（Engine と同じ物理パス）
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/reports", StaticFiles(directory=str(REPORTS_DIR), html=False), name="reports")

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Incoming request: {request.method} {request.url.path}")
    try:
        response = await call_next(request)
        logger.info(f"Response status: {response.status_code}")
        return response
    except Exception as e:
        logger.error(f"Request failed: {str(e)}")
        logger.error(traceback.format_exc())
        raise

def _load_registry() -> Dict[str, Dict[str, Any]]:
    if not REGISTRY_PATH.exists():
        return {}
    try:
        return json.loads(REGISTRY_PATH.read_text())
    except Exception:
        return {}

def _save_registry(reg: Dict[str, Dict[str, Any]]) -> None:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(json.dumps(reg, ensure_ascii=False, indent=2))

def _infer_candidates(df: pd.DataFrame) -> Dict[str, list]:
    cols = list(df.columns)
    lc = [c.lower() for c in cols]

    def pick(keys):
        out = []
        for k in keys:
            for i, name in enumerate(lc):
                if k == name or k in name:
                    out.append(cols[i])
        return list(dict.fromkeys(out))
    return {
        "y": pick(["y","outcome","label","metric","score","kpi","conversion"]),
        "treatment": pick(["treatment","w","variant","policy","exposure","dose"]),
        "unit_id": pick(["id","user_id","patient_id","device","account","node"]),
        "time": pick(["date","timestamp","period","week","day","time"]),
        "cost": pick(["cost","price","spend","loss"]),
        "log_propensity": pick(["log_propensity","lp","logit_p","pscore_logit"]),
    }

def _normalize_mapping(m: Any) -> Dict[str, str]:
    if isinstance(m, dict):
        return {k: str(v) for k, v in m.items() if v}
    if isinstance(m, list):
        out: Dict[str, str] = {}
        for item in m:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role", "")).strip()
            col = str(item.get("column", "")).strip()
            if role and col:
                out[role] = col
        return out
    return {}

@app.get("/api/health")
async def health():
    return {"ok": True, "service": "gateway"}

@app.post("/api/upload")
async def upload(file: UploadFile = File(...)) -> JSONResponse:
    """
    Upload file with Plan2 multi-format support

    Supported formats:
    - CSV, TSV (text/csv, text/tab-separated-values)
    - JSONL, NDJSON (application/jsonl, application/x-ndjson)
    - Excel (application/vnd.openxmlformats-officedocument.spreadsheetml.sheet)
    - Parquet (application/vnd.apache.parquet)
    - Feather (application/vnd.apache.arrow.feather)
    - Compressed variants: .gz, .bz2
    """
    if not file.filename:
        raise HTTPException(400, "Empty filename")

    # Plan2 multi-format validation
    SUPPORTED_EXTENSIONS = {
        ".csv", ".tsv",
        ".jsonl", ".ndjson",
        ".xlsx",
        ".parquet",
        ".feather",
        ".csv.gz", ".csv.bz2",
        ".tsv.gz", ".tsv.bz2",
        ".jsonl.gz", ".jsonl.bz2",
        ".ndjson.gz", ".ndjson.bz2",
    }

    fname_lower = file.filename.lower()
    is_valid = any(fname_lower.endswith(ext) for ext in SUPPORTED_EXTENSIONS)

    if not is_valid:
        raise HTTPException(
            400,
            f"Unsupported file format: {file.filename}. "
            f"Supported: CSV, TSV, JSONL, XLSX, Parquet, Feather (with .gz/.bz2 compression)"
        )

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dataset_id = uuid.uuid4().hex
    dst = UPLOAD_DIR / f"{dataset_id}_{file.filename}"
    content = await file.read()
    dst.write_bytes(content)

    reg = _load_registry()
    reg[dataset_id] = {"path": str(dst), "original_filename": file.filename}
    _save_registry(reg)

    try:
        # Use Parquet preprocessing pipeline
        from backend.ingestion.parquet_pipeline import ParquetPipeline

        pipeline = ParquetPipeline(BASE_DIR / "data")
        packet_info = pipeline.process_upload(dst, dataset_id)

        # Load processed data for preview
        df, metadata = pipeline.load_packet(dataset_id)

        preview_rows = df.head(10).to_dict(orient="records")
        dtypes = {c: str(t) for c, t in df.dtypes.items()}
        candidates = _infer_candidates(df)
        stats = [{"column": c, "dtype": str(df.dtypes[c]), "na": int(df[c].isna().sum())} for c in df.columns]

        logger.info(f"[Upload] Parquet pipeline processed: {packet_info['preprocessing']['missing_filled']} missing filled")
    except Exception as e:
        logger.error(f"Failed to process uploaded file with Parquet pipeline: {str(e)}")
        # Fallback to basic loader
        try:
            from ciq.scripts.convert_any_to_parquet import load_one
            df = load_one(dst)
            # Replace NaN/inf with None for JSON serialization
            df_clean = df.replace([float('inf'), float('-inf')], None).fillna(value=None)
            preview_rows = df_clean.head(10).to_dict(orient="records")
            dtypes = {c: str(t) for c, t in df.dtypes.items()}
            candidates = _infer_candidates(df)
            stats = [{"column": c, "dtype": str(df.dtypes[c]), "na": int(df[c].isna().sum())} for c in df.columns]
        except Exception as e2:
            logger.error(f"Fallback loader also failed: {str(e2)}")
            preview_rows, dtypes, candidates, stats = [], {}, {}, []

    return JSONResponse({"ok": True, "dataset_id": dataset_id,
                         "meta": {"columns": list(df.columns) if 'df' in locals() else [], "dtypes": dtypes, "preview": preview_rows},
                         "candidates": candidates, "stats": stats,
                         "packet": packet_info if 'packet_info' in locals() else None})

@app.get("/api/roles/profile")
async def roles_profile(dataset_id: str = Query(...)) -> JSONResponse:
    reg = _load_registry()
    item = reg.get(dataset_id)
    if not item:
        raise HTTPException(404, f"Dataset not found: {dataset_id}")
    path = Path(item["path"])
    if not path.exists():
        raise HTTPException(404, f"File missing on disk: {path}")
    try:
        # Use Plan2 multi-format loader
        from ciq.scripts.convert_any_to_parquet import load_one

        df = load_one(path)
        preview_rows = df.head(10).to_dict(orient="records")
        dtypes = {c: str(t) for c, t in df.dtypes.items()}
        candidates = _infer_candidates(df)
        return JSONResponse({"ok": True, "dataset_id": dataset_id,
                             "meta": {"columns": list(df.columns), "dtypes": dtypes, "preview": preview_rows},
                             "candidates": candidates})
    except Exception as e:
        raise HTTPException(500, f"Failed to read file: {str(e)}")

@app.post("/api/roles/infer")
async def infer_roles(request: Dict[str, Any]) -> JSONResponse:
    """
    Automatic role inference using ontology-based algorithm

    Request:
        {
            "dataset_id": "abc123",
            "min_confidence": 0.3  // optional, default 0.3
        }

    Response:
        {
            "ok": true,
            "mapping": {"y": "revenue", "treatment": "campaign", ...},
            "candidates": {
                "y": [
                    {"column": "revenue", "confidence": 0.95, "reasons": [...]},
                    {"column": "profit", "confidence": 0.72, "reasons": [...]}
                ],
                ...
            },
            "required_missing": [],
            "confidence": 0.87,
            "domain": {
                "domain": "retail",
                "confidence": 0.82,
                "evidence": ["customer", "product", "sales", ...]
            }
        }
    """
    dataset_id = request.get("dataset_id")
    min_confidence = request.get("min_confidence", 0.3)

    if not dataset_id:
        raise HTTPException(422, "dataset_id is required")

    reg = _load_registry()
    item = reg.get(dataset_id)
    if not item:
        raise HTTPException(404, f"Dataset not found: {dataset_id}")

    path = Path(item["path"])
    if not path.exists():
        raise HTTPException(404, f"File missing on disk: {path}")

    try:
        # Use Plan2 multi-format loader
        from ciq.scripts.convert_any_to_parquet import load_one

        df = load_one(path)

        # Import inference modules
        from backend.inference.role_inference import infer_roles_from_dataframe
        from backend.inference.domain_detection import detect_domain_from_dataframe
        from backend.inference.estimator_validator import EstimatorValidator

        # Infer roles
        role_result = infer_roles_from_dataframe(df, min_confidence)

        # Detect domain
        domain_result = detect_domain_from_dataframe(df)

        # Validate estimators with inferred mapping
        validator = EstimatorValidator(df, role_result["mapping"])
        validation_results = validator.validate_all()
        runnable_estimators = validator.get_runnable_estimators()
        enhanced_mapping = validator.suggest_enhanced_mapping()

        return JSONResponse({
            "ok": True,
            "mapping": role_result["mapping"],
            "enhanced_mapping": enhanced_mapping,
            "candidates": role_result["candidates"],
            "required_missing": role_result["required_missing"],
            "confidence": role_result["confidence"],
            "domain": domain_result,
            "estimator_validation": {
                "runnable": runnable_estimators,
                "details": validation_results,
                "count": f"{len(runnable_estimators)}/7"
            }
        })

    except ImportError as e:
        logger.error(f"Inference modules not available: {e}")
        raise HTTPException(500, f"Inference modules not available: {str(e)}")
    except Exception as e:
        logger.error(f"Role inference failed: {str(e)}")
        raise HTTPException(500, f"Failed to infer roles: {str(e)}")

# Engine call with resilience patterns
# Temporarily disable resilience for debugging
async def _call_engine_analyze(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Call engine with circuit breaker, retry, and timeout protection"""
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(f"{ENGINE_URL}/api/analyze/comprehensive", json=payload)
        r.raise_for_status()
        return r.json()

@app.post("/api/analyze/comprehensive")
async def analyze_comprehensive(request: Dict[str, Any]) -> JSONResponse:
    dataset_id = request.get("dataset_id")
    if not dataset_id:
        raise HTTPException(422, "dataset_id is required")
    reg = _load_registry()
    item = reg.get(dataset_id)
    if not item:
        raise HTTPException(404, f"Dataset not found: {dataset_id}")

    mapping = _normalize_mapping(request.get("mapping", {}))
    if not mapping:
        raise HTTPException(422, "mapping is required")
    for k in ["y","treatment","unit_id"]:
        if k not in mapping:
            raise HTTPException(422, f"Missing mapping: {k}")

    # エンジンコンテナ用にパスを変換（ホストの絶対パス → /app/ 以下）
    df_path = item["path"]
    # TODO: Re-enable for Docker deployment
    # if df_path.startswith("/home/"):
    #     # ホストパスをコンテナパスに変換
    #     df_path = df_path.replace("/home/hirokionodera/cqox-complete_b", "/app")

    forward_payload: Dict[str, Any] = {
        "dataset_id": dataset_id,
        "df_path": df_path,
        "mapping": mapping,
        "domain": request.get("domain"),
    }
    cfg_json = request.get("cfg_json")
    if cfg_json is None:
        forward_payload["cfg_json"] = json.dumps({"lambda": 1.0})
    elif isinstance(cfg_json, str):
        forward_payload["cfg_json"] = cfg_json
    else:
        forward_payload["cfg_json"] = json.dumps(cfg_json)

    try:
        result = await _call_engine_analyze(forward_payload)
        return JSONResponse(result)
    except httpx.HTTPError as e:
        logger.error(f"Engine call failed (HTTPError): {type(e).__name__}: {str(e)}")
        logger.error(f"Exception details: {repr(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(503, f"Engine service unavailable: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error calling engine: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(500, f"Internal error: {str(e)}")

# Setup observability (Metrics + Tracing)
try:
    from backend.observability.metrics import setup_observability_metrics
    setup_observability_metrics(app, service_name="gateway")
except Exception as _e:
    print(f"[observability][gateway] metrics disabled: {_e}")

try:
    from backend.observability.tracing import setup_opentelemetry, instrument_fastapi
    import os

    # Setup OpenTelemetry with environment-based configuration
    otlp_endpoint = os.getenv("OTLP_ENDPOINT")  # e.g., "http://otel-collector:4317"
    jaeger_endpoint = os.getenv("JAEGER_ENDPOINT", "localhost:6831")
    enable_console = os.getenv("OTEL_CONSOLE", "false").lower() == "true"

    setup_opentelemetry(
        service_name="gateway",
        otlp_endpoint=otlp_endpoint,
        jaeger_endpoint=jaeger_endpoint if not otlp_endpoint else None,
        enable_console=enable_console
    )
    instrument_fastapi(app, service_name="gateway")
    logger.info("[Tracing] OpenTelemetry enabled for Gateway")
except Exception as _e:
    logger.warning(f"[observability][gateway] tracing disabled: {_e}")
