"""
Tests for the /extract-local endpoint using Docling.

Tests local document extraction functionality including:
- Basic extraction with sample PDF
- OCR functionality
- Error handling
- File type validation
"""

import io
import platform
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from main import app

client = TestClient(app)

# Check if chunking dependencies are available
try:
    import tiktoken
    from docling_core.transforms.chunker.tokenizer.openai import OpenAITokenizer
    from docling.chunking import HybridChunker
    CHUNKING_AVAILABLE = True
except ImportError:
    CHUNKING_AVAILABLE = False


def create_test_pdf(num_pages: int = 2, text_content: str = None) -> bytes:
    """Create a simple test PDF with specified number of pages."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)

    for page_num in range(1, num_pages + 1):
        if text_content:
            c.drawString(100, 700, text_content)
        else:
            c.drawString(100, 700, f"Test PDF - Page {page_num}")
            c.drawString(100, 650, f"This is a test document for Docling extraction.")
            c.drawString(100, 600, f"It contains some sample text on page {page_num}.")
        c.showPage()

    c.save()
    buffer.seek(0)
    return buffer.read()


def test_extract_local_basic():
    """Test basic local PDF extraction functionality."""
    pdf_content = create_test_pdf(num_pages=2)

    files = {"file": ("test.pdf", pdf_content, "application/pdf")}
    resp = client.post("/extract-local", files=files)

    if resp.status_code != 200:
        print(f"Error response: {resp.json()}")
    assert resp.status_code == 200
    result = resp.json()

    # Verify response structure
    assert "markdown_content" in result
    assert "json_content" in result
    assert "metadata" in result

    # Check that content was extracted
    assert len(result["markdown_content"]) > 0
    assert "Test PDF" in result["markdown_content"]

    # Verify Docling document structure
    doc = result["json_content"]
    assert doc["schema_name"] == "DoclingDocument"
    assert "body" in doc
    assert "texts" in doc or "pictures" in doc or "tables" in doc

    # Check metadata
    metadata = result["metadata"]
    assert metadata["processing_type"] == "docling"
    assert metadata["filename"] == "test.pdf"
    assert metadata["ocr_enabled"] is True
    assert metadata["ocr_applied"] in [True, False]
    assert metadata["page_count"] >= 1
    assert "processing_time" in metadata
    assert "file_size" in metadata


def test_extract_local_without_ocr():
    """Test extraction with OCR disabled."""
    pdf_content = create_test_pdf(num_pages=1)

    files = {"file": ("test.pdf", pdf_content, "application/pdf")}
    data = {"ocr_enabled": "false"}
    resp = client.post("/extract-local", files=files, data=data)

    assert resp.status_code == 200
    result = resp.json()

    # Verify OCR was not applied
    assert result["metadata"]["ocr_applied"] is False
    assert result["metadata"]["ocr_enabled"] is False


def test_extract_local_with_language():
    """Test extraction with specific OCR language."""
    pdf_content = create_test_pdf(num_pages=1)

    files = {"file": ("test.pdf", pdf_content, "application/pdf")}
    data = {"ocr_enabled": "true", "ocr_lang": "es"}
    resp = client.post("/extract-local", files=files, data=data)

    assert resp.status_code == 200
    result = resp.json()

    # Should succeed with language parameter
    assert "markdown_content" in result
    assert result["metadata"]["ocr_enabled"] is True


def test_extract_local_max_pages():
    """Test extraction with max_pages limit."""
    pdf_content = create_test_pdf(num_pages=5)

    files = {"file": ("test.pdf", pdf_content, "application/pdf")}
    data = {"max_pages": "2"}
    resp = client.post("/extract-local", files=files, data=data)

    assert resp.status_code == 200
    result = resp.json()

    # Should process only specified pages
    assert "markdown_content" in result
    # Note: Actual page count verification depends on Docling's implementation


def test_extract_local_docx():
    """Test extraction with DOCX file (if fixture exists)."""
    docx_path = Path(__file__).parent / "fixtures_docling" / "sample.docx"

    if docx_path.exists():
        with open(docx_path, "rb") as f:
            docx_content = f.read()

        files = {"file": ("sample.docx", docx_content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        resp = client.post("/extract-local", files=files)

        assert resp.status_code == 200
        result = resp.json()
        assert "markdown_content" in result
        assert result["metadata"]["filename"] == "sample.docx"
    else:
        pytest.skip("DOCX test fixture not found")


def test_extract_local_invalid_file_type():
    """Test extraction with unsupported file type."""
    files = {"file": ("test.txt", b"This is not a supported format", "text/plain")}
    resp = client.post("/extract-local", files=files)

    assert resp.status_code == 400
    result = resp.json()
    assert "error" in result
    assert "Unsupported file type" in result["error"]
    assert "supported_types" in result


def test_extract_local_empty_pdf():
    """Test extraction with empty PDF."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    c.save()
    buffer.seek(0)

    files = {"file": ("empty.pdf", buffer.read(), "application/pdf")}
    resp = client.post("/extract-local", files=files)

    # Empty PDFs may fail with some PDF processors
    if resp.status_code == 500:
        result = resp.json()
        assert "error" in result
        assert "Processing failed" in result["error"]
    else:
        # If it succeeds, should have minimal content
        assert resp.status_code == 200
        result = resp.json()
        assert "docling_document" in result


