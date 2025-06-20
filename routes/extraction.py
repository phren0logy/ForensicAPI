import asyncio
import hashlib
import logging
import os
import tempfile
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
from utils import ensure_env_loaded

router = APIRouter()
logger = logging.getLogger(__name__)


def generate_element_id(element_type: str, page_number: int, index: int, content: str = "") -> str:
    """
    Generate a unique, stable ID for an element.
    
    Args:
        element_type: Type of element (paragraph, table, cell, etc.)
        page_number: Page number where element appears
        index: Global index of this element type in the document
        content: Content of the element (first 50 chars used for hash)
    
    Returns:
        Unique ID in format: {type}_{page}_{index}_{hash}
    """
    # Create a hash from content for uniqueness
    content_preview = content[:50] if content else ""
    hash_input = f"{element_type}_{page_number}_{index}_{content_preview}"
    content_hash = hashlib.md5(hash_input.encode()).hexdigest()[:6]
    
    return f"{element_type}_{page_number}_{index}_{content_hash}"


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
            para["_id"] = generate_element_id("para", page_num, indices["para"], content)
            indices["para"] += 1
    
    # Add IDs to tables and their cells
    if "tables" in result:
        for i, table in enumerate(result["tables"]):
            page_num = 1  # Default
            if "boundingRegions" in table and table["boundingRegions"]:
                page_num = table["boundingRegions"][0].get("pageNumber", 1)
            
            # Generate table ID
            table_id = generate_element_id("table", page_num, indices["table"], "")
            table["_id"] = table_id
            indices["table"] += 1
            
            # Add IDs to cells
            if "cells" in table:
                for j, cell in enumerate(table["cells"]):
                    row = cell.get("rowIndex", 0)
                    col = cell.get("columnIndex", 0)
                    content = cell.get("content", "")
                    cell["_id"] = f"cell_{page_num}_{indices['table']-1}_{row}_{col}_{hashlib.md5(content.encode()).hexdigest()[:6]}"
    
    # Add IDs to key-value pairs
    if "keyValuePairs" in result:
        for i, kv in enumerate(result["keyValuePairs"]):
            # Try to get page number from key or value
            page_num = 1
            key_content = kv.get("key", {}).get("content", "")
            value_content = kv.get("value", {}).get("content", "")
            content = f"{key_content}:{value_content}"
            
            kv["_id"] = generate_element_id("kv", page_num, indices["kv"], content)
            indices["kv"] += 1
    
    # Add IDs to lists
    if "lists" in result:
        for i, lst in enumerate(result["lists"]):
            page_num = 1
            if "boundingRegions" in lst and lst["boundingRegions"]:
                page_num = lst["boundingRegions"][0].get("pageNumber", 1)
            
            lst["_id"] = generate_element_id("list", page_num, indices["list"], "")
            indices["list"] += 1
    
    # Add IDs to figures
    if "figures" in result:
        for i, fig in enumerate(result["figures"]):
            page_num = 1
            if "boundingRegions" in fig and fig["boundingRegions"]:
                page_num = fig["boundingRegions"][0].get("pageNumber", 1)
            
            fig["_id"] = generate_element_id("fig", page_num, indices["fig"], "")
            indices["fig"] += 1
    
    # Add IDs to formulas
    if "formulas" in result:
        for i, formula in enumerate(result["formulas"]):
            page_num = 1
            if "boundingRegions" in formula and formula["boundingRegions"]:
                page_num = formula["boundingRegions"][0].get("pageNumber", 1)
            
            content = formula.get("value", "")
            formula["_id"] = generate_element_id("formula", page_num, indices["formula"], content)
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
async def extract(
    file: UploadFile = File(...), 
    batch_size: int = Form(1500),
    include_element_ids: bool = Form(True),
    return_both: bool = Form(False)
):
    """
    Extracts structured data and markdown from a PDF document.

    This endpoint processes the PDF in batches, then intelligently stitches the
    results to form a single, cohesive analysis object that is identical to
    the output of a single API call on the entire document.
    
    Args:
        file: PDF file to process
        batch_size: Number of pages per batch (default: 1500)
        include_element_ids: Add unique _id fields to all elements (default: True)
        return_both: Return both original and ID-enriched versions (default: False)
    """
    logger.info(
        f"/extract endpoint called for file: {file.filename}, "
        f"batch_size: {batch_size}, include_element_ids: {include_element_ids}, "
        f"return_both: {return_both}"
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
            
            # Prepare response based on parameters
            response_content = {
                "markdown_content": markdown_content,
            }
            
            if include_element_ids:
                # Add IDs to elements
                analysis_result_with_ids = add_ids_to_elements(analysis_result)
                
                if return_both:
                    # Return both versions
                    response_content["analysis_result"] = analysis_result_with_ids
                    response_content["analysis_result_original"] = analysis_result
                else:
                    # Return only ID-enriched version
                    response_content["analysis_result"] = analysis_result_with_ids
            else:
                # Return original without IDs
                response_content["analysis_result"] = analysis_result
            
            return JSONResponse(content=response_content)
            
    except Exception as e:
        logger.error(f"Error during PDF extraction: {e}", exc_info=True)
        return JSONResponse(
            status_code=500, content={"error": f"An unexpected error occurred: {e}"}
        )
    finally:
        os.remove(temp_path) 
