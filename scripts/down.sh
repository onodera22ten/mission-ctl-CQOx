#!/usr/bin/env bash
set -euo pipefail
docker compose -f docker-compose.grafana.yml down
docker network rm cqox-observe-net 2>/dev/null || true

