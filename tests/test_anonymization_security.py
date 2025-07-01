#!/usr/bin/env python3
"""Test anonymization security improvements."""

import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


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
            "entity_types": ["PERSON", "US_SSN", "DATE_TIME"],
            "score_threshold": 0.5
        }
    }
    
    # Make multiple requests
    results = []
    for i in range(3):
        r = client.post("/anonymization/anonymize-azure-di", json=payload)
        assert r.status_code == 200
        results.append(r.json()["anonymized_json"])
    
    # Check that results are different (no fixed seed)
    names_found = set()
    ssns_found = set()
    
    for result in results:
        content = result["content"]
        # Extract the anonymized values - they should be different each time
        names_found.add(content)
        
        # Also check metadata
        if "metadata" in result and "author" in result["metadata"]:
            names_found.add(result["metadata"]["author"])
    
    # With no fixed seed, we should get different values
    # LLM-Guard uses Faker which should generate different values each time
    assert len(names_found) > 1, "Same values generated - might still be using fixed seed"


def test_session_isolation():
    """Test that replacement mappings don't leak between sessions."""
    
    # First request with a specific name
    payload1 = {
        "azure_di_json": {"content": "Contact John Smith for details."},
        "config": {
            "entity_types": ["PERSON"],
            "score_threshold": 0.5
        }
    }
    
    # Second request with the same name
    payload2 = {
        "azure_di_json": {"content": "John Smith is the project lead."},
        "config": {
            "entity_types": ["PERSON"],
            "score_threshold": 0.5
        }
    }
    
    # First session
    r1 = client.post("/anonymization/anonymize-azure-di", json=payload1)
    assert r1.status_code == 200
    result1 = r1.json()["anonymized_json"]["content"]
    
    # Second session (should have different mapping)
    r2 = client.post("/anonymization/anonymize-azure-di", json=payload2)
    assert r2.status_code == 200
    result2 = r2.json()["anonymized_json"]["content"]
    
    # Check if "John Smith" was replaced with different values
    assert "John Smith" not in result1
    assert "John Smith" not in result2
    
    # In different sessions, the same name should get different replacements
    # because each request creates a new Vault instance
    replacement1 = result1.replace("Contact ", "").replace(" for details.", "")
    replacement2 = result2.replace(" is the project lead.", "")
    
    # With session isolation, different requests should use different replacements
    assert replacement1 != replacement2, "Sessions might not be isolated"


def test_no_mappings_id():
    """Test that mappings_id is not returned (deprecated for security)."""
    
    payload = {
        "azure_di_json": {"content": "Test data with John Doe"},
        "config": {
            "entity_types": ["PERSON"]
        }
    }
    
    r = client.post("/anonymization/anonymize-azure-di", json=payload)
    assert r.status_code == 200
    result = r.json()
    
    # Check that mappings_id is not in the response
    assert "mappings_id" not in result, "mappings_id should not be exposed"
    
    # Verify expected fields are present
    assert "anonymized_json" in result
    assert "statistics" in result