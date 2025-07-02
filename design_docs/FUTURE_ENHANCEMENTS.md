# Future Enhancements

This document serves as a living reference for all planned and possible future enhancements to the ForensicAPI document processing system. It consolidates unimplemented features from previous design documents and tracks new enhancement ideas.

**Note**: The system has already migrated from Presidio to LLM-Guard for anonymization, providing 54 PII types detection with the AI4Privacy BERT model.

## Table of Contents

1. [Anonymization Enhancements](#anonymization-enhancements)
2. [Document Processing Enhancements](#document-processing-enhancements)
3. [Performance Optimizations](#performance-optimizations)
4. [Configuration and DevOps](#configuration-and-devops)
5. [Testing and Quality](#testing-and-quality)

## Anonymization Enhancements

### 1. Stateless Deanonymization with Encrypted Keys
**Priority**: High | **Complexity**: Medium

Enable reversible anonymization without server-side storage by encrypting the anonymization mappings and returning them as a "deanonymization key".

**Technical Approach**:
- Serialize LLM-Guard's Vault containing all replacement mappings
- Encrypt using AES-256-GCM with server-side secret
- Return encrypted blob as base64-encoded key
- Implement `/deanonymize` endpoint that accepts the key

**Implementation Details**:
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

**Benefits**:
- Completely stateless operation
- Keys can be stored anywhere (client-side, S3, etc.)
- Secure with proper encryption
- Optional time-limited keys possible

### 2. Multi-language Support
**Priority**: Medium | **Complexity**: Low

Extend anonymization to support multiple languages beyond English.

**Features**:
- Enable Chinese detection (already available in LLM-Guard)
- Add language auto-detection
- Support mixed-language documents
- Configure language-specific PII patterns

### 3. Custom PII Pattern Support
**Priority**: Low | **Complexity**: Low

Add ability to define domain-specific regex patterns for specialized PII types.

**Use Cases**:
- Case numbers in specific formats
- Medical record IDs
- Custom identifiers
- Industry-specific codes

### 4. Vault Persistence
**Priority**: Low | **Complexity**: Medium

Implement optional Redis backend for maintaining consistent anonymization across multiple API calls in a session.

**Features**:
- Session-based vault storage
- TTL for automatic cleanup
- Optional feature flag
- Useful for multi-step document processing

### 5. Batch Anonymization
**Priority**: Low | **Complexity**: Medium

Process multiple documents efficiently with shared model loading and parallel processing.

**Implementation**:
- Accept array of documents
- Share model across documents
- Parallel processing with asyncio
- Aggregate statistics


### 6. Bates Numbers and Case Numbers Redaction
**Priority**: Medium | **Complexity**: Low

Special handling for Bates numbers and case numbers in documents, particularly in Azure DI Layout model Markdown footers.

**Features**:
- Detect common Bates number patterns (e.g., "BATES-001234", "DEF00012345")
- Detect case number patterns (e.g., "Case No. 1:23-cv-45678", "Docket No. 12-3456")
- Option to redact or preserve based on configuration
- Maintain document structure and readability
- Custom pattern configuration support

## Document Processing Enhancements

### 1. Azure DI Format Conversion
**Priority**: High | **Complexity**: High

Create adapter to convert Docling output to Azure Document Intelligence format for seamless pipeline integration.

**Components**:
- `extraction_adapter.py` module
- Map hierarchical structure to flat arrays
- Convert bbox coordinates to polygon format
- Calculate global text offsets and spans
- Preserve all metadata

**Implementation Approach**:
```python
def convert_docling_to_azure_di(docling_doc: Dict) -> Dict:
    """Convert Docling hierarchical format to Azure DI flat format."""
    azure_di = {
        "status": "succeeded",
        "content": "",
        "pages": [],
        "paragraphs": [],
        "tables": [],
        "figures": []
    }
    
    # Traverse Docling tree and flatten
    # Convert coordinates
    # Calculate offsets
    
    return azure_di
```

### 2. Element ID Integration for Docling
**Priority**: High | **Complexity**: Medium

Port the element ID generation system to work with Docling-extracted documents.

**Requirements**:
- Generate IDs in format: `{element_type}_{page}_{index}_{hash}`
- Ensure compatibility with filtering and segmentation
- Preserve IDs through processing pipeline
- Add `include_element_ids` parameter


### 3. Streaming Document Processing
**Priority**: Low | **Complexity**: High

Implement streaming response for real-time processing feedback on large documents.

**Features**:
- Server-sent events for progress updates
- Page-by-page results
- Early termination support
- Memory-efficient processing

## Performance Optimizations

### 1. Model Optimization
**Priority**: Medium | **Complexity**: Medium

Optimize AI models for production performance.

**Approaches**:
- ONNX conversion for LLM-Guard models
- Model quantization
- Batch inference optimization
- GPU acceleration where available

### 2. Caching Layer
**Priority**: Medium | **Complexity**: Medium

Implement intelligent caching for frequently processed content.

**Features**:
- Cache anonymization results for repeated text
- OCR result caching
- Document extraction caching
- Redis-based distributed cache

### 3. Parallel Processing
**Priority**: Medium | **Complexity**: Medium

Enhance throughput with parallel processing capabilities.

**Areas**:
- Parallel page processing for large PDFs
- Concurrent OCR for multi-page documents
- Batch API endpoint processing
- Async processing throughout

### 4. GPU Acceleration
**Priority**: Low | **Complexity**: High

Enable GPU acceleration for supported operations.

**Components**:
- EasyOCR GPU support
- BERT model GPU inference
- Parallel document processing
- Auto-detection of GPU availability

## Configuration and DevOps

### 1. Environment Configuration
**Priority**: Medium | **Complexity**: Low

Add comprehensive environment variable support for all features.

**New Variables**:
```bash
# OCR Configuration
OCR_DEFAULT_ENABLED=true
OCR_DEFAULT_LANG=en
OCR_MAX_FILE_SIZE_MB=100

# Anonymization
ANONYMIZATION_DEFAULT_THRESHOLD=0.5
ANONYMIZATION_CACHE_ENABLED=false

# Performance
ENABLE_GPU_ACCELERATION=auto
MAX_PARALLEL_WORKERS=4
```

### 2. Deployment Documentation
**Priority**: Medium | **Complexity**: Low

Create comprehensive deployment guides.

**Documents**:
- OCR dependencies installation guide
- Production deployment best practices
- Scaling recommendations
- Security hardening guide

### 3. Monitoring and Metrics
**Priority**: Low | **Complexity**: Medium

Add comprehensive monitoring capabilities.

**Features**:
- Prometheus metrics export
- Processing time tracking
- Error rate monitoring
- Model performance metrics

## Testing and Quality

### 1. Performance Benchmarking Suite
**Priority**: Medium | **Complexity**: Medium

Comprehensive performance testing framework.

**Components**:
- Automated benchmark runs
- Performance regression detection
- Memory usage profiling
- Comparative analysis tools

### 2. Integration Test Suite
**Priority**: Medium | **Complexity**: Medium

Expand test coverage for complex scenarios.

**Areas**:
- Multi-language document tests
- Large document processing
- Edge case handling
- Error recovery testing

### 3. Load Testing
**Priority**: Low | **Complexity**: Medium

Implement load testing for production readiness.

**Tools**:
- Locust or K6 integration
- Realistic workload simulation
- Bottleneck identification
- Scaling validation

## Implementation Prioritization

### Phase 1: Critical Features (1-2 months)
1. Azure DI Format Conversion
2. Element ID Integration for Docling
3. Stateless Deanonymization

### Phase 2: Enhancement Features (2-3 months)
1. Model Optimization
2. Multi-language Support
3. Environment Configuration
4. Bates Numbers and Case Numbers Redaction

### Phase 3: Performance & Scale (3-4 months)
1. Caching Layer
2. Parallel Processing
3. Performance Benchmarking
4. Deployment Documentation

### Phase 4: Advanced Features (4+ months)
1. Streaming Processing
2. GPU Acceleration
3. Monitoring and Metrics
4. Custom PII Patterns

## Notes

- This document will be updated as new enhancement ideas arise
- Each enhancement should include priority, complexity, and implementation approach
- Completed enhancements should be moved to a "Completed" section with implementation date
- Breaking changes should be clearly marked with migration guides