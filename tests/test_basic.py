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

def test_anonymize_azure_di_basic():
    # Test anonymization with basic Azure DI JSON structure
    azure_di_json = {
        "status": "succeeded",
        "content": "Patient: John Smith\nSSN: 123-45-6789",
        "paragraphs": [
            {
                "_id": "para_1_0_abc123",
                "content": "Patient: John Smith visited on January 15, 2024",
                "role": "paragraph",
                "pageNumber": 1
            }
        ]
    }
    
    payload = {
        "azure_di_json": azure_di_json,
        "config": {
            "score_threshold": 0.5,
            "entities_to_recognize": ["PERSON", "US_SSN", "DATE_TIME"]
        }
    }
    
    resp = client.post("/anonymize-azure-di", json=payload)
    assert resp.status_code == 200
    
    result = resp.json()
    assert "anonymized_json" in result
    assert "statistics" in result
    
    # Check that PII was anonymized
    anonymized_content = result["anonymized_json"]["content"]
    assert "John Smith" not in anonymized_content
    assert "123-45-6789" not in anonymized_content
    
    # Check that element IDs are preserved
    assert result["anonymized_json"]["paragraphs"][0]["_id"] == "para_1_0_abc123"

def test_anonymize_azure_di_missing_payload():
    resp = client.post("/anonymize-azure-di")
    assert resp.status_code == 422  # Unprocessable Entity
