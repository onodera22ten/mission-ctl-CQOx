# backend/engine/figures.py
from __future__ import annotations
import base64, io, json, math, uuid
from pathlib import Path
from typing import Dict, Any, List, Optional

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Plotly は任意（event study をHTMLで出したい場合）
try:
    import plotly.graph_objects as go
    from plotly.offline import plot as plotly_plot
    HAS_PLOTLY = True
except Exception:
    HAS_PLOTLY = False

FIG_KEYS = [
    "parallel_trends","event_study","ate_density","propensity_overlap","balance_smd",
    "rosenbaum_gamma","iv_first_stage_f","iv_strength_vs_2sls","transport_weights",
    "tvce_line","network_spillover","heterogeneity_waterfall","quality_gates_board",
    "cas_radar",
    "evalue_sensitivity","cate_forest"  # Figures 41-42: Advanced
]

def _ensure(p: Path): p.mkdir(parents=True, exist_ok=True)

def _save_fig(fig, path: Path):
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)

def _png_fallback_html(png_path: Path, html_path: Path, title: str):
    # 依存を増やさず HTML 化
    b64 = base64.b64encode(png_path.read_bytes()).decode("ascii")
    html = f"""<!doctype html><meta charset="utf-8">
<title>{title}</title>
<img src="data:image/png;base64,{b64}" style="max-width:100%;height:auto"/>
"""
    html_path.write_text(html, encoding="utf-8")

def _maybe_datetime(s: pd.Series) -> pd.Series:
    try:
        return pd.to_datetime(s, errors="coerce")
    except Exception:
        return s

# 1. Parallel Trends
def fig_parallel_trends(df: pd.DataFrame, m: Dict[str,str], out: Path) -> Optional[str]:
    y, t = m["y"], m["treatment"]
    time = m.get("time")
    fig = plt.figure(figsize=(6,3.5))
    ax = fig.add_subplot(111)
    if time and time in df:
        g = df.groupby([_maybe_datetime(df[time]), df[t]])[y].mean().reset_index()
        piv = g.pivot(index=time, columns=t, values=y)
        if 0 in piv: ax.plot(piv.index, piv[0], label="control")
        if 1 in piv: ax.plot(piv.index, piv[1], label="treated")
        ax.set_xlabel(time); ax.set_ylabel(f"mean({y})")
        ax.set_title("Parallel Trends")
        ax.legend()
    else:
        means = [df.loc[df[t]==0, y].mean(), df.loc[df[t]==1, y].mean()]
        ax.bar(["control","treated"], means); ax.set_title("Group Means"); ax.set_ylabel(y)
    path = out / "parallel_trends.png"; _save_fig(fig, path); return str(path)

# 2. Event Study（HTML。なければPNG→HTMLラップ）
def fig_event_study(df: pd.DataFrame, m: Dict[str,str], out: Path) -> Optional[str]:
    time, t, y = m.get("time"), m["treatment"], m["y"]
    if not time or time not in df: return None
    dt = _maybe_datetime(df[time])
    df2 = df.copy()
    df2["_t"] = df2[t].astype(int)
    df2["_rel"] = (dt - dt.min()).dt.days  # モックの相対期間
    betas = df2.groupby("_rel").apply(lambda g: g.loc[g["_t"]==1, y].mean() - g.loc[g["_t"]==0, y].mean())
    idx = sorted(betas.index.tolist())
    vals = [float(betas.get(i, np.nan)) for i in idx]
    if HAS_PLOTLY:
        fig = go.Figure([go.Scatter(x=idx, y=vals, mode="lines+markers")])
        fig.update_layout(title="Event Study Coefficients", xaxis_title="relative period (days)", yaxis_title="Δy")
        html_path = out / "event_study.html"; plotly_plot(fig, filename=str(html_path), auto_open=False, include_plotlyjs="cdn"); 
        return str(html_path)
    else:
        f = plt.figure(figsize=(6,3.5)); ax=f.add_subplot(111)
        ax.plot(idx, vals, marker="o"); ax.axhline(0, color="gray", lw=1)
        ax.set_title("Event Study (fallback)"); ax.set_xlabel("relative period"); ax.set_ylabel("Δy")
        png = out / "event_study.png"; _save_fig(f, png)
        html = out / "event_study.html"; _png_fallback_html(png, html, "Event Study")
        return str(html)

# 3. ATE Density（推定器別：ここではモック値）
def fig_ate_density(df, m, out) -> Optional[str]:
    y, t = m["y"], m["treatment"]
    treated = df.loc[df[t]==1, y].astype(float).dropna()
    control = df.loc[df[t]==0, y].astype(float).dropna()
    fig=plt.figure(figsize=(5,3.5)); ax=fig.add_subplot(111)
    ax.hist(control, bins=30, alpha=0.6, label="control"); ax.hist(treated, bins=30, alpha=0.6, label="treated")
    ax.set_title("ATE Density (by group)"); ax.legend(); path=out/"ate_density.png"; _save_fig(fig, path); return str(path)

