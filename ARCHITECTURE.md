# CQO-COMPLETE Architecture

## 現状の構成（2025-10-27時点）

### サービスポート
- **Engine**: localhost:8080 (起動中・正常動作)
- **Gateway**: localhost:8081 (要確認・Docker?)
- **Frontend（Vite dev）**: localhost:4000 (修正済み)
- **Frontend（Docker）**: localhost:4000→80

### 課題と解決計画

## フェーズ1: 緊急修正 ✓
1. [完了] Viteポートを5173→4000に統一
2. [進行中] Gateway起動確認（port 8081がDocker使用中の可能性）
3. [保留] 14種の可視化表示確認

## フェーズ2: アーキテクチャ改善
### 2.1 統合管理（docker-compose）
```yaml
services:
  gateway: 8081:8080
  engine: 8080:8080
  frontend: 4000:80

  # 監視層（ELKスタック）
  elasticsearch: 9200:9200
  kibana: 5601:5601
  fluentd: 24224:24224

  # データ層
  redis: 6379:6379
  postgres: 5432:5432  # DWH
  # OR clickhouse: 8123:8123, 9000:9000
```

### 2.2 データフロー
```
User → Frontend:4000
     → Gateway:8081 (/api, /reports proxy)
     → Engine:8080 (推定・図生成)
     → Redis (キャッシュ)
     → PostgreSQL (永続化)

Logs → Fluentd → Elasticsearch → Kibana (監視)
```

## フェーズ3: ドメイン非依存化
### 3.1 自動ロール推定（Col①仕様）
- `config/ontology/columns.json`: 列名辞書
- `config/ontology/units.json`: 単位辞書
- `config/ontology/validators.json`: 検証ルール
- バックエンド: `backend/gateway/role_inference.py`

### 3.2 ドメイン特化可視化（Col②仕様）
- 6ドメイン: Medical, Education, Retail, Finance, Network, Policy
- UI: `frontend/src/components/figures/domain/`
- バックエンド: `domain_hints` 自動推定

## 次のステップ
1. Docker Composeで全サービスを統合
2. ELKスタックを追加
3. Redis + PostgreSQLを追加
4. 自動ロール推定を実装
5. ドメイン特化可視化を実装
