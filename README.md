# FastAPI Reusable Prototyping App

## Test the Endpoints with Built-in HTML Pages

This project includes simple HTML forms for testing endpoints.

### How to Use:

1. **Start the FastAPI server:**

   ```
   uv run run.py
   ```

   or

   ```
   uvicorn main:app --reload
   ```

2. **Visit the test pages in your browser:**

   - [PDF Extraction Test](http://127.0.0.1:8000/pdf-test)
   - [Prompt Composer Test](http://127.0.0.1:8000/prompt-test)

3. **PDF Extraction Test**

   - Upload a PDF file to test the extraction endpoint with Azure Document Intelligence.

4. **Prompt Composer Test**
   - Fill in the fields and submit to see the composed prompt result.

---

## Getting Started

### Prerequisites

- Python 3.13+
- Install dependencies using [uv](https://github.com/astral-sh/uv):
  ```sh
  uv sync
  ```

### Running the Server

To start the FastAPI server:

```sh
uv run run.py
```

## API Endpoints

### `/compose-prompt` (POST)

- **Description:** Compose a prompt from multiple text fields and/or files, each wrapped in a specified XML tag.
- **Request:**
  - `multipart/form-data` with a `mapping` field (JSON: `{tag: value}`), where each key is an XML tag and the value is either:
    - A string (content), or
    - The name of an uploaded file field
  - Optionally, upload files with field names matching the mapping values.
- **Special Case:**
  - If a tag is named `instructions`, its section is wrapped in `<instructions>` and appears at both the top and bottom of the result.
- **Response:**
  - Plain text: The composed prompt with each section wrapped in its XML tag.
- **Example (text only):**
  ```json
  {
    "document": "Some document text",
    "transcript": "Transcript goes here",
    "manual": "Manual text",
    "instructions": "Do not share."
  }
  ```

### `/extract` (POST)

- **Description:** Extracts structured data and markdown from PDF documents using Azure Document Intelligence with intelligent batch processing. Implements Phase 1 of the PDF processing strategy with perfect document reconstruction for documents of any size.
- **Request:**
  - `multipart/form-data` with the following fields:
    - `file`: PDF file to process (required)
    - `batch_size`: Number of pages per batch (optional, default: 1500)
    - `include_element_ids`: Add unique IDs to all elements (optional, default: true)
    - `return_both`: Return both original and ID-enriched versions (optional, default: false)
- **Advanced Features:**
  - **Intelligent Batch Processing**: Automatically processes large documents in configurable page batches
  - **Perfect Stitching**: Reconstructs complete documents with 100% accuracy using advanced stitching algorithms
  - **Element ID Generation**: Automatically adds stable `_id` fields to all elements for tracking through filtering/segmentation
  - **Automatic Offset Calculation**: Seamlessly handles page numbering and content offsets across batches
  - **Concurrent Processing**: Processes multiple batches simultaneously for optimal performance
  - **Input Validation**: Comprehensive validation of Azure DI structure and batch sequences
  - **Production Ready**: Handles documents up to 353+ pages with robust error handling
- **Performance:**
  - Sub-second execution with minimal memory usage
  - Validated with complete 353-page document reconstruction
  - Perfect accuracy: 100% ground truth matching for content integrity
- **Response:**
  - A JSON object containing:
    ```json
    {
      "markdown_content": "Complete markdown of entire document",
      "analysis_result": {
        "content": "Full document content...",
        "paragraphs": [
          {
            "_id": "para_1_0_a3f2b1",  // Unique element ID
            "content": "...",
            "role": "paragraph",
            "boundingRegions": [...],
            // ... other Azure DI fields
          }
        ],
        "tables": [
          {
            "_id": "table_5_2_d4e5f6",
            "cells": [
              {
                "_id": "cell_5_2_0_0_b7c8d9",
                "content": "...",
                // ... other cell fields
              }
            ],
            // ... other table fields
          }
        ],
        // ... other elements with _id fields
      }
    }
    ```
  - When `include_element_ids=true` (default): Returns Azure DI format with added `_id` fields
  - When `include_element_ids=false`: Returns pure Azure DI format without IDs
  - When `return_both=true`: Returns both `analysis_result` (with IDs) and `analysis_result_original` (without IDs)

### `/segment` (POST)

- **Description:** Transforms complete Azure Document Intelligence analysis results into rich, structurally-aware segments with configurable token thresholds. Implements Phase 2 of the PDF processing strategy for creating large, coherent document chunks suitable for advanced analysis.
- **Request:**
  - A JSON object with the following structure:
    ```json
    {
      "source_file": "document.pdf",
      "analysis_result": { "... complete Azure DI analysis result ..." },
      "min_segment_tokens": 10000,
      "max_segment_tokens": 30000
    }
    ```
  - **Parameters:**
    - `source_file`: Name of the original document (required)
    - `analysis_result`: Complete Azure DI analysis result from `/extract` endpoint (required)
    - `min_segment_tokens`: Minimum tokens per segment (optional, default: 10,000)
    - `max_segment_tokens`: Maximum tokens per segment - soft limit (optional, default: 30,000)
- **Features:**
  - Configurable token thresholds for different use cases
  - Intelligent boundary detection at heading levels (H1/H2)
  - Preserves full Azure DI metadata (bounding boxes, page numbers, etc.)
  - Maintains hierarchical context (current H1-H6 headings)
  - Processes all Azure DI element types (paragraphs, tables, figures, formulas, keyValuePairs)
- **Response:**
  - A JSON array of "Rich Segment" objects with the following structure:
    ```json
    [
      {
        "segment_id": 1,
        "source_file": "document.pdf",
        "token_count": 12543,
        "structural_context": {
          "h1": "Chapter 1",
          "h2": "Section A",
          "h3": null,
          "h4": null,
          "h5": null,
          "h6": null
        },
        "elements": [
          {
            "role": "paragraph",
            "content": "...",
            "bounding_regions": [...],
            "page_number": 1
          }
        ]
      }
    ]
    ```

### `/segment-filtered` (POST)

- **Description:** Combines filtering and segmentation to prepare documents for LLM processing with significantly reduced token usage. Applies configurable filters to remove unnecessary fields while preserving element IDs for traceability.
- **Request:**
  - A JSON object with the following structure:
    ```json
    {
      "source_file": "document.pdf",
      "analysis_result": { "... Azure DI result with _id fields ..." },
      "filter_config": {
        "filter_preset": "llm_ready",
        "include_element_ids": true
      },
      "min_segment_tokens": 10000,
      "max_segment_tokens": 30000
    }
    ```
  - **Parameters:**
    - `filter_config.filter_preset`: Name of preset or "custom" (optional, default: "llm_ready")
    - `filter_config.fields`: Custom list of fields to include when using "custom" preset (optional)
    - `filter_config.include_element_ids`: Whether to include _id fields (optional, default: true)
- **Filter Presets:**
  - `no_filter`: Preserves all original fields (returns raw dictionary format)
  - `llm_ready`: Optimal balance - includes content, structure, and headers/footers for citations (default)
  - `forensic_extraction`: Includes document metadata for complex multi-document analysis
  - `citation_optimized`: Minimal fields - content, page numbers, and IDs only
- **Simplified Allowlist Filtering:**
  - **Single Field List**: Each preset defines a simple list of fields to include
  - **No Complex Rules**: Removed confusing include/exclude patterns in favor of explicit field lists
  - **Exact Field Definitions**:
    - `no_filter`: `["*"]` - includes all fields from Azure DI
    - `citation_optimized`: `["_id", "content", "pageNumber", "elementIndex", "pageFooter"]`
    - `llm_ready`: `["_id", "content", "pageNumber", "role", "elementType", "elementIndex", "pageHeader", "pageFooter", "parentSection"]`
    - `forensic_extraction`: `["_id", "content", "pageNumber", "role", "elementType", "elementIndex", "pageHeader", "pageFooter", "parentSection", "documentMetadata"]`
- **Custom Filtering Example:**
  ```json
  {
    "filter_config": {
      "filter_preset": "custom",
      "fields": ["_id", "content", "pageNumber", "myCustomField"],
      "include_element_ids": true
    }
  }
  ```
- **Features:**
  - **Element ID Preservation**: The `_id` field is included based on filter preset
  - **Hybrid Return Types**: `no_filter` returns raw dictionaries, other presets return typed FilteredElement objects
  - **Token Optimization**: Typically achieves 50-75% reduction in token usage
  - **Metrics Tracking**: Reports size reduction, element counts, and excluded fields
- **Response:**
  - A JSON object containing:
    ```json
    {
      "segments": [
        {
          "segment_id": 1,
          "source_file": "document.pdf",
          "token_count": 12543,
          "structural_context": { "h1": "Chapter 1", "h2": "Section A" },
          "elements": [
            {
              "_id": "para_1_0_a3f2b1",  // Preserved from extraction
              "content": "...",
              "pageNumber": 1,
              "role": "paragraph"
              // Only fields allowed by filter preset
            }
          ]
        }
      ],
      "element_mappings": [...],  // Maps filtered elements back to originals
      "metrics": {
        "original_size_bytes": 500000,
        "filtered_size_bytes": 150000,
        "reduction_percentage": 70.0,
        "excluded_fields": ["boundingBox", "polygon", "confidence", ...]
      }
    }
    ```

### `/anonymize-azure-di` (POST)

- **Description:** Anonymizes sensitive information in Azure Document Intelligence output using advanced NLP models.
- **Request:**
  - A JSON object containing the Azure DI analysis result (with or without element IDs)
- **Features:**
  - Uses BERT-based models for accurate PII detection
  - Supports custom entity patterns
  - Preserves document structure and element IDs
- **Response:**
  - Anonymized version of the input with sensitive data replaced

## Element ID System

The FastAPI backend implements a stable element identification system that enables tracking elements throughout the processing pipeline:

### ID Generation Strategy

Element IDs are generated during the extraction phase (`/extract`) and follow this format:
- **Pattern**: `{element_type}_{page}_{global_index}_{content_hash}`
- **Examples**: 
  - `para_1_0_a3f2b1` - First paragraph on page 1
  - `table_5_2_d4e5f6` - Third table on page 5
  - `cell_5_2_0_0_b7c8d9` - Cell at row 0, column 0 in the third table on page 5

### ID Stability Through Pipeline

```
1. Extraction (/extract)
   ├── Stitches batches from Azure DI
   └── Adds _id to all elements

2. Filtering (/segment-filtered)
   ├── Removes unwanted fields based on preset
   └── PRESERVES _id fields

3. Segmentation
   ├── Groups filtered elements into chunks
   └── Elements keep their original _id

4. LLM Processing
   └── Can reference specific elements by _id
```

### Benefits

- **Traceability**: Track any element from LLM output back to its exact location in the original document
- **Stability**: IDs remain constant regardless of filtering or segmentation choices
- **Debugging**: Easy to correlate elements across different processing stages
- **Caching**: Can cache processed elements by ID for efficiency

---

For questions or issues, please contact the project maintainer.
