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

from presidio_analyzer import AnalyzerEngine, RecognizerResult, PatternRecognizer, Pattern
from presidio_analyzer.nlp_engine import TransformersNlpEngine
from presidio_anonymizer import AnonymizerEngine, OperatorConfig
from presidio_anonymizer.entities import OperatorResult

from faker import Faker
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/anonymization", tags=["anonymization"])

# Initialize Faker for consistent replacements
fake = Faker()
Faker.seed(12345)  # Consistent seed for reproducible results


class AnonymizationConfig(BaseModel):
    """Configuration for anonymization process."""
    preserve_structure: bool = Field(default=True, description="Preserve Azure DI JSON structure")
    entity_types: List[str] = Field(
        default=[
            "PERSON", "DATE_TIME", "LOCATION", "PHONE_NUMBER", 
            "EMAIL_ADDRESS", "US_SSN", "MEDICAL_LICENSE", 
            "BATES_NUMBER", "CASE_NUMBER"
        ],
        description="Entity types to anonymize"
    )
    date_shift_days: int = Field(default=365, description="Maximum days to shift dates")
    consistent_replacements: bool = Field(default=True, description="Use consistent replacements for same values")
    use_bert_ner: bool = Field(default=True, description="Use BERT for enhanced NER")
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


# Global engines (initialized on first use)
analyzer_engine: Optional[AnalyzerEngine] = None
anonymizer_engine: Optional[AnonymizerEngine] = None

# Replacement mappings for consistent anonymization
replacement_mappings: Dict[str, Dict[str, str]] = {}

# Entity type mapping for Isotonic BERT model
# Maps fine-grained entity types to standard Presidio types
ENTITY_TYPE_MAPPING = {
    "FIRSTNAME": "PERSON",
    "LASTNAME": "PERSON",
    "MIDDLENAME": "PERSON",
    "PREFIX": "PERSON",  # Dr., Mr., etc.
    "USERNAME": "PERSON",
    "DOB": "DATE_TIME",
    "DATE": "DATE_TIME",
    "TIME": "DATE_TIME",
    "AGE": "DATE_TIME",
    "PHONENUMBER": "PHONE_NUMBER",
    "CITY": "LOCATION",
    "STATE": "LOCATION",
    "COUNTY": "LOCATION",
    "STREET": "LOCATION",
    "ZIPCODE": "LOCATION",
    "BUILDINGNAME": "LOCATION",
    "SECONDARYADDRESS": "LOCATION",
    "SSN": "US_SSN",
    "IDCARDNUMBER": "US_SSN",  # Often used for SSN
    "ACCOUNTNUMBER": "US_BANK_NUMBER",
    "PIN": "US_BANK_NUMBER",
    "CREDITCARDNUMBER": "CREDIT_CARD",
    "EMAIL": "EMAIL_ADDRESS",
    "URL": "URL",
    "IPV4": "IP_ADDRESS",
    "IPV6": "IP_ADDRESS",
    "MAC": "IP_ADDRESS",  # MAC addresses
    "VEHICLEVRM": "LICENSE_PLATE",
    "VEHICLEVINNUMBER": "LICENSE_PLATE",
    "DRIVERLICENSE": "US_DRIVER_LICENSE",
}


def get_custom_recognizers() -> List[PatternRecognizer]:
    """Create custom recognizers for forensic document patterns."""
    recognizers = []
    
    # Add custom name recognizer for common name patterns
    name_recognizer = PatternRecognizer(
        supported_entity="PERSON",
        patterns=[
            Pattern(
                name="full_name",
                regex=r"\b([A-Z][a-z]+\s+){1,3}[A-Z][a-z]+\b",  # John Smith, John A. Smith
                score=0.85
            ),
            Pattern(
                name="name_with_title",
                regex=r"\b(Mr\.|Mrs\.|Ms\.|Dr\.|Prof\.)\s+[A-Z][a-z]+(\s+[A-Z]\.?\s+)?[A-Z][a-z]+\b",
                score=0.9
            ),
            Pattern(
                name="all_caps_name",
                regex=r"\b[A-Z]{2,}(\s+[A-Z]{2,})+\b",  # JOHN SMITH
                score=0.8
            )
        ]
    )
    recognizers.append(name_recognizer)
    
    # Bates number recognizer
    bates_recognizer = PatternRecognizer(
        supported_entity="BATES_NUMBER",
        patterns=[
            Pattern(
                name="bates_standard",
                regex=r"\b[A-Z]{2,4}[-_]?\d{6,8}\b",
                score=0.9
            ),
            Pattern(
                name="bates_with_prefix",
                regex=r"\bBATES[-_]?\d{6,8}\b",
                score=0.95
            )
        ]
    )
    recognizers.append(bates_recognizer)
    
    # Case number recognizer
    case_recognizer = PatternRecognizer(
        supported_entity="CASE_NUMBER",
        patterns=[
            Pattern(
                name="case_standard",
                regex=r"\b\d{2,4}[-/]\w{2,4}[-/]\d{3,6}\b",
                score=0.85
            ),
            Pattern(
                name="case_with_prefix",
                regex=r"\b(?:Case|Docket|File)[\s#:]+[\w-]+\b",
                score=0.9
            )
        ]
    )
    recognizers.append(case_recognizer)
    
    # Medical record number recognizer
    medical_record_recognizer = PatternRecognizer(
        supported_entity="MEDICAL_RECORD_NUMBER",
        patterns=[
            Pattern(
                name="mrn_standard",
                regex=r"\b(?:MRN|MR#?)[\s:]*\d{6,10}\b",
                score=0.95
            ),
            Pattern(
                name="patient_id",
                regex=r"\b(?:Patient ID|Pt ID)[\s:]*\d{6,10}\b",
                score=0.9
            )
        ]
    )
    recognizers.append(medical_record_recognizer)
    
    return recognizers


