#!/usr/bin/env python3
"""
Test script for the anonymization endpoint.
Demonstrates how to anonymize Azure DI JSON output.

Uses Isotonic/distilbert_finetuned_ai4privacy_v2 - a BERT model
specifically fine-tuned for PII detection in privacy contexts.
"""

import json
import requests
from pathlib import Path
import sys

# Backend URL
BACKEND_URL = "http://localhost:8000"
ANONYMIZATION_ENDPOINT = f"{BACKEND_URL}/anonymization/anonymize-azure-di"

# Sample Azure DI JSON with PII (simplified structure)
SAMPLE_AZURE_DI_JSON = {
    "status": "succeeded",
    "createdDateTime": "2024-01-15T10:30:00Z",
    "content": "MEDICAL RECORD\n\nPatient: John Smith\nMRN: 12345678\nDate of Visit: January 15, 2024\n\nPhysician: Dr. Jane Williams, MD License: MD987654",
    "pages": [
        {
            "pageNumber": 1,
            "angle": 0,
            "width": 8.5,
            "height": 11,
            "unit": "inch",
            "words": [
                {
                    "content": "John",
                    "boundingBox": [100, 200, 150, 220],
                    "confidence": 0.99
                },
                {
                    "content": "Smith",
                    "boundingBox": [160, 200, 210, 220],
                    "confidence": 0.99
                }
            ],
            "lines": [
                {
                    "content": "Patient: John Smith",
                    "boundingBox": [100, 200, 300, 220]
                },
                {
                    "content": "SSN: 123-45-6789",
                    "boundingBox": [100, 240, 300, 260]
                }
            ]
        }
    ],
    "tables": [
        {
            "rowCount": 3,
            "columnCount": 3,
            "cells": [
                {
                    "rowIndex": 0,
                    "columnIndex": 0,
                    "content": "Date",
                    "kind": "columnHeader"
                },
                {
                    "rowIndex": 0,
                    "columnIndex": 1,
                    "content": "Provider",
                    "kind": "columnHeader"
                },
                {
                    "rowIndex": 1,
                    "columnIndex": 0,
                    "content": "01/15/2024"
                },
                {
                    "rowIndex": 1,
                    "columnIndex": 1,
                    "content": "Dr. Jane Williams"
                }
            ]
        }
    ],
    "keyValuePairs": [
        {
            "key": {
                "content": "Patient Name"
            },
            "value": {
                "content": "John Smith"
            }
        },
        {
            "key": {
                "content": "Phone"
            },
            "value": {
                "content": "(555) 123-4567"
            }
        },
        {
            "key": {
                "content": "Case #"
            },
            "value": {
                "content": "2024-CR-12345"
            }
        },
        {
            "key": {
                "content": "Bates"
            },
            "value": {
                "content": "BATES-001234"
            }
        }
    ]
}


def test_anonymization_endpoint():
    """Test the anonymization endpoint with sample data."""
    
    print("Testing anonymization endpoint...")
    print(f"URL: {ANONYMIZATION_ENDPOINT}")
    
    # Prepare request
    request_data = {
        "azure_di_json": SAMPLE_AZURE_DI_JSON,
        "config": {
            "preserve_structure": True,
            "entity_types": [
                "PERSON", 
                "DATE_TIME", 
                "US_SSN", 
                "PHONE_NUMBER",
                "MEDICAL_LICENSE",
                "BATES_NUMBER",
                "CASE_NUMBER",
                "MEDICAL_RECORD_NUMBER"
            ],
            "date_shift_days": 30,
            "consistent_replacements": True,
            "use_bert_ner": True  # Always use BERT
        }
    }
    
    try:
        # Make request
        response = requests.post(
            ANONYMIZATION_ENDPOINT,
            json=request_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            
            print("\n✅ Anonymization successful!")
            print(f"\nStatistics: {json.dumps(result['statistics'], indent=2)}")
            print(f"\nMappings ID: {result.get('mappings_id', 'N/A')}")
            
            # Save anonymized JSON (to gitignored directory)
            output_path = Path("../azure-di-json/sample_anonymized.json")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w') as f:
                json.dump(result['anonymized_json'], f, indent=2)
            
            print(f"\nAnonymized JSON saved to: {output_path}")
            
            # Show sample of anonymization
            print("\n--- Original vs Anonymized Sample ---")
            print(f"Original content: {SAMPLE_AZURE_DI_JSON['content'][:100]}...")
            print(f"Anonymized content: {result['anonymized_json']['content'][:100]}...")
            
        else:
            print(f"\n❌ Error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("\n❌ Could not connect to backend. Make sure it's running:")
        print("   cd backend && uv run run.py")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            print(f"Response body: {e.response.text}")


def anonymize_file(input_path: str, output_path: str = None):
    """Anonymize an Azure DI JSON file."""
    
    input_path = Path(input_path)
    if not input_path.exists():
        print(f"❌ File not found: {input_path}")
        return
    
    # Load JSON
    with open(input_path, 'r') as f:
        azure_di_json = json.load(f)
    
    print(f"Anonymizing {input_path.name}...")
    
    # Prepare request
    request_data = {
        "azure_di_json": azure_di_json,
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
            "date_shift_days": 365,
            "consistent_replacements": True,
            "use_bert_ner": True  # Use privacy-focused BERT for real files
        }
    }
    
    try:
        response = requests.post(
            ANONYMIZATION_ENDPOINT,
            json=request_data,
            headers={"Content-Type": "application/json"},
            timeout=1200  # 20 minutes for large documents with BERT processing
        )
        
        if response.status_code == 200:
            result = response.json()
            
            # Determine output path
            if output_path is None:
                output_path = input_path.parent / f"{input_path.stem}_anonymized.json"
            else:
                output_path = Path(output_path)
            
            # Save anonymized JSON
            with open(output_path, 'w') as f:
                json.dump(result['anonymized_json'], f, indent=2)
            
            print(f"✅ Anonymized and saved to: {output_path}")
            print(f"   Statistics: {result['statistics']}")
            
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Anonymize specific file
        input_file = sys.argv[1]
        output_file = sys.argv[2] if len(sys.argv) > 2 else None
        anonymize_file(input_file, output_file)
    else:
        # Run test with sample data
        test_anonymization_endpoint()