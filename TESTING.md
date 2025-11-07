# CQOx-Complete テスト手順

## 現在の環境状態（2025-10-27 17:00）

### 起動中のサービス
- **Frontend**: http://localhost:4001 ✅
- **Gateway**: http://localhost:8081 ✅ (→Engine proxy)
- **Engine**: http://localhost:8080 ✅

### テスト手順: 14種の可視化確認

#### ステップ1: ブラウザでアクセス
```
http://localhost:4001
```

#### ステップ2: CSVファイルをアップロード
既存のサンプルファイルが利用可能：
```
/home/hirokionodera/cqox-complete_b/data/uploads/05468b918ac740f7b8ae368f4765ae8b_sample_retail.csv
```

または新しいCSVをアップロード（最小構成）：
```csv
unit_id,treatment,y,date
u001,0,120,2025-01-01
u002,1,150,2025-01-02
u003,0,130,2025-01-03
u004,1,160,2025-01-04
```

#### ステップ3: Rolesマッピング
自動推定された列を確認・修正：
- **y**: outcome列
- **treatment**: 介入列（0/1またはカテゴリ）
- **unit_id**: 個体ID
- **time** (optional): 時間列

#### ステップ4: Analyze実行
"Analyze"ボタンをクリック

#### ステップ5: 可視化確認
以下の**14種の図**が表示されるはずです：

1. **Parallel Trends** - 並行トレンド（DID前提）
2. **Event Study** - イベントスタディ係数
3. **ATE Density** - 推定器別の効果分布
4. **Propensity Overlap** - 傾向スコアの重なり
5. **Balance SMD** - 共変量バランス（SMD）
6. **Rosenbaum Sensitivity** - 感度分析曲線
7. **IV First-Stage F** - 操作変数のF統計量
8. **IV Strength vs 2SLS** - IV強度と効果の安定性
9. **Transport Weights** - 輸送重みの分布
10. **TVCE Line** - 時変効果
11. **Network Spillover** - ネットワーク干渉ヒートマップ
12. **Heterogeneity Waterfall** - サブグループ異質性
13. **Quality Gates Board** - 7つの品質ゲート合否
14. **CAS Radar** - CASスコアレーダー

#### ステップ6: トラブルシューティング

##### 可視化が表示されない場合
1. ブラウザの Developer Tools (F12) を開く
2. **Console** タブでエラーを確認
3. **Network** タブで `/api/analyze/comprehensive` のレスポンスを確認

##### 期待されるAPIレスポンス形式
```json
{
  "dataset_id": "...",
  "job_id": "job_xxxxx",
  "results": [...],
  "gates": {...},
  "cas": {"overall": 0.75, ...},
  "figures": {
    "parallel_trends": "/reports/figures/job_xxxxx/parallel_trends.png",
    "event_study": "/reports/figures/job_xxxxx/event_study.html",
    ...
  }
}
```

##### よくある問題
1. **404 on /reports/figures/...**:
   - Engineが図を生成していない
   - `/reports` static file servingが無効
   - logs/engine.log を確認

2. **空のfiguresオブジェクト**:
   - データが推定器の要件を満たしていない
   - mappingが不完全
   - backend/engine/figures.py のエラー

3. **プロキシエラー**:
   - Gateway→Engine接続を確認
   - curl http://localhost:8081/api/health

### 次のステップ

#### 可視化が正常に表示された場合
→ docker-composeで統合管理に移行
→ ELKスタック追加
→ Redis+PostgreSQL追加

#### 可視化が表示されない場合
→ エラーログを共有してください：
```bash
tail -50 logs/engine.log
tail -50 logs/gateway.log
```
