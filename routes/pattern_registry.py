"""
Registry of custom regex patterns for domain-specific PII detection.

This module provides predefined pattern sets for legal, medical, and other
domain-specific identifiers that aren't covered by the standard AI4Privacy model.
"""

from typing import Dict, List, Any

# Pattern structure for LLM-Guard
# DefaultRegexPatterns = {
#     "name": str,              # Entity type name
#     "expressions": list[str], # List of regex patterns
#     "examples": list[str],    # Example matches
#     "context": list[str],     # Context words to help detection
#     "score": float,           # Confidence score (0.0-1.0)
#     "languages": list[str]    # Supported languages
# }

LEGAL_PATTERNS = [
    {
        "name": "BATES_NUMBER",
        "expressions": [
            r"\b(BATES[-_\s]?\d{6,})\b",  # BATES-001234, BATES_001234
            r"\b([A-Z]{2,4}[-_\s]?\d{6,})\b",  # DEF00012345, ABC_123456
            r"\b(CONFIDENTIAL[-_\s]?\d{6,})\b",  # CONFIDENTIAL-001234
        ],
        "examples": [
            "BATES-001234",
            "DEF00012345",
            "ABC_123456",
            "CONFIDENTIAL-001234"
        ],
        "context": ["page", "document", "exhibit", "production"],
        "score": 0.9,
        "languages": ["en"]
    },
    {
        "name": "CASE_NUMBER",
        "expressions": [
            r"\b(\d{1,2}:\d{2}-[a-z]{2}-\d{5,})\b",  # 1:23-cv-45678
            r"\b(Case\s+No\.?\s*[:\s]?\s*\d{1,2}:\d{2}-[a-z]{2}-\d{5,})\b",  # Case No. 1:23-cv-45678
            r"\b(\d{4}-[A-Z]{2,3}-\d{5,})\b",  # 2024-CR-00156
            r"\b(CV-\d{4}-\d{4,})\b",  # CV-2023-1234
            r"\b(Docket\s+No\.?\s*[:\s]?\s*\d{2,}-\d{4,})\b",  # Docket No. 12-3456
        ],
        "examples": [
            "1:23-cv-45678",
            "Case No. 2:24-cr-00123",
            "2024-CR-00156",
            "CV-2023-1234",
            "Docket No. 12-3456"
        ],
        "context": ["case", "docket", "matter", "court", "litigation"],
        "score": 0.9,
        "languages": ["en"]
    },
    {
        "name": "COURT_FILING",
        "expressions": [
            r"\b(ECF\s+No\.?\s*\d+)\b",  # ECF No. 123
            r"\b(Doc\.\s*\d+)\b",  # Doc. 45
            r"\b(Exhibit\s+[A-Z]\d*)\b",  # Exhibit A1
            r"\b(Filing\s+ID\s*[:#]?\s*\d+)\b",  # Filing ID: 12345
        ],
        "examples": [
            "ECF No. 123",
            "Doc. 45",
            "Exhibit A1",
            "Filing ID: 12345"
        ],
        "context": ["filing", "document", "exhibit", "attachment"],
        "score": 0.8,
        "languages": ["en"]
    }
]

MEDICAL_PATTERNS = [
    {
        "name": "MEDICAL_RECORD_NUMBER",
        "expressions": [
            r"\b(MRN\s*[:#]?\s*\d{6,})\b",  # MRN: 12345678
            r"\b(MR\s*#\s*\d{6,})\b",  # MR# 123456
            r"\b(Medical\s+Record\s+Number\s*[:#]?\s*\d{6,})\b",
            r"\b(Patient\s+ID\s*[:#]?\s*\d{6,})\b",  # Patient ID: 123456
        ],
        "examples": [
            "MRN: 12345678",
            "MR# 123456",
            "Medical Record Number: 1234567",
            "Patient ID: 987654"
        ],
        "context": ["patient", "medical", "record", "hospital", "clinic"],
        "score": 0.95,
        "languages": ["en"]
    },
    {
        "name": "INSURANCE_ID",
        "expressions": [
            r"\b(Member\s+ID\s*[:#]?\s*[A-Z0-9]{8,})\b",  # Member ID: ABC123456
            r"\b(Policy\s+Number\s*[:#]?\s*[A-Z0-9-]+)\b",  # Policy Number: 123-456-789
            r"\b(Claim\s+#\s*[A-Z0-9]+)\b",  # Claim # 123456ABC
        ],
        "examples": [
            "Member ID: ABC123456",
            "Policy Number: 123-456-789",
            "Claim # 123456ABC"
        ],
        "context": ["insurance", "claim", "coverage", "benefits"],
        "score": 0.85,
        "languages": ["en"]
    },
    {
        "name": "PROVIDER_NUMBER",
        "expressions": [
            r"\b(NPI\s*[:#]?\s*\d{10})\b",  # NPI: 1234567890
            r"\b(DEA\s*[:#]?\s*[A-Z]{2}\d{7})\b",  # DEA: AB1234567
            r"\b(Provider\s+ID\s*[:#]?\s*\d{6,})\b",  # Provider ID: 123456
        ],
        "examples": [
            "NPI: 1234567890",
            "DEA: AB1234567",
            "Provider ID: 123456"
        ],
        "context": ["provider", "physician", "doctor", "practitioner"],
        "score": 0.9,
        "languages": ["en"]
    }
]

