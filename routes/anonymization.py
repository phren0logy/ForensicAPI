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
    """Request body for anonymization endpoint."""
    azure_di_json: Dict[str, Any] = Field(..., description="Raw Azure DI extraction output")
    config: AnonymizationConfig = Field(default_factory=AnonymizationConfig)
    vault_data: Optional[List[List[str]]] = Field(None, description="Previous vault data for consistent anonymization across requests")


class AnonymizationResponse(BaseModel):
    """Response from anonymization endpoint."""
    anonymized_json: Dict[str, Any] = Field(..., description="Anonymized Azure DI JSON")
    statistics: Dict[str, int] = Field(..., description="Count of anonymized entities by type")
    vault_data: List[List[str]] = Field(..., description="Vault data containing anonymization mappings for stateless operation")


class MarkdownAnonymizationRequest(BaseModel):
    """Request body for markdown anonymization endpoint."""
    markdown_text: str = Field(..., description="Markdown text to anonymize")
    config: AnonymizationConfig = Field(default_factory=AnonymizationConfig)
    vault_data: Optional[List[List[str]]] = Field(None, description="Previous vault data for consistent anonymization across requests")


class MarkdownAnonymizationResponse(BaseModel):
    """Response from markdown anonymization endpoint."""
    anonymized_text: str = Field(..., description="Anonymized markdown text")
    statistics: Dict[str, int] = Field(..., description="Count of anonymized entities by type")
    decision_process: Optional[List[Dict]] = Field(None, description="Detection reasoning if requested")
    vault_data: List[List[str]] = Field(..., description="Vault data containing anonymization mappings for stateless operation")


class PseudonymizationRequest(BaseModel):
    """Request body for pseudonymization endpoint."""
    text: str = Field(..., description="Text to pseudonymize")
    vault_data: Optional[List[List[str]]] = Field(None, description="Previous vault data for consistent pseudonymization across documents")
    config: AnonymizationConfig = Field(default_factory=AnonymizationConfig)


class PseudonymizationResponse(BaseModel):
    """Response from pseudonymization endpoint."""
    pseudonymized_text: str = Field(..., description="Pseudonymized text")
    statistics: Dict[str, int] = Field(..., description="Count of pseudonymized entities by type")
    vault_data: List[List[str]] = Field(..., description="Updated vault data with all mappings")


class DeanonymizationRequest(BaseModel):
    """Request body for deanonymization endpoint."""
    text: str = Field(..., description="Text to deanonymize")
    vault_data: List[List[str]] = Field(..., description="Vault data containing anonymization mappings")


class DeanonymizationResponse(BaseModel):
    """Response from deanonymization endpoint."""
    deanonymized_text: str = Field(..., description="Deanonymized text with original values restored")
    statistics: Dict[str, int] = Field(..., description="Count of deanonymized entities by type")


# Global scanner (initialized on first use)
# Note: In production, we create new scanners per request for session isolation
global_scanner: Optional[Anonymize] = None


def serialize_vault(vault: Vault, date_offset: Optional[int] = None) -> List[List[str]]:
    """Serialize vault to list of [placeholder, original] pairs with optional metadata."""
    data = []
    
    # Add date offset as metadata if provided
    if date_offset is not None:
        data.append(["_date_offset", str(date_offset)])
    
    # Add all vault entries
    for placeholder, original in vault.get():
        data.append([placeholder, original])
    
    return data


def deserialize_vault(vault_data: Optional[List[List[str]]]) -> tuple[Vault, Optional[int]]:
    """Deserialize vault data and extract metadata.
    
    Returns:
        tuple: (vault, date_offset)
    """
    vault = Vault()
    date_offset = None
    
    if not vault_data:
        return vault, date_offset
    
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
    
    return vault, date_offset



def create_anonymizer(config: AnonymizationConfig, vault_data: Optional[List[List[str]]] = None) -> tuple[Anonymize, Vault, Optional[int]]:
    """Create LLM-Guard anonymizer with AI4Privacy model.
    
    Returns a new scanner, vault, and date_offset for session isolation.
    If vault_data is provided, initializes vault with previous anonymization mappings
    and extracts any metadata like date_offset.
    """
    # Deserialize vault data if provided
    vault, date_offset = deserialize_vault(vault_data)
    
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
            use_faker=True,  # Enable Faker for all entities (Note: limits consistency with vault)
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
        return scanner, vault, date_offset
        
    except Exception as e:
        logger.error(f"Failed to create LLM-Guard scanner: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create LLM-Guard scanner: {str(e)}")


