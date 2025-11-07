# CQOx 可観測性ダッシュボード

このドキュメントでは、CQOx の 37 パネル可観測性ダッシュボードの使用方法について説明します。

## 概要

CQOx は、因果推論エンジンの完全な可観測性を提供するために、37 個のメトリクスパネルを備えた Grafana ダッシュボードを提供しています。これらのパネルは、PDF 仕様書（`claude/plan.pdf`）に定義されている通りに実装されています。

## アーキテクチャ

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Gateway   │────▶│   Engine    │────▶│ GPU Worker  │
│  (port 8080)│     │ (port 8081) │     │             │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       │ /metrics          │ /metrics          │ /metrics
       │                   │                   │
       ▼                   ▼                   ▼
┌────────────────────────────────────────────────────┐
│              Prometheus (port 9090)                │
│           メトリクス収集とストレージ                 │
└──────────────────────┬─────────────────────────────┘
                       │
                       │ クエリ
                       ▼
┌────────────────────────────────────────────────────┐
│               Grafana (port 3000)                  │
│          37パネル可観測性ダッシュボード              │
└────────────────────────────────────────────────────┘
```

## セットアップ

### 1. サービスの起動

```bash
# Docker Compose でサービスを起動
docker-compose up -d

# または、個別にサービスを起動
docker-compose up -d prometheus grafana
```

### 2. ダッシュボードへのアクセス

- **Grafana**: http://localhost:3000
- **Prometheus**: http://localhost:9090

Grafana は匿名アクセスが有効になっているため、ログインなしでアクセスできます。

### 3. ダッシュボードの確認

1. Grafana にアクセス
2. 左側のメニューから「Dashboards」を選択
3. 「CQOx Observability Dashboard (37 Panels)」を開く

## 37 パネルの詳細

### Row 1: レイテンシメトリクス (パネル 1-4)

1. **Engine E2E Latency (p50/p95/p99)** - エンジンのエンドツーエンドリクエストレイテンシ
2. **Gateway Request Latency (p50/p95)** - ゲートウェイのリクエストレイテンシ
3. **Upload Throughput (RPS)** - アップロードスループット
4. **Analyze Throughput (RPS)** - 分析スループット

### Row 2: エラー/キュー/ワーカー (パネル 5-8)

5. **Error Rate (4xx/5xx)** - HTTPエラーレート
6. **Job Queue Depth** - ジョブキューの深さ
7. **Worker Concurrency** - ワーカーの同時実行数
8. **Worker Task Wait Time** - タスク待機時間

### Row 3: GPU メトリクス (パネル 9-11) + 推定器開始

9. **GPU Memory Used %** - GPU メモリ使用率
10. **GPU Utilization %** - GPU 計算使用率
11. **GPU Errors (OOM/Timeout)** - GPU エラー数
12. **Estimator Latency: TVCE** - TVCE 推定器のレイテンシ

### Row 4-5: 推定器レイテンシ (パネル 13-18)

13. **Estimator Latency: OPE** - OPE 推定器
14. **Estimator Latency: Hidden** - Hidden Confounder 推定器
15. **Estimator Latency: IV** - 操作変数推定器
16. **Estimator Latency: Transport** - Transport 推定器
17. **Estimator Latency: Proximal** - Proximal 推定器
18. **Estimator Latency: Network** - Network Spillover 推定器

### Row 5-7: 品質ゲート (パネル 19-25)

19. **Gate Pass Rate: ESS** - 有効サンプルサイズゲート
20. **Gate Pass Rate: Tail** - 重みの裾ゲート
21. **Gate Pass Rate: CI Width** - 信頼区間幅ゲート
22. **Gate Pass Rate: Weak IV** - 弱操作変数ゲート
23. **Gate Pass Rate: Sensitivity** - 感度分析ゲート
24. **Gate Pass Rate: Balance** - バランスゲート
25. **Gate Pass Rate: Monotonicity** - 単調性ゲート

### Row 7-8: CAS と合意メトリクス (パネル 26-32)

26. **CAS Average** - 平均 Causal Assurance Score
27. **CAS Distribution** - CAS スコアの分布
28. **Sign Consensus Ratio** - 推定器間の符号一致率
29. **CI Overlap Index** - 信頼区間重複指数
30. **Data Health Score** - データ健全性スコア
31. **Reject Rate (Fail-Closed)** - 品質ゲート不合格による拒否率
32. **Domain Auto-Detection Mix** - ドメイン自動検出分布

### Row 9-10: パフォーマンスと SLO (パネル 33-37)

33. **Largest File Size Processed** - 処理された最大ファイルサイズ
34. **P95 Time per 10k Rows** - 10k行あたりの処理時間（P95）
35. **Service Uptime** - サービス稼働時間
36. **Top Error Reasons** - エラー理由トップ5
37. **End-to-End SLO Compliance** - エンドツーエンド SLO 準拠ヒートマップ

## メトリクスの収集

### バックエンドでのメトリクス記録

メトリクスは `backend/observability/metrics.py` で定義されており、以下の関数を使用してビジネスロジックから記録できます：

```python
from backend.observability.metrics import (
    record_estimator_execution,
    record_quality_gate_result,
    record_cas_score,
    record_job_metrics,
    record_file_processing,
)

