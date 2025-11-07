import pandas as pd
from backend.engine.quality import run_all

def test_quality_fail_closed():
    df = pd.DataFrame({"y":[1]*30+[0]*30, "treatment":[1]*30+[0]*30})
    m = {"y":"y","treatment":"treatment","unit_id":"u"}
    q = run_all(df, m, tau=0.1, se=1.0)
    assert q["policy"] in ("degraded","blocked")  # ESS fail

