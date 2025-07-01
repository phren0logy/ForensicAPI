"""
PII Anonymization API endpoint for generating safe test data from Azure DI JSON.

Uses Microsoft Presidio with BERT-based NER for accurate PII detection and anonymization.
Includes custom recognizers for forensic document patterns (Bates numbers, case IDs, etc.).
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional, Set
import json
import hashlib
from datetime import datetime, timedelta
import random
from dateutil import parser as date_parser

from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_analyzer.nlp_engine import TransformersNlpEngine
from presidio_anonymizer import AnonymizerEngine, OperatorConfig
from presidio_anonymizer.entities import OperatorResult

from faker import Faker
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(tags=["anonymization"])

# Initialize Faker for consistent replacements
fake = Faker()
Faker.seed(12345)  # Consistent seed for reproducible results


class AnonymizationConfig(BaseModel):
    """Configuration for anonymization process."""
    preserve_structure: bool = Field(default=True, description="Preserve Azure DI JSON structure")
    entity_types: List[str] = Field(
        default=[
            "PERSON", "DATE_TIME", "LOCATION", "PHONE_NUMBER", 
            "EMAIL_ADDRESS", "US_SSN", "MEDICAL_LICENSE"
        ],
        description="Entity types to anonymize"
    )
    date_shift_days: int = Field(default=365, description="Maximum days to shift dates")
    consistent_replacements: bool = Field(default=True, description="Use consistent replacements for same values")
    score_threshold: float = Field(default=0.5, ge=0.0, le=1.0, description="Minimum confidence score for entity detection")
    return_decision_process: bool = Field(default=False, description="Include detailed detection reasoning")
    custom_patterns: Optional[Dict[str, str]] = Field(default=None, description="Custom regex patterns")


class AnonymizationRequest(BaseModel):
    """Request body for anonymization endpoint."""
    azure_di_json: Dict[str, Any] = Field(..., description="Raw Azure DI extraction output")
    config: AnonymizationConfig = Field(default_factory=AnonymizationConfig)


class AnonymizationResponse(BaseModel):
    """Response from anonymization endpoint."""
    anonymized_json: Dict[str, Any] = Field(..., description="Anonymized Azure DI JSON")
    statistics: Dict[str, int] = Field(..., description="Count of anonymized entities by type")
    mappings_id: Optional[str] = Field(None, description="ID for retrieving anonymization mappings")


class MarkdownAnonymizationRequest(BaseModel):
    """Request body for markdown anonymization endpoint."""
    markdown_text: str = Field(..., description="Markdown text to anonymize")
    config: AnonymizationConfig = Field(default_factory=AnonymizationConfig)


class MarkdownAnonymizationResponse(BaseModel):
    """Response from markdown anonymization endpoint."""
    anonymized_text: str = Field(..., description="Anonymized markdown text")
    statistics: Dict[str, int] = Field(..., description="Count of anonymized entities by type")
    mappings_id: Optional[str] = Field(None, description="ID for retrieving anonymization mappings")
    decision_process: Optional[List[Dict]] = Field(None, description="Detection reasoning if requested")


# Global engines (initialized on first use)
analyzer_engine: Optional[AnalyzerEngine] = None
anonymizer_engine: Optional[AnonymizerEngine] = None

# Replacement mappings for consistent anonymization
replacement_mappings: Dict[str, Dict[str, str]] = {}



def initialize_engines() -> tuple[AnalyzerEngine, AnonymizerEngine]:
    """Initialize Presidio engines with BERT model."""
    global analyzer_engine, anonymizer_engine
    
    if analyzer_engine is None:
        logger.info("Initializing Presidio engines...")
        
        try:
            # Initialize with privacy-focused BERT model
            from presidio_analyzer.nlp_engine import NlpEngineProvider
            
            # Use Isotonic's privacy-focused BERT model
            # This model is specifically fine-tuned for PII detection
            nlp_config = {
                "nlp_engine_name": "transformers",
                "models": [{
                    "lang_code": "en",
                    "model_name": {
                        "spacy": "en_core_web_md",  # For tokenization only
                        "transformers": "Isotonic/distilbert_finetuned_ai4privacy_v2",
                        "model_kwargs": {
                            "max_length": 512,  # Handle longer texts
                            "aggregation_strategy": "simple"  # Better for PII detection
                        }
                    }
                }]
            }
            
            logger.info("Loading privacy-focused BERT model: Isotonic/distilbert_finetuned_ai4privacy_v2")
            
            # Create NLP engine
            provider = NlpEngineProvider(nlp_configuration=nlp_config)
            nlp_engine = provider.create_engine()
            
            # Create analyzer with privacy-focused BERT
            analyzer_engine = AnalyzerEngine(
                nlp_engine=nlp_engine,
                supported_languages=["en"]
            )
            
            logger.info("✅ Privacy-focused BERT model loaded successfully")
            
            # Initialize anonymizer
            anonymizer_engine = AnonymizerEngine()
            
            logger.info("Presidio engines initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize BERT model: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to initialize BERT model: {str(e)}")
    
    return analyzer_engine, anonymizer_engine


def get_consistent_replacement(entity_type: str, original_value: str, 
                             date_shift_days: int = 365) -> str:
    """Get consistent replacement for a value based on entity type."""
    global replacement_mappings
    
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
            replacement_mappings["_date_shift_days"] = random.randint(-date_shift_days, date_shift_days)
        
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
        replacement = fake.ssn()
    elif entity_type == "MEDICAL_LICENSE":
        replacement = f"MD{fake.random_number(digits=6)}"
    else:
        replacement = f"[REDACTED_{entity_type}]"
    
    # Store for consistency
    replacement_mappings[entity_type][original_value] = replacement
    return replacement


def anonymize_text_field(text: str, analyzer: AnalyzerEngine, 
                        anonymizer: AnonymizerEngine, 
                        config: AnonymizationConfig) -> tuple[str, Dict[str, int], Optional[List[Dict]]]:
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
    
    # Create operators for each entity type
    for entity_type, type_results in results_by_type.items():
        if config.consistent_replacements:
            # For consistent replacements, create a mapping
            replacement_map = {}
            for result in type_results:
                original_text = text[result.start:result.end]
                if original_text not in replacement_map:
                    replacement = get_consistent_replacement(
                        entity_type, original_text, config.date_shift_days
                    )
                    replacement_map[original_text] = replacement
                    if entity_type == "DATE_TIME":
                        logger.info(f"DATE mapping '{original_text}' -> '{replacement}'")
            
            # Create custom operator that uses the mapping
            # Use default argument to capture the current replacement_map
            operators[entity_type] = OperatorConfig(
                "custom",
                {"lambda": lambda text, rm=replacement_map: rm.get(text, f"[NOT_FOUND:{text}]")}
            )
        else:
            # For non-consistent, just use replace operator
            operators[entity_type] = OperatorConfig("replace")
        
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
                           anonymizer: AnonymizerEngine) -> tuple[Dict[str, Any], Dict[str, int]]:
    """Recursively anonymize Azure DI JSON while preserving structure."""
    if not isinstance(data, dict):
        return data, {}
    
    anonymized = {}
    total_stats = {}
    
    # Fields that commonly contain PII in Azure DI output
    text_fields = {
        "content", "text", "value", "content", "name", "description",
        "title", "subject", "author", "creator", "producer"
    }
    
    for key, value in data.items():
        if isinstance(value, str) and (key in text_fields or config.preserve_structure):
            # Anonymize text field
            anonymized_text, stats, _ = anonymize_text_field(
                value, analyzer, anonymizer, config
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
                        item, config, analyzer, anonymizer
                    )
                    anonymized_list.append(anon_item)
                    # Merge statistics
                    for entity_type, count in item_stats.items():
                        total_stats[entity_type] = total_stats.get(entity_type, 0) + count
                elif isinstance(item, str):
                    # Check if it might contain PII
                    anon_text, stats, _ = anonymize_text_field(
                        item, analyzer, anonymizer, config
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
                value, config, analyzer, anonymizer
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
    1. Detects PII using Presidio with optional BERT-based NER
    2. Applies custom recognizers for forensic document patterns
    3. Replaces PII with realistic fake data
    4. Preserves Azure DI JSON structure and element IDs
    5. Provides consistent replacements for the same values
    """
    try:
        # Initialize engines
        analyzer, anonymizer = initialize_engines()
        
        # Clear mappings for new anonymization session
        global replacement_mappings
        replacement_mappings = {}
        
        # Anonymize the JSON
        anonymized_json, statistics = anonymize_azure_di_json(
            request.azure_di_json,
            request.config,
            analyzer,
            anonymizer
        )
        
        # Generate mappings ID (optional - for future deanonymization support)
        mappings_data = json.dumps(replacement_mappings, sort_keys=True)
        mappings_id = hashlib.sha256(mappings_data.encode()).hexdigest()[:16]
        
        return AnonymizationResponse(
            anonymized_json=anonymized_json,
            statistics=statistics,
            mappings_id=mappings_id
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
    2. Applies custom recognizers for forensic document patterns
    3. Replaces PII with realistic fake data
    4. Preserves markdown formatting (headers, lists, code blocks, etc.)
    5. Provides consistent replacements for the same values
    """
    try:
        # Initialize engines
        analyzer, anonymizer = initialize_engines()
        
        # Clear mappings for new anonymization session if consistent replacements enabled
        if request.config.consistent_replacements:
            global replacement_mappings
            replacement_mappings = {}
        
        # Anonymize the markdown text
        anonymized_text, statistics, decision_process = anonymize_text_field(
            request.markdown_text,
            analyzer,
            anonymizer,
            request.config
        )
        
        # Generate mappings ID (optional - for future deanonymization support)
        mappings_id = None
        if request.config.consistent_replacements:
            mappings_data = json.dumps(replacement_mappings, sort_keys=True)
            mappings_id = hashlib.sha256(mappings_data.encode()).hexdigest()[:16]
        
        return MarkdownAnonymizationResponse(
            anonymized_text=anonymized_text,
            statistics=statistics,
            mappings_id=mappings_id,
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
            "bert_engine": analyzer is not None and anonymizer is not None,
            "model": "Isotonic/distilbert_finetuned_ai4privacy_v2"
        }
    except Exception as e:
        return {
            "status": "unhealthy", 
            "service": "anonymization",
            "error": str(e)
        }