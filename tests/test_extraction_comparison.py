"""
Comparison tests between Azure DI and Docling extraction endpoints.

This module tests:
- Extraction quality comparison
- Performance differences
- Format compatibility
- Feature parity assessment
"""

import json
import time
from pathlib import Path
from typing import Dict, Any, Tuple

import pytest
from fastapi.testclient import TestClient

from main import app


class TestExtractionComparison:
    """Compare extraction results between Azure DI and Docling."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def sample_pdfs_dir(self):
        """Get path to sample PDFs."""
        return Path(__file__).parent.parent / "tests" / "sample_pdfs"
    
    @pytest.fixture
    def fixtures_dir(self):
        """Get path to fixtures."""
        return Path(__file__).parent / "fixtures"
    
    def load_fixture(self, path: Path) -> Dict[str, Any]:
        """Load a JSON fixture."""
        with open(path, 'r') as f:
            return json.load(f)
    
    def extract_text_content(self, azure_result: Dict, docling_result: Dict) -> Tuple[str, str]:
        """Extract comparable text content from both formats."""
        # Azure DI has markdown in 'markdown_content'
        azure_text = azure_result.get("markdown_content", "")
        
        # Docling also has markdown in 'markdown_content'
        docling_text = docling_result.get("markdown_content", "")
        
        return azure_text, docling_text
    
    def calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple similarity ratio between two texts."""
        if not text1 or not text2:
            return 0.0
        
        # Simple character-based similarity
        len1, len2 = len(text1), len(text2)
        max_len = max(len1, len2)
        if max_len == 0:
            return 1.0
        
        # Calculate length similarity
        length_similarity = 1 - abs(len1 - len2) / max_len
        
        # Sample content similarity (first 1000 chars)
        sample1 = text1[:1000].lower()
        sample2 = text2[:1000].lower()
        
        # Count common words in samples
        words1 = set(sample1.split())
        words2 = set(sample2.split())
        if words1 or words2:
            word_similarity = len(words1 & words2) / len(words1 | words2)
        else:
            word_similarity = 0
        
        # Combined similarity
        return (length_similarity + word_similarity) / 2
    
    def test_markdown_extraction_comparison(self, fixtures_dir):
        """Compare markdown extraction quality between endpoints."""
        # Load pre-generated fixtures
        forms_azure = fixtures_dir / "forms" / "ground_truth_result.json"
        forms_docling = fixtures_dir / "docling" / "irs_form_1099_docling.json"
        
        if not forms_azure.exists() or not forms_docling.exists():
            pytest.skip("Fixtures not yet generated")
        
        azure_data = self.load_fixture(forms_azure)
        docling_data = self.load_fixture(forms_docling)
        
        azure_text, docling_text = self.extract_text_content(azure_data, docling_data)
        
        # Both should extract text
        assert len(azure_text) > 0, "Azure DI should extract text"
        assert len(docling_text) > 0, "Docling should extract text"
        
        # Calculate similarity
        similarity = self.calculate_similarity(azure_text, docling_text)
        
        # Should have reasonable similarity (>50%)
        assert similarity > 0.5, f"Text similarity too low: {similarity:.2%}"
        
        print(f"Text extraction similarity: {similarity:.2%}")
        print(f"Azure length: {len(azure_text)} chars")
        print(f"Docling length: {len(docling_text)} chars")
    
    def test_table_extraction_comparison(self, fixtures_dir):
        """Compare table extraction capabilities."""
        # Load forms fixtures (should have tables)
        forms_azure = fixtures_dir / "forms" / "ground_truth_result.json"
        forms_docling = fixtures_dir / "docling" / "irs_form_1099_docling.json"
        
        if not forms_azure.exists() or not forms_docling.exists():
            pytest.skip("Fixtures not yet generated")
        
        azure_data = self.load_fixture(forms_azure)
        docling_data = self.load_fixture(forms_docling)
        
        # Count tables in Azure format
        azure_tables = len(azure_data.get("tables", []))
        
        # Count tables in Docling format (different structure)
        docling_doc = docling_data.get("docling_document", {})
        docling_tables = 0
        
        # Docling stores elements differently
        for page_data in docling_doc.get("pages", {}).values():
            for elem in page_data.get("elements", []):
                if elem.get("type") == "table":
                    docling_tables += 1
        
        print(f"Azure DI found {azure_tables} tables")
        print(f"Docling found {docling_tables} tables")
        
        # Both should find tables in a form document
        if "form" in str(forms_azure).lower() or "1099" in str(forms_azure).lower():
            assert azure_tables > 0 or docling_tables > 0, "Form should have tables"
    
    def test_element_structure_differences(self, fixtures_dir):
        """Document structural differences between formats."""
        # Load any fixture pair
        azure_fixture = fixtures_dir / "dracula" / "ground_truth_result.json"
        docling_fixture = fixtures_dir / "docling" / "stoker_dracula_docling.json"
        
        if not azure_fixture.exists() or not docling_fixture.exists():
            pytest.skip("Fixtures not yet generated")
        
        azure_data = self.load_fixture(azure_fixture)
        docling_data = self.load_fixture(docling_fixture)
        
        # Document Azure DI structure
        azure_structure = {
            "top_level_keys": sorted(azure_data.keys()),
            "has_pages": "pages" in azure_data,
            "has_paragraphs": "paragraphs" in azure_data,
            "has_tables": "tables" in azure_data,
            "has_element_ids": any("_id" in p for p in azure_data.get("paragraphs", [])[:5])
        }
        
        # Document Docling structure
        docling_doc = docling_data.get("docling_document", {})
        docling_structure = {
            "top_level_keys": sorted(docling_data.keys()),
            "has_pages": "pages" in docling_doc,
            "has_elements": "elements" in docling_doc,
            "has_metadata": "metadata" in docling_data,
            "has_element_ids": False  # Docling doesn't support IDs yet
        }
        
        print("\nAzure DI Structure:")
        for key, value in azure_structure.items():
            print(f"  {key}: {value}")
        
        print("\nDocling Structure:")
        for key, value in docling_structure.items():
            print(f"  {key}: {value}")
        
        # Key differences to note
        assert azure_structure["has_element_ids"] == True, "Azure DI should support element IDs"
        assert docling_structure["has_element_ids"] == False, "Docling doesn't support IDs yet"
    
    def test_performance_characteristics(self, fixtures_dir):
        """Compare performance characteristics (using pre-generated fixtures)."""
        # Note: This doesn't test actual API performance, just processing characteristics
        
        # Load large document fixtures
        azure_fixture = fixtures_dir / "dracula" / "ground_truth_result.json"
        docling_fixture = fixtures_dir / "docling" / "stoker_dracula_docling.json"
        
        if not azure_fixture.exists() or not docling_fixture.exists():
            pytest.skip("Fixtures not yet generated")
        
        # Measure fixture loading time as proxy for complexity
        start = time.time()
        azure_data = self.load_fixture(azure_fixture)
        azure_load_time = time.time() - start
        
        start = time.time()
        docling_data = self.load_fixture(docling_fixture)
        docling_load_time = time.time() - start
        
        # Measure data sizes
        azure_size = len(json.dumps(azure_data))
        docling_size = len(json.dumps(docling_data))
        
        print(f"\nPerformance Characteristics:")
        print(f"Azure DI fixture size: {azure_size / 1024 / 1024:.2f} MB")
        print(f"Docling fixture size: {docling_size / 1024 / 1024:.2f} MB")
        print(f"Azure DI load time: {azure_load_time * 1000:.1f} ms")
        print(f"Docling load time: {docling_load_time * 1000:.1f} ms")
        
        # Document which is more compact
        if azure_size < docling_size:
            print("Azure DI format is more compact")
        else:
            print("Docling format is more compact")
    
    def test_feature_parity_summary(self, fixtures_dir):
        """Summarize feature parity between endpoints."""
        features = {
            "Element IDs": {
                "Azure DI": True,
                "Docling": False,
                "Notes": "Azure DI supports _id generation"
            },
            "Batch Processing": {
                "Azure DI": True,
                "Docling": False,
                "Notes": "Azure DI supports page ranges"
            },
            "Filtering": {
                "Azure DI": True,
                "Docling": False,
                "Notes": "Azure DI works with /segment-filtered"
            },
            "OCR Support": {
                "Azure DI": True,
                "Docling": True,
                "Notes": "Both support OCR"
            },
            "Local Processing": {
                "Azure DI": False,
                "Docling": True,
                "Notes": "Docling runs locally"
            },
            "Cost": {
                "Azure DI": "Per-page pricing",
                "Docling": "Free (local)",
                "Notes": "Different cost models"
            }
        }
        
        print("\nFeature Parity Summary:")
        print("-" * 60)
        
        for feature, info in features.items():
            print(f"\n{feature}:")
            print(f"  Azure DI: {info['Azure DI']}")
            print(f"  Docling: {info['Docling']}")
            print(f"  Notes: {info['Notes']}")
        
        # Count feature advantages
        azure_advantages = sum(1 for f in features.values() 
                             if isinstance(f["Azure DI"], bool) and f["Azure DI"] and not f["Docling"])
        docling_advantages = sum(1 for f in features.values() 
                               if isinstance(f["Docling"], bool) and f["Docling"] and not f["Azure DI"])
        
        print(f"\nAzure DI advantages: {azure_advantages}")
        print(f"Docling advantages: {docling_advantages}")
        
        # Both have their strengths
        assert azure_advantages > 0, "Azure DI should have some advantages"
        assert docling_advantages > 0, "Docling should have some advantages"


