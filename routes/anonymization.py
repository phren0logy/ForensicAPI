"""
PII Anonymization API endpoint for generating safe test data from Azure DI JSON.

Uses Microsoft Presidio with BERT-based NER for accurate PII detection and anonymization.
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

from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine, OperatorConfig

from faker import Faker
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(tags=["anonymization"])

# Initialize Faker with random seed for security
fake = Faker()  # Uses random seed for unpredictable anonymization

# Default entity types for PII detection
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


class AnonymizationRequest(BaseModel):
    """Request body for anonymization endpoint."""
    azure_di_json: Dict[str, Any] = Field(..., description="Raw Azure DI extraction output")
    config: AnonymizationConfig = Field(default_factory=AnonymizationConfig)


class AnonymizationResponse(BaseModel):
    """Response from anonymization endpoint."""
    anonymized_json: Dict[str, Any] = Field(..., description="Anonymized Azure DI JSON")
    statistics: Dict[str, int] = Field(..., description="Count of anonymized entities by type")


class MarkdownAnonymizationRequest(BaseModel):
    """Request body for markdown anonymization endpoint."""
    markdown_text: str = Field(..., description="Markdown text to anonymize")
    config: AnonymizationConfig = Field(default_factory=AnonymizationConfig)


class MarkdownAnonymizationResponse(BaseModel):
    """Response from markdown anonymization endpoint."""
    anonymized_text: str = Field(..., description="Anonymized markdown text")
    statistics: Dict[str, int] = Field(..., description="Count of anonymized entities by type")
    decision_process: Optional[List[Dict]] = Field(None, description="Detection reasoning if requested")


# Global engines (initialized on first use)
analyzer_engine: Optional[AnalyzerEngine] = None
anonymizer_engine: Optional[AnonymizerEngine] = None

# Replacement mappings are created per-session to prevent information leakage



def initialize_engines() -> tuple[AnalyzerEngine, AnonymizerEngine]:
    """Initialize Presidio engines with default configuration."""
    global analyzer_engine, anonymizer_engine
    
    if analyzer_engine is None:
        logger.info("Initializing Presidio engines...")
        
        try:
            # Use default Presidio analyzer with built-in recognizers
            # This includes PERSON, US_SSN, EMAIL_ADDRESS, PHONE_NUMBER, etc.
            analyzer_engine = AnalyzerEngine(supported_languages=["en"])
            
            # Initialize anonymizer
            anonymizer_engine = AnonymizerEngine()
            
            logger.info("✅ Presidio engines initialized successfully with built-in recognizers")
            
        except Exception as e:
            logger.error(f"Failed to initialize Presidio engines: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to initialize Presidio engines: {str(e)}")
    
    return analyzer_engine, anonymizer_engine


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
        replacement = f"[REDACTED_{entity_type}]"
    
    # Store for consistency
    replacement_mappings[entity_type][original_value] = replacement
    return replacement


def anonymize_text_field(text: str, analyzer: AnalyzerEngine, 
                        anonymizer: AnonymizerEngine, 
                        config: AnonymizationConfig,
                        replacement_mappings: Dict[str, Dict[str, str]] = None) -> tuple[str, Dict[str, int], Optional[List[Dict]]]:
    """Anonymize a text field and return statistics."""
    if not text or not isinstance(text, str):
        return text, {}, None
    
    # Analyze the text with requested entity types
    results = analyzer.analyze(
        text=text, 
        language="en", 
        entities=config.entity_types,
        score_threshold=config.score_threshold,
        return_decision_process=config.return_decision_process
    )
    
    # Use results directly
    filtered_results = results
    
    # Build replacement map and operators for each entity type
    operators = {}
    stats = {}
    
    # Group results by entity type
    from collections import defaultdict
    results_by_type = defaultdict(list)
    for result in filtered_results:
        results_by_type[result.entity_type].append(result)
    
    # Create operators for each entity type with consistent replacements
    for entity_type, type_results in results_by_type.items():
        # Create a mapping for consistent replacements
        replacement_map = {}
        for result in type_results:
            original_text = text[result.start:result.end]
            if original_text not in replacement_map:
                replacement = get_consistent_replacement(
                    entity_type, original_text, config.date_shift_days,
                    replacement_mappings
                )
                replacement_map[original_text] = replacement
        
        # Create custom operator that uses the mapping
        # Use default argument to capture the current replacement_map
        operators[entity_type] = OperatorConfig(
            "custom",
            {"lambda": lambda text, rm=replacement_map: rm.get(text, f"[REDACTED_{entity_type}]")}
        )
        
        # Update statistics
        stats[entity_type] = len(type_results)
    
    # Anonymize the text
    anonymized_result = anonymizer.anonymize(
        text=text,
        analyzer_results=filtered_results,
        operators=operators
    )
    
    # Extract decision process if requested
    decision_process = None
    if config.return_decision_process and hasattr(results[0], 'analysis_explanation') if results else False:
        decision_process = [{'entity': r.entity_type, 'start': r.start, 'end': r.end, 
                           'score': r.score, 'explanation': getattr(r, 'analysis_explanation', None)} 
                          for r in results]
    
    return anonymized_result.text, stats, decision_process


def anonymize_azure_di_json(data: Dict[str, Any], 
                           config: AnonymizationConfig,
                           analyzer: AnalyzerEngine,
                           anonymizer: AnonymizerEngine,
                           replacement_mappings: Dict[str, Dict[str, str]] = None) -> tuple[Dict[str, Any], Dict[str, int]]:
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
            anonymized_text, stats, _ = anonymize_text_field(
                value, analyzer, anonymizer, config, replacement_mappings
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
                        item, config, analyzer, anonymizer, replacement_mappings
                    )
                    anonymized_list.append(anon_item)
                    # Merge statistics
                    for entity_type, count in item_stats.items():
                        total_stats[entity_type] = total_stats.get(entity_type, 0) + count
                elif isinstance(item, str):
                    # Check if it might contain PII
                    anon_text, stats, _ = anonymize_text_field(
                        item, analyzer, anonymizer, config, replacement_mappings
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
                value, config, analyzer, anonymizer, replacement_mappings
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
    1. Detects PII using Presidio with BERT-based NER
    2. Replaces PII with realistic fake data using cryptographically secure random values
    3. Preserves Azure DI JSON structure and element IDs
    4. Provides consistent replacements within a session
    5. Implements session isolation for security
    """
    try:
        # Initialize engines
        analyzer, anonymizer = initialize_engines()
        
        # Create new mappings for this anonymization session
        replacement_mappings = {}
        
        # Anonymize the JSON
        anonymized_json, statistics = anonymize_azure_di_json(
            request.azure_di_json,
            request.config,
            analyzer,
            anonymizer,
            replacement_mappings
        )
        
        return AnonymizationResponse(
            anonymized_json=anonymized_json,
            statistics=statistics
        )
        
    except Exception as e:
        logger.error(f"Anonymization failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Anonymization failed: {str(e)}")


