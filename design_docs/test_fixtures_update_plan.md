# Test Fixtures Update Plan

## Overview
This document outlines the plan for updating our test fixtures to comprehensively test the Azure Document Intelligence extraction and processing pipeline, particularly focusing on element ID generation and diverse document types.

## Current State
- Existing fixtures use real Azure DI output from a 353-page Dracula PDF
- Tests are failing due to outdated synthetic test data format
- Element ID system (`{element_type}_{page}_{index}_{hash}`) was recently added
- Need to test both with and without element IDs for backwards compatibility

## Goals
1. Maintain backwards compatibility by keeping existing fixtures
2. Create new fixtures with element IDs using "_with_ids" suffix
3. Test diverse document types to cover all Azure DI element types
4. Ensure comprehensive testing of the batching and stitching logic

## Proposed Test Documents

### 1. Small Document (2-5 pages) - Forms and Tables
**Options:**
- IRS Form 1040 (current year, public domain)
- CDC Vaccine Information Statement
- Standard government application form

**What it tests:**
- Tables with cells
- Key-value pairs (form fields)
- Checkboxes and selection marks
- Mixed content layouts

### 2. Medium Document (20-50 pages) - Technical Content
**Options:**
- Congressional Budget Office (CBO) economic report
- Scientific paper from PubMed Central (with CC license)
- WHO statistical report

**What it tests:**
- Complex tables with financial/statistical data
- Figures and charts
- Multi-column layouts
- Footnotes and references
- Lists (ordered and unordered)

### 3. Large Document (300+ pages) - Long-form Text
**Current:**
- Dracula (353 pages) - already have fixtures

**What it tests:**
- Batch processing (multiple batches of 1500 pages)
- Stitching algorithm performance
- Memory efficiency
- Consistent element ID generation across batches

### 4. Mathematical/Technical Document (10-20 pages)
**Options:**
- arXiv paper (with permissive license)
- NIST technical specification
- Open textbook chapter

**What it tests:**
- Mathematical formulas
- Technical diagrams
- Code blocks
- Specialized formatting

## Implementation Plan

### Phase 1: Create ID-Enhanced Fixtures from Existing Data
1. Write script `scripts/add_ids_to_fixtures.py` that:
   - Loads existing fixture files (batch_*.json, ground_truth_result.json)
   - Applies `add_ids_to_elements()` function from routes/extraction.py
   - Saves new files with "_with_ids" suffix
   - Validates ID uniqueness and format

2. Files to process:
   - `tests/fixtures/batch_1-50.json` → `batch_1-50_with_ids.json`
   - `tests/fixtures/batch_51-100.json` → `batch_51-100_with_ids.json`
   - `tests/fixtures/batch_101-150.json` → `batch_101-150_with_ids.json`
   - `tests/fixtures/batch_151-200.json` → `batch_151-200_with_ids.json`
   - `tests/fixtures/batch_201-250.json` → `batch_201-250_with_ids.json`
   - `tests/fixtures/batch_251-300.json` → `batch_251-300_with_ids.json`
   - `tests/fixtures/batch_301-353.json` → `batch_301-353_with_ids.json`
   - `tests/fixtures/ground_truth_result.json` → `ground_truth_result_with_ids.json`
   - `tests/fixtures_small/*.json` → `*_with_ids.json`

### Phase 2: Generate New Diverse Test Fixtures
1. Download selected public domain PDFs
2. Create new fixture generation script that:
   - Processes each PDF through Azure DI
   - Generates both full document and batched results
   - Creates both with and without ID versions
   - Organizes fixtures by document type

3. Proposed fixture structure:
```
tests/fixtures/
├── dracula/                    # Existing large document
│   ├── batch_*.json            # Original fixtures
│   └── batch_*_with_ids.json   # New ID-enhanced versions
├── forms/                      # New form/table documents
│   ├── irs_1040_full.json
│   ├── irs_1040_full_with_ids.json
│   └── irs_1040_pages_1-2.json
├── technical/                  # Scientific/technical docs
│   ├── cbo_report_full.json
│   ├── cbo_report_batch_*.json
│   └── pubmed_article_*.json
└── synthetic/                  # Updated synthetic test data
    └── (remove outdated files, create new ones)
```

### Phase 3: Update Tests
1. Fix synthetic test data to use current Azure DI format
2. Update segmentation tests to handle both fixture types
3. Add new test cases for:
   - Element ID generation and uniqueness
   - ID preservation through filtering and segmentation
   - Handling documents with various element types
   - Edge cases (empty elements, missing content, etc.)

### Phase 4: Validation
1. Ensure all tests pass with both old and new fixtures
2. Verify element IDs are:
   - Unique within documents
   - Stable (same content generates same ID)
   - Properly formatted
   - Preserved through processing pipeline

## Cost Considerations
- Azure DI API calls are paid per page
- Estimate: ~$50-100 for generating all new fixtures
- Fixtures will be committed to repository for CI/CD use

## Timeline
1. **Day 1**: Create ID enhancement script, process existing fixtures
2. **Day 2**: Select and download public domain documents
3. **Day 3**: Generate new fixtures from diverse documents
4. **Day 4**: Update tests and fix failing cases
5. **Day 5**: Final validation and documentation

## Success Criteria
- All existing tests pass with original fixtures
- All tests pass with new "_with_ids" fixtures
- Test coverage includes all Azure DI element types
- Batch processing and stitching work correctly for all document sizes
- Element IDs are properly generated and preserved throughout pipeline