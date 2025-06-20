#!/usr/bin/env python3
"""Debug the filter configuration to see what's happening."""

import json
import requests
from pprint import pprint

# Test with a simple element
test_doc = {
    "pages": [{
        "pageNumber": 1,
        "paragraphs": [{
            "content": "Test content",
            "role": "paragraph",
            "elementType": "paragraph",
            "boundingBox": {"x": 0, "y": 0},
            "confidence": 0.99,
            "spans": [{"offset": 0, "length": 12}],
            "words": ["Test", "content"],
            "styles": {"font": "Arial"}
        }]
    }]
}

print("🔍 Testing citation_optimized preset specifically")
print("=" * 60)

# According to the preset definition, citation_optimized should:
# - essential_fields: ["content", "pageNumber"]
# - contextual_fields: ["pageHeader", "pageFooter", "elementIndex"]
# - excluded_patterns: ["boundingBox", "boundingPolygon", "spans", "confidence", "words", "styles", "polygon", "selectionMarks", "role", "elementType"]

payload = {
    "source_file": "test.pdf",
    "analysis_result": test_doc,
    "filter_config": {
        "filter_preset": "citation_optimized",
        "include_element_ids": True
    }
}

response = requests.post("http://localhost:8000/segment-filtered", json=payload)

if response.status_code == 200:
    data = response.json()
    metrics = data.get("metrics", {})
    segments = data.get("segments", [])
    
    print("📊 Metrics:")
    print(f"  Excluded fields: {metrics.get('excluded_fields', [])}")
    
    if segments and segments[0].get("elements"):
        elem = segments[0]["elements"][0]
        print(f"\n🔍 Element received:")
        pprint(elem)
        
        # Check what should and shouldn't be there
        print(f"\n✅ Should have:")
        should_have = ["_id", "content", "pageNumber"]
        for field in should_have:
            status = "✓" if field in elem else "✗"
            print(f"  {status} {field}")
        
        print(f"\n❌ Should NOT have:")
        should_not_have = ["role", "elementType", "boundingBox", "confidence", "spans", "words", "styles"]
        for field in should_not_have:
            status = "✗" if field in elem else "✓"
            value = f" (value: {elem.get(field)})" if field in elem else ""
            print(f"  {status} {field}{value}")

# Let's also test sending the config explicitly
print("\n\n🔧 Testing with explicit config (no preset)")
print("=" * 60)

payload = {
    "source_file": "test.pdf", 
    "analysis_result": test_doc,
    "filter_config": {
        "filter_preset": "custom",
        "essential_fields": ["content", "pageNumber"],
        "contextual_fields": [],
        "excluded_patterns": ["role", "elementType", "boundingBox", "confidence", "spans", "words", "styles"],
        "include_element_ids": True
    }
}

response = requests.post("http://localhost:8000/segment-filtered", json=payload)

if response.status_code == 200:
    data = response.json()
    segments = data.get("segments", [])
    
    if segments and segments[0].get("elements"):
        elem = segments[0]["elements"][0]
        print("🔍 Element with explicit config:")
        pprint(elem)
        print(f"\nFields present: {list(elem.keys())}")