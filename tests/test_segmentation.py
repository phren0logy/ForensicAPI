import json
import os
from typing import Any, Dict, List

import pytest

from routes.segmentation import (
    RichSegment,
    SegmentationInput,
    StructuralContext,
    create_rich_segments,
    get_heading_level,
    update_context,
)


class TestHeadingLevelDetection:
    """Unit tests for heading level detection with Azure DI role patterns."""
    
    def test_direct_heading_patterns(self):
        """Test direct h1-h6 patterns."""
        assert get_heading_level("h1") == 1
        assert get_heading_level("h2") == 2
        assert get_heading_level("h3") == 3
        assert get_heading_level("h4") == 4
        assert get_heading_level("h5") == 5
        assert get_heading_level("h6") == 6
        
    def test_case_insensitive_patterns(self):
        """Test case insensitive handling."""
        assert get_heading_level("H1") == 1
        assert get_heading_level("H2") == 2
        assert get_heading_level("SECTIONHEADING") == 2
        assert get_heading_level("Title") == 1
        
    def test_azure_di_specific_patterns(self):
        """Test Azure DI specific role patterns."""
        assert get_heading_level("sectionHeading") == 2
        assert get_heading_level("title") == 1
        assert get_heading_level("pageHeader") == 1
        assert get_heading_level("subtitle") == 2
        
    def test_non_heading_patterns(self):
        """Test patterns that should not be detected as headings."""
        assert get_heading_level("paragraph") is None
        assert get_heading_level("") is None
        assert get_heading_level(None) is None
        assert get_heading_level("h7") is None  # Invalid level
        assert get_heading_level("h0") is None  # Invalid level
        assert get_heading_level("heading") is None  # Not a direct pattern
        

class TestContextUpdates:
    """Unit tests for structural context updates."""
    
    def test_basic_context_update(self):
        """Test basic heading context updates."""
        context = StructuralContext()
        
        # Add H1
        context = update_context(context, "h1", "Chapter 1")
        assert context.h1 == "Chapter 1"
        assert context.h2 is None
        
        # Add H2
        context = update_context(context, "h2", "Section A")
        assert context.h1 == "Chapter 1"
        assert context.h2 == "Section A"
        assert context.h3 is None
        
    def test_context_hierarchy_reset(self):
        """Test that lower levels are reset when higher level is updated."""
        context = StructuralContext()
        
        # Build up hierarchy
        context = update_context(context, "h1", "Chapter 1")
        context = update_context(context, "h2", "Section A")
        context = update_context(context, "h3", "Subsection 1")
        
        # Update H2 should reset H3+
        context = update_context(context, "h2", "Section B")
        assert context.h1 == "Chapter 1"
        assert context.h2 == "Section B"
        assert context.h3 is None
        assert context.h4 is None
        
    def test_non_heading_no_update(self):
        """Test that non-headings don't update context."""
        context = StructuralContext(h1="Chapter 1")
        original_context = context.model_copy()
        
        context = update_context(context, "paragraph", "Some content")
        assert context == original_context


class TestTokenCounting:
    """Unit tests for token counting accuracy."""
    
    def test_empty_content(self):
        """Test token counting for empty content."""
        import tiktoken
        encoding = tiktoken.get_encoding("cl100k_base")
        
        assert len(encoding.encode("")) == 0
        assert len(encoding.encode("   ")) == 1  # Whitespace has tokens
        
    def test_known_content_tokens(self):
        """Test token counting for known content."""
        import tiktoken
        encoding = tiktoken.get_encoding("cl100k_base")
        
        # Simple test cases
        assert len(encoding.encode("hello")) > 0
        assert len(encoding.encode("hello world")) >= len(encoding.encode("hello"))


class TestElementProcessing:
    """Unit tests for element type processing and ordering."""
    
    def test_supported_element_types(self):
        """Test that all supported element types are processed."""
        analysis_result = {
            "paragraphs": [{"content": "Para 1", "spans": [{"offset": 10}], "role": "paragraph"}],
            "tables": [{"content": "Table 1", "spans": [{"offset": 5}], "role": "table"}],
            "figures": [{"content": "Figure 1", "spans": [{"offset": 15}], "role": "figure"}],
            "formulas": [{"content": "E=mc²", "spans": [{"offset": 20}], "role": "formula"}],
            "keyValuePairs": [{"content": "Key: Value", "spans": [{"offset": 0}], "role": "keyValuePair"}]
        }
        
        segments = create_rich_segments(analysis_result, "test.pdf", min_segment_tokens=1, max_segment_tokens=100)
        
        # Should have elements from all types
        all_elements = []
        for segment in segments:
            all_elements.extend(segment.elements)
            
        assert len(all_elements) == 5
        
        # Should be ordered by offset
        offsets = [elem["spans"][0]["offset"] for elem in all_elements]
        assert offsets == sorted(offsets)
        
    def test_missing_element_types(self):
        """Test handling when some element types are missing."""
        analysis_result = {
            "paragraphs": [{"content": "Para 1", "spans": [{"offset": 0}], "role": "paragraph"}]
            # Missing tables, figures, etc.
        }
        
        segments = create_rich_segments(analysis_result, "test.pdf", min_segment_tokens=1, max_segment_tokens=100)
        assert len(segments) == 1
        assert len(segments[0].elements) == 1


