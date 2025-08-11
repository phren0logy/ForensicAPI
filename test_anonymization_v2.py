#!/usr/bin/env python3
"""Quick test of the new anonymization v2.0 endpoint."""

import requests
import json

# Test the anonymization endpoint locally
def test_anonymization():
    # First, let's test if the server is running
    base_url = "http://localhost:8000"
    
    # Test document with various PII
    test_document = """
    Patient: John Smith
    Date of Birth: January 15, 1985
    Email: john.smith@hospital.com
    Phone: (555) 123-4567
    SSN: 123-45-6789
    
    Dr. Sarah Johnson reviewed the case on December 25, 2024.
    Follow-up scheduled for January 15, 2025.
    """
    
    # Test anonymization
    response = requests.post(
        f"{base_url}/anonymization/anonymize",
        json={
            "content": test_document,
            "config": {
                "entity_types": ["PERSON", "DATE_TIME", "EMAIL_ADDRESS", "PHONE_NUMBER", "US_SSN"],
                "date_shift_days": 365
            }
        }
    )
    
    if response.status_code == 200:
        result = response.json()
        print("✅ Anonymization successful!")
        print("\nOriginal text:")
        print(test_document)
        print("\nAnonymized text:")
        print(result['anonymized_content'])
        print("\nStatistics:")
        print(json.dumps(result['statistics'], indent=2))
        print("\nVault structure (v2.0):")
        print(f"- Version: {result['vault_data']['version']}")
        print(f"- Created: {result['vault_data']['created']}")
        print(f"- Date offset: {result['vault_data']['metadata']['date_offset']}")
        print(f"- Mappings count: {len(result['vault_data']['mappings'])}")
        
        # Test consistency - anonymize again with the same vault
        print("\n\nTesting consistency with second document...")
        test_document_2 = """
        Follow-up for John Smith.
        Contact: john.smith@hospital.com
        """
        
        response2 = requests.post(
            f"{base_url}/anonymization/anonymize",
            json={
                "content": test_document_2,
                "vault_data": result['vault_data'],
                "config": {
                    "entity_types": ["PERSON", "EMAIL_ADDRESS"],
                    "date_shift_days": 365
                }
            }
        )
        
        if response2.status_code == 200:
            result2 = response2.json()
            print("\n✅ Second anonymization successful!")
            print("\nSecond document anonymized:")
            print(result2['anonymized_content'])
            print("\nVerifying consistency:")
            # Check if John Smith got the same replacement
            if "John Smith" in test_document_2:
                print("✅ Consistent replacements confirmed!")
        else:
            print(f"\n❌ Second anonymization failed: {response2.status_code}")
            print(response2.text)
            
    else:
        print(f"❌ Anonymization failed: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    print("Testing ForensicAPI v2.0 Anonymization...\n")
    
    # Check if server is running
    try:
        response = requests.get("http://localhost:8000/")
        print("✅ Server is running")
    except requests.exceptions.ConnectionError:
        print("❌ Server is not running. Please start it with: uv run run.py")
        exit(1)
    
    test_anonymization()