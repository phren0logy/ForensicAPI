"""
Helper functions to create valid Azure Document Intelligence test data.
Based on the actual Azure DI response format from the extraction endpoint.
"""

def create_azure_di_document(
    content: str,
    paragraphs: list = None,
    tables: list = None,
    pages: list = None,
    include_metadata: bool = True
) -> dict:
    """
    Create a valid Azure DI document structure for testing.
    
    The Azure DI format has elements both at the top level AND nested in pages.
    Top-level elements are used for processing, while page-level elements 
    maintain the document structure.
    """
    doc = {}
    
    if include_metadata:
        doc.update({
            "apiVersion": "2023-07-31",
            "modelId": "prebuilt-layout",
            "stringIndexType": "textElements",
            "contentFormat": "text"
        })
    
    doc["content"] = content
    
    # Add top-level elements (these are what segmentation uses)
    if paragraphs:
        doc["paragraphs"] = paragraphs
    
    if tables:
        doc["tables"] = tables
    
    # Add pages structure (for maintaining document layout)
    if pages:
        doc["pages"] = pages
    
    return doc


def create_paragraph(
    content: str, 
    page_number: int = 1,
    role: str = "paragraph",
    offset: int = 0,
    include_id: bool = True,
    element_index: int = 0
) -> dict:
    """Create a paragraph element with proper structure."""
    para = {
        "content": content,
        "role": role,
        "pageNumber": page_number,
        "spans": [{"offset": offset, "length": len(content)}]
    }
    
    if include_id:
        # Generate a simple ID
        para["_id"] = f"para_{page_number}_{element_index}_{hash(content) % 10000:04x}"
    
    return para


def create_table(
    cells: list,
    page_number: int = 1,
    table_index: int = 0,
    include_id: bool = True
) -> dict:
    """Create a table element with proper structure."""
    # Calculate content from cells
    content_parts = []
    for cell in cells:
        content_parts.append(cell.get("content", ""))
    content = " ".join(content_parts)
    
    table = {
        "content": content,
        "cells": cells,
        "pageNumber": page_number,
        "rowCount": max(cell.get("rowIndex", 0) for cell in cells) + 1,
        "columnCount": max(cell.get("columnIndex", 0) for cell in cells) + 1
    }
    
    if include_id:
        table["_id"] = f"table_{page_number}_{table_index}_{hash(content) % 10000:04x}"
    
    return table


def create_table_cell(
    content: str,
    row_index: int,
    column_index: int,
    include_id: bool = True
) -> dict:
    """Create a table cell element."""
    cell = {
        "content": content,
        "rowIndex": row_index,
        "columnIndex": column_index,
        "kind": "content"
    }
    
    if include_id:
        cell["_id"] = f"cell_{row_index}_{column_index}_{hash(content) % 10000:04x}"
    
    return cell


def create_simple_document(text: str, include_ids: bool = True) -> dict:
    """Create a simple document with one paragraph."""
    para = create_paragraph(text, include_id=include_ids)
    
    return create_azure_di_document(
        content=text,
        paragraphs=[para],
        pages=[{
            "pageNumber": 1,
            "paragraphs": [para.copy()]  # Copy to avoid reference issues
        }]
    )


def create_multi_page_document(
    paragraphs_per_page: list,
    include_ids: bool = True
) -> dict:
    """
    Create a multi-page document.
    
    Args:
        paragraphs_per_page: List of lists, each containing paragraph texts for that page
        include_ids: Whether to include element IDs
    """
    all_paragraphs = []
    pages = []
    offset = 0
    element_index = 0
    
    for page_num, page_paragraphs in enumerate(paragraphs_per_page, 1):
        page_para_elements = []
        
        for para_text in page_paragraphs:
            para = create_paragraph(
                content=para_text,
                page_number=page_num,
                offset=offset,
                include_id=include_ids,
                element_index=element_index
            )
            all_paragraphs.append(para)
            page_para_elements.append(para.copy())
            offset += len(para_text) + 1  # +1 for newline
            element_index += 1
        
        pages.append({
            "pageNumber": page_num,
            "paragraphs": page_para_elements
        })
    
    # Combine all content
    content = "\n".join(
        para["content"] 
        for page_paras in paragraphs_per_page 
        for para in page_paras
    )
    
    return create_azure_di_document(
        content=content,
        paragraphs=all_paragraphs,
        pages=pages
    )


def create_document_with_tables(
    paragraphs: list,
    tables: list,
    include_ids: bool = True
) -> dict:
    """Create a document with both paragraphs and tables."""
    # Create paragraph elements
    para_elements = []
    offset = 0
    for i, para_text in enumerate(paragraphs):
        para = create_paragraph(
            content=para_text,
            offset=offset,
            include_id=include_ids,
            element_index=i
        )
        para_elements.append(para)
        offset += len(para_text) + 1
    
    # Create table elements
    table_elements = []
    for i, table_data in enumerate(tables):
        cells = []
        for cell_data in table_data:
            cell = create_table_cell(
                content=cell_data["content"],
                row_index=cell_data["row"],
                column_index=cell_data["col"],
                include_id=include_ids
            )
            cells.append(cell)
        
        table = create_table(
            cells=cells,
            table_index=i,
            include_id=include_ids
        )
        table_elements.append(table)
    
    # Combine content
    content = "\n".join(para["content"] for para in para_elements)
    content += "\n" + "\n".join(table["content"] for table in table_elements)
    
    return create_azure_di_document(
        content=content,
        paragraphs=para_elements,
        tables=table_elements,
        pages=[{
            "pageNumber": 1,
            "paragraphs": [p.copy() for p in para_elements],
            "tables": [t.copy() for t in table_elements]
        }]
    )