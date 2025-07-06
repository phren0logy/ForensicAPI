# Test Fixtures Documentation

This directory contains test fixtures for the FastAPI document processing API, supporting both Azure Document Intelligence and Docling (local) extraction endpoints.

## Directory Structure

```
tests/fixtures/
├── dracula/                    # Long-form narrative text (353 pages)
│   ├── batch_*.json            # Original Azure DI fixtures
│   └── batch_*_with_ids.json   # ID-enhanced versions
├── forms/                      # Tax forms with tables and fields
├── mixed/                      # Mixed content (lists, formatted text)
├── academic/                   # Academic papers (figures, references)
└── docling/                    # Docling format fixtures for all docs
```

## Fixture Generation Scripts

### 1. `scripts/add_ids_to_fixtures.py`

Adds element IDs to existing fixtures using the same logic as the `/extract` endpoint.

```bash
uv run python scripts/add_ids_to_fixtures.py
```

### 2. `scripts/generate_test_fixtures.py`

Generates Azure DI fixtures from sample PDFs with automatic ID generation.

```bash
uv run python scripts/generate_test_fixtures.py
```

### 3. `scripts/generate_docling_fixtures.py`

Generates Docling format fixtures through the `/extract-local` endpoint.

```bash
# Start the server first
uv run run.py

# In another terminal
uv run python scripts/generate_docling_fixtures.py
```

## Sample PDFs

Located in `tests/sample_pdfs/`:

1. **Stoker-Dracula.pdf** (353 pages)
   - Long-form narrative text
   - Tests batch processing and stitching
   - Source of existing fixtures

2. **IRS-Form-1099.pdf** (2 pages)
   - Tax form with tables and form fields
   - Tests table extraction and key-value pairs

3. **CDC-VIS-covid-19.pdf** (2 pages)
   - Mixed content with lists and formatting
   - Tests diverse element types

4. **Wolke-Lereya-2015-Long-term-effects-of-bullying.pdf** (11 pages)
   - Academic paper with figures and references
   - Tests complex document structure

## Element ID Format

Element IDs follow the pattern: `{element_type}_{page}_{index}_{hash}`

- `element_type`: para, table, cell, kv, list, fig, formula
- `page`: Page number where element appears
- `index`: Global index of this element type
- `hash`: 6-character hash of content for uniqueness

Example: `para_1_0_a3f2b1`

## Testing Approach

### 1. Azure DI Testing (`/extract`)

- Tests with and without element IDs (`include_element_ids` parameter)
- Validates batch processing and stitching
- Ensures ID uniqueness and preservation

### 2. Docling Testing (`/extract-local`)

- Tests local extraction without external API calls
- Validates OCR functionality
- Note: Currently doesn't support element IDs or filtering

### 3. Comparison Testing

- Compare extraction quality between Azure DI and Docling
- Validate consistent markdown output
- Test performance differences

## Key Differences: Azure DI vs Docling

| Feature          | Azure DI         | Docling                   |
| ---------------- | ---------------- | ------------------------- |
| Element IDs      | ✅ Supported     | ❌ Not yet                |
| Filtering        | ✅ Supported     | ❌ Not yet                |
| Batch Processing | ✅ Built-in      | ❌ Single file            |
| OCR              | ✅ Cloud-based   | ✅ Local (ocrmac/EasyOCR) |
| Format           | Azure DI JSON    | Docling JSON              |
| Cost             | Per-page pricing | Free (local)              |

## Running Tests

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_extraction_azure.py
uv run pytest tests/test_extraction_docling.py

# Run with specific fixtures
uv run pytest tests/test_segmentation_with_real_data.py
```

## Adding New Fixtures

1. Add PDF to `tests/sample_pdfs/`
2. Update `PDF_CONFIGS` in `generate_test_fixtures.py`
3. Run the fixture generation scripts
4. Update tests to use new fixtures

## Notes

- Fixtures are committed to the repository to avoid API costs in CI/CD
- The Dracula fixtures test the "perfect stitching" algorithm
- Smaller documents test specific element types (forms, tables, lists)
- All fixtures include both original and ID-enhanced versions
