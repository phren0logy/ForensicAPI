"""
Test segmentation endpoints with synthetic test data.
"""

import json
from pathlib import Path
from typing import Dict, Any
import pytest
from fastapi.testclient import TestClient
from main import app


class TestSegmentationEndpoints:
    """Test segmentation functionality with various test files."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def test_data_dir(self):
        """Get test data directory."""
        return Path(__file__).parent / "test-data"
    
    def load_test_file(self, test_data_dir: Path, filename: str) -> Dict[str, Any]:
        """Load a test JSON file."""
        # Try synthetic first
        synthetic_path = test_data_dir / "synthetic" / filename
        if synthetic_path.exists():
            with open(synthetic_path, 'r') as f:
                return json.load(f)
        
        # Try anonymized
        anon_path = test_data_dir / "azure-di-json" / "anonymized" / filename  
        if anon_path.exists():
            with open(anon_path, 'r') as f:
                return json.load(f)
        
        pytest.skip(f"Test file not found: {filename}")
    
    def test_basic_segmentation(self, client, test_data_dir):
        """Test basic segmentation endpoint."""
        # Load a synthetic test file
        azure_di_json = self.load_test_file(test_data_dir, "medical_chart_multi_visit.json")
        
        # Prepare request
        payload = {
            "source_file": "medical_chart_multi_visit.pdf",
            "analysis_result": azure_di_json,
            "min_segment_tokens": 2000,
            "max_segment_tokens": 6000
        }
        
        # Send request
        response = client.post("/segment", json=payload)
        assert response.status_code == 200
        
        # Handle direct list response
        segments = response.json()
        assert isinstance(segments, list)
        assert len(segments) > 0
        
        # Verify segment structure
        first_seg = segments[0]
        assert "segment_id" in first_seg
        assert "token_count" in first_seg
        assert "elements" in first_seg
        assert "structural_context" in first_seg
        
        # Verify token counts
        total_tokens = sum(seg.get("token_count", 0) for seg in segments)
        assert total_tokens > 0
    
    def test_filtered_segmentation_presets(self, client, test_data_dir):
        """Test filtered segmentation with different presets."""
        # Load test file
        azure_di_json = self.load_test_file(test_data_dir, "legal_case_file.json")
        
        # Test each preset
        presets = ["no_filter", "llm_ready", "forensic_extraction", "citation_optimized"]
        results = {}
        
        for preset in presets:
            payload = {
                "source_file": "legal_case_file.pdf",
                "analysis_result": azure_di_json,
                "filter_config": {
                    "filter_preset": preset,
                    "include_element_ids": True
                },
                "min_segment_tokens": 2000,
                "max_segment_tokens": 6000
            }
            
            response = client.post("/segment-filtered", json=payload)
            assert response.status_code == 200
            
            data = response.json()
            assert "metrics" in data
            assert "segments" in data
            
            metrics = data.get("metrics", {})
            segments = data.get("segments", [])
            
            results[preset] = {
                "reduction": metrics.get("reduction_percentage", 0),
                "segments": len(segments)
            }
            
            # Verify reduction percentages make sense
            if preset == "citation_optimized":
                # Should have the highest reduction
                assert metrics.get("reduction_percentage", 0) > 50
            elif preset == "no_filter":
                # Should have minimal or no reduction
                assert metrics.get("reduction_percentage", 0) >= 0
        
        # Ensure all presets completed successfully
        assert len(results) == len(presets)
    
    def test_anonymized_data_if_available(self, client, test_data_dir):
        """Test with anonymized data if available."""
        # Check for anonymized files
        anon_dir = test_data_dir / "azure-di-json" / "anonymized"
        if not anon_dir.exists():
            pytest.skip("No anonymized data directory found")
        
        anon_files = list(anon_dir.glob("*.json"))
        if not anon_files:
            pytest.skip("No anonymized files found")
        
        # Test first anonymized file
        test_file = anon_files[0]
        
        with open(test_file, 'r') as f:
            azure_di_json = json.load(f)
        
        payload = {
            "source_file": test_file.name,
            "analysis_result": azure_di_json,
            "filter_config": {
                "filter_preset": "llm_ready",
                "include_element_ids": True
            },
            "min_segment_tokens": 3000,
            "max_segment_tokens": 8000
        }
        
        response = client.post("/segment-filtered", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        segments = data.get("segments", [])
        metrics = data.get("metrics", {})
        
        assert len(segments) > 0
        assert metrics.get("reduction_percentage", 0) >= 0
        
        # Count pages represented in segments
        pages = set()
        for seg in segments:
            for elem in seg.get("elements", []):
                if "pageNumber" in elem:
                    pages.add(elem["pageNumber"])
        
        assert len(pages) > 0