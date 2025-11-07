# backend/observability/tracing.py
"""
OpenTelemetry Distributed Tracing Integration
Google SRE Best Practice: Full request path visibility
"""
import logging
from typing import Optional

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor

logger = logging.getLogger(__name__)

def setup_opentelemetry(
    service_name: str,
    otlp_endpoint: Optional[str] = None,
    jaeger_endpoint: Optional[str] = None,
    enable_console: bool = False
):
    """
    Setup OpenTelemetry distributed tracing

    Google SRE Practice:
    - Trace every request across all services
    - Identify latency bottlenecks
    - Visualize error propagation

    Args:
        service_name: Name of the service (gateway, engine, etc.)
        otlp_endpoint: OTLP collector endpoint (e.g., "http://otel-collector:4317")
        jaeger_endpoint: Jaeger agent endpoint (e.g., "localhost:6831")
        enable_console: Enable console export for development
    """

    # Create resource with service name
    resource = Resource(attributes={
        SERVICE_NAME: service_name
    })

    # Create tracer provider
    tracer_provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(tracer_provider)

    # Add OTLP exporter (production: send to OpenTelemetry Collector)
    if otlp_endpoint:
        try:
            otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            logger.info(f"[Tracing] OTLP exporter enabled: {otlp_endpoint}")
        except Exception as e:
            logger.warning(f"[Tracing] Failed to setup OTLP exporter: {e}")

    # Add Jaeger exporter (development: direct to Jaeger UI)
    if jaeger_endpoint:
        try:
            jaeger_exporter = JaegerExporter(
                agent_host_name=jaeger_endpoint.split(":")[0],
                agent_port=int(jaeger_endpoint.split(":")[1]),
            )
            tracer_provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))
            logger.info(f"[Tracing] Jaeger exporter enabled: {jaeger_endpoint}")
        except Exception as e:
            logger.warning(f"[Tracing] Failed to setup Jaeger exporter: {e}")

    # Console exporter for development
    if enable_console:
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter
        console_exporter = ConsoleSpanExporter()
        tracer_provider.add_span_processor(BatchSpanProcessor(console_exporter))
        logger.info("[Tracing] Console exporter enabled")

    # Auto-instrument libraries
    try:
        HTTPXClientInstrumentor().instrument()
        logger.info("[Tracing] HTTPX instrumentation enabled")
    except Exception as e:
        logger.warning(f"[Tracing] HTTPX instrumentation failed: {e}")

    try:
        RedisInstrumentor().instrument()
        logger.info("[Tracing] Redis instrumentation enabled")
    except Exception as e:
        logger.warning(f"[Tracing] Redis instrumentation failed: {e}")

    try:
        Psycopg2Instrumentor().instrument()
        logger.info("[Tracing] Psycopg2 instrumentation enabled")
    except Exception as e:
        logger.warning(f"[Tracing] Psycopg2 instrumentation failed: {e}")

    logger.info(f"[Tracing] OpenTelemetry setup complete for service: {service_name}")

def instrument_fastapi(app, service_name: str):
    """
    Instrument FastAPI application with OpenTelemetry

    This automatically creates spans for:
    - HTTP requests (method, path, status)
    - Request/response headers
    - Errors and exceptions

    Args:
        app: FastAPI application instance
        service_name: Name of the service
    """
    try:
        FastAPIInstrumentor.instrument_app(app)
        logger.info(f"[Tracing] FastAPI instrumented for {service_name}")
    except Exception as e:
        logger.warning(f"[Tracing] FastAPI instrumentation failed: {e}")

# Convenience function for creating custom spans
def get_tracer(name: str = __name__):
    """
    Get tracer for creating custom spans

    Usage:
        from backend.observability.tracing import get_tracer

        tracer = get_tracer(__name__)

        with tracer.start_as_current_span("custom_operation") as span:
            span.set_attribute("key", "value")
            # ... your code ...
    """
    return trace.get_tracer(name)
