#!/bin/bash
# Start Gateway with proper PYTHONPATH

cd /home/hirokionodera/cqox-complete_b
export PYTHONPATH=/home/hirokionodera/cqox-complete_b

# Create .engine_url if not exists
if [ ! -f backend/gateway/.engine_url ]; then
    echo "http://localhost:8080" > backend/gateway/.engine_url
fi

# Start gateway
python3 -m uvicorn backend.gateway.app:app --host 0.0.0.0 --port 8082
