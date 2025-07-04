"""
Test script for pseudonymization and deanonymization endpoints.

This script demonstrates the stateless vault functionality.
"""

import pytest
import json
from typing import Dict, List
from datetime import datetime

# Test data with various PII types
TEST_TEXT = """
Hello, my name is John Smith and I live in New York.
My email is john.smith@example.com and my phone is (555) 123-4567.
I was born on January 15, 1985 and my SSN is 123-45-6789.
I have an appointment on December 25, 2024 at 2:30 PM.
"""

TEST_TEXT_2 = """
John Smith called me yesterday about the project.
He mentioned his email john.smith@example.com again.
We scheduled a meeting for January 15, 1985 (yes, time travel!).
"""


def test_serialize_deserialize_vault():
    """Test vault serialization and deserialization."""
    import sys
    sys.path.append('..')
    from routes.anonymization import serialize_vault, deserialize_vault, Vault
    
    # Create a vault with some test data
    vault = Vault()
    vault.append(("john.doe@example.com", "real.email@company.com"))
    vault.append(("John Doe", "Jane Smith"))
    vault.append(("2024-01-15", "2023-12-25"))
    
    # Test with date offset
    date_offset = -365
    
    # Serialize
    serialized = serialize_vault(vault, date_offset)
    
    # Check structure
    assert isinstance(serialized, list)
    assert len(serialized) == 4  # 3 entries + 1 metadata
    assert ["_date_offset", "-365"] in serialized
    
    # Deserialize
    new_vault, new_offset = deserialize_vault(serialized)
    
    # Verify
    assert new_offset == date_offset
    assert len(new_vault.get()) == 3
    
    # Check entries preserved
    vault_items = [list(item) for item in new_vault.get()]
    assert ["john.doe@example.com", "real.email@company.com"] in vault_items
    assert ["John Doe", "Jane Smith"] in vault_items
    assert ["2024-01-15", "2023-12-25"] in vault_items


def test_deanonymize_text_with_vault():
    """Test deanonymization function."""
    from routes.anonymization import deanonymize_text_with_vault
    
    # Sample pseudonymized text
    text = "Hello John Doe, your email john.doe@example.com was updated on 2024-01-15."
    
    # Vault data
    vault_data = [
        ["John Doe", "Jane Smith"],
        ["john.doe@example.com", "jane.smith@company.com"],
        ["2024-01-15", "2023-12-25"],
        ["_date_offset", "-365"]  # Should be ignored
    ]
    
    # Deanonymize
    result, stats = deanonymize_text_with_vault(text, vault_data)
    
    # Check result
    assert "Jane Smith" in result
    assert "jane.smith@company.com" in result
    assert "2023-12-25" in result
    assert "John Doe" not in result
    assert "john.doe@example.com" not in result
    
    # Check statistics
    assert stats["PERSON"] == 1
    assert stats["EMAIL_ADDRESS"] == 1
    assert stats["DATE_TIME"] == 1


def test_consistent_date_offset():
    """Test that date offset remains consistent across requests."""
    from routes.anonymization import generate_session_shift
    
    # First call - generate new offset
    offset1 = generate_session_shift(365, None)
    assert -365 <= offset1 <= 365
    
    # Second call - use existing offset
    offset2 = generate_session_shift(365, offset1)
    assert offset2 == offset1
    
    # Third call - different existing offset
    offset3 = generate_session_shift(365, 100)
    assert offset3 == 100


