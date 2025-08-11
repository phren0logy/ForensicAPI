# ForensicAPI

**Privacy-first document processing for AI assistants**

ForensicAPI anonymizes sensitive documents before they reach your AI, ensuring consistent replacements across all files. Install in seconds with UVX, no Python knowledge required.

## Quick Start

### 1. Install ForensicAPI

```bash
uvx forensicapi
```

That's it! No Python, pip, or virtual environments needed.

### 2. Configure Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "forensic-api": {
      "command": "uvx",
      "args": ["forensicapi"]
    }
  }
}
```

### 3. Start Using

In Claude Desktop:

- "Anonymize all PDFs in my contracts folder"
- "Extract this research paper to markdown"
- "Split this 500-page document into chunks"

## Core Features

### 🔒 Privacy-First Anonymization

ForensicAPI replaces sensitive information with realistic fake data **before** your AI sees it:

- **Consistent replacements**: "John Smith" → "Robert Johnson" in ALL documents
- **54 PII types detected**: Names, SSNs, emails, medical records, financial data
- **Reversible**: Restore originals anytime using the secure vault
- **Domain patterns**: Legal (case numbers, Bates) and medical (MRNs, insurance IDs)

### 📄 Document Processing

- **Universal format support**: PDF, DOCX, PPTX, HTML, Markdown
- **Local or cloud**:
  - Docling (default): Private, no external APIs
  - Azure DI (optional): 10-50x faster for large documents
- **Intelligent chunking**: Split documents for optimal LLM processing
- **No size limits**: Handle 1000+ page documents effortlessly

### 🤖 MCP-First Design

ForensicAPI works through natural language in Claude Desktop:

```
You: "I have sensitive contracts that need review"
Claude: "I'll help anonymize those contracts first to protect sensitive information..."
[ForensicAPI processes files without Claude seeing the content]
Claude: "I've anonymized 23 contracts. All names, emails, and financial data have been
consistently replaced. John Smith appears as Robert Johnson in all documents."
```

## MCP Tools

### `anonymize_documents`

Replace PII with consistent fake data across multiple documents.

```typescript
// Anonymize specific files
anonymize_documents({
  files: ["/path/to/contract.pdf", "/path/to/notes.md"],
  output_dir: "/secure/output",
});

// Anonymize entire directory
anonymize_documents({
  directory: "/contracts/2024",
  patterns: ["*.pdf", "*.docx"],
  pattern_sets: ["legal"], // Enable legal patterns
  output_dir: "/contracts/anonymized",
});
```

**Output:**

- `/output/anonymized/` - Anonymized documents
- `/output/vault.json` - Secure mapping for restoration
- `/output/REPORT.md` - Processing summary

### `restore_documents`

Restore original PII using the vault.

```typescript
restore_documents({
  directory: "/contracts/anonymized",
  vault_path: "/contracts/vault.json", // Optional, auto-detected
  output_dir: "/contracts/restored",
});
```

### `extract_document`

Convert PDFs and Office documents to markdown.

```typescript
extract_document({
  file_path: "/research/paper.pdf",
  extraction_method: "local", // or "azure" for faster processing
});
```

### `segment_document`

Split large documents into LLM-ready chunks.

```typescript
segment_document({
  file_path: "/research/paper.md",
  output_dir: "/research/chunks",
  max_tokens: 15000, // Optimal for GPT-4
});
```

## Configuration

### Minimal Setup (Local Processing)

No configuration needed! ForensicAPI works out of the box with local processing.

### Enable Azure Document Intelligence (Optional)

For 10-50x faster PDF processing, add Azure credentials to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "forensic-api": {
      "command": "uvx",
      "args": ["forensicapi"],
      "env": {
        "AZURE_DI_KEY": "your-key-here",
        "AZURE_DI_ENDPOINT": "https://your-resource.cognitiveservices.azure.com/"
      }
    }
  }
}
```

## Examples

### Legal Document Review

```
You: "I need to review these merger agreements for inconsistencies"

Claude: "I'll anonymize those merger agreements first to protect confidential information.

[Calling anonymize_documents tool...]

I've successfully anonymized 8 merger agreements:
- Replaced 127 company names, 89 person names, 45 financial figures
- 'Acme Corp' consistently appears as 'TechCo Industries' across all documents
- All Bates numbers and case references were detected and replaced

The documents are now ready for analysis. Would you like me to review them for
inconsistencies in terms, pricing, or obligations?"
```

### Medical Records Processing

```
You: "Process patient discharge summaries from the hospital folder"

Claude: "I'll anonymize the patient discharge summaries to ensure HIPAA compliance.

[Calling anonymize_documents with medical patterns...]

Processed 156 discharge summaries:
- Protected: 312 patient names, 156 MRNs, 423 diagnoses, 89 physician names
- Dates shifted consistently by 6 months
- Medical record numbers replaced with format-preserving alternatives

The anonymized summaries are ready for analysis while maintaining full privacy."
```

### Document Extraction and Analysis

```
You: "Extract and summarize this 300-page research PDF"

Claude: "I'll extract the PDF content and prepare it for analysis.

[Calling extract_document tool...]

Successfully extracted 300-page research document:
- Format: Clean markdown with preserved structure
- Size: 487,239 tokens
- Extraction time: 3.2 seconds (using Azure DI)

[Calling segment_document tool...]

Split into 15 logical segments (average 32,000 tokens each) breaking at chapter
boundaries. Ready to analyze specific sections or provide an overall summary."
```

## Privacy & Security

### How It Works

1. **File paths only**: Claude sees file paths, never document contents
2. **Local processing**: Your documents stay on your machine
3. **Consistent vault**: Same person gets same replacement everywhere
4. **No logs**: ForensicAPI doesn't store or log document content
5. **Reversible**: Original data recoverable only with your vault file

### Security Best Practices

- Keep vault files secure - they contain the restoration mappings
- Use local extraction for maximum privacy
- Review anonymized output before sharing externally
- Enable only the PII types you need to reduce false positives

## Troubleshooting

### "Command not found: uvx"

Install UVX first:

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### "Model download in progress"

First run downloads the AI4Privacy model (134MB). This happens once.

### Azure DI Timeout

Large PDFs may timeout. Solutions:

- Use local extraction (default)
- Process in smaller batches
- Increase timeout in Azure portal

## REST API (Legacy)

ForensicAPI includes a REST API for programmatic access. This is considered legacy - use MCP tools when possible.

- `POST /anonymize` - Anonymize documents
- `POST /extract` - Extract PDF/DOCX to markdown
- `POST /extract-local` - Local extraction with Docling
- `GET /health` - Service health check

See [API Documentation](docs/api-reference.md) for details.

## Contributing

ForensicAPI is open source! We welcome contributions.

- [GitHub Repository](https://github.com/yourusername/forensicapi)
- [Issue Tracker](https://github.com/yourusername/forensicapi/issues)
- [Implementation Plan](design_docs/implementation_plan.md)

## License

MIT License - see [LICENSE](LICENSE) file for details.

---

**Built for AI** - ForensicAPI ensures your sensitive documents stay private while enabling powerful AI analysis.
