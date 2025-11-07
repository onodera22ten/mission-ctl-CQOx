import pandas as pd
from backend.engine.server import analyze
import asyncio

def test_analyze_smoke(tmp_path, monkeypatch):
    p = tmp_path/"d.csv"
    df = pd.DataFrame({"user_id":range(1200),"treatment":[0,1]*600,"y":1.0})
    df.to_csv(p, index=False)
    payload={"dataset_id":"x","df_path":str(p),"mapping":{"y":"y","treatment":"treatment","unit_id":"user_id"}}
    loop=asyncio.get_event_loop()
    resp = loop.run_until_complete(analyze(payload))
    assert resp.status_code==200

