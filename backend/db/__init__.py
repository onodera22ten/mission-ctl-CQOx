# backend/db/__init__.py
"""
Database layer with support for:
- Async PostgreSQL with connection pooling (asyncpg)
- SQLAlchemy ORM models
- Cloud database configuration (AWS RDS, GCP Cloud SQL, Azure)
- Redis caching
"""

# Async PostgreSQL
from .postgres_async import (
    PostgresPool,
    PostgresConfig,
    AsyncPostgresClient,
    get_postgres_pool,
    get_postgres_client,
    close_postgres_pool
)

# SQLAlchemy Models
from .models import (
    Base,
    Dataset,
    AnalysisJob,
    EstimatorResult,
    QualityGate,
    CASScore,
    ObservabilityMetric,
    AuditLog,
    DomainInferenceCache,
    create_tables,
    drop_tables
)

# Cloud configuration
from .cloud_config import (
    CloudDBConfig,
    get_aws_rds_config,
    get_gcp_cloud_sql_config,
    get_azure_postgres_config,
    get_cloud_db_config,
    get_postgres_url
)

# Legacy sync client (deprecated, use postgres_async instead)
from .postgres_client import PostgresClient, postgres_client

# Redis
from .redis_client import RedisClient, redis_client

__all__ = [
    # Async PostgreSQL
    "PostgresPool",
    "PostgresConfig",
    "AsyncPostgresClient",
    "get_postgres_pool",
    "get_postgres_client",
    "close_postgres_pool",
    # SQLAlchemy Models
    "Base",
    "Dataset",
    "AnalysisJob",
    "EstimatorResult",
    "QualityGate",
    "CASScore",
    "ObservabilityMetric",
    "AuditLog",
    "DomainInferenceCache",
    "create_tables",
    "drop_tables",
    # Cloud config
    "CloudDBConfig",
    "get_aws_rds_config",
    "get_gcp_cloud_sql_config",
    "get_azure_postgres_config",
    "get_cloud_db_config",
    "get_postgres_url",
    # Legacy
    "PostgresClient",
    "postgres_client",
    "RedisClient",
    "redis_client",
]
