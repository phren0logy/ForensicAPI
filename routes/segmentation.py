import logging
from typing import Any, Dict, List

import tiktoken
from fastapi import APIRouter, Body
from pydantic import BaseModel, Field

# --- Configuration ---
MIN_SEGMENT_TOKENS = 500  # The minimum number of tokens for a segment
MAX_SEGMENT_TOKENS = 2000 # The target maximum number of tokens for a segment

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
    token_count: int
    structural_context: StructuralContext
    elements: List[Dict[str, Any]] = Field(default_factory=list)

class SegmentationInput(BaseModel):
    source_file: str
    analysis_result: Dict[str, Any]

# --- Core Segmentation Logic ---

logger = logging.getLogger(__name__)
router = APIRouter()
encoding = tiktoken.get_encoding("cl100k_base")

def get_heading_level(role: str) -> int | None:
    """Extracts the heading level (1-6) from a role string."""
    if role.startswith("h") and len(role) == 2 and role[1].isdigit():
        return int(role[1])
    if role == "sectionHeading": # A common, but less specific role
        return 2 # Default to H2 for generic section headings
    return None

def update_context(context: StructuralContext, role: str, content: str) -> StructuralContext:
    """Updates the structural context with a new heading."""
    level = get_heading_level(role)
    if not level:
        return context

    new_context = context.copy()
    setattr(new_context, f"h{level}", content)
    # Reset all lower-level headings
    for i in range(level + 1, 7):
        setattr(new_context, f"h{i}", None)
    return new_context

def create_rich_segments(analysis_result: Dict[str, Any], source_file: str) -> List[RichSegment]:
    """
    Implements the stateful hierarchical aggregation to create rich segments.
    """
    segments: List[RichSegment] = []
    current_context = StructuralContext()
    
    # Combine paragraphs and tables into a single, ordered list of elements
    all_elements = sorted(
        analysis_result.get("paragraphs", []) + analysis_result.get("tables", []),
        key=lambda x: x["spans"][0]["offset"]
    )

    if not all_elements:
        return []

    buffer_elements: List[Dict[str, Any]] = []
    buffer_token_count = 0
    segment_id_counter = 1

    for element in all_elements:
        element_content = element.get("content", "")
        element_tokens = len(encoding.encode(element_content))
        element_role = element.get("role", "paragraph") # Default role
        
        # Check for logical boundary to finalize a segment
        is_high_level_heading = get_heading_level(element_role) in [1, 2]
        if (
            buffer_token_count >= MIN_SEGMENT_TOKENS and
            (is_high_level_heading or buffer_token_count + element_tokens > MAX_SEGMENT_TOKENS)
        ):
            # Finalize the current segment
            segments.append(RichSegment(
                segment_id=segment_id_counter,
                token_count=buffer_token_count,
                structural_context=current_context, # Context at start of segment
                elements=buffer_elements,
            ))
            # Start a new segment
            segment_id_counter += 1
            buffer_elements = []
            buffer_token_count = 0

        # Update context if the current element is a heading
        if get_heading_level(element_role):
             current_context = update_context(current_context, element_role, element_content)

        # Add current element to the buffer
        buffer_elements.append(element)
        buffer_token_count += element_tokens

    # Add the final buffered segment if it's not empty
    if buffer_elements:
        segments.append(RichSegment(
            segment_id=segment_id_counter,
            token_count=buffer_token_count,
            structural_context=current_context,
            elements=buffer_elements,
        ))

    return segments

# --- FastAPI Endpoint ---

@router.post("/segment", response_model=List[RichSegment])
async def segment_document(payload: SegmentationInput = Body(...)):
    """
    Accepts a full analysis result and segments it into rich,
    structurally-aware chunks.
    """
    logger.info(f"Received segmentation request for {payload.source_file}")
    try:
        rich_segments = create_rich_segments(
            payload.analysis_result, payload.source_file
        )
        return rich_segments
    except Exception as e:
        logger.error(f"Error during segmentation: {e}", exc_info=True)
        # In a real app, you'd return a proper HTTPException
        raise 
