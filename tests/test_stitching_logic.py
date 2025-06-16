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

from routes.extraction import stitch_analysis_results


class TestPhase1SmallCases:
    """Phase 1: Small Test Cases (Immediate Logic Validation)
    
    CRITICAL priority - must complete before proceeding to larger tests.
    These tests focus on catching fundamental logic errors immediately.
    """

    def test_content_concatenation_simple(self):
        """Test basic content concatenation with 2-page synthetic case"""
        # First batch: pages 1-2 with simple content
        batch1 = {
            "content": "Page 1 content.\nPage 2 content.",
            "pages": [
                {"pageNumber": 1},
                {"pageNumber": 2}
            ],
            "paragraphs": [
                {
                    "content": "Page 1 content.",
                    "spans": [{"offset": 0, "length": 15}],
                    "boundingRegions": [{"pageNumber": 1}]
                },
                {
                    "content": "Page 2 content.",
                    "spans": [{"offset": 16, "length": 15}],
                    "boundingRegions": [{"pageNumber": 2}]
                }
            ]
        }
        
        # Second batch: pages 1-2 (will become pages 3-4) with simple content
        batch2 = {
            "content": "Page 3 content.\nPage 4 content.",
            "pages": [
                {"pageNumber": 1},  # Will be corrected to 3
                {"pageNumber": 2}   # Will be corrected to 4
            ],
            "paragraphs": [
                {
                    "content": "Page 3 content.",
                    "spans": [{"offset": 0, "length": 15}],
                    "boundingRegions": [{"pageNumber": 1}]  # Will be corrected to 3
                },
                {
                    "content": "Page 4 content.",
                    "spans": [{"offset": 16, "length": 15}],
                    "boundingRegions": [{"pageNumber": 2}]  # Will be corrected to 4
                }
            ]
        }
        
        # Stitch the batches
        result = stitch_analysis_results(batch1, batch2, page_offset=2)
        
        # Verify content concatenation
        expected_content = "Page 1 content.\nPage 2 content.Page 3 content.\nPage 4 content."
        assert result["content"] == expected_content
        
        # Verify page numbers are correct
        assert len(result["pages"]) == 4
        assert result["pages"][0]["pageNumber"] == 1
        assert result["pages"][1]["pageNumber"] == 2
        assert result["pages"][2]["pageNumber"] == 3
        assert result["pages"][3]["pageNumber"] == 4
        
        # Verify paragraph spans are updated correctly
        assert len(result["paragraphs"]) == 4
        
        # First batch paragraphs should remain unchanged
        assert result["paragraphs"][0]["spans"][0]["offset"] == 0
        assert result["paragraphs"][1]["spans"][0]["offset"] == 16
        
        # Second batch paragraphs should have offset updated
        batch1_content_length = len("Page 1 content.\nPage 2 content.")
        assert result["paragraphs"][2]["spans"][0]["offset"] == batch1_content_length + 0
        assert result["paragraphs"][3]["spans"][0]["offset"] == batch1_content_length + 16

    def test_span_offset_updates(self):
        """Test that span offsets are correctly updated when stitching batches"""
        batch1 = {
            "content": "First batch content.",
            "paragraphs": [
                {
                    "content": "First paragraph",
                    "spans": [{"offset": 0, "length": 15}]
                }
            ],
            "pages": [{"pageNumber": 1}]
        }
        
        batch2 = {
            "content": "Second batch content.",
            "paragraphs": [
                {
                    "content": "Second paragraph", 
                    "spans": [{"offset": 0, "length": 16}]
                }
            ],
            "pages": [{"pageNumber": 1}]
        }
        
        result = stitch_analysis_results(batch1, batch2, page_offset=1)
        
        # First batch content length
        first_content_length = len("First batch content.")
        
        # Verify final content
        assert result["content"] == "First batch content.Second batch content."
        
        # Verify span offsets
        assert result["paragraphs"][0]["spans"][0]["offset"] == 0
        assert result["paragraphs"][1]["spans"][0]["offset"] == first_content_length

    def test_page_number_corrections(self):
        """Test that page numbers are correctly updated across all elements"""
        batch1 = {
            "content": "Content 1",
            "pages": [{"pageNumber": 1}],
            "paragraphs": [
                {
                    "content": "Para 1",
                    "spans": [{"offset": 0, "length": 6}],
                    "boundingRegions": [{"pageNumber": 1}]
                }
            ],
            "tables": [
                {
                    "boundingRegions": [{"pageNumber": 1}]
                }
            ]
        }
        
        batch2 = {
            "content": "Content 2",
            "pages": [{"pageNumber": 1}],  # Should become page 2
            "paragraphs": [
                {
                    "content": "Para 2",
                    "spans": [{"offset": 0, "length": 6}],
                    "boundingRegions": [{"pageNumber": 1}]  # Should become page 2
                }
            ],
            "tables": [
                {
                    "boundingRegions": [{"pageNumber": 1}]  # Should become page 2
                }
            ]
        }
        
        result = stitch_analysis_results(batch1, batch2, page_offset=1)
        
        # Check page numbers in pages array
        assert result["pages"][0]["pageNumber"] == 1
        assert result["pages"][1]["pageNumber"] == 2
        
        # Check page numbers in paragraph bounding regions
        assert result["paragraphs"][0]["boundingRegions"][0]["pageNumber"] == 1
        assert result["paragraphs"][1]["boundingRegions"][0]["pageNumber"] == 2
        
        # Check page numbers in table bounding regions
        assert result["tables"][0]["boundingRegions"][0]["pageNumber"] == 1
        assert result["tables"][1]["boundingRegions"][0]["pageNumber"] == 2

    def test_element_array_merging(self):
        """Test that all element arrays are properly merged"""
        batch1 = {
            "content": "Content 1",
            "pages": [{"pageNumber": 1}],
            "paragraphs": [{"content": "Para 1"}],
            "tables": [{"content": "Table 1"}],
            "words": [{"content": "Word 1"}],
            "lines": [{"content": "Line 1"}],
            "selectionMarks": [{"state": "selected"}]
        }
        
        batch2 = {
            "content": "Content 2", 
            "pages": [{"pageNumber": 1}],
            "paragraphs": [{"content": "Para 2"}],
            "tables": [{"content": "Table 2"}],
            "words": [{"content": "Word 2"}],
            "lines": [{"content": "Line 2"}],
            "selectionMarks": [{"state": "unselected"}]
        }
        
        result = stitch_analysis_results(batch1, batch2, page_offset=1)
        
        # Verify all arrays are properly merged
        assert len(result["pages"]) == 2
        assert len(result["paragraphs"]) == 2
        assert len(result["tables"]) == 2
        assert len(result["words"]) == 2
        assert len(result["lines"]) == 2
        assert len(result["selectionMarks"]) == 2
        
        # Verify content is from both batches
        assert result["paragraphs"][0]["content"] == "Para 1"
        assert result["paragraphs"][1]["content"] == "Para 2"

    def test_empty_first_batch(self):
        """Test handling when the first batch (stitched_result) is empty"""
        empty_batch = {}
        
        batch2 = {
            "content": "Second batch content",
            "pages": [{"pageNumber": 1}],
            "paragraphs": [
                {
                    "content": "Para 1",
                    "spans": [{"offset": 0, "length": 6}],
                    "boundingRegions": [{"pageNumber": 1}]
                }
            ]
        }
        
        result = stitch_analysis_results(empty_batch, batch2, page_offset=5)
        
        # When first batch is empty, function should handle page offset correctly
        assert result["pages"][0]["pageNumber"] == 6  # 1 + 5
        assert result["paragraphs"][0]["boundingRegions"][0]["pageNumber"] == 6

    def test_missing_optional_elements(self):
        """Test handling when batches are missing optional element arrays"""
        batch1 = {
            "content": "Content 1",
            "pages": [{"pageNumber": 1}],
            "paragraphs": [{"content": "Para 1"}]
            # Missing tables, words, lines, etc.
        }
        
        batch2 = {
            "content": "Content 2",
            "pages": [{"pageNumber": 1}],
            "paragraphs": [{"content": "Para 2"}],
            "tables": [{"content": "Table 1"}]  # Only batch2 has tables
        }
        
        result = stitch_analysis_results(batch1, batch2, page_offset=1)
        
        # Should handle missing elements gracefully
        assert len(result["paragraphs"]) == 2
        assert len(result["tables"]) == 1  # Only from batch2
        assert result["tables"][0]["content"] == "Table 1"


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