def get_consistent_replacement(entity_type: str, original_value: str, 
                             date_shift_days: int = 365,
                             replacement_mappings: Dict[str, Dict[str, str]] = None) -> str:
    """Get consistent replacement for a value based on entity type."""
    if replacement_mappings is None:
        replacement_mappings = {}
    
    # Check if we already have a replacement for this value
    if entity_type not in replacement_mappings:
        replacement_mappings[entity_type] = {}
    
    if original_value in replacement_mappings[entity_type]:
        return replacement_mappings[entity_type][original_value]
    
    # Generate new replacement based on entity type
    if entity_type == "PERSON":
        replacement = fake.name()
    elif entity_type == "DATE_TIME":
        # Get or create consistent shift for this session
        if "_date_shift_days" not in replacement_mappings:
            # Add some noise to the shift range for better security
            noise_factor = random.uniform(0.8, 1.2)
            adjusted_days = int(date_shift_days * noise_factor)
            replacement_mappings["_date_shift_days"] = random.randint(-adjusted_days, adjusted_days)
        
        shift_days = replacement_mappings["_date_shift_days"]
        
        try:
            # Parse the original date
            parsed_date = date_parser.parse(original_value, fuzzy=True)
            
            # Apply the shift
            shifted_date = parsed_date + timedelta(days=shift_days)
            
            # Format based on original format hints
            if ":" in original_value and len(original_value) > 10:
                # Likely includes time
                replacement = shifted_date.strftime("%B %d, %Y at %I:%M %p")
            elif "/" in original_value:
                # US format
                replacement = shifted_date.strftime("%m/%d/%Y")
            elif "-" in original_value and len(original_value) == 10:
                # ISO format
                replacement = shifted_date.strftime("%Y-%m-%d")
            else:
                # Default readable format
                replacement = shifted_date.strftime("%B %d, %Y")
        except Exception as e:
            # Fallback to a random date this year
            logger.warning(f"Could not parse date '{original_value}': {e}")
            replacement = fake.date_this_year().strftime("%B %d, %Y")
    elif entity_type == "LOCATION":
        replacement = fake.city()
    elif entity_type == "PHONE_NUMBER":
        replacement = fake.phone_number()
    elif entity_type == "EMAIL_ADDRESS":
        replacement = fake.email()
    elif entity_type == "US_SSN":
        # Use cryptographically secure random for sensitive IDs
        area = secrets.randbelow(899) + 100  # 100-999, avoiding 666
        group = secrets.randbelow(99) + 1     # 01-99
        serial = secrets.randbelow(9999) + 1  # 0001-9999
        replacement = f"{area:03d}-{group:02d}-{serial:04d}"
    elif entity_type == "MEDICAL_LICENSE":
        # Use cryptographically secure random for medical licenses
        replacement = f"MD{secrets.randbelow(999999):06d}"
    else:
        # Check if this is a custom pattern type
        custom_replacement = get_replacement_for_pattern(entity_type, original_value)
        if custom_replacement != f"[REDACTED_{entity_type}]":
            replacement = custom_replacement
        else:
            # Default for unknown types
            replacement = f"[REDACTED_{entity_type}]"
    
    # Store for consistency
    replacement_mappings[entity_type][original_value] = replacement
    return replacement


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


def extract_date_entities_from_vault(vault: Vault) -> List[tuple[str, str]]:
    """Extract date entities from LLM-Guard vault.
    
    Returns list of (replacement, original) tuples for DATE_TIME entities.
    """
    date_entities = []
    
    # Get all tuples from vault
    for replacement, original in vault.get():
        # Check if this looks like a date based on the replacement format
        # LLM-Guard typically replaces dates with YYYY-MM-DD format
        if len(replacement) == 10 and replacement.count('-') == 2:
            try:
                # Verify it's a valid date
                date_parser.parse(replacement)
                date_entities.append((replacement, original))
            except (ValueError, TypeError):
                pass
    
    return date_entities


