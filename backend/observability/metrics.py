"""
可観測性ダッシュボード用の詳細メトリクス収集
37パネルすべてに対応したメトリクスを定義
"""
from __future__ import annotations
import time
from typing import Dict, Any
from prometheus_client import (
    CollectorRegistry, Counter, Histogram, Gauge, Summary,
    CONTENT_TYPE_LATEST, generate_latest,
)
from fastapi import FastAPI, Request
from starlette.responses import Response

# グローバルレジストリ（全サービスで共有）
global_registry = CollectorRegistry()

# =============================================================================
# パネル 1-5: 基本的なリクエストメトリクス
# =============================================================================

# パネル1: Engine E2E Latency p50/p95/p99
engine_e2e_latency = Histogram(
    "cqox_engine_e2e_duration_seconds",
    "Engine end-to-end request duration",
    ["endpoint"],
    registry=global_registry,
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0)
)

# パネル2: Gateway Request Latency p50/p95
gateway_request_latency = Histogram(
    "cqox_gateway_request_duration_seconds",
    "Gateway request duration",
    ["method", "path"],
    registry=global_registry,
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0)
)

# パネル3: Upload Throughput RPS
upload_requests_total = Counter(
    "cqox_upload_requests_total",
    "Total upload requests",
    ["status"],
    registry=global_registry
)

# パネル4: Analyze Throughput RPS
analyze_requests_total = Counter(
    "cqox_analyze_requests_total",
    "Total analyze requests",
    ["status"],
    registry=global_registry
)

# パネル5: Error Rate (4xx/5xx)
http_errors_total = Counter(
    "cqox_http_errors_total",
    "HTTP errors by status code",
    ["service", "status_code"],
    registry=global_registry
)

# =============================================================================
# パネル 6-11: Worker/GPU メトリクス
# =============================================================================

# パネル6: Job Queue Depth (engine)
job_queue_depth = Gauge(
    "cqox_job_queue_depth",
    "Number of jobs waiting in queue",
    registry=global_registry
)

# パネル7: Worker Concurrency (実行中ジョブ)
worker_active_jobs = Gauge(
    "cqox_worker_active_jobs",
    "Number of currently running jobs",
    ["worker_id"],
    registry=global_registry
)

# パネル8: Worker Task Wait Time
worker_task_wait_seconds = Histogram(
    "cqox_worker_task_wait_seconds",
    "Time a task waits before execution",
    registry=global_registry,
    buckets=(0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0)
)

# パネル9: GPU Memory Used %
gpu_memory_used_percent = Gauge(
    "cqox_gpu_memory_used_percent",
    "GPU memory utilization percentage",
    ["device_id"],
    registry=global_registry
)

# パネル10: GPU Utilization %
gpu_utilization_percent = Gauge(
    "cqox_gpu_utilization_percent",
    "GPU compute utilization percentage",
    ["device_id"],
    registry=global_registry
)

# パネル11: GPU OOM/Timeout Count
gpu_errors_total = Counter(
    "cqox_gpu_errors_total",
    "GPU errors (OOM, timeout, etc)",
    ["error_type", "device_id"],
    registry=global_registry
)

# =============================================================================
# パネル 12-18: 推定器レイテンシ (7推定器)
# =============================================================================
estimator_latency = Histogram(
    "cqox_estimator_duration_seconds",
    "Estimator execution duration",
    ["estimator_name"],
    registry=global_registry,
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0)
)

# =============================================================================
# パネル 19-25: 品質ゲート通過率 (7ゲート)
# =============================================================================
gate_pass_rate = Counter(
    "cqox_quality_gate_checks_total",
    "Quality gate check results",
    ["gate_name", "result"],  # result: pass/fail
    registry=global_registry
)

# =============================================================================
# パネル 26-31: CAS/Consensus/Health メトリクス
# =============================================================================

# パネル26: CAS Average (全ジョブ)
cas_score = Histogram(
    "cqox_cas_score",
    "Causal Assurance Score distribution",
    registry=global_registry,
    buckets=(0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100)
)

# パネル27: CAS Distribution Histogram (上記と同じ)

# パネル28: Sign Consensus Ratio (+一致率)
sign_consensus_ratio = Histogram(
    "cqox_sign_consensus_ratio",
    "Ratio of estimators agreeing on effect sign",
    registry=global_registry,
    buckets=(0.0, 0.2, 0.4, 0.6, 0.7, 0.8, 0.9, 1.0)
)

# パネル29: CI Overlap Index
ci_overlap_index = Histogram(
    "cqox_ci_overlap_index",
    "Confidence interval overlap index",
    registry=global_registry,
    buckets=(0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9, 1.0)
)

# パネル30: Data Health (missing+imbalance 指標)
data_health_score = Gauge(
    "cqox_data_health_score",
    "Overall data health score",
    ["dataset_id"],
    registry=global_registry
)

# パネル31: Reject (Fail-Closed) Rate
reject_rate_total = Counter(
    "cqox_reject_total",
    "Jobs rejected due to quality gate failures",
    ["reason"],
    registry=global_registry
)

# =============================================================================
# パネル 32-37: その他のメトリクス
# =============================================================================

# パネル32: Domain-Agnostic Mix (自動判定カテゴリ比)
domain_auto_detect = Counter(
    "cqox_domain_auto_detected_total",
    "Auto-detected domain categories",
    ["detected_category"],
    registry=global_registry
)

# パネル33: Largest File Size Processed (rolling)
file_size_processed_bytes = Histogram(
    "cqox_file_size_processed_bytes",
    "Size of processed CSV files",
    registry=global_registry,
    buckets=(1e4, 1e5, 1e6, 1e7, 1e8, 1e9)
)

