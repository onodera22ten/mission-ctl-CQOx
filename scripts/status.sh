#!/usr/bin/env bash
set -euo pipefail

echo "== Prometheus targets =="
curl -s http://localhost:9090/targets \
 | jq '.data.activeTargets | map({job:.labels.job, url:.scrapeUrl, health:.health})'

echo
echo "== Grafana health =="
curl -s http://localhost:3000/api/health | jq .

echo
echo "== Grafana datasources =="
curl -s http://localhost:3000/api/datasources | jq -r '.[]|[.name,.type,.url]|@tsv' || true

echo
echo "== Example QPS (1m) =="
curl -s 'http://localhost:9090/api/v1/query?query=sum(rate(http_server_requests_seconds_count[1m]))' \
 | jq '.data.result'

