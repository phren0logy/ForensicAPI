"""
Tests for the stitch_analysis_results function in routes/extraction.py

This module tests the critical stitching logic that combines Azure Document Intelligence
batch results into a single, cohesive analysis result. Tests are organized by complexity:

Phase 1: Small synthetic and real data subsets (CRITICAL)
Phase 2: Medium-scale real fixture testing (HIGH)  
Phase 3: Large-scale testing (FUTURE - documented as TODOs)

All tests directly call the stitch_analysis_results function with JSON dictionaries
to avoid Azure SDK mocking issues and TestClient serialization problems.
"""

import json
import os
import sys
from typing import Any, Dict

import pytest

# Add project root to path to import the function under test
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

from routes.extraction import (
    calculate_page_offset,
    stitch_analysis_results,
    validate_batch_sequence,
    validate_batch_structure,
)


def create_simple_batch(page_numbers: list, content: str) -> Dict[str, Any]:
    """Create a simple synthetic batch for testing."""
    return {
        "content": content,
        "pages": [{"pageNumber": num} for num in page_numbers]
    }


def create_batch_with_paragraph(page_numbers: list, content: str, paragraph_content: str) -> Dict[str, Any]:
    """Create a batch with a paragraph for testing."""
    return {
        "content": content,
        "pages": [{"pageNumber": num} for num in page_numbers],
        "paragraphs": [
            {
                "content": paragraph_content,
                "spans": [{"offset": 0, "length": len(paragraph_content)}]
            }
        ]
    }


def extract_page_subset(batch: Dict[str, Any], start_page: int, end_page: int) -> Dict[str, Any]:
    """Extract a subset of pages from a batch for testing."""
    subset = {
        "content": batch["content"],
        "pages": [p for p in batch["pages"] if start_page <= p["pageNumber"] <= end_page],
        "paragraphs": [
            p for p in batch.get("paragraphs", [])
            if any(start_page <= r["pageNumber"] <= end_page for r in p.get("boundingRegions", []))
        ]
    }
    return subset


class TestPhase1SmallScale:
    """Phase 1: Small-scale validation with synthetic and real data subsets."""
    
    def test_empty_first_batch(self):
        """Test stitching when first batch is empty."""
        batch = create_simple_batch([1], "Test content")
        
        result = stitch_analysis_results({}, batch)
        
        assert len(result["pages"]) == 1
        assert result["pages"][0]["pageNumber"] == 1
        assert result["content"] == "Test content"
    
    def test_two_page_synthetic_batches(self):
        """Test basic stitching with two simple synthetic batches."""
        batch1 = create_simple_batch([1], "First batch content. ")
        batch2 = create_simple_batch([2], "Second batch content.")
        
        # Test automatic offset calculation
        result = stitch_analysis_results(batch1, batch2)
        
        assert len(result["pages"]) == 2
        assert result["pages"][0]["pageNumber"] == 1
        assert result["pages"][1]["pageNumber"] == 2
        assert result["content"] == "First batch content. Second batch content."
    
    def test_span_offset_calculation(self):
        """Test that span offsets are correctly calculated."""
        batch1 = create_batch_with_paragraph([1], "First content. ", "First content. ")
        batch2 = create_batch_with_paragraph([2], "Second content.", "Second content.")
        
        # Calculate expected values BEFORE stitching (since stitching modifies inputs)
        batch1_content_len = len(batch1["content"])
        
        result = stitch_analysis_results(batch1, batch2)
        
        # Check that paragraph spans were updated correctly
        assert len(result["paragraphs"]) == 2
        assert result["paragraphs"][0]["spans"][0]["offset"] == 0
        assert result["paragraphs"][1]["spans"][0]["offset"] == batch1_content_len
    
    def test_multiple_element_types(self):
        """Test stitching with different element types."""
        batch1 = {
            "content": "Content 1. ",
            "pages": [{"pageNumber": 1}],
            "paragraphs": [{"spans": [{"offset": 0, "length": 10}], "boundingRegions": [{"pageNumber": 1}]}],
            "tables": [{"boundingRegions": [{"pageNumber": 1}]}]
        }
        batch2 = {
            "content": "Content 2.",
            "pages": [{"pageNumber": 2}],
            "paragraphs": [{"spans": [{"offset": 0, "length": 10}], "boundingRegions": [{"pageNumber": 2}]}],
            "tables": [{"boundingRegions": [{"pageNumber": 2}]}]
        }
        
        # Calculate expected values BEFORE stitching
        batch1_content_len = len(batch1["content"])
        
        result = stitch_analysis_results(batch1, batch2)
        
        assert len(result["pages"]) == 2
        assert len(result["paragraphs"]) == 2
        assert len(result["tables"]) == 2
        
        # Check span offset for second paragraph
        assert result["paragraphs"][1]["spans"][0]["offset"] == batch1_content_len
        
        # Check page numbers
        assert result["paragraphs"][0]["boundingRegions"][0]["pageNumber"] == 1
        assert result["paragraphs"][1]["boundingRegions"][0]["pageNumber"] == 2
        assert result["tables"][0]["boundingRegions"][0]["pageNumber"] == 1
        assert result["tables"][1]["boundingRegions"][0]["pageNumber"] == 2
    
    def test_element_preservation_single_element_type(self):
        """Test that all elements are preserved when first batch lacks certain types."""
        # First batch has no paragraphs
        batch1 = create_simple_batch([1], "First. ")
        
        # Second batch has paragraphs
        batch2 = create_batch_with_paragraph([2], "Second.", "Second.")
        
        result = stitch_analysis_results(batch1, batch2)
        
        assert len(result["pages"]) == 2
        assert len(result["paragraphs"]) == 1  # Only from batch2
        assert result["paragraphs"][0]["content"] == "Second."
        assert result["content"] == "First. Second."
    
    def test_real_data_subset_stitching(self, real_batch_1_50, real_batch_51_100):
        """Test stitching with real Azure DI data subsets."""
        # Get first 5 pages from each real batch for faster testing
        batch1_subset = extract_page_subset(real_batch_1_50, 1, 5)
        batch2_subset = extract_page_subset(real_batch_51_100, 51, 55)
        
        # Calculate expected values BEFORE stitching
        expected_pages = len(batch1_subset["pages"]) + len(batch2_subset["pages"])
        expected_paragraphs = len(batch1_subset["paragraphs"]) + len(batch2_subset["paragraphs"])
        batch1_content_len = len(batch1_subset["content"])
        total_expected_len = batch1_content_len + len(batch2_subset["content"])
        
        # Automatic offset calculation should handle the page numbering
        result = stitch_analysis_results(batch1_subset, batch2_subset)
        
        assert len(result["pages"]) == expected_pages
        assert len(result["paragraphs"]) == expected_paragraphs
        assert len(result["content"]) == total_expected_len
        
        # Verify page numbering remains correct
        page_numbers = [page["pageNumber"] for page in result["pages"]]
        assert page_numbers == list(range(1, expected_pages + 1))
    
    def test_edge_case_empty_content(self):
        """Test edge case with empty content in one batch."""
        batch1 = create_simple_batch([1], "")
        batch2 = create_simple_batch([2], "Only content")
        
        result = stitch_analysis_results(batch1, batch2)
        
        assert result["content"] == "Only content"
        assert len(result["pages"]) == 2
    
    def test_edge_case_no_paragraphs(self):
        """Test edge case when batches have no paragraphs."""
        batch1 = {"content": "Content 1. ", "pages": [{"pageNumber": 1}]}
        batch2 = {"content": "Content 2.", "pages": [{"pageNumber": 2}]}
        
        result = stitch_analysis_results(batch1, batch2)
        
        assert result["content"] == "Content 1. Content 2."
        assert len(result["pages"]) == 2
        assert result.get("paragraphs", []) == []
    
    def test_single_word_span_handling(self):
        """Test that individual word spans (using 'span' not 'spans') are handled correctly."""
        batch1 = {
            "content": "Word1 ",
            "pages": [{"pageNumber": 1}],
            "words": [{"span": {"offset": 0, "length": 5}, "content": "Word1"}]
        }
        batch2 = {
            "content": "Word2",
            "pages": [{"pageNumber": 2}],
            "words": [{"span": {"offset": 0, "length": 5}, "content": "Word2"}]
        }
        
        # Calculate expected offset
        batch1_content_len = len(batch1["content"])
        
        result = stitch_analysis_results(batch1, batch2)
        
        assert len(result["words"]) == 2
        assert result["words"][0]["span"]["offset"] == 0
        assert result["words"][1]["span"]["offset"] == batch1_content_len


