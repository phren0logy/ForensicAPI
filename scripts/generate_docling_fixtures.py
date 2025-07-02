#!/usr/bin/env python3
"""
Generate test fixtures using the Docling local extraction endpoint.

This script processes PDFs through the /extract-local endpoint to create
fixtures in Docling's native format for comparison with Azure DI results.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any

import requests
from pypdf import PdfReader


# --- Configuration ---
SAMPLE_PDFS_DIR = Path("tests/sample_pdfs")
FIXTURES_DIR = Path("tests/fixtures/docling")
API_BASE_URL = "http://127.0.0.1:8000"

# PDFs to process
PDF_FILES = [
    "IRS-Form-1099.pdf",
    "CDC-VIS-covid-19.pdf", 
    "Wolke-Lereya-2015-Long-term-effects-of-bullying.pdf",
    "Stoker-Dracula.pdf"
]


def get_pdf_page_count(file_path: str) -> int:
    """Gets the total number of pages in a PDF file."""
    reader = PdfReader(file_path)
    return len(reader.pages)


def process_pdf_with_docling(pdf_path: Path, ocr_enabled: bool = True) -> Dict[str, Any]:
    """
    Process a PDF file through the /extract-local endpoint.
    
    Args:
        pdf_path: Path to PDF file
        ocr_enabled: Whether to enable OCR
        
    Returns:
        Response data from the endpoint
    """
    print(f"  Sending {pdf_path.name} to /extract-local endpoint...")
    
    with open(pdf_path, 'rb') as f:
        files = {'file': (pdf_path.name, f, 'application/pdf')}
        data = {
            'ocr_enabled': str(ocr_enabled).lower(),
            'ocr_lang': 'en'
        }
        
        response = requests.post(
            f"{API_BASE_URL}/extract-local",
            files=files,
            data=data
        )
    
    if response.status_code != 200:
        raise Exception(f"API returned status {response.status_code}: {response.text}")
    
    return response.json()


def extract_statistics(docling_response: Dict[str, Any]) -> Dict[str, Any]:
    """Extract statistics from Docling response."""
    stats = {
        "pages": 0,
        "elements": {
            "text": 0,
            "table": 0,
            "list": 0,
            "figure": 0,
            "heading": 0,
            "paragraph": 0
        }
    }
    
    # Get page count from docling document
    docling_doc = docling_response.get("docling_document", {})
    pages = docling_doc.get("pages", {})
    stats["pages"] = len(pages)
    
    # Count elements by type
    # Note: Docling uses a different structure than Azure DI
    # Elements are stored in the pages structure
    for page_id, page_data in pages.items():
        if "elements" in page_data:
            for elem in page_data["elements"]:
                elem_type = elem.get("type", "unknown")
                if elem_type in stats["elements"]:
                    stats["elements"][elem_type] += 1
    
    # Also check for elements in the main document structure
    if "elements" in docling_doc:
        for elem_id, elem_data in docling_doc["elements"].items():
            elem_type = elem_data.get("type", "unknown")
            if elem_type == "text":
                # Further classify text elements
                if elem_data.get("is_heading"):
                    stats["elements"]["heading"] += 1
                else:
                    stats["elements"]["paragraph"] += 1
            elif elem_type in stats["elements"]:
                stats["elements"][elem_type] += 1
    
    return stats


def main():
    """Main function to generate Docling fixtures."""
    print("Docling Test Fixture Generator")
    print("=" * 60)
    
    # Check if server is running
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        if response.status_code != 200:
            print("Error: FastAPI server is not running at http://127.0.0.1:8000")
            print("Please start the server with: uv run run.py")
            return 1
    except requests.ConnectionError:
        print("Error: Cannot connect to FastAPI server at http://127.0.0.1:8000")
        print("Please start the server with: uv run run.py")
        return 1
    
    # Create output directory
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    
    all_stats = []
    
    for pdf_filename in PDF_FILES:
        pdf_path = SAMPLE_PDFS_DIR / pdf_filename
        
        # Check if PDF exists
        if not pdf_path.exists():
            print(f"\nWarning: PDF not found: {pdf_path}")
            continue
        
        print(f"\nProcessing '{pdf_filename}'...")
        print(f"  File size: {pdf_path.stat().st_size / 1024 / 1024:.1f} MB")
        print(f"  Page count: {get_pdf_page_count(pdf_path)}")
        
        try:
            # Process with OCR enabled
            response_data = process_pdf_with_docling(pdf_path, ocr_enabled=True)
            
            # Extract base filename without extension
            base_name = pdf_path.stem.lower().replace(" ", "_").replace("-", "_")
            
            # Save full response
            output_path = FIXTURES_DIR / f"{base_name}_docling.json"
            with open(output_path, 'w') as f:
                json.dump(response_data, f, indent=2)
            print(f"  Saved fixture to: {output_path}")
            
            # Save just the markdown content for easy comparison
            markdown_path = FIXTURES_DIR / f"{base_name}_markdown.md"
            with open(markdown_path, 'w') as f:
                f.write(response_data.get("markdown_content", ""))
            print(f"  Saved markdown to: {markdown_path}")
            
            # Extract and print statistics
            stats = extract_statistics(response_data)
            stats["filename"] = pdf_filename
            stats["ocr_applied"] = response_data.get("ocr_applied", False)
            all_stats.append(stats)
            
            print(f"  OCR applied: {stats['ocr_applied']}")
            print(f"  Pages processed: {stats['pages']}")
            print(f"  Elements found:")
            for elem_type, count in stats['elements'].items():
                if count > 0:
                    print(f"    - {elem_type}: {count}")
                    
        except Exception as e:
            print(f"  Error processing {pdf_filename}: {e}")
            continue
    
    # Print summary
    print("\n" + "=" * 60)
    print("Summary of Docling Fixtures:")
    print("=" * 60)
    
    for stats in all_stats:
        print(f"\n{stats['filename']}:")
        print(f"  - Pages: {stats['pages']}")
        print(f"  - OCR applied: {stats['ocr_applied']}")
        total_elements = sum(stats['elements'].values())
        print(f"  - Total elements: {total_elements}")
    
    # Create a comparison README
    readme_path = FIXTURES_DIR / "README.md"
    with open(readme_path, 'w') as f:
        f.write("# Docling Test Fixtures\n\n")
        f.write("This directory contains test fixtures generated using the Docling local extraction endpoint.\n\n")
        f.write("## Files\n\n")
        f.write("- `*_docling.json` - Full Docling response including document structure\n")
        f.write("- `*_markdown.md` - Extracted markdown content for easy reading\n\n")
        f.write("## Key Differences from Azure DI\n\n")
        f.write("1. **Format**: Docling uses a different JSON structure with elements organized by page\n")
        f.write("2. **Element IDs**: Docling doesn't currently generate element IDs\n")
        f.write("3. **Filtering**: The /extract-local endpoint doesn't support filtering\n")
        f.write("4. **OCR**: Uses ocrmac on macOS, EasyOCR on other platforms\n\n")
        f.write("## Statistics\n\n")
        for stats in all_stats:
            f.write(f"### {stats['filename']}\n")
            f.write(f"- Pages: {stats['pages']}\n")
            f.write(f"- OCR applied: {stats['ocr_applied']}\n")
            for elem_type, count in stats['elements'].items():
                if count > 0:
                    f.write(f"- {elem_type.capitalize()}: {count}\n")
            f.write("\n")
    
    print(f"\nCreated README at: {readme_path}")
    print("\nDocling fixture generation complete!")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())