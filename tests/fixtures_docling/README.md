# Docling Test Fixtures

This directory contains test fixtures for the Docling extraction tests.

## Structure

- `sample.pdf` - Basic test PDF with text content
- `sample.docx` - Basic test DOCX document
- `scanned_document.pdf` - PDF with scanned content requiring OCR
- `mixed_content.pdf` - PDF with both text and scanned content
- `expected_outputs/` - Expected outputs for comparison testing

## Adding Test Fixtures

To add new test fixtures:

1. Place the test document in this directory
2. Run the extract-local endpoint manually to generate expected output
3. Save the expected output in the `expected_outputs/` directory
4. Update the test cases in `test_extraction_docling.py`

## Note

The actual test fixtures are not included in the repository to keep it lightweight.
You can generate test PDFs using the `create_test_pdf()` function in the test file
or use your own sample documents.