class TestPhase1RealDataSubsets:
    """Phase 1: Real Data Subset Tests
    
    Test with small portions extracted from real Azure DI fixtures
    to verify the function works with actual response structures.
    """

    def test_with_real_fixture_structure(self):
        """Test stitching with simplified real-like Azure DI response structure"""
        # Create realistic batch 1 (pages 1-2)
        batch1 = {
            "content": "Page 1 text content.\n\nPage 2 text content.",
            "pages": [
                {"pageNumber": 1, "width": 8.5, "height": 11, "unit": "inch"},
                {"pageNumber": 2, "width": 8.5, "height": 11, "unit": "inch"}
            ],
            "paragraphs": [
                {
                    "spans": [{"offset": 0, "length": 19}],
                    "boundingRegions": [{"pageNumber": 1}],
                    "content": "Page 1 text content"
                },
                {
                    "spans": [{"offset": 22, "length": 19}],
                    "boundingRegions": [{"pageNumber": 2}],
                    "content": "Page 2 text content"
                }
            ],
            "tables": [
                {
                    "boundingRegions": [{"pageNumber": 2}],
                    "rowCount": 1,
                    "columnCount": 1
                }
            ]
        }
        
        # Create realistic batch 2 (pages 1-2, which will become 3-4)
        batch2 = {
            "content": "Page 3 text content.\n\nPage 4 text content.",
            "pages": [
                {"pageNumber": 1, "width": 8.5, "height": 11, "unit": "inch"},  # Will become page 3
                {"pageNumber": 2, "width": 8.5, "height": 11, "unit": "inch"}   # Will become page 4
            ],
            "paragraphs": [
                {
                    "spans": [{"offset": 0, "length": 19}],  # Will be adjusted
                    "boundingRegions": [{"pageNumber": 1}],   # Will become page 3
                    "content": "Page 3 text content"
                },
                {
                    "spans": [{"offset": 22, "length": 19}], # Will be adjusted
                    "boundingRegions": [{"pageNumber": 2}],   # Will become page 4
                    "content": "Page 4 text content"
                }
            ]
        }
        
        # Stitch the batches
        result = stitch_analysis_results(batch1, batch2, page_offset=2)
        
        # Verify structure preservation
        assert "content" in result
        assert "pages" in result
        assert "paragraphs" in result
        assert "tables" in result
        
        # Verify page count and numbers
        assert len(result["pages"]) == 4
        assert result["pages"][0]["pageNumber"] == 1
        assert result["pages"][1]["pageNumber"] == 2
        assert result["pages"][2]["pageNumber"] == 3
        assert result["pages"][3]["pageNumber"] == 4
        
        # Verify content concatenation
        expected_content = "Page 1 text content.\n\nPage 2 text content.Page 3 text content.\n\nPage 4 text content."
        assert result["content"] == expected_content
        
        # Verify span offset updates
        assert len(result["paragraphs"]) == 4
        batch1_content_len = len("Page 1 text content.\n\nPage 2 text content.")
        
        # First batch paragraphs should remain unchanged
        assert result["paragraphs"][0]["spans"][0]["offset"] == 0
        assert result["paragraphs"][1]["spans"][0]["offset"] == 22
        
        # Second batch paragraphs should have updated offsets
        assert result["paragraphs"][2]["spans"][0]["offset"] == batch1_content_len + 0
        assert result["paragraphs"][3]["spans"][0]["offset"] == batch1_content_len + 22
        
        # Verify page number updates in bounding regions
        assert result["paragraphs"][0]["boundingRegions"][0]["pageNumber"] == 1
        assert result["paragraphs"][1]["boundingRegions"][0]["pageNumber"] == 2
        assert result["paragraphs"][2]["boundingRegions"][0]["pageNumber"] == 3
        assert result["paragraphs"][3]["boundingRegions"][0]["pageNumber"] == 4

    def test_real_structure_with_mixed_elements(self):
        """Test with real structure including various element types"""
        batch1 = {
            "content": "First part content with words and lines.",
            "pages": [{"pageNumber": 1}],
            "words": [
                {
                    "content": "First",
                    "span": {"offset": 0, "length": 5},
                    "confidence": 0.995
                }
            ],
            "lines": [
                {
                    "content": "First part content",
                    "spans": [{"offset": 0, "length": 18}]
                }
            ],
            "paragraphs": [
                {
                    "content": "First paragraph",
                    "spans": [{"offset": 0, "length": 15}],
                    "boundingRegions": [{"pageNumber": 1}]
                }
            ]
        }
        
        batch2 = {
            "content": "Second part with more elements.",
            "pages": [{"pageNumber": 1}],  # Will become page 2
            "words": [
                {
                    "content": "Second",
                    "span": {"offset": 0, "length": 6},
                    "confidence": 0.994
                }
            ],
            "lines": [
                {
                    "content": "Second part with more",
                    "spans": [{"offset": 0, "length": 21}]
                }
            ],
            "paragraphs": [
                {
                    "content": "Second paragraph",
                    "spans": [{"offset": 0, "length": 16}],
                    "boundingRegions": [{"pageNumber": 1}]  # Will become page 2
                }
            ],
            "selectionMarks": [
                {
                    "state": "selected",
                    "pageNumber": 1  # Will become page 2
                }
            ]
        }
        
        result = stitch_analysis_results(batch1, batch2, page_offset=1)
        
        # Verify all element types are present and correctly merged
        assert len(result["pages"]) == 2
        assert len(result["words"]) == 2
        assert len(result["lines"]) == 2  
        assert len(result["paragraphs"]) == 2
        assert len(result["selectionMarks"]) == 1  # Only from batch2
        
        # Verify span updates in words
        first_content_len = len("First part content with words and lines.")
        assert result["words"][1]["span"]["offset"] == first_content_len + 0
        
        # Verify span updates in lines
        assert result["lines"][1]["spans"][0]["offset"] == first_content_len + 0
        
        # Verify page number updates in selection marks
        assert result["selectionMarks"][0]["pageNumber"] == 2


