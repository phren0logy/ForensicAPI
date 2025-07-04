# ForensicAPI

This is a tool to facilitate LLM experiments with PDFs, especially those that contain sensitive information. Remember to only use services that provide appropriate privacy. Because of the Azure policy covering HIPAA and providing a BAA for Azure customers, many of the functions of this library are Azure-centric.

This application provides an API that uses Azure Document Intelligence to convert PDFs to Markdown and structured JSON, handling PDFs of arbitrary size (rather than being limited to Azure's single-request limit of 2000 pages). The system preserves document structure through intelligent segmentation that maintains hierarchical heading context (H1-H6). Every JSON element is automatically assigned a unique ID for tracing back to the source document. The filtering endpoint facilitates stripping out unnecessary JSON components to optimize for LLM token usage.

There is also an endpoint to anonymize documents using LLM-Guard with the AI4Privacy BERT model for comprehensive PII detection (54 entity types with 97.8% F1 score), as well as an endpoint to compose prompts around large documents with instructions and the beginning and the end (as recommended by the GPT-4.1 documentation).

## Test the Endpoints

### Using the API Documentation

FastAPI provides automatic interactive API documentation:

1. **Start the FastAPI server:**

   ```
   uv run run.py
   ```

   or

   ```
   uvicorn main:app --reload
   ```

2. **Visit the interactive documentation:**

   - [Swagger UI](http://127.0.0.1:8000/docs) - Interactive API testing
   - [ReDoc](http://127.0.0.1:8000/redoc) - Alternative API documentation

3. **Test endpoints directly** through the Swagger UI interface by:
   - Clicking on any endpoint
   - Clicking "Try it out"
   - Filling in the request parameters
   - Clicking "Execute"

---

## Getting Started

### Prerequisites

- Python 3.13+
- Azure Document Intelligence account and credentials
- Install dependencies using [uv](https://github.com/astral-sh/uv):
  ```sh
  uv sync
  ```

### Environment Configuration

The application requires Azure Document Intelligence credentials. Create a `.env` file in the project root with:

```env
# Azure Document Intelligence Configuration
AZURE_DI_ENDPOINT=https://your-resource-name.cognitiveservices.azure.com/
AZURE_DI_KEY=your-api-key-here

# Optional: Logging level (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO
```

**Important**: Never commit the `.env` file to version control. It's already included in `.gitignore`.

### Key Dependencies

- **[Azure Document Intelligence](https://azure.microsoft.com/en-us/products/ai-services/ai-document-intelligence/)**: Enterprise-grade PDF to structured data extraction
- **[LLM-Guard](https://llm-guard.com/)**: Advanced PII detection and anonymization with AI4Privacy BERT model (54 PII types)
- **[FastAPI](https://fastapi.tiangolo.com/)**: Modern, fast web framework with automatic API documentation
- **[UV](https://github.com/astral-sh/uv)**: Ultra-fast Python package and project management
- **Python 3.13+**: Required for latest performance improvements and type hints

### Examples

Example scripts are provided in the `examples/` directory:
- `pseudonymization_demo.py`: Demonstrates stateless pseudonymization and deanonymization workflows

### Running the Server

To start the FastAPI server:

```sh
uv run run.py
```

## API Endpoints

### `/` (GET)

- **Description:** Root endpoint that returns information about all available API endpoints.
- **Response:**
  - JSON object with welcome message and list of available endpoints with their descriptions.

### `/health` (GET)

- **Description:** Health check endpoint to verify the service is running.
- **Response:**
  - JSON object with status "healthy" and timestamp.

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
    "document": "Text of your document goes here",
    "transcript": "Transcript of therapy session goes here",
    "manual": "Scoring manual for scoring therapy session fidelity",
    "instructions": "Score the attached transcript, wrapped in transcript tags, according to the manual, wrapped in manual tags. Provide a score for each scale in the manual."
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

- **Description:** Transforms complete Azure Document Intelligence analysis results into rich, structurally-aware segments with configurable token thresholds. This creates large, coherent document chunks suitable for advanced analysis.
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
    - `filter_config.include_element_ids`: Whether to include \_id fields (optional, default: true)
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

### `/filter/presets` (GET)

- **Description:** Returns all available filter presets and their descriptions for use with the filtering and segmentation endpoints.
- **Response:**
  - JSON object containing preset names as keys and their configurations as values:
    ```json
    {
      "no_filter": {
        "description": "Preserves all original fields from Azure DI",
        "fields": ["*"]
      },
      "llm_ready": {
        "description": "Optimal balance for LLM processing - includes content, structure, and headers/footers",
        "fields": [
          "_id",
          "content",
          "pageNumber",
          "role",
          "elementType",
          "elementIndex",
          "pageHeader",
          "pageFooter",
          "parentSection"
        ]
      },
      "forensic_extraction": {
        "description": "Includes document metadata for complex multi-document analysis",
        "fields": [
          "_id",
          "content",
          "pageNumber",
          "role",
          "elementType",
          "elementIndex",
          "pageHeader",
          "pageFooter",
          "parentSection",
          "documentMetadata"
        ]
      },
      "citation_optimized": {
        "description": "Minimal fields - content, page numbers, and IDs only",
        "fields": ["_id", "content", "pageNumber", "elementIndex", "pageFooter"]
      }
    }
    ```

### `/anonymization/anonymize-azure-di` (POST)

- **Description:** Anonymizes sensitive information in Azure Document Intelligence output using LLM-Guard with the AI4Privacy BERT model. Supports stateless operation by accepting and returning vault data for consistent anonymization across requests.
- **Request:**
  - A JSON object with the following structure:
    ```json
    {
      "azure_di_json": {
        /* Azure DI analysis result */
      },
      "config": {
        "entity_types": [
          "PERSON",
          "DATE_TIME",
          "LOCATION",
          "PHONE_NUMBER",
          "EMAIL_ADDRESS",
          "US_SSN",
          "MEDICAL_LICENSE"
        ],
        "score_threshold": 0.5,
        "anonymize_all_strings": true,
        "date_shift_days": 365,
        "return_decision_process": false
      },
      "vault_data": [  /* Optional: Previous vault data for consistent replacements */
        ["John Doe", "Jane Smith"],
        ["_date_offset", "-365"]
      ]
    }
    ```
- **Features:**
  - Uses LLM-Guard with AI4Privacy BERT model (Isotonic/distilbert_finetuned_ai4privacy_v2)
  - Detects 54 different PII types with 97.8% F1 score
  - Advanced pattern recognition beyond basic NER
  - Configurable confidence threshold to reduce false positives
  - Realistic fake data generation using Faker library
  - Cryptographically secure random generation for sensitive IDs
  - Session-isolated replacements for security
  - Preserves document structure and element IDs
  - Optional decision process debugging
- **Supported Entity Types:**
  - All 54 PII types from AI4Privacy model including:
    - Personal: Names, ages, gender, occupation, education
    - Financial: Bank accounts, credit cards, IBANs
    - Contact: Emails, phones, addresses, URLs
    - Technical: IP addresses, crypto wallets, API keys
    - Medical: Diagnoses, medications, conditions
    - Legal: Case numbers, court names
  - Note: You can specify a subset of entity types in the config
- **Response:**
  - JSON object containing:
    ```json
    {
      "anonymized_json": { /* Anonymized Azure DI JSON */ },
      "statistics": { "PERSON": 5, "DATE_TIME": 2, ... },
      "vault_data": [  /* Updated vault with all anonymization mappings */
        ["John Doe", "Jane Smith"],
        ["john@example.com", "jane@example.com"],
        ["_date_offset", "-365"]
      ]
    }
    ```

### `/anonymization/anonymize-markdown` (POST)

- **Description:** Anonymizes sensitive information in markdown or plain text while preserving formatting. Supports stateless operation with vault data.
- **Request:**
  - A JSON object with the following structure:
    ```json
    {
      "markdown_text": "Your markdown or plain text content...",
      "config": {
        "entity_types": ["PERSON", "DATE_TIME", ...],
        "score_threshold": 0.5,
        "anonymize_all_strings": true,
        "return_decision_process": false
      },
      "vault_data": [  /* Optional: Previous vault data */
        ["placeholder", "original"], ...
      ]
    }
    ```
- **Features:**
  - Same powerful anonymization engine as the Azure DI endpoint
  - Preserves markdown formatting (headers, lists, code blocks, etc.)
  - Configurable entity detection with score threshold
  - Consistent replacements across the document
  - Optional decision process for debugging
- **Response:**
  - JSON object containing:
    ```json
    {
      "anonymized_text": "Anonymized markdown content...",
      "statistics": { "PERSON": 3, "EMAIL_ADDRESS": 2, ... },
      "decision_process": [ /* optional debugging info */ ],
      "vault_data": [ /* Updated vault data */ ]
    }
    ```

### `/anonymization/health` (GET)

- **Description:** Health check endpoint for the anonymization service. Verifies that the LLM-Guard scanner with AI4Privacy BERT model is ready.
- **Response:**
  - JSON object with service status and model information:
    ```json
    {
      "status": "healthy",
      "service": "anonymization",
      "engines_initialized": true,
      "recognizers": "LLM-Guard with AI4Privacy model (54 PII types)",
      "model": "Isotonic/distilbert_finetuned_ai4privacy_v2"
    }
    ```
  - Returns `"status": "unhealthy"` with error details if the service is not ready.

### `/anonymization/pseudonymize` (POST)

- **Description:** Pseudonymize text with consistent replacements designed for reversibility. Uses vault state for maintaining mappings across multiple documents.
- **Request:**
  ```json
  {
    "text": "Text to pseudonymize",
    "config": {
      "entity_types": ["PERSON", "EMAIL_ADDRESS", ...],
      "date_shift_days": 365
    },
    "vault_data": [ /* Optional: Previous vault data */ ]
  }
  ```
- **Response:**
  ```json
  {
    "pseudonymized_text": "Text with consistent pseudonyms",
    "statistics": { "PERSON": 2, ... },
    "vault_data": [ /* Updated vault with all mappings */ ]
  }
  ```

### `/anonymization/deanonymize` (POST)

- **Description:** Reverse pseudonymization using vault mappings to restore original values.
- **Request:**
  ```json
  {
    "text": "Pseudonymized text",
    "vault_data": [ /* Required: Vault data from pseudonymization */ ]
  }
  ```
- **Response:**
  ```json
  {
    "deanonymized_text": "Original text restored",
    "statistics": { "PERSON": 2, ... }
  }
  ```

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

## Performance and Limits

- **PDF Processing**:
  - Maximum tested: 353+ pages with perfect reconstruction
  - Default batch size: 1500 pages per Azure DI request
  - Concurrent batch processing for optimal speed
  - Sub-second execution for most operations
- **Segmentation**:
  - Token limits: Configurable 10k-30k tokens per segment
  - Intelligent boundary detection at H1/H2 headings
  - Minimal memory usage through streaming architecture
- **Anonymization**:
  - Sub-second processing for typical documents
  - BERT model initialization: ~2-3 seconds on first request
  - High accuracy for common PII types
- **API Limits**:
  - Request size: Limited by web server configuration (typically 100MB)
  - Timeout: Default 120 seconds, configurable
  - Concurrent requests: Handled by multiple workers (default: 4)

## Anonymization Configuration Parameters

The anonymization endpoints support the following configuration parameters:

- **entity_types**: List of entity types to detect and anonymize
  - Default: Basic types like `PERSON`, `DATE_TIME`, `LOCATION`, `PHONE_NUMBER`, `EMAIL_ADDRESS`, `US_SSN`, `MEDICAL_LICENSE`
  - AI4Privacy model supports 54 PII types - leave empty to detect all
  - Note: US_SSN detection requires valid SSN patterns (not test patterns like 123-45-6789)
- **score_threshold**: Minimum confidence score (0.0-1.0, default: 0.5)
  - Higher values reduce false positives but may miss some entities
  - Recommended range: 0.5-0.7
- **anonymize_all_strings**: Anonymize all string fields (true) or only known PII fields (false) (default: true)
- **date_shift_days**: Maximum days to shift dates for anonymization (default: 365)
- **return_decision_process**: Include debugging information about detection reasoning (default: false) - Note: Not currently supported with LLM-Guard

## Planned Features
- **Forensic Document Pattern Detection**:
  - Bates number recognition (e.g., "ABC-123456")
  - Case number patterns (e.g., "2024-CR-00156")
  - Medical record numbers (e.g., "MRN: 12345678")
- **Custom Regex Pattern Support**: Allow users to define domain-specific entity patterns
- **Multi-language Support**: Currently English-only, planning to add other languages
- **Batch Processing**: Anonymize multiple documents in a single request

## Example Workflow

Here's a complete workflow showing how to process a sensitive PDF document:

### 1. Extract PDF Content with Element IDs

```bash
# Extract structured data from PDF
curl -X POST http://localhost:8000/extract \
  -F "file=@confidential_document.pdf" \
  -F "batch_size=1500" \
  -F "include_element_ids=true" \
  > extracted_result.json
```

### 2. Filter and Segment for LLM Processing

```bash
# Prepare document for LLM with optimized token usage
curl -X POST http://localhost:8000/segment-filtered \
  -H "Content-Type: application/json" \
  -d '{
    "source_file": "confidential_document.pdf",
    "analysis_result": '$(cat extracted_result.json | jq .analysis_result)',
    "filter_config": {
      "filter_preset": "llm_ready",
      "include_element_ids": true
    },
    "min_segment_tokens": 10000,
    "max_segment_tokens": 30000
  }' \
  > segmented_result.json
```

### 3. Anonymize Sensitive Content (Optional)

```bash
# Remove PII before sending to LLM
curl -X POST http://localhost:8000/anonymization/anonymize-azure-di \
  -H "Content-Type: application/json" \
  -d '{
    "azure_di_json": '$(cat extracted_result.json | jq .analysis_result)',
    "config": {
      "entity_types": ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "US_SSN"],
      "score_threshold": 0.6,
      "anonymize_all_strings": true
    }
  }' \
  > anonymized_result.json
```

### 4. Compose Prompt for LLM

```bash
# Create structured prompt with instructions
curl -X POST http://localhost:8000/compose-prompt \
  -F 'mapping={"instructions":"Summarize the key findings","document":"@segmented_result.json"}' \
  -F "document=@segmented_result.json" \
  > final_prompt.txt
```

## Error Handling

### Common Errors and Solutions

- **413 Request Entity Too Large**

  - Solution: Reduce the `batch_size` parameter in `/extract`
  - Default file size limit can be increased in server configuration

- **Azure DI Timeout (504 Gateway Timeout)**

  - Large PDFs may exceed Azure's processing time
  - Solution: Use smaller batch sizes (e.g., 500-1000 pages)

- **Memory Errors**

  - For documents with many tables or complex layouts
  - Solution: Process in smaller segments or increase server memory

- **AI4Privacy Model Loading Errors**

  - LLM-Guard will download the AI4Privacy model on first use
  - Solution: Ensure internet connectivity for model download (~134MB)

- **Invalid Azure Credentials**
  - Check your `.env` file configuration
  - Verify endpoint URL includes `https://` and trailing `/`

### Debugging Tips

1. Enable debug logging: Set `LOG_LEVEL=DEBUG` in `.env`
2. Check element IDs for tracking issues through the pipeline
3. Use `/anonymization/health` to verify service status
4. Test with smaller documents first

## Security Considerations

### Data Protection

- **Use HTTPS in Production**: Always deploy with TLS/SSL certificates
- **Secure Credentials**:
  - Store Azure keys in environment variables, never in code
  - Use Azure Key Vault or similar for production deployments
  - Rotate API keys regularly

### Anonymization Best Practices

- **One-Way Anonymization**: Mappings are not stored by default (future deanonymization support planned)
- **Review Output**: Always verify anonymized content before sharing
- **Session Isolation**: Each anonymization request uses isolated replacement mappings
- **Score Threshold**: Adjust based on your security requirements (higher = fewer false positives)

### Network Security

- **API Authentication**: Consider adding authentication middleware for production
- **Network Isolation**: Deploy in a private network for sensitive documents
- **Rate Limiting**: Implement to prevent abuse
- **CORS Configuration**: Restrict to trusted domains only

### Compliance Notes

- Azure Document Intelligence is HIPAA compliant with proper configuration
- Anonymization helps meet GDPR/CCPA requirements
- Audit logs should be implemented for forensic use cases
- Consider data residency requirements for your jurisdiction

---
