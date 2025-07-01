"""Test LLM-Guard integration with the anonymization endpoints"""

import pytest
import httpx
from datetime import datetime, timedelta
import json

BASE_URL = "http://localhost:8000"


@pytest.mark.asyncio
async def test_health_endpoint():
    """Test that the anonymization health check works with LLM-Guard"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/anonymization/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "AI4Privacy" in data["recognizers"]
        assert data["model"] == "Isotonic/distilbert_finetuned_ai4privacy_v2"


@pytest.mark.asyncio
async def test_markdown_anonymization():
    """Test markdown anonymization with LLM-Guard"""
    async with httpx.AsyncClient() as client:
        request_data = {
            "markdown_text": "Contact John Doe at john@example.com or call 555-123-4567.",
            "config": {
                "entity_types": ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER"],
                "score_threshold": 0.5
            }
        }
        
        response = await client.post(
            f"{BASE_URL}/anonymization/anonymize-markdown",
            json=request_data
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check that entities were detected and replaced
        assert "john@example.com" not in data["anonymized_text"]
        assert "John Doe" not in data["anonymized_text"]
        assert "555-123-4567" not in data["anonymized_text"]
        
        # Check statistics
        assert data["statistics"]["EMAIL_ADDRESS"] >= 1
        assert data["statistics"]["PERSON"] >= 1
        # Phone number detection might vary


@pytest.mark.asyncio
async def test_date_shifting():
    """Test that date shifting maintains temporal relationships"""
    async with httpx.AsyncClient() as client:
        request_data = {
            "markdown_text": "Meeting on January 15, 2024. Follow-up on January 22, 2024.",
            "config": {
                "entity_types": ["DATE_TIME"],
                "date_shift_days": 365,
                "score_threshold": 0.5
            }
        }
        
        response = await client.post(
            f"{BASE_URL}/anonymization/anonymize-markdown",
            json=request_data
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Extract dates from anonymized text
        import re
        date_pattern = r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}\b|\b\d{4}-\d{2}-\d{2}\b'
        dates = re.findall(date_pattern, data["anonymized_text"])
        
        if len(dates) >= 2:
            # Parse the dates
            from dateutil import parser as date_parser
            date1 = date_parser.parse(dates[0])
            date2 = date_parser.parse(dates[1])
            
            # Check that the 7-day gap is preserved
            gap = abs((date2 - date1).days)
            assert gap == 7, f"Expected 7-day gap, got {gap}"
        
        # Check statistics
        assert data["statistics"]["DATE_TIME"] >= 2


@pytest.mark.asyncio 
async def test_azure_di_anonymization():
    """Test Azure DI JSON anonymization"""
    async with httpx.AsyncClient() as client:
        # Sample Azure DI structure
        azure_di_json = {
            "content": "Patient John Smith, DOB: 1985-03-15, visited on January 10, 2024.",
            "paragraphs": [
                {
                    "content": "Contact email: john.smith@example.com",
                    "role": "paragraph"
                }
            ],
            "metadata": {
                "author": "Dr. Jane Doe"
            }
        }
        
        request_data = {
            "azure_di_json": azure_di_json,
            "config": {
                "anonymize_all_strings": True,
                "date_shift_days": 180,
                "score_threshold": 0.5
            }
        }
        
        response = await client.post(
            f"{BASE_URL}/anonymization/anonymize-azure-di",
            json=request_data
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check that PII was anonymized
        anon_json = data["anonymized_json"]
        assert "John Smith" not in json.dumps(anon_json)
        assert "john.smith@example.com" not in json.dumps(anon_json)
        assert "1985-03-15" not in json.dumps(anon_json)
        assert "Jane Doe" not in json.dumps(anon_json)
        
        # Check structure is preserved
        assert "content" in anon_json
        assert "paragraphs" in anon_json
        assert "metadata" in anon_json
        
        # Check statistics show detections
        stats = data["statistics"]
        assert stats.get("PERSON", 0) >= 2  # John Smith, Jane Doe
        assert stats.get("EMAIL_ADDRESS", 0) >= 1
        assert stats.get("DATE_TIME", 0) >= 2  # DOB and visit date


@pytest.mark.asyncio
async def test_ai4privacy_detection_types():
    """Test that AI4Privacy model detects many more entity types than basic Presidio"""
    async with httpx.AsyncClient() as client:
        # Text with various PII types that AI4Privacy should detect
        test_text = """
        Customer: Sarah Johnson (Age: 35)
        Account: 4532-1234-5678-9012
        IP Address: 192.168.1.100
        Bitcoin: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa
        Company: Acme Corporation
        Location: 123 Main St, San Francisco, CA 94105
        """
        
        request_data = {
            "markdown_text": test_text,
            "config": {
                "score_threshold": 0.3  # Lower threshold to catch more
            }
        }
        
        response = await client.post(
            f"{BASE_URL}/anonymization/anonymize-markdown", 
            json=request_data
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should detect various entity types
        stats = data["statistics"]
        total_detections = sum(stats.values())
        
        # AI4Privacy should detect many entities in this text
        assert total_detections >= 5, f"Expected at least 5 detections, got {total_detections}: {stats}"
        
        # Specific checks
        assert "Sarah Johnson" not in data["anonymized_text"]
        assert "192.168.1.100" not in data["anonymized_text"]


if __name__ == "__main__":
    # Run a simple test when executed directly
    import asyncio
    
    async def run_test():
        try:
            await test_health_endpoint()
            print("✓ Health check passed")
        except httpx.ConnectError:
            print("⚠️  Server not running. Start with: uv run run.py")
        except AssertionError as e:
            print(f"✗ Test failed: {e}")
            # Debug: print what we actually got
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{BASE_URL}/anonymization/health")
                print(f"Response: {response.json()}")
        
    asyncio.run(run_test())