class TestPhase1EdgeCases:
    """Edge case testing for Phase 1"""
    
    def test_empty_content_handling(self):
        """Test handling of empty content strings"""
        batch1 = {
            "content": "",
            "pages": [{"pageNumber": 1}],
            "paragraphs": []
        }
        
        batch2 = {
            "content": "Some content",
            "pages": [{"pageNumber": 1}],
            "paragraphs": [
                {
                    "content": "Para 1",
                    "spans": [{"offset": 0, "length": 6}]
                }
            ]
        }
        
        result = stitch_analysis_results(batch1, batch2, page_offset=1)
        
        assert result["content"] == "Some content"
        assert result["paragraphs"][0]["spans"][0]["offset"] == 0  # No offset needed

    def test_zero_page_offset(self):
        """Test with zero page offset (should still work correctly)"""
        batch1 = {
            "content": "Content 1",
            "pages": [{"pageNumber": 1}]
        }
        
        batch2 = {
            "content": "Content 2", 
            "pages": [{"pageNumber": 1}]
        }
        
        result = stitch_analysis_results(batch1, batch2, page_offset=0)
        
        # Both pages should have the same page number (edge case but should not crash)
        assert result["pages"][0]["pageNumber"] == 1
        assert result["pages"][1]["pageNumber"] == 1


# TODO: Phase 3 - Large-Scale Testing (Future Implementation)
"""
Large-scale testing for production readiness with 12,000+ page documents:

- Full 353-page document validation against ground truth
- Performance benchmarking for memory usage and execution time  
- Stress testing with synthetic large datasets
- Memory efficiency optimization
- Execution time profiling for very large documents

These tests will be implemented when Phase 1 and Phase 2 are complete
and the application is ready for large-scale production deployment.
"""


