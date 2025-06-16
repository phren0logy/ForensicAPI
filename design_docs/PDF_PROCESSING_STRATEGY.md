# Structured Data Extraction: Strategy for Large Document Processing

Note: On 2025-06-16, this file was moved to the FastAPI backend for implementation.

This document outlines a strategy for processing extremely large documents (e.g., thousands of pages) by creating large, structurally-aware, and metadata-rich segments suitable for advanced analysis.

The primary goal is to generate document segments ranging from 10,000 to 30,000 tokens (estimated range) while preserving the full hierarchical context and granular metadata provided by the source analysis engine.

## Implementation Status

### ✅ Phase 1: Batch Processing & Perfect Stitching (COMPLETE)

- **Implemented in**: `routes/extraction.py`
- **Core Function**: `stitch_analysis_results()` with enhanced validation and automatic offset calculation
- **Testing**: 36 comprehensive tests validating all scenarios (small-scale, medium-scale, edge cases)
- **Production Ready**: Handles documents up to ~150 pages with robust error handling

### 🔄 Phase 2: Rich Segment Creation (PLANNED)

- **Planned Endpoint**: `POST /segment`
- **Purpose**: Transform complete Azure DI results into structured Rich Segments
- **Status**: Strategy defined, ready for implementation

## Core Principles

