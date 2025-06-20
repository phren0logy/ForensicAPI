#!/usr/bin/env python3
"""Quick test to verify segmentation is working."""

import requests
import json
from pathlib import Path

# Check health
print("Checking backend health...")
try:
    r = requests.get("http://localhost:8000/health")
    print(f"Health check: {r.status_code}")
except Exception as e:
    print(f"Backend not running: {e}")
    exit(1)

# Load a synthetic file
test_file = Path(__file__).parent / "test-data" / "synthetic" / "medical_chart_multi_visit.json"
if not test_file.exists():
    print(f"Test file not found: {test_file}")
    exit(1)

with open(test_file, 'r') as f:
    data = json.load(f)

# Test basic segmentation
print("\nTesting /segment endpoint...")
payload = {
    "source_file": "test.pdf",
    "analysis_result": data,
    "min_segment_tokens": 2000,
    "max_segment_tokens": 6000
}

try:
    r = requests.post("http://localhost:8000/segment", json=payload, timeout=30)
    if r.status_code == 200:
        result = r.json()
        # Handle both dict with 'segments' key and direct list response
        if isinstance(result, list):
            segments = result
        else:
            segments = result.get('segments', [])
        print(f"✅ Success! Got {len(segments)} segments")
    else:
        print(f"❌ Error {r.status_code}: {r.text[:200]}")
except Exception as e:
    print(f"❌ Request failed: {e}")

# Test filtered segmentation
print("\nTesting /segment-filtered endpoint...")
payload["filter_config"] = {
    "filter_preset": "llm_ready",
    "include_element_ids": True
}

try:
    r = requests.post("http://localhost:8000/segment-filtered", json=payload, timeout=30)
    if r.status_code == 200:
        result = r.json()
        metrics = result.get("metrics", {})
        print(f"✅ Success! Reduction: {metrics.get('reduction_percentage', 0):.1f}%")
    else:
        print(f"❌ Error {r.status_code}: {r.text[:200]}")
except Exception as e:
    print(f"❌ Request failed: {e}")

print("\nDone!")