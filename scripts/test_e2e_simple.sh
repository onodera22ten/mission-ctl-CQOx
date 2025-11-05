#!/bin/bash
# E2E Test Script for CQOx System

echo "=========================================="
echo "CQOx E2E Test (SSOT準拠)"
echo "=========================================="

# Step 1: Health Check
echo ""
echo "[1/4] Health Check..."
HEALTH=$(curl -s http://localhost:8080/api/health)
echo "Response: $HEALTH"

if echo "$HEALTH" | grep -q '"ok":true'; then
    echo "✓ Health check passed"
else
    echo "✗ Health check failed"
    exit 1
fi

# Step 2: Submit Analysis
echo ""
echo "[2/4] Submitting analysis request..."
RESPONSE=$(curl -s -w '\n%{http_code}' -X POST http://localhost:8080/api/analyze/comprehensive \
  -H 'content-type: application/json' \
  -d '{
    "df_path": "data/realistic_retail_5k.csv",
    "mapping": {
      "y": "y",
      "treatment": "treatment",
      "time": "date"
    }
  }')

# Extract HTTP code (last line)
HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

echo "HTTP Code: $HTTP_CODE"

if [ "$HTTP_CODE" = "200" ]; then
    echo "✓ API returned 200"
else
    echo "✗ API returned $HTTP_CODE"
    echo "Response body:"
    echo "$BODY" | head -20
    exit 1
fi

# Step 3: Parse Response
echo ""
echo "[3/4] Checking response content..."

# Extract key fields using grep (避免jq依赖)
STATUS=$(echo "$BODY" | grep -o '"status":"[^"]*"' | cut -d':' -f2 | tr -d '"')
JOB_ID=$(echo "$BODY" | grep -o '"job_id":"[^"]*"' | cut -d':' -f2 | tr -d '"')
DECISION_CARD=$(echo "$BODY" | grep -o '"decision_card":"[^"]*"' | cut -d':' -f2 | tr -d '"')

echo "Status: $STATUS"
echo "Job ID: $JOB_ID"
echo "Decision Card: $DECISION_CARD"

if [ "$STATUS" = "completed" ]; then
    echo "✓ Status is 'completed'"
else
    echo "✗ Status is not 'completed': $STATUS"
    exit 1
fi

# Step 4: Verify Decision Card
echo ""
echo "[4/4] Verifying Decision Card PDF..."

if [ -f "$DECISION_CARD" ]; then
    SIZE=$(ls -lh "$DECISION_CARD" | awk '{print $5}')
    echo "✓ Decision Card exists: $DECISION_CARD ($SIZE)"
else
    echo "✗ Decision Card not found: $DECISION_CARD"
    exit 1
fi

# Summary
echo ""
echo "=========================================="
echo "✓ E2E Test PASSED"
echo "=========================================="
echo "Job ID: $JOB_ID"
echo "Decision Card: $DECISION_CARD"
echo ""
echo "To view results:"
echo "  ls -lh jobs/$JOB_ID/"
echo "  ls -lh exports/$JOB_ID/"
