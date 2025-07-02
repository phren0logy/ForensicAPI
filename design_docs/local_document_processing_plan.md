# Local Document Processing with Docling - Implementation Plan

## Overview
This document outlines the plan for adding local document processing capabilities using the Docling library with OCR support. The initial implementation will provide a simple `/extract-local` endpoint that returns native Docling JSON and markdown output, with immediate OCR support using ocrmac on macOS.

## Implementation Plan for /extract-local Endpoint

### Phase 1: Dependencies and Setup

#### 1.1 Add Dependencies with numpy constraint
```bash
# Add docling with numpy version constraint for macOS compatibility
uv add docling "numpy<2.0.0"

# Add ocrmac for macOS OCR support
uv add ocrmac
```

#### 1.2 New Module Structure
```
routes/
├── extraction_docling.py    # New Docling-based local extraction with OCR
└── extraction.py           # Existing Azure DI extraction (unchanged)
```

### Phase 2: Core Implementation with OCR

#### 2.1 Basic Implementation with ocrmac
```python
# routes/extraction_docling.py
from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse
from docling.document_converter import DocumentConverter
from docling.datamodel.pipeline_options import PipelineOptions, OcrMacOptions
from pathlib import Path
import tempfile
import os
import platform

router = APIRouter()

@router.post("/extract-local")
async def extract_local(
    file: UploadFile = File(...),
    ocr_enabled: bool = Form(True),
    ocr_lang: str = Form("en")  # Language for OCR
):
    """
    Extract document locally using Docling with OCR support.
    Returns native Docling JSON and markdown.
    
    Args:
        file: PDF or DOCX file to process
        ocr_enabled: Enable OCR for scanned documents (default: True)
        ocr_lang: OCR language code (default: "en")
        
    Returns:
        {
            "markdown_content": str,  # Markdown representation
            "docling_document": dict, # Native DoclingDocument JSON
            "ocr_applied": bool      # Whether OCR was used
        }
    """
    # Validate file type
    allowed_types = [".pdf", ".docx", ".doc", ".pptx", ".html", ".md"]
    file_ext = os.path.splitext(file.filename)[1].lower()
    
    if file_ext not in allowed_types:
        return JSONResponse(
            status_code=400,
            content={"error": f"Unsupported file type: {file_ext}"}
        )
    
    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
        contents = await file.read()
        temp_file.write(contents)
        temp_file.flush()
        temp_path = temp_file.name
    
    try:
        # Configure pipeline options with OCR
        pipeline_options = PipelineOptions()
        
        if ocr_enabled:
            pipeline_options.do_ocr = True
            
            # Use ocrmac on macOS, fallback to EasyOCR on other platforms
            if platform.system() == "Darwin":  # macOS
                pipeline_options.ocr_options = OcrMacOptions(
                    lang=[ocr_lang] if ocr_lang != "auto" else None
                )
            else:
                # Fallback to EasyOCR for non-macOS systems
                from docling.datamodel.pipeline_options import EasyOcrOptions
                pipeline_options.ocr_options = EasyOcrOptions()
        
        # Initialize Docling converter with OCR options
        converter = DocumentConverter(
            pipeline_options=pipeline_options
        )
        
        # Convert document
        result = converter.convert_single(temp_path)
        
        # Check if OCR was actually applied
        ocr_applied = ocr_enabled and result.status == "success_with_ocr"
        
        # Extract outputs
        markdown_content = result.document.export_to_markdown()
        docling_json = result.document.export_to_dict()
        
        return JSONResponse(content={
            "markdown_content": markdown_content,
            "docling_document": docling_json,
            "ocr_applied": ocr_applied
        })
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Processing failed: {str(e)}"}
        )
    finally:
        os.remove(temp_path)
```

### Phase 3: Enhanced Error Handling and Validation

#### 3.1 Comprehensive Error Handling
```python
@router.post("/extract-local")
async def extract_local(
    file: UploadFile = File(...),
    ocr_enabled: bool = Form(True),
    ocr_lang: str = Form("en"),
    max_pages: int = Form(None)  # Limit pages for large documents
):
    # Size validation
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
    if file.size and file.size > MAX_FILE_SIZE:
        return JSONResponse(
            status_code=400,
            content={"error": "File size exceeds 100MB limit"}
        )
    
    # Platform-specific OCR availability check
    if ocr_enabled and platform.system() == "Darwin":
        try:
            import ocrmac
        except ImportError:
            return JSONResponse(
                status_code=500,
                content={
                    "error": "ocrmac not installed. Run: pip install ocrmac",
                    "suggestion": "Disable OCR or install ocrmac"
                }
            )
    
    # ... rest of implementation
```

### Phase 4: Testing Implementation

#### 4.1 Test Structure
```
tests/
├── test_extraction_docling.py   # Tests for Docling endpoint
└── fixtures_docling/            # Test fixtures
    ├── text_document.pdf        # Regular text PDF
    ├── scanned_document.pdf     # Scanned PDF requiring OCR
    ├── mixed_content.pdf        # Mixed text and scanned content
    ├── sample.docx
    └── expected_outputs/
        ├── text_document_markdown.md
        ├── scanned_document_ocr_markdown.md
        └── *.json
```

