from fastapi import FastAPI, UploadFile, File
from fastapi.responses import PlainTextResponse
from typing import Optional

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "FastAPI reusable prototyping app. Use /pdf-to-markdown to convert PDFs."}

@app.post("/pdf-to-markdown", response_class=PlainTextResponse)
async def pdf_to_markdown(file: UploadFile = File(...)):
    # Placeholder: just return file name for now
    return f"Received file: {file.filename}\n(PDF to Markdown conversion not yet implemented)"
