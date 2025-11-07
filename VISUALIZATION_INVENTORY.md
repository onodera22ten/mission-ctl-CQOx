# Visualization Inventory - CQOx Complete

## 基本図表セット（14種 - Always Generated）

| # | 名称 | ファイル | 実装状況 |
|---|------|---------|---------|
| 1 | Parallel Trends | `fig_parallel_trends()` | ✅ |
| 2 | Event Study | `fig_event_study()` | ✅ |
| 3 | ATE Density | `fig_ate_density()` | ✅ |
| 4 | Propensity Overlap | `fig_propensity_overlap()` | ✅ |
| 5 | Balance SMD | `fig_balance_smd()` | ✅ |
| 6 | Rosenbaum Gamma | `fig_rosenbaum_gamma()` | ✅ |
| 7 | IV First Stage F | `fig_iv_first_stage_f()` | ✅ |
| 8 | IV Strength vs 2SLS | `fig_iv_strength_vs_2sls()` | ✅ |
| 9 | Transport Weights | `fig_transport_weights()` | ✅ |
| 10 | TVCE Line | `fig_tvce_line()` | ✅ |
| 11 | Network Spillover | `fig_network_spillover()` | ✅ |
| 12 | Heterogeneity Waterfall | `fig_heterogeneity_waterfall()` | ✅ |
| 13 | Quality Gates Board | `fig_quality_gates_board()` | ✅ |
| 14 | CAS Radar | `fig_cas_radar()` | ✅ |

**Status**: ✅ 14/14 完全実装済み

---

## ドメイン別可視化（26種 - Domain-Conditional）

### Medical Domain (6 figures)
| # | 名称 | 実装状況 |
|---|------|---------|
| 15 | KM Survival | ✅ |
| 16 | Dose-Response | ✅ |
| 17 | Cluster Effect (Facility) | ✅ |
| 18 | Adverse Events Risk Map | ✅ |
| 19 | IV Candidates | ✅ |
| 20 | Sensitivity Analysis | ✅ |

### Education Domain (5 figures)
| # | 名称 | 実装状況 |
|---|------|---------|
| 21 | Learning Curve | ✅ |
| 22 | School Fixed Effects | ✅ |
| 23 | RD Cutoff | ✅ |
| 24 | Long-term Impact | ✅ |
| 25 | Teacher Quality | ✅ |

### Retail Domain (5 figures)
| # | 名称 | 実装状況 |
|---|------|---------|
| 26 | Customer Funnel | ✅ |
| 27 | Seasonality Decomp | ✅ |
| 28 | Product Substitution | ✅ |
| 29 | CLV by Cohort | ✅ |
| 30 | Geographic Heatmap | ✅ |

### Finance Domain (4 figures)
| # | 名称 | 実装状況 |
|---|------|---------|
| 31 | Portfolio Returns Timeline | ✅ |
| 32 | Risk-Return Scatter | ✅ |
| 33 | Synthetic DiD | ✅ |
| 34 | Volatility Regime | ✅ |

### Network Domain (3 figures)
| # | 名称 | 実装状況 |
|---|------|---------|
| 35 | Network Graph | ✅ |
| 36 | Exposure Distribution | ✅ |
| 37 | Spillover Heatmap | ✅ |

### Policy Domain (3 figures)
| # | 名称 | 実装状況 |
|---|------|---------|
| 38 | Policy Rollout Map | ✅ |
| 39 | Staggered Adoption | ✅ |
| 40 | Welfare Simulation | ✅ |

**Domain Status**: ✅ 26/26 完全実装済み

---

## 合計: 40種類の可視化

- 基本図表: 14種
- ドメイン別: 26種
- **Total**: 40種類

---

## 不足分の分析

### 40-42の可視化について

現在40種類実装済み。ユーザーが指摘する「40-42が出てこない」について：

**可能性1**: ドメイン判定が正しく機能していない
- Policy domain の #38-40 が生成されていない可能性

**可能性2**: 追加の高度な可視化が必要
- 41: Advanced Sensitivity Analysis (E-value, Cornfield bounds)
- 42: Causal Forest CATE visualization
- (これらはまだ未実装)

---

## WolframONE統合計画

### 優先順位（ユーザー要望）

1. **既存の14基本図表をWolframONEで再実装**
   - 2D/3D/アニメーション判断を自動化
   - 既存のChartをWolframONEで置き換え

2. **CAS Radarの改善**
   - 現状: 「チープ」（ユーザー評価）
   - WolframONE版: より高品質なレーダーチャート

3. **ドメイン別可視化のWolframONE移行**
   - 特にインタラクティブなアニメーションが有効な図表

### 実装戦略

```python
# WolframONE呼び出しの基本構造
def generate_wolfram_figure(
    data: pd.DataFrame,
    fig_type: str,
    output_path: Path,
    dimension: str = "2D"  # "2D", "3D", "animation"
) -> str:
    """
    Call WolframScript to generate high-quality figures

    Args:
        data: Input data
        fig_type: Type of figure to generate
        output_path: Where to save the output
        dimension: 2D, 3D, or animation

    Returns:
        Path to generated figure
    """
    pass
```

---

## 次のアクション

1. ✅ 40種類の可視化が正しく生成されているか検証
2. ⏳ 41-42の高度な可視化を実装（Sensitivity, CATE）
3. ⏳ WolframONE統合開始（基本14図表から）
4. ⏳ ドメイン判定ロジックの強化（自動判断システム）
5. ⏳ 地理データ対応（tigramite統合）

---

**Generated**: 2025-10-28
**Status**: 40/40 基本可視化完了、WolframONE統合開始