#### 4.2 OCR-Specific Tests
```python
# tests/test_extraction_docling.py
import platform
import pytest

def test_extract_local_with_ocr():
    """Test local extraction with OCR enabled."""
    with open("tests/fixtures_docling/scanned_document.pdf", "rb") as f:
        response = client.post(
            "/extract-local",
            files={"file": ("scanned.pdf", f, "application/pdf")},
            data={"ocr_enabled": "true", "ocr_lang": "en"}
        )
    
    assert response.status_code == 200
    result = response.json()
    
    # Verify OCR was applied
    assert result.get("ocr_applied") is True
    assert len(result["markdown_content"]) > 0
    
    # Check for extracted text from scanned content
    assert "expected_scanned_text" in result["markdown_content"]

@pytest.mark.skipif(platform.system() != "Darwin", reason="ocrmac only on macOS")
def test_ocrmac_specific():
    """Test ocrmac-specific functionality on macOS."""
    # Test with various OCR languages
    for lang in ["en", "es", "fr"]:
        response = client.post(
            "/extract-local",
            files={"file": ("test.pdf", create_test_pdf(), "application/pdf")},
            data={"ocr_enabled": "true", "ocr_lang": lang}
        )
        assert response.status_code == 200

def test_extract_local_without_ocr():
    """Test extraction with OCR disabled."""
    with open("tests/fixtures_docling/text_document.pdf", "rb") as f:
        response = client.post(
            "/extract-local",
            files={"file": ("text.pdf", f, "application/pdf")},
            data={"ocr_enabled": "false"}
        )
    
    assert response.status_code == 200
    result = response.json()
    assert result.get("ocr_applied") is False
```

### Phase 5: Integration and Documentation

#### 5.1 Update Dependencies
```toml
# pyproject.toml
[project]
dependencies = [
    # ... existing dependencies
    "docling>=2.0.0",
    "numpy<2.0.0",  # Required for macOS compatibility
    "ocrmac>=0.1.0; platform_system=='Darwin'",  # macOS only
]
```

#### 5.2 Environment Configuration
```python
# Add to .env.example
# OCR Configuration
OCR_DEFAULT_ENABLED=true
OCR_DEFAULT_LANG=en
OCR_MAX_FILE_SIZE_MB=100
```

#### 5.3 API Documentation
```python
# Add comprehensive docstring
"""
Extract document locally using Docling with OCR support.

This endpoint processes documents locally without sending data to external services.
OCR is automatically applied to scanned content when enabled.

Supported formats: PDF, DOCX, DOC, PPTX, HTML, MD

OCR Support:
- macOS: Uses native Vision framework via ocrmac (fast, accurate)
- Other platforms: Falls back to EasyOCR

Parameters:
- file: Document file to process
- ocr_enabled: Enable OCR for scanned content (default: true)
- ocr_lang: OCR language (default: "en", use "auto" for detection)

Returns Docling's native JSON format with hierarchical document structure.
"""
```

## Format Comparison Reference

### Azure Document Intelligence vs Docling

| Feature | Azure DI | Docling |
|---------|----------|---------|
| Structure | Flat arrays | Hierarchical tree |
| Coordinates | Polygon arrays | LTRB bounding boxes |
| Text References | Global offset/length | Local charspan |
| Element Types | paragraphs, tables, etc. | texts with labels |
| Page Info | Detailed words/lines | Size only |
| OCR | Cloud-based | Local (ocrmac/EasyOCR) |

## Future Enhancements

### 1. Azure DI Format Conversion
- Create `extraction_adapter.py` module with conversion functions
- Map Docling hierarchical structure to Azure DI flat arrays
- Convert bbox coordinates to polygon format
- Calculate global text offsets and spans
- Enable seamless switching between processors

### 2. Element ID Integration
- Port `add_ids_to_elements()` function to work with Docling format
- Add IDs to texts, tables, and pictures
- Ensure ID format compatibility: `{element_type}_{page}_{index}_{hash}`
- Enable filtering and segmentation compatibility

### 3. Advanced OCR Features
- **Language Auto-Detection**: Implement automatic language detection
- **Multi-Language Support**: Process documents with mixed languages
- **OCR Confidence Scores**: Expose OCR confidence metrics
- **Custom OCR Models**: Allow pluggable OCR engines

### 4. Performance Optimization
- Parallel page processing for large documents
- OCR result caching
- Streaming response for real-time feedback
- GPU acceleration for EasyOCR on supported systems

## Success Criteria

1. **Immediate Goals**
   - Successfully extract text from both regular and scanned PDFs
   - OCR works reliably on macOS with ocrmac
   - Graceful fallback to EasyOCR on other platforms
   - Handle common document types without errors

2. **Performance Targets**
   - Process 50-page text document in <10 seconds
   - OCR processing: <2 seconds per page on macOS
   - Memory usage under 2GB for typical documents

3. **Quality Metrics**
   - OCR accuracy >95% for printed text
   - Preserve document structure and layout
   - Maintain reading order with OCR content

## Timeline

**Week 1**: OCR-enabled implementation
- Implement extraction_docling.py with ocrmac support
- Test OCR on various document types
- Handle platform-specific OCR selection

**Week 2**: Testing and optimization
- Create comprehensive test suite with OCR cases
- Performance benchmarking
- Error handling refinement

**Week 3**: Documentation and deployment
- API documentation with OCR examples
- Deployment guide with OCR dependencies
- Performance tuning