def apply_date_shifts(text: str, date_entities: List[tuple[str, str]], date_shift: int) -> str:
    """Apply date shifting to preserve temporal relationships."""
    result = text
    
    for faker_date, original_date in date_entities:
        try:
            # Parse the original date
            parsed_date = date_parser.parse(original_date, fuzzy=True)
            
            # Apply the shift
            shifted_date = parsed_date + timedelta(days=date_shift)
            
            # Format based on original format hints
            if ":" in original_date and len(original_date) > 10:
                # Likely includes time
                new_date = shifted_date.strftime("%B %d, %Y at %I:%M %p")
            elif "/" in original_date:
                # US format
                new_date = shifted_date.strftime("%m/%d/%Y")
            elif "-" in original_date and len(original_date) == 10:
                # ISO format
                new_date = shifted_date.strftime("%Y-%m-%d")
            else:
                # Default readable format
                new_date = shifted_date.strftime("%B %d, %Y")
            
            # Replace the faker date with our shifted date
            result = result.replace(faker_date, new_date)
            
        except Exception as e:
            logger.warning(f"Could not shift date '{original_date}': {e}")
    
    return result


def update_vault_with_shifted_dates(vault: Vault, date_entities: List[tuple[str, str]], date_shift: int):
    """Update vault with shifted dates for consistency."""
    # Remove old entries and add updated ones
    for faker_date, original_date in date_entities:
        try:
            # Parse and shift the original date
            parsed_date = date_parser.parse(original_date, fuzzy=True)
            shifted_date = parsed_date + timedelta(days=date_shift)
            
            # Format the shifted date (using ISO format for consistency)
            shifted_str = shifted_date.strftime("%Y-%m-%d")
            
            # Remove the old tuple
            vault.remove((faker_date, original_date))
            
            # Add the new tuple with shifted date as the replacement
            vault.append((shifted_str, original_date))
            
        except Exception as e:
            logger.warning(f"Could not update vault for date '{original_date}': {e}")



def deanonymize_text_with_vault(text: str, vault_data: List[List[str]]) -> tuple[str, Dict[str, int]]:
    """Deanonymize text using vault mappings.
    
    Args:
        text: Text containing pseudonymized values
        vault_data: Vault data with [placeholder, original] mappings
        
    Returns:
        tuple: (deanonymized_text, statistics)
    """
    result = text
    statistics = {}
    
    # Sort by placeholder length (descending) to avoid partial replacements
    sorted_mappings = sorted(vault_data, key=lambda x: len(x[0]) if len(x) == 2 else 0, reverse=True)
    
    for mapping in sorted_mappings:
        if len(mapping) != 2:
            continue
            
        placeholder, original = mapping
        
        # Skip metadata entries
        if placeholder.startswith("_"):
            continue
            
        # Count occurrences before replacement
        count = result.count(placeholder)
        if count > 0:
            # Replace all occurrences
            result = result.replace(placeholder, original)
            
            # Infer entity type for statistics
            # Check if it's a custom entity type with pattern [REDACTED_ENTITY_TYPE_N]
            if placeholder.startswith('[REDACTED_') and placeholder.endswith(']'):
                # Extract entity type from pattern like [REDACTED_BATES_NUMBER_1]
                parts = placeholder[10:-1].rsplit('_', 1)  # Remove [REDACTED_ and ], split from right
                if len(parts) == 2 and parts[1].isdigit():
                    entity_type = parts[0]
                else:
                    entity_type = 'OTHER'
            elif '@' in placeholder:
                entity_type = 'EMAIL_ADDRESS'
            elif len(placeholder) == 11 and placeholder[3] == '-' and placeholder[6] == '-':
                entity_type = 'US_SSN'
            elif len(placeholder) == 10 and placeholder.count('-') == 2:
                entity_type = 'DATE_TIME'
            elif placeholder.replace('-', '').replace(' ', '').replace('(', '').replace(')', '').isdigit() and len(placeholder) >= 10:
                entity_type = 'PHONE_NUMBER'
            else:
                # Check if it looks like a name
                words = placeholder.split()
                if len(words) >= 2 and all(w[0].isupper() for w in words if w):
                    entity_type = 'PERSON'
                else:
                    entity_type = 'OTHER'
            
            statistics[entity_type] = statistics.get(entity_type, 0) + count
    
    return result, statistics


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