class TestPhase2MediumScale:
    """Phase 2: Medium-scale validation using real fixture files."""
    
    def test_two_consecutive_batches_basic(self, real_batch_1_50, real_batch_51_100):
        """Test basic stitching of two consecutive 50-page batches with automatic offset calculation."""
        # Calculate expected values BEFORE stitching (since stitching modifies inputs)
        expected_pages = len(real_batch_1_50["pages"]) + len(real_batch_51_100["pages"])
        expected_paragraphs = len(real_batch_1_50["paragraphs"]) + len(real_batch_51_100["paragraphs"])
        batch1_content_len = len(real_batch_1_50["content"])
        total_expected_len = batch1_content_len + len(real_batch_51_100["content"])
        
        # Use automatic page offset calculation
        result = stitch_analysis_results(real_batch_1_50, real_batch_51_100)
        
        assert len(result["pages"]) == expected_pages
        assert len(result["paragraphs"]) == expected_paragraphs
        assert len(result["content"]) == total_expected_len
        
        # Verify page numbering is consecutive
        page_numbers = [page["pageNumber"] for page in result["pages"]]
        assert page_numbers == list(range(1, expected_pages + 1))
    
    def test_three_consecutive_batches(self, real_batch_1_50, real_batch_51_100, real_batch_101_150):
        """Test cumulative stitching of three consecutive batches with automatic calculation."""
        # Stitch first two batches with automatic offset
        intermediate_result = stitch_analysis_results(real_batch_1_50, real_batch_51_100)
        
        # Calculate expected values BEFORE final stitching
        expected_pages = len(intermediate_result["pages"]) + len(real_batch_101_150["pages"])
        expected_paragraphs = len(intermediate_result["paragraphs"]) + len(real_batch_101_150["paragraphs"])
        intermediate_content_len = len(intermediate_result["content"])
        total_expected_len = intermediate_content_len + len(real_batch_101_150["content"])
        
        # Stitch third batch with automatic offset
        final_result = stitch_analysis_results(intermediate_result, real_batch_101_150)
        
        assert len(final_result["pages"]) == expected_pages
        assert len(final_result["paragraphs"]) == expected_paragraphs
        assert len(final_result["content"]) == total_expected_len
        
        # Verify all page numbers are consecutive 1-150
        page_numbers = [page["pageNumber"] for page in final_result["pages"]]
        assert page_numbers == list(range(1, expected_pages + 1))
    
    def test_span_offset_accuracy_at_scale(self, real_batch_1_50, real_batch_51_100):
        """Test span offset calculations at medium scale with automatic offset."""
        # Calculate expected offset BEFORE stitching
        batch1_content_len = len(real_batch_1_50["content"])
        
        result = stitch_analysis_results(real_batch_1_50, real_batch_51_100)
        
        # Check that all second batch spans have been offset correctly
        for paragraph in result["paragraphs"]:
            if paragraph.get("boundingRegions") and paragraph["boundingRegions"][0]["pageNumber"] > 50:
                # This paragraph is from the second batch
                for span in paragraph.get("spans", []):
                    assert span["offset"] >= batch1_content_len, f"Span offset {span['offset']} should be >= {batch1_content_len}"
    
    def test_element_preservation_at_scale(self, real_batch_1_50, real_batch_51_100):
        """Test that all element types are preserved at medium scale."""
        # Count elements BEFORE stitching  
        batch1_paragraphs = len(real_batch_1_50["paragraphs"])
        batch2_paragraphs = len(real_batch_51_100["paragraphs"])
        batch1_pages = len(real_batch_1_50["pages"])
        batch2_pages = len(real_batch_51_100["pages"])
        
        result = stitch_analysis_results(real_batch_1_50, real_batch_51_100)
        
        # Verify all elements are preserved
        assert len(result["paragraphs"]) == batch1_paragraphs + batch2_paragraphs
        assert len(result["pages"]) == batch1_pages + batch2_pages
        
        # Check for other element types that might exist
        for element_type in ["tables", "words", "lines", "selectionMarks"]:
            if element_type in real_batch_1_50 or element_type in real_batch_51_100:
                batch1_count = len(real_batch_1_50.get(element_type, []))
                batch2_count = len(real_batch_51_100.get(element_type, []))
                result_count = len(result.get(element_type, []))
                assert result_count == batch1_count + batch2_count, f"{element_type} count mismatch"
    
    def test_ground_truth_content_sample_validation(self, real_batch_1_50, real_batch_51_100, ground_truth_result):
        """Test that stitched content matches ground truth for sample validation."""
        result = stitch_analysis_results(real_batch_1_50, real_batch_51_100)
        
        # Compare first 500 characters as a sample
        result_sample = result["content"][:500]
        ground_truth_sample = ground_truth_result["content"][:500]
        
        assert result_sample == ground_truth_sample, "Content sample should match ground truth"
        
        # Since we're only stitching first 100 pages, we can't compare the end with full ground truth
        # Instead, verify that our result length is reasonable for 100 pages
        # and that the content structure looks correct
        assert len(result["content"]) > 0, "Stitched content should not be empty"
        assert "CHAPTER" in result["content"], "Content should contain chapter markers"
        assert result["content"].startswith("# DRACULA"), "Content should start with title"
    
    def test_page_boundaries_across_batches(self, real_batch_1_50, real_batch_51_100):
        """Test that page boundaries are correctly maintained across batches."""
        result = stitch_analysis_results(real_batch_1_50, real_batch_51_100)
        
        # Check that page numbers are exactly 1-100 with no gaps
        page_numbers = sorted([page["pageNumber"] for page in result["pages"]])
        expected_pages = list(range(1, 101))  # Pages 1-100
        assert page_numbers == expected_pages, f"Page numbers should be 1-100, got {page_numbers[:10]}...{page_numbers[-10:]}"
        
        # Check that elements reference valid page numbers
        for paragraph in result["paragraphs"]:
            for region in paragraph.get("boundingRegions", []):
                page_num = region["pageNumber"]
                assert 1 <= page_num <= 100, f"Invalid page number {page_num} in paragraph"
    
    def test_data_structure_consistency(self, real_batch_1_50, real_batch_51_100):
        """Test that the stitched result maintains Azure DI data structure consistency."""
        result = stitch_analysis_results(real_batch_1_50, real_batch_51_100)
        
        # Check that required top-level fields exist
        assert "content" in result
        assert "pages" in result
        assert isinstance(result["content"], str)
        assert isinstance(result["pages"], list)
        
        # Check that all pages have required structure
        for page in result["pages"]:
            assert "pageNumber" in page
            assert isinstance(page["pageNumber"], int)
            assert page["pageNumber"] > 0
        
        # Check that all paragraphs have required structure
        for paragraph in result.get("paragraphs", []):
            assert "spans" in paragraph
            assert isinstance(paragraph["spans"], list)
            for span in paragraph["spans"]:
                assert "offset" in span
                assert "length" in span
                assert isinstance(span["offset"], int)
                assert isinstance(span["length"], int)
                assert span["offset"] >= 0


