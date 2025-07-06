# Extraction Endpoint Unification Design Document

## Overview

This document outlines the plan to unify the response formats of the `/extract` (Azure Document Intelligence) and `/extract-local` (Docling) endpoints while preserving the unique characteristics of each processing engine.

## Current State

### `/extract` Endpoint (Azure DI)
- **Path**: `/extract`
- **Processor**: Azure Document Intelligence
- **Current Response Format**:
```json
{
    "markdown_content": "string",
    "analysis_result": {
        // Azure DI format with optional element IDs
        "content": "string",
        "pages": [...],
        "paragraphs": [...],
        "tables": [...],
        // ... other Azure DI fields
    }
}
```

### `/extract-local` Endpoint (Docling)
- **Path**: `/extract-local`
- **Processor**: Docling with OCR support
- **Current Response Format**:
```json
{
    "markdown_content": "string",
    "docling_document": {
        // Raw DoclingDocument format
        "schema_name": "DoclingDocument",
        "version": "1.5.0",
        "body": {...},
        "texts": [...],
        "tables": [...],
        // ... other Docling fields
    },
    "ocr_applied": true,
    "metadata": {
        "filename": "string",
        "file_size_bytes": 12345,
        "ocr_enabled": true,
        "ocr_platform": "ocrmac",
        "pages_processed": 10
    }
}
```

## Proposed Unified Format

Both endpoints will adopt the following response structure:

```json
{
    "markdown_content": "string",
    "json_content": {
        // Unmodified processor-specific JSON
        // For Azure DI: Current analysis_result content
        // For Docling: Current docling_document content
    },
    "metadata": {
        // Common fields
        "page_count": 10,
        "processing_type": "azure_di" | "docling",
        "processing_time": 1.234,
        "file_size": 123456,
        "filename": "document.pdf",
        
        // Azure DI specific (when processing_type == "azure_di")
        "batch_size": 1500,
        "element_ids_included": true,
        
        // Docling specific (when processing_type == "docling")
        "ocr_applied": true,
        "ocr_platform": "ocrmac" | "easyocr",
        "ocr_enabled": true
    }
}
```

## Key Design Decisions

1. **Preserve Original JSON**: The `json_content` field contains the unmodified output from each processor
2. **Unified Metadata**: Common metadata structure with processor-specific extensions
3. **Parallel Naming**: `markdown_content` and `json_content` create semantic symmetry
4. **Processor Identification**: `processing_type` field clearly identifies which engine was used

## Implementation Plan

### Phase 1: Update Response Structures

#### 1.1 Update `/extract` Endpoint (routes/extraction.py)

**Changes Required**:
- Add timing measurement around processing
- Rename `analysis_result` to `json_content` in response
- Add metadata construction with:
  - Common fields: page_count, processing_type, processing_time, file_size, filename
  - Azure-specific fields: batch_size, element_ids_included

**Code Changes**:
```python
# Before
response_content = {
    "markdown_content": markdown_content,
    "analysis_result": analysis_result_with_ids
}

# After
import time
start_time = time.time()
# ... processing ...
processing_time = time.time() - start_time

response_content = {
    "markdown_content": markdown_content,
    "json_content": analysis_result_with_ids,
    "metadata": {
        "page_count": total_pages,
        "processing_type": "azure_di",
        "processing_time": processing_time,
        "file_size": file.size,
        "filename": file.filename,
        "batch_size": batch_size,
        "element_ids_included": include_element_ids
    }
}
```

#### 1.2 Update `/extract-local` Endpoint (routes/extraction_docling.py)

**Changes Required**:
- Rename `docling_document` to `json_content`
- Move OCR fields from top-level into metadata
- Remove existing metadata field
- Extract page count from Docling structure

**Code Changes**:
```python
# Before
response_data = {
    "markdown_content": markdown_content,
    "docling_document": docling_json,
    "ocr_applied": ocr_applied,
    "metadata": {
        "filename": file.filename,
        "file_size_bytes": file.size,
        "ocr_enabled": ocr_enabled,
        "ocr_platform": "ocrmac" if platform.system() == "Darwin" else "easyocr",
        "pages_processed": len(docling_json.get("pages", {})),
    },
}

# After
import time
start_time = time.time()
# ... processing ...
processing_time = time.time() - start_time

response_data = {
    "markdown_content": markdown_content,
    "json_content": docling_json,
    "metadata": {
        "page_count": len(docling_json.get("pages", {})),
        "processing_type": "docling",
        "processing_time": processing_time,
        "file_size": file.size,
        "filename": file.filename,
        "ocr_applied": ocr_applied,
        "ocr_enabled": ocr_enabled,
        "ocr_platform": "ocrmac" if platform.system() == "Darwin" else "easyocr"
    }
}
```

