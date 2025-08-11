# REST API Reference (Legacy)

> **Note**: The REST API is considered legacy. Use MCP tools through Claude Desktop when possible.

## Base URL

```
http://localhost:8000
```

## Authentication

No authentication required for local use.

## Endpoints

### POST /anonymize

Anonymize markdown text with consistent PII replacement.

**Request:**
```json
{
  "content": "Your markdown text with PII",
  "config": {
    "entity_types": ["PERSON", "EMAIL_ADDRESS"],
    "pattern_sets": ["legal", "medical"],
    "score_threshold": 0.6
  },
  "vault_data": null  // Optional: previous vault for consistency
}
```

**Response:**
```json
{
  "anonymized_content": "Anonymized markdown text",
  "statistics": {
    "PERSON": 5,
    "EMAIL_ADDRESS": 3
  },
  "vault_data": {
    "version": "2.0",
    "mappings": [["fake_name", "real_name"], ...]
  }
}
```

### POST /extract

Extract PDF to markdown using Azure Document Intelligence.

**Request:**
- Content-Type: `multipart/form-data`
- Fields:
  - `file`: PDF file
  - `batch_size`: Pages per batch (default: 1500)

**Response:**
- Content-Type: `text/plain`
- Body: Markdown content

### POST /extract-local  

Extract documents locally using Docling (no external APIs).

**Request:**
- Content-Type: `multipart/form-data`
- Fields:
  - `file`: Document file (PDF, DOCX, etc.)
  - `ocr_enabled`: Enable OCR (default: true)

**Response:**
```json
{
  "markdown_content": "Extracted markdown",
  "metadata": {
    "page_count": 10,
    "processing_type": "docling",
    "ocr_applied": false
  }
}
```

### GET /health

Check service health.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:00:00Z"
}
```

### GET /anonymization/health

Check anonymization service health.

**Response:**
```json
{
  "status": "healthy",
  "service": "anonymization",
  "engines_initialized": true,
  "model": "Isotonic/distilbert_finetuned_ai4privacy_v2"
}
```

## Error Responses

All endpoints return errors in this format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

Common HTTP status codes:
- `400`: Bad Request - Invalid input
- `404`: Not Found - Resource not found
- `500`: Internal Server Error - Processing failed

## Rate Limits

No rate limits for local deployment.

## CORS

CORS is enabled for all origins in development mode.

---

For production deployments, consider:
- Adding authentication
- Implementing rate limiting
- Restricting CORS origins
- Using HTTPS
- Adding request logging