class TestValidationFunctions:
    """Test the new validation and utility functions added to the application logic."""
    
    def test_validate_batch_structure_valid(self):
        """Test that valid batch structure passes validation."""
        valid_batch = {
            "content": "Test content",
            "pages": [{"pageNumber": 1}, {"pageNumber": 2}]
        }
        
        # Should not raise any exception
        validate_batch_structure(valid_batch)
    
    def test_validate_batch_structure_missing_content(self):
        """Test validation fails when content field is missing."""
        invalid_batch = {
            "pages": [{"pageNumber": 1}]
        }
        
        with pytest.raises(ValueError, match="Missing required field: content"):
            validate_batch_structure(invalid_batch)
    
    def test_validate_batch_structure_missing_pages(self):
        """Test validation fails when pages field is missing."""
        invalid_batch = {
            "content": "Test content"
        }
        
        with pytest.raises(ValueError, match="Missing required field: pages"):
            validate_batch_structure(invalid_batch)
    
    def test_validate_batch_structure_invalid_content_type(self):
        """Test validation fails when content is not a string."""
        invalid_batch = {
            "content": 123,
            "pages": [{"pageNumber": 1}]
        }
        
        with pytest.raises(ValueError, match="Content field must be a string"):
            validate_batch_structure(invalid_batch)
    
    def test_validate_batch_structure_invalid_pages_type(self):
        """Test validation fails when pages is not a list."""
        invalid_batch = {
            "content": "Test content",
            "pages": "not a list"
        }
        
        with pytest.raises(ValueError, match="Pages field must be a list"):
            validate_batch_structure(invalid_batch)
    
    def test_validate_batch_structure_invalid_page_structure(self):
        """Test validation fails when page lacks pageNumber."""
        invalid_batch = {
            "content": "Test content",
            "pages": [{"notPageNumber": 1}]
        }
        
        with pytest.raises(ValueError, match="Page 0 missing pageNumber field"):
            validate_batch_structure(invalid_batch)
    
    def test_calculate_page_offset_empty_first_batch(self):
        """Test page offset calculation when first batch is empty."""
        empty_batch = {}
        new_batch = {"pages": [{"pageNumber": 1}, {"pageNumber": 2}]}
        
        offset = calculate_page_offset(empty_batch, new_batch)
        assert offset == 0
    
    def test_calculate_page_offset_consecutive_batches(self):
        """Test page offset calculation for consecutive batches."""
        first_batch = {"pages": [{"pageNumber": 1}, {"pageNumber": 2}]}
        second_batch = {"pages": [{"pageNumber": 3}, {"pageNumber": 4}]}
        
        offset = calculate_page_offset(first_batch, second_batch)
        assert offset == 0  # Already consecutive, no offset needed
    
    def test_calculate_page_offset_non_consecutive_batches(self):
        """Test page offset calculation for non-consecutive batches."""
        first_batch = {"pages": [{"pageNumber": 1}, {"pageNumber": 2}]}
        second_batch = {"pages": [{"pageNumber": 1}, {"pageNumber": 2}]}  # Needs offset
        
        offset = calculate_page_offset(first_batch, second_batch)
        assert offset == 2  # Should offset by 2 to make second batch pages 3,4
    
    def test_validate_batch_sequence_consecutive(self):
        """Test validation passes for consecutive batches."""
        batch1 = {"pages": [{"pageNumber": 1}, {"pageNumber": 2}]}
        batch2 = {"pages": [{"pageNumber": 3}, {"pageNumber": 4}]}
        batch3 = {"pages": [{"pageNumber": 5}, {"pageNumber": 6}]}
        
        # Should not raise any exception
        validate_batch_sequence([batch1, batch2, batch3])
    
    def test_validate_batch_sequence_single_batch(self):
        """Test validation with single batch (should pass)."""
        batch1 = {"pages": [{"pageNumber": 1}, {"pageNumber": 2}]}
        
        # Should not raise any exception
        validate_batch_sequence([batch1])
    
    def test_validate_batch_sequence_non_consecutive(self):
        """Test validation fails for non-consecutive batches."""
        batch1 = {"pages": [{"pageNumber": 1}, {"pageNumber": 2}]}
        batch2 = {"pages": [{"pageNumber": 4}, {"pageNumber": 5}]}  # Gap at page 3
        
        with pytest.raises(ValueError, match="Non-consecutive batches: gap between page 2 and 4"):
            validate_batch_sequence([batch1, batch2])
    
    def test_stitch_analysis_results_with_validation_enabled(self):
        """Test stitching with input validation enabled (default)."""
        batch1 = create_simple_batch([1], "First content. ")
        batch2 = create_simple_batch([2], "Second content.")
        
        # Should work with validation enabled (default)
        result = stitch_analysis_results(batch1, batch2, validate_inputs=True)
        assert len(result["pages"]) == 2
        assert result["content"] == "First content. Second content."
    
    def test_stitch_analysis_results_with_validation_disabled(self):
        """Test stitching with input validation disabled."""
        batch1 = create_simple_batch([1], "First content. ")
        batch2 = create_simple_batch([2], "Second content.")
        
        # Should work with validation disabled
        result = stitch_analysis_results(batch1, batch2, validate_inputs=False)
        assert len(result["pages"]) == 2
        assert result["content"] == "First content. Second content."
    
    def test_stitch_analysis_results_validation_catches_invalid_input(self):
        """Test that validation catches invalid input when enabled."""
        valid_batch = create_simple_batch([1], "Valid content. ")
        invalid_batch = {"invalid": "structure"}  # Missing required fields
        
        with pytest.raises(ValueError, match="Missing required field"):
            stitch_analysis_results(valid_batch, invalid_batch, validate_inputs=True)
    
    def test_automatic_page_offset_calculation(self):
        """Test that automatic page offset calculation works correctly."""
        batch1 = create_simple_batch([1, 2], "First batch. ")
        batch2 = create_simple_batch([1, 2], "Second batch.")  # Will be auto-adjusted
        
        # Don't specify page_offset - should be calculated automatically
        result = stitch_analysis_results(batch1, batch2)
        
        # Pages should be numbered 1, 2, 3, 4
        page_numbers = [page["pageNumber"] for page in result["pages"]]
        assert page_numbers == [1, 2, 3, 4]


