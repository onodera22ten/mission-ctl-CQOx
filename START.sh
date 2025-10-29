#!/bin/bash
# CQOx-Complete Startup Script

echo "=== CQOx-Complete Startup ==="
echo ""

# プロジェクトディレクトリ
cd "$(dirname "$0")"
PROJECT_ROOT=$(pwd)

echo "[1/4] Stopping existing processes..."
pkill -f "uvicorn.*engine" 2>/dev/null
pkill -f "uvicorn.*gateway" 2>/dev/null
pkill -f "vite.*frontend" 2>/dev/null
sleep 2

echo "[2/4] Starting Engine (port 8080)..."
cd "$PROJECT_ROOT"
nohup python3 -m uvicorn backend.engine.server:app --host 0.0.0.0 --port 8080 > logs/engine.log 2>&1 &
ENGINE_PID=$!
echo "Engine PID: $ENGINE_PID"
sleep 3

echo "[3/4] Starting Gateway (port 8081)..."
nohup python3 -m uvicorn backend.gateway.app:app --host 0.0.0.0 --port 8081 > logs/gateway.log 2>&1 &
GATEWAY_PID=$!
echo "Gateway PID: $GATEWAY_PID"
sleep 3

echo "[4/4] Starting Frontend (port 4000)..."
cd "$PROJECT_ROOT/frontend"
nohup npm run dev > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"

cd "$PROJECT_ROOT"
mkdir -p logs
echo "$ENGINE_PID" > logs/engine.pid
echo "$GATEWAY_PID" > logs/gateway.pid
echo "$FRONTEND_PID" > logs/frontend.pid

echo ""
echo "=== Services Started ==="
echo "Engine:   http://localhost:8080"
echo "Gateway:  http://localhost:8081"
echo "Frontend: http://localhost:4000"
echo ""
echo "Check logs:"
echo "  tail -f logs/engine.log"
echo "  tail -f logs/gateway.log"
echo "  tail -f logs/frontend.log"
echo ""
echo "Health check:"
sleep 3
curl -s http://localhost:8080/api/health && echo " ← Engine OK" || echo " ← Engine FAIL"
curl -s http://localhost:8081/api/health && echo " ← Gateway OK" || echo " ← Gateway FAIL"
