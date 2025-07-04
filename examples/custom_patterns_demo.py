"""
Demonstration of custom pattern detection for legal and medical documents.

This example shows how to:
1. Use predefined pattern sets (legal, medical)
2. Define custom patterns for domain-specific identifiers
3. Combine AI detection with regex patterns
"""

import requests
import json

# Base URL for the API
BASE_URL = "http://localhost:8000/anonymization"

def demo_legal_patterns():
    """Demonstrate legal document pattern detection."""
    
    legal_document = """
    MEMORANDUM OF LAW
    
    Case No. 1:23-cv-45678
    Hon. Jane Smith, Presiding
    
    Plaintiff submits this memorandum in support of their Motion for Summary Judgment
    (ECF No. 123). As detailed in Exhibit A (BATES-001234 through BATES-001456),
    the evidence clearly establishes...
    
    The deposition transcript of John Doe (DEF00012345) confirms that on
    January 15, 2024, the defendant admitted liability. See Docket No. 45-2.
    
    For further reference, see Court Filing ID: 2024-CR-00156.
    """
    
    print("=== Legal Pattern Detection Demo ===\n")
    
    response = requests.post(
        f"{BASE_URL}/anonymize-markdown",
        json={
            "markdown_text": legal_document,
            "config": {
                "pattern_sets": ["legal"],  # Enable legal patterns
                "entity_types": ["PERSON", "DATE_TIME"],  # Also detect names and dates
                "score_threshold": 0.7
            }
        }
    )
    
    if response.status_code == 200:
        result = response.json()
        print("Original Document:")
        print(legal_document[:200] + "...\n")
        
        print("Anonymized Document:")
        print(result['anonymized_text'][:200] + "...\n")
        
        print("Detection Statistics:")
        for entity_type, count in result['statistics'].items():
            print(f"  {entity_type}: {count}")
        
        # Show some vault entries
        print("\nSample Anonymization Mappings:")
        for entry in result['vault_data'][:5]:
            if not entry[0].startswith("_"):
                print(f"  {entry[1]} → {entry[0]}")
    else:
        print(f"Error: {response.status_code} - {response.text}")


def demo_medical_patterns():
    """Demonstrate medical document pattern detection."""
    
    medical_record = """
    PATIENT DISCHARGE SUMMARY
    
    Patient Name: Sarah Johnson
    MRN: 12345678
    DOB: 05/15/1980
    
    Admission Date: December 1, 2024
    Discharge Date: December 5, 2024
    
    Primary Care Provider: Dr. Michael Chen, MD
    Provider NPI: 1234567890
    
    Insurance: BlueCross BlueShield
    Member ID: ABC123456789
    Policy Number: GRP-2024-789
    
    Discharge Medications:
    - Prescribed by Dr. Chen (DEA: AB1234567)
    - Pharmacy to process Claim # MED2024-456789
    """
    
    print("\n\n=== Medical Pattern Detection Demo ===\n")
    
    response = requests.post(
        f"{BASE_URL}/anonymize-markdown",
        json={
            "markdown_text": medical_record,
            "config": {
                "pattern_sets": ["medical"],  # Enable medical patterns
                "entity_types": ["PERSON", "DATE_TIME"],  # Also detect names and dates
                "date_shift_days": 30  # Shift dates by up to 30 days
            }
        }
    )
    
    if response.status_code == 200:
        result = response.json()
        print("Anonymized Medical Record:")
        print(result['anonymized_text'][:300] + "...\n")
        
        print("Detection Statistics:")
        for entity_type, count in result['statistics'].items():
            print(f"  {entity_type}: {count}")
    else:
        print(f"Error: {response.status_code} - {response.text}")


