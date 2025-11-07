import numpy as np, pandas as pd, uuid, os
def greedy_topk(user_ids, cate, cost, budget: float, out_dir: str):
    idx = np.argsort(-cate); sel=[]; spend=0.0; gain=0.0
    for i in idx:
        c=float(cost[i]) if cost is not None else 0.0
        if spend+c<=budget: spend+=c; gain+=float(cate[i])-c; sel.append(int(user_ids[i]))
    fn=f"policy_{uuid.uuid4().hex[:8]}.csv"; os.makedirs(out_dir, exist_ok=True)
    pd.DataFrame({'user_id':sel}).to_csv(os.path.join(out_dir,fn), index=False)
    return {'budget':float(budget),'expected_profit':float(gain),'selected':len(sel),'csv_asset':fn}
