# backend/db/cloud_config.py
"""
Cloud database configuration helpers for AWS RDS, GCP Cloud SQL, and Azure Database.
"""
import os
from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class CloudDBConfig:
    """Cloud database connection configuration"""
    provider: str  # aws, gcp, azure
    host: str
    port: int
    database: str
    user: str
    password: str
    ssl_mode: str = "require"
    ssl_cert_path: Optional[str] = None
    connection_timeout: int = 10
    extra_params: Dict[str, str] = None

    def to_url(self) -> str:
        """Generate PostgreSQL connection URL"""
        base_url = f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

        params = []
        if self.ssl_mode and self.ssl_mode != "disable":
            params.append(f"sslmode={self.ssl_mode}")
        if self.ssl_cert_path:
            params.append(f"sslrootcert={self.ssl_cert_path}")
        if self.connection_timeout:
            params.append(f"connect_timeout={self.connection_timeout}")

        if self.extra_params:
            params.extend([f"{k}={v}" for k, v in self.extra_params.items()])

        if params:
            base_url += "?" + "&".join(params)

        return base_url


# ========================================
# AWS RDS Configuration
# ========================================

def get_aws_rds_config() -> Optional[CloudDBConfig]:
    """
    Get AWS RDS PostgreSQL configuration from environment variables.

    Required environment variables:
    - AWS_RDS_HOST
    - AWS_RDS_DATABASE
    - AWS_RDS_USER
    - AWS_RDS_PASSWORD

    Optional:
    - AWS_RDS_PORT (default: 5432)
    - AWS_RDS_SSL_MODE (default: require)
    - AWS_RDS_SSL_CERT_PATH
    """
    host = os.getenv("AWS_RDS_HOST")
    if not host:
        return None

    return CloudDBConfig(
        provider="aws",
        host=host,
        port=int(os.getenv("AWS_RDS_PORT", "5432")),
        database=os.getenv("AWS_RDS_DATABASE", "cqox_db"),
        user=os.getenv("AWS_RDS_USER", "cqox"),
        password=os.getenv("AWS_RDS_PASSWORD", ""),
        ssl_mode=os.getenv("AWS_RDS_SSL_MODE", "require"),
        ssl_cert_path=os.getenv("AWS_RDS_SSL_CERT_PATH"),
        connection_timeout=int(os.getenv("AWS_RDS_TIMEOUT", "10")),
    )


# ========================================
# GCP Cloud SQL Configuration
# ========================================

def get_gcp_cloud_sql_config() -> Optional[CloudDBConfig]:
    """
    Get GCP Cloud SQL PostgreSQL configuration from environment variables.

    Two connection modes supported:

    1. Public IP with SSL:
       - GCP_CLOUD_SQL_HOST
       - GCP_CLOUD_SQL_DATABASE
       - GCP_CLOUD_SQL_USER
       - GCP_CLOUD_SQL_PASSWORD
       - GCP_CLOUD_SQL_SSL_CERT_PATH (server-ca.pem)

    2. Unix socket (Cloud SQL Proxy):
       - GCP_CLOUD_SQL_INSTANCE (project:region:instance)
       - GCP_CLOUD_SQL_DATABASE
       - GCP_CLOUD_SQL_USER
       - GCP_CLOUD_SQL_PASSWORD
    """
    # Check for Unix socket mode (Cloud SQL Proxy)
    instance = os.getenv("GCP_CLOUD_SQL_INSTANCE")
    if instance:
        # Unix socket path: /cloudsql/{instance}
        socket_path = f"/cloudsql/{instance}"
        return CloudDBConfig(
            provider="gcp",
            host=socket_path,
            port=5432,  # Not used for Unix sockets
            database=os.getenv("GCP_CLOUD_SQL_DATABASE", "cqox_db"),
            user=os.getenv("GCP_CLOUD_SQL_USER", "cqox"),
            password=os.getenv("GCP_CLOUD_SQL_PASSWORD", ""),
            ssl_mode="disable",  # Not needed for Unix sockets
            extra_params={"host": socket_path}
        )

    # Public IP mode
    host = os.getenv("GCP_CLOUD_SQL_HOST")
    if not host:
        return None

    return CloudDBConfig(
        provider="gcp",
        host=host,
        port=int(os.getenv("GCP_CLOUD_SQL_PORT", "5432")),
        database=os.getenv("GCP_CLOUD_SQL_DATABASE", "cqox_db"),
        user=os.getenv("GCP_CLOUD_SQL_USER", "cqox"),
        password=os.getenv("GCP_CLOUD_SQL_PASSWORD", ""),
        ssl_mode=os.getenv("GCP_CLOUD_SQL_SSL_MODE", "verify-ca"),
        ssl_cert_path=os.getenv("GCP_CLOUD_SQL_SSL_CERT_PATH"),
        connection_timeout=int(os.getenv("GCP_CLOUD_SQL_TIMEOUT", "10")),
    )