# 4. Propensity Overlap
def fig_propensity_overlap(df, m, out) -> Optional[str]:
    p = m.get("log_propensity") or "log_propensity"
    if p not in df: return None
    t = m["treatment"]; fig=plt.figure(figsize=(5,3.5)); ax=fig.add_subplot(111)
    ax.hist(df.loc[df[t]==0, p], bins=30, alpha=0.6, label="control")
    ax.hist(df.loc[df[t]==1, p], bins=30, alpha=0.6, label="treated")
    ax.set_title("Propensity Overlap (logit)"); ax.legend()
    path=out/"propensity_overlap.png"; _save_fig(fig, path); return str(path)

# 5. Balance SMD Lollipop
def _smd(a, b):
    a, b = np.asarray(a), np.asarray(b)
    v = np.sqrt((np.nanvar(a, ddof=1)+np.nanvar(b, ddof=1))/2.0 + 1e-12); 
    return float(abs(np.nanmean(a)-np.nanmean(b))/max(v,1e-12))
def fig_balance_smd(df, m, out) -> Optional[str]:
    y, t = m["y"], m["treatment"]
    num_cols = [c for c in df.columns if c not in {y,t} and pd.api.types.is_numeric_dtype(df[c])]
    smd = [(c, _smd(df.loc[df[t]==1, c], df.loc[df[t]==0, c])) for c in num_cols][:18]
    if not smd: return None
    smd.sort(key=lambda x:x[1]); labs=[s[0] for s in smd]; vals=[s[1] for s in smd]
    fig=plt.figure(figsize=(6,0.5*len(smd)+1.5)); ax=fig.add_subplot(111)
    ax.hlines(range(len(vals)), 0, vals); ax.plot(vals, range(len(vals)), "o"); ax.set_yticks(range(len(vals))); ax.set_yticklabels(labs)
    ax.set_title("Balance SMD"); ax.set_xlabel("SMD")
    path=out/"balance_smd.png"; _save_fig(fig, path); return str(path)

# 6. Rosenbaum Sensitivity（モック曲線）
def fig_rosenbaum_gamma(df,m,out)->Optional[str]:
    gammas = np.linspace(1.0, 2.0, 21); eff = 1.0/np.sqrt(gammas)  # 仮の形
    fig=plt.figure(figsize=(5,3)); ax=fig.add_subplot(111); ax.plot(gammas, eff, marker="o"); ax.set_title("Rosenbaum Γ Sensitivity"); ax.set_xlabel("Γ"); ax.set_ylabel("Effect bound")
    path=out/"rosenbaum_gamma.png"; _save_fig(fig,path); return str(path)

# 7. IV First-Stage F
def fig_iv_first_stage_f(df,m,out)->Optional[str]:
    if "z" not in df or m["treatment"] not in df: return None
    # F 統計モック：相関から単純化
    r = np.corrcoef(df["z"], df[m["treatment"]])[0,1]; F = (len(df)-2)*r*r/(1-r*r+1e-9)
    fig=plt.figure(figsize=(4,3)); ax=fig.add_subplot(111); ax.hist([F], bins=1); ax.axvline(10, color="r", ls="--", label="threshold 10")
    ax.set_title("IV First-Stage F"); ax.legend(); path=out/"iv_first_stage_f.png"; _save_fig(fig,path); return str(path)

# 8. IV 強度 vs 2SLS 効果
def fig_iv_strength_vs_2sls(df,m,out)->Optional[str]:
    if "z" not in df or m["y"] not in df: return None
    strength = np.linspace(0.1,1.0,10); eff = 0.5 + 0.3*(strength-0.5)  # モック
    fig=plt.figure(figsize=(4.5,3)); ax=fig.add_subplot(111); ax.plot(strength, eff, marker="o"); ax.set_title("IV Strength vs 2SLS"); ax.set_xlabel("strength"); ax.set_ylabel("tau_2sls")
    path=out/"iv_strength_vs_2sls.png"; _save_fig(fig,path); return str(path)

# 9. Transport Weights
def fig_transport_weights(df,m,out)->Optional[str]:
    wcol = "transport_weight" if "transport_weight" in df else None
    if wcol is None:  # モック
        rng = np.random.default_rng(123); s = pd.Series(rng.random(len(df)))
    else:
        s = df[wcol]
    fig=plt.figure(figsize=(4.5,3)); ax=fig.add_subplot(111); ax.hist(s, bins=30); ax.set_title("Transport Weights")
    path=out/"transport_weights.png"; _save_fig(fig,path); return str(path)

#10. TVCE（時変効果）
def fig_tvce_line(df,m,out)->Optional[str]:
    time, y, t = m.get("time"), m["y"], m["treatment"]
    if not time or time not in df: return None
    dt = _maybe_datetime(df[time]); g=df.groupby(dt.dt.to_period("D"))\
        .apply(lambda g: g.loc[g[t]==1, y].mean()-g.loc[g[t]==0, y].mean())
    fig=plt.figure(figsize=(6,3.5)); ax=fig.add_subplot(111); ax.plot(g.index.astype(str), g.values, marker="o"); ax.axhline(0,color="gray",lw=1)
    ax.set_title("Time-Varying Effect (TVCE)"); ax.set_xlabel("time"); ax.set_ylabel("Δy"); path=out/"tvce_line.png"; _save_fig(fig,path); return str(path)

