#!/usr/bin/env python3
"""
現実的な中規模リテールデータ生成（5000行、欠損・異常値・不均衡含む）
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

np.random.seed(42)

N = 5000  # 現実的なサイズ

# === 基本情報 ===
user_ids = np.arange(1, N+1)
start_date = datetime(2023, 1, 1)
dates = [start_date + timedelta(days=int(x)) for x in np.random.randint(0, 365, N)]

# === 処置割り当て（不均衡：70% control, 30% treatment）===
treatment = np.random.choice([0, 1], size=N, p=[0.7, 0.3])

# === 共変量（現実的な分布と相関）===
# 年齢：20-70歳、正規分布
age = np.clip(np.random.normal(40, 15, N), 20, 70)

# 性別：やや女性多め
gender = np.random.choice(['M', 'F', 'Other'], size=N, p=[0.45, 0.53, 0.02])

# 地域：不均等分布
region = np.random.choice(['Tokyo', 'Osaka', 'Nagoya', 'Fukuoka', 'Sapporo', 'Other'],
                         size=N, p=[0.35, 0.20, 0.12, 0.10, 0.08, 0.15])

# 過去購入回数：Poisson分布（ロイヤルティ指標）
past_purchases = np.random.poisson(lam=5, size=N)

# SES（社会経済的地位）: 1-5のスコア
ses_score = np.random.choice([1,2,3,4,5], size=N, p=[0.1, 0.2, 0.4, 0.2, 0.1])

# === 傾向スコア（Propensity）===
# 真の処置割り当てメカニズム：年齢・SES・過去購入に依存
logit_ps = -2.0 + 0.03*age + 0.4*ses_score + 0.05*past_purchases
ps = 1 / (1 + np.exp(-logit_ps))
log_propensity = np.log(ps + 1e-10)

# === コスト（処置群のみ、欠損あり）===
cost_base = np.where(treatment == 1,
                     np.random.gamma(shape=2, scale=150, size=N),  # 平均300円
                     0)
# 10%の処置群でコスト記録なし（欠損）
cost = np.where((treatment == 1) & (np.random.rand(N) < 0.1), np.nan, cost_base)

# === アウトカム生成（複雑な因果構造）===
# True ATE = +200円（処置効果）
# + 交絡バイアス（年齢・SES・過去購入）
# + 異質性（年齢で効果が異なる）

# ベースライン傾向
baseline = 500 + 10*age + 100*ses_score + 20*past_purchases

# 処置効果（年齢による異質性: 若年層で大きい効果）
treatment_effect = treatment * (200 + 5*(50 - age))

# ノイズ（現実的なばらつき）
noise = np.random.normal(0, 200, N)

# 最終アウトカム
y = baseline + treatment_effect + noise

# === 現実的な問題を追加 ===
# 1. 外れ値（5%）
outlier_mask = np.random.rand(N) < 0.05
y[outlier_mask] = y[outlier_mask] * np.random.choice([0.1, 3.0, 5.0], size=outlier_mask.sum())

# 2. 欠損値（3%のアウトカム、5%の共変量）
y[np.random.rand(N) < 0.03] = np.nan
age[np.random.rand(N) < 0.05] = np.nan
# past_purchasesはfloatに変換してから欠損値を設定
past_purchases = past_purchases.astype(float)
past_purchases[np.random.rand(N) < 0.05] = np.nan

# 3. 負の値の発生（不正確な計測）
negative_mask = np.random.rand(N) < 0.02
y[negative_mask] = -np.abs(y[negative_mask])

# === DataFrame構築 ===
df = pd.DataFrame({
    'user_id': user_ids,
    'date': dates,
    'treatment': treatment,
    'y': y,
    'cost': cost,
    'log_propensity': log_propensity,
    'age': age,
    'gender': gender,
    'region': region,
    'past_purchases': past_purchases,
    'ses_score': ses_score,
    'propensity_score': ps
})

# === データ品質診断 ===
print("=== Realistic Retail Dataset (N=5000) ===")
print(f"Shape: {df.shape}")
print(f"\nTreatment distribution:")
print(df['treatment'].value_counts(normalize=True))
print(f"\nMissing values:")
print(df.isnull().sum())
print(f"\nOutcome statistics:")
print(df['y'].describe())
print(f"\nCost statistics (treatment group):")
print(df[df['treatment']==1]['cost'].describe())

# === 保存 ===
output_path = "/home/hirokionodera/cqox-complete_c/data/realistic_retail_5k.csv"
df.to_csv(output_path, index=False)
print(f"\n✓ Saved to: {output_path}")
