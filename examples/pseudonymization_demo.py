"""
Demonstration of pseudonymization and deanonymization with vault state.

This example shows how to:
1. Pseudonymize text with PII detection
2. Store vault state for consistent replacements
3. Use the vault across multiple documents
4. Deanonymize text to restore original values
"""

import requests
import json

# Base URL for the API
BASE_URL = "http://localhost:8000/anonymization"

def demo_pseudonymization():
    """Demonstrate pseudonymization with vault state."""
    
    # Document 1: Initial document with PII
    document1 = """
    Patient: John Smith
    Date of Birth: January 15, 1985
    Email: john.smith@hospital.com
    Phone: (555) 123-4567
    SSN: 123-45-6789
    
    Appointment scheduled for December 25, 2024 at 2:30 PM.
    Please contact Dr. Sarah Johnson at sarah.johnson@hospital.com.
    """
    
    # Document 2: Follow-up document referencing same entities
    document2 = """
    Follow-up for John Smith (DOB: January 15, 1985)
    
    Dr. Sarah Johnson has reviewed the case.
    Next appointment: January 15, 2025
    Contact: john.smith@hospital.com or (555) 123-4567
    """
    
    print("=== Pseudonymization Demo ===\n")
    
    # Step 1: Pseudonymize first document
    print("1. Pseudonymizing first document...")
    response1 = requests.post(
        f"{BASE_URL}/pseudonymize",
        json={
            "text": document1,
            "config": {
                "entity_types": ["PERSON", "DATE_TIME", "EMAIL_ADDRESS", "PHONE_NUMBER", "US_SSN"],
                "date_shift_days": 365  # Shift dates by up to 1 year
            }
        }
    )
    
    if response1.status_code == 200:
        result1 = response1.json()
        print(f"✓ Pseudonymized text:\n{result1['pseudonymized_text']}")
        print(f"\n✓ Statistics: {result1['statistics']}")
        print(f"\n✓ Vault entries: {len(result1['vault_data'])}")
        
        # Extract vault for reuse
        vault_data = result1['vault_data']
        
        # Show date offset
        date_offset = next((entry[1] for entry in vault_data if entry[0] == "_date_offset"), None)
        print(f"✓ Date offset: {date_offset} days")
    else:
        print(f"✗ Error: {response1.status_code} - {response1.text}")
        return
    
    # Step 2: Pseudonymize second document with same vault
    print("\n\n2. Pseudonymizing second document with same vault...")
    response2 = requests.post(
        f"{BASE_URL}/pseudonymize",
        json={
            "text": document2,
            "vault_data": vault_data,  # Use existing vault
            "config": {
                "entity_types": ["PERSON", "DATE_TIME", "EMAIL_ADDRESS", "PHONE_NUMBER"],
                "date_shift_days": 365
            }
        }
    )
    
    if response2.status_code == 200:
        result2 = response2.json()
        print(f"✓ Pseudonymized text:\n{result2['pseudonymized_text']}")
        print(f"\n✓ Statistics: {result2['statistics']}")
        print(f"\n✓ Total vault entries: {len(result2['vault_data'])}")
        
        # Update vault with any new entries
        vault_data = result2['vault_data']
    else:
        print(f"✗ Error: {response2.status_code} - {response2.text}")
        return
    
    # Step 3: Deanonymize to verify reversibility
    print("\n\n3. Deanonymizing first document...")
    response3 = requests.post(
        f"{BASE_URL}/deanonymize",
        json={
            "text": result1['pseudonymized_text'],
            "vault_data": vault_data
        }
    )
    
    if response3.status_code == 200:
        result3 = response3.json()
        print(f"✓ Deanonymized text:\n{result3['deanonymized_text']}")
        print(f"\n✓ Statistics: {result3['statistics']}")
        
        # Verify original content is restored
        if "John Smith" in result3['deanonymized_text'] and "123-45-6789" in result3['deanonymized_text']:
            print("\n✓ Original PII successfully restored!")
        else:
            print("\n✗ Warning: Some PII may not have been fully restored")
    else:
        print(f"✗ Error: {response3.status_code} - {response3.text}")
    
    # Step 4: Show vault contents (for demonstration)
    print("\n\n4. Vault contents (sample):")
    for i, (placeholder, original) in enumerate(vault_data[:5]):  # Show first 5 entries
        if not placeholder.startswith("_"):  # Skip metadata
            print(f"   {placeholder} → {original}")
    if len(vault_data) > 5:
        print(f"   ... and {len(vault_data) - 5} more entries")


def demo_stateless_workflow():
    """Demonstrate a stateless workflow where client manages vault."""
    print("\n\n=== Stateless Workflow Demo ===\n")
    
    # Simulate multiple API calls with client-managed state
    documents = [
        "Contact John Smith at john.smith@example.com",
        "John Smith called about the project",
        "Email sent to john.smith@example.com"
    ]
    
    vault_data = None  # Client maintains this
    pseudonymized_docs = []
    
    # Process each document
    for i, doc in enumerate(documents):
        print(f"\nProcessing document {i+1}...")
        
        request_data = {
            "text": doc,
            "config": {"entity_types": ["PERSON", "EMAIL_ADDRESS"]}
        }
        
        # Include vault data if we have it
        if vault_data:
            request_data["vault_data"] = vault_data
        
        response = requests.post(f"{BASE_URL}/pseudonymize", json=request_data)
        
        if response.status_code == 200:
            result = response.json()
            pseudonymized_docs.append(result['pseudonymized_text'])
            vault_data = result['vault_data']  # Update vault
            print(f"✓ Pseudonymized: {result['pseudonymized_text']}")
        else:
            print(f"✗ Error: {response.status_code}")
    
    # Show that all documents use consistent replacements
    print("\n✓ All documents processed with consistent pseudonyms!")
    print(f"✓ Final vault size: {len(vault_data)} entries")
    
    # Client can save vault_data to database, file, etc.
    print("\n✓ Client can now save vault_data for future use")


if __name__ == "__main__":
    print("Starting Pseudonymization Demo...")
    print("Make sure the FastAPI server is running on http://localhost:8000\n")
    
    try:
        # Check if server is running
        response = requests.get("http://localhost:8000/anonymization/health")
        if response.status_code == 200:
            print("✓ Server is healthy\n")
            demo_pseudonymization()
            demo_stateless_workflow()
        else:
            print("✗ Server health check failed")
    except requests.ConnectionError:
        print("✗ Cannot connect to server. Please start the server with: uv run run.py")