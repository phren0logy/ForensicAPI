from fastapi import APIRouter, UploadFile, File
from fastapi.responses import PlainTextResponse
from typing import List
import tempfile
import os
import json
from pypdf import PdfReader, PdfWriter
import azure.ai.documentintelligence as adi
import asyncio
from azure.core.credentials import AzureKeyCredential
from utils import ensure_env_loaded

router = APIRouter()

MAX_PDF_PAGES = 2000

def split_pdf_recursive(input_path: str, max_pages: int = MAX_PDF_PAGES) -> List[str]:
    reader = PdfReader(input_path)
    num_pages = len(reader.pages)
    if num_pages <= max_pages:
        return [input_path]
    else:
        mid = num_pages // 2
        temp_files = []
        for start, end in [(0, mid), (mid, num_pages)]:
            writer = PdfWriter()
            for i in range(start, end):
                writer.add_page(reader.pages[i])
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_out:
                writer.write(temp_out)
                temp_files.extend(split_pdf_recursive(temp_out.name, max_pages))
        if os.path.basename(input_path).startswith("tmp"):
            try:
                os.remove(input_path)
            except Exception:
                pass
        return temp_files

def extract_markdown_from_layout_result(result) -> str:
    markdown = []
    for page in result.pages:
        for line in getattr(page, 'lines', []):
            markdown.append(line.content)
    return "\n".join(markdown)

def analyze_pdf_chunk_azure(chunk_path: str, client: adi.DocumentIntelligenceClient) -> str:
    with open(chunk_path, "rb") as f:
        poller = client.begin_analyze_document(
            "prebuilt-layout", f, content_type="application/pdf"
        )
        result = poller.result()
    return extract_markdown_from_layout_result(result)

@router.post("/pdf-to-markdown", response_class=PlainTextResponse)
async def pdf_to_markdown(file: UploadFile = File(...)):
    ensure_env_loaded()
    endpoint = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
    key = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY")
    if not endpoint or not key:
        return "Azure Document Intelligence endpoint/key not set in .env"
    client = adi.DocumentIntelligenceClient(
        endpoint=endpoint,
        credential=AzureKeyCredential(key),
    )
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_in:
        contents = await file.read()
        temp_in.write(contents)
        temp_in.flush()
        temp_path = temp_in.name
    chunk_paths = split_pdf_recursive(temp_path, MAX_PDF_PAGES)
    if temp_path not in chunk_paths:
        try:
            os.remove(temp_path)
        except Exception:
            pass
    try:
        import anyio
        markdown_chunks = []
        for chunk_path in chunk_paths:
            md = await anyio.to_thread.run_sync(analyze_pdf_chunk_azure, chunk_path, client)
            markdown_chunks.append(md)
        combined_md = "\n\n".join(markdown_chunks)
    finally:
        for p in chunk_paths:
            try:
                os.remove(p)
            except Exception:
                pass
    return combined_md