# Fixtures for loading real data
@pytest.fixture
def real_batch_1_50():
    """Load the real batch_1-50.json fixture."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "dracula", "batch_1-50.json")
    with open(fixture_path, 'r') as f:
        return json.load(f)


@pytest.fixture
def real_batch_51_100():
    """Load the real batch_51-100.json fixture."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "dracula", "batch_51-100.json")
    with open(fixture_path, 'r') as f:
        return json.load(f)


@pytest.fixture
def real_batch_101_150():
    """Load the real batch_101-150.json fixture."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "dracula", "batch_101-150.json")
    with open(fixture_path, 'r') as f:
        return json.load(f)


@pytest.fixture
def ground_truth_result():
    """Load the ground truth result fixture."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "dracula", "ground_truth_result.json")
    with open(fixture_path, 'r') as f:
        return json.load(f)


# Phase 4 Fixtures - Full Document Testing
@pytest.fixture
def all_batch_fixtures():
    """Load all 8 batch files in the correct order for full document reconstruction."""
    fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures", "dracula")
    batch_files = [
        "batch_1-50.json",
        "batch_51-100.json", 
        "batch_101-150.json",
        "batch_151-200.json",
        "batch_201-250.json",
        "batch_251-300.json",
        "batch_301-350.json",
        "batch_351-353.json"
    ]
    
    batches = []
    for batch_file in batch_files:
        batch_path = os.path.join(fixtures_dir, batch_file)
        with open(batch_path, 'r') as f:
            batches.append(json.load(f))
    
    return batches


