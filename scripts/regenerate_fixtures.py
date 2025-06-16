import asyncio
import json
import os
import sys

# Add project root to the Python path to resolve imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

import azure.ai.documentintelligence as adi
from azure.core.credentials import AzureKeyCredential

from routes.extraction import get_pdf_page_count
from utils import ensure_env_loaded

# --- Constants ---
FIXTURES_DIR = "tests/fixtures"
SAMPLE_PDF_PATH = "tests/sample_pdfs/05dracula.pdf"
BATCH_SIZE = 50


async def regenerate_fixtures():
    """
    Deletes old fixture files and regenerates them by calling the Azure
    Document Intelligence API on the sample PDF.

    This script ensures that the batch files and the ground truth file are
    all generated with the same (current) version of the API and logic.
    """
    print("--- Starting Fixture Regeneration ---")
    ensure_env_loaded()
    endpoint = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
    key = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY")

    if not endpoint or not key:
        raise ValueError("Azure DI endpoint/key not set in .env file.")

    client = adi.DocumentIntelligenceClient(
        endpoint=endpoint, credential=AzureKeyCredential(key)
    )

    # 1. Clean up old fixtures
    print(f"Cleaning up old fixtures in {FIXTURES_DIR}...")
    for filename in os.listdir(FIXTURES_DIR):
        if filename.startswith("batch_") or filename == "ground_truth_result.json":
            os.remove(os.path.join(FIXTURES_DIR, filename))
            print(f"  - Deleted {filename}")

    # 2. Generate new batch fixtures
    print("\nGenerating new batch fixtures...")
    total_pages = get_pdf_page_count(SAMPLE_PDF_PATH)
    print(f"Found {total_pages} pages in {SAMPLE_PDF_PATH}.")

    for i in range(1, total_pages + 1, BATCH_SIZE):
        start_page = i
        end_page = min(i + BATCH_SIZE - 1, total_pages)
        page_range_str = f"{start_page}-{end_page}"
        
        print(f"  - Analyzing page range: {page_range_str}...")
        
        with open(SAMPLE_PDF_PATH, "rb") as f:
            poller = client.begin_analyze_document(
                "prebuilt-layout",
                f.read(),
                pages=page_range_str,
                output_content_format="markdown",
                content_type="application/pdf",
            )
            result = poller.result()

        fixture_filename = f"batch_{page_range_str}.json"
        fixture_path = os.path.join(FIXTURES_DIR, fixture_filename)
        with open(fixture_path, "w") as f:
            json.dump(result.as_dict(), f, indent=2)
            f.write('\n') # Add trailing newline for consistency
        print(f"    ✓ Saved {fixture_filename}")

    # 3. Generate the new ground truth fixture
    print("\nGenerating new ground truth fixture (analyzing full document)...")
    with open(SAMPLE_PDF_PATH, "rb") as f:
        poller = client.begin_analyze_document(
            "prebuilt-layout",
            f.read(),
            output_content_format="markdown",
            content_type="application/pdf",
        )
        result = poller.result()
    
    ground_truth_path = os.path.join(FIXTURES_DIR, "ground_truth_result.json")
    with open(ground_truth_path, "w") as f:
        json.dump(result.as_dict(), f, indent=2)
        f.write('\n')
    print("  ✓ Saved ground_truth_result.json")

    print("\n🎉 Fixture regeneration complete!")


if __name__ == "__main__":
    asyncio.run(regenerate_fixtures()) 
