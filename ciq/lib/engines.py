# ciq/lib/engines.py
"""
Database Engine Wrappers

Purpose: Thin wrappers around DuckDB and PostgreSQL for unified interface
Features:
- Context managers for connection handling
- Automatic DataFrame return for SELECTs
- Execution time tracking
"""

from __future__ import annotations

import contextlib
import time
from typing import Any, Dict

import duckdb
import pandas as pd
import psycopg2
import psycopg2.extras


class DuckEngine:
    """DuckDB engine wrapper"""

    def __init__(self, db_path: str = "ciq/warehouse/warehouse.duckdb"):
        self.db_path = db_path

    @contextlib.contextmanager
    def conn(self):
        """Connection context manager"""
        con = duckdb.connect(self.db_path)
        try:
            yield con
        finally:
            con.close()

    def execute(self, sql: str) -> Dict[str, Any]:
        """
        Execute SQL query

        Args:
            sql: SQL query string

        Returns:
            Dict with engine, elapsed, df (for SELECT) or rowcount (for DML)
        """
        t0 = time.time()
        with self.conn() as con:
            cur = con.execute(sql)
            try:
                # Try to fetch as DataFrame
                df = cur.fetch_df()
                return {"engine": "duckdb", "elapsed": time.time() - t0, "df": df}
            except duckdb.IOException:
                # DML/DDL (no result set)
                return {
                    "engine": "duckdb",
                    "elapsed": time.time() - t0,
                    "rowcount": cur.rowcount,
                }


class PGEngine:
    """PostgreSQL engine wrapper"""

    def __init__(self, dsn: str):
        self.dsn = dsn

    @contextlib.contextmanager
    def conn(self):
        """Connection context manager"""
        conn = psycopg2.connect(self.dsn)
        try:
            yield conn
        finally:
            conn.close()

    def execute(self, sql: str) -> Dict[str, Any]:
        """
        Execute SQL query

        Args:
            sql: SQL query string

        Returns:
            Dict with engine, elapsed, df (for SELECT) or rowcount (for DML)
        """
        t0 = time.time()
        with self.conn() as c:
            # Check if SELECT (simple heuristic)
            if sql.lstrip().lower().startswith("select"):
                df = pd.read_sql(sql, c)
                return {"engine": "pg", "elapsed": time.time() - t0, "df": df}
            else:
                # DML/DDL
                with c.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    cur.execute(sql)
                    c.commit()
                    return {
                        "engine": "pg",
                        "elapsed": time.time() - t0,
                        "rowcount": cur.rowcount,
                    }
