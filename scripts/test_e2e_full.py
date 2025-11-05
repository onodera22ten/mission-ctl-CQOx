#!/usr/bin/env python3.11
"""
E2E Test: Realistic Data + ObjectiveSpec + CF + WolframONE + Decision Card
Tests the complete Plan1.pdf implementation
"""
import requests
import json
import time
from pathlib import Path

BASE_URL = "http://localhost:8080"

def test_e2e():
    """Run complete E2E test"""

    print("=" * 80)
    print("E2E TEST: CQOx Complete System (Plan1.pdf準拠)")
    print("=" * 80)

    # Step 1: Check dataset exists
    print("\n[1/5] Checking realistic retail dataset (5000 rows)...")
    dataset_path = Path("data/realistic_retail_5k.csv").absolute()

    if not dataset_path.exists():
        print(f"❌ Dataset not found: {dataset_path}")
        return False

    print(f"✓ Dataset exists: {dataset_path}")
    print(f"  Size: {dataset_path.stat().st_size / 1024:.1f} KB")

    # Step 2: Load ObjectiveSpec
    print("\n[2/5] Loading ObjectiveSpec: profit_max.json...")
    objective_path = Path("objective_specs/profit_max.json")

    with open(objective_path) as f:
        objective_spec = json.load(f)

    print(f"✓ ObjectiveSpec loaded: {objective_spec['objective_id']}")
    print(f"  Description: {objective_spec['description']}")

    # Step 3: Run causal analysis (baseline - no CF)
    print("\n[3/5] Running baseline causal analysis...")

    payload = {
        "df_path": str(dataset_path),
        "mapping": {
            "unit_id": "user_id",
            "time": "date",
            "treatment": "treatment",
            "y": "y",
            "cost": "cost"
        },
        "estimator": "IPW",
        "objective_spec": objective_spec
    }

    resp = requests.post(f"{BASE_URL}/api/analyze/comprehensive", json=payload, timeout=120)

    if resp.status_code != 200:
        print(f"❌ Analysis failed: {resp.status_code} {resp.text[:500]}")
        return False

    result = resp.json()
    job_id = result.get("job_id")
    print(f"✓ Analysis complete: {job_id}")
    print(f"  ATE: {result.get('ate', 'N/A'):.2f}")
    print(f"  CAS Overall: {result.get('cas_overall', 'N/A'):.1f}/100")
    print(f"  Figures generated: {len(result.get('figures', []))}")

    # Step 4: Run CF scenario analysis
    print("\n[4/5] Running counterfactual scenario analysis...")

    cf_payload = payload.copy()
    cf_payload["scenario_id"] = "cf_do_all_treatment"

    resp_cf = requests.post(f"{BASE_URL}/api/analyze/comprehensive", json=cf_payload, timeout=120)

    if resp_cf.status_code != 200:
        print(f"⚠ CF analysis failed: {resp_cf.status_code} {resp_cf.text[:500]}")
        print("  (Continuing with baseline results)")
    else:
        result_cf = resp_cf.json()
        job_id_cf = result_cf.get("job_id")
        print(f"✓ CF Analysis complete: {job_id_cf}")
        print(f"  CF ATE: {result_cf.get('ate', 'N/A'):.2f}")
        print(f"  CF CAS: {result_cf.get('cas_overall', 'N/A'):.1f}/100")

    # Step 5: Verify outputs
    print("\n[5/5] Verifying outputs...")

    output_dir = Path(f"jobs/{job_id}")

    checks = {
        "Report HTML": output_dir / "report.html",
        "Report JSON": output_dir / "report.json",
        "Decision Card": output_dir / "decision_card.pdf",
        "WolframONE CAS Radar": output_dir / "cas_radar.png"
    }

    all_pass = True
    for name, path in checks.items():
        if path.exists():
            size_kb = path.stat().st_size / 1024
            print(f"  ✓ {name}: {size_kb:.1f} KB")
        else:
            print(f"  ✗ {name}: NOT FOUND")
            all_pass = False

    # Check for WolframONE CF figures (if CF scenario ran)
    wolfram_cf_dir = output_dir / "wolfram_cf"
    if wolfram_cf_dir.exists():
        cf_figures = list(wolfram_cf_dir.glob("*.png"))
        print(f"  ✓ WolframONE CF figures: {len(cf_figures)} files")

    print("\n" + "=" * 80)
    if all_pass:
        print("✓ E2E TEST PASSED")
        print(f"  Job directory: {output_dir}")
    else:
        print("⚠ E2E TEST COMPLETED WITH WARNINGS")

    print("=" * 80)

    return all_pass

if __name__ == "__main__":
    import sys
    success = test_e2e()
    sys.exit(0 if success else 1)