@pytest.fixture
def ground_truth_full():
    """Load the ground truth result fixture."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "dracula", "ground_truth_result.json")
    with open(fixture_path, 'r') as f:
        return json.load(f)


def create_stitched_full_document(all_batch_fixtures):
    """Create the full stitched document (helper function for individual tests)."""
    # Start with first batch
    result = all_batch_fixtures[0].copy()
    
    # Stitch all remaining batches sequentially
    for i, batch in enumerate(all_batch_fixtures[1:], 1):
        result = stitch_analysis_results(result, batch.copy())
    
    return result


class TestPhase4FullDocumentStitching:
    """Phase 4: Full document stitching tests with complete 353-page validation."""

    def test_full_document_sequential_stitching_basic(self, all_batch_fixtures):
        """Test basic sequential stitching of all 7 batches to reconstruct the full 353-page document."""
        # Track progress
        import time
        start_time = time.time()
        
        # Start with the first batch
        result = all_batch_fixtures[0].copy()
        initial_pages = len(result["pages"])
        initial_paragraphs = len(result["paragraphs"])
        
        # Stitch all remaining batches sequentially using automatic offset calculation
        for i, batch in enumerate(all_batch_fixtures[1:], 1):
            batch_copy = batch.copy()  # Don't modify original fixtures
            
            # Track batch info before stitching
            batch_pages = len(batch_copy["pages"])
            batch_paragraphs = len(batch_copy["paragraphs"])
            
            # Perform stitching with automatic offset calculation
            result = stitch_analysis_results(result, batch_copy)
            
            # Verify incremental progress
            expected_total_pages = initial_pages + sum(len(b["pages"]) for b in all_batch_fixtures[1:i+1])
            assert len(result["pages"]) == expected_total_pages, f"Page count mismatch after batch {i+1}"
            
            print(f"Batch {i+1} stitched: +{batch_pages} pages, +{batch_paragraphs} paragraphs")
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Verify final document structure
        assert len(result["pages"]) == 353, "Final document should have exactly 353 pages"
        assert result["pages"][0]["pageNumber"] == 1, "First page should be numbered 1"
        assert result["pages"][-1]["pageNumber"] == 353, "Last page should be numbered 353"
        
        # Verify page numbering is consecutive
        page_numbers = [page["pageNumber"] for page in result["pages"]]
        expected_pages = list(range(1, 354))  # 1 through 353
        assert page_numbers == expected_pages, "Page numbers should be consecutive from 1 to 353"
        
        # Verify content is substantial
        assert len(result["content"]) > 800000, "Full document content should be substantial (>800KB)"
        assert "DRACULA" in result["content"], "Content should contain the book title"
        
        # Performance validation
        assert execution_time < 60, f"Stitching should complete in under 60 seconds, took {execution_time:.2f}s"
        
        print(f"✅ Full document stitching successful: 353 pages in {execution_time:.2f} seconds")

    def test_full_document_structure_integrity(self, all_batch_fixtures, ground_truth_full):
        """Validate that the stitched result maintains all structural elements correctly."""
        result = create_stitched_full_document(all_batch_fixtures)
        ground_truth = ground_truth_full
        
        # Critical structural validation
        assert "content" in result, "Stitched result must have content field"
        assert "pages" in result, "Stitched result must have pages field"
        assert "paragraphs" in result, "Stitched result must have paragraphs field"
        
        # Page count validation
        assert len(result["pages"]) == len(ground_truth["pages"]), \
            f"Page count mismatch: {len(result['pages'])} vs {len(ground_truth['pages'])}"
        
        # Element count validation
        result_paragraphs = len(result["paragraphs"])
        gt_paragraphs = len(ground_truth["paragraphs"])
        assert result_paragraphs == gt_paragraphs, \
            f"Paragraph count mismatch: {result_paragraphs} vs {gt_paragraphs}"
        
        # Content length validation (should be very close)
        result_length = len(result["content"])
        gt_length = len(ground_truth["content"])
        length_diff = abs(result_length - gt_length)
        length_tolerance = max(100, gt_length * 0.001)  # 0.1% tolerance or 100 chars
        assert length_diff <= length_tolerance, \
            f"Content length differs by {length_diff} chars (>{length_tolerance} tolerance)"
        
        # Verify other element types if they exist
        for element_type in ["tables", "words", "lines", "selectionMarks"]:
            if element_type in ground_truth:
                assert element_type in result, f"Missing element type: {element_type}"
                result_count = len(result[element_type])
                gt_count = len(ground_truth[element_type])
                assert result_count == gt_count, \
                    f"{element_type} count mismatch: {result_count} vs {gt_count}"
        
        print(f"✅ Structure integrity validated: {len(result['pages'])} pages, {len(result['paragraphs'])} paragraphs")

    def test_full_document_content_samples(self, all_batch_fixtures, ground_truth_full):
        """Validate content accuracy using strategic sampling across the document."""
        result = create_stitched_full_document(all_batch_fixtures)
        ground_truth = ground_truth_full
        
        # Beginning content validation (first 500 characters)
        result_start = result["content"][:500]
        gt_start = ground_truth["content"][:500]
        assert result_start == gt_start, "First 500 characters should match exactly"
        
        # End content validation (last 500 characters)
        result_end = result["content"][-500:]
        gt_end = ground_truth["content"][-500:]
        assert result_end == gt_end, "Last 500 characters should match exactly"
        
        # Validate key content markers and structure
        chapter_count_result = result["content"].count("CHAPTER")
        chapter_count_gt = ground_truth["content"].count("CHAPTER")
        assert chapter_count_result == chapter_count_gt, \
            f"Chapter count mismatch: {chapter_count_result} vs {chapter_count_gt}"
        
        # Validate document starts correctly
        assert result["content"].startswith("# DRACULA"), "Document should start with DRACULA title"
        
        # Validate content length is very close (within 1% tolerance)
        result_length = len(result["content"])
        gt_length = len(ground_truth["content"])
        length_diff = abs(result_length - gt_length)
        tolerance = max(100, gt_length * 0.01)  # 1% or 100 chars minimum
        assert length_diff <= tolerance, \
            f"Content length differs by {length_diff} chars (tolerance: {tolerance})"
        
        # Validate key structural elements are present
        assert "Jonathan Harker" in result["content"], "Should contain character names"
        assert "Van Helsing" in result["content"], "Should contain character names"
        assert "Mina" in result["content"], "Should contain character names"
        assert "Castle Dracula" in result["content"] or "castle" in result["content"].lower(), "Should contain castle references"
        
        print(f"✅ Content samples validated: start/end exact match, {chapter_count_result} chapters, length within tolerance")

    def test_full_document_span_offset_precision(self, all_batch_fixtures):
        """Verify span offset calculations are accurate across all 353 pages."""
        result = create_stitched_full_document(all_batch_fixtures)
        
        # Collect all spans with their page numbers
        span_info = []
        for paragraph in result["paragraphs"]:
            for region in paragraph.get("boundingRegions", []):
                page_num = region["pageNumber"]
                for span in paragraph.get("spans", []):
                    span_info.append({
                        "page": page_num,
                        "offset": span["offset"],
                        "length": span["length"]
                    })
        
        # Verify spans are monotonically increasing
        prev_offset = -1
        for i, span in enumerate(span_info):
            assert span["offset"] >= prev_offset, \
                f"Span {i} has offset {span['offset']} < previous {prev_offset}"
            prev_offset = span["offset"]
        
        # Verify spans don't exceed content length
        content_length = len(result["content"])
        for span in span_info:
            span_end = span["offset"] + span["length"]
            assert span_end <= content_length, \
                f"Span extends beyond content: offset {span['offset']} + length {span['length']} > {content_length}"
        
        # Verify spans at critical page boundaries (pages 50, 100, 150, 200, 250, 300)
        boundary_pages = [50, 100, 150, 200, 250, 300]
        boundary_spans = {page: [] for page in boundary_pages}
        
        for span in span_info:
            if span["page"] in boundary_pages:
                boundary_spans[span["page"]].append(span)
        
        # Verify each boundary has spans and they're reasonable
        for page in boundary_pages:
            spans = boundary_spans[page]
            assert len(spans) > 0, f"Page {page} should have at least one span"
            
            # Verify spans for this page don't have negative offsets
            for span in spans:
                assert span["offset"] >= 0, f"Page {page} has negative span offset: {span['offset']}"
        
        # Cross-boundary validation - spans should increase across page boundaries
        for i in range(len(boundary_pages) - 1):
            current_page = boundary_pages[i]
            next_page = boundary_pages[i + 1]
            
            current_max_offset = max(s["offset"] for s in boundary_spans[current_page])
            next_min_offset = min(s["offset"] for s in boundary_spans[next_page])
            
            assert next_min_offset >= current_max_offset, \
                f"Span offsets don't increase across pages {current_page}->{next_page}: {current_max_offset} -> {next_min_offset}"
        
        print(f"✅ Span precision validated: {len(span_info)} spans across 353 pages, all monotonic")

    def test_full_document_performance_metrics(self, all_batch_fixtures):
        """Benchmark performance and memory usage for production readiness."""
        import os
        import time

        import psutil
        
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Track timing for each batch
        batch_times = []
        start_time = time.time()
        
        # Perform stitching with timing
        result = all_batch_fixtures[0].copy()
        
        for i, batch in enumerate(all_batch_fixtures[1:], 1):
            batch_start = time.time()
            batch_copy = batch.copy()
            result = stitch_analysis_results(result, batch_copy)
            batch_end = time.time()
            
            batch_time = batch_end - batch_start
            batch_times.append(batch_time)
            
            # Check memory usage
            current_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = current_memory - initial_memory
            
            print(f"Batch {i+1}: {batch_time:.2f}s, Memory: {current_memory:.1f}MB (+{memory_increase:.1f}MB)")
            
            # Memory shouldn't grow excessively (allow up to 500MB increase)
            assert memory_increase < 500, f"Memory usage grew too much: {memory_increase:.1f}MB"
        
        total_time = time.time() - start_time
        final_memory = process.memory_info().rss / 1024 / 1024
        total_memory_increase = final_memory - initial_memory
        
        # Performance assertions
        assert total_time < 30, f"Total stitching time {total_time:.2f}s exceeds 30s limit"
        assert max(batch_times) < 10, f"Longest batch took {max(batch_times):.2f}s, should be <10s"
        assert total_memory_increase < 1000, f"Total memory increase {total_memory_increase:.1f}MB too high"
        
        # Performance summary
        avg_batch_time = sum(batch_times) / len(batch_times)
        print(f"✅ Performance validated:")
        print(f"   Total time: {total_time:.2f}s")
        print(f"   Avg batch time: {avg_batch_time:.2f}s")
        print(f"   Memory increase: {total_memory_increase:.1f}MB")
        print(f"   Final document: {len(result['pages'])} pages, {len(result['content'])} chars")

    def test_full_document_with_validation_enabled(self, all_batch_fixtures):
        """Test full stitching with all validation features enabled."""
        # This test verifies that validation doesn't break the stitching process
        # and that all batches pass validation
        
        # Start with first batch
        result = all_batch_fixtures[0].copy()
        
        # Validate first batch structure
        validate_batch_structure(result)
        
        # Stitch remaining batches with validation enabled
        for i, batch in enumerate(all_batch_fixtures[1:], 1):
            batch_copy = batch.copy()
            
            # Validate batch structure before stitching
            validate_batch_structure(batch_copy)
            
            # Stitch with validation enabled (default)
            result = stitch_analysis_results(result, batch_copy, validate_inputs=True)
            
            # Verify result still has valid structure
            assert "content" in result
            assert "pages" in result
            assert len(result["pages"]) > 0
        
        # Final validation - verify batches are properly structured
        # Each individual batch should be valid (already tested above)
        # The sequence validation is implicit in the successful stitching
        
        # Verify final result
        assert len(result["pages"]) == 353
        page_numbers = [page["pageNumber"] for page in result["pages"]]
        assert page_numbers == list(range(1, 354))
        
        print(f"✅ Validation enabled test passed: all {len(all_batch_fixtures)} batches validated and stitched")
