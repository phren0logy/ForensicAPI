# LLM-Guard Migration Design Document

## Executive Summary

This document outlines the migration plan from our current Presidio-based anonymization system to LLM-Guard, primarily to leverage the superior AI4Privacy BERT model (`Isotonic/distilbert_finetuned_ai4privacy_v2`) for PII detection. The migration will maintain our custom date shifting logic and session isolation while adopting LLM-Guard's enhanced detection capabilities.

## Motivation

### Current Limitations
- Basic Presidio recognizers detect only 7 PII types
- Limited accuracy with spaCy NER models
- Manual configuration complexity
- No built-in deanonymization capability

### LLM-Guard Benefits
- **54 PII types** supported by AI4Privacy model
- **97.8% F1 score** for PII detection
- Built-in Faker integration
- Vault system for deanonymization
- Active development with LLM-specific features
- ONNX optimization support

## Architecture Overview

### Core Components

```
┌─────────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   FastAPI Router    │────▶│  LLM-Guard       │────▶│   AI4Privacy    │
│  (Existing APIs)    │     │   Anonymizer     │     │   BERT Model    │
└─────────────────────┘     └──────────────────┘     └─────────────────┘
           │                          │
           │                          ▼
           │                 ┌──────────────────┐
           │                 │      Vault       │
           │                 │  (Per Session)   │
           │                 └──────────────────┘
           │
           ▼
┌─────────────────────┐     ┌──────────────────┐
│   Custom Logic      │     │   Date Shift     │
│  - Azure DI JSON    │────▶│   Post-Processor │
│  - Recursive        │     │  (Temporal       │
│    Processing       │     │   Consistency)   │
└─────────────────────┘     └──────────────────┘
```

## Implementation Details

### 1. Dependencies Update

```toml
# pyproject.toml changes
[project]
dependencies = [
    # Remove these:
    # "presidio-analyzer>=2.2.35",
    # "presidio-anonymizer>=2.2.35",
    # "spacy>=3.7.0",
    # "spacy-huggingface-pipelines>=0.0.4",
    
    # Add this:
    "llm-guard>=0.3.0",
    
    # Keep these for custom logic:
    "faker>=20.1.0",
    "python-dateutil>=2.9.0.post0",
]
```

### 2. Core Scanner Implementation

```python
# routes/anonymization.py

from llm_guard.input_scanners import Anonymize
from llm_guard.input_scanners.anonymize_helpers import get_ai4privacy_config
from llm_guard.vault import Vault

def create_anonymizer(config: AnonymizationConfig) -> tuple[Anonymize, Vault]:
    """Create LLM-Guard anonymizer with AI4Privacy model.
    
    Returns a new scanner and vault for session isolation.
    """
    vault = Vault()  # New vault per request for session isolation
    
    # Use AI4Privacy model with 54 PII types
    recognizer_config = get_ai4privacy_config()
    
    scanner = Anonymize(
        vault=vault,
        recognizer_conf=recognizer_config,
        threshold=config.score_threshold,
        use_faker=True,  # Enable Faker for all entities
        entity_types=config.entity_types if config.entity_types else None,
        language="en"
    )
    
    return scanner, vault
```

### 3. Custom Date Shifting Integration

Since LLM-Guard generates random dates without preserving temporal relationships, we'll implement a post-processing layer:

```python
def anonymize_with_custom_dates(
    text: str, 
    scanner: Anonymize,
    config: AnonymizationConfig
) -> tuple[str, Dict[str, int]]:
    """Anonymize text with custom date shifting logic."""
    
    # Step 1: LLM-Guard anonymization
    sanitized_text, is_valid, risk_score = scanner.scan(text)
    
    # Step 2: Extract date entities from vault
    if config.date_shift_days:
        date_entities = extract_date_entities_from_vault(scanner.vault)
        
        if date_entities:
            # Generate consistent shift for this session
            shift_days = generate_session_shift(config.date_shift_days)
            
            # Replace LLM-Guard's random dates with shifted dates
            sanitized_text = apply_date_shifts(
                sanitized_text, 
                date_entities, 
                shift_days
            )
            
            # Update vault for deanonymization
            update_vault_with_shifted_dates(
                scanner.vault, 
                date_entities, 
                shift_days
            )
    
    # Step 3: Extract statistics
    statistics = extract_statistics_from_vault(scanner.vault)
    
    return sanitized_text, statistics
```

### 4. Azure DI JSON Processing

Maintain our recursive processing logic while using LLM-Guard for detection:

```python
def anonymize_azure_di_json(
    data: Dict[str, Any],
    config: AnonymizationConfig
) -> tuple[Dict[str, Any], Dict[str, int]]:
    """Process Azure DI JSON with LLM-Guard."""
    
    # Create new scanner for session isolation
    scanner, vault = create_anonymizer(config)
    
    # Session-wide date shift
    date_shift = None
    if config.date_shift_days:
        date_shift = generate_session_shift(config.date_shift_days)
    
    # Recursive processing with custom handler
    anonymized = process_recursive(
        data, 
        scanner, 
        config,
        date_shift
    )
    
    statistics = extract_statistics_from_vault(vault)
    
    return anonymized, statistics
```

### 5. API Endpoints

Keep the same API surface while updating internals:

```python
@router.post("/anonymize-azure-di", response_model=AnonymizationResponse)
async def anonymize_azure_di_endpoint(request: AnonymizationRequest):
    """Anonymize Azure DI JSON with AI4Privacy model."""
    try:
        anonymized_json, statistics = anonymize_azure_di_json(
            request.azure_di_json,
            request.config
        )
        
        return AnonymizationResponse(
            anonymized_json=anonymized_json,
            statistics=statistics
        )
    except Exception as e:
        logger.error(f"Anonymization failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
```

