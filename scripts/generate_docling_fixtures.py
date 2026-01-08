#!/usr/bin/env python3
"""
Generate test fixtures using a docling-serve instance.

This script processes PDFs through docling-serve to create fixtures in
standard docling-serve v1 response format for comparison with Azure DI results.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any

import httpx
from pypdf import PdfReader


# --- Configuration ---
SAMPLE_PDFS_DIR = Path("tests/sample_pdfs")
FIXTURES_DIR = Path("tests/fixtures/docling")
DOCLING_SERVE_BASE_URL = os.getenv("DOCLING_SERVE_BASE_URL", "http://127.0.0.1:5001").rstrip("/")
DOCLING_SERVE_API_KEY = os.getenv("DOCLING_SERVE_API_KEY")

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
    Process a PDF file through docling-serve.
    
    Args:
        pdf_path: Path to PDF file
        ocr_enabled: Whether to enable OCR
        
    Returns:
        Response data from docling-serve
    """
    print(f"  Sending {pdf_path.name} to docling-serve...")

    headers = {}
    if DOCLING_SERVE_API_KEY:
        headers["X-Api-Key"] = DOCLING_SERVE_API_KEY

    with open(pdf_path, "rb") as f:
        files = {"files": (pdf_path.name, f, "application/pdf")}
        data = {
            "to_formats": ["md", "json"],
            "do_ocr": str(ocr_enabled).lower(),
            "ocr_lang": "en",
        }

        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{DOCLING_SERVE_BASE_URL}/v1/convert/file",
                files=files,
                data=data,
                headers=headers,
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
    document = docling_response.get("document", {})
    docling_doc = document.get("json_content", {})
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
    print("Docling-serve Test Fixture Generator")
    print("=" * 60)
    
    # Check if docling-serve is reachable
    try:
        with httpx.Client(timeout=5.0) as client:
            client.get(DOCLING_SERVE_BASE_URL)
    except httpx.RequestError:
        print(f"Error: Cannot connect to docling-serve at {DOCLING_SERVE_BASE_URL}")
        print("Please start docling-serve and/or set DOCLING_SERVE_BASE_URL.")
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
                document = response_data.get("document", {})
                f.write(document.get("md_content", ""))
            print(f"  Saved markdown to: {markdown_path}")
            
            # Extract and print statistics
            stats = extract_statistics(response_data)
            stats["filename"] = pdf_filename
            stats["ocr_applied"] = ocr_enabled
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
        f.write("This directory contains test fixtures generated using docling-serve.\n\n")
        f.write("## Files\n\n")
        f.write("- `*_docling.json` - Full docling-serve response including document structure\n")
        f.write("- `*_markdown.md` - Extracted markdown content for easy reading\n\n")
        f.write("## Key Differences from Azure DI\n\n")
        f.write("1. **Format**: Docling uses a different JSON structure with elements organized by page\n")
        f.write("2. **Element IDs**: Docling doesn't currently generate element IDs\n")
        f.write("3. **OCR**: Controlled by docling-serve parameters\n\n")
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
