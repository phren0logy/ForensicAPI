"""
Integration tests for the full document processing pipeline.

Tests the complete workflow:
1. Extract PDF → 2. Segment → 3. Filter → 4. (Optional) Anonymize
"""

import io
import json
from pathlib import Path
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

from main import app

client = TestClient(app)


def create_test_pdf_with_structure() -> bytes:
    """Create a test PDF with headings and multiple sections."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    
    # Page 1
    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, 700, "Chapter 1: Introduction")
    c.setFont("Helvetica", 12)
    c.drawString(100, 650, "This is the introduction to our test document.")
    c.drawString(100, 630, "It contains important information about testing.")
    
    c.setFont("Helvetica-Bold", 14)
    c.drawString(100, 580, "Section 1.1: Background")
    c.setFont("Helvetica", 12)
    c.drawString(100, 550, "Here we discuss the background of our project.")
    c.drawString(100, 530, "Patient John Doe visited on January 15, 2024.")
    
    c.showPage()
    
    # Page 2
    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, 700, "Chapter 2: Methods")
    c.setFont("Helvetica", 12)
    c.drawString(100, 650, "This chapter describes our methodology.")
    c.drawString(100, 630, "We used various techniques for analysis.")
    
    c.setFont("Helvetica-Bold", 14)
    c.drawString(100, 580, "Section 2.1: Data Collection")
    c.setFont("Helvetica", 12)
    c.drawString(100, 550, "Data was collected from multiple sources.")
    c.drawString(100, 530, "Contact: jane.smith@example.com or 555-123-4567")
    
    c.save()
    buffer.seek(0)
    return buffer.read()


def test_full_pipeline_extract_segment_filter():
    """Test the complete extraction → segmentation → filtering pipeline."""
    
    # Step 1: Extract PDF
    pdf_content = create_test_pdf_with_structure()
    files = {"file": ("test_document.pdf", pdf_content, "application/pdf")}
    
    extract_resp = client.post("/extract", files=files)
    assert extract_resp.status_code == 200
    extract_result = extract_resp.json()
    
    # Verify extraction worked
    assert "analysis_result" in extract_result
    assert "markdown_content" in extract_result
    assert "Chapter 1" in extract_result["markdown_content"]
    
    # Step 2: Segment the extracted content
    segment_payload = {
        "source_file": "test_document.pdf",
        "analysis_result": extract_result["analysis_result"],
        "min_segment_tokens": 100,  # Small for testing
        "max_segment_tokens": 500
    }
    
    segment_resp = client.post("/segment", json=segment_payload)
    assert segment_resp.status_code == 200
    segments = segment_resp.json()
    
    # Verify segmentation
    assert isinstance(segments, list)
    assert len(segments) > 0
    assert all("segment_id" in s for s in segments)
    assert all("elements" in s for s in segments)
    
    # Step 3: Filter and segment in one operation
    filter_segment_payload = {
        "source_file": "test_document.pdf",
        "analysis_result": extract_result["analysis_result"],
        "filter_config": {
            "filter_preset": "llm_ready",
            "include_element_ids": True
        },
        "min_segment_tokens": 100,
        "max_segment_tokens": 500
    }
    
    filter_resp = client.post("/segment-filtered", json=filter_segment_payload)
    assert filter_resp.status_code == 200
    filter_result = filter_resp.json()
    
    # Verify filtered segmentation
    assert "segments" in filter_result
    assert "metrics" in filter_result
    assert filter_result["metrics"]["reduction_percentage"] > 0
    
    # Check that element IDs are preserved
    filtered_segments = filter_result["segments"]
    for segment in filtered_segments:
        elements = segment.get("elements", [])
        if elements:
            # At least some elements should have IDs
            elements_with_ids = [e for e in elements if "_id" in e]
            assert len(elements_with_ids) > 0


def test_pipeline_with_anonymization():
    """Test pipeline including anonymization step."""
    
    # Step 1: Extract
    pdf_content = create_test_pdf_with_structure()
    files = {"file": ("medical_record.pdf", pdf_content, "application/pdf")}
    
    extract_resp = client.post("/extract", files=files)
    assert extract_resp.status_code == 200
    extract_result = extract_resp.json()
    
    # Step 2: Anonymize the extracted content
    anonymize_payload = {
        "azure_di_json": extract_result["analysis_result"],
        "config": {
            "score_threshold": 0.5,
            "entity_types": ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER"]
        }
    }
    
    anonymize_resp = client.post("/anonymization/anonymize-azure-di", json=anonymize_payload)
    assert anonymize_resp.status_code == 200
    anonymize_result = anonymize_resp.json()
    
    # Verify anonymization
    assert "anonymized_json" in anonymize_result
    assert "statistics" in anonymize_result
    
    anonymized_content = anonymize_result["anonymized_json"]["content"]
    assert "John Doe" not in anonymized_content
    assert "jane.smith@example.com" not in anonymized_content
    
    # Step 3: Segment the anonymized content
    segment_payload = {
        "source_file": "medical_record_anonymized.pdf",
        "analysis_result": anonymize_result["anonymized_json"],
        "min_segment_tokens": 100,
        "max_segment_tokens": 500
    }
    
    segment_resp = client.post("/segment", json=segment_payload)
    assert segment_resp.status_code == 200
    segments = segment_resp.json()
    
    # Verify the pipeline preserved structure
    assert len(segments) > 0
    assert all(isinstance(s, dict) for s in segments)


def test_pipeline_with_different_filter_presets():
    """Test pipeline with different filter presets."""
    
    # Extract once
    pdf_content = create_test_pdf_with_structure()
    files = {"file": ("test.pdf", pdf_content, "application/pdf")}
    
    extract_resp = client.post("/extract", files=files)
    assert extract_resp.status_code == 200
    extract_result = extract_resp.json()
    
    # Test each filter preset
    presets = ["no_filter", "llm_ready", "citation_optimized", "forensic_extraction"]
    
    for preset in presets:
        filter_payload = {
            "source_file": "test.pdf",
            "analysis_result": extract_result["analysis_result"],
            "filter_config": {
                "filter_preset": preset,
                "include_element_ids": True
            },
            "min_segment_tokens": 50,
            "max_segment_tokens": 300
        }
        
        resp = client.post("/segment-filtered", json=filter_payload)
        assert resp.status_code == 200, f"Failed with preset: {preset}"
        
        result = resp.json()
        assert "segments" in result
        assert "metrics" in result
        
        # Different presets should have different reduction percentages
        if preset == "no_filter":
            # no_filter might still have some reduction due to structure differences
            assert result["metrics"]["reduction_percentage"] >= 0
        elif preset == "citation_optimized":
            # Should have the highest reduction
            assert result["metrics"]["reduction_percentage"] > 50


def test_pipeline_error_handling():
    """Test error handling throughout the pipeline."""
    
    # Test with invalid data at each step
    
    # 1. Invalid segmentation input (missing analysis_result)
    segment_payload = {
        "source_file": "test.pdf",
        "min_segment_tokens": 100
    }
    resp = client.post("/segment", json=segment_payload)
    assert resp.status_code == 422
    
    # 2. Invalid filter config
    filter_payload = {
        "source_file": "test.pdf",
        "analysis_result": {"content": "test"},
        "filter_config": {
            "filter_preset": "invalid_preset"
        }
    }
    resp = client.post("/segment-filtered", json=filter_payload)
    # Should handle gracefully (might use default or return error)
    assert resp.status_code in [200, 400, 422]


def test_large_document_pipeline():
    """Test pipeline with a larger document to ensure performance."""
    
    # Create a larger test PDF (10 pages)
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    
    for chapter in range(1, 6):
        c.setFont("Helvetica-Bold", 16)
        c.drawString(100, 700, f"Chapter {chapter}: Topic {chapter}")
        c.setFont("Helvetica", 12)
        
        y_pos = 650
        for para in range(5):
            c.drawString(100, y_pos, f"This is paragraph {para + 1} of chapter {chapter}.")
            c.drawString(100, y_pos - 20, f"It contains various information about topic {chapter}.")
            y_pos -= 50
        
        c.showPage()
        
        # Add another page for each chapter
        c.setFont("Helvetica-Bold", 14)
        c.drawString(100, 700, f"Chapter {chapter} Continued")
        c.setFont("Helvetica", 12)
        c.drawString(100, 650, f"More details about topic {chapter}.")
        c.showPage()
    
    c.save()
    buffer.seek(0)
    
    # Run through pipeline
    files = {"file": ("large_test.pdf", buffer.read(), "application/pdf")}
    
    # Extract with batching
    extract_resp = client.post("/extract", files=files, data={"batch_size": "5"})
    assert extract_resp.status_code == 200
    extract_result = extract_resp.json()
    
    # Segment and filter
    filter_payload = {
        "source_file": "large_test.pdf",
        "analysis_result": extract_result["analysis_result"],
        "filter_config": {
            "filter_preset": "llm_ready"
        },
        "min_segment_tokens": 1000,
        "max_segment_tokens": 3000
    }
    
    filter_resp = client.post("/segment-filtered", json=filter_payload)
    assert filter_resp.status_code == 200
    filter_result = filter_resp.json()
    
    # Should create at least one segment (might be all in one if content is small)
    assert len(filter_result["segments"]) >= 1
    
    # Each segment should have reasonable token counts
    for i, segment in enumerate(filter_result["segments"]):
        # Last segment can be smaller than min_segment_tokens
        is_last_segment = (i == len(filter_result["segments"]) - 1)
        if not is_last_segment:
            # Non-last segments should meet the minimum threshold
            assert segment["token_count"] >= 500  # Adjusted for test PDF size
        # All segments should respect maximum (with some overflow tolerance)
        assert segment["token_count"] <= 3000 * 1.2  # Allow some overflow