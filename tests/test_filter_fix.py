#!/usr/bin/env python3
"""Test that filter presets now work correctly after the fix."""

import json
import requests
from pathlib import Path

print("🧪 Testing Filter Presets After Fix")
print("=" * 60)

# Create a test document with various fields
test_doc = {
    "pages": [{
        "pageNumber": 1,
        "paragraphs": [{
            "content": "Test paragraph content",
            "role": "paragraph",
            "elementType": "paragraph",
            "boundingBox": {"x": 0, "y": 0, "width": 100, "height": 20},
            "confidence": 0.99,
            "spans": [{"offset": 0, "length": 22}],
            "words": ["Test", "paragraph", "content"],
            "styles": {"font": "Arial", "size": 12}
        }]
    }]
}

# Test each preset
presets = ["no_filter", "llm_ready", "forensic_extraction", "citation_optimized"]
results = {}

for preset in presets:
    print(f"\n🔧 Testing preset: {preset}")
    
    payload = {
        "source_file": "test.pdf",
        "analysis_result": test_doc,
        "filter_config": {
            "filter_preset": preset,
            "include_element_ids": True
        }
    }
    
    response = requests.post("http://localhost:8000/segment-filtered", json=payload)
    
    if response.status_code == 200:
        data = response.json()
        metrics = data.get("metrics", {})
        segments = data.get("segments", [])
        
        if segments and segments[0].get("elements"):
            elem = segments[0]["elements"][0]
            fields = list(elem.keys())
            
            results[preset] = {
                "fields": fields,
                "excluded": metrics.get("excluded_fields", []),
                "reduction": metrics.get("reduction_percentage", 0)
            }
            
            print(f"  ✅ Fields included: {fields}")
            print(f"  ❌ Fields excluded: {metrics.get('excluded_fields', [])}")
            print(f"  📊 Reduction: {metrics.get('reduction_percentage', 0):.1f}%")

# Verify differences
print("\n\n📊 Verification")
print("=" * 60)

# Check that each preset has different fields
all_fields_same = all(
    set(results[p]["fields"]) == set(results["no_filter"]["fields"]) 
    for p in presets if p in results
)

if all_fields_same:
    print("❌ FAIL: All presets still have the same fields!")
else:
    print("✅ PASS: Presets have different fields as expected!")

# Check specific expectations
print("\n🔍 Specific Checks:")

# no_filter should have most fields
if "no_filter" in results:
    no_filter_fields = set(results["no_filter"]["fields"])
    print(f"\n1. no_filter has {len(no_filter_fields)} fields")
    expected_in_no_filter = ["boundingBox", "confidence", "spans", "words", "styles"]
    missing = [f for f in expected_in_no_filter if f not in no_filter_fields]
    if not missing:
        print("   ✅ Includes all fields (boundingBox, confidence, spans, etc.)")
    else:
        print(f"   ❌ Missing fields: {missing}")

# citation_optimized should have fewest fields
if "citation_optimized" in results:
    citation_fields = set(results["citation_optimized"]["fields"])
    print(f"\n2. citation_optimized has {len(citation_fields)} fields")
    should_not_have = ["role", "elementType", "boundingBox", "spans", "confidence"]
    unwanted = [f for f in should_not_have if f in citation_fields]
    if not unwanted:
        print("   ✅ Excludes role, elementType, boundingBox, etc.")
    else:
        print(f"   ❌ Has unwanted fields: {unwanted}")

# llm_ready should be balanced
if "llm_ready" in results:
    llm_fields = set(results["llm_ready"]["fields"])
    print(f"\n3. llm_ready has {len(llm_fields)} fields")
    should_have = ["content", "pageNumber", "role", "elementType"]
    should_not_have = ["boundingBox", "spans", "confidence"]
    
    missing = [f for f in should_have if f not in llm_fields]
    unwanted = [f for f in should_not_have if f in llm_fields]
    
    if not missing and not unwanted:
        print("   ✅ Has expected fields, excludes visual metadata")
    else:
        if missing:
            print(f"   ❌ Missing: {missing}")
        if unwanted:
            print(f"   ❌ Has unwanted: {unwanted}")

# Compare reduction percentages
print("\n4. Reduction Percentages:")
for preset, data in sorted(results.items(), key=lambda x: x[1]["reduction"]):
    print(f"   {preset:20} {data['reduction']:6.1f}%")