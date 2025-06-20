"""
LLM Data Filtering Module

This module implements the filtering logic for preparing Azure Document Intelligence
output for LLM consumption, reducing token usage while preserving element traceability.
"""

import logging
from typing import Any, Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, Field
import hashlib
import json

logger = logging.getLogger(__name__)

# --- Pydantic Models ---

class FilterConfig(BaseModel):
    """Configuration for filtering Azure DI elements."""
    filter_preset: str = "legal_analysis"
    essential_fields: List[str] = Field(default_factory=lambda: ["content", "role", "pageNumber"])
    contextual_fields: List[str] = Field(default_factory=list)
    excluded_patterns: List[str] = Field(default_factory=lambda: ["boundingBox", "spans", "confidence"])
    include_element_ids: bool = True

class FilteredElement(BaseModel):
    """Filtered element for LLM consumption."""
    id: Optional[str] = Field(None, alias="_id")
    content: str
    role: Optional[str] = None
    pageNumber: Optional[int] = None
    elementType: Optional[str] = None
    elementIndex: Optional[int] = None
    parentSection: Optional[str] = None
    # Table-specific fields
    rowIndex: Optional[int] = None
    columnIndex: Optional[int] = None
    columnHeader: Optional[str] = None
    
    model_config = {"populate_by_name": True}

class ElementMapping(BaseModel):
    """Mapping between filtered and original elements."""
    filtered_index: int
    azure_element_id: str
    element_type: str
    page_number: int
    content_hash: Optional[str] = None

class FilterMetrics(BaseModel):
    """Metrics about the filtering process."""
    original_size_bytes: int
    filtered_size_bytes: int
    reduction_percentage: float
    total_elements: int
    filtered_elements: int
    excluded_fields: List[str]

# --- Filter Presets ---

FILTER_PRESETS = {
    "legal_analysis": {
        "essential_fields": ["content", "role", "pageNumber", "elementType"],
        "contextual_fields": ["parentSection", "elementIndex"],
        "excluded_patterns": ["boundingBox", "boundingPolygon", "spans", "confidence", "words", "styles"],
    },
    "content_extraction": {
        "essential_fields": ["content", "pageNumber"],
        "contextual_fields": ["role"],
        "excluded_patterns": ["boundingBox", "boundingPolygon", "spans", "confidence", "words", "styles", "boundingRegions"],
    },
    "structured_qa": {
        "essential_fields": ["content", "role", "pageNumber", "elementType"],
        "contextual_fields": ["parentSection"],
        "excluded_patterns": ["boundingBox", "spans", "confidence", "words"],
    },
    "minimal": {
        "essential_fields": ["content", "pageNumber"],
        "contextual_fields": [],
        "excluded_patterns": ["boundingBox", "boundingPolygon", "spans", "confidence", "words", "styles", "boundingRegions", "selectionMarks"],
    }
}

# --- Filtering Logic ---

def generate_element_id(element: Dict[str, Any], index: int) -> str:
    """Generate a unique ID for an element if it doesn't have one."""
    # Try to use existing ID fields
    if "_id" in element:
        return str(element["_id"])
    if "id" in element:
        return str(element["id"])
    
    # Generate ID based on content and position
    content = element.get("content", "")
    page = element.get("pageNumber", 0)
    role = element.get("role", "unknown")
    
    # Create a deterministic ID
    id_string = f"{role}_{page}_{index}_{content[:50]}"
    return f"elem_{hashlib.md5(id_string.encode()).hexdigest()[:8]}"

def should_exclude_field(field_name: str, excluded_patterns: List[str]) -> bool:
    """Check if a field should be excluded based on patterns."""
    field_lower = field_name.lower()
    for pattern in excluded_patterns:
        if pattern.lower() in field_lower:
            return True
    return False

def filter_element(
    element: Dict[str, Any], 
    config: FilterConfig,
    index: int,
    parent_section: Optional[str] = None
) -> Tuple[Optional[FilteredElement], Optional[str]]:
    """
    Filter a single element according to the configuration.
    
    Returns:
        Tuple of (filtered_element, element_id) or (None, None) if element should be skipped
    """
    # Skip empty content
    content = element.get("content", "").strip()
    if not content:
        return None, None
    
    # Generate or extract element ID
    element_id = generate_element_id(element, index)
    
    # Start with essential fields
    filtered_data = {}
    
    # Always include ID if configured
    if config.include_element_ids:
        filtered_data["id"] = element_id
    
    # Add essential fields
    for field in config.essential_fields:
        if field in element:
            filtered_data[field] = element[field]
    
    # Add contextual fields if present
    for field in config.contextual_fields:
        if field in element:
            filtered_data[field] = element[field]
    
    # Special handling for common fields
    filtered_data["content"] = content
    filtered_data["pageNumber"] = element.get("pageNumber", element.get("page_number"))
    filtered_data["elementType"] = element.get("role", element.get("type", "paragraph"))
    
    # Add parent section if available and requested
    if "parentSection" in config.contextual_fields and parent_section:
        filtered_data["parentSection"] = parent_section
    
    # Add element index if requested
    if "elementIndex" in config.contextual_fields:
        filtered_data["elementIndex"] = index
    
    # Handle table-specific fields
    if element.get("role") == "table" or element.get("type") == "table":
        if "rowIndex" in element:
            filtered_data["rowIndex"] = element["rowIndex"]
        if "columnIndex" in element:
            filtered_data["columnIndex"] = element["columnIndex"]
        if "columnHeader" in element:
            filtered_data["columnHeader"] = element["columnHeader"]
    
    try:
        filtered_element = FilteredElement(**filtered_data)
        return filtered_element, element_id
    except Exception as e:
        logger.error(f"Error creating filtered element: {e}")
        return None, None

