from fastapi.testclient import TestClient
from main import app
import io
import json

client = TestClient(app)

def test_root():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "message" in resp.json()
    assert "FastAPI reusable prototyping app" in resp.json()["message"]

def test_compose_prompt_text_only():
    mapping = {"document": "Doc text", "instructions": "Do not share."}
    data = {"mapping": json.dumps(mapping)}
    resp = client.post("/compose-prompt", data=data)
    assert resp.status_code == 200
    assert "<document>" in resp.text
    assert "<instructions>" in resp.text

def test_compose_prompt_file_upload():
    # Compose prompt with a file upload
    file_content = b"File section contents"
    mapping = {"document": "uploaded_file", "instructions": "Do not share."}
    data = {"mapping": json.dumps(mapping)}
    files = {"uploaded_file": ("section.txt", file_content, "text/plain")}
    resp = client.post("/compose-prompt", data=data, files=files)
    assert resp.status_code == 200
    assert "<document>" in resp.text
    assert "File section contents" in resp.text
    assert "<instructions>" in resp.text

def test_pdf_to_markdown_missing_file():
    resp = client.post("/pdf-to-markdown")
    assert resp.status_code == 422  # Missing file field

def test_pdf_to_markdown_invalid_azure(monkeypatch):
    # Patch env to simulate missing Azure credentials
    import os
    monkeypatch.setenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", "")
    monkeypatch.setenv("AZURE_DOCUMENT_INTELLIGENCE_KEY", "")
    file_content = b"%PDF-1.4 fake pdf"
    files = {"file": ("test.pdf", io.BytesIO(file_content), "application/pdf")}
    resp = client.post("/pdf-to-markdown", files=files)
    assert resp.status_code == 200
    assert "Azure Document Intelligence endpoint/key not set" in resp.text
