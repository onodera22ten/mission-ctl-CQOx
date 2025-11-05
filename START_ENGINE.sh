#!/bin/bash
# Engine起動スクリプト

cd /home/hirokionodera/cqox-complete_c

# 既存プロセス終了
pkill -f "python.*uvicorn.*8080" 2>/dev/null
sleep 1

# Engine起動
MPLBACKEND=Agg \
CQOX_DISABLE_METRICS=1 \
CQOX_DISABLE_TRACING=1 \
python3.11 -m uvicorn backend.engine.server:app \
  --host 0.0.0.0 \
  --port 8080 \
  --log-level warning
