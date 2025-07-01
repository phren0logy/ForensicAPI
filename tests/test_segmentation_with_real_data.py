"""
Test segmentation and filtering with real anonymized and synthetic data.

This module tests the /segment and /segment-filtered endpoints using
both synthetic test data (safe for repository) and anonymized real data
(gitignored) to validate:

1. Segmentation works correctly with complex multi-page documents
2. All filter presets produce expected token reductions
3. Element IDs are preserved for post-processing
4. Performance is acceptable for large documents
"""

import json
import os
import time
from pathlib import Path
from typing import Dict, List, Any
import pytest
from fastapi.testclient import TestClient

from main import app
from routes.filtering import FilterConfig
from routes.segmentation import (
    SegmentationInput,
    FilteredSegmentationInput,
)


class TestRealDataSegmentation:
    """Test segmentation with real document structures."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def test_data_dir(self):
        """Get test data directory paths."""
        # Test data is now in backend/tests/test-data
        current_dir = Path(__file__).parent
        return {
            "synthetic": current_dir / "test-data" / "synthetic",
            "anonymized": current_dir / "test-data" / "azure-di-json" / "anonymized"
        }
    
    @pytest.fixture
    def synthetic_files(self, test_data_dir):
        """Load all synthetic test files."""
        synthetic_dir = test_data_dir["synthetic"]
        if not synthetic_dir.exists():
            pytest.skip(f"Synthetic data directory not found: {synthetic_dir}")
        
        files = {}
        for json_file in synthetic_dir.glob("*.json"):
            with open(json_file, 'r') as f:
                files[json_file.stem] = json.load(f)
        
        if not files:
            pytest.skip("No synthetic test files found")
        
        return files
    
    @pytest.fixture
    def anonymized_files(self, test_data_dir):
        """Load anonymized test files (if available)."""
        anonymized_dir = test_data_dir["anonymized"]
        if not anonymized_dir.exists():
            return {}  # OK if not present - these are gitignored
        
        files = {}
        for json_file in anonymized_dir.glob("*.json"):
            with open(json_file, 'r') as f:
                files[json_file.stem] = json.load(f)
        
        return files
    
    def test_basic_segmentation_synthetic(self, client, synthetic_files):
        """Test basic segmentation with synthetic data."""
        results = {}
        
        for filename, azure_di_json in synthetic_files.items():
            print(f"\n📄 Testing segmentation for: {filename}")
            
            payload = {
                "source_file": f"{filename}.pdf",
                "analysis_result": azure_di_json,
                "min_segment_tokens": 2000,
                "max_segment_tokens": 6000
            }
            
            start_time = time.time()
            response = client.post("/segment", json=payload)
            elapsed = time.time() - start_time
            
            assert response.status_code == 200, f"Failed for {filename}: {response.text}"
            
            data = response.json()
            segments = data.get("segments", [])
            
            results[filename] = {
                "segment_count": len(segments),
                "total_tokens": sum(seg.get("token_count", 0) for seg in segments),
                "processing_time": elapsed,
                "has_context": all(seg.get("structural_context") for seg in segments)
            }
            
            print(f"  ✅ Segments: {len(segments)}")
            print(f"  📊 Total tokens: {results[filename]['total_tokens']}")
            print(f"  ⏱️  Time: {elapsed:.2f}s")
        
        # Verify all files were processed
        assert len(results) == len(synthetic_files)
        
        # Save results for inspection
        self._save_results(results, "synthetic/segmentation/basic_segmentation.json")
    
    def test_filtered_segmentation_all_presets(self, client, synthetic_files):
        """Test filtered segmentation with all presets."""
        presets = ["no_filter", "llm_ready", "forensic_extraction", "citation_optimized"]
        
        all_results = {}
        
        for filename, azure_di_json in synthetic_files.items():
            print(f"\n📄 Testing filtered segmentation for: {filename}")
            file_results = {}
            
            for preset in presets:
                print(f"  🔧 Testing preset: {preset}")
                
                payload = {
                    "source_file": f"{filename}.pdf",
                    "analysis_result": azure_di_json,
                    "filter_config": {
                        "filter_preset": preset,
                        "include_element_ids": True
                    },
                    "min_segment_tokens": 2000,
                    "max_segment_tokens": 6000
                }
                
                start_time = time.time()
                response = client.post("/segment-filtered", json=payload)
                elapsed = time.time() - start_time
                
                assert response.status_code == 200, f"Failed for {filename}/{preset}: {response.text}"
                
                data = response.json()
                segments = data.get("segments", [])
                metrics = data.get("metrics", {})
                mappings = data.get("element_mappings", [])
                
                # Calculate token statistics
                total_tokens = sum(
                    seg.get("token_count", 0) 
                    for seg in segments
                )
                
                file_results[preset] = {
                    "segment_count": len(segments),
                    "total_tokens": total_tokens,
                    "reduction_percentage": metrics.get("reduction_percentage", 0),
                    "filtered_elements": metrics.get("filtered_elements", 0),
                    "total_elements": metrics.get("total_elements", 0),
                    "processing_time": elapsed,
                    "has_mappings": len(mappings) > 0,
                    "all_elements_have_ids": self._verify_element_ids(segments)
                }
                
                print(f"    ✅ Reduction: {metrics.get('reduction_percentage', 0):.1f}%")
                print(f"    📊 Tokens: {total_tokens}")
                print(f"    🔗 Elements: {metrics.get('filtered_elements')}/{metrics.get('total_elements')}")
            
            all_results[filename] = file_results
        
        # Verify expected reduction patterns
        for filename, results in all_results.items():
            # no_filter should have least reduction (or negative due to overhead)
            # citation_optimized should have most reduction
            assert results["citation_optimized"]["reduction_percentage"] >= \
                   results["llm_ready"]["reduction_percentage"], \
                   f"Citation optimized should reduce more than llm_ready for {filename}"
        
        # Save detailed results
        self._save_results(all_results, "synthetic/filtering/all_presets_comparison.json")
    
    def test_anonymized_data_if_available(self, client, anonymized_files):
        """Test with anonymized real data if available."""
        if not anonymized_files:
            pytest.skip("No anonymized data available (this is normal)")
        
        print(f"\n🔒 Testing with {len(anonymized_files)} anonymized file(s)")
        
        results = {}
        
        for filename, azure_di_json in anonymized_files.items():
            print(f"\n📄 Testing anonymized: {filename}")
            
            # Test with llm_ready preset (default for production)
            payload = {
                "source_file": f"{filename}.pdf",
                "analysis_result": azure_di_json,
                "filter_config": {
                    "filter_preset": "llm_ready",
                    "include_element_ids": True
                },
                "min_segment_tokens": 3000,
                "max_segment_tokens": 8000
            }
            
            start_time = time.time()
            response = client.post("/segment-filtered", json=payload, timeout=30.0)
            elapsed = time.time() - start_time
            
            assert response.status_code == 200, f"Failed for {filename}: {response.text}"
            
            data = response.json()
            segments = data.get("segments", [])
            metrics = data.get("metrics", {})
            
            results[filename] = {
                "segment_count": len(segments),
                "total_tokens": sum(seg.get("token_count", 0) for seg in segments),
                "reduction_percentage": metrics.get("reduction_percentage", 0),
                "processing_time": elapsed,
                "page_count": self._count_unique_pages(segments)
            }
            
            print(f"  ✅ Segments: {len(segments)}")
            print(f"  📄 Pages: {results[filename]['page_count']}")
            print(f"  📊 Tokens: {results[filename]['total_tokens']}")
            print(f"  🔽 Reduction: {metrics.get('reduction_percentage', 0):.1f}%")
            print(f"  ⏱️  Time: {elapsed:.2f}s")
        
        # Save results to gitignored location
        self._save_results(results, "anonymized/segmentation_results.json", anonymized=True)
    
    def test_multi_document_handling(self, client, synthetic_files):
        """Test handling of multi-document PDFs."""
        # Look for files that might be multi-document
        multi_doc_candidates = [
            name for name in synthetic_files.keys()
            if "multi" in name or "case" in name
        ]
        
        if not multi_doc_candidates:
            pytest.skip("No multi-document test files found")
        
        for filename in multi_doc_candidates:
            azure_di_json = synthetic_files[filename]
            print(f"\n📚 Testing multi-document handling: {filename}")
            
            # Use forensic_extraction preset optimized for multi-doc
            payload = {
                "source_file": f"{filename}.pdf",
                "analysis_result": azure_di_json,
                "filter_config": {
                    "filter_preset": "forensic_extraction",
                    "include_element_ids": True
                },
                "min_segment_tokens": 2000,
                "max_segment_tokens": 6000
            }
            
            response = client.post("/segment-filtered", json=payload)
            assert response.status_code == 200
            
            data = response.json()
            segments = data.get("segments", [])
            
            # Check for document boundaries (usually indicated by h1 or page headers)
            doc_boundaries = 0
            for seg in segments:
                for elem in seg.get("elements", []):
                    if elem.get("role") in ["h1", "sectionHeading", "title"]:
                        doc_boundaries += 1
            
            print(f"  ✅ Found {doc_boundaries} potential document boundaries")
            print(f"  📄 Total segments: {len(segments)}")
    
    def test_performance_benchmarks(self, client, synthetic_files):
        """Test performance with different document sizes."""
        results = []
        
        for filename, azure_di_json in synthetic_files.items():
            # Estimate document size
            json_str = json.dumps(azure_di_json)
            size_kb = len(json_str) / 1024
            
            # Test both filtered and unfiltered
            for endpoint, use_filter in [("/segment", False), ("/segment-filtered", True)]:
                payload = {
                    "source_file": f"{filename}.pdf",
                    "analysis_result": azure_di_json,
                    "min_segment_tokens": 2000,
                    "max_segment_tokens": 6000
                }
                
                if use_filter:
                    payload["filter_config"] = {
                        "filter_preset": "llm_ready",
                        "include_element_ids": True
                    }
                
                start_time = time.time()
                response = client.post(endpoint, json=payload)
                elapsed = time.time() - start_time
                
                assert response.status_code == 200
                
                results.append({
                    "filename": filename,
                    "size_kb": size_kb,
                    "endpoint": endpoint,
                    "processing_time": elapsed,
                    "time_per_kb": elapsed / size_kb if size_kb > 0 else 0
                })
        
        # Verify performance is reasonable
        for result in results:
            # Should process at least 10 KB/second
            assert result["time_per_kb"] < 0.1, \
                f"Processing too slow for {result['filename']} on {result['endpoint']}"
        
        # Save benchmark results
        self._save_results(results, "synthetic/performance_benchmarks.json")
    
    def test_element_id_preservation(self, client, synthetic_files):
        """Verify element IDs are preserved through filtering."""
        # Pick one file for detailed testing
        test_file = list(synthetic_files.items())[0]
        filename, azure_di_json = test_file
        
        print(f"\n🔍 Testing element ID preservation with: {filename}")
        
        payload = {
            "source_file": f"{filename}.pdf",
            "analysis_result": azure_di_json,
            "filter_config": {
                "filter_preset": "llm_ready",
                "include_element_ids": True
            },
            "min_segment_tokens": 1000,
            "max_segment_tokens": 3000
        }
        
        response = client.post("/segment-filtered", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        segments = data.get("segments", [])
        mappings = data.get("element_mappings", [])
        
        # Collect all element IDs from segments
        segment_element_ids = set()
        for seg in segments:
            for elem in seg.get("elements", []):
                if "_id" in elem:
                    segment_element_ids.add(elem["_id"])
        
        # Collect all element IDs from mappings
        mapping_element_ids = set()
        for segment_mappings in mappings:
            for mapping in segment_mappings:
                mapping_element_ids.add(mapping["azure_element_id"])
        
        # Verify all mapped IDs exist in segments
        assert mapping_element_ids.issubset(segment_element_ids), \
            "Some mapped element IDs not found in segments"
        
        print(f"  ✅ All {len(mapping_element_ids)} mapped elements found in segments")
        print(f"  🔗 Total elements in segments: {len(segment_element_ids)}")
    
    def _verify_element_ids(self, segments: List[Dict]) -> bool:
        """Verify all elements have IDs."""
        for segment in segments:
            for element in segment.get("elements", []):
                if "_id" not in element:
                    return False
        return True
    
    def _count_unique_pages(self, segments: List[Dict]) -> int:
        """Count unique page numbers across all segments."""
        pages = set()
        for segment in segments:
            for element in segment.get("elements", []):
                if "pageNumber" in element:
                    pages.add(element["pageNumber"])
        return len(pages)
    
    def _save_results(self, results: Any, relative_path: str, anonymized: bool = False):
        """Save test results to file."""
        base_dir = Path(__file__).parent / "test_results"
        
        # For anonymized results, use different directory
        if anonymized:
            output_path = base_dir / "anonymized" / relative_path
        else:
            output_path = base_dir / relative_path
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n💾 Results saved to: {output_path}")


class TestSegmentationEdgeCases:
    """Test edge cases specific to real document structures."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    def test_very_long_segments(self, client):
        """Test handling of segments that exceed max tokens."""
        # Create a document with one extremely long paragraph
        long_content = "This is a test sentence. " * 2000  # ~8000 tokens
        
        azure_di_json = {
            "pages": [{
                "pageNumber": 1,
                "paragraphs": [{
                    "content": long_content,
                    "role": "paragraph"
                }]
            }]
        }
        
        payload = {
            "source_file": "long_segment.pdf",
            "analysis_result": azure_di_json,
            "min_segment_tokens": 1000,
            "max_segment_tokens": 3000  # Much smaller than content
        }
        
        response = client.post("/segment", json=payload)
        assert response.status_code == 200
        
        segments = response.json()
        # Should create single segment even if it exceeds max
        assert len(segments) == 1
        assert segments[0]["token_count"] > 3000
    
    def test_empty_document_pages(self, client):
        """Test documents with empty pages."""
        azure_di_json = {
            "pages": [
                {"pageNumber": 1, "paragraphs": []},  # Empty page
                {
                    "pageNumber": 2,
                    "paragraphs": [{"content": "Content on page 2", "role": "paragraph"}]
                },
                {"pageNumber": 3, "paragraphs": []},  # Another empty page
            ]
        }
        
        payload = {
            "source_file": "sparse_document.pdf",
            "analysis_result": azure_di_json,
            "filter_config": {"filter_preset": "llm_ready"}
        }
        
        response = client.post("/segment-filtered", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        # Should only have content from page 2
        assert data["metrics"]["filtered_elements"] == 1
    
    def test_complex_table_structures(self, client):
        """Test documents with complex tables."""
        azure_di_json = {
            "pages": [{
                "pageNumber": 1,
                "tables": [{
                    "content": "Table content",
                    "cells": [
                        {"content": "Header 1", "rowIndex": 0, "columnIndex": 0},
                        {"content": "Header 2", "rowIndex": 0, "columnIndex": 1},
                        {"content": "Data 1", "rowIndex": 1, "columnIndex": 0},
                        {"content": "Data 2", "rowIndex": 1, "columnIndex": 1},
                    ]
                }]
            }]
        }
        
        # Test with different presets to see table handling
        for preset in ["llm_ready", "forensic_extraction"]:
            payload = {
                "source_file": "table_document.pdf",
                "analysis_result": azure_di_json,
                "filter_config": {"filter_preset": preset}
            }
            
            response = client.post("/segment-filtered", json=payload)
            assert response.status_code == 200
            
            # Verify table structure is preserved
            segments = response.json()
            assert len(segments) > 0


def test_generate_summary_report():
    """Generate a summary report of all test results."""
    results_dir = Path(__file__).parent / "test_results"
    if not results_dir.exists():
        print("No test results found to summarize")
        return
    
    summary = {
        "test_run_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "synthetic_tests": {},
        "anonymized_tests": {},
        "performance_summary": {}
    }
    
    # Collect synthetic test results
    synthetic_dir = results_dir / "synthetic"
    if synthetic_dir.exists():
        for json_file in synthetic_dir.rglob("*.json"):
            with open(json_file, 'r') as f:
                data = json.load(f)
                summary["synthetic_tests"][json_file.stem] = data
    
    # Collect anonymized test results (if any)
    anon_dir = results_dir / "anonymized"
    if anon_dir.exists():
        file_count = len(list(anon_dir.rglob("*.json")))
        summary["anonymized_tests"]["file_count"] = file_count
        summary["anonymized_tests"]["note"] = "Detailed results not included in summary"
    
    # Save summary
    summary_path = results_dir / "test_summary.json"
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n📊 Test summary generated: {summary_path}")
    
    # Print key metrics
    print("\n🎯 Key Metrics:")
    if "all_presets_comparison" in summary["synthetic_tests"]:
        presets_data = summary["synthetic_tests"]["all_presets_comparison"]
        for filename, results in presets_data.items():
            print(f"\n  {filename}:")
            for preset, metrics in results.items():
                print(f"    {preset}: {metrics.get('reduction_percentage', 0):.1f}% reduction")


if __name__ == "__main__":
    # Run specific test if needed
    pytest.main([__file__, "-v", "-s"])