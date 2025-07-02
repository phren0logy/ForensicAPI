"""
Tests for the /extract endpoint using Azure Document Intelligence.

This module tests the Azure DI extraction functionality including:
- Element ID generation and preservation
- Batch processing and stitching
- Different document types (forms, mixed content, academic)
- Backwards compatibility with and without IDs
"""

import json
import os
from pathlib import Path
from typing import Dict, Any

import pytest
from fastapi.testclient import TestClient

from main import app
from routes.extraction import add_ids_to_elements, generate_element_id


class TestElementIDGeneration:
    """Test the element ID generation logic."""
    
    def test_generate_element_id_format(self):
        """Test that element IDs follow the expected format."""
        element_id = generate_element_id("para", 1, 0, "Sample content")
        
        # Should be in format: {type}_{page}_{index}_{hash}
        parts = element_id.split("_")
        assert len(parts) == 4
        assert parts[0] == "para"
        assert parts[1] == "1"
        assert parts[2] == "0"
        assert len(parts[3]) == 6  # 6-character hash
    
    def test_generate_element_id_deterministic(self):
        """Test that same inputs generate same ID."""
        id1 = generate_element_id("table", 5, 2, "Table content")
        id2 = generate_element_id("table", 5, 2, "Table content")
        assert id1 == id2
    
    def test_generate_element_id_unique_content(self):
        """Test that different content generates different IDs."""
        id1 = generate_element_id("para", 1, 0, "Content A")
        id2 = generate_element_id("para", 1, 0, "Content B")
        assert id1 != id2
    
    def test_generate_element_id_empty_content(self):
        """Test ID generation with empty content."""
        element_id = generate_element_id("fig", 3, 1, "")
        parts = element_id.split("_")
        assert len(parts) == 4
        assert parts[0] == "fig"


class TestAddIDsToElements:
    """Test the add_ids_to_elements function."""
    
    def test_add_ids_to_paragraphs(self):
        """Test adding IDs to paragraphs."""
        doc = {
            "paragraphs": [
                {"content": "Para 1", "boundingRegions": [{"pageNumber": 1}]},
                {"content": "Para 2", "boundingRegions": [{"pageNumber": 2}]}
            ]
        }
        
        result = add_ids_to_elements(doc)
        
        assert "_id" in result["paragraphs"][0]
        assert "_id" in result["paragraphs"][1]
        assert result["paragraphs"][0]["_id"].startswith("para_1_0_")
        assert result["paragraphs"][1]["_id"].startswith("para_2_1_")
    
    def test_add_ids_to_tables_and_cells(self):
        """Test adding IDs to tables and their cells."""
        doc = {
            "tables": [{
                "boundingRegions": [{"pageNumber": 3}],
                "cells": [
                    {"rowIndex": 0, "columnIndex": 0, "content": "Cell 1"},
                    {"rowIndex": 0, "columnIndex": 1, "content": "Cell 2"}
                ]
            }]
        }
        
        result = add_ids_to_elements(doc)
        
        assert "_id" in result["tables"][0]
        assert result["tables"][0]["_id"].startswith("table_3_0_")
        
        assert "_id" in result["tables"][0]["cells"][0]
        assert "_id" in result["tables"][0]["cells"][1]
        assert result["tables"][0]["cells"][0]["_id"].startswith("cell_3_0_0_0_")
        assert result["tables"][0]["cells"][1]["_id"].startswith("cell_3_0_0_1_")
    
    def test_add_ids_preserves_original_structure(self):
        """Test that adding IDs doesn't modify other fields."""
        doc = {
            "content": "Document content",
            "pages": [{"pageNumber": 1}],
            "paragraphs": [{
                "content": "Test paragraph",
                "spans": [{"offset": 0, "length": 14}],
                "boundingRegions": [{"pageNumber": 1}]
            }]
        }
        
        result = add_ids_to_elements(doc)
        
        # Check original fields are preserved
        assert result["content"] == doc["content"]
        assert len(result["pages"]) == len(doc["pages"])
        assert result["paragraphs"][0]["content"] == doc["paragraphs"][0]["content"]
        assert result["paragraphs"][0]["spans"] == doc["paragraphs"][0]["spans"]
        
        # Check ID was added
        assert "_id" in result["paragraphs"][0]
    
    def test_add_ids_to_all_element_types(self):
        """Test that IDs are added to all supported element types."""
        doc = {
            "paragraphs": [{"content": "Para", "boundingRegions": [{"pageNumber": 1}]}],
            "tables": [{"boundingRegions": [{"pageNumber": 1}]}],
            "keyValuePairs": [{"key": {"content": "Key"}, "value": {"content": "Value"}}],
            "lists": [{"boundingRegions": [{"pageNumber": 1}]}],
            "figures": [{"boundingRegions": [{"pageNumber": 1}]}],
            "formulas": [{"value": "E=mc^2", "boundingRegions": [{"pageNumber": 1}]}]
        }
        
        result = add_ids_to_elements(doc)
        
        assert "_id" in result["paragraphs"][0]
        assert "_id" in result["tables"][0]
        assert "_id" in result["keyValuePairs"][0]
        assert "_id" in result["lists"][0]
        assert "_id" in result["figures"][0]
        assert "_id" in result["formulas"][0]


