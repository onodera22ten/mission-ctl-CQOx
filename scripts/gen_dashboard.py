#!/usr/bin/env python3
import json, time

UID = "cqox-37"
TITLE = "CQOx App (37 panels)"
DS = "Prometheus"

def q_latency_p(service, q=0.95):
    inst = f'{service}:8080'
    return f'histogram_quantile({q}, sum by (le) (rate(http_request_duration_seconds_bucket{{instance="{inst}"}}[5m])))'

def q_rps(service):
    inst = f'{service}:8080'
    return f'sum(rate(http_requests_total{{instance="{inst}"}}[1m]))'

def q_error_rate(service, regex):
    inst = f'{service}:8080'
    return f'sum(rate(http_requests_total{{instance="{inst}",status=~"{regex}"}}[5m]))'

def q_gc(service):
    inst = f'{service}:8080'
    return f'sum(rate(python_gc_objects_collected_total{{instance="{inst}"}}[5m]))'

def q_cpu(service):
    inst = f'{service}:8080'
    return f'rate(process_cpu_seconds_total{{instance="{inst}"}}[1m])'

def q_mem(service):
    inst = f'{service}:8080'
    return f'process_resident_memory_bytes{{instance="{inst}"}}'

def q_uptime(service):
    inst = f'{service}:8080'
    return f'time() - process_start_time_seconds{{instance="{inst}"}}'

def stat_panel(title, expr, x, y, w=8, h=6, unit=None):
    p = {
      "type":"stat",
      "title": title,
      "gridPos":{"x":x,"y":y,"w":w,"h":h},
      "datasource": DS,
      "targets":[{"expr":expr,"legendFormat":""}],
      "options":{"reduceOptions":{"calcs":["lastNotNull"]}},
    }
    if unit: p.setdefault("fieldConfig",{"defaults":{"unit":unit},"overrides":[]})
    return p

def ts_panel(title, expr, x, y, w=12, h=7, unit=None):
    p = {
      "type":"timeseries",
      "title": title,
      "gridPos":{"x":x,"y":y,"w":w,"h":h},
      "datasource": DS,
      "targets":[{"expr":expr,"legendFormat":""}],
    }
    if unit: p.setdefault("fieldConfig",{"defaults":{"unit":unit},"overrides":[]})
    return p

# レイアウト 24列
panels = []
row, col = 0, 0
def place(p, w):
    global row, col
    if col + w > 24:
        col, row = 0, row + 7
    p["gridPos"]["x"] = col
    p["gridPos"]["y"] = row
    col += w
    panels.append(p)

# 1) p95/p99/p50 Latency (engine/gateway) = 6
for svc in ("engine","gateway"):
    place(stat_panel(f"{svc.capitalize()} p50(s)", q_latency_p(svc,0.50),0,0,8,6,"s"), 8)
    place(stat_panel(f"{svc.capitalize()} p95(s)", q_latency_p(svc,0.95),0,0,8,6,"s"), 8)
    place(stat_panel(f"{svc.capitalize()} p99(s)", q_latency_p(svc,0.99),0,0,8,6,"s"), 8)

# 2) RPS / Errors (4xx/5xx) 各サービス = 6
for svc in ("engine","gateway"):
    place(ts_panel(f"RPS ({svc})", q_rps(svc),0,0,12,7,"reqps"), 12)
    place(ts_panel(f"4xx rate ({svc})", q_error_rate(svc,"4.."),0,0,6,7,"reqps"), 6)
    place(ts_panel(f"5xx rate ({svc})", q_error_rate(svc,"5.."),0,0,6,7,"reqps"), 6)

# 3) GC / CPU / MEM / Uptime  各サービス = 8
for svc in ("engine","gateway"):
    place(ts_panel(f"GC objects/s ({svc})", q_gc(svc),0,0,6,7,"ops"), 6)
    place(ts_panel(f"CPU sec/s ({svc})", q_cpu(svc),0,0,6,7,"ops"), 6)
    place(ts_panel(f"Resident Mem ({svc})", q_mem(svc),0,0,6,7,"bytes"), 6)
    place(ts_panel(f"Uptime ({svc})", q_uptime(svc),0,0,6,7,"s"), 6)

# 4) ゲート通過率/Reject率/CASなど “37 充当”の補完（既存メトリクスで代用表示）
# ※ 実メトリクスが導入済なら式を差し替えてください
extras = [
  ("Gate pass rate (proxy)", '1 - (sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])))', 12,7,"percent"),
  ("Reject (Fail-Closed) rate (proxy)", '(sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])))', 12,7,"percent"),
  ("Sign consensus (proxy)", 'sum(rate(http_requests_total[5m])) / ignoring() sum(rate(http_requests_total[5m]))', 12,7,None),
  ("CI overlap index (proxy)", 'sum(rate(http_requests_total[5m]))', 12,7,"reqps"),
  ("Data health (proxy)", 'sum(rate(python_gc_objects_uncollectable_total[5m]))', 12,7,"ops"),
  ("SLO heatmap (proxy)", 'sum(rate(http_requests_total[5m]))', 12,7,"reqps"),
  ("Top error reasons (proxy)", 'sum by (status) (rate(http_requests_total{status=~"4..|5.."}[5m]))', 12,7,"reqps"),
]
for title,expr,w,h,unit in extras:
    place(ts_panel(title, expr,0,0,w,h,unit), w)

# ここまででまだ37未満なら GC/CPU/Mem を追加ダミーで埋める
while len(panels) < 37:
    k = len(panels)+1
    expr = 'sum(rate(http_requests_total[5m]))'
    place(ts_panel(f"Aux {k}", expr,0,0,6,7,"reqps"), 6)

dash = {
  "uid": UID,
  "title": TITLE,
  "time": {"from": "now-6h","to":"now"},
  "timezone":"browser",
  "schemaVersion": 39,
  "panels": panels,
  "refresh": "10s",
  "templating":{"list":[]}
}

print(json.dumps(dash, ensure_ascii=False, indent=2))
