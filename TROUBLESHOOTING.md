# トラブルシューティング

このドキュメントは、可観測性ダッシュボードのセットアップ中に発生した問題と解決方法を記録しています。

## 修正した問題

### 1. Grafanaダッシュボードが空だった

**問題**: `grafana/dashboards/cqox.json` に `panels: []` のみが含まれており、パネルが定義されていなかった。

**解決策**:
- `scripts/generate_dashboard.py` を作成し、37パネルすべてを定義
- `python scripts/generate_dashboard.py` を実行して `grafana/dashboards/cqox_integrated.json` を生成

### 2. 詳細メトリクスが不足していた

**問題**: 基本的なHTTPメトリクスのみが収集され、37パネルに必要な詳細メトリクスが不足していた。

**解決策**:
- `backend/observability/metrics.py` を作成し、すべての37パネル用のPrometheusメトリクスを定義
- `backend/engine/server.py` と `backend/gateway/app.py` に詳細なメトリクス収集を統合

### 3. SELinux権限エラー

**問題**: Fedora LinuxのSELinuxにより、Grafanaコンテナがプロビジョニングファイルにアクセスできなかった。

**エラーメッセージ**:
```
logger=provisioning.dashboard level=error msg="can't read dashboard provisioning files from directory"
path=/etc/grafana/provisioning/dashboards error="open /etc/grafana/provisioning/dashboards: permission denied"
```

**解決策**:
```yaml
# docker-compose.yml
grafana:
  user: "root"  # rootユーザーで実行
  volumes:
    - ./grafana/provisioning:/etc/grafana/provisioning:z  # SELinuxラベル :z を追加
    - ./grafana/dashboards:/var/lib/grafana/dashboards:z
```

### 4. 重複するPrometheusデータソース設定

**問題**: 複数のPrometheusデータソース設定ファイルがあり、両方が `isDefault: true` に設定されていた。

**エラーメッセージ**:
```
Datasource provisioning error: datasource.yaml config is invalid.
Only one datasource per organization can be marked as default
```

**解決策**:
- `grafana/provisioning/datasources/datasource.yml` を削除
- `grafana/provisioning/datasources/prometheus.yaml` から `deleteDatasources` セクションを削除

### 5. Prometheusスクレイプターゲットの設定ミス

**問題**: `prometheus.yml` でDockerネットワーク内のサービス名ではなく `host.docker.internal` を使用していた。

**解決策**:
```yaml
# prometheus/prometheus.yml
scrape_configs:
  - job_name: 'gateway'
    static_configs:
      - targets: ['gateway:8080']  # host.docker.internal:8080 から変更

  - job_name: 'engine'
    static_configs:
      - targets: ['engine:8080']   # host.docker.internal:8081 から変更
```

### 6. Frontendポート競合

**問題**: ポート5173が既に使用されていた。

**解決策**:
```yaml
# docker-compose.yml
frontend:
  ports: [ "5174:80" ]  # 5173 から 5174 に変更
```

### 7. docker-compose.yml の古いバージョンフィールド

**警告**: `version: "3.9"` フィールドが古いとの警告が表示された。

**解決策**: `version` フィールドを削除（Docker Composeの新しいバージョンでは不要）

## 動作確認

### Grafanaダッシュボードの確認

1. **Grafanaにアクセス**: http://localhost:3000
2. **ダッシュボードリストを確認**:
   ```bash
   curl -s 'http://localhost:3000/api/search?type=dash-db' | python -m json.tool
   ```
3. **メインダッシュボード**: http://localhost:3000/d/cqox-37-integrated/cqox-observability-dashboard-37-panels

### Prometheusターゲットの確認

1. **Prometheusにアクセス**: http://localhost:9090
2. **ターゲット状態を確認**: http://localhost:9090/targets
3. **メトリクスを確認**:
   ```bash
   curl http://localhost:8080/metrics  # Gateway
   curl http://localhost:8081/metrics  # Engine (起動後)
   ```

### メトリクスの動作確認

バックエンドサービスを起動してメトリクスを生成:
```bash
docker-compose up -d engine gateway
```

データをアップロードして分析を実行すると、以下のメトリクスが収集されます:
- 推定器レイテンシ (7種類)
- 品質ゲート通過率 (7種類)
- CASスコア
- ファイル処理メトリクス
- その他

## 現在の状態

✅ **解決済み**:
- Grafanaダッシュボードが正しく表示される
- 37パネルすべてが定義されている
- Prometheusがメトリクスを収集できる
- SELinux権限問題が解決された

⚠️ **注意事項**:
- バックエンドサービス(engine/gateway)を起動しないと、メトリクスデータは表示されません
- 初回起動時は、データがないためグラフは空です
- データをアップロードして分析を実行すると、メトリクスが蓄積されます

## ファイル構造

```
cqox-complete_b/
├── backend/
│   ├── observability/
│   │   ├── __init__.py
│   │   └── metrics.py          # 37パネル用メトリクス定義
│   ├── engine/
│   │   └── server.py           # メトリクス収集統合
│   └── gateway/
│       └── app.py              # メトリクス収集統合
├── grafana/
│   ├── dashboards/
│   │   ├── cqox_integrated.json  # 37パネルダッシュボード (生成済み)
│   │   ├── cqox.json
│   │   └── cas.json
│   └── provisioning/
│       ├── dashboards/
│       │   └── cqox.yaml
│       └── datasources/
│           └── prometheus.yaml   # 修正済み
├── prometheus/
│   └── prometheus.yml          # スクレイプ設定修正済み
├── scripts/
│   └── generate_dashboard.py  # ダッシュボード生成スクリプト
├── docker-compose.yml          # 修正済み
├── OBSERVABILITY.md            # 使用方法ドキュメント
└── TROUBLESHOOTING.md          # このファイル
```

## 参考リンク

- [Grafana Provisioning Documentation](https://grafana.com/docs/grafana/latest/administration/provisioning/)
- [Prometheus Configuration](https://prometheus.io/docs/prometheus/latest/configuration/configuration/)
- [Docker SELinux Labels](https://docs.docker.com/storage/bind-mounts/#configure-the-selinux-label)
