#!/usr/bin/env python3
"""
Grafana 37パネルダッシュボード生成スクリプト
PDFの仕様に基づいて37パネルの可観測性ダッシュボードを生成
"""
import json
from pathlib import Path

def create_panel(panel_id, title, description, x, y, w, h, query, visualization="timeseries", unit=None):
    """Grafanaパネルを生成"""
    panel = {
        "id": panel_id,
        "title": title,
        "description": description,
        "type": visualization,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "targets": [{
            "expr": query,
            "refId": "A",
            "datasource": {"type": "prometheus", "uid": "prometheus"}
        }],
        "options": {},
        "fieldConfig": {
            "defaults": {
                "custom": {},
                "mappings": [],
                "thresholds": {
                    "mode": "absolute",
                    "steps": [
                        {"color": "green", "value": None},
                        {"color": "yellow", "value": 80},
                        {"color": "red", "value": 90}
                    ]
                }
            },
            "overrides": []
        }
    }

    if unit:
        panel["fieldConfig"]["defaults"]["unit"] = unit

    return panel

def generate_dashboard():
    """37パネルのダッシュボードを生成"""
    panels = []

    # パネルのグリッド位置を計算（24列グリッド、各行8単位高さ）
    row_height = 8
    col_width = 6  # 各パネル幅（4パネル/行）

    # ==========================================================================
    # Row 1: レイテンシメトリクス (パネル 1-4)
    # ==========================================================================
    y = 0

    # パネル1: Engine E2E Latency p50/p95/p99
    panels.append(create_panel(
        1, "Engine E2E Latency (p50/p95/p99)",
        "Engine end-to-end request latency percentiles",
        0, y, col_width, row_height,
        'histogram_quantile(0.5, rate(cqox_engine_e2e_duration_seconds_bucket[5m]))',
        unit="s"
    ))

    # パネル2: Gateway Request Latency p50/p95
    panels.append(create_panel(
        2, "Gateway Request Latency (p50/p95)",
        "Gateway request duration percentiles",
        col_width, y, col_width, row_height,
        'histogram_quantile(0.5, rate(cqox_gateway_request_duration_seconds_bucket[5m]))',
        unit="s"
    ))

    # パネル3: Upload Throughput RPS
    panels.append(create_panel(
        3, "Upload Throughput (RPS)",
        "Upload requests per second",
        col_width*2, y, col_width, row_height,
        'rate(cqox_upload_requests_total[1m])',
        unit="reqps"
    ))

    # パネル4: Analyze Throughput RPS
    panels.append(create_panel(
        4, "Analyze Throughput (RPS)",
        "Analyze requests per second",
        col_width*3, y, col_width, row_height,
        'rate(cqox_analyze_requests_total[1m])',
        unit="reqps"
    ))

    # ==========================================================================
    # Row 2: エラー/キュー/ワーカー (パネル 5-8)
    # ==========================================================================
    y += row_height

    # パネル5: Error Rate (4xx/5xx)
    panels.append(create_panel(
        5, "Error Rate (4xx/5xx)",
        "HTTP errors by status code",
        0, y, col_width, row_height,
        'sum(rate(cqox_http_errors_total[1m])) by (status_code)',
        unit="ops"
    ))

    # パネル6: Job Queue Depth
    panels.append(create_panel(
        6, "Job Queue Depth",
        "Number of jobs waiting in queue",
        col_width, y, col_width, row_height,
        'cqox_job_queue_depth',
        unit="short"
    ))

    # パネル7: Worker Concurrency
    panels.append(create_panel(
        7, "Worker Concurrency",
        "Currently running jobs per worker",
        col_width*2, y, col_width, row_height,
        'sum(cqox_worker_active_jobs) by (worker_id)',
        unit="short"
    ))

    # パネル8: Worker Task Wait Time
    panels.append(create_panel(
        8, "Worker Task Wait Time",
        "Time tasks wait before execution",
        col_width*3, y, col_width, row_height,
        'histogram_quantile(0.95, rate(cqox_worker_task_wait_seconds_bucket[5m]))',
        unit="s"
    ))

    # ==========================================================================
    # Row 3: GPU メトリクス (パネル 9-11) + Estimator開始
    # ==========================================================================
    y += row_height

    # パネル9: GPU Memory Used %
    panels.append(create_panel(
        9, "GPU Memory Used %",
        "GPU memory utilization",
        0, y, col_width, row_height,
        'cqox_gpu_memory_used_percent',
        visualization="gauge",
        unit="percent"
    ))

    # パネル10: GPU Utilization %
    panels.append(create_panel(
        10, "GPU Utilization %",
        "GPU compute utilization",
        col_width, y, col_width, row_height,
        'cqox_gpu_utilization_percent',
        visualization="gauge",
        unit="percent"
    ))

    # パネル11: GPU OOM/Timeout Count
    panels.append(create_panel(
        11, "GPU Errors (OOM/Timeout)",
        "GPU error counts",
        col_width*2, y, col_width, row_height,
        'sum(rate(cqox_gpu_errors_total[5m])) by (error_type)',
        unit="ops"
    ))

    # パネル12: Estimator Latency (tvce)
    panels.append(create_panel(
        12, "Estimator Latency: TVCE",
        "Time-varying causal effects estimator latency",
        col_width*3, y, col_width, row_height,
        'histogram_quantile(0.95, rate(cqox_estimator_duration_seconds_bucket{estimator_name="tvce"}[5m]))',
        unit="s"
    ))

    # ==========================================================================
    # Row 4: Estimator Latency (パネル 13-16)
    # ==========================================================================
    y += row_height

    for i, estimator in enumerate(["ope", "hidden", "iv", "transport"]):
        panels.append(create_panel(
            13 + i,
            f"Estimator Latency: {estimator.upper()}",
            f"{estimator.upper()} estimator execution latency",
            col_width * i, y, col_width, row_height,
            f'histogram_quantile(0.95, rate(cqox_estimator_duration_seconds_bucket{{estimator_name="{estimator}"}}[5m]))',
            unit="s"
        ))

    # ==========================================================================
    # Row 5: Estimator Latency続き + Quality Gates開始 (パネル 17-20)
    # ==========================================================================
    y += row_height

    # パネル17: Estimator Latency (proximal)
    panels.append(create_panel(
        17, "Estimator Latency: Proximal",
        "Proximal causal inference estimator latency",
        0, y, col_width, row_height,
        'histogram_quantile(0.95, rate(cqox_estimator_duration_seconds_bucket{estimator_name="proximal"}[5m]))',
        unit="s"
    ))

    # パネル18: Estimator Latency (network)
    panels.append(create_panel(
        18, "Estimator Latency: Network",
        "Network spillover estimator latency",
        col_width, y, col_width, row_height,
        'histogram_quantile(0.95, rate(cqox_estimator_duration_seconds_bucket{estimator_name="network"}[5m]))',
        unit="s"
    ))

    # パネル19: Gate Pass Rate (ess)
    panels.append(create_panel(
        19, "Gate Pass Rate: ESS",
        "Effective sample size gate pass rate",
        col_width*2, y, col_width, row_height,
        'sum(rate(cqox_quality_gate_checks_total{gate_name="ess",result="pass"}[5m])) / sum(rate(cqox_quality_gate_checks_total{gate_name="ess"}[5m]))',
        visualization="gauge",
        unit="percentunit"
    ))

    # パネル20: Gate Pass Rate (tail)
    panels.append(create_panel(
        20, "Gate Pass Rate: Tail",
        "Weight tail gate pass rate",
        col_width*3, y, col_width, row_height,
        'sum(rate(cqox_quality_gate_checks_total{gate_name="tail",result="pass"}[5m])) / sum(rate(cqox_quality_gate_checks_total{gate_name="tail"}[5m]))',
        visualization="gauge",
        unit="percentunit"
    ))

    # ==========================================================================
    # Row 6: Quality Gates (パネル 21-24)
    # ==========================================================================
    y += row_height

    for i, gate in enumerate(["ci_width", "weak_iv", "sensitivity", "balance"]):
        panels.append(create_panel(
            21 + i,
            f"Gate Pass Rate: {gate.replace('_', ' ').title()}",
            f"{gate} quality gate pass rate",
            col_width * i, y, col_width, row_height,
            f'sum(rate(cqox_quality_gate_checks_total{{gate_name="{gate}",result="pass"}}[5m])) / sum(rate(cqox_quality_gate_checks_total{{gate_name="{gate}"}}[5m]))',
            visualization="gauge",
            unit="percentunit"
        ))

    # ==========================================================================
    # Row 7: Quality Gate最後 + CAS (パネル 25-28)
    # ==========================================================================
    y += row_height

    # パネル25: Gate Pass Rate (mono)
    panels.append(create_panel(
        25, "Gate Pass Rate: Monotonicity",
        "Monotonicity assumption gate pass rate",
        0, y, col_width, row_height,
        'sum(rate(cqox_quality_gate_checks_total{gate_name="mono",result="pass"}[5m])) / sum(rate(cqox_quality_gate_checks_total{gate_name="mono"}[5m]))',
        visualization="gauge",
        unit="percentunit"
    ))

    # パネル26: CAS Average
    panels.append(create_panel(
        26, "CAS Average",
        "Average Causal Assurance Score",
        col_width, y, col_width, row_height,
        'avg(cqox_cas_score)',
        visualization="stat",
        unit="short"
    ))

    # パネル27: CAS Distribution Histogram
    panels.append(create_panel(
        27, "CAS Distribution",
        "Distribution of CAS scores",
        col_width*2, y, col_width, row_height,
        'rate(cqox_cas_score_bucket[5m])',
        visualization="heatmap"
    ))

    # パネル28: Sign Consensus Ratio
    panels.append(create_panel(
        28, "Sign Consensus Ratio",
        "Estimator effect sign agreement ratio",
        col_width*3, y, col_width, row_height,
        'avg(cqox_sign_consensus_ratio)',
        visualization="gauge",
        unit="percentunit"
    ))

    # ==========================================================================
    # Row 8: Health/Reject/Domain (パネル 29-32)
    # ==========================================================================
    y += row_height

    # パネル29: CI Overlap Index
    panels.append(create_panel(
        29, "CI Overlap Index",
        "Confidence interval overlap index",
        0, y, col_width, row_height,
        'avg(cqox_ci_overlap_index)',
        visualization="gauge",
        unit="percentunit"
    ))

    # パネル30: Data Health
    panels.append(create_panel(
        30, "Data Health Score",
        "Overall data health (missing + imbalance)",
        col_width, y, col_width, row_height,
        'avg(cqox_data_health_score)',
        visualization="gauge",
        unit="percentunit"
    ))

    # パネル31: Reject (Fail-Closed) Rate
    panels.append(create_panel(
        31, "Reject Rate (Fail-Closed)",
        "Jobs rejected due to quality gates",
        col_width*2, y, col_width, row_height,
        'rate(cqox_reject_total[5m])',
        unit="ops"
    ))

    # パネル32: Domain-Agnostic Mix
    panels.append(create_panel(
        32, "Domain Auto-Detection Mix",
        "Auto-detected domain category distribution",
        col_width*3, y, col_width, row_height,
        'sum(rate(cqox_domain_auto_detected_total[5m])) by (detected_category)',
        visualization="piechart"
    ))

    # ==========================================================================
    # Row 9: Performance/Uptime (パネル 33-36)
    # ==========================================================================
    y += row_height

    # パネル33: Largest File Size Processed
    panels.append(create_panel(
        33, "Largest File Size Processed",
        "Maximum file size processed (rolling)",
        0, y, col_width, row_height,
        'max(cqox_file_size_processed_bytes)',
        visualization="stat",
        unit="bytes"
    ))

    # パネル34: P95 Time per 10k Rows
    panels.append(create_panel(
        34, "P95 Time per 10k Rows",
        "Processing time normalized per 10k rows",
        col_width, y, col_width, row_height,
        'histogram_quantile(0.95, rate(cqox_processing_time_per_10k_rows_seconds_bucket[5m]))',
        unit="s"
    ))

    # パネル35: Uptime / Availability
    panels.append(create_panel(
        35, "Service Uptime",
        "Service uptime in seconds",
        col_width*2, y, col_width, row_height,
        'cqox_service_uptime_seconds',
        visualization="stat",
        unit="s"
    ))

    # パネル36: Top Error Reasons
    panels.append(create_panel(
        36, "Top Error Reasons",
        "Errors categorized by reason",
        col_width*3, y, col_width, row_height,
        'topk(5, sum(rate(cqox_error_reasons_total[5m])) by (error_category))',
        visualization="bargauge"
    ))

    # ==========================================================================
    # Row 10: SLO Compliance (パネル 37)
    # ==========================================================================
    y += row_height

    # パネル37: End-to-End SLO Compliance Heatmap
    panels.append(create_panel(
        37, "End-to-End SLO Compliance",
        "SLO compliance check results heatmap",
        0, y, 24, row_height,  # 全幅を使用
        'sum(rate(cqox_slo_compliance_total[5m])) by (slo_name, result)',
        visualization="heatmap"
    ))

    # ダッシュボード全体の構造
    dashboard = {
        "uid": "cqox-37-integrated",
        "title": "CQOx Observability Dashboard (37 Panels)",
        "tags": ["cqox", "observability", "causal-inference"],
        "timezone": "browser",
        "schemaVersion": 38,
        "version": 1,
        "refresh": "10s",
        "time": {"from": "now-6h", "to": "now"},
        "timepicker": {
            "refresh_intervals": ["5s", "10s", "30s", "1m", "5m", "15m", "30m", "1h"],
            "time_options": ["5m", "15m", "1h", "6h", "12h", "24h", "2d", "7d", "30d"]
        },
        "panels": panels,
        "templating": {"list": []},
        "annotations": {"list": []},
        "editable": True,
        "fiscalYearStartMonth": 0,
        "graphTooltip": 1,
        "links": [],
        "liveNow": False,
        "style": "dark"
    }

    return dashboard

if __name__ == "__main__":
    dashboard = generate_dashboard()

    # 出力先
    output_path = Path(__file__).resolve().parents[1] / "grafana" / "dashboards" / "cqox_integrated.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # JSON出力
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(dashboard, f, indent=2, ensure_ascii=False)

    print(f"✅ Generated 37-panel dashboard: {output_path}")
    print(f"   Total panels: {len(dashboard['panels'])}")
    print(f"   Dashboard UID: {dashboard['uid']}")
