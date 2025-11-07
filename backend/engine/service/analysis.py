import uuid, numpy as np, pandas as pd, os
from .gates import gates_summary, cas_from
from .estimators import tvce, ope_ipw, iv_2sls, transport, proximal, network, hidden
from .policy import greedy_topk
def analyze_comprehensive(df: pd.DataFrame, roles: dict, cfg: dict, lam=1.65, broker=None):
    # Full dataset analysis (preview mode removed)
    r=roles; y=df[r['y']] if 'y' in r and r['y'] in df else pd.Series([],dtype=float); w=df[r['w']] if 'w' in r and r['w'] in df else pd.Series([],dtype=float)
    ests=[]
    def wrap(kind,res):
        if res is None: return {"kind":kind,"status":"EST_SKIP","tau":0,"se":0,"ci":[0,0],"message":"missing roles"}
        tau,se,ci,msg=res; status="EST_SUCCESS" if (ci[0]*ci[1]>0) else "EST_FAIL"
        return {"kind":kind,"status":status,"tau":float(tau),"se":float(se),"ci":[float(ci[0]),float(ci[1])],"message":msg}
    ests.append(wrap("KIND_TVCE", tvce(df,r)))
    ests.append(wrap("KIND_OPE", ope_ipw(df,r)))
    ests.append(wrap("KIND_IV", iv_2sls(df,r)))
    ests.append(wrap("KIND_TRANSPORT", transport(df,r)))
    ests.append(wrap("KIND_PROXIMAL", proximal(df,r)))
    ests.append(wrap("KIND_NETWORK", network(df,r)))
    ests.append(wrap("KIND_HIDDEN", hidden(df,r)))
    ok=[e for e in ests if e["status"]=="EST_SUCCESS"]
    thr = (cfg.get("gate_thresholds",{}) if cfg else {})
    g=gates_summary(ok, df, y, w, thresholds=thr); cas=cas_from(g, len(ok), len(ests), df)
    suggest = (cfg.get("visualizations",[]) if cfg else [])
    # policy
    budget_ratio = (cfg.get("policy_defaults",{}).get("budget_ratio",0.10) if cfg else 0.10)
    budget=float(df[r['cost']].sum()*budget_ratio) if 'cost' in r and r['cost'] in df else 0.0
    user_ids=df[r['unit_id']].values if 'unit_id' in r and r['unit_id'] in df else np.arange(len(df))
    cate=np.full(len(df), np.mean([e['tau'] for e in ok]) if ok else 0.0)
    cost=df[r['cost']].values if 'cost' in r and r['cost'] in df else np.zeros(len(df))
    out_dir=os.environ.get("CQO_DATA","./data")
    policy=greedy_topk(user_ids, cate, cost, budget, out_dir)
    return {"run_id": str(uuid.uuid4()), "estimators": ests, "gate": g, "cas": cas, "suggest": suggest, "policy": policy}
