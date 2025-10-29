from backend.engine.cas import compute_cas
def test_cas_shape():
    gates = {k: {"passed": True, "value": 1.0, "threshold": 1.0} for k in
             ["ess","overlap","weak_iv","sensitivity","balance","mono","placebo"]}
    c = compute_cas(gates)
    assert 0 <= c["score"] <= 1 and set(c["axes"].keys())=={"internal","external","transport","robustness","stability"}

