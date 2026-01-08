import logging
from typing import Any, Dict, List, Optional, Tuple, Union

import tiktoken
from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field

# Import filtering functionality
from .filtering import (
    FilterConfig, FilteredElement, ElementMapping, FilterMetrics,
    apply_filters
)

# --- Configuration ---
# Remove hard-coded constants, will be configurable via API
# MIN_SEGMENT_TOKENS = 500  # The minimum number of tokens for a segment
# MAX_SEGMENT_TOKENS = 2000 # The target maximum number of tokens for a segment

# --- Pydantic Models for Data Structures ---

class StructuralContext(BaseModel):
    h1: str | None = None
    h2: str | None = None
    h3: str | None = None
    h4: str | None = None
    h5: str | None = None
    h6: str | None = None

class RichSegment(BaseModel):
    segment_id: int
    source_file: str  # Added per strategy document specification
    token_count: int
    structural_context: StructuralContext
    elements: List[Dict[str, Any]] = Field(default_factory=list)

class SegmentationInput(BaseModel):
    source_file: str
    json_content: Dict[str, Any]  # Changed from analysis_result
    min_segment_tokens: int = 10000  # Configurable with reasonable default
    max_segment_tokens: int = 30000  # Configurable with reasonable default

class FilteredSegmentationInput(BaseModel):
    source_file: str
    json_content: Dict[str, Any]  # Changed from analysis_result
    filter_config: FilterConfig
    min_segment_tokens: int = 10000  # Configurable with reasonable default
    max_segment_tokens: int = 30000  # Configurable with reasonable default

class DoclingSegmentationInput(BaseModel):
    source_file: str
    docling_response: Dict[str, Any]
    min_segment_tokens: int = 1000
    max_segment_tokens: int = 30000
    merge_peers: bool = True

class FilteredSegment(BaseModel):
    segment_id: int
    source_file: str
    token_count: int
    structural_context: StructuralContext
    elements: List[Union[FilteredElement, Dict[str, Any]]] = Field(default_factory=list)

class FilteredSegmentationResponse(BaseModel):
    segments: List[FilteredSegment]
    element_mappings: List[List[ElementMapping]]  # Mappings per segment
    metrics: FilterMetrics

# --- Core Segmentation Logic ---

logger = logging.getLogger(__name__)
router = APIRouter()
encoding = tiktoken.get_encoding("cl100k_base")

def get_heading_level(role: str) -> int | None:
    """Extracts the heading level (1-6) from a role string.
    
    Handles various Azure DI heading role patterns:
    - Direct numeric patterns: "h1", "h2", etc.
    - Generic section headings: "sectionHeading"
    - Title patterns: "title", "pageHeader"
    """
    if not role:
        return None
        
    role_lower = role.lower()
    
    # Direct heading level patterns (h1, h2, etc.)
    if role_lower.startswith("h") and len(role_lower) == 2 and role_lower[1].isdigit():
        level = int(role_lower[1])
        return level if 1 <= level <= 6 else None
    
    # Azure DI specific patterns
    if role_lower == "sectionheading":
        return 2  # Default to H2 for generic section headings
    
    if role_lower in ["title", "pageheader"]:
        return 1  # Treat titles and page headers as H1
        
    if role_lower == "subtitle":
        return 2  # Treat subtitles as H2
        
    # No heading detected
    return None

def update_context(context: StructuralContext, role: str, content: str) -> StructuralContext:
    """Updates the structural context with a new heading."""
    level = get_heading_level(role)
    if not level:
        return context

    new_context = context.model_copy()
    setattr(new_context, f"h{level}", content)
    # Reset all lower-level headings
    for i in range(level + 1, 7):
        setattr(new_context, f"h{i}", None)
    return new_context

