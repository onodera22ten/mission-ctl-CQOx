#!/usr/bin/env python3
"""
現実的な複雑テストデータ生成

要件:
- 中規模: 5,000行
- 複雑な列名（日本語 + 意図的にcontractと不一致）
- 欠損値: 15%
- 外れ値: 含む
- カテゴリ変数: 性別、地域、商品カテゴリ
- 時系列: 2023年1月〜2024年12月
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# 固定シード
np.random.seed(42)

# データサイズ
N = 5000

print(f"Generating realistic test data: {N} rows")

# 1. 基本ID
customer_ids = np.arange(1, N+1)

# 2. 日本語列名（意図的にcontractと不一致）
data = {
    "顧客ID": customer_ids,
    "購入日時": [
        (datetime(2023, 1, 1) + timedelta(days=np.random.randint(0, 730))).strftime("%Y-%m-%d %H:%M:%S")
        for _ in range(N)
    ],
    "キャンペーン適用": np.random.binomial(1, 0.5, N),  # treatment
    "売上金額": np.random.gamma(shape=2, scale=500, size=N),  # y (outcome)
    "顧客年齢": np.random.normal(40, 15, N).clip(18, 80).astype(int),
    "性別": np.random.choice(["男性", "女性", "その他"], N, p=[0.48, 0.48, 0.04]),
    "地域": np.random.choice(["東京", "大阪", "名古屋", "福岡", "札幌"], N, p=[0.3, 0.25, 0.2, 0.15, 0.1]),
    "商品カテゴリ": np.random.choice(["家電", "衣料", "食品", "書籍"], N, p=[0.3, 0.25, 0.25, 0.2]),
    "購入回数": np.random.poisson(lam=3, size=N),
    "Web閲覧時間_分": np.random.exponential(scale=20, size=N).clip(0, 300),
    "メール開封率": np.random.beta(a=2, b=5, size=N),
    "広告費": np.random.gamma(shape=1.5, scale=200, size=N),
    "前月購入額": np.random.gamma(shape=2, scale=300, size=N),
}

df = pd.DataFrame(data)

# 3. 欠損値を現実的に追加 (15%)
missing_cols = ["顧客年齢", "Web閲覧時間_分", "メール開封率", "前月購入額"]
for col in missing_cols:
    missing_mask = np.random.random(N) < 0.15
    df.loc[missing_mask, col] = np.nan

# 4. 外れ値を追加（5%のデータに）
outlier_mask = np.random.random(N) < 0.05
df.loc[outlier_mask, "売上金額"] = df.loc[outlier_mask, "売上金額"] * 10

# 5. treatment effectを追加（因果効果を埋め込む）
treatment_effect = 300  # ATEを300に設定
noise = np.random.normal(0, 50, N)
df.loc[df["キャンペーン適用"] == 1, "売上金額"] += treatment_effect + noise[df["キャンペーン適用"] == 1]

# 6. Confoundingを追加（年齢がtreatmentとoutcomeに影響）
age_effect_on_treatment = (df["顧客年齢"] - 40) / 50  # 年齢が高いほどtreatment確率が高い
df["キャンペーン適用"] = ((df["キャンペーン適用"] + age_effect_on_treatment) > 0.5).astype(int)

age_effect_on_outcome = (df["顧客年齢"] - 40) * 10  # 年齢が高いほど購入額が高い
df["売上金額"] += age_effect_on_outcome

# 7. 統計サマリ表示
print("\n=== Data Summary ===")
print(f"Shape: {df.shape}")
print(f"Columns: {list(df.columns)}")
print(f"\nTreatment balance:")
print(df["キャンペーン適用"].value_counts())
print(f"\nOutcome stats:")
print(df["売上金額"].describe())
print(f"\nMissing values:")
print(df.isnull().sum()[df.isnull().sum() > 0])

# 8. 保存
output_path = "realistic_test_data.csv"
df.to_csv(output_path, index=False, encoding="utf-8-sig")
print(f"\n✅ Saved to: {output_path}")
print(f"File size: {df.memory_usage(deep=True).sum() / 1024:.1f} KB")

# 9. 追加情報
print("\n=== Expected Mapping ===")
print("顧客ID → unit_id")
print("購入日時 → time")
print("キャンペーン適用 → treatment")
print("売上金額 → y")
print("広告費 → cost")
print("顧客年齢, 性別, 地域, 商品カテゴリ, etc → covariates (features)")
print("\nExpected ATE: ~300 (embedded in data)")

