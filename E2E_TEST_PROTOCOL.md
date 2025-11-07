# 🧪 CQOx End-to-End テストプロトコル

**Date**: 2025-11-01  
**Purpose**: 完全なE2E動作を証明（ファイルアップロード → 可視化 → パラメータ調整）

---

## ❌ これまでの失敗

**私の過ち**:
- CSV→Parquet変換の部分的なテストで満足
- UI起動せず
- 可視化未確認
- パラメータ調整未確認

**ユーザーの正当な指摘**:
> いや、可視化やパラメータまでできてからでしょ。

**NASA/Googleレベルでは**:
- 部分的なテスト = 価値ゼロ
- E2E動作証明が必須
- スクリーンショット/ビデオが標準

---

## ✅ 完全E2Eテストプロトコル

### Step 1: サービス起動 ✅

```bash
# Engine (port 8080)
python3 -m uvicorn backend.engine.server:app --host 0.0.0.0 --port 8080

# Gateway (port 8081)
python3 -m uvicorn backend.gateway.app:app --host 0.0.0.0 --port 8081

# Frontend (port 4000)
cd frontend && npm run dev
```

**Health Check**:
```bash
curl http://localhost:8080/api/health  # {"ok":true,"service":"engine"}
curl http://localhost:8081/api/health  # {"ok":true,"service":"gateway"}
curl http://localhost:4000/            # HTML
```

---

### Step 2: ファイルアップロード

**テストデータ**: `mini_retail.csv`
```csv
user_id,date,treatment,sales,cost
1,2024-01-01,1,1250.5,320.0
2,2024-01-01,0,890.2,250.0
...
```

**UI操作**:
1. ブラウザで http://localhost:4000/ にアクセス
2. ファイル選択: `mini_retail.csv`
3. ドメイン選択: `retail`
4. "Upload" ボタンクリック

**期待される結果**:
- ✅ アップロード成功
- ✅ 列名が表示される: `['user_id', 'date', 'treatment', 'sales', 'cost']`
- ✅ プレビューデータが表示される

**API確認**:
```bash
curl -X POST http://localhost:8081/api/upload \
  -F "file=@mini_retail.csv"
```

**期待されるレスポンス**:
```json
{
  "ok": true,
  "dataset_id": "abc123...",
  "meta": {
    "columns": ["user_id", "date", "treatment", "sales", "cost"],
    "dtypes": {...},
    "preview": [...]
  },
  "candidates": {
    "y": ["sales"],
    "treatment": ["treatment"],
    "unit_id": ["user_id"],
    "time": ["date"],
    "cost": ["cost"]
  }
}
```

---

### Step 3: Mapping指定（自動推論 + Manual Override）

**UI操作**:
1. 自動推論結果が表示される:
   - Outcome (y): `sales` ✅
   - Treatment: `treatment` ✅
   - Unit ID: `user_id` ✅
   - Time: `date` ✅
   - Cost: `cost` ✅

2. （必要なら）マニュアル修正
   - ドロップダウンから列を選択

**期待される結果**:
- ✅ 全ての必須列（y, treatment, unit_id）が推論される
- ✅ "Analyze" ボタンが有効化される

---

### Step 4: 分析実行

**UI操作**:
1. "Analyze" ボタンクリック
2. ローディング表示

**API確認**:
```bash
curl -X POST http://localhost:8080/api/analyze/comprehensive \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_id": "abc123",
    "df_path": "data/packets/abc123/data.parquet",
    "mapping": {
      "y": "sales",
      "treatment": "treatment",
      "unit_id": "user_id",
      "time": "date",
      "cost": "cost"
    },
    "objective": "GP28"
  }'
```

**期待される結果**:
- ✅ ステータス: 200 OK
- ✅ job_id返却
- ✅ エラーなし

---

### Step 5: 可視化表示

**UI確認項目**:

#### 5.1 基本的な図（Matplotlib）
- [ ] ATE推定値の棒グラフ
- [ ] ATE信頼区間の図
- [ ] Covariate Balance（SMD）
- [ ] Propensity Score分布