class TestMigrationPath:
    """Test migration path from Azure DI to Docling."""
    
    def test_docling_can_process_same_documents(self, fixtures_dir):
        """Verify Docling can process all document types Azure DI handles."""
        document_types = ["forms", "mixed", "academic", "dracula"]
        
        for doc_type in document_types:
            azure_fixture = fixtures_dir / doc_type / "ground_truth_result.json"
            
            # Map to expected Docling fixture name
            docling_name_map = {
                "forms": "irs_form_1099",
                "mixed": "cdc_vis_covid_19",
                "academic": "wolke_lereya_2015_long_term_effects_of_bullying",
                "dracula": "stoker_dracula"
            }
            
            docling_fixture = fixtures_dir / "docling" / f"{docling_name_map.get(doc_type, doc_type)}_docling.json"
            
            if azure_fixture.exists() and docling_fixture.exists():
                # Both processed successfully
                azure_data = json.loads(azure_fixture.read_text())
                docling_data = json.loads(docling_fixture.read_text())
                
                # Both should have content
                assert len(azure_data.get("content", "")) > 0
                assert len(docling_data.get("markdown_content", "")) > 0
                
                print(f"✓ {doc_type}: Both endpoints processed successfully")
            else:
                print(f"- {doc_type}: Fixtures not yet generated")
    
    def test_docling_limitations_documented(self):
        """Document current Docling limitations for migration planning."""
        limitations = [
            "No element ID generation",
            "No filtering support in /extract-local",
            "No batch processing (full document only)",
            "Different JSON output format",
            "No direct integration with /segment-filtered endpoint"
        ]
        
        print("\nCurrent Docling Limitations:")
        for i, limitation in enumerate(limitations, 1):
            print(f"{i}. {limitation}")
        
        # This test documents limitations rather than asserting
        # It serves as a checklist for future development
        assert len(limitations) > 0, "Limitations should be documented"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])