### Phase 2: Update Downstream Dependencies

#### 2.1 Update Segmentation Endpoints (routes/segmentation.py)

**Changes Required**:
- Update `SegmentationInput` model to use `json_content` instead of `analysis_result`
- Update `FilteredSegmentationInput` model similarly
- Update any references in the code

**Code Changes**:
```python
class SegmentationInput(BaseModel):
    source_file: str
    json_content: Dict[str, Any]  # Changed from analysis_result
    min_segment_tokens: int = 10000
    max_segment_tokens: int = 30000

# Update function calls
rich_segments = create_rich_segments(
    payload.json_content,  # Changed from payload.analysis_result
    payload.source_file,
    payload.min_segment_tokens,
    payload.max_segment_tokens
)
```

#### 2.2 Update Filtering Module (routes/filtering.py)

- Search for any references to `analysis_result` and update to `json_content`

### Phase 3: Update Tests

#### 3.1 Update test_extraction_azure.py
- Update assertions to check for `json_content` instead of `analysis_result`
- Add tests for metadata structure

#### 3.2 Update test_extraction_docling.py
- Update assertions for new response structure
- Remove checks for top-level `ocr_applied`
- Add metadata validation

#### 3.3 Update test_extraction_comparison.py
- Update field references in comparison logic
- Add metadata comparison tests

#### 3.4 Update test_segmentation.py
- Update test payloads to use `json_content`

### Phase 4: Update Documentation and Examples

#### 4.1 Update API Documentation
- Document the unified response format
- Explain processor-specific metadata fields
- Note breaking changes

#### 4.2 Update Example Scripts
- Update any example code that uses the endpoints
- Add migration examples

#### 4.3 Update CLAUDE.md
- Document the new unified format
- Update any instructions about using the extraction endpoints

## Migration Guide

### For Clients Using `/extract`
```python
# Old
result = response.json()
azure_data = result["analysis_result"]

# New
result = response.json()
azure_data = result["json_content"]
processor = result["metadata"]["processing_type"]  # "azure_di"
```

### For Clients Using `/extract-local`
```python
# Old
result = response.json()
docling_data = result["docling_document"]
ocr_applied = result["ocr_applied"]

# New
result = response.json()
docling_data = result["json_content"]
ocr_applied = result["metadata"]["ocr_applied"]
processor = result["metadata"]["processing_type"]  # "docling"
```

### For Clients Using Segmentation
```python
# Old
payload = {
    "source_file": "document.pdf",
    "analysis_result": azure_result,
    "min_segment_tokens": 10000
}

# New
payload = {
    "source_file": "document.pdf",
    "json_content": azure_result,
    "min_segment_tokens": 10000
}
```

## Benefits

1. **Consistency**: Unified response structure across extraction endpoints
2. **Clarity**: Clear parallel between `markdown_content` and `json_content`
3. **Flexibility**: Processor-specific metadata without breaking the common structure
4. **Future-Proof**: Easy to add new processors with the same format
5. **Discoverability**: `processing_type` makes it clear which engine was used

## Risks and Mitigations

### Risk 1: Breaking Changes
- **Impact**: All clients must update their code
- **Mitigation**: Provide clear migration guide and examples

### Risk 2: Segmentation Compatibility
- **Impact**: Segmentation still only works with Azure DI format
- **Mitigation**: Document this limitation clearly; plan future work to support Docling

### Risk 3: Test Coverage
- **Impact**: Tests may miss edge cases during migration
- **Mitigation**: Comprehensive test updates in Phase 3

## Future Enhancements

1. **Format Conversion**: Add optional parameter to convert Docling format to Azure DI-compatible structure
2. **Unified Segmentation**: Update segmentation to handle both JSON formats natively
3. **Additional Processors**: Easy to add new extraction engines (e.g., PDF.js, Apache Tika)
4. **Streaming Support**: Consider streaming responses for large documents

## Timeline

- Phase 1: 2-3 hours (Update response structures)
- Phase 2: 1-2 hours (Update downstream dependencies)
- Phase 3: 2-3 hours (Update and run all tests)
- Phase 4: 1 hour (Update documentation)

Total estimated time: 6-9 hours

## Success Criteria

1. Both endpoints return the unified format
2. All existing tests pass with updates
3. Segmentation works with Azure DI format (unchanged)
4. Documentation is updated
5. No loss of functionality or data