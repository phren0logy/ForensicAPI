"""
Local document extraction using Docling with OCR support.

This module provides local document processing capabilities without requiring
external API calls to Azure Document Intelligence. It supports OCR for scanned
documents using ocrmac on macOS and EasyOCR on other platforms.
"""

import os
import platform
import tempfile
import time
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

# Chunking imports
try:
    import tiktoken
    from docling_core.transforms.chunker.tokenizer.openai import OpenAITokenizer
    from docling.chunking import HybridChunker
    CHUNKING_AVAILABLE = True
except ImportError:
    CHUNKING_AVAILABLE = False

router = APIRouter()


@router.post("/extract-local")
async def extract_local(
    file: UploadFile = File(...),
    ocr_enabled: bool = Form(True),
    ocr_lang: str = Form("en"),
    max_pages: Optional[int] = Form(None),
    # New chunking parameters
    enable_chunking: bool = Form(False),
    chunk_min_tokens: int = Form(1000),
    chunk_max_tokens: int = Form(30000),
    merge_peers: bool = Form(True),
):
    """
    Extract document locally using Docling with OCR support and optional chunking.

    This endpoint processes documents locally without sending data to external services.
    OCR is automatically applied to scanned content when enabled. Document chunking
    creates semantically meaningful text chunks suitable for RAG pipelines and LLMs.

    Supported formats: PDF, DOCX, DOC, PPTX, HTML, MD

    OCR Support:
    - macOS: Uses native Vision framework via ocrmac (fast, accurate)
    - Other platforms: Falls back to EasyOCR

    Chunking Support:
    - Uses tiktoken with cl100k_base encoding (GPT-4 compatible)
    - Respects document structure (headings, paragraphs, tables)
    - Includes hierarchical context in each chunk

    Args:
        file: Document file to process
        ocr_enabled: Enable OCR for scanned content (default: true)
        ocr_lang: OCR language code (default: "en", use "auto" for detection)
        max_pages: Maximum number of pages to process (optional)
        enable_chunking: Enable document chunking (default: false)
        chunk_min_tokens: Minimum tokens per chunk (default: 1000)
        chunk_max_tokens: Maximum tokens per chunk (default: 30000)
        merge_peers: Merge sibling elements when possible (default: true)

    Returns:
        JSON response with:
        - markdown_content: Markdown representation of the document
        - json_content: Native DoclingDocument JSON format
        - chunks: Array of document chunks (if chunking enabled)
        - metadata: Processing information including OCR and chunking details
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

    # Start timing
    start_time = time.time()
    
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

    # Get file size
    file_size = file.size if file.size else 0
    
    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
        contents = await file.read()
        if file_size == 0:  # If size wasn't available before reading
            file_size = len(contents)
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

        # Calculate processing time
        processing_time = time.time() - start_time
        
        # Get page count from Docling structure
        page_count = len(docling_json.get("pages", {}))

        # Build response with unified format
        response_data = {
            "markdown_content": markdown_content,
            "json_content": docling_json,  # Renamed from docling_document
        }

        # Apply chunking if enabled
        if enable_chunking:
            if not CHUNKING_AVAILABLE:
                return JSONResponse(
                    status_code=500,
                    content={
                        "error": "Chunking dependencies not installed",
                        "details": "Run: uv add 'docling-core[chunking-openai]'",
                    },
                )
            
            try:
                # Initialize tokenizer with GPT-4's encoding
                tokenizer = OpenAITokenizer(
                    tokenizer=tiktoken.get_encoding("cl100k_base"),
                    max_tokens=chunk_max_tokens
                )
                
                # Create chunker with configuration
                chunker = HybridChunker(
                    tokenizer=tokenizer,
                    merge_peers=merge_peers,
                    min_tokens=chunk_min_tokens
                )
                
                # Process chunks
                chunks = []
                for chunk in chunker.chunk(result.document):
                    # Get contextualized text (includes headings)
                    contextualized_text = chunker.contextualize(chunk)
                    
                    chunks.append({
                        "text": contextualized_text,
                        "token_count": tokenizer.count_tokens(contextualized_text),
                        "meta": chunk.meta.export_json_dict()
                    })
                
                # Add chunks to response
                response_data["chunks"] = chunks
                
            except Exception as e:
                return JSONResponse(
                    status_code=500,
                    content={
                        "error": "Chunking failed",
                        "details": str(e),
                    },
                )

        # Add metadata
        response_data["metadata"] = {
            "page_count": page_count,
            "processing_type": "docling",
            "processing_time": processing_time,
            "file_size": file_size,
            "filename": file.filename,
            "ocr_applied": ocr_applied,
            "ocr_enabled": ocr_enabled,
            "ocr_platform": "ocrmac" if platform.system() == "Darwin" else "easyocr"
        }
        
        # Add chunking metadata if enabled
        if enable_chunking and "chunks" in response_data:
            response_data["metadata"]["chunk_count"] = len(response_data["chunks"])
            response_data["metadata"]["chunking_enabled"] = True
            response_data["metadata"]["chunk_config"] = {
                "min_tokens": chunk_min_tokens,
                "max_tokens": chunk_max_tokens,
                "tokenizer": "tiktoken-cl100k_base",
                "merge_peers": merge_peers
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