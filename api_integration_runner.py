#!/usr/bin/env python3
"""
Test script for new /api/analyze/objective endpoint
Tests all 9 tasks with full role dataset
"""

import requests
import json
from pathlib import Path

GATEWAY_URL = "http://localhost:8081"

def test_upload():
    """Upload sample dataset with all roles"""
    sample_file = Path("data/sample_full_roles.csv")

    with open(sample_file, 'rb') as f:
        files = {'file': ('sample_full_roles.csv', f, 'text/csv')}
        response = requests.post(f"{GATEWAY_URL}/api/upload", files=files)

    response.raise_for_status()
    data = response.json()
    print(f"✓ Upload successful: dataset_id={data['dataset_id']}")
    return data['dataset_id']

def test_panels_available():
    """Test /api/panels/available endpoint"""
    params = {
        'treatment': '1',
        'y': '1',
        'unit_id': '1',
        'time': '1',
        'cost': '1',
        'log_propensity': '1',
        'cluster_id': '1',
        'instrument': '1',
        'objective': '1',
        'features': '1',
    }

    response = requests.get(f"{GATEWAY_URL}/api/panels/available", params=params)
    response.raise_for_status()
    data = response.json()

    print(f"\n✓ Available panels: {len(data['available_panels'])}/37")
    print(f"  Recommended: {len(data['recommended_panels'])}")

    print("\n  Task availability:")
    for task_key, task_info in data['tasks'].items():
        status = "✓" if task_info['can_run'] else "✗"
        print(f"    {status} {task_info['name']}: {task_info['available_panels']}/{task_info['total_panels']} panels")

    return data

def print_analysis_summary(data):
    """Prints a summary of the analysis results."""
    print(f"✓ Analysis complete: job_id={data['job_id']}")
    print(f"\n  Summary:")
    print(f"    Total tasks: {data['summary']['total_tasks']}")
    print(f"    Successful: {data['summary']['successful']}")
    print(f"    Skipped: {data['summary']['skipped']}")
    print(f"    Failed: {data['summary']['failed']}")
    print(f"    Total figures: {data['summary']['total_figures']}")

    print(f"\n  Execution log:")
    for log in data['execution_log']:
        status_icon = {"success": "✓", "skipped": "⊘", "error": "✗"}[log['status']]
        task_name = log['task']
        if log['status'] == 'success':
            print(f"    {status_icon} {task_name}: {log['n_figures']} figures")
        elif log['status'] == 'skipped':
            print(f"    {status_icon} {task_name}: {log['reason']}")
        else:
            print(f"    {status_icon} {task_name}: ERROR - {log.get('error', 'unknown')}")

    print(f"\n  Generated figures ({len(data['figures'])}):")
    for panel_key, url in sorted(data['figures'].items())[:10]:  # Show first 10
        print(f"    - {panel_key}: {url}")
    if len(data['figures']) > 10:
        print(f"    ... and {len(data['figures']) - 10} more")

def test_objective_analysis(dataset_id):
    """Test /api/analyze/objective endpoint"""
    payload = {
        "dataset_id": dataset_id,
        "mapping": {
            "treatment": "treatment",
            "y": "y",
            "unit_id": "unit_id",
            "time": "time",
            "cost": "cost",
            "log_propensity": "log_propensity",
            "cluster_id": "cluster_id",
            "instrument": "instrument",
            "objective": "retail",
            "strata": "strata",
            "dose": "dose",
            "features": "x_age,x_income,x_education"
        },
        "objectives": None  # Run all tasks
    }

    print(f"\n→ Calling /api/analyze/objective...")
    response = requests.post(
        f"{GATEWAY_URL}/api/analyze/objective",
        json=payload,
        timeout=180
    )

    response.raise_for_status()
    data = response.json()

    print_analysis_summary(data)

    return data

def main():
    print("=" * 60)
    print("Testing Plan3 Objective-Lens API")
    print("=" * 60)

    try:
        # Test 1: Upload
        print("\n[1/3] Testing /api/upload...")
        dataset_id = test_upload()

        # Test 2: Panels available
        print("\n[2/3] Testing /api/panels/available...")
        panels_data = test_panels_available()

        # Test 3: Objective analysis
        print("\n[3/3] Testing /api/analyze/objective...")
        result = test_objective_analysis(dataset_id)

        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)

        # Save result for inspection
        output_file = Path("test_objective_result.json")
        output_file.write_text(json.dumps(result, indent=2, ensure_ascii=False))
        print(f"\nFull result saved to: {output_file}")

    except requests.exceptions.HTTPError as e:
        print(f"\n✗ HTTP Error: {e}")
        print(f"  Response: {e.response.text}")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
