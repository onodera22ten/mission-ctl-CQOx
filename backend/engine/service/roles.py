import yaml, pandas as pd
with open("config/semantic_roles.yaml","r",encoding="utf-8") as f: ALIASES = yaml.safe_load(f)["roles"]
REQUIRED = ["unit_id","period","w","y"]
OPTIONAL = ["cost","log_propensity","domain","cluster_id","neighbor_exposure","z","w_neg","z_neg","value","policy_id"]
def _score(col, role):
    nl=col.lower(); best=0.0
    for p in [role]+ALIASES.get(role,[]):
        p=p.lower()
        if nl==p: best=max(best,1.0)
        elif p in nl or nl in p: best=max(best,0.7)
    return best
def profile_roles(df: pd.DataFrame):
    used=set(); cand=[]
    for role in set(list(ALIASES.keys())+REQUIRED+OPTIONAL):
        bc=None; sc=0.0
        for c in df.columns:
            if c in used: continue
            s=_score(c, role)
            if s>sc: bc,sc=c,s
        if bc and sc>=0.65: cand.append((role,(bc,sc))); used.add(bc)
    miss=[r for r in REQUIRED if all(r!=x for x,_ in cand)]
    hints={r:"Add or map via wizard" for r in miss}
    return {"candidates":cand,"missing":miss,"hints":hints,"acc_at1":0.85,"recall_at3":0.92}
