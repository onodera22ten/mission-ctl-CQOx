# backend/db/postgres_async.py
"""
Async PostgreSQL client with connection pooling, retry, and timeout support.
Supports both local PostgreSQL and cloud databases (AWS RDS, GCP Cloud SQL, Azure Database).
"""
import os
import asyncio
from typing import Optional, Dict, List, Any, Union
from contextlib import asynccontextmanager
import logging

try:
    import asyncpg
    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False
    print("Warning: asyncpg not installed. Run: pip install asyncpg")

logger = logging.getLogger(__name__)

# ========================================
# Configuration
# ========================================

class PostgresConfig:
    """PostgreSQL connection configuration with cloud support"""

    def __init__(self):
        # Connection string (fallback to local)
        self.url = os.getenv(
            "POSTGRES_URL",
            "postgresql://cqox:cqox_password@localhost:5432/cqox_db"
        )

        # Cloud-specific configurations
        self.is_cloud = os.getenv("POSTGRES_CLOUD", "false").lower() == "true"
        self.cloud_provider = os.getenv("POSTGRES_CLOUD_PROVIDER", "")  # aws, gcp, azure

        # SSL/TLS configuration for cloud
        self.ssl_mode = os.getenv("POSTGRES_SSL_MODE", "prefer")  # require, verify-ca, verify-full
        self.ssl_cert_path = os.getenv("POSTGRES_SSL_CERT_PATH", "")

        # Connection pool settings
        self.min_pool_size = int(os.getenv("POSTGRES_POOL_MIN", "2"))
        self.max_pool_size = int(os.getenv("POSTGRES_POOL_MAX", "10"))

        # Timeout settings (seconds)
        self.connect_timeout = float(os.getenv("POSTGRES_CONNECT_TIMEOUT", "10.0"))
        self.command_timeout = float(os.getenv("POSTGRES_COMMAND_TIMEOUT", "30.0"))

        # Retry settings
        self.max_retries = int(os.getenv("POSTGRES_MAX_RETRIES", "3"))
        self.retry_delay = float(os.getenv("POSTGRES_RETRY_DELAY", "1.0"))

    def get_ssl_context(self):
        """Get SSL context for cloud connections"""
        if not self.is_cloud or self.ssl_mode == "disable":
            return None

        import ssl
        ssl_context = ssl.create_default_context()

        if self.ssl_mode == "require":
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
        elif self.ssl_mode in ("verify-ca", "verify-full"):
            if self.ssl_cert_path:
                ssl_context.load_verify_locations(self.ssl_cert_path)

        return ssl_context


# ========================================
# Connection Pool Manager
# ========================================