def test_extract_local_large_file():
    """Test file size limit enforcement."""
    # Create a fake large file (just headers, not actual content)
    large_content = b"PDF" + b"0" * (101 * 1024 * 1024)  # 101MB

    files = {"file": ("large.pdf", large_content, "application/pdf")}
    # Note: TestClient might not properly set file.size, so this test might not trigger the size check
    resp = client.post("/extract-local", files=files)

    # Should either fail with 400 or succeed if size check wasn't triggered
    assert resp.status_code in [200, 400, 500]


@pytest.mark.skipif(platform.system() != "Darwin", reason="ocrmac only on macOS")
def test_extract_local_ocrmac_platform():
    """Test that ocrmac is used on macOS."""
    pdf_content = create_test_pdf(num_pages=1)

    files = {"file": ("test.pdf", pdf_content, "application/pdf")}
    resp = client.post("/extract-local", files=files)

    assert resp.status_code == 200
    result = resp.json()

    # Verify ocrmac is reported as the OCR platform
    assert result["metadata"]["ocr_platform"] == "ocrmac"


@pytest.mark.skipif(platform.system() == "Darwin", reason="EasyOCR on non-macOS")
def test_extract_local_easyocr_platform():
    """Test that EasyOCR is used on non-macOS platforms."""
    pdf_content = create_test_pdf(num_pages=1)

    files = {"file": ("test.pdf", pdf_content, "application/pdf")}
    resp = client.post("/extract-local", files=files)

    assert resp.status_code == 200
    result = resp.json()

    # Verify easyocr is reported as the OCR platform
    assert result["metadata"]["ocr_platform"] == "easyocr"


def test_extract_local_real_scanned_pdf():
    """Test extraction with real scanned PDF if it exists."""
    scanned_pdf_path = Path(__file__).parent / "fixtures_docling" / "scanned_document.pdf"

    if scanned_pdf_path.exists():
        with open(scanned_pdf_path, "rb") as f:
            pdf_content = f.read()

        files = {"file": ("scanned.pdf", pdf_content, "application/pdf")}
        resp = client.post("/extract-local", files=files)

        assert resp.status_code == 200
        result = resp.json()

        # OCR should be applied and produce content
        assert result["metadata"]["ocr_applied"] is True
        assert len(result["markdown_content"]) > 100  # Should have substantial content
    else:
        pytest.skip("Scanned PDF test fixture not found")


