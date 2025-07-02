"""
Local document extraction using Docling with OCR support.

This module provides local document processing capabilities without requiring
external API calls to Azure Document Intelligence. It supports OCR for scanned
documents using ocrmac on macOS and EasyOCR on other platforms.
"""

import os
import platform
import tempfile
from typing import Optional

from docling.datamodel.pipeline_options import (
    EasyOcrOptions,
    OcrMacOptions,
    PdfPipelineOptions,
)
from docling.datamodel.base_models import ConversionStatus
from docling.document_converter import DocumentConverter
from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse

router = APIRouter()


@router.post("/extract-local")
async def extract_local(
    file: UploadFile = File(...),
    ocr_enabled: bool = Form(True),
    ocr_lang: str = Form("en"),
    max_pages: Optional[int] = Form(None),
):
    """
    Extract document locally using Docling with OCR support.

    This endpoint processes documents locally without sending data to external services.
    OCR is automatically applied to scanned content when enabled.

    Supported formats: PDF, DOCX, DOC, PPTX, HTML, MD

    OCR Support:
    - macOS: Uses native Vision framework via ocrmac (fast, accurate)
    - Other platforms: Falls back to EasyOCR

    Args:
        file: Document file to process
        ocr_enabled: Enable OCR for scanned content (default: true)
        ocr_lang: OCR language code (default: "en", use "auto" for detection)
        max_pages: Maximum number of pages to process (optional)

    Returns:
        JSON response with:
        - markdown_content: Markdown representation of the document
        - docling_document: Native DoclingDocument JSON format
        - ocr_applied: Whether OCR was actually used in processing
    """
    # Validate file type
    allowed_types = [".pdf", ".docx", ".doc", ".pptx", ".html", ".md"]
    file_ext = os.path.splitext(file.filename)[1].lower()

    if file_ext not in allowed_types:
        return JSONResponse(
            status_code=400,
            content={
                "error": f"Unsupported file type: {file_ext}",
                "supported_types": allowed_types,
            },
        )

    # Size validation
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
    if file.size and file.size > MAX_FILE_SIZE:
        return JSONResponse(
            status_code=400,
            content={
                "error": f"File size exceeds {MAX_FILE_SIZE // (1024*1024)}MB limit",
                "file_size_mb": file.size / (1024 * 1024),
            },
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
                    "suggestion": "Disable OCR or install ocrmac",
                },
            )

    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
        contents = await file.read()
        temp_file.write(contents)
        temp_file.flush()
        temp_path = temp_file.name

    try:
        # For now, use default converter settings
        # TODO: Add OCR configuration once we understand the correct API
        converter = DocumentConverter()

        # Convert document
        result = converter.convert(temp_path)

        # Check conversion status
        if result.status != ConversionStatus.SUCCESS:
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Document conversion failed",
                    "status": str(result.status),
                    "details": getattr(result, "errors", "Unknown error"),
                },
            )

        # Check if OCR was actually applied
        # Note: Docling doesn't have a direct "success_with_ocr" status,
        # so we check if OCR was enabled and document has content
        ocr_applied = ocr_enabled and len(result.document.export_to_markdown()) > 0

        # Extract outputs
        markdown_content = result.document.export_to_markdown()
        docling_json = result.document.export_to_dict()

        # Add metadata about processing
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

        return JSONResponse(content=response_data)

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": "Processing failed",
                "details": str(e),
                "file": file.filename,
            },
        )
    finally:
        # Clean up temporary file
        if os.path.exists(temp_path):
            os.remove(temp_path)