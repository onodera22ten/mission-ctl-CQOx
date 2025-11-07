# ciq/tests/test_router.py
"""
Router decision logic tests

Purpose: Verify automatic engine selection heuristics
"""

import pytest

from ciq.lib.router import EngineRouter


@pytest.fixture
def router():
    """Create router with dummy DSN"""
    return EngineRouter(
        pg_dsn="postgresql://localhost/test",
        duck_path=":memory:",  # In-memory DuckDB
        cfg_path="ciq/config/router.yml",
    )


def test_insert_goes_pg(router):
    """DDL/DML should always go to PostgreSQL"""
    assert router.decide("INSERT INTO public.t(a) VALUES(1)") == "pg"


def test_parquet_select_duckdb(router):
    """SELECT with read_parquet() should go to DuckDB"""
    assert (
        router.decide("SELECT * FROM read_parquet('ciq/data/staged/*.parquet')")
        == "duckdb"
    )


def test_hint_overrides(router):
    """Hint comment should override decision"""
    assert router.decide("/* engine:pg */ SELECT 1") == "pg"
    assert router.decide("/* engine:duckdb */ SELECT 1") == "duckdb"


def test_api_context_prefers_pg(router):
    """API context should prefer PostgreSQL"""
    assert router.decide("SELECT * FROM users", context="api") == "pg"


def test_batch_select_default_duckdb(router):
    """Batch SELECT without special conditions should go to DuckDB"""
    assert router.decide("SELECT 1", context="batch") == "duckdb"


def test_ddl_always_pg(router):
    """DDL should always go to PostgreSQL (Fail-close)"""
    assert router.decide("CREATE TABLE t (id INT)") == "pg"
    assert router.decide("ALTER TABLE t ADD COLUMN name TEXT") == "pg"
    assert router.decide("DROP TABLE t") == "pg"


def test_dml_always_pg(router):
    """DML should always go to PostgreSQL (Fail-close)"""
    assert router.decide("UPDATE t SET a=1") == "pg"
    assert router.decide("DELETE FROM t WHERE id=1") == "pg"