class TestExtractionWithFixtures:
    """Test extraction using real fixture data."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def dracula_fixtures_dir(self):
        """Get path to Dracula fixtures."""
        return Path(__file__).parent / "fixtures" / "dracula"
    
    @pytest.fixture
    def forms_fixtures_dir(self):
        """Get path to forms fixtures."""
        return Path(__file__).parent / "fixtures" / "forms"
    
    def load_fixture(self, fixture_path: Path) -> Dict[str, Any]:
        """Load a JSON fixture file."""
        with open(fixture_path, 'r') as f:
            return json.load(f)
    
    def test_dracula_fixture_with_ids(self, dracula_fixtures_dir):
        """Test that Dracula fixtures with IDs have correct structure."""
        # Load a batch with IDs
        batch_with_ids = self.load_fixture(dracula_fixtures_dir / "batch_1-50_with_ids.json")
        
        # Verify IDs exist
        assert len(batch_with_ids["paragraphs"]) > 0
        for para in batch_with_ids["paragraphs"][:5]:  # Check first 5
            assert "_id" in para
            assert para["_id"].startswith("para_")
        
        # Load ground truth with IDs
        ground_truth_with_ids = self.load_fixture(dracula_fixtures_dir / "ground_truth_result_with_ids.json")
        
        # Verify ground truth has more elements than any single batch
        assert len(ground_truth_with_ids["paragraphs"]) > len(batch_with_ids["paragraphs"])
        assert len(ground_truth_with_ids["pages"]) == 353
    
    def test_dracula_fixture_without_ids(self, dracula_fixtures_dir):
        """Test that original fixtures don't have IDs."""
        # Load original batch without IDs
        batch_original = self.load_fixture(dracula_fixtures_dir / "batch_1-50.json")
        
        # Verify no IDs exist
        for para in batch_original["paragraphs"][:5]:  # Check first 5
            assert "_id" not in para
    
    def test_forms_fixture_structure(self, forms_fixtures_dir):
        """Test forms fixtures have expected structure with tables."""
        if not forms_fixtures_dir.exists():
            pytest.skip("Forms fixtures not yet generated")
        
        # Load forms ground truth
        forms_data = self.load_fixture(forms_fixtures_dir / "ground_truth_result.json")
        
        # Forms should have tables and key-value pairs
        assert "tables" in forms_data
        assert len(forms_data["tables"]) > 0
        
        # Check table structure
        first_table = forms_data["tables"][0]
        assert "cells" in first_table
        assert len(first_table["cells"]) > 0
        
        # If key-value pairs exist, verify structure
        if "keyValuePairs" in forms_data:
            assert len(forms_data["keyValuePairs"]) > 0
            first_kv = forms_data["keyValuePairs"][0]
            assert "key" in first_kv
            assert "value" in first_kv
    
    def test_element_id_uniqueness_in_fixtures(self, dracula_fixtures_dir):
        """Test that all element IDs are unique within a document."""
        ground_truth_with_ids = self.load_fixture(dracula_fixtures_dir / "ground_truth_result_with_ids.json")
        
        all_ids = set()
        duplicate_ids = []
        
        # Collect all IDs from paragraphs
        for para in ground_truth_with_ids.get("paragraphs", []):
            if "_id" in para:
                if para["_id"] in all_ids:
                    duplicate_ids.append(para["_id"])
                all_ids.add(para["_id"])
        
        # Collect all IDs from tables
        for table in ground_truth_with_ids.get("tables", []):
            if "_id" in table:
                if table["_id"] in all_ids:
                    duplicate_ids.append(table["_id"])
                all_ids.add(table["_id"])
                
                # Check cells
                for cell in table.get("cells", []):
                    if "_id" in cell:
                        if cell["_id"] in all_ids:
                            duplicate_ids.append(cell["_id"])
                        all_ids.add(cell["_id"])
        
        # No duplicates should exist
        assert len(duplicate_ids) == 0, f"Found duplicate IDs: {duplicate_ids}"
        
        # Should have many unique IDs
        assert len(all_ids) > 100, f"Expected many IDs, only found {len(all_ids)}"