def demo_custom_patterns():
    """Demonstrate custom pattern definition."""
    
    technical_document = """
    INCIDENT REPORT
    
    Ticket ID: TICK-2024-001234
    Severity: HIGH
    
    The security breach was detected in server PROD-WEB-001 at IP 192.168.1.100.
    The attacker's Bitcoin wallet 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa was identified.
    
    API Key compromised: sk_test_XXXXXXXXXXXXXXXXXXXX
    
    Transaction logs show suspicious activity from tracking code TRACK-ABC-123456.
    Reference: Internal audit report AUD-2024-Q4-001.
    """
    
    print("\n\n=== Custom Pattern Demo ===\n")
    
    # Define custom patterns for this technical document
    custom_patterns = [
        {
            "name": "TICKET_ID",
            "expressions": [r"\bTICK-\d{4}-\d{6}\b"],
            "examples": ["TICK-2024-001234"]
        },
        {
            "name": "SERVER_ID", 
            "expressions": [r"\b(PROD|DEV|TEST)-[A-Z]+-\d{3}\b"],
            "examples": ["PROD-WEB-001"]
        },
        {
            "name": "TRACKING_CODE",
            "expressions": [r"\bTRACK-[A-Z]{3}-\d{6}\b"],
            "examples": ["TRACK-ABC-123456"]
        },
        {
            "name": "AUDIT_REPORT",
            "expressions": [r"\bAUD-\d{4}-Q[1-4]-\d{3}\b"],
            "examples": ["AUD-2024-Q4-001"]
        }
    ]
    
    response = requests.post(
        f"{BASE_URL}/anonymize-markdown",
        json={
            "markdown_text": technical_document,
            "config": {
                "custom_patterns": custom_patterns,
                "entity_types": ["IP_ADDRESS", "CRYPTO", "API_KEY"],  # Combine with AI detection
                "score_threshold": 0.8
            }
        }
    )
    
    if response.status_code == 200:
        result = response.json()
        print("Original Technical Document:")
        print(technical_document[:200] + "...\n")
        
        print("Anonymized Document:")
        print(result['anonymized_text'][:300] + "...\n")
        
        print("Detection Statistics:")
        for entity_type, count in result['statistics'].items():
            print(f"  {entity_type}: {count}")
            
        print("\n✓ Custom patterns successfully detected technical identifiers!")
    else:
        print(f"Error: {response.status_code} - {response.text}")


def demo_combined_patterns():
    """Demonstrate combining multiple pattern sets."""
    
    mixed_document = """
    FORENSIC ANALYSIS REPORT
    
    Case No. 2:24-cr-00789
    Evidence Item: BATES-567890
    
    Patient: Robert Smith (MRN: 87654321)
    Treating Physician: Dr. Emily White, NPI: 9876543210
    
    Digital evidence recovered from device shows communication with 
    john.doe@example.com regarding transaction TRACK-XYZ-789012.
    
    Insurance claim (Member ID: XYZ987654) pending review.
    Court hearing scheduled for March 15, 2025 (Docket No. 89-123).
    """
    
    print("\n\n=== Combined Patterns Demo ===\n")
    
    response = requests.post(
        f"{BASE_URL}/anonymize-markdown",
        json={
            "markdown_text": mixed_document,
            "config": {
                "pattern_sets": ["legal", "medical"],  # Use both pattern sets
                "custom_patterns": [
                    {
                        "name": "TRACKING_CODE",
                        "expressions": [r"\bTRACK-[A-Z]{3}-\d{6}\b"]
                    }
                ],
                "entity_types": ["PERSON", "EMAIL_ADDRESS", "DATE_TIME"],
                "score_threshold": 0.7
            }
        }
    )
    
    if response.status_code == 200:
        result = response.json()
        print("Anonymized Mixed Document:")
        print(result['anonymized_text'])
        
        print("\nDetection Statistics:")
        for entity_type, count in result['statistics'].items():
            print(f"  {entity_type}: {count}")
            
        print("\n✓ Successfully combined AI detection with legal, medical, and custom patterns!")
    else:
        print(f"Error: {response.status_code} - {response.text}")


if __name__ == "__main__":
    print("Custom Pattern Detection Demo")
    print("=============================")
    print("Make sure the FastAPI server is running on http://localhost:8000\n")
    
    try:
        # Check if server is running
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            print("✓ Server is healthy\n")
            
            # Run all demos
            demo_legal_patterns()
            demo_medical_patterns()
            demo_custom_patterns()
            demo_combined_patterns()
            
        else:
            print("✗ Server health check failed")
    except requests.ConnectionError:
        print("✗ Cannot connect to server. Please start the server with: uv run run.py")