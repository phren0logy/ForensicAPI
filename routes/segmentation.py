import logging
from typing import Any, Dict, List

import tiktoken
from fastapi import APIRouter, Body
from pydantic import BaseModel, Field

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
    analysis_result: Dict[str, Any]
    min_segment_tokens: int = 10000  # Configurable with reasonable default
    max_segment_tokens: int = 30000  # Configurable with reasonable default

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
            element_content = element.get("content", "")
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

# --- FastAPI Endpoint ---

@router.post("/segment", response_model=List[RichSegment])
async def segment_document(payload: SegmentationInput = Body(...)):
    """
    Segment a complete Azure Document Intelligence analysis result into rich, structurally-aware chunks.
    
    This endpoint implements Phase 2 of the PDF processing strategy, transforming complete Azure DI 
    results into structured Rich Segments with configurable token thresholds.
    
    **Input:**
    - `source_file`: Name of the original document
    - `analysis_result`: Complete Azure DI analysis result (from Phase 1 extraction)
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
        "analysis_result": {...},  # Azure DI output
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
    
    # Validate analysis_result structure
    if not isinstance(payload.analysis_result, dict):
        error_msg = "analysis_result must be a dictionary"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    try:
        rich_segments = create_rich_segments(
            payload.analysis_result, 
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
