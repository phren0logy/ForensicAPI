import asyncio
import hashlib
import logging
import os
import tempfile
import time
from typing import Any, Dict, List, Optional, Tuple
import copy

from azure.ai.documentintelligence.aio import (
    DocumentIntelligenceClient as AsyncDocumentIntelligenceClient,
)
from azure.ai.documentintelligence.models import AnalyzeResult
from azure.core.credentials import AzureKeyCredential
from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse
from pypdf import PdfReader
from utils import ensure_env_loaded, generate_stable_element_id

# Import segmentation functionality
from .segmentation import create_rich_segments

router = APIRouter()
logger = logging.getLogger(__name__)


def generate_element_id(
    element_type: str,
    page_number: int,
    index: int,
    content: str = "",
    *,
    span_offset: Optional[int] = None,
    span_length: Optional[int] = None,
    bbox: Optional[List[float]] = None,
    anchor: Optional[str] = None,
) -> str:
    """Generate a stable ID for an element using spans/bounds when available."""
    return generate_stable_element_id(
        element_type,
        page_number,
        content=content[:200] if content else "",
        span_offset=span_offset,
        span_length=span_length,
        bbox=bbox,
        anchor=anchor,
        index=index,
    )


def add_ids_to_elements(analysis_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add unique _id fields to all elements in the Azure DI analysis result.
    
    This modifies the analysis result in-place by adding _id fields to:
    - Paragraphs (document level)
    - Tables (document level)
    - Key-value pairs
    - Cells within tables
    - Any other element types with content
    
    Args:
        analysis_result: Azure DI analysis result
        
    Returns:
        Modified analysis result with _id fields added
    """
    # Create a deep copy to avoid modifying the original
    result = copy.deepcopy(analysis_result)
    
    # Track global indices for each element type
    indices = {
        "para": 0,
        "table": 0,
        "kv": 0,
        "list": 0,
        "fig": 0,
        "formula": 0,
    }
    
    # Add IDs to paragraphs
    if "paragraphs" in result:
        for i, para in enumerate(result["paragraphs"]):
            page_num = 1  # Default
            if "boundingRegions" in para and para["boundingRegions"]:
                page_num = para["boundingRegions"][0].get("pageNumber", 1)
            
            content = para.get("content", "")
            span_offset = None
            span_length = None
            if para.get("spans"):
                span_offset = para["spans"][0].get("offset")
                span_length = para["spans"][0].get("length")
            bbox = None
            if "boundingRegions" in para and para["boundingRegions"]:
                bbox = para["boundingRegions"][0].get("polygon")
            para["_id"] = generate_element_id(
                "para",
                page_num,
                indices["para"],
                content,
                span_offset=span_offset,
                span_length=span_length,
                bbox=bbox,
            )
            indices["para"] += 1
    
    # Add IDs to tables and their cells
    if "tables" in result:
        for i, table in enumerate(result["tables"]):
            page_num = 1  # Default
            if "boundingRegions" in table and table["boundingRegions"]:
                page_num = table["boundingRegions"][0].get("pageNumber", 1)
            
            span_offset = None
            span_length = None
            if table.get("spans"):
                span_offset = table["spans"][0].get("offset")
                span_length = table["spans"][0].get("length")
            bbox = None
            if "boundingRegions" in table and table["boundingRegions"]:
                bbox = table["boundingRegions"][0].get("polygon")
            # Generate table ID
            table_id = generate_element_id(
                "table",
                page_num,
                indices["table"],
                "",
                span_offset=span_offset,
                span_length=span_length,
                bbox=bbox,
            )
            table["_id"] = table_id
            indices["table"] += 1
            
            # Add IDs to cells
            if "cells" in table:
                for j, cell in enumerate(table["cells"]):
                    row = cell.get("rowIndex", 0)
                    col = cell.get("columnIndex", 0)
                    row_span = cell.get("rowSpan", 1)
                    col_span = cell.get("columnSpan", 1)
                    content = cell.get("content", "")
                    cell_span_offset = None
                    cell_span_length = None
                    if cell.get("spans"):
                        cell_span_offset = cell["spans"][0].get("offset")
                        cell_span_length = cell["spans"][0].get("length")
                    cell_bbox = None
                    if "boundingRegions" in cell and cell["boundingRegions"]:
                        cell_bbox = cell["boundingRegions"][0].get("polygon")
                    cell["_id"] = generate_element_id(
                        "cell",
                        page_num,
                        indices["table"] - 1,
                        content,
                        span_offset=cell_span_offset,
                        span_length=cell_span_length,
                        bbox=cell_bbox,
                        anchor=f"cell:{row}:{col}:{row_span}:{col_span}",
                    )
    
    # Add IDs to key-value pairs
    if "keyValuePairs" in result:
        for i, kv in enumerate(result["keyValuePairs"]):
            # Try to get page number from key or value
            page_num = 1
            key_content = kv.get("key", {}).get("content", "")
            value_content = kv.get("value", {}).get("content", "")
            content = f"{key_content}:{value_content}"
            
            span_offset = None
            span_length = None
            key_spans = kv.get("key", {}).get("spans", [])
            value_spans = kv.get("value", {}).get("spans", [])
            if key_spans:
                span_offset = key_spans[0].get("offset")
                span_length = key_spans[0].get("length")
            elif value_spans:
                span_offset = value_spans[0].get("offset")
                span_length = value_spans[0].get("length")
            kv["_id"] = generate_element_id(
                "kv",
                page_num,
                indices["kv"],
                content,
                span_offset=span_offset,
                span_length=span_length,
            )
            indices["kv"] += 1
    
    # Add IDs to lists
    if "lists" in result:
        for i, lst in enumerate(result["lists"]):
            page_num = 1
            if "boundingRegions" in lst and lst["boundingRegions"]:
                page_num = lst["boundingRegions"][0].get("pageNumber", 1)
            
            span_offset = None
            span_length = None
            if lst.get("spans"):
                span_offset = lst["spans"][0].get("offset")
                span_length = lst["spans"][0].get("length")
            bbox = None
            if "boundingRegions" in lst and lst["boundingRegions"]:
                bbox = lst["boundingRegions"][0].get("polygon")
            lst["_id"] = generate_element_id(
                "list",
                page_num,
                indices["list"],
                "",
                span_offset=span_offset,
                span_length=span_length,
                bbox=bbox,
            )
            indices["list"] += 1
    
    # Add IDs to figures
    if "figures" in result:
        for i, fig in enumerate(result["figures"]):
            page_num = 1
            if "boundingRegions" in fig and fig["boundingRegions"]:
                page_num = fig["boundingRegions"][0].get("pageNumber", 1)
            
            span_offset = None
            span_length = None
            if fig.get("spans"):
                span_offset = fig["spans"][0].get("offset")
                span_length = fig["spans"][0].get("length")
            bbox = None
            if "boundingRegions" in fig and fig["boundingRegions"]:
                bbox = fig["boundingRegions"][0].get("polygon")
            fig["_id"] = generate_element_id(
                "fig",
                page_num,
                indices["fig"],
                "",
                span_offset=span_offset,
                span_length=span_length,
                bbox=bbox,
            )
            indices["fig"] += 1
    
    # Add IDs to formulas
    if "formulas" in result:
        for i, formula in enumerate(result["formulas"]):
            page_num = 1
            if "boundingRegions" in formula and formula["boundingRegions"]:
                page_num = formula["boundingRegions"][0].get("pageNumber", 1)
            
            content = formula.get("value", "")
            span_offset = None
            span_length = None
            if formula.get("spans"):
                span_offset = formula["spans"][0].get("offset")
                span_length = formula["spans"][0].get("length")
            bbox = None
            if "boundingRegions" in formula and formula["boundingRegions"]:
                bbox = formula["boundingRegions"][0].get("polygon")
            formula["_id"] = generate_element_id(
                "formula",
                page_num,
                indices["formula"],
                content,
                span_offset=span_offset,
                span_length=span_length,
                bbox=bbox,
            )
            indices["formula"] += 1
    
    return result


def get_pdf_page_count(file_path: str) -> int:
    """Gets the total number of pages in a PDF file."""
    reader = PdfReader(file_path)
    return len(reader.pages)


def validate_batch_structure(batch_data: Dict[str, Any]) -> None:
    """
    Validate that batch data has the required Azure Document Intelligence structure.
    
    Args:
        batch_data: Dictionary containing Azure DI analysis result
        
    Raises:
        ValueError: If required fields are missing or invalid
    """
    if not isinstance(batch_data, dict):
        raise ValueError("Batch data must be a dictionary")
    
    # Check required top-level fields
    required_fields = ["content", "pages"]
    for field in required_fields:
        if field not in batch_data:
            raise ValueError(f"Missing required field: {field}")
    
    # Validate content field
    if not isinstance(batch_data["content"], str):
        raise ValueError("Content field must be a string")
    
    # Validate pages field
    if not isinstance(batch_data["pages"], list):
        raise ValueError("Pages field must be a list")
    
    # Validate page structure
    for i, page in enumerate(batch_data["pages"]):
        if not isinstance(page, dict):
            raise ValueError(f"Page {i} must be a dictionary")
        if "pageNumber" not in page:
            raise ValueError(f"Page {i} missing pageNumber field")
        if not isinstance(page["pageNumber"], int) or page["pageNumber"] <= 0:
            raise ValueError(f"Page {i} pageNumber must be a positive integer")


def calculate_page_offset(stitched_result: Dict[str, Any], new_result: Dict[str, Any]) -> int:
    """
    Calculate the appropriate page offset for stitching two batches.
    
    Args:
        stitched_result: The existing stitched result (first batch if empty)
        new_result: The new batch to be added
        
    Returns:
        int: Page offset to apply to new_result pages
    """
    # If no existing result, no offset needed
    if not stitched_result or not stitched_result.get("pages"):
        return 0
    
    # Get page number ranges
    stitched_max_page = max(page["pageNumber"] for page in stitched_result["pages"])
    new_min_page = min(page["pageNumber"] for page in new_result["pages"])
    
    # If batches are consecutive (new starts right after stitched), no offset needed
    if new_min_page == stitched_max_page + 1:
        return 0
    
    # Otherwise, calculate offset to make them consecutive
    return stitched_max_page - new_min_page + 1


def validate_batch_sequence(batches: List[Dict[str, Any]]) -> None:
    """
    Validate that a sequence of batches forms continuous page numbers.
    
    Args:
        batches: List of batch dictionaries in order
        
    Raises:
        ValueError: If batches are not consecutive
    """
    if len(batches) < 2:
        return
    
    for i in range(1, len(batches)):
        prev_batch = batches[i-1]
        curr_batch = batches[i]
        
        if not prev_batch.get("pages") or not curr_batch.get("pages"):
            continue
            
        prev_max = max(page["pageNumber"] for page in prev_batch["pages"])
        curr_min = min(page["pageNumber"] for page in curr_batch["pages"])
        
        if curr_min != prev_max + 1:
            raise ValueError(f"Non-consecutive batches: gap between page {prev_max} and {curr_min}")


def _apply_offsets_to_result(result: Any, content_offset: int, page_offset: int) -> None:
    """Recursively apply content/page offsets to Azure DI result structures."""
    if isinstance(result, dict):
        for key, value in result.items():
            if key == "spans" and isinstance(value, list):
                for span in value:
                    if isinstance(span, dict) and isinstance(span.get("offset"), int):
                        span["offset"] += content_offset
            elif key == "span" and isinstance(value, dict):
                if isinstance(value.get("offset"), int):
                    value["offset"] += content_offset
            elif key == "pageNumber" and isinstance(value, int):
                result[key] = value + page_offset

            if isinstance(value, (dict, list)):
                _apply_offsets_to_result(value, content_offset, page_offset)
    elif isinstance(result, list):
        for item in result:
            _apply_offsets_to_result(item, content_offset, page_offset)


def stitch_analysis_results(
    stitched_result: Dict[str, Any],
    new_result: Dict[str, Any],
    page_offset: Optional[int] = None,
    validate_inputs: bool = True,
) -> Dict[str, Any]:
    """
    Stitches a new analysis result dictionary into an existing one.
    
    Args:
        stitched_result: The existing stitched result (will be modified in place)
        new_result: The new batch to stitch in
        page_offset: Page offset to apply (calculated automatically if None)
        validate_inputs: Whether to validate input structure
        
    Returns:
        Dict[str, Any]: The stitched result (same object as stitched_result)
        
    Raises:
        ValueError: If input validation fails
    """
    # Validate inputs if requested
    if validate_inputs:
        if stitched_result:  # Don't validate empty first batch
            validate_batch_structure(stitched_result)
        validate_batch_structure(new_result)
    
    # Calculate page offset automatically if not provided
    if page_offset is None:
        page_offset = calculate_page_offset(stitched_result, new_result)
    
    # Handle first batch case
    if not stitched_result:
        # For the first batch, only page numbers need offset adjustments
        if page_offset != 0:
            _apply_offsets_to_result(new_result, 0, page_offset)
        return new_result

    content_offset = len(stitched_result["content"])
    concatenated_content = stitched_result["content"] + new_result["content"]

    # Update spans and page numbers in all elements (including nested page structures)
    _apply_offsets_to_result(new_result, content_offset, page_offset)

    # Append the updated list elements to the stitched result
    for key, value in new_result.items():
        if key == "content":
            continue
        if isinstance(value, list):
            if key not in stitched_result:
                stitched_result[key] = []
            stitched_result[key].extend(value)
        elif key not in stitched_result:
            stitched_result[key] = value

    stitched_result["content"] = concatenated_content
    return stitched_result


async def analyze_pdf_in_batches(
    file_path: str, client: AsyncDocumentIntelligenceClient, batch_size: int
) -> Tuple[Dict[str, Any], str]:
    """
    Analyzes a PDF in batches and stitches the results together.
    """
    total_pages = get_pdf_page_count(file_path)
    stitched_result: Dict[str, Any] = {}
    all_results = []

    async def analyze_range(page_start, page_end):
        page_range_str = f"{page_start}-{page_end}"
        logger.info(f"Starting analysis of page range: {page_range_str}")
        with open(file_path, "rb") as f:
            logger.info(f"File opened for range {page_range_str}")
            poller = await client.begin_analyze_document(
                "prebuilt-layout",
                f.read(),
                pages=page_range_str,
                output_content_format="markdown",
                content_type="application/pdf"
            )
            logger.info(f"Got poller for range {page_range_str}")
            result = await poller.result()
            logger.info(f"Got result for range {page_range_str}")
            # Convert to dict immediately
            all_results.append((page_start - 1, result.as_dict()))

    tasks = []
    for i in range(1, total_pages + 1, batch_size):
        start_page = i
        end_page = min(i + batch_size - 1, total_pages)
        tasks.append(analyze_range(start_page, end_page))
    
    await asyncio.gather(*tasks)

    # Sort results by page start to ensure correct order for stitching
    all_results.sort(key=lambda x: x[0])

    for page_offset, result_dict in all_results:
        if not stitched_result:
            # First result - let stitch_analysis_results handle page numbering
            stitched_result = stitch_analysis_results({}, result_dict)
        else:
            # Subsequent results - automatic offset calculation will handle page numbers
            stitched_result = stitch_analysis_results(stitched_result, result_dict)
            
    if not stitched_result:
        return {}, ""

    # Return the dictionary representation of the final result
    return stitched_result, stitched_result.get("content", "")


@router.post("/extract", response_class=JSONResponse)
async def extract(
    file: UploadFile = File(...), 
    batch_size: int = Form(1500),
    include_element_ids: bool = Form(True),
    return_both: bool = Form(False),
    # New segmentation parameters
    enable_segmentation: bool = Form(False),
    segment_min_tokens: int = Form(10000),
    segment_max_tokens: int = Form(30000)
):
    """
    Extracts structured data and markdown from a PDF document with optional segmentation.

    This endpoint processes the PDF in batches, then intelligently stitches the
    results to form a single, cohesive analysis object that is identical to
    the output of a single API call on the entire document. Optionally segments
    the result into semantically meaningful chunks for LLM processing.
    
    Args:
        file: PDF file to process
        batch_size: Number of pages per batch (default: 1500)
        include_element_ids: Add unique _id fields to all elements (default: True)
        return_both: Return both original and ID-enriched versions (default: False)
        enable_segmentation: Enable automatic segmentation of results (default: False)
        segment_min_tokens: Minimum tokens per segment (default: 10000)
        segment_max_tokens: Maximum tokens per segment (default: 30000)
    """
    start_time = time.time()
    
    logger.info(
        f"/extract endpoint called for file: {file.filename}, "
        f"batch_size: {batch_size}, include_element_ids: {include_element_ids}, "
        f"return_both: {return_both}, enable_segmentation: {enable_segmentation}, "
        f"segment_min_tokens: {segment_min_tokens}, segment_max_tokens: {segment_max_tokens}"
    )
    ensure_env_loaded()
    endpoint = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
    key = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY")
    if not endpoint or not key:
        logger.warning("Azure DI endpoint/key not set.")
        return JSONResponse(
            status_code=500,
            content={"error": "Azure Document Intelligence endpoint/key not set"},
        )
    client = AsyncDocumentIntelligenceClient(
        endpoint=endpoint, credential=AzureKeyCredential(key)
    )

    # Get file size before reading
    file_size = file.size if file.size else 0
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
        contents = await file.read()
        if file_size == 0:  # If size wasn't available before reading
            file_size = len(contents)
        temp_file.write(contents)
        temp_file.flush()
        temp_path = temp_file.name

    try:
        # Get page count
        total_pages = get_pdf_page_count(temp_path)
        
        async with client:
            analysis_result, markdown_content = await analyze_pdf_in_batches(
                temp_path, client, batch_size
            )
            
            # Calculate processing time
            processing_time = time.time() - start_time
            
            # Prepare the main content
            if include_element_ids:
                # Add IDs to elements
                analysis_result_with_ids = add_ids_to_elements(analysis_result)
                json_content = analysis_result_with_ids
            else:
                # Return original without IDs
                json_content = analysis_result
            
            # Build response with unified format
            response_content = {
                "markdown_content": markdown_content,
                "json_content": json_content,
                "metadata": {
                    "page_count": total_pages,
                    "processing_type": "azure_di",
                    "processing_time": processing_time,
                    "file_size": file_size,
                    "filename": file.filename,
                    "batch_size": batch_size,
                    "element_ids_included": include_element_ids
                }
            }
            
            # Apply segmentation if enabled
            if enable_segmentation:
                try:
                    # Create segments using the existing segmentation logic
                    segments = create_rich_segments(
                        json_content,
                        file.filename,
                        segment_min_tokens,
                        segment_max_tokens
                    )
                    
                    # Add segments to response
                    response_content["segments"] = [segment.model_dump() for segment in segments]
                    
                    # Update metadata with segmentation info
                    response_content["metadata"]["segmentation_enabled"] = True
                    response_content["metadata"]["segment_count"] = len(segments)
                    response_content["metadata"]["segment_config"] = {
                        "min_tokens": segment_min_tokens,
                        "max_tokens": segment_max_tokens
                    }
                except Exception as e:
                    logger.error(f"Segmentation failed: {e}", exc_info=True)
                    # Continue without segmentation rather than failing the entire request
                    response_content["metadata"]["segmentation_enabled"] = False
                    response_content["metadata"]["segmentation_error"] = str(e)
            else:
                response_content["metadata"]["segmentation_enabled"] = False
            
            # Handle legacy return_both parameter if needed
            if return_both and include_element_ids:
                response_content["json_content_original"] = analysis_result
            
            return JSONResponse(content=response_content)
            
    except Exception as e:
        logger.error(f"Error during PDF extraction: {e}", exc_info=True)
        return JSONResponse(
            status_code=500, content={"error": f"An unexpected error occurred: {e}"}
        )
    finally:
        os.remove(temp_path) 