class PostgresPool:
    """Async PostgreSQL connection pool with retry and timeout"""

    def __init__(self, config: Optional[PostgresConfig] = None):
        self.config = config or PostgresConfig()
        self.pool: Optional[asyncpg.Pool] = None
        self._lock = asyncio.Lock()

    async def initialize(self):
        """Initialize connection pool with retry"""
        if not HAS_ASYNCPG:
            logger.error("asyncpg not installed. PostgreSQL features disabled.")
            return False

        async with self._lock:
            if self.pool:
                logger.warning("Pool already initialized")
                return True

            for attempt in range(1, self.config.max_retries + 1):
                try:
                    logger.info(f"[PostgreSQL] Connecting (attempt {attempt}/{self.config.max_retries})...")

                    ssl_context = self.config.get_ssl_context()

                    self.pool = await asyncpg.create_pool(
                        self.config.url,
                        min_size=self.config.min_pool_size,
                        max_size=self.config.max_pool_size,
                        command_timeout=self.config.command_timeout,
                        timeout=self.config.connect_timeout,
                        ssl=ssl_context
                    )

                    # Test connection
                    async with self.pool.acquire() as conn:
                        version = await conn.fetchval("SELECT version()")
                        logger.info(f"[PostgreSQL] Connected successfully: {version[:50]}...")

                    return True

                except Exception as e:
                    logger.error(f"[PostgreSQL] Connection failed (attempt {attempt}): {e}")
                    if attempt < self.config.max_retries:
                        await asyncio.sleep(self.config.retry_delay * attempt)
                    else:
                        logger.error("[PostgreSQL] Max retries exceeded. Pool initialization failed.")
                        return False

    async def close(self):
        """Close connection pool"""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("[PostgreSQL] Pool closed")

    @asynccontextmanager
    async def acquire(self):
        """Acquire connection from pool with timeout"""
        if not self.pool:
            raise RuntimeError("Pool not initialized. Call initialize() first.")

        conn = None
        try:
            conn = await asyncio.wait_for(
                self.pool.acquire(),
                timeout=self.config.connect_timeout
            )
            yield conn
        finally:
            if conn:
                await self.pool.release(conn)

    async def execute(self, query: str, *args, timeout: Optional[float] = None) -> str:
        """Execute a command (INSERT, UPDATE, DELETE) with retry"""
        timeout = timeout or self.config.command_timeout

        for attempt in range(1, self.config.max_retries + 1):
            try:
                async with self.acquire() as conn:
                    result = await asyncio.wait_for(
                        conn.execute(query, *args),
                        timeout=timeout
                    )
                    return result
            except (asyncpg.PostgresError, asyncio.TimeoutError) as e:
                logger.warning(f"[PostgreSQL] Execute failed (attempt {attempt}): {e}")
                if attempt < self.config.max_retries:
                    await asyncio.sleep(self.config.retry_delay)
                else:
                    raise

    async def fetchone(self, query: str, *args, timeout: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Fetch one row as dictionary"""
        timeout = timeout or self.config.command_timeout

        try:
            async with self.acquire() as conn:
                row = await asyncio.wait_for(
                    conn.fetchrow(query, *args),
                    timeout=timeout
                )
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"[PostgreSQL] fetchone error: {e}")
            return None

    async def fetchall(self, query: str, *args, timeout: Optional[float] = None) -> List[Dict[str, Any]]:
        """Fetch all rows as list of dictionaries"""
        timeout = timeout or self.config.command_timeout

        try:
            async with self.acquire() as conn:
                rows = await asyncio.wait_for(
                    conn.fetch(query, *args),
                    timeout=timeout
                )
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"[PostgreSQL] fetchall error: {e}")
            return []

    async def fetchval(self, query: str, *args, column: int = 0, timeout: Optional[float] = None) -> Any:
        """Fetch single value"""
        timeout = timeout or self.config.command_timeout

        try:
            async with self.acquire() as conn:
                value = await asyncio.wait_for(
                    conn.fetchval(query, *args, column=column),
                    timeout=timeout
                )
                return value
        except Exception as e:
            logger.error(f"[PostgreSQL] fetchval error: {e}")
            return None


# ========================================
# High-level Database Operations
# ========================================

class AsyncPostgresClient:
    """High-level async PostgreSQL client with domain-specific operations"""

    def __init__(self, pool: PostgresPool):
        self.pool = pool

    async def insert_dataset(
        self,
        dataset_id: str,
        filename: str,
        rows: int,
        cols: int,
        size: int,
        metadata: dict
    ) -> bool:
        """Insert or update dataset record"""
        query = """
            INSERT INTO datasets (dataset_id, filename, rows_count, columns_count, file_size_bytes, metadata)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (dataset_id) DO UPDATE
            SET uploaded_at = CURRENT_TIMESTAMP, metadata = $6
        """
        try:
            import json
            await self.pool.execute(query, dataset_id, filename, rows, cols, size, json.dumps(metadata))
            return True
        except Exception as e:
            logger.error(f"[PostgreSQL] insert_dataset error: {e}")
            return False

    async def insert_job(self, job_id: str, dataset_id: str, mapping: dict, config: dict) -> bool:
        """Insert analysis job record"""
        query = """
            INSERT INTO analysis_jobs (job_id, dataset_id, mapping, config)
            VALUES ($1, $2, $3, $4)
        """
        try:
            import json
            await self.pool.execute(query, job_id, dataset_id, json.dumps(mapping), json.dumps(config))
            return True
        except Exception as e:
            logger.error(f"[PostgreSQL] insert_job error: {e}")
            return False

    async def update_job(
        self,
        job_id: str,
        status: str,
        results: Optional[dict] = None,
        error: Optional[str] = None
    ) -> bool:
        """Update job status and results"""
        try:
            import json
            if results:
                query = """
                    UPDATE analysis_jobs
                    SET status = $1, completed_at = CURRENT_TIMESTAMP,
                        duration_seconds = EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - started_at)),
                        results = $2
                    WHERE job_id = $3
                """
                await self.pool.execute(query, status, json.dumps(results), job_id)
            elif error:
                query = """
                    UPDATE analysis_jobs
                    SET status = $1, completed_at = CURRENT_TIMESTAMP,
                        duration_seconds = EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - started_at)),
                        error_message = $2
                    WHERE job_id = $3
                """
                await self.pool.execute(query, status, error, job_id)
            else:
                query = "UPDATE analysis_jobs SET status = $1 WHERE job_id = $2"
                await self.pool.execute(query, status, job_id)
            return True
        except Exception as e:
            logger.error(f"[PostgreSQL] update_job error: {e}")
            return False

    async def insert_estimator_result(
        self,
        job_id: str,
        estimator: str,
        tau: float,
        se: float,
        ci_lower: float,
        ci_upper: float,
        p_value: Optional[float],
        exec_time: float
    ) -> bool:
        """Insert estimator result"""
        query = """
            INSERT INTO estimator_results
            (job_id, estimator_name, tau_hat, se, ci_lower, ci_upper, p_value, execution_time_seconds, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'success')
        """
        try:
            await self.pool.execute(query, job_id, estimator, tau, se, ci_lower, ci_upper, p_value, exec_time)
            return True
        except Exception as e:
            logger.error(f"[PostgreSQL] insert_estimator_result error: {e}")
            return False

    async def insert_quality_gate(
        self,
        job_id: str,
        gate_name: str,
        pass_: bool,
        value: float,
        threshold: float,
        message: Optional[str] = None
    ) -> bool:
        """Insert quality gate result"""
        query = """
            INSERT INTO quality_gates (job_id, gate_name, pass, value, threshold, message)
            VALUES ($1, $2, $3, $4, $5, $6)
        """
        try:
            await self.pool.execute(query, job_id, gate_name, pass_, value, threshold, message)
            return True
        except Exception as e:
            logger.error(f"[PostgreSQL] insert_quality_gate error: {e}")
            return False

    async def insert_cas_score(self, job_id: str, overall: float, components: dict, grade: str) -> bool:
        """Insert CAS score"""
        query = """
            INSERT INTO cas_scores
            (job_id, overall_score, gate_pass_score, sign_consensus_score,
             ci_overlap_score, data_health_score, sensitivity_score, grade)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """
        try:
            await self.pool.execute(
                query,
                job_id,
                overall,
                components.get('gate_pass', 0.0),
                components.get('sign_consensus', 0.0),
                components.get('ci_overlap', 0.0),
                components.get('data_health', 0.0),
                components.get('sensitivity', 0.0),
                grade
            )
            return True
        except Exception as e:
            logger.error(f"[PostgreSQL] insert_cas_score error: {e}")
            return False

    async def get_recent_jobs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent jobs with CAS scores"""
        query = "SELECT * FROM recent_jobs_with_cas LIMIT $1"
        return await self.pool.fetchall(query, limit)

    async def get_estimator_stats(self) -> List[Dict[str, Any]]:
        """Get estimator performance statistics"""
        query = "SELECT * FROM estimator_performance_stats"
        return await self.pool.fetchall(query)

    async def get_quality_gate_stats(self) -> List[Dict[str, Any]]:
        """Get quality gate pass rate statistics"""
        query = "SELECT * FROM quality_gate_pass_rates"
        return await self.pool.fetchall(query)


# ========================================
# Global Pool Instance
# ========================================

_global_pool: Optional[PostgresPool] = None

async def get_postgres_pool() -> PostgresPool:
    """Get or create global PostgreSQL pool"""
    global _global_pool
    if _global_pool is None:
        _global_pool = PostgresPool()
        await _global_pool.initialize()
    return _global_pool

async def get_postgres_client() -> AsyncPostgresClient:
    """Get PostgreSQL client with global pool"""
    pool = await get_postgres_pool()
    return AsyncPostgresClient(pool)

async def close_postgres_pool():
    """Close global PostgreSQL pool"""
    global _global_pool
    if _global_pool:
        await _global_pool.close()
        _global_pool = None
