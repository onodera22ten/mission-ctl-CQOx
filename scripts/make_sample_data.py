# scripts/make_sample_data.py
"""
PDF準拠の列で10k行サンプルを作る:
 - user_id,date,treatment(0/1),y,cost,log_propensity,z,segment,x1..x5
 - 追加: transport_weight (ダミー), network_edges（別CSV）
"""
from __future__ import annotations
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "examples" / "data"
np.random.seed(7)

def gen_retail(n=10_000):
    OUT.mkdir(parents=True, exist_ok=True)
    user_id = np.arange(1, n+1)
    date = pd.date_range("2025-01-01", periods=n, freq="H")[:n]
    x = {f"x{i}": np.random.normal(0,1,n) for i in range(1,6)}
    score = 0.8*x["x1"] -0.6*x["x2"] + 0.4*np.random.normal(0,1,n)
    p = 1/(1+np.exp(-score))
    treatment = (np.random.rand(n) < p).astype(int)
    log_propensity = np.log(p/(1-p+1e-12))
    z = (np.random.rand(n) < (0.5+0.2*(x["x1"]>0))).astype(int)  # instrument
    base = 10 + 0.5*x["x1"] -0.2*x["x3"]
    tau = 1.0 + 0.5*(x["x2"]>0)  # heterogeneous effect
    y = base + tau*treatment + np.random.normal(0,1,n)
    cost = (2.0 + 0.3*treatment + 0.1*np.abs(x["x1"])) * np.random.uniform(0.8,1.2,n)
    segment = np.random.choice(list("ABCDEFGHIJ"), size=n, p=[0.1]*10)
    transport_weight = np.random.beta(2,5,size=n)

    df = pd.DataFrame({
        "user_id":user_id, "date":date, "treatment":treatment, "y":y, "cost":cost,
        "log_propensity":log_propensity, "z":z, "segment":segment, "transport_weight":transport_weight,
        **x
    })
    df.to_csv(OUT/"retail_large.csv", index=False)
    # 小さなネットワーク（100ノードのみ）: edges
    m=100
    src=np.random.randint(1,m+1,size=500); dst=np.random.randint(1,m+1,size=500)
    pd.DataFrame({"src":src,"dst":dst,"weight":np.random.rand(500)}).to_csv(OUT/"network_edges.csv", index=False)
    print("saved:", OUT/"retail_large.csv", OUT/"network_edges.csv")

if __name__ == "__main__":
    gen_retail()

