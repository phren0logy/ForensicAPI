#!/usr/bin/env python3
"""
Test the anonymization endpoint using synthetic test data.
This script uses the safe synthetic files that can be committed to the repo.
"""

import json
import requests
from pathlib import Path
import sys

# Backend URL
BACKEND_URL = "http://localhost:8000"
ANONYMIZATION_ENDPOINT = f"{BACKEND_URL}/anonymization/anonymize-azure-di"
HEALTH_ENDPOINT = f"{BACKEND_URL}/anonymization/health"

# Synthetic test data directory
SYNTHETIC_DIR = Path(__file__).parent.parent / "synthetic"


def check_backend_health():
    """Check if the anonymization service is ready."""
    try:
        response = requests.get(HEALTH_ENDPOINT, timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Backend health check: {data['status']}")
            return True
        else:
            print(f"❌ Backend health check failed: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to backend. Make sure it's running:")
        print("   cd backend && uv run run.py")
        return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False


def test_synthetic_file(file_path: Path, use_bert: bool = True):
    """Test anonymization with a synthetic file."""
    print(f"\n{'='*60}")
    print(f"Testing: {file_path.name}")
    print(f"BERT NER: {'Enabled' if use_bert else 'Disabled (pattern-based only)'}")
    print('='*60)
    
    # Load the synthetic data
    with open(file_path, 'r') as f:
        synthetic_data = json.load(f)
    
    # Prepare request
    request_data = {
        "azure_di_json": synthetic_data,
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
            "use_bert_ner": use_bert
        }
    }
    
    try:
        # Make request
        response = requests.post(
            ANONYMIZATION_ENDPOINT,
            json=request_data,
            headers={"Content-Type": "application/json"},
            timeout=1200 if use_bert else 60  # 20 minutes for BERT
        )
        
        if response.status_code == 200:
            result = response.json()
            
            print("\n✅ Anonymization successful!")
            print(f"\nStatistics:")
            for entity_type, count in sorted(result['statistics'].items()):
                print(f"  - {entity_type}: {count} found")
            
            # Save anonymized result (to gitignored directory)
            output_dir = Path(__file__).parent.parent / "azure-di-json" / "synthetic_tests"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            output_filename = f"{file_path.stem}_anonymized{'_bert' if use_bert else '_pattern'}.json"
            output_path = output_dir / output_filename
            
            with open(output_path, 'w') as f:
                json.dump(result['anonymized_json'], f, indent=2)
            
            print(f"\n📁 Saved to: {output_path}")
            
            # Show sample comparisons
            print("\n--- Content Comparison Sample ---")
            original_content = synthetic_data.get('content', '')[:200]
            anonymized_content = result['anonymized_json'].get('content', '')[:200]
            
            print(f"Original:   {original_content}...")
            print(f"Anonymized: {anonymized_content}...")
            
            return True
            
        else:
            print(f"\n❌ Error: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        return False


def main():
    """Run tests on all synthetic files."""
    print("🧪 Testing Anonymization Endpoint with Synthetic Data")
    print("="*60)
    
    # Check backend health first
    if not check_backend_health():
        sys.exit(1)
    
    # Get all synthetic test files
    synthetic_files = list(SYNTHETIC_DIR.glob("*.json"))
    
    if not synthetic_files:
        print("❌ No synthetic test files found!")
        print(f"   Run: python generate_synthetic_test_data.py")
        sys.exit(1)
    
    print(f"\nFound {len(synthetic_files)} synthetic test files")
    
    # Test each file with both pattern-based and BERT
    success_count = 0
    total_tests = len(synthetic_files) * 2  # Testing each file twice
    
    for file_path in synthetic_files:
        # Test with pattern-based recognition
        if test_synthetic_file(file_path, use_bert=False):
            success_count += 1
        
        # Test with BERT NER
        print(f"\n🔄 Re-testing {file_path.name} with BERT NER...")
        if test_synthetic_file(file_path, use_bert=True):
            success_count += 1
    
    # Summary
    print(f"\n{'='*60}")
    print(f"✨ Test Summary: {success_count}/{total_tests} tests passed")
    
    if success_count == total_tests:
        print("\n🎉 All tests passed! The anonymization endpoint is working correctly.")
        print("\n📝 Next steps:")
        print("1. Process your real PDFs through Azure DI")
        print("2. Use test_anonymization.py to anonymize the real JSON files")
        print("3. The anonymized files will be saved to test-data/azure-di-json/ (gitignored)")
    else:
        print("\n⚠️  Some tests failed. Check the errors above.")


if __name__ == "__main__":
    main()