def anonymize_text_with_date_shift(text: str, scanner: Anonymize,
                                  vault: Vault,
                                  config: AnonymizationConfig,
                                  date_shift: Optional[int] = None) -> tuple[str, Dict[str, int], Optional[List[Dict]]]:
    """Anonymize text using LLM-Guard with custom date shifting."""
    if not text or not isinstance(text, str):
        return text, {}, None
    
    # Step 1: LLM-Guard anonymization
    sanitized_text, is_valid, risk_score = scanner.scan(text)
    
    # Step 2: Apply custom date shifting if enabled
    if config.date_shift_days and date_shift is not None:
        # Extract date entities from vault
        date_entities = extract_date_entities_from_vault(vault)
        
        if date_entities:
            # Replace LLM-Guard's random dates with shifted dates
            sanitized_text = apply_date_shifts(
                sanitized_text, 
                date_entities, 
                date_shift
            )
            
            # Update vault for consistency
            update_vault_with_shifted_dates(
                vault, 
                date_entities, 
                date_shift
            )
    
    # Step 3: Extract statistics from vault
    statistics = extract_statistics_from_vault(vault)
    
    # Decision process not yet supported with LLM-Guard
    decision_process = None
    
    return sanitized_text, statistics, decision_process


def anonymize_azure_di_json(data: Dict[str, Any], 
                           config: AnonymizationConfig,
                           scanner: Anonymize,
                           vault: Vault,
                           date_shift: Optional[int] = None) -> tuple[Dict[str, Any], Dict[str, int]]:
    """Recursively anonymize Azure DI JSON while preserving structure."""
    if not isinstance(data, dict):
        return data, {}
    
    anonymized = {}
    total_stats = {}
    
    # Fields that commonly contain PII in Azure DI output
    text_fields = {
        "content", "text", "value", "name", "description",
        "title", "subject", "author", "creator", "producer"
    }
    
    for key, value in data.items():
        if isinstance(value, str) and (key in text_fields or config.anonymize_all_strings):
            # Anonymize text field
            anonymized_text, stats, _ = anonymize_text_with_date_shift(
                value, scanner, vault, config, date_shift
            )
            anonymized[key] = anonymized_text
            
            # Merge statistics
            for entity_type, count in stats.items():
                total_stats[entity_type] = total_stats.get(entity_type, 0) + count
                
        elif isinstance(value, list):
            # Recursively process lists
            anonymized_list = []
            for item in value:
                if isinstance(item, dict):
                    anon_item, item_stats = anonymize_azure_di_json(
                        item, config, scanner, vault, date_shift
                    )
                    anonymized_list.append(anon_item)
                    # Merge statistics
                    for entity_type, count in item_stats.items():
                        total_stats[entity_type] = total_stats.get(entity_type, 0) + count
                elif isinstance(item, str):
                    # Check if it might contain PII
                    anon_text, stats, _ = anonymize_text_with_date_shift(
                        item, scanner, vault, config, date_shift
                    )
                    anonymized_list.append(anon_text)
                    for entity_type, count in stats.items():
                        total_stats[entity_type] = total_stats.get(entity_type, 0) + count
                else:
                    anonymized_list.append(item)
            anonymized[key] = anonymized_list
            
        elif isinstance(value, dict):
            # Recursively process nested objects
            anon_dict, dict_stats = anonymize_azure_di_json(
                value, config, scanner, vault, date_shift
            )
            anonymized[key] = anon_dict
            # Merge statistics
            for entity_type, count in dict_stats.items():
                total_stats[entity_type] = total_stats.get(entity_type, 0) + count
        else:
            # Keep other types as-is (numbers, booleans, null)
            anonymized[key] = value
    
    return anonymized, total_stats


@router.post("/anonymize-azure-di", response_model=AnonymizationResponse)
async def anonymize_azure_di_endpoint(request: AnonymizationRequest):
    """
    Anonymize Azure DI JSON output for safe storage and testing.
    
    This endpoint:
    1. Detects PII using LLM-Guard with AI4Privacy BERT model (54 PII types)
    2. Replaces PII with realistic fake data using cryptographically secure random values
    3. Preserves Azure DI JSON structure and element IDs
    4. Provides consistent replacements within a session
    5. Implements session isolation for security
    6. Supports stateless operation by accepting/returning vault data
    """
    try:
        # Create scanner with optional vault data for stateless operation
        scanner, vault, existing_date_offset = create_anonymizer(request.config, request.vault_data)
        
        # Generate or use existing date shift if enabled
        date_shift = None
        if request.config.date_shift_days:
            date_shift = generate_session_shift(request.config.date_shift_days, existing_date_offset)
        
        # Anonymize the JSON
        anonymized_json, statistics = anonymize_azure_di_json(
            request.azure_di_json,
            request.config,
            scanner,
            vault,
            date_shift
        )
        
        return AnonymizationResponse(
            anonymized_json=anonymized_json,
            statistics=statistics,
            vault_data=serialize_vault(vault, date_shift)
        )
        
    except Exception as e:
        logger.error(f"Anonymization failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Anonymization failed: {str(e)}")


