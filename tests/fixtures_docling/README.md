# Docling Test Fixtures

This directory contains notes for optional Docling-related tests.

## Structure

- `expected_outputs/` - Optional expected outputs for comparison testing

## Adding Test Fixtures

To add new test fixtures:

1. Place the test document in this directory
2. Run docling-serve directly to generate expected output
3. Save the expected output in the `expected_outputs/` directory
4. Update the test cases in `test_extraction_docling.py` if needed

## Note

The actual test fixtures are not included in the repository to keep it lightweight.
You can generate test PDFs using the `create_test_pdf()` function in the test file
or use your own sample documents.
