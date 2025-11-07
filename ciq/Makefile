# CQOx Data Quality Pipeline (Plan2)
# Purpose: One-command execution for causal-safe data preparation

VENV = .venv
ACT = source $(VENV)/bin/activate
PYTHON = $(ACT); python3

# Paths
CONTRACT = ciq/contracts/dataset.yaml
RAW_DIR = ciq/data/raw
STAGED = ciq/data/staged/staged.parquet
WAREHOUSE = ciq/warehouse/warehouse.duckdb
PROCESSED = ciq/data/processed/causal_ready.parquet
METRICS = ciq/artifacts/overlap_metrics.json

.PHONY: help init convert dbt prepare test all clean

help:
	@echo "CQOx Data Quality Pipeline (Plan2)"
	@echo ""
	@echo "Targets:"
	@echo "  init       - Create venv and install dependencies"
	@echo "  convert    - Convert multi-format files to Parquet"
	@echo "  dbt        - Run dbt build (staging → curated → features)"
	@echo "  prepare    - Compute causal safety metrics (overlap, SMD)"
	@echo "  test       - Run pytest quality gates"
	@echo "  all        - Run full pipeline (convert → dbt → prepare → test)"
	@echo "  clean      - Remove generated artifacts"

init:
	@echo "[init] Creating venv..."
	python3 -m venv $(VENV)
	$(PYTHON) -m pip install -U pip setuptools wheel
	$(PYTHON) -m pip install \
		duckdb \
		dbt-duckdb \
		pandas \
		polars \
		pyarrow \
		pandera \
		pydantic \
		scikit-learn \
		pytest \
		rich \
		python-magic \
		filetype \
		openpyxl \
		sqlparse \
		pyyaml \
		psycopg2-binary
	@echo "[init] ✓ Dependencies installed"

convert:
	@echo "[convert] Converting multi-format files to Parquet..."
	@if [ ! -d "$(RAW_DIR)" ] || [ -z "$$(ls -A $(RAW_DIR) 2>/dev/null)" ]; then \
		echo "ERROR: No files in $(RAW_DIR)"; \
		exit 1; \
	fi
	$(PYTHON) ciq/scripts/convert_any_to_parquet.py
	@echo "[convert] ✓ Staged: $(STAGED)"

dbt:
	@echo "[dbt] Running dbt build..."
	@if [ ! -f "$(STAGED)" ]; then \
		echo "ERROR: $(STAGED) not found. Run 'make convert' first."; \
		exit 1; \
	fi
	$(ACT); cd ciq/dbt_project && dbt build --profiles-dir .
	@echo "[dbt] ✓ Warehouse: $(WAREHOUSE)"

prepare:
	@echo "[prepare] Computing causal safety metrics..."
	@if [ ! -f "$(WAREHOUSE)" ]; then \
		echo "ERROR: $(WAREHOUSE) not found. Run 'make dbt' first."; \
		exit 1; \
	fi
	$(PYTHON) ciq/scripts/prepare_causal.py
	@echo "[prepare] ✓ Processed: $(PROCESSED)"
	@echo "[prepare] ✓ Metrics: $(METRICS)"

test:
	@echo "[test] Running pytest..."
	$(ACT); pytest -q ciq/tests/
	@echo "[test] ✓ All tests passed"

all: convert dbt prepare test
	@echo ""
	@echo "=========================================="
	@echo "✓ Pipeline complete!"
	@echo "=========================================="
	@echo "  Staged:    $(STAGED)"
	@echo "  Warehouse: $(WAREHOUSE)"
	@echo "  Processed: $(PROCESSED)"
	@echo "  Metrics:   $(METRICS)"
	@echo ""
	@if [ -f "$(METRICS)" ]; then \
		echo "Overlap metrics:"; \
		cat $(METRICS); \
	fi

clean:
	@echo "[clean] Removing generated artifacts..."
	rm -rf ciq/data/staged/* ciq/data/processed/* ciq/artifacts/* ciq/warehouse/*
	rm -rf ciq/dbt_project/target ciq/dbt_project/dbt_packages
	@echo "[clean] ✓ Clean complete"
