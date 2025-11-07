from __future__ import annotations
import time
from typing import Callable

from fastapi import FastAPI, Request
from starlette.responses import Response
from prometheus_client import (
    CollectorRegistry, Counter, Histogram, Gauge,
    CONTENT_TYPE_LATEST, generate_latest,
)

def setup_metrics(app: FastAPI, path: str = "/metrics") -> None:
    """
    アプリに依存しないメトリクス公開ユーティリティ。
    - リクエスト数/レイテンシ/例外回数を収集
    - {path} に Prometheus 形式で公開
    """
    app_name = getattr(app, "title", "app").lower().replace(" ", "_")
    registry = CollectorRegistry()

    req_count = Counter(
        "cqox_http_requests_total", "Total HTTP requests",
        ["app", "method", "path", "status"], registry=registry
    )
    req_latency = Histogram(
        "cqox_request_duration_seconds", "Request duration seconds",
        ["app", "path"], registry=registry
    )
    exceptions = Counter(
        "cqox_exceptions_total", "Unhandled exceptions",
        ["app", "path"], registry=registry
    )
    start_gauge = Gauge(
        "cqox_start_time_seconds", "App start time",
        ["app"], registry=registry
    )
    start_gauge.labels(app_name).set(time.time())

    @app.middleware("http")
    async def _metrics_mw(request: Request, call_next: Callable):
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = getattr(response, "status_code", 200)
            return response
        except Exception:
            exceptions.labels(app_name, request.url.path).inc()
            raise
        finally:
            dur = time.perf_counter() - start
            req_latency.labels(app_name, request.url.path).observe(dur)
            req_count.labels(app_name, request.method, request.url.path, str(status)).inc()

    @app.get(path)
    async def _metrics_endpoint():
        return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)
