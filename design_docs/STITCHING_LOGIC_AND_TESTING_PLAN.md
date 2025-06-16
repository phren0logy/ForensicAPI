# Stitching Logic and Testing Plan

## Overview

This document outlines the comprehensive testing strategy for the `stitch_analysis_results` function in `routes/extraction.py`. The function performs critical operations to combine Azure Document Intelligence batch results into a single, cohesive analysis result that is identical to what would be produced by analyzing the entire document in one API call.

## Function Responsibilities

The `stitch_analysis_results` function must:

1. **Content Concatenation**: Merge `content` strings from multiple batches
2. **Span Offset Updates**: Adjust character offsets for all elements to point to correct locations in the final concatenated content
3. **Page Number Corrections**: Update page numbers across all elements and bounding regions
4. **Element List Merging**: Combine arrays of pages, paragraphs, tables, words, lines, selection marks, etc.

## Testing Strategy

### Phase 1: Small Test Cases (Immediate Logic Validation)

_Priority: CRITICAL - Must complete before proceeding to larger tests_

#### Small Synthetic Cases

- [x] Create 2-page synthetic test case with basic content
- [x] Test content concatenation accuracy
- [x] Verify span offset calculations for simple case
- [x] Test page number updates (pages 1-2 → pages 1-2, then pages 3-4)
- [x] Validate element array merging

#### Real Data Subsets (5-10 pages)

- [x] Extract small portions from existing fixtures
- [x] Test with real Azure DI response structure
- [x] Verify all element types are handled correctly
- [x] Compare against expected manual calculations

#### Edge Cases

- [x] Test empty batch handling
- [x] Test single page documents
- [x] Test batches with no paragraphs/tables
- [x] Test boundary conditions (empty content, missing spans)

### Phase 2: Medium Test Cases (Scaling Validation)

_Priority: HIGH - Validates real-world usage_

#### Existing Fixture Integration

- [ ] Test with 2 consecutive 50-page batches
- [ ] Test with 3 consecutive 50-page batches
- [ ] Verify cumulative offset calculations remain accurate
- [ ] Compare stitched result structure against ground truth

#### Real Data Validation

- [ ] Load existing batch files as JSON dictionaries
- [ ] Implement ground truth comparison logic
- [ ] Test with actual batch_1-50.json and batch_51-100.json
- [ ] Verify no information loss during stitching
- [ ] Ensure output matches Azure DI response format

#### Multi-batch Scenarios

- [ ] Test non-consecutive page ranges
- [ ] Test batches with different element densities
- [ ] Validate span continuity across multiple batches
- [ ] Test page number sequence integrity

### Phase 3: Large-Scale Testing (Future - Production Readiness)

_Priority: MEDIUM - For production deployment_

```
# TODO: Future large-scale testing implementation
# - Full 353-page document validation
# - Performance benchmarking for memory usage
# - Stress testing with 12,000+ page scenarios
# - Execution time profiling
# - Memory efficiency optimization
```

## Test Implementation Structure

### File Organization

```
tests/
├── test_stitching_logic.py           # Main test file
├── fixtures_small/                   # Hand-crafted minimal cases
│   ├── synthetic_2_pages.json
│   ├── real_extract_5_pages.json
│   └── edge_cases/
├── fixtures_medium/                  # Existing 50-page batches
│   ├── batch_1-50.json              # (existing)
│   ├── batch_51-100.json            # (existing)
│   └── ground_truth_result.json     # (existing)
└── test_integration.py              # End-to-end without HTTP
```

### Test Categories

#### A. Basic Stitching Logic Tests

- [x] `test_content_concatenation()`
- [x] `test_span_offset_updates()`
- [x] `test_page_number_corrections()`
- [x] `test_element_array_merging()`

#### B. Real Data Validation Tests

- [ ] `test_with_real_batch_data()`
- [ ] `test_against_ground_truth()`
- [ ] `test_data_fidelity_preservation()`
- [ ] `test_azure_format_consistency()`

#### C. Edge Case Tests

- [x] `test_empty_batch_handling()`
- [x] `test_single_page_documents()`
- [x] `test_missing_elements()`
- [x] `test_boundary_conditions()`

#### D. Scaling Behavior Tests

- [ ] `test_multi_batch_accumulation()`
- [ ] `test_offset_calculation_at_scale()`
- [ ] `test_memory_efficiency()`

## Validation Framework

### Level 1: Structural Validation

- [ ] Implement JSON schema compliance checks
- [ ] Verify required fields presence
- [ ] Check data type consistency
- [ ] Validate array structure integrity

### Level 2: Mathematical Validation

- [ ] Content length equation verification
- [ ] Span offset continuity checks
- [ ] Page number sequence validation
- [ ] Bounding region consistency

### Level 3: Semantic Validation

- [ ] Ground truth comparison implementation
- [ ] Content preservation verification
- [ ] Element relationship integrity checks

## Implementation Timeline

### Week 1 - Core Logic Validation

- [x] Day 1: Implement synthetic 2-page test case
- [x] Day 2: Create real 5-page extract and test
- [x] Day 3: Implement basic validation framework
- [x] Day 4-5: Complete all Phase 1 tests

### Week 2 - Real Data Integration

- [ ] Day 1-2: Implement fixture loading and ground truth comparison
- [ ] Day 3-4: Test with existing 50-page batches
- [ ] Day 5: Complete all Phase 2 tests and validation

## Success Criteria

### Phase 1 Success

- [x] All synthetic tests pass
- [x] Real data subset tests pass
- [x] Edge cases handled correctly
- [x] No fundamental logic errors detected

### Phase 2 Success

- [ ] Multi-batch stitching works correctly
- [ ] Ground truth comparison validates accuracy
- [ ] Performance acceptable for medium datasets
- [ ] Ready for production use with documents up to ~500 pages

### Overall Success

- [ ] `stitch_analysis_results` function is thoroughly tested
- [ ] Confident in correctness for production deployment
- [ ] Clear path to large-scale testing when needed
- [ ] Comprehensive test coverage documented

## Testing Principles

1. **Fail-Fast**: Run small cases first, stop on any failure
2. **Property-Based**: Test mathematical invariants on every case
3. **Incremental Complexity**: Only proceed to larger tests after smaller ones pass
4. **Direct Function Testing**: Bypass HTTP layer to avoid TestClient issues
5. **Real Data Focus**: Use actual Azure DI responses whenever possible

## Notes

- All tests should directly call `stitch_analysis_results` function with JSON dictionaries
- Avoid mocking Azure SDK objects - use real fixture data instead
- Focus on data integrity and mathematical correctness
- Phase 3 large-scale testing deferred but documented for future implementation
