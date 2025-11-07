#!/usr/bin/env bash
set -euo pipefail
python -m grpc_tools.protoc -I proto   --python_out=backend/engine/generated --grpc_python_out=backend/engine/generated   proto/causal.proto
echo "✓ Generated to backend/engine/generated"
