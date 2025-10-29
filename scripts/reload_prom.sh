#!/usr/bin/env bash
set -euo pipefail
docker compose -f docker-compose.grafana.yml exec -T prometheus sh -lc 'wget -qO- http://localhost:9090/-/reload'
echo "Prometheus reloaded."

