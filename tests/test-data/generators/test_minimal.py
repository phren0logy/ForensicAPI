#!/usr/bin/env python3
"""Minimal test of the anonymization endpoint."""

import requests

# Test health endpoint
try:
    response = requests.get("http://localhost:8000/anonymization/health", timeout=5)
    print(f"Health check status: {response.status_code}")
    if response.status_code != 200:
        print(f"Response: {response.text}")
    else:
        print(f"Response: {response.json()}")
except Exception as e:
    print(f"Error: {e}")

# Test a simple POST
try:
    simple_data = {
        "azure_di_json": {"content": "Test"},
        "config": {"preserve_structure": True}
    }
    response = requests.post("http://localhost:8000/anonymization/anonymize-azure-di", 
                           json=simple_data, timeout=5)
    print(f"\nAnonymize endpoint status: {response.status_code}")
    if response.status_code != 200:
        print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")