1.  **Direct JSON Consumption:** Instead of processing derived formats like Markdown, this strategy consumes the raw JSON output from the [Azure Document Intelligence `prebuilt-layout` model](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/prebuilt/layout?view=doc-intel-4.0.0&tabs=rest%2Csample-code#document-structure-layout-analysis). This provides direct access to detailed structural and positional metadata.
2.  **Aggregation over Splitting:** This approach focuses on intelligently aggregating document elements (paragraphs, headings, tables) into large, coherent blocks.
3.  **Stateful Batch Processing:** To handle documents that exceed API limits, a stateful process manages the hierarchical context (e.g., current chapter and section) across multiple, sequential API calls.

---

## The `Rich Segment` Data Structure

A "segment" is no longer a simple string of text. It is a structured JSON object designed to be self-contained and fully descriptive.

### Conceptual Schema

```json
{
  "segment_id": "integer",
  "source_file": "string",
  "token_count": "integer",
  "structural_context": {
    "h1": "string | null",
    "h2": "string | null",
    "h3": "string | null",
    "h4": "string | null"
  },
  "elements": [
    // Array of original element objects from Document Intelligence
    {
      "role": "string",
      "content": "string",
      "bounding_regions": "[...]",
      "page_number": "integer"
    }
    // ... more elements like paragraphs, tables, figures, etc.
  ]
}
```

- `segment_id`: A unique identifier for the segment within a processing run.
- `source_file`: The name of the original source document (e.g., `my_large_document.pdf`).
- `token_count`: The total approximate token count of the content within the `elements` array. (let's either defer this, or do it properly using tiktoken)
- `structural_context`: An object that stores the last seen heading for each level, providing the hierarchical context for the beginning of the segment.
- `elements`: An ordered list of the full JSON objects for each document element (paragraph, heading, table, etc.) as returned by the Document Intelligence API. This preserves all original metadata like page numbers and bounding boxes.

---

## The Workflow: Stateful Hierarchical Aggregation

This workflow is designed to be orchestrated by a new function that manages the entire process for a single large document.

### 1. Initialization

- **Input:** The path to the large source document (e.g., a 5000-page PDF).
- **Configuration:** Define a tunable `PAGE_BATCH_SIZE` (e.g., 200 pages) to control the size of each call to the Document Intelligence API.
- **State Management:**
  - Initialize an empty `StructuralContext` object to track the current headings: `{ "h1": null, "h2": null, ... }`.
  - Initialize an empty list to hold the final `Rich Segment` objects.
  - Initialize a main buffer to accumulate elements for the current in-progress segment.

### 2. Iterative Batch Processing

The system will loop through the total number of pages in the document, processing one batch at a time.

- **API Call:** For each batch, make a call to the Document Intelligence API using the `pages` query parameter to specify the range (e.g., `pages="1-200"`, then `pages="201-400"`).

#### "Perfect Stitching" of Batch Results ✅ IMPLEMENTED

**Implementation**: Our production system now implements perfect stitching through the enhanced `stitch_analysis_results()` function in `routes/extraction.py`.

**Key Features**:

- **Automatic Offset Calculation**: `calculate_page_offset()` automatically determines correct page number adjustments
- **Input Validation**: `validate_batch_structure()` ensures Azure DI format compliance before processing
- **Comprehensive Testing**: 36 tests validate correctness across synthetic data, real data subsets, and full-scale scenarios

To ensure the final, combined output is indistinguishable from a single API call on the entire document, our implementation performs the following operations:

1.  **Concatenate Content:** The `content` string (the full Markdown or text) from each batch result is appended to create one single, continuous string.
2.  **Automatic Page Number Correction:** The enhanced system automatically calculates and applies the correct page offset for each batch, ensuring continuous page numbering.
3.  **Precise Character Offset Updates:** All `span` offsets (both `spans` array and individual `span` objects) are automatically adjusted by the cumulative content length from preceding batches.
4.  **Element Preservation**: All element types (paragraphs, tables, words, lines, selectionMarks) are properly merged while preserving their original metadata.

**Validation**: Our test suite validates this stitching logic against:

- Real Azure DI batch outputs (`batch_1-50.json`, `batch_51-100.json`, etc.)
- Ground truth comparisons for content accuracy
- Edge cases (empty batches, missing elements, various span patterns)

This meticulous process guarantees that the final `analysis_result` object is a valid and internally consistent representation of the entire document, ready for Phase 2 segmentation.

- **Process Response:** For each JSON response received from the API:
  - Use our validated stitching function to combine results
  - Iterate through the document elements (e.g., `paragraphs`, `tables`) returned for that page range.
  - **Update Context:** If an element is a heading (e.g., `role: "sectionHeading"`), update the `StructuralContext` object. For example, a new `h2` heading would update the `h2` field and set `h3`, `h4`, etc., to `null`.
  - **Buffer Elements:** Append the **full, original JSON object** for each element to the main buffer's `elements` list.

### 3. Segment Creation and Finalization

After processing the elements from a batch, the system checks if a `Rich Segment` should be finalized.

- **Check Thresholds:** Calculate the current token count of the elements in the main buffer.
- **Find Boundary:** If the token count exceeds the minimum threshold (e.g., 10,000 tokens), the system looks for a logical boundary to "seal" the segment. A preferred boundary is a high-level `sectionHeading` (e.g., H1 or H2).
- **Finalize Segment:**
  1.  Once a boundary is identified, a new `Rich Segment` object is created.
  2.  The `structural_context` is populated from the state object at the _beginning_ of the segment's content.
  3.  The `elements` list is moved from the main buffer into the new segment.
  4.  The finalized `Rich Segment` is added to the results list.
  5.  The main buffer is cleared to begin accumulating elements for the next segment.

This process continues until all pages of the document have been processed.

### 4. Data Storage

We'll need to provide an ouptut that can be fed into a database.

---

## Phase 2: The Segmentation Service

Once a full, stitched `analysis_result` is obtained from the extraction process, it can be passed to a separate, dedicated segmentation service.

**Current Status**: The extraction phase is complete and production-ready. The segmentation service represents the next phase of development.

**Endpoint:** `POST /segment`

**Responsibility:** To consume the full JSON output from the extraction step and apply the stateful hierarchical aggregation logic to produce logically coherent `Rich Segment` objects.

**Input:** The endpoint will accept a JSON payload containing the complete, validated `analysis_result` object produced by our stitching implementation.

**Workflow:** The service will execute the "Stateful Hierarchical Aggregation" workflow described in this document. It will iterate through the elements in the `analysis_result`, track the heading context, and group elements into segments based on token count and logical boundaries (e.g., section headings).

**Output:** A JSON array of `Rich Segment` objects, which can then be stored or used for downstream analysis tasks.

## Technical Implementation Reference

### Current Implementation

- **File**: `routes/extraction.py`
- **Main Function**: `stitch_analysis_results(stitched_result, new_result, page_offset=None, validate_inputs=True)`
- **Validation Functions**: `validate_batch_structure()`, `calculate_page_offset()`, `validate_batch_sequence()`
- **Production Endpoint**: `POST /extract` (handles batch processing and stitching)

### Test Coverage

- **File**: `tests/test_stitching_logic.py`
- **Total Tests**: 36 (all passing)
- **Coverage**: Synthetic data, real Azure DI data, edge cases, validation functions
- **Performance**: Full test suite completes in under 2 seconds

### Key Features Implemented

- **Automatic Offset Calculation**: Eliminates manual page numbering errors
- **Input Validation**: Ensures Azure DI format compliance
- **Backward Compatibility**: Existing code continues to work
- **Comprehensive Error Handling**: Clear validation messages for debugging
- **Real Data Validation**: Tested against actual Azure DI batch outputs

This foundation provides a robust platform for implementing Phase 2's Rich Segment creation service.
