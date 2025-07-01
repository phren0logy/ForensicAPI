#!/usr/bin/env python3
"""
Test script for the markdown anonymization endpoint.
"""

import requests
import json

# Test markdown with various PII
test_markdown = """
# Meeting Notes - Project Phoenix

**Date**: January 15, 2024  
**Attendees**: Dr. Sarah Johnson, Michael Chen, Emily Rodriguez

## Overview

The meeting was held at 742 Evergreen Terrace, Springfield, IL 62701. 
Dr. Johnson (email: sarah.johnson@example.com, phone: 555-123-4567) presented 
the latest findings from patient MRN: 12345678.

## Key Points

1. **Budget Approval**: Case #2024-CR-00156 has been approved
2. **Medical Records**: Patient SSN 123-45-6789 needs updating
3. **Contact Info**: Reach Michael at michael.chen@company.com or (555) 987-6543

## Action Items

- [ ] Follow up with Emily Rodriguez at emily.r@example.org
- [ ] Review Bates numbers ABC-123456 through ABC-123467
- [ ] Schedule next meeting for February 20, 2024

---

*Confidential - Internal Use Only*
"""

def test_markdown_anonymization():
    """Test the markdown anonymization endpoint."""
    url = "http://localhost:8000/anonymization/anonymize-markdown"
    
    # Prepare request
    request_data = {
        "markdown_text": test_markdown,
        "config": {
            "preserve_structure": True,
            "consistent_replacements": True,
            "use_bert_ner": True,
            "entity_types": [
                "PERSON", "DATE_TIME", "LOCATION", "PHONE_NUMBER",
                "EMAIL_ADDRESS", "US_SSN", "MEDICAL_RECORD_NUMBER",
                "BATES_NUMBER", "CASE_NUMBER"
            ]
        }
    }
    
    print("Testing markdown anonymization endpoint...")
    print("=" * 80)
    
    try:
        # Make request
        response = requests.post(url, json=request_data)
        response.raise_for_status()
        
        # Parse response
        result = response.json()
        
        print("ORIGINAL MARKDOWN:")
        print("-" * 80)
        print(test_markdown)
        print("\n" + "=" * 80 + "\n")
        
        print("ANONYMIZED MARKDOWN:")
        print("-" * 80)
        print(result["anonymized_text"])
        print("\n" + "=" * 80 + "\n")
        
        print("STATISTICS:")
        print("-" * 80)
        for entity_type, count in sorted(result["statistics"].items()):
            print(f"{entity_type:25} : {count:3} occurrences")
        
        if result.get("mappings_id"):
            print(f"\nMappings ID: {result['mappings_id']}")
        
        print("\n✅ Test completed successfully!")
        
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to server. Make sure the server is running:")
        print("   uv run run.py")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    test_markdown_anonymization()