def initialize_engines(use_bert: bool = True) -> tuple[AnalyzerEngine, AnonymizerEngine]:
    """Initialize Presidio engines with optional BERT support."""
    global analyzer_engine, anonymizer_engine
    
    if analyzer_engine is None:
        logger.info("Initializing Presidio engines...")
        
        try:
            if use_bert:
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
                
            else:
                # Pattern-based analyzer without NLP
                logger.info("Using pattern-based recognition only")
                # Create analyzer with registry only - no NLP
                from presidio_analyzer import RecognizerRegistry
                
                # Create empty registry
                registry = RecognizerRegistry()
                registry.load_predefined_recognizers(["en"])
                
                analyzer_engine = AnalyzerEngine(
                    registry=registry,
                    supported_languages=["en"]
                )
            
            # Add custom recognizers for forensic patterns
            for recognizer in get_custom_recognizers():
                analyzer_engine.registry.add_recognizer(recognizer)
            
            # Initialize anonymizer
            anonymizer_engine = AnonymizerEngine()
            
            logger.info("Presidio engines initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize BERT model: {str(e)}")
            logger.info("Falling back to pattern-based recognition")
            
            # Fall back to basic mode without BERT
            analyzer_engine = AnalyzerEngine()
            for recognizer in get_custom_recognizers():
                analyzer_engine.registry.add_recognizer(recognizer)
            anonymizer_engine = AnonymizerEngine()
    
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
        # Shift date by random amount up to date_shift_days
        shift_days = random.randint(-date_shift_days, date_shift_days)
        try:
            # Try to parse and shift the date
            # This is simplified - in production, use better date parsing
            replacement = f"[DATE_SHIFTED_{shift_days}d]"
        except:
            replacement = f"[DATE_SHIFTED]"
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
    elif entity_type == "BATES_NUMBER":
        replacement = f"ANON-{fake.random_number(digits=6)}"
    elif entity_type == "CASE_NUMBER":
        replacement = f"{fake.random_number(digits=4)}-CR-{fake.random_number(digits=5)}"
    elif entity_type == "MEDICAL_RECORD_NUMBER":
        replacement = f"MRN{fake.random_number(digits=8)}"
    else:
        replacement = f"[REDACTED_{entity_type}]"
    
    # Store for consistency
    replacement_mappings[entity_type][original_value] = replacement
    return replacement


def anonymize_text_field(text: str, analyzer: AnalyzerEngine, 
                        anonymizer: AnonymizerEngine, 
                        entity_types: List[str],
                        use_consistent: bool = True,
                        date_shift_days: int = 365,
                        use_bert: bool = True) -> tuple[str, Dict[str, int]]:
    """Anonymize a text field and return statistics."""
    if not text or not isinstance(text, str):
        return text, {}
    
    # Analyze the text with requested entity types
    results = analyzer.analyze(text=text, language="en", entities=entity_types)
    
    # For BERT mode, also check for fine-grained types and map them
    if use_bert and "PERSON" in entity_types:
        # Get all results to check for name-related entities
        all_results = analyzer.analyze(text=text, language="en", entities=None)
        
        # Find and add name-related entities
        person_types = {k for k, v in ENTITY_TYPE_MAPPING.items() if v == "PERSON"}
        for result in all_results:
            if result.entity_type in person_types:
                # Map to PERSON and add if not overlapping
                mapped_result = RecognizerResult(
                    entity_type="PERSON",
                    start=result.start,
                    end=result.end,
                    score=result.score
                )
                # Check for overlap with existing results
                overlap = False
                for existing in results:
                    if (mapped_result.start < existing.end and 
                        mapped_result.end > existing.start):
                        overlap = True
                        break
                if not overlap:
                    results.append(mapped_result)
    
    # Use results directly
    filtered_results = results
    
    # Create operators for anonymization
    operators = {}
    stats = {}
    
    for result in filtered_results:
        entity_type = result.entity_type
        original_text = text[result.start:result.end]
        
        if use_consistent:
            replacement = get_consistent_replacement(
                entity_type, original_text, date_shift_days
            )
            operators[entity_type] = OperatorConfig(
                "replace",
                {"new_value": replacement}
            )
        else:
            operators[entity_type] = OperatorConfig("replace")
        
        # Update statistics
        stats[entity_type] = stats.get(entity_type, 0) + 1
    
    # Anonymize the text
    anonymized_result = anonymizer.anonymize(
        text=text,
        analyzer_results=filtered_results,
        operators=operators
    )
    
    return anonymized_result.text, stats


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
            anonymized_text, stats = anonymize_text_field(
                value, analyzer, anonymizer,
                config.entity_types,
                config.consistent_replacements,
                config.date_shift_days,
                config.use_bert_ner
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
                    anon_text, stats = anonymize_text_field(
                        item, analyzer, anonymizer,
                        config.entity_types,
                        config.consistent_replacements,
                        config.date_shift_days,
                        config.use_bert_ner
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
        # Initialize engines (always use BERT for now)
        analyzer, anonymizer = initialize_engines(use_bert=True)
        
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


@router.get("/health")
async def health_check():
    """Check if anonymization service is ready."""
    try:
        # Only test BERT since pattern-only isn't working without spaCy
        analyzer, anonymizer = initialize_engines(use_bert=True)
        
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