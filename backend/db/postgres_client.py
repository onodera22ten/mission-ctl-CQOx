# backend/db/postgres_client.py
import os
from typing import Optional, Dict, List, Any
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor, Json
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False
    print("Warning: psycopg2 not installed. PostgreSQL features disabled.")

POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://cqox:cqox_password@localhost:5432/cqox_db")

class PostgresClient:
    def __init__(self):
        self.conn = None
        if HAS_PSYCOPG2:
            try:
                self.conn = psycopg2.connect(POSTGRES_URL)
            except Exception as e:
                print(f"PostgreSQL connection error: {e}")

    def execute(self, query: str, params: Optional[tuple] = None) -> bool:
        """Execute a query (INSERT, UPDATE, DELETE)"""
        if not self.conn:
            return False
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, params)
            self.conn.commit()
            return True
        except Exception as e:
            self.conn.rollback()
            print(f"PostgreSQL execute error: {e}")
            return False

    def fetchone(self, query: str, params: Optional[tuple] = None) -> Optional[Dict[str, Any]]:
        """Fetch one row as dictionary"""
        if not self.conn:
            return None
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                result = cur.fetchone()
                return dict(result) if result else None
        except Exception as e:
            print(f"PostgreSQL fetchone error: {e}")
            return None

    def fetchall(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """Fetch all rows as list of dictionaries"""
        if not self.conn:
            return []
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                results = cur.fetchall()
                return [dict(row) for row in results] if results else []
        except Exception as e:
            print(f"PostgreSQL fetchall error: {e}")
            return []

    def insert_dataset(self, dataset_id: str, filename: str, rows: int, cols: int, size: int, metadata: dict) -> bool:
        """Insert dataset record"""
        query = """
            INSERT INTO datasets (dataset_id, filename, rows_count, columns_count, file_size_bytes, metadata)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (dataset_id) DO UPDATE
            SET uploaded_at = CURRENT_TIMESTAMP
        """
        return self.execute(query, (dataset_id, filename, rows, cols, size, Json(metadata)))

    def insert_job(self, job_id: str, dataset_id: str, mapping: dict, config: dict) -> bool:
        """Insert analysis job record"""
        query = """
            INSERT INTO analysis_jobs (job_id, dataset_id, mapping, config)
            VALUES (%s, %s, %s, %s)
        """
        return self.execute(query, (job_id, dataset_id, Json(mapping), Json(config)))

    def update_job(self, job_id: str, status: str, results: Optional[dict] = None,
                   error: Optional[str] = None) -> bool:
        """Update job status and results"""
        if results:
            query = """
                UPDATE analysis_jobs
                SET status = %s, completed_at = CURRENT_TIMESTAMP,
                    duration_seconds = EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - started_at)),
                    results = %s
                WHERE job_id = %s
            """
            return self.execute(query, (status, Json(results), job_id))
        elif error:
            query = """
                UPDATE analysis_jobs
                SET status = %s, completed_at = CURRENT_TIMESTAMP,
                    duration_seconds = EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - started_at)),
                    error_message = %s
                WHERE job_id = %s
            """
            return self.execute(query, (status, error, job_id))
        else:
            query = "UPDATE analysis_jobs SET status = %s WHERE job_id = %s"
            return self.execute(query, (status, job_id))

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Fetch job results by job_id"""
        query = "SELECT results FROM analysis_jobs WHERE job_id = %s"
        result = self.fetchone(query, (job_id,))
        if result and result.get("results"):
            return result["results"]
        return None

    def insert_estimator_result(self, job_id: str, estimator: str, tau: float, se: float,
                                ci_lower: float, ci_upper: float, exec_time: float) -> bool:
        """Insert estimator result"""
        query = """
            INSERT INTO estimator_results
            (job_id, estimator_name, tau_hat, se, ci_lower, ci_upper, execution_time_seconds, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'success')
        """
        return self.execute(query, (job_id, estimator, tau, se, ci_lower, ci_upper, exec_time))

    def insert_quality_gate(self, job_id: str, gate_name: str, pass_: bool, value: float, threshold: float) -> bool:
        """Insert quality gate result"""
        query = """
            INSERT INTO quality_gates (job_id, gate_name, pass, value, threshold)
            VALUES (%s, %s, %s, %s, %s)
        """
        return self.execute(query, (job_id, gate_name, pass_, value, threshold))

    def insert_cas_score(self, job_id: str, overall: float, components: dict, grade: str) -> bool:
        """Insert CAS score"""
        query = """
            INSERT INTO cas_scores
            (job_id, overall_score, gate_pass_score, sign_consensus_score,
             ci_overlap_score, data_health_score, sensitivity_score, grade)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        return self.execute(query, (
            job_id, overall,
            components.get('gate_pass', 0),
            components.get('sign_consensus', 0),
            components.get('ci_overlap', 0),
            components.get('data_health', 0),
            components.get('sensitivity', 0),
            grade
        ))

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

# Global instance
postgres_client = PostgresClient()
