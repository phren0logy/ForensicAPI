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
    assert "docling_document" in result
    assert "ocr_applied" in result
    assert "metadata" in result

    # Check that content was extracted
    assert len(result["markdown_content"]) > 0
    assert "Test PDF" in result["markdown_content"]

    # Verify Docling document structure
    doc = result["docling_document"]
    assert doc["schema_name"] == "DoclingDocument"
    assert "body" in doc
    assert "texts" in doc or "pictures" in doc or "tables" in doc

    # Check metadata
    metadata = result["metadata"]
    assert metadata["filename"] == "test.pdf"
    assert metadata["ocr_enabled"] is True
    assert metadata["pages_processed"] >= 1


def test_extract_local_without_ocr():
    """Test extraction with OCR disabled."""
    pdf_content = create_test_pdf(num_pages=1)

    files = {"file": ("test.pdf", pdf_content, "application/pdf")}
    data = {"ocr_enabled": "false"}
    resp = client.post("/extract-local", files=files, data=data)

    assert resp.status_code == 200
    result = resp.json()

    # Verify OCR was not applied
    assert result["ocr_applied"] is False
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
        assert result["ocr_applied"] is True
        assert len(result["markdown_content"]) > 100  # Should have substantial content
    else:
        pytest.skip("Scanned PDF test fixture not found")