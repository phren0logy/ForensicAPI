import asyncio
import json
import os

import azure.ai.documentintelligence as adi
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv

# --- Configuration ---
SOURCE_PDF_PATH = "tests/sample_pdfs/05dracula.pdf"
FIXTURES_DIR = "tests/fixtures"
BATCH_SIZE = 50

# --- Helper to get total pages ---
from pypdf import PdfReader


def get_pdf_page_count(file_path: str) -> int:
    reader = PdfReader(file_path)
    return len(reader.pages)

# --- Main Fixture Generation Logic ---
async def generate_fixtures():
    """
    Connects to the live Azure service to generate test fixture files.
    - A single 'ground_truth' file for the entire document.
    - Multiple 'batch_X-Y' files for each page batch.
    """
    load_dotenv()
    endpoint = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
    key = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY")
    if not endpoint or not key:
        print("Error: Azure Document Intelligence endpoint/key not set in .env")
        return

    os.makedirs(FIXTURES_DIR, exist_ok=True)
    client = adi.DocumentIntelligenceClient(
        endpoint=endpoint, credential=AzureKeyCredential(key)
    )

    print(f"Processing '{SOURCE_PDF_PATH}' with live Azure service...")

    # 1. Generate Ground Truth (full document)
    print("Generating ground truth for the full document...")
    with open(SOURCE_PDF_PATH, "rb") as f:
        poller = client.begin_analyze_document(
            "prebuilt-layout", f.read(), content_type="application/pdf"
        )
        full_result = poller.result()

    full_result_path = os.path.join(FIXTURES_DIR, "ground_truth_result.json")
    with open(full_result_path, "w") as f:
        json.dump(full_result.as_dict(), f, indent=2)
    print(f"Saved ground truth to {full_result_path}")

    # 2. Generate Batched Results
    total_pages = get_pdf_page_count(SOURCE_PDF_PATH)
    print(f"Generating batched results in increments of {BATCH_SIZE} pages...")
    for i in range(1, total_pages + 1, BATCH_SIZE):
        start_page = i
        end_page = min(i + BATCH_SIZE - 1, total_pages)
        page_range_str = f"{start_page}-{end_page}"
        
        print(f"  - Analyzing page range: {page_range_str}")
        with open(SOURCE_PDF_PATH, "rb") as f:
            poller = client.begin_analyze_document(
                "prebuilt-layout",
                f.read(),
                pages=page_range_str,
                content_type="application/pdf",
            )
            batch_result = poller.result()

        batch_filename = f"batch_{page_range_str}.json"
        batch_filepath = os.path.join(FIXTURES_DIR, batch_filename)
        with open(batch_filepath, "w") as f:
            json.dump(batch_result.as_dict(), f, indent=2)
        print(f"    Saved to {batch_filepath}")

    print("\nFixture generation complete.")

if __name__ == "__main__":
    # In Python 3.8+ on Windows, the default event loop policy may need to be changed
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(generate_fixtures()) 
