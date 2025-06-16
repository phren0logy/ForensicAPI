import asyncio
import logging
import os
import tempfile
from typing import Any, Dict, List, Tuple

import azure.ai.documentintelligence as adi
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


def stitch_analysis_results(
    stitched_result: Dict[str, Any], new_result: Dict[str, Any], page_offset: int
) -> Dict[str, Any]:
    """
    Stitches a new analysis result dictionary into an existing one.
    """
    if not stitched_result:
        # For the first batch, we just need to update page numbers
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
    file_path: str, client: adi.DocumentIntelligenceClient, batch_size: int
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
            poller = await asyncio.to_thread(
                client.begin_analyze_document,
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
            # First result, correct page numbers and initialize
            for page in result_dict.get("pages", []):
                page["pageNumber"] += page_offset
            for element in result_dict.get("paragraphs", []) + result_dict.get("tables", []):
                for region in element.get("boundingRegions", []):
                    region["pageNumber"] += page_offset
            stitched_result = result_dict
        else:
            stitched_result = stitch_analysis_results(
                stitched_result, result_dict, page_offset
            )
            
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
    client = adi.DocumentIntelligenceClient(
        endpoint=endpoint, credential=AzureKeyCredential(key)
    )

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
        contents = await file.read()
        temp_file.write(contents)
        temp_file.flush()
        temp_path = temp_file.name

    try:
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