# パネル34: P95 Time per 10k Rows
processing_time_per_10k_rows = Histogram(
    "cqox_processing_time_per_10k_rows_seconds",
    "Processing time normalized per 10k rows",
    registry=global_registry,
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0)
)

# パネル35: Uptime / Availability
service_uptime_seconds = Gauge(
    "cqox_service_uptime_seconds",
    "Service uptime in seconds",
    ["service"],
    registry=global_registry
)

# パネル36: Top Error Reasons (分類)
error_reasons_total = Counter(
    "cqox_error_reasons_total",
    "Errors categorized by reason",
    ["service", "error_category"],
    registry=global_registry
)

# パネル37: End-to-End SLO Compliance Heatmap
slo_compliance_checks = Counter(
    "cqox_slo_compliance_total",
    "SLO compliance check results",
    ["slo_name", "result"],  # result: met/violated
    registry=global_registry
)

# =============================================================================
# ヘルパー関数
# =============================================================================

def setup_observability_metrics(app: FastAPI, service_name: str = "unknown") -> None:
    """
    FastAPIアプリケーションに可観測性メトリクスを統合
    - Prometheusエンドポイント (/metrics) を追加
    - リクエストミドルウェアでメトリクスを自動収集
    """
    start_time = time.time()
    service_uptime_seconds.labels(service=service_name).set_function(
        lambda: time.time() - start_time
    )

    @app.middleware("http")
    async def observability_middleware(request: Request, call_next):
        method = request.method
        path = request.url.path

        # メトリクスエンドポイント自体は測定しない
        if path == "/metrics":
            return await call_next(request)

        start = time.perf_counter()
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code

            # エラーカウント
            if status_code >= 400:
                http_errors_total.labels(
                    service=service_name,
                    status_code=str(status_code)
                ).inc()

            # 特定エンドポイントのトラッキング
            if "/api/upload" in path:
                upload_requests_total.labels(
                    status="success" if status_code < 400 else "error"
                ).inc()

            if "/api/analyze" in path:
                analyze_requests_total.labels(
                    status="success" if status_code < 400 else "error"
                ).inc()

                # Engine E2E レイテンシ
                if service_name == "engine":
                    duration = time.perf_counter() - start
                    engine_e2e_latency.labels(endpoint=path).observe(duration)

            # Gateway レイテンシ
            if service_name == "gateway":
                duration = time.perf_counter() - start
                gateway_request_latency.labels(method=method, path=path).observe(duration)

            return response

        except Exception as e:
            http_errors_total.labels(
                service=service_name,
                status_code="500"
            ).inc()
            error_reasons_total.labels(
                service=service_name,
                error_category=type(e).__name__
            ).inc()
            raise

    @app.get("/metrics")
    async def metrics_endpoint():
        """Prometheusメトリクスエンドポイント"""
        return Response(
            generate_latest(global_registry),
            media_type=CONTENT_TYPE_LATEST
        )


# =============================================================================
# ビジネスロジック用のヘルパー関数
# =============================================================================

def record_estimator_execution(estimator_name: str, duration_seconds: float):
    """推定器の実行時間を記録"""
    estimator_latency.labels(estimator_name=estimator_name).observe(duration_seconds)

def record_quality_gate_result(gate_name: str, passed: bool):
    """品質ゲートの結果を記録"""
    result = "pass" if passed else "fail"
    gate_pass_rate.labels(gate_name=gate_name, result=result).inc()

def record_cas_score(score: float):
    """CASスコアを記録"""
    cas_score.observe(score)

def record_job_metrics(
    cas_score_value: float,
    sign_consensus: float,
    ci_overlap: float,
    data_health: float,
    dataset_id: str
):
    """ジョブ完了時の総合メトリクスを記録"""
    cas_score.observe(cas_score_value)
    sign_consensus_ratio.observe(sign_consensus)
    ci_overlap_index.observe(ci_overlap)
    data_health_score.labels(dataset_id=dataset_id).set(data_health)

def record_file_processing(file_size_bytes: int, rows: int, duration_seconds: float):
    """ファイル処理のメトリクスを記録"""
    file_size_processed_bytes.observe(file_size_bytes)

    # 10k行あたりの処理時間に正規化
    if rows > 0:
        time_per_10k = (duration_seconds / rows) * 10000
        processing_time_per_10k_rows.observe(time_per_10k)

def record_gpu_metrics(device_id: str, memory_percent: float, utilization_percent: float):
    """GPUメトリクスを記録"""
    gpu_memory_used_percent.labels(device_id=device_id).set(memory_percent)
    gpu_utilization_percent.labels(device_id=device_id).set(utilization_percent)

def record_gpu_error(error_type: str, device_id: str = "0"):
    """GPUエラーを記録"""
    gpu_errors_total.labels(error_type=error_type, device_id=device_id).inc()

def set_queue_depth(depth: int):
    """ジョブキューの深さを設定"""
    job_queue_depth.set(depth)

def set_worker_active_jobs(worker_id: str, count: int):
    """ワーカーのアクティブジョブ数を設定"""
    worker_active_jobs.labels(worker_id=worker_id).set(count)

def record_task_wait_time(wait_seconds: float):
    """タスクの待機時間を記録"""
    worker_task_wait_seconds.observe(wait_seconds)

def record_slo_check(slo_name: str, met: bool):
    """SLOコンプライアンスチェックを記録"""
    result = "met" if met else "violated"
    slo_compliance_checks.labels(slo_name=slo_name, result=result).inc()

def record_rejection(reason: str):
    """Fail-Closedによる拒否を記録"""
    reject_rate_total.labels(reason=reason).inc()
