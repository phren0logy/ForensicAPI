from fastapi import FastAPI, UploadFile, File, Form, Request, APIRouter, Body, status, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse
from fastapi.datastructures import UploadFile as FastAPIUploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Optional, Any
import tempfile
import os
import json
from pypdf import PdfReader, PdfWriter
from dotenv import load_dotenv
import azure.ai.documentintelligence as adi
import asyncio

app = FastAPI()

MAX_PDF_PAGES = 2000

# Load Azure credentials from .env at startup
env_loaded = False
def ensure_env_loaded():
    global env_loaded
    if not env_loaded:
        load_dotenv()
        env_loaded = True

def split_pdf_recursive(input_path: str, max_pages: int = MAX_PDF_PAGES) -> List[str]:
    """Recursively split a PDF into chunks of <= max_pages, saving to temp files. Returns list of temp file paths."""
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
        # Optionally delete the original input_path if it was a temp file
        if os.path.basename(input_path).startswith("tmp"):
            try:
                os.remove(input_path)
            except Exception:
                pass
        return temp_files

def extract_markdown_from_layout_result(result) -> str:
    # Placeholder: extract markdown from layout result. Adjust as needed for your needs.
    # Here, we simply concatenate all text lines.
    markdown = []
    for page in result.pages:
        for line in getattr(page, 'lines', []):
            markdown.append(line.content)
    return "\n".join(markdown)

def analyze_pdf_chunk_azure(chunk_path: str, client: adi.DocumentIntelligenceClient) -> str:
    # Use Azure DocumentIntelligence layout model with built-in retry logic
    with open(chunk_path, "rb") as f:
        poller = client.begin_analyze_document(
            "prebuilt-layout", f, content_type="application/pdf"
        )
        result = poller.result()
    return extract_markdown_from_layout_result(result)

@app.get("/")
def read_root():
    return {"message": "FastAPI reusable prototyping app. Use /pdf-to-markdown to convert PDFs."}

@app.post("/pdf-to-markdown", response_class=PlainTextResponse)
async def pdf_to_markdown(file: UploadFile = File(...)):
    ensure_env_loaded()
    import os
    endpoint = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
    key = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY")
    if not endpoint or not key:
        return "Azure Document Intelligence endpoint/key not set in .env"
    # Azure client with retry logic
    from azure.core.credentials import AzureKeyCredential
    client = adi.DocumentIntelligenceClient(
        endpoint=endpoint,
        credential=AzureKeyCredential(key),
    )
    # Save uploaded file to a temp file
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
    # Analyze all chunks and collect markdown
    try:
        import anyio
        markdown_chunks = []
        for chunk_path in chunk_paths:
            md = await anyio.to_thread.run_sync(analyze_pdf_chunk_azure, chunk_path, client)
            markdown_chunks.append(md)
        combined_md = "\n\n".join(markdown_chunks)
    finally:
        # Clean up all temp files
        for p in chunk_paths:
            try:
                os.remove(p)
            except Exception:
                pass
    return combined_md

@app.post("/compose-prompt", response_class=PlainTextResponse)
async def compose_prompt(request: Request):
    """
    Accepts a multipart/form-data request with:
    - A 'mapping' JSON field: {"tag1": "string or filename", ...}
    - Optional files: each with their field name matching a tag or filename in the mapping.
    For each tag, if a file is uploaded for the value, use its contents; otherwise, use the string directly.
    """
    # Parse multipart form
    form = await request.form()
    # Extract mapping JSON from form
    mapping_json = form.get("mapping")
    if mapping_json is None:
        raise HTTPException(status_code=400, detail="Missing 'mapping' field in form data.")
    try:
        mapping = json.loads(mapping_json)
    except Exception:
        raise HTTPException(status_code=400, detail="'mapping' field is not valid JSON.")
    # Prepare result
    composed_sections = []
    instructions_section = None
    for tag, value in mapping.items():
        file_obj = form.get(value)
        if isinstance(file_obj, FastAPIUploadFile):
            file_bytes = await file_obj.read()
            content = file_bytes.decode("utf-8", errors="replace")
        else:
            content = value
        wrapped = f"<{tag}>\n{content}\n</{tag}>"
        if tag.lower() == "instructions":
            instructions_section = wrapped
        else:
            composed_sections.append(wrapped)
    if instructions_section:
        combined = f"{instructions_section}\n\n" + "\n\n".join(composed_sections) + f"\n\n{instructions_section}"
    else:
        combined = "\n\n".join(composed_sections)
    return combined
