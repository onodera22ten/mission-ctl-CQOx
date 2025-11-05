#!/bin/bash
# E2E接続テスト: Gateway → Engine

echo "=== CQOx E2E Connection Test ==="
echo ""

# Engine health check
echo "[1/4] Engine Health Check (8080)..."
ENGINE_HEALTH=$(curl -s http://localhost:8080/api/health)
echo "  $ENGINE_HEALTH"
echo ""

# Gateway health check
echo "[2/4] Gateway Health Check (8081)..."
GATEWAY_HEALTH=$(curl -s http://localhost:8081/api/health)
echo "  $GATEWAY_HEALTH"
echo ""

# Test file upload
echo "[3/4] Testing file upload to Gateway..."
TEST_FILE="data/uploads/ca520a8830834a098a36cf9402d8e507_mini_retail_complete.csv"
if [ -f "$TEST_FILE" ]; then
    UPLOAD_RESULT=$(curl -s -X POST http://localhost:8081/api/upload \
        -F "file=@$TEST_FILE" \
        -F "filename=test_mini_retail.csv")
    echo "  Upload result:"
    echo "  $UPLOAD_RESULT" | python3 -m json.tool 2>/dev/null || echo "  $UPLOAD_RESULT"
else
    echo "  ✗ Test file not found: $TEST_FILE"
fi
echo ""

# Test column inference
echo "[4/4] Testing column inference..."
DATA_ID=$(echo "$UPLOAD_RESULT" | python3 -c "import sys, json; print(json.load(sys.stdin)['data_id'])" 2>/dev/null)
if [ ! -z "$DATA_ID" ]; then
    INFER_RESULT=$(curl -s -X POST http://localhost:8081/api/roles/infer \
        -H "Content-Type: application/json" \
        -d "{\"data_id\": \"$DATA_ID\"}")
    echo "  Inference result:"
    echo "  $INFER_RESULT" | python3 -m json.tool 2>/dev/null | head -30
else
    echo "  ✗ No data_id available"
fi
echo ""

echo "=== Test Complete ==="
