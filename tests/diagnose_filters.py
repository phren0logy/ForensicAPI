#!/usr/bin/env python3
"""Diagnose why all filter presets are giving the same reduction."""

import json
import requests
from pathlib import Path

# Load test file
test_file = Path(__file__).parent / "test-data" / "synthetic" / "legal_case_file.json"
with open(test_file, 'r') as f:
    azure_di_json = json.load(f)

print(f"📄 Test file loaded: {test_file.name}")
print(f"   Original size: {len(json.dumps(azure_di_json)):,} bytes")

# Test each preset and examine the output
presets = ["no_filter", "llm_ready", "forensic_extraction", "citation_optimized"]

for preset in presets:
    print(f"\n🔧 Testing preset: {preset}")
    print("-" * 40)
    
    payload = {
        "source_file": "test.pdf",
        "analysis_result": azure_di_json,
        "filter_config": {
            "filter_preset": preset,
            "include_element_ids": True
        },
        "min_segment_tokens": 2000,
        "max_segment_tokens": 6000
    }
    
    response = requests.post("http://localhost:8000/segment-filtered", json=payload)
    
    if response.status_code == 200:
        data = response.json()
        metrics = data.get("metrics", {})
        segments = data.get("segments", [])
        mappings = data.get("element_mappings", [])
        
        print(f"✅ Status: Success")
        print(f"📊 Metrics:")
        print(f"   - Total elements: {metrics.get('total_elements', 0)}")
        print(f"   - Filtered elements: {metrics.get('filtered_elements', 0)}")
        print(f"   - Original size: {metrics.get('original_size_bytes', 0):,} bytes")
        print(f"   - Filtered size: {metrics.get('filtered_size_bytes', 0):,} bytes")
        print(f"   - Reduction: {metrics.get('reduction_percentage', 0):.1f}%")
        print(f"   - Excluded fields: {metrics.get('excluded_fields', [])}")
        
        # Check first element to see what fields are included
        if segments and segments[0].get("elements"):
            first_elem = segments[0]["elements"][0]
            print(f"\n🔍 First element fields: {list(first_elem.keys())}")
            
            # Check if elements actually differ between presets
            elem_str = json.dumps(first_elem, sort_keys=True)
            print(f"   Element size: {len(elem_str)} bytes")
        
        # Save the output for manual inspection
        output_file = Path(f"test_results/filter_debug/{preset}_output.json")
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"\n💾 Saved to: {output_file}")
        
    else:
        print(f"❌ Error: {response.status_code}")

# Also test the filter config endpoint directly
print("\n\n🔍 Checking filter presets configuration...")
print("-" * 40)

# Try to get the filter presets from the API
try:
    # Check if there's an endpoint to get filter presets
    response = requests.get("http://localhost:8000/anonymization/health")
    print(f"Anonymization health: {response.status_code}")
except:
    pass

# Let's also check what happens with a minimal document
print("\n\n🧪 Testing with minimal document...")
print("-" * 40)

minimal_doc = {
    "pages": [
        {
            "pageNumber": 1,
            "paragraphs": [
                {
                    "content": "This is a test paragraph with some content.",
                    "role": "paragraph",
                    "boundingBox": {"x": 0, "y": 0, "width": 100, "height": 20},
                    "confidence": 0.99,
                    "spans": [{"offset": 0, "length": 42}]
                }
            ]
        }
    ]
}

for preset in ["minimal", "llm_ready"]:
    payload = {
        "source_file": "minimal.pdf",
        "analysis_result": minimal_doc,
        "filter_config": {"filter_preset": preset}
    }
    
    response = requests.post("http://localhost:8000/segment-filtered", json=payload)
    if response.status_code == 200:
        data = response.json()
        metrics = data.get("metrics", {})
        print(f"\n{preset}: {metrics.get('reduction_percentage', 0):.1f}% reduction")
        
        # Check actual element
        segments = data.get("segments", [])
        if segments and segments[0].get("elements"):
            elem = segments[0]["elements"][0]
            print(f"  Fields: {list(elem.keys())}")