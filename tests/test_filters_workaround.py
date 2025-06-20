#!/usr/bin/env python3
"""Test filter presets with workaround for default values issue."""

import json
import requests
from pathlib import Path

# Load test file
test_file = Path(__file__).parent / "test-data" / "synthetic" / "legal_case_file.json"
with open(test_file, 'r') as f:
    azure_di_json = json.load(f)

print("📄 Testing filter presets with explicit empty fields to force preset application")
print("=" * 60)

# Test each preset with explicit empty fields
presets_config = {
    "no_filter": {
        "filter_preset": "no_filter",
        "essential_fields": [],  # Empty to force preset
        "excluded_patterns": [],  # Empty to force preset
        "include_element_ids": True
    },
    "llm_ready": {
        "filter_preset": "llm_ready",
        "essential_fields": [],  # Empty to force preset
        "excluded_patterns": [],  # Empty to force preset
        "include_element_ids": True
    },
    "forensic_extraction": {
        "filter_preset": "forensic_extraction",
        "essential_fields": [],  # Empty to force preset
        "excluded_patterns": [],  # Empty to force preset
        "include_element_ids": True
    },
    "citation_optimized": {
        "filter_preset": "citation_optimized",
        "essential_fields": [],  # Empty to force preset
        "excluded_patterns": [],  # Empty to force preset
        "include_element_ids": True
    }
}

results = {}

for preset_name, filter_config in presets_config.items():
    print(f"\n🔧 Testing preset: {preset_name}")
    print("-" * 40)
    
    payload = {
        "source_file": "test.pdf",
        "analysis_result": azure_di_json,
        "filter_config": filter_config,
        "min_segment_tokens": 2000,
        "max_segment_tokens": 6000
    }
    
    response = requests.post("http://localhost:8000/segment-filtered", json=payload)
    
    if response.status_code == 200:
        data = response.json()
        metrics = data.get("metrics", {})
        segments = data.get("segments", [])
        
        results[preset_name] = {
            "reduction": metrics.get("reduction_percentage", 0),
            "excluded_fields": metrics.get("excluded_fields", []),
            "element_count": metrics.get("filtered_elements", 0)
        }
        
        print(f"✅ Reduction: {metrics.get('reduction_percentage', 0):.1f}%")
        print(f"📊 Excluded fields: {metrics.get('excluded_fields', [])}")
        
        # Check first element
        if segments and segments[0].get("elements"):
            first_elem = segments[0]["elements"][0]
            print(f"🔍 Element fields: {list(first_elem.keys())}")
    else:
        print(f"❌ Error: {response.status_code}")

# Compare results
print("\n\n📊 Comparison of Filter Presets")
print("=" * 60)
print(f"{'Preset':<20} {'Reduction':<15} {'Excluded Fields'}")
print("-" * 60)

for preset, data in results.items():
    reduction = f"{data['reduction']:.1f}%"
    excluded = len(data['excluded_fields'])
    print(f"{preset:<20} {reduction:<15} {excluded} fields excluded")

# Test with explicit field configurations
print("\n\n🔬 Testing with explicit field configurations")
print("=" * 60)

custom_configs = {
    "Minimal Fields": {
        "filter_preset": "custom",
        "essential_fields": ["content", "pageNumber"],
        "excluded_patterns": ["*"],  # Exclude everything else
        "include_element_ids": False
    },
    "Full Context": {
        "filter_preset": "custom", 
        "essential_fields": ["content", "pageNumber", "role", "elementType", "pageHeader", "pageFooter"],
        "contextual_fields": ["elementIndex", "parentSection"],
        "excluded_patterns": ["boundingBox", "spans"],
        "include_element_ids": True
    }
}

for config_name, filter_config in custom_configs.items():
    print(f"\n🔧 {config_name}")
    
    payload = {
        "source_file": "test.pdf",
        "analysis_result": azure_di_json,
        "filter_config": filter_config,
        "min_segment_tokens": 2000,
        "max_segment_tokens": 6000
    }
    
    response = requests.post("http://localhost:8000/segment-filtered", json=payload)
    
    if response.status_code == 200:
        data = response.json()
        metrics = data.get("metrics", {})
        print(f"  Reduction: {metrics.get('reduction_percentage', 0):.1f}%")
        print(f"  Excluded: {metrics.get('excluded_fields', [])}")