# Pattern sets that can be enabled via API
PATTERN_SETS: Dict[str, List[Dict[str, Any]]] = {
    "legal": LEGAL_PATTERNS,
    "medical": MEDICAL_PATTERNS,
}

# All available patterns (for reference)
ALL_PATTERNS = LEGAL_PATTERNS + MEDICAL_PATTERNS


def get_patterns_by_sets(pattern_sets: List[str]) -> List[Dict[str, Any]]:
    """
    Get patterns for the specified pattern sets.
    
    Args:
        pattern_sets: List of pattern set names (e.g., ["legal", "medical"])
        
    Returns:
        List of pattern dictionaries for LLM-Guard
    """
    patterns = []
    for set_name in pattern_sets:
        if set_name in PATTERN_SETS:
            patterns.extend(PATTERN_SETS[set_name])
    return patterns


def merge_custom_patterns(
    builtin_patterns: List[Dict[str, Any]], 
    custom_patterns: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Merge built-in patterns with user-provided custom patterns.
    
    Args:
        builtin_patterns: Patterns from pattern sets
        custom_patterns: User-provided custom patterns
        
    Returns:
        Merged list of patterns
    """
    # Validate custom patterns have required fields
    for pattern in custom_patterns:
        if not all(key in pattern for key in ["name", "expressions"]):
            raise ValueError(f"Custom pattern missing required fields: {pattern}")
        
        # Set defaults for optional fields
        pattern.setdefault("examples", [])
        pattern.setdefault("context", [])
        pattern.setdefault("score", 0.8)
        pattern.setdefault("languages", ["en"])
    
    # Combine patterns
    return builtin_patterns + custom_patterns


def get_replacement_for_pattern(entity_type: str, original: str) -> str:
    """
    Generate format-preserving replacements for custom entity types.
    
    Args:
        entity_type: The custom entity type (e.g., "BATES_NUMBER")
        original: The original value to replace
        
    Returns:
        A replacement that preserves the format
    """
    import random
    import re
    
    if entity_type == "BATES_NUMBER":
        # Extract prefix and number
        match = re.match(r'([A-Z]+[-_\s]?)(\d+)', original)
        if match:
            prefix, number = match.groups()
            # Generate new number with same length
            new_number = str(random.randint(10**(len(number)-1), 10**len(number)-1))
            return f"{prefix}{new_number}"
    
    elif entity_type == "CASE_NUMBER":
        # Preserve case number format
        if ":" in original and "-" in original:
            # Federal format: 1:23-cv-45678
            parts = re.match(r'(\d+):(\d+)-([a-z]+)-(\d+)', original)
            if parts:
                court = random.randint(1, 9)
                year = random.randint(20, 24)
                case_num = random.randint(10000, 99999)
                return f"{court}:{year}-{parts.group(3)}-{case_num}"
        elif re.match(r'\d{4}-[A-Z]{2,3}-\d+', original):
            # State format: 2024-CR-00156
            parts = re.match(r'(\d{4})-([A-Z]+)-(\d+)', original)
            if parts:
                year = random.randint(2020, 2024)
                case_num = str(random.randint(100, 99999)).zfill(len(parts.group(3)))
                return f"{year}-{parts.group(2)}-{case_num}"
    
    elif entity_type == "MEDICAL_RECORD_NUMBER":
        # Extract number and preserve length
        numbers = re.findall(r'\d+', original)
        if numbers:
            num_len = len(numbers[0])
            new_num = str(random.randint(10**(num_len-1), 10**num_len-1))
            return re.sub(r'\d+', new_num, original, count=1)
    
    # Default: generic replacement
    return f"[REDACTED_{entity_type}]"