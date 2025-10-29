import numpy as np, pandas as pd
def gates_summary(ok, df, y, w, thresholds: dict):
    ess = _ess(w) if len(w)>0 else 0.0
    tail_ratio = _tail(y) if len(y)>0 else 0.0
    ciw = float(np.nanmean([(e["ci"][1]-e["ci"][0]) for e in ok])) if ok else 1.0
    sign = float(np.mean([1.0 if e["tau"]>0 else 0.0 for e in ok])) if ok else 0.0
    ess_min = thresholds.get("ess_min", 100.0)
    ciw_max = thresholds.get("ci_width_max", 0.30)
    gate_pass = bool(ess>=ess_min and ciw<=ciw_max)
    return {"pass": gate_pass, "ess":ess, "tail_ratio":tail_ratio, "ci_width":ciw, "sign_consistency":sign}
def _ess(w): n1=(w==w.max()).sum(); n0=(w==w.min()).sum(); return (n1*n0)/(n1+n0+1e-9)*4
def _tail(y): return float(y.quantile(0.99)-y.quantile(0.95))
def cas_from(g, ok_count, total_count, df):
    gate = 100.0 if g["pass"] else 40.0
    sign= g["sign_consistency"]*100
    overlap = 60.0 if ok_count>=2 else 0.0
    data_health = 100.0*(1.0 - float(df.isna().mean().mean()))
    sens = 70.0
    total = 0.35*gate + 0.25*sign + 0.15*overlap + 0.15*data_health + 0.10*sens
    return {"gate_pass":gate,"sign_consistency":sign,"ci_overlap":overlap,"data_health":data_health,"sensitivity":sens,"total":total}