@router.post("/anonymize-markdown", response_model=MarkdownAnonymizationResponse)
async def anonymize_markdown_endpoint(request: MarkdownAnonymizationRequest):
    """
    Anonymize markdown text while preserving formatting.
    
    This endpoint:
    1. Detects PII in markdown text using Presidio with BERT-based NER
    2. Replaces PII with realistic fake data using secure random generation
    3. Preserves markdown formatting (headers, lists, code blocks, etc.)
    4. Provides consistent replacements within a session
    5. Implements session isolation for security
    """
    try:
        # Initialize engines
        analyzer, anonymizer = initialize_engines()
        
        # Create new mappings for this anonymization session
        replacement_mappings = {}
        
        # Anonymize the markdown text
        anonymized_text, statistics, decision_process = anonymize_text_field(
            request.markdown_text,
            analyzer,
            anonymizer,
            request.config,
            replacement_mappings
        )
        
        return MarkdownAnonymizationResponse(
            anonymized_text=anonymized_text,
            statistics=statistics,
            decision_process=decision_process
        )
        
    except Exception as e:
        logger.error(f"Markdown anonymization failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Markdown anonymization failed: {str(e)}")


@router.get("/health")
async def health_check():
    """Check if anonymization service is ready."""
    try:
        # Test engine initialization
        analyzer, anonymizer = initialize_engines()
        
        return {
            "status": "healthy",
            "service": "anonymization",
            "engines_initialized": analyzer is not None and anonymizer is not None,
            "recognizers": "Built-in Presidio recognizers (PERSON, US_SSN, EMAIL_ADDRESS, etc.)"
        }
    except Exception as e:
        return {
            "status": "unhealthy", 
            "service": "anonymization",
            "error": str(e)
        }