def create_rich_segments(
    analysis_result: Dict[str, Any], 
    source_file: str,
    min_segment_tokens: int = 10000,
    max_segment_tokens: int = 30000
) -> List[RichSegment]:
    """
    Implements the stateful hierarchical aggregation to create rich segments.
    
    Args:
        analysis_result: Azure DI analysis result dictionary
        source_file: Name of the source document
        min_segment_tokens: Minimum tokens per segment
        max_segment_tokens: Maximum tokens per segment (soft limit)
        
    Returns:
        List of RichSegment objects
        
    Raises:
        ValueError: If input parameters are invalid
        KeyError: If required Azure DI data structure is malformed
    """
    # Input validation
    if not isinstance(analysis_result, dict):
        raise ValueError("analysis_result must be a dictionary")
    
    if not isinstance(source_file, str) or not source_file.strip():
        raise ValueError("source_file must be a non-empty string")
        
    if min_segment_tokens <= 0 or max_segment_tokens <= 0:
        raise ValueError("Token thresholds must be positive")
        
    if min_segment_tokens >= max_segment_tokens:
        raise ValueError("min_segment_tokens must be less than max_segment_tokens")
    
    segments: List[RichSegment] = []
    current_context = StructuralContext()
    
    def get_element_text(element: Dict[str, Any]) -> str:
        """Best-effort extraction of textual content from Azure DI elements."""
        content = element.get("content")
        if isinstance(content, str) and content.strip():
            return content
        value = element.get("value")
        if isinstance(value, str) and value.strip():
            return value
        if isinstance(element.get("key"), dict) or isinstance(element.get("value"), dict):
            key_content = element.get("key", {}).get("content", "")
            value_content = element.get("value", {}).get("content", "")
            combined = f"{key_content}: {value_content}".strip(": ").strip()
            if combined:
                return combined
        if isinstance(element.get("cells"), list):
            cell_text = " ".join(
                cell.get("content", "") for cell in element["cells"] if isinstance(cell, dict)
            ).strip()
            if cell_text:
                return cell_text
        if isinstance(element.get("lines"), list):
            line_text = " ".join(
                line.get("content", "") for line in element["lines"] if isinstance(line, dict)
            ).strip()
            if line_text:
                return line_text
        if isinstance(element.get("words"), list):
            word_text = " ".join(
                word.get("content", "") for word in element["words"] if isinstance(word, dict)
            ).strip()
            if word_text:
                return word_text
        return ""

    # Supported Azure DI element types - expanded from just paragraphs + tables
    SUPPORTED_ELEMENT_TYPES = ["paragraphs", "tables", "figures", "formulas", "keyValuePairs"]
    
    # Combine all supported element types into a single, ordered list
    all_elements = []
    for element_type in SUPPORTED_ELEMENT_TYPES:
        elements = analysis_result.get(element_type, [])
        if elements:  # Only process if elements exist
            # Validate element structure
            for i, element in enumerate(elements):
                if not isinstance(element, dict):
                    raise ValueError(f"Element {i} in {element_type} must be a dictionary")
                if "content" not in element:
                    logger.warning(f"Element {i} in {element_type} missing 'content' field")
            all_elements.extend(elements)

    if not all_elements:
        pages = analysis_result.get("pages", [])
        for page in pages:
            page_number = page.get("pageNumber", 0)
            page_lines = page.get("lines") or []
            page_words = page.get("words") or []
            if page_lines:
                for line in page_lines:
                    if isinstance(line, dict):
                        line["pageNumber"] = page_number
                        line.setdefault("role", "line")
                        all_elements.append(line)
            elif page_words:
                for word in page_words:
                    if isinstance(word, dict):
                        word["pageNumber"] = page_number
                        word.setdefault("role", "word")
                        all_elements.append(word)
    
    # Sort by span offset to maintain document order, handling different span structures
    def get_element_offset(element):
        """Extract offset from element, handling different Azure DI structures."""
        try:
            if "spans" in element and element["spans"]:
                return element["spans"][0]["offset"]
            elif "span" in element:
                return element["span"]["offset"]
            else:
                # Fallback for elements without spans (shouldn't happen in valid Azure DI data)
                logger.warning(f"Element missing span information: {element.get('content', 'Unknown')[:50]}")
                return 0
        except (KeyError, IndexError, TypeError) as e:
            logger.warning(f"Error extracting offset from element: {e}")
            return 0
    
    try:
        all_elements.sort(key=get_element_offset)
    except Exception as e:
        raise ValueError(f"Failed to sort elements by offset: {e}")

    if not all_elements:
        logger.info("No processable elements found in analysis result")
        return []

    buffer_elements: List[Dict[str, Any]] = []
    buffer_token_count = 0
    segment_id_counter = 1

    for element in all_elements:
        try:
            element_content = get_element_text(element)
            if not element_content:
                continue
            element_tokens = len(encoding.encode(element_content))
            element_role = element.get("role", "paragraph") # Default role
            
            # Check for logical boundary to finalize a segment BEFORE processing this element
            is_high_level_heading = get_heading_level(element_role) in [1, 2]
            if (
                buffer_elements and  # Only if we have elements to segment
                buffer_token_count >= min_segment_tokens and
                (is_high_level_heading or buffer_token_count + element_tokens > max_segment_tokens)
            ):
                # Finalize the current segment with current context state
                segments.append(RichSegment(
                    segment_id=segment_id_counter,
                    source_file=source_file,
                    token_count=buffer_token_count,
                    structural_context=current_context.model_copy(), # Current context at this point
                    elements=buffer_elements,
                ))
                # Start a new segment
                segment_id_counter += 1
                buffer_elements = []
                buffer_token_count = 0

            # Update context if current element is a heading
            if get_heading_level(element_role):
                 current_context = update_context(current_context, element_role, element_content)

            # Add current element to the buffer
            buffer_elements.append(element)
            buffer_token_count += element_tokens
            
        except Exception as e:
            logger.error(f"Error processing element: {element.get('content', 'Unknown')[:100]}: {e}")
            # Continue processing other elements instead of failing completely
            continue

    # Add the final buffered segment if it's not empty
    if buffer_elements:
        segments.append(RichSegment(
            segment_id=segment_id_counter,
            source_file=source_file,
            token_count=buffer_token_count,
            structural_context=current_context.model_copy(), # Final context state
            elements=buffer_elements,
        ))

    logger.info(f"Created {len(segments)} segments from {len(all_elements)} elements")
    return segments


