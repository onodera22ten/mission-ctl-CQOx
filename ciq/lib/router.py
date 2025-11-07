# ciq/lib/router.py
"""
Automatic Engine Router

Purpose: Route queries to PostgreSQL or DuckDB based on heuristics
Features:
- DDL/DML → PG固定 (Fail-close)
- SELECT + Parquet → DuckDB
- SELECT + large data → DuckDB
- API context → PG優先
- Hint comments: /* engine:pg|duckdb */
- Safe fallback (read-only)
"""

from __future__ import annotations

import glob
import os
import re
from pathlib import Path
from typing import Any, Dict

import sqlparse
import yaml

from .engines import DuckEngine, PGEngine

# Regex patterns
HINT_RE = re.compile(r"/\*\s*engine\s*:\s*(pg|duckdb)\s*\*/", re.I)
READ_PARQUET_RE = re.compile(r"read_parquet\s*\(\s*'([^']+)'", re.I)
FROM_TOKEN_RE = re.compile(r"\bfrom\s+([a-zA-Z0-9_\.\"']+)", re.I)


class EngineRouter:
    """
    Automatic engine router with heuristic-based routing

    Routing logic:
    1. Hint comment → override
    2. DDL/DML → PG (固定)
    3. API context → PG (connection pooling, access control)
    4. SELECT + read_parquet() → DuckDB
    5. SELECT + large input → DuckDB
    6. SELECT + API schemas → PG
    7. Default → DuckDB (for SELECT), PG (for others)
    """

    def __init__(
        self,
        pg_dsn: str,
        duck_path: str = "ciq/warehouse/warehouse.duckdb",
        cfg_path: str = "ciq/config/router.yml",
    ):
        self.pg = PGEngine(pg_dsn)
        self.duck = DuckEngine(duck_path)
        self.cfg = yaml.safe_load(Path(cfg_path).read_text())

    def _stmt_type(self, sql: str) -> str:
        """Parse SQL statement type"""
        parsed = sqlparse.parse(sql)
        if not parsed:
            return "unknown"
        return parsed[0].get_type().lower()  # 'select', 'insert', ...

    def _total_input_mb(self, sql: str) -> float:
        """Calculate total input size from read_parquet() calls"""
        mb = 0.0
        for m in READ_PARQUET_RE.finditer(sql):
            pat = m.group(1)
            for p in glob.glob(pat):
                if os.path.isfile(p):
                    mb += os.path.getsize(p) / 1024 / 1024
        return mb

    def _schemas_in_query(self, sql: str) -> set[str]:
        """Extract schema names from FROM clauses"""
        schemas = set()
        for m in FROM_TOKEN_RE.finditer(sql):
            token = m.group(1).strip('"\'')
            if "." in token:
                schemas.add(token.split(".")[0])
        return schemas

    def decide(self, sql: str, context: str = "batch") -> str:
        """
        Decide which engine to use

        Args:
            sql: SQL query string
            context: "batch" or "api"

        Returns:
            "pg" or "duckdb"
        """
        # 1. Hint comment override
        hint = HINT_RE.search(sql)
        if hint:
            return hint.group(1).lower()

        typ = self._stmt_type(sql)
        cfg = self.cfg["defaults"]
        rules = self.cfg["rules"]
        api_schemas = set(cfg["api_schemas"])

        # 2. DDL/DML → PG固定 (Fail-close, no fallback)
        if typ in {"insert", "update", "delete", "create", "alter", "drop"}:
            return "pg"

        # 3. API context → PG優先
        if context == "api":
            return "pg"

        # 4. Parquet直接参照 → DuckDB
        if rules.get("prefer_duckdb_if_parquet") and READ_PARQUET_RE.search(sql):
            return "duckdb"

        # 5. 大きめSELECT → DuckDB
        if typ == "select" and self._total_input_mb(sql) >= cfg["large_select_mb"]:
            return "duckdb"

        # 6. API系スキーマ参照 → PG
        if self._schemas_in_query(sql) & api_schemas:
            return "pg"

        # 7. Default
        return "duckdb" if typ == "select" else "pg"

    def execute(self, sql: str, context: str = "batch") -> Dict[str, Any]:
        """
        Execute SQL with automatic engine selection

        Args:
            sql: SQL query string
            context: "batch" or "api"

        Returns:
            Dict with engine, elapsed, df/rowcount, chosen, fallback (if applicable)

        Raises:
            RuntimeError: If both engines fail
        """
        choice = self.decide(sql, context=context)

        try:
            if choice == "duckdb":
                result = self.duck.execute(sql)
            else:
                result = self.pg.execute(sql)
            result["chosen"] = choice
            return result

        except Exception as e:
            # Fallback only for SELECT (read-only, safe)
            if (
                self.cfg["rules"].get("allow_select_fallback", True)
                and self._stmt_type(sql) == "select"
            ):
                other = "pg" if choice == "duckdb" else "duckdb"
                try:
                    if other == "pg":
                        result = self.pg.execute(sql)
                    else:
                        result = self.duck.execute(sql)
                    result["chosen"] = choice
                    result["fallback"] = other
                    result["error"] = str(e)
                    return result
                except Exception as e2:
                    raise RuntimeError(f"Both engines failed: {e} / {e2}")
            raise