@pytest.mark.asyncio
async def test_pseudonymization_endpoint(test_client):
    """Test the /pseudonymize endpoint."""
    # First request - no vault data
    response = test_client.post(
        "/anonymization/pseudonymize",
        json={
            "text": TEST_TEXT,
            "config": {
                "entity_types": ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "DATE_TIME", "US_SSN"],
                "date_shift_days": 365
            }
        }
    )
    
    assert response.status_code == 200
    data1 = response.json()
    
    # Check response structure
    assert "pseudonymized_text" in data1
    assert "statistics" in data1
    assert "vault_data" in data1
    
    # Verify PII was replaced
    assert "John Smith" not in data1["pseudonymized_text"]
    assert "john.smith@example.com" not in data1["pseudonymized_text"]
    assert "123-45-6789" not in data1["pseudonymized_text"]
    
    # Check vault data includes date offset
    date_offset_entries = [entry for entry in data1["vault_data"] if entry[0] == "_date_offset"]
    assert len(date_offset_entries) == 1
    
    # Second request - use vault data for consistency
    response2 = test_client.post(
        "/anonymization/pseudonymize",
        json={
            "text": TEST_TEXT_2,
            "vault_data": data1["vault_data"],
            "config": {
                "entity_types": ["PERSON", "EMAIL_ADDRESS", "DATE_TIME"],
                "date_shift_days": 365
            }
        }
    )
    
    assert response2.status_code == 200
    data2 = response2.json()
    
    # Extract pseudonyms from both texts
    # Since "John Smith" appears in both texts, it should have the same replacement
    # We'll check by looking at the vault data
    vault1_names = [entry for entry in data1["vault_data"] if "John Smith" in entry]
    vault2_names = [entry for entry in data2["vault_data"] if "John Smith" in entry]
    
    # Should have consistent replacements
    if vault1_names and vault2_names:
        assert vault1_names[0][0] == vault2_names[0][0]  # Same pseudonym


@pytest.mark.asyncio
async def test_deanonymization_endpoint(test_client):
    """Test the /deanonymize endpoint."""
    # First, pseudonymize some text
    response = test_client.post(
        "/anonymization/pseudonymize",
        json={
            "text": TEST_TEXT,
            "config": {
                "entity_types": ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "DATE_TIME", "US_SSN"],
                "date_shift_days": 0  # No date shifting for easier testing
            }
        }
    )
    
    assert response.status_code == 200
    pseudo_data = response.json()
    
    # Now deanonymize it
    response2 = test_client.post(
        "/anonymization/deanonymize",
        json={
            "text": pseudo_data["pseudonymized_text"],
            "vault_data": pseudo_data["vault_data"]
        }
    )
    
    assert response2.status_code == 200
    deano_data = response2.json()
    
    # The deanonymized text should match the original
    # Note: Due to how LLM-Guard processes text, there might be minor formatting differences
    assert "John Smith" in deano_data["deanonymized_text"]
    assert "john.smith@example.com" in deano_data["deanonymized_text"]
    assert "123-45-6789" in deano_data["deanonymized_text"]
    
    # Check statistics
    assert deano_data["statistics"]["PERSON"] >= 1
    assert deano_data["statistics"]["EMAIL_ADDRESS"] >= 1
    assert deano_data["statistics"]["US_SSN"] >= 1


@pytest.mark.asyncio
async def test_anonymization_endpoints_with_vault(test_client):
    """Test that anonymization endpoints now support vault data."""
    # Test Azure DI endpoint
    azure_di_json = {
        "content": "Contact John Smith at john.smith@example.com",
        "pages": [],
        "paragraphs": []
    }
    
    response = test_client.post(
        "/anonymization/anonymize-azure-di",
        json={
            "azure_di_json": azure_di_json,
            "config": {
                "entity_types": ["PERSON", "EMAIL_ADDRESS"]
            }
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "vault_data" in data
    assert len(data["vault_data"]) > 0
    
    # Test with existing vault data
    response2 = test_client.post(
        "/anonymization/anonymize-azure-di",
        json={
            "azure_di_json": azure_di_json,
            "vault_data": data["vault_data"],
            "config": {
                "entity_types": ["PERSON", "EMAIL_ADDRESS"]
            }
        }
    )
    
    assert response2.status_code == 200
    
    # Test markdown endpoint
    response3 = test_client.post(
        "/anonymization/anonymize-markdown",
        json={
            "markdown_text": "# Contact\n\nEmail John Smith at john.smith@example.com",
            "config": {
                "entity_types": ["PERSON", "EMAIL_ADDRESS"]
            }
        }
    )
    
    assert response3.status_code == 200
    data3 = response3.json()
    assert "vault_data" in data3


if __name__ == "__main__":
    # Run the tests that don't require a test client
    print("Testing vault serialization...")
    test_serialize_deserialize_vault()
    print("✓ Vault serialization works correctly")
    
    print("\nTesting deanonymization function...")
    test_deanonymize_text_with_vault()
    print("✓ Deanonymization works correctly")
    
    print("\nTesting date offset consistency...")
    test_consistent_date_offset()
    print("✓ Date offset consistency works correctly")
    
    print("\nAll manual tests passed!")
    print("\nTo run the full test suite with API endpoints, use: pytest tests/test_pseudonymization.py")