# 推定器の実行時間を記録
record_estimator_execution("tvce", duration_seconds=2.5)

# 品質ゲートの結果を記録
record_quality_gate_result("ess", passed=True)

# CAS スコアを記録
record_cas_score(75.0)

# ジョブ完了時の総合メトリクスを記録
record_job_metrics(
    cas_score_value=75.0,
    sign_consensus=0.85,
    ci_overlap=0.6,
    data_health=0.9,
    dataset_id="dataset123"
)

# ファイル処理メトリクスを記録
record_file_processing(
    file_size_bytes=1024000,
    rows=10000,
    duration_seconds=5.2
)
```

### Prometheus エンドポイント

各サービスは `/metrics` エンドポイントで Prometheus 形式のメトリクスを公開しています：

- Gateway: http://localhost:8080/metrics
- Engine: http://localhost:8081/metrics

## トラブルシューティング

### ダッシュボードが表示されない

1. Grafana が起動しているか確認:
   ```bash
   docker-compose ps grafana
   ```

2. ダッシュボードファイルが存在するか確認:
   ```bash
   ls -la grafana/dashboards/cqox_integrated.json
   ```

3. Grafana ログを確認:
   ```bash
   docker-compose logs grafana
   ```

### メトリクスが表示されない

1. Prometheus が起動しているか確認:
   ```bash
   docker-compose ps prometheus
   ```

2. Prometheus のターゲットが UP か確認:
   - http://localhost:9090/targets にアクセス
   - `gateway` と `engine` が UP 状態であることを確認

3. バックエンドサービスが `/metrics` エンドポイントを公開しているか確認:
   ```bash
   curl http://localhost:8080/metrics
   curl http://localhost:8081/metrics
   ```

### ダッシュボードの再生成

ダッシュボード定義を変更した場合は、以下のコマンドで再生成できます：

```bash
python scripts/generate_dashboard.py
```

その後、Grafana を再起動:

```bash
docker-compose restart grafana
```

## カスタマイズ

### メトリクスの追加

1. `backend/observability/metrics.py` に新しいメトリクスを定義
2. ビジネスロジックから記録関数を呼び出す
3. `scripts/generate_dashboard.py` に新しいパネルを追加
4. ダッシュボードを再生成

### アラートの設定

Grafana でアラートを設定するには：

1. パネルを編集モードで開く
2. 「Alert」タブを選択
3. 条件とアクション（通知チャンネル）を設定

## 参考

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [CQOx 仕様書](claude/plan.pdf) - 37パネルの詳細定義