#11. Network Spillover（ヒートマップ or 近接行列が無ければモック）
def fig_network_spillover(df,m,out)->Optional[str]:
    # 期待：別CSV "network_edges.csv" or "adjacency.csv" があれば読み込む実装に拡張可
    n=30; rng=np.random.default_rng(42); adj=rng.random((n,n)); np.fill_diagonal(adj,0)
    fig=plt.figure(figsize=(4,4)); ax=fig.add_subplot(111); im=ax.imshow(adj, aspect="auto"); fig.colorbar(im, ax=ax); ax.set_title("Network Spillover (mock)")
    path=out/"network_spillover.png"; _save_fig(fig,path); return str(path)

#12. Heterogeneity Waterfall（segmentごと上位10）
def fig_heterogeneity_waterfall(df,m,out)->Optional[str]:
    seg = "segment" if "segment" in df else None
    if seg is None: return None
    y, t = m["y"], m["treatment"]
    eff = df.groupby(seg).apply(lambda g: g.loc[g[t]==1, y].mean()-g.loc[g[t]==0, y].mean()).sort_values(ascending=False)[:10]
    fig=plt.figure(figsize=(6,3)); ax=fig.add_subplot(111); ax.bar(range(len(eff)), eff.values); ax.set_xticks(range(len(eff))); ax.set_xticklabels(eff.index, rotation=30, ha="right")
    ax.set_title("Heterogeneity (Top 10)"); path=out/"heterogeneity_waterfall.png"; _save_fig(fig,path); return str(path)

#13. Quality Gates Board（合否7枚→ボード）
def fig_quality_gates_board(gates: Dict[str,Any], out: Path) -> Optional[str]:
    keys = ["ess","overlap","weak_iv","sensitivity","balance","mono","placebo"]
    vals = [(k, bool(gates.get(k,{}).get("pass", False))) for k in keys]
    fig=plt.figure(figsize=(6,2.8)); ax=fig.add_subplot(111); 
    ax.axis("off"); 
    text = "\n".join([f"{k:>10}: {'PASS' if v else 'FAIL'}" for k,v in vals]); 
    ax.text(0.05, 0.95, text, va="top", family="monospace", fontsize=12)
    path=out/"quality_gates_board.png"; _save_fig(fig,path); return str(path)

#14. CAS Radar（5軸モック）
def fig_cas_radar(scores: Dict[str,float], out: Path) -> Optional[str]:
    axes = ["internal","external","transport","robustness","stability"]
    vals = [float(scores.get(a,0.7)) for a in axes]
    # レーダー
    angles = np.linspace(0, 2*np.pi, len(axes), endpoint=False).tolist(); vals2 = vals + vals[:1]; angles2 = angles + angles[:1]
    fig=plt.figure(figsize=(4.2,4.2)); ax=fig.add_subplot(111, polar=True); ax.plot(angles2, vals2); ax.fill(angles2, vals2, alpha=0.25)
    ax.set_thetagrids(np.degrees(angles), axes); ax.set_title("CAS Radar")
    path=out/"cas_radar.png"; _save_fig(fig,path); return str(path)

def generate_all(df: pd.DataFrame, mapping: Dict[str,str], out_dir: Path,
                 gates: Optional[Dict[str,Any]]=None, cas_scores: Optional[Dict[str,float]]=None) -> Dict[str,str]:
    """14種の図を保存し、{key: '/reports/figures/<job_id>/file'} を返す"""
    _ensure(out_dir)
    m = mapping
    out: Dict[str,str] = {}

    def add(key:str, p: Optional[str]):
        if p: out[key] = p

    add("parallel_trends",      fig_parallel_trends(df, m, out_dir))
    add("event_study",          fig_event_study(df, m, out_dir))
    add("ate_density",          fig_ate_density(df, m, out_dir))
    add("propensity_overlap",   fig_propensity_overlap(df, m, out_dir))
    add("balance_smd",          fig_balance_smd(df, m, out_dir))
    add("rosenbaum_gamma",      fig_rosenbaum_gamma(df, m, out_dir))
    add("iv_first_stage_f",     fig_iv_first_stage_f(df, m, out_dir))
    add("iv_strength_vs_2sls",  fig_iv_strength_vs_2sls(df, m, out_dir))
    add("transport_weights",    fig_transport_weights(df, m, out_dir))
    add("tvce_line",            fig_tvce_line(df, m, out_dir))
    add("network_spillover",    fig_network_spillover(df, m, out_dir))
    add("heterogeneity_waterfall", fig_heterogeneity_waterfall(df, m, out_dir))
    add("quality_gates_board",  fig_quality_gates_board(gates or {}, out_dir))
    add("cas_radar",            fig_cas_radar(cas_scores or {}, out_dir))
    return out