class TestConfigurableThresholds:
    """Unit tests for configurable token thresholds."""
    
    def test_custom_thresholds(self):
        """Test segmentation with custom thresholds."""
        # Create content that will exceed small thresholds
        long_content = "This is a very long paragraph. " * 50  # ~1500 tokens approx
        
        analysis_result = {
            "paragraphs": [
                {"content": long_content, "spans": [{"offset": 0}], "role": "paragraph"},
                {"content": long_content, "spans": [{"offset": 1000}], "role": "paragraph"},
            ]
        }
        
        # Test with small thresholds - should create multiple segments
        segments_small = create_rich_segments(
            analysis_result, "test.pdf", 
            min_segment_tokens=100, max_segment_tokens=200
        )
        
        # Test with large thresholds - should create fewer segments
        segments_large = create_rich_segments(
            analysis_result, "test.pdf", 
            min_segment_tokens=1000, max_segment_tokens=5000
        )
        
        # Small thresholds should create more segments
        assert len(segments_small) >= len(segments_large)
        
    def test_threshold_validation_logic(self):
        """Test the logical boundary detection with thresholds."""
        analysis_result = {
            "paragraphs": [
                {"content": "Short", "spans": [{"offset": 0}], "role": "paragraph"},
                {"content": "Chapter 1", "spans": [{"offset": 10}], "role": "h1"},
                {"content": "Short", "spans": [{"offset": 20}], "role": "paragraph"},
            ]
        }
        
        segments = create_rich_segments(
            analysis_result, "test.pdf", 
            min_segment_tokens=1, max_segment_tokens=100
        )
        
        # Should break at H1 heading even if under max threshold
        assert len(segments) >= 2


class TestRealDataIntegration:
    """Integration tests using real Azure DI data."""
    
    @pytest.fixture
    def small_real_data(self):
        """Load small real data fixture for testing."""
        fixture_path = os.path.join(os.path.dirname(__file__), "fixtures_small", "real_extract_5_pages.json")
        if os.path.exists(fixture_path):
            with open(fixture_path, 'r') as f:
                return json.load(f)
        return None
        
    def test_real_data_segmentation(self, small_real_data):
        """Test segmentation with real Azure DI data."""
        if small_real_data is None:
            pytest.skip("Real data fixture not available")
            
        segments = create_rich_segments(
            small_real_data, "real_document.pdf",
            min_segment_tokens=500, max_segment_tokens=2000
        )
        
        # Basic validation
        assert len(segments) > 0
        
        for segment in segments:
            assert segment.source_file == "real_document.pdf"
            assert segment.segment_id > 0
            assert segment.token_count > 0
            assert len(segment.elements) > 0
            assert isinstance(segment.structural_context, StructuralContext)


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""
    
    def test_empty_document(self):
        """Test handling of empty documents."""
        analysis_result = {}
        segments = create_rich_segments(analysis_result, "empty.pdf")
        assert segments == []
        
        analysis_result = {"paragraphs": []}
        segments = create_rich_segments(analysis_result, "empty.pdf")
        assert segments == []
        
    def test_single_large_element(self):
        """Test handling of single element that exceeds max threshold."""
        huge_content = "Very long content. " * 1000  # Very large content
        
        analysis_result = {
            "paragraphs": [{"content": huge_content, "spans": [{"offset": 0}], "role": "paragraph"}]
        }
        
        segments = create_rich_segments(
            analysis_result, "large.pdf", 
            min_segment_tokens=100, max_segment_tokens=200
        )
        
        # Should still create a segment even if it exceeds max
        assert len(segments) == 1
        assert segments[0].token_count > 200
        
    def test_no_headings_document(self):
        """Test document with no headings."""
        analysis_result = {
            "paragraphs": [
                {"content": "Para 1", "spans": [{"offset": 0}], "role": "paragraph"},
                {"content": "Para 2", "spans": [{"offset": 10}], "role": "paragraph"},
                {"content": "Para 3", "spans": [{"offset": 20}], "role": "paragraph"},
            ]
        }
        
        segments = create_rich_segments(analysis_result, "no_headings.pdf")
        
        # Should still create segments
        assert len(segments) > 0
        
        # All contexts should be empty
        for segment in segments:
            context = segment.structural_context
            assert all(getattr(context, f"h{i}") is None for i in range(1, 7))