@router.post("/anonymize-markdown", response_model=MarkdownAnonymizationResponse)
async def anonymize_markdown_endpoint(request: MarkdownAnonymizationRequest):
    """
    Anonymize markdown text while preserving formatting.
    
    This endpoint:
    1. Detects PII in markdown text using LLM-Guard with AI4Privacy BERT model
    2. Replaces PII with realistic fake data using secure random generation
    3. Preserves markdown formatting (headers, lists, code blocks, etc.)
    4. Provides consistent replacements within a session
    5. Implements session isolation for security
    6. Supports stateless operation by accepting/returning vault data
    """
    try:
        # Create scanner with optional vault data for stateless operation
        scanner, vault, existing_date_offset = create_anonymizer(request.config, request.vault_data)
        
        # Generate or use existing date shift if enabled
        date_shift = None
        if request.config.date_shift_days:
            date_shift = generate_session_shift(request.config.date_shift_days, existing_date_offset)
        
        # Anonymize the markdown text
        anonymized_text, statistics, decision_process = anonymize_text_with_date_shift(
            request.markdown_text,
            scanner,
            vault,
            request.config,
            date_shift
        )
        
        return MarkdownAnonymizationResponse(
            anonymized_text=anonymized_text,
            statistics=statistics,
            decision_process=decision_process,
            vault_data=serialize_vault(vault, date_shift)
        )
        
    except Exception as e:
        logger.error(f"Markdown anonymization failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Markdown anonymization failed: {str(e)}")


@router.post("/pseudonymize", response_model=PseudonymizationResponse)
async def pseudonymize_endpoint(request: PseudonymizationRequest):
    """
    Pseudonymize text with consistent replacements across documents.
    
    This endpoint:
    1. Detects PII using LLM-Guard with AI4Privacy BERT model
    2. Replaces PII with consistent pseudonyms
    3. Maintains vault data for reversibility and consistency
    4. Supports stateless operation by accepting/returning vault data
    
    The difference from anonymization is that this is designed for reversibility
    and maintaining consistent replacements across multiple documents.
    """
    try:
        # Create scanner with optional vault data for stateless operation
        scanner, vault, existing_date_offset = create_anonymizer(request.config, request.vault_data)
        
        # Generate or use existing date shift if enabled
        date_shift = None
        if request.config.date_shift_days:
            date_shift = generate_session_shift(request.config.date_shift_days, existing_date_offset)
        
        # Pseudonymize the text
        pseudonymized_text, statistics, _ = anonymize_text_with_date_shift(
            request.text,
            scanner,
            vault,
            request.config,
            date_shift
        )
        
        return PseudonymizationResponse(
            pseudonymized_text=pseudonymized_text,
            statistics=statistics,
            vault_data=serialize_vault(vault, date_shift)
        )
        
    except Exception as e:
        logger.error(f"Pseudonymization failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Pseudonymization failed: {str(e)}")


@router.post("/deanonymize", response_model=DeanonymizationResponse)
async def deanonymize_endpoint(request: DeanonymizationRequest):
    """
    Deanonymize text using vault mappings.
    
    This endpoint:
    1. Reverses pseudonymization using vault data
    2. Restores original values from pseudonyms
    3. Provides statistics on deanonymized entities
    
    Note: This only works with text that was pseudonymized using the
    /pseudonymize endpoint with the same vault data.
    """
    try:
        # Deanonymize using vault mappings
        deanonymized_text, statistics = deanonymize_text_with_vault(
            request.text,
            request.vault_data
        )
        
        return DeanonymizationResponse(
            deanonymized_text=deanonymized_text,
            statistics=statistics
        )
        
    except Exception as e:
        logger.error(f"Deanonymization failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Deanonymization failed: {str(e)}")


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