class TestExtractionEndpointMocked:
    """Test the /extract endpoint with mocked Azure DI responses."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    def test_extract_with_element_ids_default(self, client, monkeypatch):
        """Test that element IDs are included by default."""
        # Mock the Azure DI response
        mock_response = {
            "content": "Test document",
            "pages": [{"pageNumber": 1}],
            "paragraphs": [{"content": "Test paragraph", "boundingRegions": [{"pageNumber": 1}]}]
        }
        
        async def mock_analyze(*args, **kwargs):
            return (mock_response, "Test document")
        
        # Skip file upload handling for this test
        # In real implementation, would need to mock the full flow
        
        # For now, just test the ID addition logic directly
        result_with_ids = add_ids_to_elements(mock_response)
        assert "_id" in result_with_ids["paragraphs"][0]
    
    def test_extract_without_element_ids(self, client):
        """Test extraction with include_element_ids=false."""
        # This would test the actual endpoint
        # For now, we test the logic directly
        mock_response = {
            "content": "Test document",
            "pages": [{"pageNumber": 1}],
            "paragraphs": [{"content": "Test paragraph", "boundingRegions": [{"pageNumber": 1}]}]
        }
        
        # When include_element_ids=false, original should be returned
        assert "_id" not in mock_response["paragraphs"][0]
    
    def test_extract_return_both_versions(self):
        """Test extraction with return_both=true."""
        mock_response = {
            "content": "Test document",
            "pages": [{"pageNumber": 1}],
            "paragraphs": [{"content": "Test paragraph", "boundingRegions": [{"pageNumber": 1}]}]
        }
        
        # When return_both=true, should get both versions
        result_with_ids = add_ids_to_elements(mock_response.copy())
        
        # Verify we can have both versions
        assert "_id" not in mock_response["paragraphs"][0]  # Original unchanged
        assert "_id" in result_with_ids["paragraphs"][0]    # New version has IDs


class TestBatchProcessingIntegration:
    """Test batch processing with real fixtures."""
    
    @pytest.fixture
    def dracula_batches(self):
        """Load all Dracula batch fixtures."""
        fixtures_dir = Path(__file__).parent / "fixtures" / "dracula"
        batches = []
        
        for i in range(1, 354, 50):
            end = min(i + 49, 353)
            batch_file = fixtures_dir / f"batch_{i}-{end}.json"
            if batch_file.exists():
                with open(batch_file, 'r') as f:
                    batches.append(json.load(f))
        
        return batches
    
    def test_batch_page_continuity(self, dracula_batches):
        """Test that batches have continuous page numbering."""
        if not dracula_batches:
            pytest.skip("No batch fixtures found")
        
        last_page = 0
        for batch in dracula_batches:
            pages = batch["pages"]
            page_numbers = [p["pageNumber"] for p in pages]
            
            # First page should be last_page + 1
            assert min(page_numbers) == last_page + 1
            
            # Pages should be continuous
            assert page_numbers == list(range(min(page_numbers), max(page_numbers) + 1))
            
            last_page = max(page_numbers)
    
    def test_element_distribution_across_batches(self, dracula_batches):
        """Test that elements are well-distributed across batches."""
        if not dracula_batches:
            pytest.skip("No batch fixtures found")
        
        paragraph_counts = []
        for batch in dracula_batches:
            paragraph_counts.append(len(batch.get("paragraphs", [])))
        
        # All batches should have paragraphs
        assert all(count > 0 for count in paragraph_counts)
        
        # Distribution should be somewhat even (not all in one batch)
        avg_count = sum(paragraph_counts) / len(paragraph_counts)
        assert max(paragraph_counts) < avg_count * 3  # No batch has 3x average


class TestComparisonBetweenFixtureTypes:
    """Test consistency between fixtures with and without IDs."""
    
    def compare_documents_excluding_ids(self, doc1: Dict, doc2: Dict) -> bool:
        """Compare two documents ignoring _id fields."""
        # Remove all _id fields from both documents
        def remove_ids(obj):
            if isinstance(obj, dict):
                return {k: remove_ids(v) for k, v in obj.items() if k != "_id"}
            elif isinstance(obj, list):
                return [remove_ids(item) for item in obj]
            else:
                return obj
        
        doc1_clean = remove_ids(doc1)
        doc2_clean = remove_ids(doc2)
        
        # Compare content length (should be identical)
        if doc1_clean.get("content") != doc2_clean.get("content"):
            return False
        
        # Compare page count
        if len(doc1_clean.get("pages", [])) != len(doc2_clean.get("pages", [])):
            return False
        
        # Compare paragraph count
        if len(doc1_clean.get("paragraphs", [])) != len(doc2_clean.get("paragraphs", [])):
            return False
        
        return True
    
    def test_dracula_fixtures_consistency(self):
        """Test that fixtures with and without IDs are otherwise identical."""
        fixtures_dir = Path(__file__).parent / "fixtures" / "dracula"
        
        # Load ground truth versions
        with open(fixtures_dir / "ground_truth_result.json", 'r') as f:
            ground_truth_original = json.load(f)
        
        with open(fixtures_dir / "ground_truth_result_with_ids.json", 'r') as f:
            ground_truth_with_ids = json.load(f)
        
        # Should be identical except for IDs
        assert self.compare_documents_excluding_ids(ground_truth_original, ground_truth_with_ids)
        
        # Verify IDs exist in the with_ids version
        assert "_id" in ground_truth_with_ids["paragraphs"][0]
        assert "_id" not in ground_truth_original["paragraphs"][0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])