class TestOutputStructureCompliance:
    """Tests for output structure compliance with strategy document."""
    
    def test_rich_segment_structure(self):
        """Test that RichSegment structure matches specification."""
        analysis_result = {
            "paragraphs": [{"content": "Test", "spans": [{"offset": 0}], "role": "h1"}]
        }
        
        segments = create_rich_segments(analysis_result, "test.pdf")
        assert len(segments) == 1
        
        segment = segments[0]
        
        # Check all required fields
        assert hasattr(segment, 'segment_id')
        assert hasattr(segment, 'source_file')
        assert hasattr(segment, 'token_count')
        assert hasattr(segment, 'structural_context')
        assert hasattr(segment, 'elements')
        
        # Check field types
        assert isinstance(segment.segment_id, int)
        assert isinstance(segment.source_file, str)
        assert isinstance(segment.token_count, int)
        assert isinstance(segment.structural_context, StructuralContext)
        assert isinstance(segment.elements, list)
        
        # Check values
        assert segment.source_file == "test.pdf"
        assert segment.segment_id == 1
        assert segment.token_count > 0
        
    def test_context_preservation(self):
        """Test that context is properly preserved across segments."""
        analysis_result = {
            "paragraphs": [
                {"content": "Chapter 1", "spans": [{"offset": 0}], "role": "h1"},
                {"content": "Section A", "spans": [{"offset": 10}], "role": "h2"},
                {"content": "Content 1", "spans": [{"offset": 20}], "role": "paragraph"},
                {"content": "Chapter 2", "spans": [{"offset": 30}], "role": "h1"},  # Should trigger new segment
                {"content": "Content 2", "spans": [{"offset": 40}], "role": "paragraph"},
            ]
        }
        
        segments = create_rich_segments(
            analysis_result, "test.pdf",
            min_segment_tokens=1, max_segment_tokens=100
        )
        
        # Should have multiple segments due to H1 boundary
        assert len(segments) >= 2
        
        # Find segment containing "Section A"
        section_a_segment = None
        for segment in segments:
            if any("Section A" in elem.get("content", "") for elem in segment.elements):
                section_a_segment = segment
                break
                
        assert section_a_segment is not None, "Should find segment containing Section A"
        assert section_a_segment.structural_context.h1 == "Chapter 1"
        assert section_a_segment.structural_context.h2 == "Section A"


class TestErrorHandling:
    """Tests for error handling and input validation."""
    
    def test_invalid_analysis_result(self):
        """Test handling of invalid analysis_result types."""
        with pytest.raises(ValueError, match="analysis_result must be a dictionary"):
            create_rich_segments(None, "test.pdf")
            
        with pytest.raises(ValueError, match="analysis_result must be a dictionary"):
            create_rich_segments("not a dict", "test.pdf")
            
    def test_invalid_source_file(self):
        """Test handling of invalid source_file values."""
        analysis_result = {"paragraphs": []}
        
        with pytest.raises(ValueError, match="source_file must be a non-empty string"):
            create_rich_segments(analysis_result, "")
            
        with pytest.raises(ValueError, match="source_file must be a non-empty string"):
            create_rich_segments(analysis_result, "   ")
            
    def test_invalid_token_thresholds(self):
        """Test handling of invalid token threshold values."""
        analysis_result = {"paragraphs": []}
        
        with pytest.raises(ValueError, match="Token thresholds must be positive"):
            create_rich_segments(analysis_result, "test.pdf", min_segment_tokens=0)
            
        with pytest.raises(ValueError, match="Token thresholds must be positive"):
            create_rich_segments(analysis_result, "test.pdf", max_segment_tokens=-1)
            
        with pytest.raises(ValueError, match="min_segment_tokens must be less than max_segment_tokens"):
            create_rich_segments(analysis_result, "test.pdf", min_segment_tokens=100, max_segment_tokens=50)
            
    def test_malformed_elements(self):
        """Test handling of malformed elements in analysis result."""
        analysis_result = {
            "paragraphs": [
                "not a dict",  # Invalid element type
                {"content": "Valid element", "spans": [{"offset": 0}], "role": "paragraph"}
            ]
        }
        
        with pytest.raises(ValueError, match="Element .* must be a dictionary"):
            create_rich_segments(analysis_result, "test.pdf")


# Performance and validation fixtures
@pytest.fixture
def ground_truth_data():
    """Load ground truth data if available for performance testing."""
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "ground_truth_result.json")
    if os.path.exists(fixture_path):
        with open(fixture_path, 'r') as f:
            return json.load(f)
    return None


class TestPerformanceValidation:
    """Performance tests to ensure segmentation meets benchmarks."""
    
    def test_execution_time(self, ground_truth_data):
        """Test execution time with large document."""
        if ground_truth_data is None:
            pytest.skip("Ground truth data not available")
            
        import time
        start_time = time.time()
        
        segments = create_rich_segments(
            ground_truth_data, "large_document.pdf",
            min_segment_tokens=5000, max_segment_tokens=15000
        )
        
        execution_time = time.time() - start_time
        
        # Should complete in reasonable time (under 5 seconds for large doc)
        assert execution_time < 5.0
        assert len(segments) > 0
        
    def test_memory_efficiency(self, ground_truth_data):
        """Test memory usage during segmentation."""
        if ground_truth_data is None:
            pytest.skip("Ground truth data not available")
            
        # Basic test - should not crash with large data
        segments = create_rich_segments(
            ground_truth_data, "large_document.pdf"
        )
        
        # Should produce reasonable number of segments
        assert 1 <= len(segments) <= 100  # Reasonable bounds
        
        # Each segment should have reasonable size
        for segment in segments:
            assert segment.token_count > 0
            assert len(segment.elements) > 0 
