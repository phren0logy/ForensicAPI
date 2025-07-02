#!/usr/bin/env python3
"""
Generate test fixtures from various PDF documents using Azure Document Intelligence.

This script processes multiple PDF types to create comprehensive test fixtures
for different document scenarios (forms, mixed content, academic papers).
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import azure.ai.documentintelligence as adi
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv
from pypdf import PdfReader

# Add parent directory to path to import from routes
sys.path.insert(0, str(Path(__file__).parent.parent))

from routes.extraction import add_ids_to_elements


# --- Configuration ---
SAMPLE_PDFS_DIR = Path("tests/sample_pdfs")
FIXTURES_DIR = Path("tests/fixtures")

# PDF configurations with their output directories and batch sizes
PDF_CONFIGS = {
    "IRS-Form-1099.pdf": {
        "output_dir": "forms",
        "batch_size": 10,  # Small doc, small batches
        "description": "Tax form with tables and form fields"
    },
    "CDC-VIS-covid-19.pdf": {
        "output_dir": "mixed",
        "batch_size": 10,
        "description": "Mixed content document with lists and formatted text"
    },
    "Wolke-Lereya-2015-Long-term-effects-of-bullying.pdf": {
        "output_dir": "academic",
        "batch_size": 20,  # Medium doc
        "description": "Academic paper with figures, tables, and references"
    },
    "Stoker-Dracula.pdf": {
        "output_dir": "dracula",
        "batch_size": 50,  # Large doc, larger batches
        "description": "Long-form narrative text",
        "skip_if_exists": True  # Don't regenerate if already exists
    }
}


def get_pdf_page_count(file_path: str) -> int:
    """Gets the total number of pages in a PDF file."""
    reader = PdfReader(file_path)
    return len(reader.pages)


async def process_single_pdf(
    client: adi.DocumentIntelligenceClient,
    pdf_path: Path,
    output_dir: Path,
    batch_size: int,
    generate_with_ids: bool = True
) -> Dict[str, any]:
    """
    Process a single PDF file and generate fixtures.
    
    Args:
        client: Azure DI client
        pdf_path: Path to PDF file
        output_dir: Directory to save fixtures
        batch_size: Pages per batch
        generate_with_ids: Whether to generate ID-enhanced versions
        
    Returns:
        Statistics about processing
    """
    stats = {
        "filename": pdf_path.name,
        "total_pages": 0,
        "batches_created": 0,
        "elements": {
            "paragraphs": 0,
            "tables": 0,
            "lists": 0,
            "figures": 0,
            "formulas": 0
        }
    }
    
    print(f"\nProcessing '{pdf_path.name}'...")
    total_pages = get_pdf_page_count(str(pdf_path))
    stats["total_pages"] = total_pages
    
    # 1. Generate Ground Truth (full document)
    print("  Generating ground truth for the full document...")
    with open(pdf_path, "rb") as f:
        poller = client.begin_analyze_document(
            "prebuilt-layout", 
            f.read(), 
            content_type="application/pdf",
            output_content_format="markdown"
        )
        full_result = poller.result()
    
    full_result_dict = full_result.as_dict()
    
    # Count elements
    if "paragraphs" in full_result_dict:
        stats["elements"]["paragraphs"] = len(full_result_dict["paragraphs"])
    if "tables" in full_result_dict:
        stats["elements"]["tables"] = len(full_result_dict["tables"])
    if "lists" in full_result_dict:
        stats["elements"]["lists"] = len(full_result_dict["lists"])
    if "figures" in full_result_dict:
        stats["elements"]["figures"] = len(full_result_dict["figures"])
    if "formulas" in full_result_dict:
        stats["elements"]["formulas"] = len(full_result_dict["formulas"])
    
    # Save ground truth (original)
    full_result_path = output_dir / "ground_truth_result.json"
    with open(full_result_path, "w") as f:
        json.dump(full_result_dict, f, indent=2)
    print(f"  Saved ground truth to {full_result_path}")
    
    # Save with IDs if requested
    if generate_with_ids:
        full_result_with_ids = add_ids_to_elements(full_result_dict)
        full_result_ids_path = output_dir / "ground_truth_result_with_ids.json"
        with open(full_result_ids_path, "w") as f:
            json.dump(full_result_with_ids, f, indent=2)
        print(f"  Saved ground truth with IDs to {full_result_ids_path}")
    
    # 2. Generate Batched Results (only if more than batch_size pages)
    if total_pages > batch_size:
        print(f"  Generating batched results in increments of {batch_size} pages...")
        
        for i in range(1, total_pages + 1, batch_size):
            start_page = i
            end_page = min(i + batch_size - 1, total_pages)
            page_range_str = f"{start_page}-{end_page}"
            
            print(f"    - Analyzing page range: {page_range_str}")
            with open(pdf_path, "rb") as f:
                poller = client.begin_analyze_document(
                    "prebuilt-layout",
                    f.read(),
                    pages=page_range_str,
                    content_type="application/pdf",
                    output_content_format="markdown"
                )
                batch_result = poller.result()
            
            batch_result_dict = batch_result.as_dict()
            
            # Save original batch
            batch_filename = f"batch_{page_range_str}.json"
            batch_filepath = output_dir / batch_filename
            with open(batch_filepath, "w") as f:
                json.dump(batch_result_dict, f, indent=2)
            print(f"      Saved to {batch_filepath}")
            
            # Save with IDs if requested
            if generate_with_ids:
                batch_with_ids = add_ids_to_elements(batch_result_dict)
                batch_ids_filename = f"batch_{page_range_str}_with_ids.json"
                batch_ids_filepath = output_dir / batch_ids_filename
                with open(batch_ids_filepath, "w") as f:
                    json.dump(batch_with_ids, f, indent=2)
                print(f"      Saved with IDs to {batch_ids_filepath}")
            
            stats["batches_created"] += 1
    
    return stats


async def main():
    """Main function to generate fixtures for all configured PDFs."""
    load_dotenv()
    endpoint = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
    key = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY")
    
    if not endpoint or not key:
        print("Error: Azure Document Intelligence endpoint/key not set in .env")
        return 1
    
    client = adi.DocumentIntelligenceClient(
        endpoint=endpoint, credential=AzureKeyCredential(key)
    )
    
    print("Azure Document Intelligence Test Fixture Generator")
    print("=" * 60)
    
    all_stats = []
    
    for pdf_filename, config in PDF_CONFIGS.items():
        pdf_path = SAMPLE_PDFS_DIR / pdf_filename
        output_dir = FIXTURES_DIR / config["output_dir"]
        
        # Check if PDF exists
        if not pdf_path.exists():
            print(f"\nWarning: PDF not found: {pdf_path}")
            continue
        
        # Check if should skip
        if config.get("skip_if_exists") and (output_dir / "ground_truth_result.json").exists():
            print(f"\nSkipping {pdf_filename} - fixtures already exist")
            continue
        
        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Process the PDF
        try:
            stats = await process_single_pdf(
                client,
                pdf_path,
                output_dir,
                config["batch_size"]
            )
            all_stats.append(stats)
        except Exception as e:
            print(f"\nError processing {pdf_filename}: {e}")
            continue
    
    # Print summary
    print("\n" + "=" * 60)
    print("Summary of Generated Fixtures:")
    print("=" * 60)
    
    for stats in all_stats:
        print(f"\n{stats['filename']}:")
        print(f"  - Total pages: {stats['total_pages']}")
        print(f"  - Batches created: {stats['batches_created']}")
        print(f"  - Elements found:")
        for elem_type, count in stats['elements'].items():
            if count > 0:
                print(f"    - {elem_type}: {count}")
    
    print("\nFixture generation complete!")
    return 0


if __name__ == "__main__":
    # Use asyncio.run() for the async main function
    import asyncio
    asyncio.run(main())