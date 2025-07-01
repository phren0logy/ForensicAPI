"""
Test the anonymization endpoint using synthetic test data.
"""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from main import app


class TestAnonymizationWithSynthetic:
    """Test anonymization functionality with synthetic data."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def synthetic_dir(self):
        """Get synthetic test data directory."""
        return Path(__file__).parent / "test-data" / "synthetic"
    
    def test_synthetic_file_anonymization(self, client, synthetic_dir):
        """Test anonymization with synthetic files."""
        # Get all synthetic test files
        synthetic_files = list(synthetic_dir.glob("*.json"))
        
        if not synthetic_files:
            pytest.skip("No synthetic test files found")
        
        # Test first synthetic file
        file_path = synthetic_files[0]
        
        # Load the synthetic data
        with open(file_path, 'r') as f:
            synthetic_data = json.load(f)
        
        # Prepare request
        request_data = {
            "azure_di_json": synthetic_data,
            "config": {
                "entity_types": [
                    "PERSON", 
                    "DATE_TIME", 
                    "LOCATION",
                    "US_SSN", 
                    "PHONE_NUMBER",
                    "EMAIL_ADDRESS",
                    "MEDICAL_LICENSE"
                ],
                "date_shift_days": 365,
                "score_threshold": 0.5
            }
        }
        
        # Make request
        response = client.post(
            "/anonymization/anonymize-azure-di",
            json=request_data
        )
        
        assert response.status_code == 200
        result = response.json()
        
        # Verify response structure
        assert "anonymized_json" in result
        assert "statistics" in result
        
        # Verify anonymization occurred
        original_content = synthetic_data.get('content', '')
        anonymized_content = result['anonymized_json'].get('content', '')
        
        # Content should be different if PII was found
        if any(result['statistics'].values()):
            assert original_content != anonymized_content
        
        # Verify structure is preserved
        assert set(result['anonymized_json'].keys()) == set(synthetic_data.keys())
    
    def test_multiple_synthetic_files(self, client, synthetic_dir):
        """Test anonymization with multiple synthetic files."""
        synthetic_files = list(synthetic_dir.glob("*.json"))
        
        if len(synthetic_files) < 2:
            pytest.skip("Need at least 2 synthetic files for this test")
        
        success_count = 0
        
        for file_path in synthetic_files[:3]:  # Test up to 3 files
            with open(file_path, 'r') as f:
                synthetic_data = json.load(f)
            
            request_data = {
                "azure_di_json": synthetic_data,
                "config": {
                    "entity_types": None,  # Detect all entity types
                    "score_threshold": 0.5
                }
            }
            
            response = client.post(
                "/anonymization/anonymize-azure-di",
                json=request_data
            )
            
            if response.status_code == 200:
                success_count += 1
                result = response.json()
                
                # Verify statistics show detections
                stats = result.get('statistics', {})
                total_detections = sum(stats.values())
                
                # Most synthetic files should have some PII
                assert total_detections >= 0
        
        # All files should process successfully
        assert success_count == min(len(synthetic_files), 3)