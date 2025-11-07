# Phase 1完了: Docker Compose統合管理

## ✅ 実装完了項目

### 1. **docker-compose.full.yml**
全サービスを統合管理：
- **Gateway** (port 8082)
- **Engine** (port 8080)
- **Frontend** (port 4000)
- **Redis** (port 6379) - キャッシュ層
- **PostgreSQL** (port 5432) - DWH
- **Elasticsearch** (port 9200)
- **Kibana** (port 5601)
- **Fluentd** (port 24224) - ログ集約
- **Prometheus** (port 9090) - 移行期間用
- **Grafana** (port 3000) - 移行期間用

### 2. **データ永続化層**
- `backend/db/redis_client.py` - Redisクライアント
- `backend/db/postgres_client.py` - PostgreSQLクライアント
- `db/init.sql` - データベース初期化スクリプト
  - datasets, analysis_jobs, estimator_results
  - quality_gates, cas_scores
  - observability_metrics (37パネル用)
  - audit_log, domain_inference_cache

### 3. **ELKスタック設定**
- `fluentd/Dockerfile` - Fluentdコンテナ
- `fluentd/conf/fluent.conf` - ログ集約設定

### 4. **Engine統合**
- Redis キャッシュ (30分TTL)
- PostgreSQL 永続化 (全ジョブ・結果・メトリクス)
- 自動的にDBが無い環境でも動作 (HAS_DB フラグ)

## 🚀 起動方法

```bash
# 全サービス起動
docker-compose -f docker-compose.full.yml up -d

# ログ確認
docker-compose -f docker-compose.full.yml logs -f

# サービス停止
docker-compose -f docker-compose.full.yml down

# ボリューム含めて完全削除
docker-compose -f docker-compose.full.yml down -v
```

## 📊 アクセスURL

- **Frontend**: http://localhost:4000
- **Gateway API**: http://localhost:8082/api
- **Engine API**: http://localhost:8080/api
- **Kibana** (ログ可視化): http://localhost:5601
- **Grafana** (メトリクス): http://localhost:3000
- **Prometheus**: http://localhost:9090
- **PostgreSQL**: localhost:5432 (user: cqox, password: cqox_password, db: cqox_db)
- **Redis**: localhost:6379

## 🔄 移行手順

### 現在のローカル環境から移行

1. **現在のサービスを停止**:
```bash
pkill -f "uvicorn"
pkill -f "vite"
```

2. **Docker Composeで起動**:
```bash
docker-compose -f docker-compose.full.yml up -d
```

3. **動作確認**:
```bash
curl http://localhost:8082/api/health  # Gateway
curl http://localhost:8080/api/health  # Engine
curl http://localhost:4000             # Frontend
```

4. **データベース接続確認**:
```bash
docker exec -it cqox-postgres psql -U cqox -d cqox_db -c "\dt"
docker exec -it cqox-redis redis-cli ping
```

## 📈 次のステップ (Phase 2)

1. **ObservabilityDashboardページ作成**
   - `frontend/src/pages/ObservabilityDashboard.tsx`
   - 37パネルのメトリクス表示

2. **メトリクスAPI実装**
   - `backend/engine/observability_api.py`
   - PostgreSQLから37種のメトリクスを取得

3. **Kibanaダッシュボード設定**
   - ログ可視化
   - エラー追跡
   - パフォーマンス監視

## 🐛 トラブルシューティング

### ポート競合
既存のサービスがポートを使用中の場合：
```bash
lsof -i :8080  # Engineポート確認
lsof -i :8082  # Gatewayポート確認
lsof -i :4000  # Frontendポート確認
```

### データベース接続エラー
```bash
# PostgreSQL接続テスト
docker exec -it cqox-postgres pg_isready -U cqox

# Redis接続テスト
docker exec -it cqox-redis redis-cli ping
```

### Elasticsearch起動失敗
メモリ不足の場合：
```bash
# docker-compose.full.ymlのES_JAVA_OPTSを調整
# -Xms512m -Xmx512m → -Xms256m -Xmx256m
```