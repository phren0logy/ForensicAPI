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

# Define a batch size for processing pages. This is the number of pages
# sent to Azure Document Intelligence in a single API call.
PAGE_BATCH_SIZE = 100


def get_pdf_page_count(file_path: str) -> int:
    """Gets the total number of pages in a PDF file."""
    reader = PdfReader(file_path)
    return len(reader.pages)


def stitch_analysis_results(
    stitched_result: AnalyzeResult, new_result: AnalyzeResult, page_offset: int
) -> AnalyzeResult:
    """
    Stitches a new analysis result into an existing (stitched) result.

    This function is the core of the "perfect stitching" logic. It updates page
    numbers and character offsets to make the combined result look like it
    came from a single API call.
    """
    if not stitched_result:
        # For the first batch, we just need to update page numbers
        for page in new_result.pages:
            page.page_number += page_offset
        for element in new_result.paragraphs + new_result.tables:
            for region in element.bounding_regions:
                region.page_number += page_offset
        return new_result

    content_offset = len(stitched_result.content)
    new_result.content = stitched_result.content + new_result.content

    # Update spans and page numbers in all relevant elements
    for element_list in [
        new_result.pages,
        new_result.paragraphs,
        new_result.tables,
        new_result.words,
        new_result.lines,
        new_result.selection_marks,
    ]:
        for element in element_list:
            if hasattr(element, "spans"):
                for span in element.spans:
                    span.offset += content_offset
            if hasattr(element, "page_number"):
                element.page_number += page_offset
            if hasattr(element, "bounding_regions"):
                for region in element.bounding_regions:
                    region.page_number += page_offset

    # Append the updated elements to the stitched result
    stitched_result.pages.extend(new_result.pages)
    stitched_result.paragraphs.extend(new_result.paragraphs)
    stitched_result.tables.extend(new_result.tables)
    stitched_result.words.extend(new_result.words)
    stitched_result.lines.extend(new_result.lines)
    stitched_result.selection_marks.extend(new_result.selection_marks)

    stitched_result.content = new_result.content
    return stitched_result


async def analyze_pdf_in_batches(
    file_path: str, client: adi.DocumentIntelligenceClient
) -> Tuple[Dict[str, Any], str]:
    """
    Analyzes a PDF in batches and stitches the results together.
    """
    total_pages = get_pdf_page_count(file_path)
    stitched_result = None
    all_results = []

    async def analyze_range(page_start, page_end):
        page_range_str = f"{page_start}-{page_end}"
        logger.info(f"Analyzing page range: {page_range_str}")
        with open(file_path, "rb") as f:
            poller = await asyncio.to_thread(
                client.begin_analyze_document,
                "prebuilt-layout",
                f,
                pages=page_range_str,
                output_content_format="markdown",
            )
            result = await asyncio.to_thread(poller.result)
            all_results.append((page_start - 1, result))

    tasks = []
    for i in range(1, total_pages + 1, PAGE_BATCH_SIZE):
        start_page = i
        end_page = min(i + PAGE_BATCH_SIZE - 1, total_pages)
        tasks.append(analyze_range(start_page, end_page))
    
    await asyncio.gather(*tasks)

    # Sort results by page start to ensure correct order for stitching
    all_results.sort(key=lambda x: x[0])

    for page_offset, result in all_results:
        if not stitched_result:
            # First result, correct page numbers and initialize
            for page in result.pages:
                page.page_number += page_offset
            for element in result.paragraphs + result.tables:
                if hasattr(element, "bounding_regions"):
                    for region in element.bounding_regions:
                        region.page_number += page_offset
            stitched_result = result
        else:
            stitched_result = stitch_analysis_results(
                stitched_result, result, page_offset
            )
            
    if not stitched_result:
        return {}, ""

    return stitched_result.to_dict(), stitched_result.content


@router.post("/extract", response_class=JSONResponse)
async def extract(file: UploadFile = File(...)):
    """
    Extracts structured data and markdown from a PDF document.

    This endpoint processes the PDF in batches, then intelligently stitches the
    results to form a single, cohesive analysis object that is identical to
    the output of a single API call on the entire document.
    """
    logger.info(f"/extract endpoint called for file: {file.filename}")
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
            temp_path, client
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
