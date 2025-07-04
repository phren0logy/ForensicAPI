"""
Test custom pattern detection for legal and forensic documents.
"""

import pytest
from typing import Dict, List
import sys
sys.path.append('..')
from routes.anonymization import AnonymizationConfig, create_anonymizer, anonymize_text_with_date_shift
from routes.pattern_registry import LEGAL_PATTERNS, MEDICAL_PATTERNS, get_replacement_for_pattern


def test_legal_pattern_detection():
    """Test detection of legal identifiers."""
    text = """
    Please refer to document BATES-001234 in case 1:23-cv-45678.
    The filing can be found at ECF No. 123, which references 
    DEF00012345 and Docket No. 12-3456.
    """
    
    config = AnonymizationConfig(
        pattern_sets=["legal"],
        entity_types=[],  # Only use custom patterns
        date_shift_days=0
    )
    
    scanner, vault, _ = create_anonymizer(config)
    
    # Anonymize the text
    result, stats, _ = anonymize_text_with_date_shift(text, scanner, vault, config, None)
    
    # Check that patterns were detected
    assert "BATES-001234" not in result
    assert "1:23-cv-45678" not in result
    assert "DEF00012345" not in result
    assert "ECF No. 123" not in result
    
    # Check statistics
    print(f"Detected entities: {stats}")
    assert stats.get("BATES_NUMBER", 0) >= 2  # BATES-001234 and DEF00012345
    assert stats.get("CASE_NUMBER", 0) >= 2  # 1:23-cv-45678 and Docket No. 12-3456
    assert stats.get("COURT_FILING", 0) >= 1  # ECF No. 123


def test_medical_pattern_detection():
    """Test detection of medical identifiers."""
    text = """
    Patient ID: 123456 was admitted with MRN: 87654321.
    Insurance Member ID: ABC123456 covers this visit.
    Provider NPI: 1234567890 prescribed medication.
    """
    
    config = AnonymizationConfig(
        pattern_sets=["medical"],
        entity_types=[],
        date_shift_days=0
    )
    
    scanner, vault, _ = create_anonymizer(config)
    
    # Anonymize the text
    result, stats, _ = anonymize_text_with_date_shift(text, scanner, vault, config, None)
    
    # Check that patterns were detected
    assert "123456" not in result or "Patient ID: 123456" not in result
    assert "87654321" not in result
    assert "ABC123456" not in result
    assert "1234567890" not in result
    
    # Check statistics
    print(f"Detected entities: {stats}")
    assert stats.get("MEDICAL_RECORD_NUMBER", 0) >= 2
    assert stats.get("INSURANCE_ID", 0) >= 1
    assert stats.get("PROVIDER_NUMBER", 0) >= 1


def test_custom_pattern_api():
    """Test custom patterns via API."""
    text = "The tracking number is TRACK-2024-001 for order #ORD-5678."
    
    custom_patterns = [
        {
            "name": "TRACKING_NUMBER",
            "expressions": [r"\bTRACK-\d{4}-\d{3}\b"],
            "examples": ["TRACK-2024-001"],
            "context": ["tracking", "shipment"],
            "score": 0.9,
            "languages": ["en"]
        },
        {
            "name": "ORDER_NUMBER",
            "expressions": [r"\b#?ORD-\d{4}\b"],
            "examples": ["ORD-5678", "#ORD-1234"],
        }
    ]
    
    config = AnonymizationConfig(
        custom_patterns=custom_patterns,
        entity_types=[],
        date_shift_days=0
    )
    
    scanner, vault, _ = create_anonymizer(config)
    
    # Anonymize the text
    result, stats, _ = anonymize_text_with_date_shift(text, scanner, vault, config, None)
    
    # Check that patterns were detected
    assert "TRACK-2024-001" not in result
    assert "ORD-5678" not in result
    
    print(f"Result: {result}")
    print(f"Stats: {stats}")


def test_format_preserving_replacements():
    """Test that replacements preserve format."""
    
    # Test Bates number replacement
    bates_replacement = get_replacement_for_pattern("BATES_NUMBER", "BATES-001234")
    assert bates_replacement.startswith("BATES-")
    assert len(bates_replacement) == len("BATES-001234")
    
    # Test case number replacement
    case_replacement = get_replacement_for_pattern("CASE_NUMBER", "1:23-cv-45678")
    assert ":" in case_replacement
    assert "-cv-" in case_replacement
    
    # Test medical record replacement
    mrn_replacement = get_replacement_for_pattern("MEDICAL_RECORD_NUMBER", "MRN: 12345678")
    assert mrn_replacement.startswith("MRN: ")
    assert len(mrn_replacement) == len("MRN: 12345678")


def test_combined_ai_and_patterns():
    """Test combining AI4Privacy with custom patterns."""
    text = """
    John Smith (email: john@example.com) filed case 1:23-cv-45678.
    His medical record MRN: 12345678 shows treatment on 2024-01-15.
    Reference document BATES-001234.
    """
    
    config = AnonymizationConfig(
        pattern_sets=["legal", "medical"],
        entity_types=["PERSON", "EMAIL_ADDRESS", "DATE_TIME"],
        date_shift_days=0
    )
    
    scanner, vault, _ = create_anonymizer(config)
    
    # Anonymize the text
    result, stats, _ = anonymize_text_with_date_shift(text, scanner, vault, config, None)
    
    # Check both AI and pattern detection worked
    assert "John Smith" not in result
    assert "john@example.com" not in result
    assert "1:23-cv-45678" not in result
    assert "12345678" not in result
    assert "BATES-001234" not in result
    
    # Should have both standard and custom entities
    print(f"Combined detection stats: {stats}")
    assert "PERSON" in stats
    assert "EMAIL_ADDRESS" in stats
    assert any(key in stats for key in ["BATES_NUMBER", "CASE_NUMBER", "MEDICAL_RECORD_NUMBER"])


if __name__ == "__main__":
    print("Testing legal patterns...")
    test_legal_pattern_detection()
    print("\nTesting medical patterns...")
    test_medical_pattern_detection()
    print("\nTesting custom pattern API...")
    test_custom_pattern_api()
    print("\nTesting format-preserving replacements...")
    test_format_preserving_replacements()
    print("\nTesting combined AI and patterns...")
    test_combined_ai_and_patterns()
    print("\nAll tests completed!")