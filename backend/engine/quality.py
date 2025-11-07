# backend/engine/quality.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Tuple, List
import numpy as np
import pandas as pd

@dataclass
class GateResult:
    passed: bool
    value: float | None
    threshold: float | None
    reason: str = ""

def _smd(a: pd.Series, b: pd.Series) -> float:
    a = a.astype(float).dropna(); b = b.astype(float).dropna()
    if len(a) < 2 or len(b) < 2: return float("nan")
    v = np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2.0) or 1e-12
    return float(abs(a.mean() - b.mean()) / v)

def ess(df: pd.DataFrame, t: str) -> GateResult:
    n1 = int((df[t] == 1).sum()); n0 = int((df[t] == 0).sum())
    val = min(n1, n0)
    thr = 1000  # default threshold; tune per domain
    return GateResult(passed=val >= thr, value=val, threshold=thr,
                      reason=f"min(n_treat={n1}, n_ctrl={n0}) >= {thr}?")

def overlap_logit(df: pd.DataFrame, t: str, lp: str | None) -> GateResult:
    if not lp or lp not in df: 
        return GateResult(passed=False, value=None, threshold=None, reason="log_propensity missing")
    c = df[df[t]==0][lp].astype(float).dropna()
    tr = df[df[t]==1][lp].astype(float).dropna()
    # histogram intersection as overlap proxy (larger is better)
    hist_range = (np.nanmin(df[lp]), np.nanmax(df[lp]))
    hc,_ = np.histogram(c, bins=40, range=hist_range, density=True)
    ht,_ = np.histogram(tr, bins=40, range=hist_range, density=True)
    inter = float(np.sum(np.minimum(hc, ht)) * (hist_range[1]-hist_range[0])/40.0)
    thr = 0.15  # require some overlap mass
    return GateResult(passed=inter >= thr, value=inter, threshold=thr, reason="histogram intersection")

def weak_iv(df: pd.DataFrame, t: str, z: str | None) -> GateResult:
    if not z or z not in df or t not in df:
        return GateResult(passed=True, value=None, threshold=10.0, reason="no IV -> skip")
    a = df[z].astype(float).values; b = df[t].astype(float).values
    if len(a) < 3: return GateResult(passed=False, value=0.0, threshold=10.0, reason="too small")
    r = np.corrcoef(a, b)[0,1]
    F = (len(a)-2) * (r*r) / max(1e-9, 1 - r*r)
    thr = 10.0
    return GateResult(passed=F >= thr, value=float(F), threshold=thr, reason="first-stage F >= 10")

def sensitivity_gamma(tau: float, se: float) -> GateResult:
    # very coarse: bound ~ |tau|/se ; require >1.5 as robustness proxy
    if not np.isfinite(tau) or not np.isfinite(se) or se <= 0:
        return GateResult(passed=False, value=None, threshold=1.5, reason="tau/se invalid")
    eff = abs(tau) / se
    thr = 1.5
    return GateResult(passed=eff >= thr, value=float(eff), threshold=thr, reason="|tau|/se >= 1.5")

def balance_smd(df: pd.DataFrame, t: str, exclude: List[str]) -> GateResult:
    nums = [c for c in df.columns if c not in exclude and pd.api.types.is_numeric_dtype(df[c])]
    if not nums: 
        return GateResult(passed=False, value=None, threshold=0.1, reason="no numeric covariates")
    vals = []
    for c in nums:
        try: vals.append(_smd(df[df[t]==1][c], df[df[t]==0][c]))
        except Exception: pass
    m = float(np.nanmean(vals)) if vals else float("nan")
    thr = 0.1
    return GateResult(passed=np.isfinite(m) and m <= thr, value=m, threshold=thr, reason="mean SMD <= 0.1")

def monotonicity(df: pd.DataFrame, t: str, z: str | None) -> GateResult:
    if not z or z not in df: 
        return GateResult(passed=True, value=None, threshold=None, reason="no IV")
    r = np.corrcoef(df[z].astype(float), df[t].astype(float))[0,1]
    return GateResult(passed=r >= -0.05, value=float(r), threshold=-0.05, reason="no strong negative")

def placebo(df: pd.DataFrame, t: str, y: str, time: str | None) -> GateResult:
    if not time or time not in df: 
        return GateResult(passed=True, value=None, threshold=None, reason="no time col")
    s = pd.to_datetime(df[time], errors="coerce")
    mid = s.min() + (s.max()-s.min())/3
    pre = df[s < mid]; post = df[s >= mid]
    if len(pre) < 50 or len(post) < 50: 
        return GateResult(passed=True, value=None, threshold=None, reason="small pre segment")
    d = pre.groupby(t)[y].mean()
    diff = float(abs(d.get(1, np.nan) - d.get(0, np.nan)))
    thr = 0.25 * float(post[y].std())  # pre-effect should be small
    return GateResult(passed=(np.isfinite(diff) and diff <= thr), value=diff, threshold=thr, reason="pre-period effect small")

def run_all(df: pd.DataFrame, mapping: Dict[str,str], tau: float, se: float) -> Dict[str, Any]:
    y = mapping["y"]; t = mapping["treatment"]
    time = mapping.get("time"); lp = mapping.get("log_propensity"); z = mapping.get("z")
    excl = [y, t, time, lp, z, mapping.get("unit_id"), mapping.get("cost"), mapping.get("segment")]
    excl = [c for c in excl if c]
    gates = {
        "ess": ess(df, t).__dict__,
        "overlap": overlap_logit(df, t, lp).__dict__,
        "weak_iv": weak_iv(df, t, z).__dict__,
        "sensitivity": sensitivity_gamma(tau, se).__dict__,
        "balance": balance_smd(df, t, excl).__dict__,
        "mono": monotonicity(df, t, z).__dict__,
        "placebo": placebo(df, t, y, time).__dict__,
    }
    # policy
    hard_fails = [g for k,g in gates.items() if k in ("ess","overlap","balance") and not g["passed"]]
    any_fail   = [g for g in gates.values() if g and not g["passed"]]
    if hard_fails:
        policy = "blocked"
    elif any_fail:
        policy = "degraded"
    else:
        policy = "allowed"
    return {"gates": gates, "policy": policy}