def _extract_docling_document(docling_response: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(docling_response, dict):
        raise HTTPException(status_code=400, detail="docling_response must be an object")
    document = docling_response.get("document")
    if not isinstance(document, dict):
        raise HTTPException(status_code=400, detail="docling_response.document is required")
    json_content = document.get("json_content")
    if not isinstance(json_content, dict):
        raise HTTPException(status_code=400, detail="docling_response.document.json_content must be an object")
    return json_content


def _chunk_docling_document(
    docling_json: Dict[str, Any],
    source_file: str,
    min_segment_tokens: int,
    max_segment_tokens: int,
    merge_peers: bool,
) -> List[Dict[str, Any]]:
    try:
        from docling_core.transforms.chunker.hybrid_chunker import HybridChunker
        from docling_core.transforms.chunker.tokenizer.openai import OpenAITokenizer
        try:
            from docling_core.types.doc import DoclingDocument
        except Exception:
            from docling_core.types import Document as DoclingDocument
    except Exception as exc:  # pragma: no cover - import guard
        raise HTTPException(
            status_code=500,
            detail=f"Docling chunking dependencies are not available: {exc}",
        )

    try:
        if hasattr(DoclingDocument, "model_validate"):
            docling_doc = DoclingDocument.model_validate(docling_json)
        else:
            docling_doc = DoclingDocument.parse_obj(docling_json)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid docling document: {exc}")

    tokenizer = OpenAITokenizer(
        tokenizer=encoding,
        max_tokens=max_segment_tokens,
    )
    chunker = HybridChunker(tokenizer=tokenizer, merge_peers=merge_peers)

    segments: List[Dict[str, Any]] = []
    segment_id = 1

    for chunk in chunker.chunk(docling_doc):
        raw_text = getattr(chunk, "text", "")
        contextualized = raw_text
        contextualize = getattr(chunker, "contextualize", None)
        if callable(contextualize):
            try:
                contextualized = contextualize(chunk)
            except Exception:
                contextualized = raw_text

        token_count = len(encoding.encode(contextualized))

        element: Dict[str, Any] = {
            "content": contextualized,
            "role": "chunk",
        }

        if raw_text and raw_text != contextualized:
            element["raw_content"] = raw_text

        meta = getattr(chunk, "meta", None)
        if meta is not None:
            export = getattr(meta, "export_json_dict", None)
            if callable(export):
                element["docling_meta"] = export()

        segments.append({
            "segment_id": segment_id,
            "source_file": source_file,
            "token_count": token_count,
            "structural_context": StructuralContext().model_dump(),
            "elements": [element],
        })
        segment_id += 1

    if min_segment_tokens > 0 and segments:
        merged: List[Dict[str, Any]] = []
        buffer = segments[0]
        for segment in segments[1:]:
            if buffer["token_count"] < min_segment_tokens:
                buffer["elements"].extend(segment["elements"])
                buffer["token_count"] += segment["token_count"]
            else:
                merged.append(buffer)
                buffer = segment
        if buffer:
            merged.append(buffer)

        for idx, segment in enumerate(merged, start=1):
            segment["segment_id"] = idx
        segments = merged

    return segments

def create_filtered_segments(
    filtered_elements: List[Union[FilteredElement, Dict[str, Any]]],
    source_file: str,
    min_segment_tokens: int = 10000,
    max_segment_tokens: int = 30000
) -> List[FilteredSegment]:
    """
    Create segments from pre-filtered elements.
    
    This is similar to create_rich_segments but works with FilteredElement objects
    that have already been processed to remove unnecessary fields.
    """
    segments = []
    buffer_elements = []
    buffer_token_count = 0
    segment_id_counter = 0
    current_context = StructuralContext()

    for element in filtered_elements:
        # Get fields from element (handle both dict and object)
        if isinstance(element, dict):
            role = element.get("role")
            content = element.get("content", "")
        else:
            role = element.role
            content = element.content
        
        # Update structural context for headings
        if role:
            level = get_heading_level(role)
            if level:
                new_context = update_context(current_context, role, content)
                current_context = new_context

        # Calculate tokens for this element
        element_tokens = len(encoding.encode(content))

        # Decision: Should we start a new segment?
        should_segment = False
        
        # Check if adding this element would exceed max tokens
        if buffer_token_count + element_tokens > max_segment_tokens:
            should_segment = True
            logger.debug(f"Segmenting due to token limit: {buffer_token_count} + {element_tokens} > {max_segment_tokens}")
        
        # Check if we hit a major structural boundary (H1 or H2) with enough content
        elif buffer_token_count >= min_segment_tokens:
            level = get_heading_level(role or "")
            if level and level <= 2:
                should_segment = True
                logger.debug(f"Segmenting at {role} boundary with {buffer_token_count} tokens")

        # Create segment if needed
        if should_segment and buffer_elements:
            segments.append(FilteredSegment(
                segment_id=segment_id_counter,
                source_file=source_file,
                token_count=buffer_token_count,
                structural_context=current_context.model_copy(),
                elements=buffer_elements,
            ))
            segment_id_counter += 1
            buffer_elements = []
            buffer_token_count = 0

        # Add element to buffer
        buffer_elements.append(element)
        buffer_token_count += element_tokens

    # Add final segment if buffer not empty
    if buffer_elements:
        segments.append(FilteredSegment(
            segment_id=segment_id_counter,
            source_file=source_file,
            token_count=buffer_token_count,
            structural_context=current_context.model_copy(),
            elements=buffer_elements,
        ))

    logger.info(f"Created {len(segments)} filtered segments from {len(filtered_elements)} elements")
    return segments

# --- FastAPI Endpoints ---

@router.post("/segment", response_model=List[RichSegment])
async def segment_document(payload: SegmentationInput = Body(...)):
    """
    Segment a complete Azure Document Intelligence analysis result into rich, structurally-aware chunks.
    
    This endpoint implements Phase 2 of the PDF processing strategy, transforming complete Azure DI 
    results into structured Rich Segments with configurable token thresholds.
    
    **Input:**
    - `source_file`: Name of the original document
    - `json_content`: Complete Azure DI analysis result (from Phase 1 extraction)
    - `min_segment_tokens`: Minimum tokens per segment (default: 10,000)
    - `max_segment_tokens`: Maximum tokens per segment - soft limit (default: 30,000)
    
    **Output:**
    - Array of RichSegment objects with hierarchical context and metadata
    
    **Features:**
    - Configurable token thresholds for different use cases
    - Intelligent boundary detection at heading levels (H1/H2)
    - Preserves full Azure DI metadata (bounding boxes, page numbers, etc.)
    - Maintains hierarchical context (current H1-H6 headings)
    - Processes all Azure DI element types (paragraphs, tables, figures, formulas, keyValuePairs)
    
    **Example:**
    ```python
    payload = {
        "source_file": "document.pdf",
        "json_content": {...},  # Azure DI output
        "min_segment_tokens": 5000,
        "max_segment_tokens": 15000
    }
    ```
    """
    logger.info(f"Received segmentation request for {payload.source_file}")
    logger.info(f"Token thresholds: min={payload.min_segment_tokens}, max={payload.max_segment_tokens}")
    
    # Validate parameters
    if payload.min_segment_tokens <= 0:
        error_msg = f"min_segment_tokens must be positive, got {payload.min_segment_tokens}"
        logger.error(error_msg)
        raise ValueError(error_msg)
        
    if payload.max_segment_tokens <= 0:
        error_msg = f"max_segment_tokens must be positive, got {payload.max_segment_tokens}"
        logger.error(error_msg)
        raise ValueError(error_msg)
        
    if payload.min_segment_tokens >= payload.max_segment_tokens:
        error_msg = f"min_segment_tokens ({payload.min_segment_tokens}) must be less than max_segment_tokens ({payload.max_segment_tokens})"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    # Validate json_content structure
    if not isinstance(payload.json_content, dict):
        error_msg = "json_content must be a dictionary"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    try:
        rich_segments = create_rich_segments(
            payload.json_content, 
            payload.source_file,
            payload.min_segment_tokens,
            payload.max_segment_tokens
        )
        logger.info(f"Successfully created {len(rich_segments)} segments for {payload.source_file}")
        
        # Log summary statistics
        if rich_segments:
            total_tokens = sum(segment.token_count for segment in rich_segments)
            avg_tokens = total_tokens / len(rich_segments)
            logger.info(f"Segmentation stats: {total_tokens} total tokens, {avg_tokens:.1f} avg tokens per segment")
        
        return rich_segments
    except Exception as e:
        error_msg = f"Error during segmentation of {payload.source_file}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        # In a real app, you'd return a proper HTTPException
        raise ValueError(error_msg)

@router.post("/segment-filtered", response_model=FilteredSegmentationResponse)
async def segment_with_filtering(payload: FilteredSegmentationInput = Body(...)):
    """
    Segment a document with LLM-optimized filtering applied.
    
    This endpoint combines filtering and segmentation to prepare documents for LLM processing
    with significantly reduced token usage (typically 50-75% reduction).
    
    **Input:**
    - `source_file`: Name of the original document
    - `json_content`: Complete Azure DI analysis result
    - `filter_config`: Configuration for filtering elements
    - `min_segment_tokens`: Minimum tokens per segment (default: 10,000)
    - `max_segment_tokens`: Maximum tokens per segment (default: 30,000)
    
    **Filter Presets:**
    - `legal_analysis`: Includes context, structure, and metadata
    - `content_extraction`: Minimal filtering, focus on text
    - `structured_qa`: Balanced filtering for Q&A tasks
    - `minimal`: Maximum reduction, only essential content
    
    **Output:**
    - `segments`: Array of filtered segments ready for LLM
    - `element_mappings`: Mappings to trace back to original elements
    - `metrics`: Statistics about filtering effectiveness
    
    **Example:**
    ```python
    payload = {
        "source_file": "contract.pdf",
        "json_content": {...},  # Azure DI output
        "filter_config": {
            "filter_preset": "legal_analysis",
            "include_element_ids": true
        },
        "min_segment_tokens": 10000,
        "max_segment_tokens": 30000
    }
    ```
    """
    logger.info(f"Received filtered segmentation request for {payload.source_file}")
    logger.info(f"Filter preset: {payload.filter_config.filter_preset}")
    logger.info(f"Token thresholds: min={payload.min_segment_tokens}, max={payload.max_segment_tokens}")
    
    # Validate parameters
    if payload.min_segment_tokens <= 0:
        raise HTTPException(status_code=400, detail=f"min_segment_tokens must be positive")
        
    if payload.max_segment_tokens <= 0:
        raise HTTPException(status_code=400, detail=f"max_segment_tokens must be positive")
        
    if payload.min_segment_tokens >= payload.max_segment_tokens:
        raise HTTPException(status_code=400, detail=f"min_segment_tokens must be less than max_segment_tokens")
    
    try:
        # Step 1: Apply filters to the json_content
        filtered_elements, element_mappings, metrics = apply_filters(
            payload.json_content,
            payload.filter_config
        )
        
        logger.info(f"Filtering complete: {len(filtered_elements)} elements retained, "
                    f"{metrics.reduction_percentage:.1f}% size reduction")
        
        # Step 2: Create segments from filtered elements
        filtered_segments = create_filtered_segments(
            filtered_elements,
            payload.source_file,
            payload.min_segment_tokens,
            payload.max_segment_tokens
        )
        
        logger.info(f"Created {len(filtered_segments)} filtered segments")
        
        # Step 3: Organize mappings by segment
        # This allows frontend to know which elements are in each segment
        segment_mappings = []
        for segment in filtered_segments:
            segment_element_ids = set()
            for elem in segment.elements:
                if isinstance(elem, dict):
                    elem_id = elem.get("_id")
                else:
                    elem_id = elem.id
                if elem_id:
                    segment_element_ids.add(elem_id)
            
            segment_maps = [
                mapping for mapping in element_mappings 
                if mapping.azure_element_id in segment_element_ids
            ]
            segment_mappings.append(segment_maps)
        
        # Return the response
        return FilteredSegmentationResponse(
            segments=filtered_segments,
            element_mappings=segment_mappings,
            metrics=metrics
        )
        
    except Exception as e:
        error_msg = f"Error during filtered segmentation of {payload.source_file}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise HTTPException(status_code=500, detail=error_msg)


@router.post("/segment-docling", response_model=List[RichSegment])
async def segment_docling(payload: DoclingSegmentationInput = Body(...)):
    """
    Segment a docling-serve response into rich, structurally-aware chunks.

    **Input:**
    - `source_file`: Name of the original document
    - `docling_response`: Full docling-serve response with `document.json_content`
    - `min_segment_tokens`: Minimum tokens per segment (default: 1,000)
    - `max_segment_tokens`: Maximum tokens per segment (default: 30,000)
    - `merge_peers`: Merge adjacent peers when chunking (default: true)
    """
    if payload.min_segment_tokens <= 0:
        raise HTTPException(status_code=400, detail="min_segment_tokens must be positive")
    if payload.max_segment_tokens <= 0:
        raise HTTPException(status_code=400, detail="max_segment_tokens must be positive")
    if payload.min_segment_tokens >= payload.max_segment_tokens:
        raise HTTPException(status_code=400, detail="min_segment_tokens must be less than max_segment_tokens")

    docling_json = _extract_docling_document(payload.docling_response)
    segments = _chunk_docling_document(
        docling_json=docling_json,
        source_file=payload.source_file,
        min_segment_tokens=payload.min_segment_tokens,
        max_segment_tokens=payload.max_segment_tokens,
        merge_peers=payload.merge_peers,
    )
    return segments
