# Docling Test Fixtures

This directory contains test fixtures generated using the Docling local extraction endpoint.

## Files

- `*_docling.json` - Full Docling response including document structure
- `*_markdown.md` - Extracted markdown content for easy reading

## Key Differences from Azure DI

1. **Format**: Docling uses a different JSON structure with elements organized by page
2. **Element IDs**: Docling doesn't currently generate element IDs
3. **Filtering**: The /extract-local endpoint doesn't support filtering
4. **OCR**: Uses ocrmac on macOS, EasyOCR on other platforms

## Statistics

### IRS-Form-1099.pdf
- Pages: 3
- OCR applied: True

### CDC-VIS-covid-19.pdf
- Pages: 2
- OCR applied: True

### Wolke-Lereya-2015-Long-term-effects-of-bullying.pdf
- Pages: 7
- OCR applied: True

### Stoker-Dracula.pdf
- Pages: 353
- OCR applied: True