def extract_elements_from_azure_di(analysis_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract all elements from Azure DI result in reading order."""
    elements = []
    
    # Process pages in order
    pages = analysis_result.get("pages", [])
    for page in pages:
        page_number = page.get("pageNumber", 0)
        
        # Add page elements with page number
        for element_type in ["words", "lines", "paragraphs", "tables", "figures", "formulas"]:
            page_elements = page.get(element_type, [])
            for elem in page_elements:
                elem["pageNumber"] = page_number
                elem["elementType"] = element_type.rstrip("s")  # Remove plural
                elements.append(elem)
    
    # Add document-level elements
    for element_type in ["paragraphs", "tables", "figures", "lists", "keyValuePairs"]:
        doc_elements = analysis_result.get(element_type, [])
        for elem in doc_elements:
            if "pageNumber" not in elem and "boundingRegions" in elem:
                # Extract page number from bounding regions
                regions = elem.get("boundingRegions", [])
                if regions:
                    elem["pageNumber"] = regions[0].get("pageNumber", 0)
            elem["elementType"] = element_type.rstrip("s")
            elements.append(elem)
    
    return elements

def apply_filters(
    analysis_result: Dict[str, Any],
    config: FilterConfig
) -> Tuple[List[FilteredElement], List[ElementMapping], FilterMetrics]:
    """
    Apply filters to Azure DI analysis result.
    
    Returns:
        Tuple of (filtered_elements, element_mappings, metrics)
    """
    # Apply preset if specified
    if config.filter_preset in FILTER_PRESETS:
        preset = FILTER_PRESETS[config.filter_preset]
        # Update config with preset values (keeping any custom overrides)
        if not config.essential_fields:
            config.essential_fields = preset["essential_fields"]
        if not config.excluded_patterns:
            config.excluded_patterns = preset["excluded_patterns"]
    
    # Calculate original size
    original_json = json.dumps(analysis_result)
    original_size = len(original_json.encode('utf-8'))
    
    # Extract all elements
    all_elements = extract_elements_from_azure_di(analysis_result)
    
    # Track current section context
    current_sections = {f"h{i}": None for i in range(1, 7)}
    
    # Filter elements
    filtered_elements = []
    element_mappings = []
    excluded_fields_set = set()
    
    for idx, element in enumerate(all_elements):
        # Update section context if this is a heading
        role = element.get("role", "").lower()
        if role.startswith("h") and len(role) == 2 and role[1].isdigit():
            level = int(role[1])
            if 1 <= level <= 6:
                current_sections[role] = element.get("content", "")
                # Clear lower-level headings
                for i in range(level + 1, 7):
                    current_sections[f"h{i}"] = None
        
        # Determine parent section (highest level heading)
        parent_section = None
        for i in range(1, 7):
            if current_sections[f"h{i}"]:
                parent_section = current_sections[f"h{i}"]
                break
        
        # Filter the element
        filtered_elem, elem_id = filter_element(element, config, idx, parent_section)
        
        if filtered_elem and elem_id:
            filtered_index = len(filtered_elements)
            filtered_elements.append(filtered_elem)
            
            # Create mapping
            mapping = ElementMapping(
                filtered_index=filtered_index,
                azure_element_id=elem_id,
                element_type=element.get("role", element.get("type", "unknown")),
                page_number=element.get("pageNumber", 0),
                content_hash=hashlib.md5(filtered_elem.content.encode()).hexdigest()
            )
            element_mappings.append(mapping)
        
        # Track excluded fields
        for field in element.keys():
            if should_exclude_field(field, config.excluded_patterns):
                excluded_fields_set.add(field)
    
    # Calculate filtered size
    filtered_data = {
        "elements": [elem.model_dump() for elem in filtered_elements],
        "mappings": [mapping.model_dump() for mapping in element_mappings]
    }
    filtered_json = json.dumps(filtered_data)
    filtered_size = len(filtered_json.encode('utf-8'))
    
    # Calculate metrics
    reduction_pct = ((original_size - filtered_size) / original_size * 100) if original_size > 0 else 0
    
    metrics = FilterMetrics(
        original_size_bytes=original_size,
        filtered_size_bytes=filtered_size,
        reduction_percentage=reduction_pct,
        total_elements=len(all_elements),
        filtered_elements=len(filtered_elements),
        excluded_fields=sorted(list(excluded_fields_set))
    )
    
    logger.info(f"Filtering complete: {len(filtered_elements)}/{len(all_elements)} elements kept, "
                f"{reduction_pct:.1f}% size reduction")
    
    return filtered_elements, element_mappings, metrics