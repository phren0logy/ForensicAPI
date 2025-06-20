"""
LLM Data Filtering Module

This module implements the filtering logic for preparing Azure Document Intelligence
output for LLM consumption, reducing token usage while preserving element traceability.
"""

import logging
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from pydantic import BaseModel, Field
import hashlib
import json

logger = logging.getLogger(__name__)

# --- Pydantic Models ---

class FilterConfig(BaseModel):
    """Configuration for filtering Azure DI elements."""
    filter_preset: str = "llm_ready"
    fields: List[str] = Field(default_factory=lambda: ["*"])  # Fields to include (allowlist)
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
    kind: Optional[str] = None  # For cell types
    
    model_config = {
        "populate_by_name": True,
        "extra": "allow"  # Allow extra fields for no_filter preset
    }
    
    def model_dump(self, **kwargs):
        """Override to exclude None values by default."""
        kwargs.setdefault('exclude_none', True)
        return super().model_dump(**kwargs)

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
    "no_filter": {
        "fields": ["*"]  # Include all fields
    },
    "citation_optimized": {
        "fields": ["_id", "content", "pageNumber", "elementIndex", "pageFooter"]
    },
    "llm_ready": {
        "fields": ["_id", "content", "pageNumber", "role", "elementType", 
                   "elementIndex", "pageHeader", "pageFooter", "parentSection"]
    },
    "forensic_extraction": {
        "fields": ["_id", "content", "pageNumber", "role", "elementType",
                   "elementIndex", "pageHeader", "pageFooter", "parentSection",
                   "documentMetadata"]
    }
}

# --- Filtering Logic ---

def filter_element(
    element: Dict[str, Any], 
    config: FilterConfig,
    index: int,
    parent_section: Optional[str] = None
) -> Tuple[Optional[Union[FilteredElement, Dict[str, Any]]], Optional[str]]:
    """
    Filter a single element according to the configuration.
    
    Uses an allowlist approach - only fields in config.fields are included.
    
    Returns:
        Tuple of (filtered_element, element_id) or (None, None) if element should be skipped
    """
    # Skip empty content
    content = element.get("content", "").strip()
    if not content:
        return None, None
    
    # Extract element ID from input (should already have _id from extraction phase)
    element_id = element.get("_id", element.get("id"))
    
    # Start with empty filtered data
    filtered_data = {}
    
    # Handle special case: "*" means include all fields
    if "*" in config.fields:
        # Include all fields from the element
        filtered_data = element.copy()
    else:
        # Include only fields in the allowlist
        for field in config.fields:
            if field == "_id":
                # Special handling for ID field
                if config.include_element_ids and element_id:
                    filtered_data["_id"] = element_id
            elif field == "pageNumber":
                # Handle alternate field names
                value = element.get("pageNumber", element.get("page_number"))
                if value is not None:
                    filtered_data["pageNumber"] = value
            elif field == "elementType":
                # Map from role or type to elementType
                value = element.get("elementType", element.get("role", element.get("type")))
                if value:
                    filtered_data["elementType"] = value
            elif field == "parentSection":
                # Special field that comes from context, not element
                if parent_section:
                    filtered_data["parentSection"] = parent_section
            elif field == "elementIndex":
                # Special field that comes from index parameter
                filtered_data["elementIndex"] = index
            elif field in element:
                # Direct field copy
                filtered_data[field] = element[field]
    
    # Ensure content is always included if we have any data
    if filtered_data and "content" not in filtered_data:
        filtered_data["content"] = content
    
    try:
        # For no_filter preset, return raw dict to preserve all fields
        if "*" in config.fields:
            # Ensure _id is included if configured
            if config.include_element_ids and element_id and "_id" not in filtered_data:
                filtered_data["_id"] = element_id
            return filtered_data, element_id
        else:
            # For other presets, use FilteredElement model for validation
            filtered_element = FilteredElement.model_validate(filtered_data)
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
) -> Tuple[List[Union[FilteredElement, Dict[str, Any]]], List[ElementMapping], FilterMetrics]:
    """
    Apply filters to Azure DI analysis result.
    
    Returns:
        Tuple of (filtered_elements, element_mappings, metrics)
    """
    # Apply preset if specified
    if config.filter_preset in FILTER_PRESETS:
        preset = FILTER_PRESETS[config.filter_preset]
        # Use preset fields
        config.fields = preset["fields"]
    
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
            
            # Get content for hash - handle both dict and FilteredElement
            if isinstance(filtered_elem, dict):
                content = filtered_elem.get("content", "")
            else:
                content = filtered_elem.content
            
            # Create mapping
            mapping = ElementMapping(
                filtered_index=filtered_index,
                azure_element_id=elem_id,
                element_type=element.get("role", element.get("type", "unknown")),
                page_number=element.get("pageNumber", 0),
                content_hash=hashlib.md5(content.encode()).hexdigest()
            )
            element_mappings.append(mapping)
        
        # Track excluded fields (fields in original but not in filtered)
        if filtered_elem:
            if isinstance(filtered_elem, dict):
                filtered_fields = set(filtered_elem.keys())
            else:
                filtered_fields = set(filtered_elem.model_dump(exclude_none=True).keys())
            
            for field in element.keys():
                if field not in filtered_fields and field != "_id":  # _id might be renamed
                    excluded_fields_set.add(field)
    
    # Calculate filtered size
    filtered_data = {
        "elements": [
            elem if isinstance(elem, dict) else elem.model_dump()
            for elem in filtered_elements
        ],
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