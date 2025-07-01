#!/usr/bin/env python3
"""Debug anonymization issues."""

import requests
import json

def test_all_entity_types():
    """Test detection of all entity types."""
    
    test_cases = [
        {
            "name": "Simple name",
            "text": "John Smith is here",
            "expected": ["PERSON"]
        },
        {
            "name": "Full context",
            "text": "Dr. Sarah Johnson, MD is a doctor",
            "expected": ["PERSON"]
        },
        {
            "name": "SSN",
            "text": "SSN: 123-45-6789",
            "expected": ["US_SSN"]
        },
        {
            "name": "Multiple PII",
            "text": "Contact Dr. Emily Brown at emily@example.com or 555-123-4567",
            "expected": ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER"]
        }
    ]
    
    for test in test_cases:
        print(f"\n=== Testing: {test['name']} ===")
        print(f"Text: {test['text']}")
        
        payload = {
            "azure_di_json": {"content": test['text']},
            "config": {
                "entity_types": ["PERSON", "US_SSN", "EMAIL_ADDRESS", "PHONE_NUMBER", "DATE_TIME", "LOCATION"],
                "score_threshold": 0.01,  # Very low threshold for debugging
                "return_decision_process": True
            }
        }
        
        try:
            r = requests.post("http://localhost:8000/anonymization/anonymize-azure-di", json=payload)
            if r.status_code == 200:
                result = r.json()
                print(f"Anonymized: {result['anonymized_json']['content']}")
                print(f"Statistics: {result['statistics']}")
                
                # Check if expected entities were detected
                detected_types = list(result['statistics'].keys())
                for expected_type in test['expected']:
                    if expected_type in detected_types:
                        print(f"✅ {expected_type} detected")
                    else:
                        print(f"❌ {expected_type} NOT detected")
            else:
                print(f"❌ Error {r.status_code}: {r.text}")
        except Exception as e:
            print(f"❌ Request failed: {e}")

if __name__ == "__main__":
    print("Debugging anonymization detection...\n")
    
    # Check if server is running
    try:
        r = requests.get("http://localhost:8000/health")
        if r.status_code != 200:
            print("❌ Server not healthy")
            exit(1)
    except:
        print("❌ Server not running. Start with: uv run run.py")
        exit(1)
    
    test_all_entity_types()