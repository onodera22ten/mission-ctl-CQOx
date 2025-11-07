#!/bin/bash
# 分析エンドポイントテスト

DATASET_ID="24b9bac328e947aa809b4aafcf689b76"

echo "=== Testing Analysis Endpoint ==="
echo "Dataset ID: $DATASET_ID"
echo ""

# Test comprehensive analysis via Gateway
echo "[1/2] Testing Gateway → Engine analysis..."
PAYLOAD='{
  "dataset_id": "'$DATASET_ID'",
  "mapping": {
    "y": "y",
    "treatment": "treatment",
    "unit_id": "user_id",
    "time": "date",
    "cost": "cost",
    "log_propensity": "log_propensity"
  },
  "objective": "retail"
}'

echo "Payload:"
echo "$PAYLOAD" | python3 -m json.tool
echo ""

RESULT=$(curl -s -X POST http://localhost:8081/api/analyze/comprehensive \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD" \
  --max-time 30)

if [ $? -eq 0 ]; then
    echo "Analysis result:"
    echo "$RESULT" | python3 -m json.tool 2>/dev/null | head -50 || echo "$RESULT"
else
    echo "✗ Request failed or timed out"
fi
echo ""

echo "=== Test Complete ==="
