"""
PII Anonymization API endpoint for generating safe test data from Azure DI JSON.

Uses LLM-Guard with AI4Privacy BERT model for accurate PII detection and anonymization.
Implements security-focused design with random data generation and session isolation.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import json
from datetime import timedelta
import random
import secrets
from dateutil import parser as date_parser

from llm_guard.input_scanners import Anonymize
from llm_guard.input_scanners.anonymize_helpers import DISTILBERT_AI4PRIVACY_v2_CONF
from llm_guard.vault import Vault

from faker import Faker
import logging

# Import pattern registry for custom PII patterns
from .pattern_registry import get_patterns_by_sets, merge_custom_patterns, get_replacement_for_pattern

# Configure logging
logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(tags=["anonymization"])

# Initialize Faker with random seed for security
fake = Faker()  # Uses random seed for unpredictable anonymization

# Default entity types for PII detection
# LLM-Guard AI4Privacy supports 54 PII types - we can specify a subset or use all
DEFAULT_ENTITY_TYPES = [
    "PERSON", "DATE_TIME", "LOCATION", "PHONE_NUMBER", 
    "EMAIL_ADDRESS", "US_SSN", "MEDICAL_LICENSE"
]


class AnonymizationConfig(BaseModel):
    """Configuration for anonymization process."""
    anonymize_all_strings: bool = Field(default=True, description="Anonymize all string fields (True) or only known PII fields (False)")
    entity_types: List[str] = Field(
        default_factory=lambda: DEFAULT_ENTITY_TYPES.copy(),
        description="Entity types to anonymize"
    )
    date_shift_days: int = Field(default=365, description="Maximum days to shift dates")
    # Note: consistent_replacements is now always True for better security and user experience
    score_threshold: float = Field(default=0.5, ge=0.0, le=1.0, description="Minimum confidence score for entity detection")
    return_decision_process: bool = Field(default=False, description="Include detailed detection reasoning")
    pattern_sets: List[str] = Field(default_factory=list, description="Enable pattern sets: 'legal', 'medical'")
    custom_patterns: List[Dict[str, Any]] = Field(default_factory=list, description="Custom regex patterns for domain-specific PII")


class AnonymizationRequest(BaseModel):
    """Request body for unified anonymization endpoint."""
    content: str = Field(..., description="Markdown text to anonymize")
    config: AnonymizationConfig = Field(default_factory=AnonymizationConfig)
    vault_data: Optional[Dict[str, Any]] = Field(None, description="Previous vault data for consistent anonymization across requests")


class AnonymizationResponse(BaseModel):
    """Response from anonymization endpoint."""
    anonymized_content: str = Field(..., description="Anonymized markdown text")
    statistics: Dict[str, int] = Field(..., description="Count of anonymized entities by type")
    vault_data: Dict[str, Any] = Field(..., description="Vault data containing anonymization mappings for stateless operation")






# Global scanner (initialized on first use)
# Note: In production, we create new scanners per request for session isolation
global_scanner: Optional[Anonymize] = None


def serialize_vault_v2(vault_mappings: Dict[str, str], date_offset: int, total_files: int = 1) -> Dict[str, Any]:
    """Serialize vault to v2.0 format."""
    from datetime import datetime
    return {
        "version": "2.0",
        "created": datetime.now().isoformat(),
        "metadata": {
            "date_offset": date_offset,
            "total_files": total_files
        },
        "mappings": [[replacement, original] for original, replacement in vault_mappings.items()]
    }


def deserialize_vault_v2(vault_data: Optional[Dict[str, Any]]) -> tuple[Vault, Optional[int], Dict[str, str]]:
    """Deserialize v2.0 vault data.
    
    Returns:
        tuple: (vault, date_offset, mappings_dict)
    """
    vault = Vault()
    date_offset = None
    mappings = {}
    
    if not vault_data:
        return vault, date_offset, mappings
    
    # Handle v2.0 format
    if isinstance(vault_data, dict) and vault_data.get("version") == "2.0":
        # Extract metadata
        metadata = vault_data.get("metadata", {})
        date_offset = metadata.get("date_offset")
        
        # Extract mappings
        for mapping in vault_data.get("mappings", []):
            if len(mapping) == 2:
                replacement, original = mapping
                mappings[original] = replacement
                # For LLM-Guard compatibility, we need placeholders in vault
                # We'll reconstruct them when scanning
    else:
        # Handle legacy format (list of lists)
        if isinstance(vault_data, list):
            for entry in vault_data:
                if len(entry) != 2:
                    continue
                    
                placeholder, original = entry
                
                # Handle metadata entries
                if placeholder == "_date_offset":
                    try:
                        date_offset = int(original)
                    except ValueError:
                        logger.warning(f"Invalid date offset value: {original}")
                else:
                    # Regular vault entry
                    vault.append((placeholder, original))
    
    return vault, date_offset, mappings



def create_anonymizer(config: AnonymizationConfig, vault_data: Optional[Dict[str, Any]] = None) -> tuple[Anonymize, Vault, Optional[int], Dict[str, str]]:
    """Create LLM-Guard anonymizer with AI4Privacy model.
    
    Returns a new scanner, vault, date_offset, and mappings for session isolation.
    If vault_data is provided, initializes vault with previous anonymization mappings
    and extracts any metadata like date_offset.
    """
    # Deserialize vault data if provided
    vault, date_offset, mappings = deserialize_vault_v2(vault_data)
    
    try:
        # Default entity types used by LLM-Guard when entity_types is None
        DEFAULT_LLM_GUARD_ENTITIES = [
            'CREDIT_CARD', 'CRYPTO', 'EMAIL_ADDRESS', 'IBAN_CODE', 
            'IP_ADDRESS', 'PERSON', 'PHONE_NUMBER', 'US_SSN', 
            'US_BANK_NUMBER', 'CREDIT_CARD_RE', 'UUID', 
            'EMAIL_ADDRESS_RE', 'US_SSN_RE'
        ]
        
        # Get custom patterns if specified
        regex_patterns = None
        all_entity_types = config.entity_types
        
        if config.pattern_sets or config.custom_patterns:
            builtin_patterns = get_patterns_by_sets(config.pattern_sets)
            regex_patterns = merge_custom_patterns(builtin_patterns, config.custom_patterns)
            
            # Extract custom entity types from patterns
            custom_entity_types = [p["name"] for p in regex_patterns]
            
            # Handle entity types configuration
            if config.entity_types is None:
                # If None, we want to use defaults + custom
                all_entity_types = DEFAULT_LLM_GUARD_ENTITIES + custom_entity_types
            elif len(config.entity_types) == 0:
                # If empty list, user wants ONLY custom patterns
                all_entity_types = custom_entity_types
            else:
                # If specific types listed, merge with custom types
                all_entity_types = list(set(config.entity_types + custom_entity_types))
        
        # Use AI4Privacy model with 54 PII types + custom patterns
        scanner = Anonymize(
            vault=vault,
            recognizer_conf=DISTILBERT_AI4PRIVACY_v2_CONF,
            threshold=config.score_threshold,
            use_faker=False,  # Disable faker to get placeholder tokens for consistent replacement
            entity_types=all_entity_types,
            regex_patterns=regex_patterns,  # Add custom regex patterns
            language="en"
        )
        
        logger.info("✅ LLM-Guard scanner created with AI4Privacy model")
        if regex_patterns:
            logger.info(f"✅ Added {len(regex_patterns)} custom regex patterns")
            for pattern in regex_patterns:
                logger.debug(f"  - Pattern: {pattern['name']} with expressions: {pattern['expressions']}")
        if all_entity_types:
            logger.info(f"✅ Using entity types: {all_entity_types}")
        else:
            logger.info("✅ Using all default entity types + custom patterns")
        return scanner, vault, date_offset, mappings
        
    except Exception as e:
        logger.error(f"Failed to create LLM-Guard scanner: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create LLM-Guard scanner: {str(e)}")


def apply_consistent_faker_replacements(text: str, vault: Vault, config: AnonymizationConfig, existing_mappings: Dict[str, str], date_offset: Optional[int] = None) -> tuple[str, Dict[str, int], Dict[str, Any]]:
    """
    Post-process LLM-Guard output to replace placeholders with consistent faker values.
    
    Args:
        text: Text with [REDACTED_ENTITY_TYPE_N] placeholders from LLM-Guard
        vault: Vault containing existing mappings
        config: Anonymization configuration
        date_offset: Existing date offset for consistency
        
    Returns:
        tuple: (processed_text, statistics, vault_mappings_dict)
    """
    import re
    
    # Create mappings dict for v2.0 vault structure
    vault_mappings = {}
    statistics = {}
    result_text = text
    
    # Use provided existing mappings
    current_mappings = existing_mappings.copy()
    
    # Find all placeholders in the text
    placeholder_pattern = r'\[REDACTED_([A-Z_]+)_(\d+)\]'
    placeholders = re.findall(placeholder_pattern, text)
    
    # Get unique placeholders to process
    unique_placeholders = list(set(placeholders))
    
    # Process each unique placeholder
    for entity_type, index in unique_placeholders:
        placeholder = f"[REDACTED_{entity_type}_{index}]"
        
        # Get the original value from vault
        original_value = None
        for vault_placeholder, vault_original in vault.get():
            if vault_placeholder == placeholder:
                original_value = vault_original
                break
        
        if not original_value:
            # This shouldn't happen with LLM-Guard, but handle gracefully
            logger.warning(f"No original value found for placeholder: {placeholder}")
            continue
        
        # Check if we already have a replacement for this value
        if original_value in current_mappings:
            replacement = current_mappings[original_value]
        else:
            # Generate new replacement based on entity type
            replacement = generate_faker_replacement(entity_type, original_value, config, date_offset)
            current_mappings[original_value] = replacement
        
        # Replace all occurrences of this placeholder
        result_text = result_text.replace(placeholder, replacement)
        
        # Update statistics
        count = text.count(placeholder)
        statistics[entity_type] = statistics.get(entity_type, 0) + count
        
        # Add to vault mappings for v2.0 structure
        vault_mappings[original_value] = replacement
    
    return result_text, statistics, vault_mappings


def generate_faker_replacement(entity_type: str, original_value: str, config: AnonymizationConfig, date_offset: Optional[int] = None) -> str:
    """Generate a faker replacement for a given entity type and value."""
    if entity_type == "PERSON":
        return fake.name()
    elif entity_type == "DATE_TIME" or entity_type == "DATE":
        # Apply consistent date shifting
        if date_offset is None:
            date_offset = random.randint(-config.date_shift_days, config.date_shift_days)
        
        try:
            parsed_date = date_parser.parse(original_value, fuzzy=True)
            shifted_date = parsed_date + timedelta(days=date_offset)
            
            # Format based on original format hints
            if ":" in original_value and len(original_value) > 10:
                return shifted_date.strftime("%B %d, %Y at %I:%M %p")
            elif "/" in original_value:
                return shifted_date.strftime("%m/%d/%Y")
            elif "-" in original_value and len(original_value) == 10:
                return shifted_date.strftime("%Y-%m-%d")
            else:
                return shifted_date.strftime("%B %d, %Y")
        except Exception:
            return fake.date_this_year().strftime("%B %d, %Y")
    elif entity_type == "LOCATION":
        return fake.city()
    elif entity_type == "PHONE_NUMBER":
        return fake.phone_number()
    elif entity_type == "EMAIL_ADDRESS" or entity_type == "EMAIL":
        return fake.email()
    elif entity_type == "US_SSN" or entity_type == "SSN":
        area = secrets.randbelow(899) + 100
        group = secrets.randbelow(99) + 1
        serial = secrets.randbelow(9999) + 1
        return f"{area:03d}-{group:02d}-{serial:04d}"
    elif entity_type == "MEDICAL_LICENSE":
        return f"MD{secrets.randbelow(999999):06d}"
    else:
        # Check for custom pattern replacement
        custom_replacement = get_replacement_for_pattern(entity_type, original_value)
        if custom_replacement != f"[REDACTED_{entity_type}]":
            return custom_replacement
        else:
            # Default: use a generic faker method
            return f"ANON_{entity_type}_{secrets.token_hex(4).upper()}"




def generate_session_shift(date_shift_days: int, existing_offset: Optional[int] = None) -> int:
    """Generate or return existing date shift for the session.
    
    Args:
        date_shift_days: Maximum days to shift dates
        existing_offset: Previously generated offset from vault
        
    Returns:
        Date offset in days (positive or negative)
    """
    if existing_offset is not None:
        return existing_offset
        
    # Generate new offset without noise for consistency
    # Use a fixed range for predictable behavior
    return random.randint(-date_shift_days, date_shift_days)







def extract_statistics_from_vault(vault: Vault) -> Dict[str, int]:
    """Extract entity statistics from vault.
    
    Note: LLM-Guard's vault doesn't store entity types directly,
    so we infer them from the replacement patterns.
    """
    stats = {}
    
    for replacement, original in vault.get():
        # Check if it's a custom entity type with pattern [REDACTED_ENTITY_TYPE_N]
        if replacement.startswith('[REDACTED_') and replacement.endswith(']'):
            # Extract entity type from pattern like [REDACTED_BATES_NUMBER_1]
            parts = replacement[10:-1].rsplit('_', 1)  # Remove [REDACTED_ and ], split from right
            if len(parts) == 2 and parts[1].isdigit():
                entity_type = parts[0]
            else:
                entity_type = 'OTHER'
        # Infer standard entity types from replacement pattern
        elif '@' in replacement:
            entity_type = 'EMAIL_ADDRESS'
        elif len(replacement) == 11 and replacement[3] == '-' and replacement[6] == '-':
            entity_type = 'US_SSN'
        elif len(replacement) == 10 and replacement.count('-') == 2:
            entity_type = 'DATE_TIME'
        elif replacement.replace('-', '').replace(' ', '').replace('(', '').replace(')', '').isdigit() and len(replacement) >= 10:
            entity_type = 'PHONE_NUMBER'
        else:
            # Check if it looks like a name (title case words)
            words = replacement.split()
            if len(words) >= 2 and all(w[0].isupper() for w in words if w):
                entity_type = 'PERSON'
            else:
                entity_type = 'OTHER'
        
        stats[entity_type] = stats.get(entity_type, 0) + 1
    
    return stats


def anonymize_text_with_consistent_replacements(text: str, scanner: Anonymize,
                                               vault: Vault,
                                               config: AnonymizationConfig,
                                               existing_mappings: Dict[str, str],
                                               date_offset: Optional[int] = None) -> tuple[str, Dict[str, int], Dict[str, Any]]:
    """Anonymize text using LLM-Guard with consistent faker replacements."""
    if not text or not isinstance(text, str):
        return text, {}, {}
    
    # Step 1: LLM-Guard anonymization (with use_faker=False to get placeholders)
    sanitized_text, is_valid, risk_score = scanner.scan(text)
    
    # Step 2: Apply consistent faker replacements
    processed_text, statistics, vault_mappings = apply_consistent_faker_replacements(
        sanitized_text, vault, config, existing_mappings, date_offset
    )
    
    return processed_text, statistics, vault_mappings






@router.post("/anonymize", response_model=AnonymizationResponse)
async def anonymize_endpoint(request: AnonymizationRequest):
    """
    Anonymize markdown text with consistent, reversible PII replacement.
    
    This endpoint:
    1. Detects PII using LLM-Guard with AI4Privacy BERT model (54 PII types)
    2. Replaces PII with consistent fake data (same person = same fake name)
    3. Always creates a reversible vault for restoration
    4. Preserves markdown formatting (headers, lists, code blocks, etc.)
    5. Supports stateless operation by accepting/returning vault data
    """
    try:
        # Create scanner with optional vault data for stateless operation
        scanner, vault, existing_date_offset, existing_mappings = create_anonymizer(request.config, request.vault_data)
        
        # Generate or use existing date shift if enabled
        date_shift = None
        if request.config.date_shift_days:
            date_shift = generate_session_shift(request.config.date_shift_days, existing_date_offset)
        
        # Anonymize the text with consistent replacements
        anonymized_text, statistics, vault_mappings = anonymize_text_with_consistent_replacements(
            request.content,
            scanner,
            vault,
            request.config,
            existing_mappings,
            date_shift
        )
        
        # Create v2.0 vault structure
        from datetime import datetime
        vault_v2 = {
            "version": "2.0",
            "created": datetime.now().isoformat(),
            "metadata": {
                "date_offset": date_shift if date_shift is not None else 0,
                "total_files": 1
            },
            "mappings": [[replacement, original] for original, replacement in vault_mappings.items()]
        }
        
        return AnonymizationResponse(
            anonymized_content=anonymized_text,
            statistics=statistics,
            vault_data=vault_v2
        )
        
    except Exception as e:
        logger.error(f"Anonymization failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Anonymization failed: {str(e)}")




@router.get("/health")
async def health_check():
    """Check if anonymization service is ready."""
    try:
        # Test scanner creation with default config
        test_config = AnonymizationConfig()
        scanner, vault, _ = create_anonymizer(test_config)
        
        return {
            "status": "healthy",
            "service": "anonymization",
            "engines_initialized": scanner is not None and vault is not None,
            "recognizers": "LLM-Guard with AI4Privacy model (54 PII types)",
            "model": "Isotonic/distilbert_finetuned_ai4privacy_v2"
        }
    except Exception as e:
        return {
            "status": "unhealthy", 
            "service": "anonymization",
            "error": str(e)
        }