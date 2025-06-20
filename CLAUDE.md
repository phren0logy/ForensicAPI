# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Recent Updates (2025-06-20)

### Element ID System
- IDs are now generated in the extraction phase (`/extract` endpoint) by default
- Format: `{element_type}_{page}_{index}_{hash}` (e.g., `para_1_0_a3f2b1`)
- IDs are preserved through filtering and segmentation
- The `include_element_ids` parameter (default: true) controls ID generation

## Project Overview

FastAPI-based document processing API focused on handling large PDF documents using Azure Document Intelligence. The project implements a sophisticated 2-phase processing pipeline for perfect document reconstruction and intelligent segmentation.

## Key Architecture

### Technology Stack
- **Framework**: FastAPI with Uvicorn (Python 3.13+)
- **Key Services**: Azure Document Intelligence, Presidio (PII anonymization), BERT models
- **Package Manager**: uv (modern Python package management)

### Core Processing Pipeline
1. **Phase 1 - Extract**: Batch processing of PDFs with perfect stitching algorithm
   - Handles 350+ page documents with 100% accuracy
   - Concurrent batch processing with configurable batch sizes
   - Located in `routes/extract.py`

2. **Phase 2 - Segment**: Creates rich document segments for LLM consumption
   - Configurable token thresholds (10k-30k tokens)
   - Intelligent boundary detection at heading levels
   - Located in `routes/segment.py`

### API Endpoints
- `/` - Root endpoint
- `/compose-prompt` - XML-tagged prompt composition
- `/extract` - PDF to structured data extraction (now with element IDs)
- `/segment` - Document segmentation with token control
- `/segment-filtered` - Combined filtering and segmentation for LLM processing
- `/anonymization/anonymize-azure-di` - PII detection and anonymization
- `/health` - Health check endpoint

## Development Commands

### Running the Application
```bash
# Recommended: Use 4 workers for concurrent requests
uv run run.py

# Alternative: Single worker with auto-reload for development
uvicorn main:app --reload
```

### Testing
```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_basic.py

# Run with verbose output and stop on first failure
uv run pytest -xvs
```

### Dependency Management
```bash
# Install/sync dependencies
uv sync

# Add new dependency
uv add package-name

# Add development dependency
uv add --dev package-name
```

### Key Scripts
```bash
# Generate test fixtures from Azure DI
uv run python scripts/generate_test_fixtures.py

# Setup anonymization models
uv run python scripts/setup_anonymization.py

# Quick testing
uv run python tests/quick_test.py
```

### Built-in Test Pages
When server is running:
- PDF Test: http://127.0.0.1:8000/pdf-test
- Prompt Test: http://127.0.0.1:8000/prompt-test

## Important Implementation Details

### Batch Processing Strategy
The `/extract` endpoint implements sophisticated batch processing:
- Default batch size: 1500 pages
- Handles document offsets automatically
- Uses "perfect stitching" algorithm to reconstruct documents
- Test fixtures in `tests/fixtures/` demonstrate the complete pipeline

### Token Management
The `/segment` endpoint creates optimal chunks for LLMs:
- Default: 10k-30k tokens per segment
- Breaks at structural boundaries (H1/H2 headings)
- Preserves full Azure DI metadata including bounding boxes

### Testing Philosophy
- Uses real 353-page PDF test documents
- Comprehensive fixtures from actual Azure DI responses
- Performance benchmarking with memory profiling
- Test data includes synthetic examples for edge cases

### Environment Configuration
- Uses `.env` file for Azure credentials and configuration
- No Docker setup - direct Python execution model
- Custom `run.py` configures multi-worker uvicorn for production performance

## Code Patterns

### Route Organization
Each endpoint is a separate module under `routes/`:
- Self-contained with request/response models
- Uses Pydantic for validation
- Includes HTML test templates where applicable

### Error Handling
- Comprehensive input validation
- Detailed error messages for debugging
- Graceful handling of large documents

### Performance Considerations
- Sub-second execution for most operations
- Minimal memory usage through streaming
- Concurrent batch processing for large PDFs