# ========================================
# Azure Database for PostgreSQL Configuration
# ========================================

def get_azure_postgres_config() -> Optional[CloudDBConfig]:
    """
    Get Azure Database for PostgreSQL configuration from environment variables.

    Required environment variables:
    - AZURE_POSTGRES_HOST (e.g., myserver.postgres.database.azure.com)
    - AZURE_POSTGRES_DATABASE
    - AZURE_POSTGRES_USER (format: username@servername)
    - AZURE_POSTGRES_PASSWORD

    Optional:
    - AZURE_POSTGRES_PORT (default: 5432)
    - AZURE_POSTGRES_SSL_MODE (default: require)
    """
    host = os.getenv("AZURE_POSTGRES_HOST")
    if not host:
        return None

    return CloudDBConfig(
        provider="azure",
        host=host,
        port=int(os.getenv("AZURE_POSTGRES_PORT", "5432")),
        database=os.getenv("AZURE_POSTGRES_DATABASE", "cqox_db"),
        user=os.getenv("AZURE_POSTGRES_USER", "cqox"),
        password=os.getenv("AZURE_POSTGRES_PASSWORD", ""),
        ssl_mode=os.getenv("AZURE_POSTGRES_SSL_MODE", "require"),
        connection_timeout=int(os.getenv("AZURE_POSTGRES_TIMEOUT", "10")),
    )


# ========================================
# Auto-detect Cloud Provider
# ========================================

def get_cloud_db_config() -> Optional[CloudDBConfig]:
    """
    Auto-detect and return cloud database configuration.
    Checks in order: AWS RDS, GCP Cloud SQL, Azure PostgreSQL.
    """
    # Try AWS RDS
    config = get_aws_rds_config()
    if config:
        return config

    # Try GCP Cloud SQL
    config = get_gcp_cloud_sql_config()
    if config:
        return config

    # Try Azure PostgreSQL
    config = get_azure_postgres_config()
    if config:
        return config

    return None


# ========================================
# Connection String Helper
# ========================================

def get_postgres_url() -> str:
    """
    Get PostgreSQL connection URL.
    Priority:
    1. POSTGRES_URL environment variable
    2. Cloud provider auto-detection
    3. Local PostgreSQL (default)
    """
    # Explicit URL override
    url = os.getenv("POSTGRES_URL")
    if url:
        return url

    # Cloud auto-detection
    cloud_config = get_cloud_db_config()
    if cloud_config:
        return cloud_config.to_url()

    # Local default
    return "postgresql://cqox:cqox_password@localhost:5432/cqox_db"


# ========================================
# Example Environment Variable Templates
# ========================================

AWS_RDS_EXAMPLE = """
# AWS RDS PostgreSQL
export AWS_RDS_HOST="mydb.abc123.us-east-1.rds.amazonaws.com"
export AWS_RDS_DATABASE="cqox_db"
export AWS_RDS_USER="cqox"
export AWS_RDS_PASSWORD="secure_password_here"
export AWS_RDS_SSL_MODE="require"
export AWS_RDS_SSL_CERT_PATH="/path/to/rds-ca-bundle.pem"
"""

GCP_CLOUD_SQL_EXAMPLE = """
# GCP Cloud SQL PostgreSQL (Public IP)
export GCP_CLOUD_SQL_HOST="35.123.456.789"
export GCP_CLOUD_SQL_DATABASE="cqox_db"
export GCP_CLOUD_SQL_USER="cqox"
export GCP_CLOUD_SQL_PASSWORD="secure_password_here"
export GCP_CLOUD_SQL_SSL_MODE="verify-ca"
export GCP_CLOUD_SQL_SSL_CERT_PATH="/path/to/server-ca.pem"

# OR via Cloud SQL Proxy (Unix socket)
export GCP_CLOUD_SQL_INSTANCE="myproject:us-central1:myinstance"
export GCP_CLOUD_SQL_DATABASE="cqox_db"
export GCP_CLOUD_SQL_USER="cqox"
export GCP_CLOUD_SQL_PASSWORD="secure_password_here"
"""

AZURE_POSTGRES_EXAMPLE = """
# Azure Database for PostgreSQL
export AZURE_POSTGRES_HOST="myserver.postgres.database.azure.com"
export AZURE_POSTGRES_DATABASE="cqox_db"
export AZURE_POSTGRES_USER="cqox@myserver"
export AZURE_POSTGRES_PASSWORD="secure_password_here"
export AZURE_POSTGRES_SSL_MODE="require"
"""