### 6. Future Deanonymization Support

LLM-Guard's vault system enables deanonymization capabilities that we could add in the future if needed. The vault stores the mapping between original and anonymized values, allowing for reversible anonymization. This would be particularly useful for:

- Debugging anonymized outputs
- Temporary anonymization for processing
- Audit trails that need to be reversed

For now, we'll maintain one-way anonymization for security but keep the vault infrastructure in place for future enhancement.

## Custom Components to Retain

### 1. Date Shifting Algorithm
- **Purpose**: Maintain temporal relationships between dates
- **Implementation**: Post-process LLM-Guard results
- **Benefits**: Document coherence, realistic test data

### 2. Session Isolation
- **Purpose**: Security through isolated replacement mappings
- **Implementation**: New Vault instance per request
- **Benefits**: No information leakage between requests

### 3. Azure DI Structure Preservation
- **Purpose**: Maintain document structure and element IDs
- **Implementation**: Keep recursive JSON processing
- **Benefits**: Seamless integration with existing pipeline

## Migration Strategy

### Phase 1: Setup (Day 1)
1. Add LLM-Guard dependency
2. Verify AI4Privacy model downloads correctly
3. Create parallel implementation for testing

### Phase 2: Core Migration (Days 2-3)
1. Replace Presidio initialization with LLM-Guard
2. Update text anonymization logic
3. Implement date shifting post-processor
4. Maintain Azure DI recursive processing

### Phase 3: Testing (Days 4-5)
1. Compare detection accuracy (old vs new)
2. Verify date shifting consistency
3. Performance benchmarking
4. Edge case testing

### Phase 4: Cleanup (Day 6)
1. Remove Presidio dependencies
2. Update documentation
3. Add deanonymization endpoint
4. Update README

## Expected Improvements

### Detection Accuracy
- **Before**: 7 basic PII types (PERSON, DATE_TIME, LOCATION, etc.)
- **After**: 54 PII types including:
  - Financial: Bank accounts, credit cards, financial amounts
  - Medical: Diagnoses, medications, medical conditions
  - Personal: Age, gender, occupation, education
  - Technical: API keys, passwords, usernames
  - Legal: Case numbers, court names

### Performance
- Initial model load: ~3-5 seconds (one-time)
- Per-request overhead: Minimal (similar to current)
- ONNX optimization available for production

### User Experience
- Same API endpoints and contracts
- Better PII detection out of the box
- Consistent date relationships preserved
- Potential for future deanonymization features

## Risks and Mitigations

### Risk 1: Model Size
- **Issue**: AI4Privacy model is larger than spaCy
- **Mitigation**: Cache model in memory, use ONNX optimization

### Risk 2: Breaking Changes
- **Issue**: Different detection patterns might break tests
- **Mitigation**: Comprehensive testing phase, update test expectations

### Risk 3: Date Format Changes
- **Issue**: LLM-Guard might detect dates differently
- **Mitigation**: Robust date entity extraction from vault

## Success Criteria

1. All existing tests pass with updated expectations
2. Detection of at least 40+ PII types (vs current 7)
3. Date shifting maintains temporal consistency
4. No performance regression
5. Clean, maintainable code

## Future Enhancements

### 1. Stateless Deanonymization with Encrypted Keys

A potential future enhancement would be to implement stateless deanonymization that doesn't require database storage. This would work by encrypting the anonymization mappings and returning them as a "deanonymization key" alongside the anonymized content.

#### Technical Approach

**Encrypted Vault Serialization:**
- Serialize LLM-Guard's Vault (containing all replacement mappings) plus our custom date shift amount
- Encrypt the serialized data using AES-256-GCM with a server-side secret
- Return the encrypted blob as a base64-encoded "deanonymization key"
- To reverse: decrypt the key, reconstruct the vault, and apply deanonymization

**Implementation Sketch:**
```python
class DeanonymizationKey:
    def create_key(self, vault: Vault, date_shift: Optional[int]) -> str:
        """Create encrypted deanonymization key."""
        data = {
            "mappings": vault.get_all_mappings(),
            "date_shift": date_shift,
            "version": 1
        }
        
        # Serialize with msgpack (more compact than JSON)
        serialized = msgpack.packb(data)
        
        # Encrypt with server secret
        encrypted = self.cipher.encrypt(serialized)
        
        return base64.urlsafe_b64encode(encrypted).decode()
```

**Response Structure:**
```json
{
    "anonymized_json": {...},
    "statistics": {...},
    "deanonymization_key": "gAAAAABh3K4R..."  // Optional encrypted key
}
```

**Benefits:**
- Completely stateless - no database required
- Keys can be stored anywhere (client-side, S3, etc.)
- Secure with proper encryption
- Works with all features including date shifting
- Optional - only generate when explicitly requested

**Security Considerations:**
- Use strong server-side secrets (min 32 bytes)
- Consider key size limits for large documents
- Optional authentication for deanonymization endpoint
- Time-limited keys could be implemented by adding expiration

This approach would provide complete reversibility without any server-side storage, making it ideal for scenarios where temporary anonymization is needed for processing but the original data must be recoverable.

### 2. Multi-language Support
LLM-Guard supports Chinese detection out of the box, which could be enabled with minimal configuration changes.

### 3. Custom Patterns
Add domain-specific regex patterns for specialized PII types (case numbers, medical record IDs, etc.)

### 4. Vault Persistence
Optional Redis backend for multi-request sessions where consistent anonymization is needed across multiple API calls.

### 5. Batch Processing
Process multiple documents efficiently with shared model loading and parallel processing.

## Conclusion

This migration balances the benefits of LLM-Guard's superior detection with our custom requirements for date handling and session isolation. The result will be more accurate PII detection with minimal code complexity while preserving the features that make our system unique.