#### 5.2 WolframONE 3D/Animated 図
- [ ] CAS Radar Chart (`cas_radar_chart.png`)
- [ ] Causal Surface 3D (`causal_surface_3d.png`)
- [ ] ATE Animation (`ate_animation.gif`)
- [ ] Domain Network (`domain_network_graph.png`)

#### 5.3 Objective-Specific 図（GP28用）
- [ ] 2D Figure: `gp28_objective_2d.png`
- [ ] 3D Figure: `gp28_objective_3d.png`
- [ ] Animated: `gp28_objective_animated.gif`

#### 5.4 World-Class Showcase 図
- [ ] Dynamic Effects Over Time (`world_class_dynamic_effects.png`)
- [ ] Multi-Estimator Comparison (`world_class_estimator_comparison.png`)
- [ ] Heterogeneous Effects (`world_class_heterogeneous_effects.png`)
- [ ] Sensitivity Analysis Surface (`world_class_sensitivity_surface.png`)
- [ ] Counterfactual Policy Space (`world_class_policy_space.png`)
- [ ] Causal Graph Interactive (`world_class_causal_graph.png`)

**ファイル確認**:
```bash
ls -lh reports/figures/*.png
ls -lh reports/figures/*.gif
ls -lh reports/figures/*.svg
```

**期待される結果**:
- ✅ 全図が生成されている
- ✅ ファイルサイズ > 0
- ✅ UI上で表示される

---

### Step 6: パラメータ調整

**UI確認項目**:

#### 6.1 Counterfactual Parameters（3 Systems）
- [ ] Linear System: スライダーで係数調整
- [ ] Non-linear System: パラメータ入力
- [ ] ML-based System: モデル選択

**API確認**:
```bash
curl http://localhost:8080/api/counterfactuals \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_id": "abc123",
    "system": "linear",
    "parameters": {"coef_treatment": 1.5, "coef_age": 0.3}
  }'
```

#### 6.2 Shadow Price / Net Benefit（Wolfram評価）
- [ ] Shadow Price入力
- [ ] Net Benefit計算
- [ ] Wolfram式で即座に評価

**ファイル確認**:
```bash
# Wolfram script存在確認
ls -lh backend/wolfram/shadow_price_net_benefit.wls

# 実行確認
wolframscript -file backend/wolfram/shadow_price_net_benefit.wls
```

#### 6.3 推定量パラメータ
- [ ] Double ML: cross-fitting folds数
- [ ] Bootstrap: replications数
- [ ] Robust SE: HC0/HC1/HC2/HC3選択

**期待される結果**:
- ✅ パラメータ変更 → 再計算
- ✅ 結果がリアルタイム更新
- ✅ 図が再生成される

---

### Step 7: 結果ダウンロード

**UI確認項目**:
- [ ] LaTeX Regression Table (`reports/tables/regression_table.tex`)
- [ ] LaTeX Balance Table (`reports/tables/balance_table.tex`)
- [ ] CSV Estimates (`reports/tables/estimates.csv`)
- [ ] CSV Summary Metrics (`reports/tables/summary_metrics.csv`)
- [ ] HTML Report (`reports/index.html`)

**ファイル確認**:
```bash
ls -lh reports/tables/*.tex
ls -lh reports/tables/*.csv
ls -lh reports/*.html
```

**期待される結果**:
- ✅ 全ファイルが生成されている
- ✅ ダウンロード可能
- ✅ LaTeXがコンパイル可能

---

## 📸 証拠収集

### 必須スクリーンショット

1. **Upload画面**: ファイル選択 + Upload成功
2. **Mapping画面**: 自動推論結果 + 列選択UI
3. **Analysis実行中**: ローディング表示
4. **Results画面**: 
   - ATE推定値表示
   - 信頼区間図
   - Covariate Balance
5. **WolframONE図**:
   - CAS Radar Chart
   - 3D Causal Surface
   - ATE Animation（GIF）
