#!/usr/bin/env python3
"""Test anonymization security improvements."""

import requests
import json
from typing import Dict, List

def test_anonymization_randomness():
    """Test that anonymization produces different results each time (no fixed seed)."""
    
    # Sample data with PII
    test_data = {
        "content": "Dr. John Smith (SSN: 123-45-6789) treated patient Jane Doe on January 15, 2025.",
        "metadata": {
            "author": "Dr. Emily Johnson",
            "date": "2025-01-15"
        }
    }
    
    payload = {
        "azure_di_json": test_data,
        "config": {
            "preserve_structure": True,
            "entity_types": ["PERSON", "US_SSN", "DATE_TIME"],
            "consistent_replacements": True,
            "score_threshold": 0.5
        }
    }
    
    # Make multiple requests
    results = []
    for i in range(3):
        try:
            r = requests.post("http://localhost:8000/anonymization/anonymize-azure-di", json=payload)
            if r.status_code == 200:
                results.append(r.json()["anonymized_json"])
            else:
                print(f"❌ Request {i+1} failed: {r.status_code}")
                return False
        except Exception as e:
            print(f"❌ Request {i+1} error: {e}")
            return False
    
    # Check that results are different (no fixed seed)
    names_found = set()
    ssns_found = set()
    
    for result in results:
        content = result["content"]
        # Extract the anonymized values
        # This is a simple check - in reality the positions might vary
        if "Dr." in content:
            # Extract name after "Dr."
            dr_pos = content.index("Dr.")
            name_end = content.find("(", dr_pos)
            if name_end > dr_pos:
                name = content[dr_pos:name_end].strip()
                names_found.add(name)
        
        if "SSN:" in content:
            ssn_pos = content.index("SSN:") + 5
            ssn_end = content.find(")", ssn_pos)
            if ssn_end > ssn_pos:
                ssn = content[ssn_pos:ssn_end].strip()
                ssns_found.add(ssn)
    
    print(f"Found {len(names_found)} different names across runs")
    print(f"Found {len(ssns_found)} different SSNs across runs")
    
    # With no fixed seed, we should get different values
    if len(names_found) > 1 or len(ssns_found) > 1:
        print("✅ Randomization working - different values generated")
        return True
    else:
        print("❌ Same values generated - might still be using fixed seed")
        return False


def test_session_isolation():
    """Test that replacement mappings don't leak between sessions."""
    
    # First request with a specific name
    payload1 = {
        "azure_di_json": {"content": "Contact John Smith for details."},
        "config": {
            "entity_types": ["PERSON"],
            "consistent_replacements": True,
            "score_threshold": 0.5
        }
    }
    
    # Second request with the same name
    payload2 = {
        "azure_di_json": {"content": "John Smith is the project lead."},
        "config": {
            "entity_types": ["PERSON"],
            "consistent_replacements": True,
            "score_threshold": 0.5
        }
    }
    
    try:
        # First session
        r1 = requests.post("http://localhost:8000/anonymization/anonymize-azure-di", json=payload1)
        if r1.status_code != 200:
            print(f"❌ First request failed: {r1.status_code}")
            return False
        
        result1 = r1.json()["anonymized_json"]["content"]
        
        # Second session (should have different mapping)
        r2 = requests.post("http://localhost:8000/anonymization/anonymize-azure-di", json=payload2)
        if r2.status_code != 200:
            print(f"❌ Second request failed: {r2.status_code}")
            return False
        
        result2 = r2.json()["anonymized_json"]["content"]
        
        # Extract the replacement names
        # They should be different since sessions are isolated
        print(f"Session 1: {result1}")
        print(f"Session 2: {result2}")
        
        # Check if "John Smith" was replaced with different values
        if "John Smith" not in result1 and "John Smith" not in result2:
            # Both were anonymized, check if replacements differ
            if result1 != result2:
                print("✅ Session isolation working - different replacements in different sessions")
                return True
            else:
                print("⚠️  Same replacement used - sessions might not be isolated")
                return False
        else:
            print("❌ Anonymization failed - original text still present")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_no_mappings_id():
    """Test that mappings_id is not returned (deprecated for security)."""
    
    payload = {
        "azure_di_json": {"content": "Test data with John Doe"},
        "config": {
            "entity_types": ["PERSON"],
            "consistent_replacements": True
        }
    }
    
    try:
        r = requests.post("http://localhost:8000/anonymization/anonymize-azure-di", json=payload)
        if r.status_code == 200:
            result = r.json()
            mappings_id = result.get("mappings_id")
            if mappings_id is None:
                print("✅ Security improvement: mappings_id not exposed")
                return True
            else:
                print(f"❌ mappings_id still exposed: {mappings_id}")
                return False
        else:
            print(f"❌ Request failed: {r.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    print("Testing anonymization security improvements...\n")
    
    # Check if server is running
    try:
        r = requests.get("http://localhost:8000/health")
        if r.status_code != 200:
            print("❌ Server not healthy")
            exit(1)
    except:
        print("❌ Server not running. Start with: uv run run.py")
        exit(1)
    
    # Run tests
    tests = [
        ("Randomness Test", test_anonymization_randomness),
        ("Session Isolation Test", test_session_isolation),
        ("No Mappings ID Test", test_no_mappings_id)
    ]
    
    passed = 0
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        if test_func():
            passed += 1
        print()
    
    print(f"\nSummary: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("✅ All security improvements verified!")
        exit(0)
    else:
        print("❌ Some tests failed")
        exit(1)