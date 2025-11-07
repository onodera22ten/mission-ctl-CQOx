# ポート設定

## 固定ポート割り当て

すべてのサービスは以下のポートで固定されています：

| サービス | ポート | URL | 説明 |
|---------|--------|-----|------|
| Frontend | 4000 | http://localhost:4000 | 可視化ダッシュボード（メインUI） |
| Gateway | 8080 | http://localhost:8080 | バックエンドAPI（データアップロード等） |
| Engine | 8081 | http://localhost:8081 | 推定エンジン（因果推論計算） |
| Grafana | 3000 | http://localhost:3000 | 可観測性ダッシュボード（37パネル） |
| Prometheus | 9090 | http://localhost:9090 | メトリクス収集・ストレージ |

## 注意事項

- **Frontend**: 本来は5173を使用する予定でしたが、既に別のプロセスが使用していたため4000に変更
- **その他のポート**: Gateway(8080)、Engine(8081)、Grafana(3000)、Prometheus(9090)は固定

## サービスの起動

```bash
# 全サービスを起動
docker-compose up -d

# 特定のサービスのみ起動
docker-compose up -d gateway engine frontend

# 状態確認
docker-compose ps
```

## トラブルシューティング

### ポート競合エラー

```
Error: failed to bind host port for 0.0.0.0:XXXX
```

このエラーが発生した場合:

1. どのプロセスが使用しているか確認:
   ```bash
   lsof -i :XXXX
   # または
   ss -tlnp | grep :XXXX
   ```

2. 不要なプロセスを停止するか、docker-compose.ymlのポート設定を変更

### サービスが起動しない

```bash
# ログを確認
docker-compose logs <service-name>

# 例: gatewayのログ
docker-compose logs gateway --tail 50
```

## 修正履歴

- 2025-10-25: Frontend を 5173 → 4000 に変更（ポート競合のため）
- 2025-10-25: Gateway に python-multipart を追加（ファイルアップロード対応）
- 2025-10-25: Frontend の nginx 設定を修正（500エラー・リダイレクトループ解消、Gateway ポート 8081→8080 に修正）
- 2025-10-25: Frontend の nginx に client_max_body_size 100M を追加（CSVアップロード 413 エラー解消）
- 2025-10-25: Frontend の nginx プロキシ設定を改善（X-Forwarded ヘッダー、HTTP/1.1、バッファリング無効化）
- 2025-10-25: Engine と Gateway のボリュームマウントに SELinux ラベル :z を追加（Permission denied 解消）

