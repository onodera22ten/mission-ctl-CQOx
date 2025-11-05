#!/bin/bash
# Gateway起動スクリプト

cd /home/hirokionodera/cqox-complete_c

# 既存プロセス終了
pkill -f "python.*uvicorn.*8081" 2>/dev/null
sleep 1

# Gateway起動
python3.11 -m uvicorn backend.gateway.app:app \
  --host 0.0.0.0 \
  --port 8081 \
  --log-level info
