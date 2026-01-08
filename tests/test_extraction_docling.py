"""
Docling-serve fixtures and optional live integration tests.
"""

import io
import json
import os
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from main import app
from utils import ensure_env_loaded

client = TestClient(app)


def create_test_pdf() -> bytes:
    """Create a simple single-page PDF."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    c.drawString(100, 700, "Docling-serve test PDF")
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.read()


def load_docling_fixture(name: str) -> dict:
    fixtures_dir = Path(__file__).parent / "fixtures" / "docling"
    fixture_path = fixtures_dir / name
    if not fixture_path.exists():
        pytest.skip(f"Fixture not found: {fixture_path}")
    return json.loads(fixture_path.read_text())


def test_docling_fixture_format():
    """Fixtures should match docling-serve v1 response format."""
    data = load_docling_fixture("irs_form_1099_docling.json")
    assert "document" in data
    assert "status" in data
    document = data["document"]
    assert isinstance(document.get("md_content"), str)
    assert isinstance(document.get("json_content"), dict)


def test_anonymize_markdown_with_docling_fixture():
    """Docling markdown should work with markdown anonymization endpoint."""
    data = load_docling_fixture("irs_form_1099_docling.json")
    markdown = data.get("document", {}).get("md_content", "")[:2000]

    resp = client.post(
        "/anonymization/anonymize-markdown",
        json={"markdown_text": markdown},
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload.get("anonymized_text")
    assert "vault_data" in payload


def test_docling_serve_live_optional():
    """Optionally exercise a live docling-serve instance if configured."""
    ensure_env_loaded()
    base_url = os.getenv("DOCLING_SERVE_BASE_URL")
    if not base_url:
        pytest.skip("DOCLING_SERVE_BASE_URL not set")

    headers = {}
    api_key = os.getenv("DOCLING_SERVE_API_KEY")
    if api_key:
        headers["X-Api-Key"] = api_key

    pdf_bytes = create_test_pdf()
    files = {"files": ("test.pdf", pdf_bytes, "application/pdf")}
    data = {"to_formats": ["md", "json"], "do_ocr": "false"}

    try:
        with httpx.Client(timeout=30.0) as client_http:
            response = client_http.post(
                f"{base_url.rstrip('/')}/v1/convert/file",
                files=files,
                data=data,
                headers=headers,
            )
    except httpx.RequestError:
        pytest.skip("docling-serve not reachable")

    assert response.status_code == 200
    payload = response.json()
    assert "document" in payload
    assert "md_content" in payload["document"]
    assert "json_content" in payload["document"]


def test_segment_docling_from_fixture():
    """Chunk docling-serve fixture using the local chunking endpoint."""
    try:
        import docling_core  # noqa: F401
    except Exception:
        pytest.skip("docling-core not available")

    data = load_docling_fixture("irs_form_1099_docling.json")
    payload = {
        "source_file": "irs_form_1099.pdf",
        "docling_response": data,
        "min_segment_tokens": 50,
        "max_segment_tokens": 1000,
        "merge_peers": True,
    }

    resp = client.post("/segment-docling", json=payload)
    assert resp.status_code == 200
    segments = resp.json()
    assert isinstance(segments, list)
    assert segments
    first = segments[0]
    assert "segment_id" in first
    assert "token_count" in first
    assert "elements" in first
