import numpy as np, pandas as pd
def _ci(tau, se): hw=1.96*se; return (float(tau-hw), float(tau+hw))
def tvce(df, r):
    if all(k in r for k in ["period","w","y"]):
        d=df[[r["period"],r["w"],r["y"]]].dropna()
        if d[r["period"]].nunique()>=2:
            ts=sorted(d[r["period"]].unique())
            pre=d[d[r["period"]]==ts[0]]; post=d[d[r["period"]]==ts[-1]]
            def m(g): return g[g[r["w"]]==1][r["y"]].mean() - g[g[r["w"]]==0][r["y"]].mean()
            tau=(m(post)-m(pre)); se=d[r["y"]].std()/max(1,len(d))**0.5; return tau,se,_ci(tau,se),""
    d=df[[r["w"],r["y"]]].dropna(); y1=d[d[r["w"]]==1][r["y"]]; y0=d[d[r["w"]]==0][r["y"]]
    tau=float(y1.mean()-y0.mean()); se=float(y1.std()/max(1,len(y1))**0.5 + y0.std()/max(1,len(y0))**0.5); return tau,se,_ci(tau,se),""
def ope_ipw(df, r):
    if "log_propensity" not in r or r["log_propensity"] not in df: return None
    d=df[[r["w"],r["y"],r["log_propensity"]]].dropna()
    p=1/(1+np.exp(-d[r["log_propensity"]].to_numpy())); w=d[r["w"]].to_numpy(); y=d[r["y"]].to_numpy()
    ipw=(w*y/p)-((1-w)*y/(1-p)); tau=ipw.mean(); se=ipw.std()/max(1,len(ipw))**0.5; return tau,se,_ci(tau,se),"IPW"
def iv_2sls(df, r):
    if "z" not in r or r["z"] not in df: return None
    d=df[[r["z"],r["w"],r["y"]]].dropna()
    if d[r["z"]].nunique()<2: return 0.0,1.0,_ci(0,1.0),"weak IV"
    num=d[r["y"]][d[r["z"]]==1].mean()-d[r["y"]][d[r["z"]]==0].mean()
    den=d[r["w"]][d[r["z"]]==1].mean()-d[r["w"]][d[r["z"]]==0].mean()
    tau=float(num/(den+1e-9)); se=d[r["y"]].std()/max(1,len(d))**0.5; return tau,se,_ci(tau,se),"Wald"
def transport(df, r):
    if "domain" not in r or r["domain"] not in df: return None
    d=df[[r["domain"],r["w"],r["y"]]].dropna()
    tau=float(d.groupby(r["domain"])[r["y"]].mean().mean()); se=d[r["y"]].std()/max(1,len(d))**0.5; return tau,se,_ci(tau,se),"Domain avg"
def proximal(df, r):
    if not all(k in r and r[k] in df for k in ["w_neg","z_neg"]): return None
    d=df[[r["w_neg"],r["z_neg"],r["y"]]].dropna()
    tau=0.0; se=d[r["y"]].std()/max(1,len(d))**0.5; return tau,se,_ci(tau,se),"Placebo"
def network(df, r):
    if not all(k in r and r[k] in df for k in ["cluster_id","neighbor_exposure"]): return None
    d=df[[r["y"],r["neighbor_exposure"]]].dropna()
    if len(d)<5: return None
    rho=float(d.corr().iloc[0,1]); se=(1-rho**2)/max(1,len(d))**0.5; return rho,se,_ci(rho,se),"Corr"
def hidden(df, r): tau=0.0; se=1.0; return tau,se,_ci(tau,se),"Unidentified"
