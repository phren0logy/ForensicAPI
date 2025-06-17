import asyncio
import logging
import os
import tempfile
from typing import Any, Dict, List, Optional, Tuple

from azure.ai.documentintelligence.aio import (
    DocumentIntelligenceClient as AsyncDocumentIntelligenceClient,
)
from azure.ai.documentintelligence.models import AnalyzeResult
from azure.core.credentials import AzureKeyCredential
from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse
from pypdf import PdfReader
from utils import ensure_env_loaded

router = APIRouter()
logger = logging.getLogger(__name__)


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


def stitch_analysis_results(
    stitched_result: Dict[str, Any], 
    new_result: Dict[str, Any], 
    page_offset: Optional[int] = None,
    validate_inputs: bool = True
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
        # For the first batch, we just need to update page numbers if offset is needed
        if page_offset != 0:
            for page in new_result.get("pages", []):
                page["pageNumber"] += page_offset
            for element in new_result.get("paragraphs", []) + new_result.get("tables", []):
                for region in element.get("boundingRegions", []):
                    region["pageNumber"] += page_offset
        return new_result

    content_offset = len(stitched_result["content"])
    concatenated_content = stitched_result["content"] + new_result["content"]

    # Update spans and page numbers in all relevant elements
    for element_list_key in ["pages", "paragraphs", "tables", "words", "lines", "selectionMarks"]:
        for element in new_result.get(element_list_key, []):
            # Handle both "spans" (for paragraphs, lines, etc.) and "span" (for words)
            if "spans" in element:
                for span in element["spans"]:
                    span["offset"] += content_offset
            elif "span" in element:
                element["span"]["offset"] += content_offset
            if "pageNumber" in element:
                element["pageNumber"] += page_offset
            if "boundingRegions" in element:
                for region in element["boundingRegions"]:
                    region["pageNumber"] += page_offset

    # Append the updated elements to the stitched result
    for key in ["pages", "paragraphs", "tables", "words", "lines", "selectionMarks"]:
        if key not in stitched_result:
            stitched_result[key] = []
        stitched_result[key].extend(new_result.get(key, []))

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
async def extract(file: UploadFile = File(...), batch_size: int = 1500):
    """
    Extracts structured data and markdown from a PDF document.

    This endpoint processes the PDF in batches, then intelligently stitches the
    results to form a single, cohesive analysis object that is identical to
    the output of a single API call on the entire document.
    """
    logger.info(f"/extract endpoint called for file: {file.filename}, batch_size: {batch_size}")
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

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
        contents = await file.read()
        temp_file.write(contents)
        temp_file.flush()
        temp_path = temp_file.name

    try:
        async with client:
            analysis_result, markdown_content = await analyze_pdf_in_batches(
                temp_path, client, batch_size
            )
            return JSONResponse(
                content={
                    "markdown_content": markdown_content,
                    "analysis_result": analysis_result,
                }
            )
    except Exception as e:
        logger.error(f"Error during PDF extraction: {e}", exc_info=True)
        return JSONResponse(
            status_code=500, content={"error": f"An unexpected error occurred: {e}"}
        )
    finally:
        os.remove(temp_path) 