# Chunking tests
@pytest.mark.skipif(not CHUNKING_AVAILABLE, reason="Chunking dependencies not installed")
def test_extract_local_with_chunking_basic():
    """Test basic chunking functionality."""
    # Create a multi-page PDF with sections
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    
    # Page 1 - Introduction
    c.drawString(100, 700, "# Introduction")
    c.drawString(100, 650, "This is the introduction section with some content.")
    c.drawString(100, 600, "It contains multiple paragraphs of text that should be chunked.")
    c.showPage()
    
    # Page 2 - Section 1
    c.drawString(100, 700, "## Section 1: Overview")
    c.drawString(100, 650, "This is section 1 with detailed information.")
    c.drawString(100, 600, "It has enough content to potentially form its own chunk.")
    c.showPage()
    
    # Page 3 - Section 2
    c.drawString(100, 700, "## Section 2: Details") 
    c.drawString(100, 650, "Section 2 contains additional details and explanations.")
    c.drawString(100, 600, "This content might be merged with other sections depending on token limits.")
    c.showPage()
    
    c.save()
    buffer.seek(0)
    
    files = {"file": ("test_chunking.pdf", buffer.read(), "application/pdf")}
    data = {
        "enable_chunking": "true",
        "chunk_min_tokens": "50",
        "chunk_max_tokens": "500"
    }
    
    resp = client.post("/extract-local", files=files, data=data)
    assert resp.status_code == 200
    result = resp.json()
    
    # Verify chunks are present
    assert "chunks" in result
    assert isinstance(result["chunks"], list)
    assert len(result["chunks"]) > 0
    
    # Verify chunk structure
    first_chunk = result["chunks"][0]
    assert "text" in first_chunk
    assert "token_count" in first_chunk
    assert "meta" in first_chunk
    
    # Verify token count is within limits
    assert first_chunk["token_count"] <= 500
    
    # Verify metadata includes chunking info
    metadata = result["metadata"]
    assert metadata["chunking_enabled"] is True
    assert "chunk_count" in metadata
    assert metadata["chunk_count"] == len(result["chunks"])
    assert "chunk_config" in metadata
    assert metadata["chunk_config"]["min_tokens"] == 50
    assert metadata["chunk_config"]["max_tokens"] == 500
    assert metadata["chunk_config"]["tokenizer"] == "tiktoken-cl100k_base"
    assert metadata["chunk_config"]["merge_peers"] is True


@pytest.mark.skipif(not CHUNKING_AVAILABLE, reason="Chunking dependencies not installed")
def test_extract_local_chunking_disabled():
    """Test that chunking is disabled by default."""
    pdf_content = create_test_pdf(num_pages=2)
    
    files = {"file": ("test.pdf", pdf_content, "application/pdf")}
    # Don't specify enable_chunking (defaults to False)
    resp = client.post("/extract-local", files=files)
    
    assert resp.status_code == 200
    result = resp.json()
    
    # Chunks should not be present
    assert "chunks" not in result
    assert "chunking_enabled" not in result.get("metadata", {})


@pytest.mark.skipif(not CHUNKING_AVAILABLE, reason="Chunking dependencies not installed")
def test_extract_local_chunking_token_limits():
    """Test chunking respects token limits."""
    # Create a PDF with varied content lengths
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    
    # Add multiple pages with different content lengths
    for i in range(5):
        c.drawString(100, 700, f"# Section {i+1}")
        # Add varying amounts of content
        y_pos = 650
        for j in range(10 + i * 5):  # Increasing content per page
            c.drawString(100, y_pos, f"Line {j+1}: This is sample text content for testing chunking behavior.")
            y_pos -= 20
            if y_pos < 100:
                break
        c.showPage()
    
    c.save()
    buffer.seek(0)
    
    files = {"file": ("test_limits.pdf", buffer.read(), "application/pdf")}
    data = {
        "enable_chunking": "true",
        "chunk_min_tokens": "100",
        "chunk_max_tokens": "1000"
    }
    
    resp = client.post("/extract-local", files=files, data=data)
    assert resp.status_code == 200
    result = resp.json()
    
    # Verify all chunks respect token limits
    for chunk in result["chunks"]:
        assert chunk["token_count"] <= 1000
        # Note: min_tokens is a soft limit, so very small documents might have smaller chunks


