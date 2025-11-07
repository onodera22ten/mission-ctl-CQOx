# CQOx UI実装ガイド（完全版）

**対象レベル**: NASA/Google極秘PJ品質
**最終更新**: 2025-10-31

---

## 📋 目次

1. [UIアーキテクチャ概要](#uiアーキテクチャ概要)
2. [UIコンポーネント実装詳細](#uiコンポーネント実装詳細)
3. [データフロー詳細](#データフロー詳細)
4. [API連携詳細](#api連携詳細)
5. [セキュリティ実装](#セキュリティ実装)
6. [エラーハンドリング](#エラーハンドリング)
7. [パフォーマンス最適化](#パフォーマンス最適化)

---

## UIアーキテクチャ概要

### 技術スタック

```
Frontend Stack:
├── React 18.x (UI フレームワーク)
├── TypeScript (型安全性)
├── Vite (ビルドツール)
├── Axios (HTTP クライアント)
├── Recharts (チャート可視化)
└── Custom Components (タスクパネル、図表表示)
```

### ディレクトリ構造

```
frontend/
├── src/
│   ├── ui/
│   │   ├── App.tsx                    # メインアプリケーション
│   │   ├── TasksPanel.tsx             # タスクパネル（診断、推定など）
│   │   └── FiguresPanel.tsx           # 図表表示パネル
│   ├── components/
│   │   ├── MetricsDashboard.tsx       # メトリクスダッシュボード
│   │   └── figures/
│   │       └── Figure.tsx             # 図表コンポーネント
│   ├── lib/
│   │   └── client.ts                  # API クライアント
│   └── index.html                     # エントリーポイント
├── package.json                       # 依存関係
├── vite.config.ts                     # Vite設定
└── dist/                              # ビルド出力
```

---

## UIコンポーネント実装詳細

### 1. メインアプリケーション (`App.tsx`)

#### 機能概要

メインアプリケーションは以下のフローで動作します：

```
1. ファイルアップロード
   ↓
2. 自動ロール推論（列マッピング）
   ↓
3. ユーザー確認・調整
   ↓
4. 分析実行
   ↓
5. 結果表示（推定量、図表、診断）
```

#### 実装詳細

**ファイルアップロード**:

```typescript
// frontend/src/ui/App.tsx (抜粋)

async function onUpload() {
  if (!file) return;
  setBusy(true);
  try {
    // 1. ファイルアップロード
    const up = await uploadFile(file);
    setDatasetId(up.dataset_id);

    // 2. 自動ロール推論
    const inference = await inferRoles(up.dataset_id);

    // 3. マッピング設定
    const auto: Mapping = {
      y: inference.mapping.outcome || inference.mapping.y || "",
      treatment: inference.mapping.treatment || "",
      unit_id: inference.mapping.unit_id || "",
      time: inference.mapping.time || "",
      cost: inference.mapping.cost || "",
      log_propensity: inference.mapping.propensity || "",
    };

    // 4. ドメイン自動設定
    if (inference.domain?.domain) {
      setDomain(inference.domain.domain);
    }

    setMapping(auto);
    setResult(null);
  } finally {
    setBusy(false);
  }
}
```

**分析実行**:

```typescript
async function onAnalyze() {
  if (!canAnalyze) return;
  setBusy(true);
  try {
    // API呼び出し
    const analysisResult = await analyzeComprehensive({
      dataset_id: datasetId,
      mapping: mapping,
      objective: domain,
      auto_select_columns: true,
    });
    
    setResult(analysisResult);
  } finally {
    setBusy(false);
  }
}
```

#### UIレイアウト

```
┌─────────────────────────────────────────┐
│  CQOx Causal Inference Platform         │
├─────────────────────────────────────────┤
│  [ファイル選択] [ドメイン選択] [Upload] │
│  [Analyze]                              │
├─────────────────────────────────────────┤
│  タスクタブ: [診断] [推定] [ヘテロ] ... │
├─────────────────────────────────────────┤
│  図表グリッド表示                        │
│  ┌──────┐ ┌──────┐ ┌──────┐            │
│  │ Fig1 │ │ Fig2 │ │ Fig3 │            │
│  └──────┘ └──────┘ └──────┘            │
└─────────────────────────────────────────┘
```

### 2. タスクパネル (`TasksPanel.tsx`)

#### タスク定義

```typescript
const TASKS = [
  {
    key: "diagnostics",
    name: "診断 (Diagnostics)",
    icon: "🔍",
    color: "#3b82f6",
    panels: [
      "quality_gates_board",
      "cas_radar",
      "love_plot",
      "covariate_correlation",
      "propensity_overlap",
      "prediction_vs_residual",
      "missing_map",
      "outlier_impact",
      "missing_mechanism",
    ],
  },
  // ... 他のタスク
];
```

#### 実装ポイント

1. **動的パネル表示**: 利用可能な図表のみ表示
2. **タスク別フィルタリング**: 各タスクに応じた図表のみ表示
3. **レスポンシブデザイン**: グリッドレイアウトで自動調整

### 3. APIクライアント (`client.ts`)

#### 主要関数

```typescript
// frontend/src/lib/client.ts

// 1. ファイルアップロード
export async function uploadFile(file: File) {
  const fd = new FormData();
  fd.append("file", file);
  const { data } = await api.post("/upload", fd);
  return data;
}

// 2. ロール推論
export async function inferRoles(dataset_id: string) {
  const { data } = await api.post("/roles/infer", { dataset_id });
  return data;
}

// 3. 包括的分析
export async function analyzeComprehensive(params: any) {
  const { data } = await api.post("/analyze/comprehensive", params);
  return data;
}
```

---

## データフロー詳細

### 1. ファイルアップロードフロー

```
ユーザー操作
    ↓
[ファイル選択] → FormData作成
    ↓
POST /api/upload
    ↓
バックエンド処理:
  ├── ファイル検証
  ├── データ読み込み（CSV/JSON/Parquet対応）
  ├── メタデータ抽出
  └── データセットID生成
    ↓
レスポンス:
{
  "dataset_id": "edu_2024_001",
  "meta": {
    "columns": [...],
    "dtypes": {...},
    "preview": [...]
  }
    ↓
自動ロール推論開始
```

### 2. 自動ロール推論フロー

```
POST /api/roles/infer
    ↓
バックエンド処理:
  ├── 列名パターンマッチング
  ├── データ型分析
  ├── 統計的特徴抽出
  └── 信頼度スコア計算
    ↓
レスポンス:
{
  "mapping": {
    "y": "test_score",
    "treatment": "intervention",
    "unit_id": "student_id",
    ...
  },
  "confidence": {
    "y": 0.95,
    "treatment": 0.88,
    ...
  },
  "domain": {
    "domain": "education",
    "confidence": 0.92
  }
}
    ↓
UI上で確認・調整可能
```

### 3. 分析実行フロー

```
POST /api/analyze/comprehensive
    ↓
バックエンド処理:
  ├── データ読み込み
  ├── バリデーション（Leakage, VIF, Missing, Balance）
  ├── 列自動選択
  ├── 11種類の推定量実行
  ├── 品質ゲートチェック
  ├── 42種類の図表生成（WolframONE）
  ├── 反実仮想3系統推定
  ├── 影の価格/純便益計算
  └── 結果永続化（PostgreSQL）
    ↓
レスポンス:
{
  "results": [...],      # 推定量結果
  "figures": {...},     # 図表URL
  "counterfactuals": {...},  # 反実仮想結果
  "policy_metrics": {...},   # 影の価格/純便益
  "diagnostics": {...},      # 診断情報
  ...
}
    ↓
UIで結果表示
```

---

## API連携詳細

### エンドポイント一覧

| エンドポイント | メソッド | 説明 |
|--------------|---------|------|
| `/api/upload` | POST | ファイルアップロード |
| `/api/roles/infer` | POST | 自動ロール推論 |
| `/api/roles/profile` | GET | ロールプロファイル取得 |
| `/api/analyze/comprehensive` | POST | 包括的分析実行 |

### リクエスト/レスポンス形式

#### ファイルアップロード

**リクエスト**:
```typescript
FormData {
  file: File  // CSV, TSV, JSON, Parquet, XLSX対応
}
```

**レスポンス**:
```json
{
  "ok": true,
  "dataset_id": "edu_2024_001",
  "meta": {
    "columns": ["student_id", "test_score", "intervention", ...],
    "dtypes": {
      "student_id": "object",
      "test_score": "float64",
      "intervention": "int64"
    },
    "preview": [
      {"student_id": "S001", "test_score": 85.5, ...}
    ]
  },
  "candidates": {
    "y": ["test_score", "final_grade", "outcome"],
    "treatment": ["intervention", "treatment", "treated"],
    ...
  },
  "stats": [
    {"column": "test_score", "dtype": "float64", "na": 0},
    ...
  ]
}
```

#### 包括的分析

**リクエスト**:
```json
{
  "dataset_id": "edu_2024_001",
  "mapping": {
    "y": "test_score",
    "treatment": "intervention",
    "unit_id": "student_id",
    "time": "semester",
    "cost": "cost_per_student"
  },
  "objective": "education",
  "auto_select_columns": true,
  "parameters": {
    "inference": {
      "method": "robust_se"  // または "bootstrap"
    }
  }
}
```

**レスポンス**:
```json
{
  "job_id": "job_20241031_001",
  "results": [
    {
      "name": "tvce",
      "tau_hat": 2.45,
      "se": 0.12,
      "ci_lower": 2.21,
      "ci_upper": 2.69,
      "status": "success",
      "diagnostics": {
        "method": "double_ml_plr",
        "se_type": "robust_hc1"
      }
    },
    ...
  ],
  "figures": {
    "education_event_study_2d": "/reports/figures/job_xxx/education_event_study_2d.png",
    "education_event_study_3d": "/reports/figures/job_xxx/education_event_study_3d.png",
    "education_event_study_animated": "/reports/figures/job_xxx/education_event_study_animated.gif",
    ...
  },
  "counterfactuals": {
    "linear": {
      "system_type": "linear",
      "mean_treatment_effect": 2.45,
      "r_squared": 0.85,
      "parameters": {...}
    },
    "nonlinear": {...},
    "ml_based": {...}
  },
  "policy_metrics": {
    "shadow_price": {
      "value": 2.5,
      "formula": "τ/c",
      "interpretation": "Effect per unit cost"
    },
    "net_benefit": {
      "value": 1.8,
      "formula": "τ - λc",
      "interpretation": "Net benefit"
    }
  },
  "diagnostics": {
    "balance": {
      "smd_max": 0.08,
      "smd_mean": 0.04,
      "n_variables": 15,
      "imbalanced": 0
    },
    ...
  }
}
```

---

## セキュリティ実装

### 1. 認証・認可

**現在の実装状況**:
- ✅ JWT認証（`backend/security/jwt_auth.py`）
- ✅ OAuth2対応準備済み
- ⚠️ UI上での認証フロー未統合

**実装が必要な機能**:

```typescript
// frontend/src/lib/auth.ts (新規作成が必要)

export async function login(username: string, password: string) {
  const { data } = await api.post("/auth/login", { username, password });
  // JWTトークンをlocalStorageに保存
  localStorage.setItem("jwt_token", data.token);
  return data;
}

export function logout() {
  localStorage.removeItem("jwt_token");
  window.location.href = "/login";
}

// APIリクエストにトークン自動付与
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("jwt_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});
```

### 2. 入力検証

**フロントエンド検証**:
- ファイルサイズ制限（最大100MB）
- ファイル形式検証
- マッピング必須項目チェック

### 3. エラーハンドリング

```typescript
// frontend/src/lib/client.ts

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // 認証エラー → ログインページへ
      window.location.href = "/login";
    } else if (error.response?.status === 403) {
      // 権限エラー
      alert("アクセス権限がありません");
    } else if (error.response?.status >= 500) {
      // サーバーエラー
      alert("サーバーエラーが発生しました。管理者に連絡してください。");
    }
    return Promise.reject(error);
  }
);
```

---

## エラーハンドリング

### ユーザーフレンドリーなエラーメッセージ

```typescript
// frontend/src/ui/App.tsx

async function onAnalyze() {
  try {
    const result = await analyzeComprehensive({...});
    setResult(result);
  } catch (error: any) {
    // エラーメッセージを日本語で表示
    const errorMessage = error.response?.data?.detail || 
                        error.response?.data?.error ||
                        "分析の実行に失敗しました。";
    
    alert(`エラー: ${errorMessage}`);
    
    // 詳細ログ（開発環境のみ）
    if (process.env.NODE_ENV === "development") {
      console.error("Analysis error:", error);
    }
  }
}
```

---

## パフォーマンス最適化

### 1. 図表の遅延読み込み

```typescript
// frontend/src/components/figures/Figure.tsx

import { lazy, Suspense } from "react";

const LazyFigure = lazy(() => import("./Figure"));

export function Figure({ src }: { src: string }) {
  return (
    <Suspense fallback={<div>読み込み中...</div>}>
      <LazyFigure src={src} />
    </Suspense>
  );
}
```

### 2. APIリクエストのキャッシング

```typescript
// frontend/src/lib/client.ts

const cache = new Map<string, { data: any; timestamp: number }>();
const CACHE_TTL = 5 * 60 * 1000; // 5分

export async function fetchRolesProfile(dataset_id: string) {
  const cacheKey = `profile_${dataset_id}`;
  const cached = cache.get(cacheKey);
  
  if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
    return cached.data;
  }
  
  const { data } = await api.get("/roles/profile", { params: { dataset_id } });
  cache.set(cacheKey, { data, timestamp: Date.now() });
  return data;
}
```

---

## デプロイ方法

### 開発環境

```bash
cd frontend
npm install
npm run dev
# http://localhost:5173 で起動
```

### 本番環境

```bash
# ビルド
npm run build

# Dockerイメージ作成（Dockerfile.frontend使用）
docker build -f Dockerfile.frontend -t cqox-frontend .

# Docker Composeで起動
docker-compose up -d frontend
```

---

## トラブルシューティング

### よくある問題

1. **API接続エラー**
   - 確認: `backend/engine/server.py`が起動しているか
   - 確認: CORS設定が正しいか

2. **ファイルアップロード失敗**
   - 確認: ファイルサイズ制限（100MB）
   - 確認: ファイル形式がサポートされているか

3. **図表が表示されない**
   - 確認: `/reports/figures/`ディレクトリが存在するか
   - 確認: バックエンドの図表生成が成功しているか

---

## 次のステップ（NASA/Googleレベルへの向上）

### 推奨実装項目

1. **リアルタイム更新**
   - WebSocket統合で分析進捗をリアルタイム表示

2. **高度な可視化**
   - インタラクティブな図表（Plotly.js統合）
   - 3D可視化の直接表示

3. **コラボレーション機能**
   - 分析結果の共有
   - コメント機能

4. **アクセシビリティ**
   - WCAG 2.1 AA準拠
   - スクリーンリーダー対応

---

**Generated**: 2025-10-31
**Version**: 1.0.0

