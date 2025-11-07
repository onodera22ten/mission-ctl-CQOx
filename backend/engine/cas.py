# backend/engine/cas.py
from __future__ import annotations
from typing import Dict, Any

def _nz(v, default=0.0):
    try:
        return float(v) if v is not None else default
    except Exception:
        return default

def compute_cas(gates: Dict[str, dict], weights: Dict[str, float] | None = None) -> Dict[str, Any]:
    """
    5 axes in [0,1]:
      internal: data size & balance (ess, balance)
      external: domain coverage proxy (use overlap)
      transport: overlap + mono
      robustness: sensitivity + weak_iv + placebo
      stability: monotonic time effect proxy (reuse placebo pass + balance)
    """
    w = weights or {k:1.0 for k in ["internal","external","transport","robustness","stability"]}
    # map gate metrics -> [0,1]
    ess = 1.0 if gates["ess"]["passed"] else 0.0
    balance = max(0.0, 1.0 - _nz(gates["balance"]["value"], 0.3)/max(_nz(gates["balance"]["threshold"], 0.1),1e-6))
    overlap = min(1.0, _nz(gates["overlap"]["value"], 0.0)/max(_nz(gates["overlap"]["threshold"], 0.2),1e-6))
    weak_iv = min(1.0, _nz(gates["weak_iv"]["value"], 0.0)/max(_nz(gates["weak_iv"]["threshold"], 10.0),1e-6))
    sens = min(1.0, _nz(gates["sensitivity"]["value"], 0.0)/max(_nz(gates["sensitivity"]["threshold"], 1.5),1e-6))
    mono = 1.0 if gates["mono"]["passed"] else 0.4
    placebo = 1.0 if gates["placebo"]["passed"] else 0.2

    axes = {
        "internal": 0.6*ess + 0.4*balance,
        "external": overlap,
        "transport": 0.7*overlap + 0.3*mono,
        "robustness": 0.5*sens + 0.3*weak_iv + 0.2*placebo,
        "stability": 0.6*placebo + 0.4*balance,
    }
    tot_w = sum(w.values()) or 1.0
    score = sum(axes[k]*w[k] for k in axes)/tot_w
    grade = "green" if score >= 0.7 else ("yellow" if score >= 0.6 else "red")
    return {"score": float(score), "grade": grade, "axes": axes}

