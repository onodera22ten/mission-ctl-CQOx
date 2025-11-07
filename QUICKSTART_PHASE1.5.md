# Phase 1.5 クイックスタートガイド

## 🚀 すぐに試す（5分）

### 1. 依存関係インストール
```bash
cd /home/hirokionodera/cqox-complete_b
pip install -r requirements.txt
```

### 2. Jaegerを起動（分散トレーシングUI）
```bash
docker run -d --name jaeger \
  -p 16686:16686 \
  -p 6831:6831/udp \
  jaegertracing/all-in-one:1.52
```

### 3. サービス起動

**Terminal 1: Engine**
```bash
cd /home/hirokionodera/cqox-complete_b/backend/engine
JAEGER_ENDPOINT=localhost:6831 uvicorn server:app --port 8080
```

**Terminal 2: Gateway**
```bash
cd /home/hirokionodera/cqox-complete_b/backend/gateway
echo "http://localhost:8080" > .engine_url
JAEGER_ENDPOINT=localhost:6831 uvicorn app:app --port 8082
```

**Terminal 3: Frontend**
```bash
cd /home/hirokionodera/cqox-complete_b/frontend
npm run dev
```

### 4. 動作確認

**4.1 ヘルスチェック**
```bash
curl http://localhost:8082/api/health
# 期待: {"ok":true,"service":"gateway"}

curl http://localhost:8080/api/health
# 期待: {"ok":true,"service":"engine"}
```

**4.2 CSV アップロード & 分析**
```bash
# Frontend: http://localhost:4001
# 1. mini_retail_complete.csv をアップロード
# 2. マッピング設定
# 3. 分析実行
```

**4.3 分散トレーシング確認**
```bash
# Jaeger UI: http://localhost:16686
# - Service: gateway を選択
# - Operation: POST /api/analyze/comprehensive
# - Find Traces で最新のトレースを確認

# 確認項目:
# ✓ gateway → engine のHTTP呼び出し
# ✓ 各スパンのレイテンシ
# ✓ エラーの有無
```

---

## 🧪 Resilience Patterns テスト

### Circuit Breaker テスト

```bash
# 1. Engineを停止
pkill -f "uvicorn server:app"

# 2. 5回連続でリクエスト（失敗）
for i in {1..5}; do
  curl -X POST http://localhost:8082/api/analyze/comprehensive \
    -H "Content-Type: application/json" \
    -d '{
      "dataset_id": "test",
      "mapping": {"y": "y", "treatment": "w", "unit_id": "id"}
    }'
  echo ""
done

# 3. 6回目: Circuit Breaker OPEN
# 期待: "Circuit breaker OPEN" エラーが即座に返る

# 4. Engineを再起動
cd /home/hirokionodera/cqox-complete_b/backend/engine
JAEGER_ENDPOINT=localhost:6831 uvicorn server:app --port 8080

# 5. 60秒待機後、自動回復
sleep 60
curl http://localhost:8082/api/health
# 期待: 正常復帰
```

### Retry テスト

```bash
# Gateway ログを監視
tail -f /tmp/gateway.log

# リクエスト送信（Engineが不安定な状態で）
curl -X POST http://localhost:8082/api/analyze/comprehensive \
  -H "Content-Type: application/json" \
  -d @request.json

# ログで確認:
# [Retry] Attempt 1/3 failed: ... Retrying in 1.23s...
# [Retry] Attempt 2/3 failed: ... Retrying in 2.87s...
# (成功 or 3回目で諦め)
```

---

## 📊 Jaeger UI の見方

### アクセス: http://localhost:16686

### 基本操作

1. **Service 選択**: `gateway` または `engine`
2. **Operation 選択**: `POST /api/analyze/comprehensive`
3. **Find Traces**: 最新のトレースを検索
4. **トレース詳細**:
   - タイムライン表示
   - 各スパンのレイテンシ
   - タグ（HTTP status, error info）
   - ログ（エラーメッセージ）

### 確認すべきポイント

✅ **正常系**:
- gateway → engine: ~50-200ms
- engine → redis: ~5ms (キャッシュヒット)
- engine → postgres: ~10-20ms
- 全体: ~500ms-2000ms (データサイズ依存)

⚠️ **異常系**:
- エラースパン（赤色）の有無
- タイムアウト（>120秒）
- Retry スパンの繰り返し

### Service Dependencies グラフ

- `System Architecture` タブ
- 依存関係の可視化: gateway → engine → DB

---

## 🐳 Docker Compose で起動（推奨）

```bash
cd /home/hirokionodera/cqox-complete_b

# 全サービス起動
docker-compose -f docker-compose.full.yml up -d

# サービス一覧
docker-compose -f docker-compose.full.yml ps

# ログ確認
docker-compose -f docker-compose.full.yml logs -f gateway engine

# 停止
docker-compose -f docker-compose.full.yml down
```

### アクセスURL

| サービス | URL |
|---------|-----|
| Frontend | http://localhost:4000 |
| Gateway | http://localhost:8082 |
| Engine | http://localhost:8080 |
| **Jaeger UI** | http://localhost:16686 |
| Kibana (Logs) | http://localhost:5601 |
| Grafana (Metrics) | http://localhost:3000 |
| Prometheus | http://localhost:9090 |

---

## 📝 チェックリスト

Phase 1.5 が正しく動作していることを確認:

- [ ] Gateway ヘルスチェック OK
- [ ] Engine ヘルスチェック OK
- [ ] CSV アップロード成功
- [ ] 14種類の可視化が表示される
- [ ] Jaeger UI でトレースが見える
- [ ] Circuit Breaker テスト成功
- [ ] Retry テスト成功
- [ ] Graceful Shutdown テスト成功

---

## 🆘 トラブルシューティング

### Jaeger に トレースが表示されない

**原因**: OpenTelemetry の設定ミス

**解決**:
```bash
# 環境変数を確認
echo $JAEGER_ENDPOINT  # localhost:6831 or jaeger:6831

# Jaeger コンテナが起動しているか確認
docker ps | grep jaeger

# Gateway/Engine のログを確認
# 期待: "[Tracing] OpenTelemetry enabled"
```

### Circuit Breaker が動作しない

**原因**: HAS_RESILIENCE = False

**解決**:
```bash
# resilience モジュールが読み込まれているか確認
python3 -c "from backend.resilience.circuit_breaker import circuit_breaker"

# エラーが出る場合は依存関係を再インストール
pip install -r requirements.txt
```

### Gateway → Engine 接続エラー

**原因**: ENGINE_URL の設定ミス

**解決**:
```bash
# .engine_url ファイルを確認
cat backend/gateway/.engine_url
# 期待: http://localhost:8080 (開発) or http://engine:8080 (Docker)

# 手動で修正
echo "http://localhost:8080" > backend/gateway/.engine_url
```

---

## 📚 詳細ドキュメント

- **PHASE1.5_RELIABILITY.md**: 実装詳細、アーキテクチャ解説
- **WORLD_CLASS_COMPARISON.md**: 世界最高峰基準との比較
- **backend/resilience/**: ソースコード

---

## ✅ 次のステップ

Phase 1.5 が正常に動作したら:

**Phase 2**: 37パネル Observability Dashboard 実装
- Grafana の37パネルをUIに統合
- リアルタイムメトリクス表示
- カスタムダッシュボード

**Phase 3**: ドメイン非依存化
- 自動ロール推論
- ドメイン固有可視化（医療、教育、小売、金融、ネットワーク、政策）
