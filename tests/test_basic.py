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

def test_extract_missing_file():
    resp = client.post("/extract")
    assert resp.status_code == 422  # Missing file field

def test_health_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"
