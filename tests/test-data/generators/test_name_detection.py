#!/usr/bin/env python3
"""Test name detection specifically."""

import requests
import json

# Test data with clear names
TEST_DATA = {
    "status": "succeeded",
    "createdDateTime": "2024-01-15T10:30:00Z",
    "content": """CASE REPORT

Complainant: John Smith
Witness: Jane Doe
Officer: Michael Johnson
Suspect: Robert Williams

On January 15, 2024, John Smith reported that Robert Williams had stolen his property.
Jane Doe witnessed the incident. Officer Michael Johnson responded to the scene.

Case #2024-CR-12345
SSN: 123-45-6789
Phone: (555) 123-4567
""",
    "pages": [{"pageNumber": 1, "angle": 0, "width": 8.5, "height": 11, "unit": "inch"}]
}

def test_name_detection():
    """Test if names are being detected."""
    
    # Test with explicit PERSON entity type
    request_data = {
        "azure_di_json": TEST_DATA,
        "config": {
            "preserve_structure": True,
            "entity_types": ["PERSON"],  # Only test PERSON detection
            "date_shift_days": 30,
            "consistent_replacements": True,
            "use_bert_ner": True
        }
    }
    
    print("Testing PERSON detection only...")
    
    try:
        response = requests.post(
            "http://localhost:8000/anonymization/anonymize-azure-di",
            json=request_data,
            timeout=1200  # 20 minutes for BERT processing
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ Response received")
            print(f"Statistics: {result['statistics']}")
            
            # Check if any names were replaced
            original = TEST_DATA['content']
            anonymized = result['anonymized_json']['content']
            
            print("\n--- Name Detection Results ---")
            names = ["John Smith", "Jane Doe", "Michael Johnson", "Robert Williams"]
            for name in names:
                if name in original and name not in anonymized:
                    print(f"✅ '{name}' was anonymized")
                elif name in anonymized:
                    print(f"❌ '{name}' was NOT anonymized")
            
            print(f"\n--- Full Anonymized Content ---")
            print(anonymized)
            
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ Error: {e}")


def test_all_entities():
    """Test with all entity types."""
    
    request_data = {
        "azure_di_json": TEST_DATA,
        "config": {
            "preserve_structure": True,
            "entity_types": [
                "PERSON", 
                "DATE_TIME", 
                "LOCATION",
                "US_SSN", 
                "PHONE_NUMBER",
                "EMAIL_ADDRESS",
                "MEDICAL_LICENSE",
                "BATES_NUMBER",
                "CASE_NUMBER",
                "MEDICAL_RECORD_NUMBER"
            ],
            "date_shift_days": 30,
            "consistent_replacements": True,
            "use_bert_ner": True
        }
    }
    
    print("\n\nTesting ALL entity types...")
    
    try:
        response = requests.post(
            "http://localhost:8000/anonymization/anonymize-azure-di",
            json=request_data,
            timeout=1200  # 20 minutes for BERT processing
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ Response received")
            print(f"Statistics: {result['statistics']}")
            
            print(f"\n--- Anonymized Content ---")
            print(result['anonymized_json']['content'])
            
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    test_name_detection()
    test_all_entities()