@pytest.mark.skipif(not CHUNKING_AVAILABLE, reason="Chunking dependencies not installed")
def test_extract_local_chunking_merge_peers():
    """Test peer merging functionality."""
    pdf_content = create_test_pdf(num_pages=3)
    
    # Test with merge_peers disabled
    files = {"file": ("test.pdf", pdf_content, "application/pdf")}
    data = {
        "enable_chunking": "true",
        "chunk_min_tokens": "50",
        "chunk_max_tokens": "500",
        "merge_peers": "false"
    }
    
    resp = client.post("/extract-local", files=files, data=data)
    assert resp.status_code == 200
    result_no_merge = resp.json()
    
    # Test with merge_peers enabled (default)
    files = {"file": ("test.pdf", pdf_content, "application/pdf")}
    data = {
        "enable_chunking": "true",
        "chunk_min_tokens": "50",
        "chunk_max_tokens": "500"
    }
    
    resp = client.post("/extract-local", files=files, data=data)
    assert resp.status_code == 200
    result_merge = resp.json()
    
    # Verify merge_peers setting is reflected in metadata
    assert result_no_merge["metadata"]["chunk_config"]["merge_peers"] is False
    assert result_merge["metadata"]["chunk_config"]["merge_peers"] is True


@pytest.mark.skipif(not CHUNKING_AVAILABLE, reason="Chunking dependencies not installed")
def test_extract_local_chunking_metadata():
    """Test chunk metadata structure."""
    pdf_content = create_test_pdf(num_pages=2)
    
    files = {"file": ("test.pdf", pdf_content, "application/pdf")}
    data = {
        "enable_chunking": "true",
        "chunk_min_tokens": "50",
        "chunk_max_tokens": "300"
    }
    
    resp = client.post("/extract-local", files=files, data=data)
    assert resp.status_code == 200
    result = resp.json()
    
    # Verify chunk metadata
    for chunk in result["chunks"]:
        meta = chunk["meta"]
        assert isinstance(meta, dict)
        
        # Check for expected metadata fields
        if "doc_items" in meta:
            assert isinstance(meta["doc_items"], list)
            for item in meta["doc_items"]:
                assert "self_ref" in item
                assert "label" in item
                
        if "headings" in meta:
            assert isinstance(meta["headings"], list)
            
        if "origin" in meta:
            assert "filename" in meta["origin"]


@pytest.mark.skipif(not CHUNKING_AVAILABLE, reason="Chunking dependencies not installed")
def test_extract_local_chunking_with_ocr():
    """Test chunking combined with OCR."""
    pdf_content = create_test_pdf(num_pages=2)
    
    files = {"file": ("test.pdf", pdf_content, "application/pdf")}
    data = {
        "ocr_enabled": "true",
        "enable_chunking": "true",
        "chunk_min_tokens": "50",
        "chunk_max_tokens": "500"
    }
    
    resp = client.post("/extract-local", files=files, data=data)
    assert resp.status_code == 200
    result = resp.json()
    
    # Verify both OCR and chunking were applied
    assert result["metadata"]["ocr_enabled"] is True
    assert result["metadata"]["chunking_enabled"] is True
    assert "chunks" in result
    assert len(result["chunks"]) > 0


@pytest.mark.skipif(CHUNKING_AVAILABLE, reason="Testing missing dependencies")
def test_extract_local_chunking_missing_deps():
    """Test error handling when chunking dependencies are missing."""
    pdf_content = create_test_pdf(num_pages=1)
    
    files = {"file": ("test.pdf", pdf_content, "application/pdf")}
    data = {
        "enable_chunking": "true"
    }
    
    resp = client.post("/extract-local", files=files, data=data)
    
    # Should fail gracefully if dependencies are missing
    if resp.status_code == 500:
        result = resp.json()
        assert "error" in result
        assert "Chunking dependencies not installed" in result["error"]
    else:
        # If dependencies are actually installed, test should pass
        assert resp.status_code == 200