6. **Counterfactual Parameters**: スライダー/入力UI
7. **Download**: ファイルリスト

### 必須ビデオ

**録画内容**:
1. ブラウザで http://localhost:4000/ にアクセス
2. `mini_retail.csv`をアップロード
3. 自動推論結果を確認
4. "Analyze"クリック
5. 結果表示（スクロールして全図を表示）
6. パラメータ調整（スライダー操作）
7. 再計算 → 図更新
8. ダウンロード

**ツール**:
```bash
# スクリーンショット
import pyautogui
pyautogui.screenshot('screenshot.png')

# ビデオ録画
ffmpeg -video_size 1920x1080 -framerate 30 -f x11grab -i :0.0 output.mp4
```

---

## 🚨 失敗時のデバッグ

### ログ確認
```bash
tail -f logs/engine_new.log
tail -f logs/gateway_new.log
tail -f logs/frontend_new.log
```

### よくあるエラー

#### Error 1: "Module not found"
```bash
pip3 install -r requirements.txt
```

#### Error 2: "Port already in use"
```bash
pkill -f "uvicorn.*engine"
pkill -f "uvicorn.*gateway"
pkill -f "vite.*frontend"
```

#### Error 3: "WolframScript not found"
```bash
which wolframscript
# インストール: https://www.wolfram.com/engine/
```

#### Error 4: "Permission denied"
```bash
chmod +x backend/wolfram/*.wls
```

---

## ✅ 成功基準

### Minimum Viable Product (MVP)
- [x] サービス起動
- [ ] ファイルアップロード成功
- [ ] Mapping自動推論
- [ ] 分析実行（エラーなし）
- [ ] 基本図表示（Matplotlib）
- [ ] 結果ダウンロード

### NASA/Googleレベル
- [ ] 全サービス稼働（health check緑）
- [ ] E2E動作（Upload → Analysis → Results）
- [ ] WolframONE図生成（14 base + 6 world-class）
- [ ] Objective-Specific図（2D/3D/Animated）
- [ ] Counterfactual Systems（3系統）
- [ ] Shadow Price/Net Benefit（Wolfram評価）
- [ ] パラメータ調整リアルタイム反映
- [ ] Publication-Ready Reports（LaTeX/CSV/HTML）
- [ ] デザイン（Inter font, Framer Motion, Icons）
- [ ] 証拠（スクリーンショット + ビデオ）

---

## 📋 実行チェックリスト

### Phase 1: 起動確認
- [ ] Engine起動（port 8080）
- [ ] Gateway起動（port 8081）
- [ ] Frontend起動（port 4000）
- [ ] Health check全て緑

### Phase 2: アップロード
- [ ] UIでファイル選択可能
- [ ] Upload成功
- [ ] 列名表示
- [ ] プレビュー表示

### Phase 3: Mapping
- [ ] 自動推論実行
- [ ] 推論結果表示
- [ ] Manual override可能
- [ ] Analyzeボタン有効化

### Phase 4: 分析
- [ ] Analyze実行
- [ ] ローディング表示
- [ ] エラーなし
- [ ] Results画面遷移

### Phase 5: 可視化
- [ ] Matplotlib図表示（10+図）
- [ ] WolframONE図表示（20+図）
- [ ] GIFアニメーション表示
- [ ] 全図がクリア（解像度十分）

### Phase 6: パラメータ
- [ ] Counterfactual UI表示
- [ ] スライダー操作可能
- [ ] 再計算実行
- [ ] 図更新

### Phase 7: ダウンロード
- [ ] LaTeX tables生成
- [ ] CSV files生成
- [ ] HTML report生成
- [ ] ダウンロード可能

### Phase 8: 証拠
- [ ] スクリーンショット7枚以上
- [ ] デモビデオ録画
- [ ] ログ出力保存
- [ ] ファイルリスト保存

---

**Generated**: 2025-11-01  
**Status**: 実行開始  
**Goal**: 完全なE2E動作証明

