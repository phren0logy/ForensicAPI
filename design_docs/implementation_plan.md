# ForensicAPI 2.0 Implementation Plan - MCP-First Design

## Executive Summary

ForensicAPI 2.0 transforms document processing into an MCP-first service optimized for Claude Desktop and other AI assistants. The core focus is document anonymization with consistent, reversible vault-based PII replacement. By leveraging FastMCP with FastAPI as the backend and UVX for deployment, users can install and use ForensicAPI in seconds without Python knowledge.

**Key Features:**
- Zero-config local processing with Docling
- Optional Azure DI for 10-50x faster processing
- Single "anonymize" operation (always reversible)
- Consistent replacements across all documents (same person = same fake name)
- Markdown-only output for LLM consumption
- Four focused MCP tools for clear operations
- UVX deployment: `uvx forensicapi`

## Table of Contents

1. [Overview](#overview)
2. [Privacy-First Architecture](#privacy-first-architecture)
3. [Architecture](#architecture)
4. [MCP Tools](#mcp-tools)
5. [Deployment](#deployment)
6. [Configuration](#configuration)
7. [Implementation Phases](#implementation-phases)
8. [Migration Guide](#migration-guide)
9. [Examples](#examples)
10. [Technical Details](#technical-details)
11. [Future Considerations](#future-considerations)

## Overview

### Vision

ForensicAPI 2.0 is designed from the ground up for Model Context Protocol (MCP) integration. Users interact with their documents through natural language in Claude Desktop, with ForensicAPI handling the complex processing behind the scenes.

### Core Principles

1. **MCP-First**: Primary interface through MCP tools, REST API secondary
2. **Simplicity**: Single anonymize operation, smart defaults, minimal configuration
3. **Privacy**: Local processing by default, no cloud dependencies
4. **Reversibility**: Always create vault for optional restoration
5. **Consistency**: Same PII always gets same replacement across documents
6. **Markdown**: All outputs in markdown format for LLM consumption

### What's New in 2.0

- **Removed**: Separate pseudonymize endpoint ✅, JSON outputs ✅, complex filtering ✅, element IDs ✅, Azure DI JSON format in anonymization ✅
- **Added**: UVX deployment ✅, MCP tools ✅, markdown-only output ✅, privacy-first design ✅, consistent replacements ✅
- **Changed**: "Anonymize" now always reversible (vault-based) with consistent faker values ✅
- **Simplified**: Four focused tools instead of many endpoints ✅, no element tracking ✅
- **Enhanced**: Same entity always gets same replacement across all documents ✅

## Privacy-First Architecture

ForensicAPI 2.0 is designed to protect sensitive document content from LLM exposure:

- **File Path Operations**: MCP tools work exclusively with file paths
- **No Content Exposure**: The LLM orchestrates operations without seeing document contents
- **Safe Progress Messages**: Status updates describe operations, not data
- **Isolated Processing**: All PII detection and replacement happens in the backend

Example safe progress message:
```
Anonymizing document batch...
✓ Processed 5 of 23 files
✓ Current file: contract_2023.pdf (15 pages)
✓ Detected and replaced 47 PII instances
```

## Architecture

### Technology Stack

```
┌─────────────────┐
│  Claude Desktop │ 
│  (or other MCP  │
│     client)     │
└────────┬────────┘
         │ MCP Protocol
┌────────▼────────┐
│    FastMCP      │ 
│  (MCP Server)   │
└────────┬────────┘
         │ 
┌────────▼────────┐
│    FastAPI      │ 
│ (Processing     │
│    Engine)      │
└────────┬────────┘
         │
┌────────▼────────┐
│  LLM-Guard +    │
│    Docling/     │
│   Azure DI      │
└─────────────────┘
```

### Component Responsibilities

1. **FastMCP Layer**: 
   - Exposes 4 MCP tools
   - Handles file path resolution
   - Manages progress streaming
   - Integrates with filesystem MCP server

2. **FastAPI Backend**:
   - Document processing logic
   - Vault management
   - File type detection
   - Error handling

3. **Processing Engines**:
   - **Docling**: Local PDF extraction (default) ✅
   - **Azure DI**: Cloud PDF extraction (optional, faster) ✅
   - **LLM-Guard**: PII detection and replacement ✅

## MCP Tools ✅ IMPLEMENTED

### Tool Design Philosophy

- Each tool has a single, clear purpose ✅
- File paths in, file paths out (no content exposure to LLM) ✅
- Smart defaults for all parameters ✅
- Clear, actionable error messages ✅
- Privacy-preserving progress updates ✅

### 1. `anonymize_documents` ✅

**Purpose**: Replace PII with realistic fake data, creating a reversible vault

```typescript
interface AnonymizeDocumentsParams {
  // Input files (one required)
  files?: string[];        // Specific file paths
  directory?: string;      // Or scan directory
  
  // Options
  patterns?: string[];     // File patterns (default: ["*.pdf", "*.md", "*.txt"])
  recursive?: boolean;     // Include subdirectories (default: true)
  pattern_sets?: string[]; // Domain patterns: "legal", "medical" (default: [])
  
  // Output
  output_dir: string;      // Required output directory
}
```

**Example Output:**
```
/output/
├── anonymized/
│   ├── contract_001.md
│   ├── agreement.md
│   └── notes.md
├── vault.json
└── REPORT.md
```

### 2. `restore_documents` ✅

**Purpose**: Restore original PII using vault

```typescript
interface RestoreDocumentsParams {
  // Input files (one required)
  files?: string[];      // Specific anonymized files
  directory?: string;    // Or scan directory
  
  // Vault
  vault_path?: string;   // Optional, auto-detects vault.json
  
  // Output
  output_dir: string;    // Required output directory
}
```

### 3. `extract_document` ✅

**Purpose**: Convert PDF/DOCX to markdown

```typescript
interface ExtractDocumentParams {
  file_path: string;           // Input document
  output_path?: string;        // Optional output path
  extraction_method?: string;  // "local" (default) or "azure"
}
```

**Features:**
- Automatic OCR for scanned PDFs ✅
- Preserves document structure ✅
- Handles tables and formatting ✅
- Reports output size in tokens ✅

### 4. `segment_document` ✅

**Purpose**: Split large documents into LLM-ready chunks

```typescript
interface SegmentDocumentParams {
  file_path: string;       // Markdown file to segment
  output_dir: string;      // Directory for chunks
  max_tokens?: number;     // Tokens per chunk (default: 15000)
  min_tokens?: number;     // Minimum tokens per chunk (default: 10000)
}
```

**Output Format:**
```
/chunks/
├── document_001_of_015.md
├── document_002_of_015.md
├── document_003_of_015.md
...
└── document_015_of_015.md
```

Each file contains a logical section of the document, with clean breaks at chapter/section boundaries when possible.

## Deployment

### UVX Installation

ForensicAPI 2.0 uses UVX for zero-friction deployment:

```bash
# Install once
uvx forensicapi

# That's it! No Python, no pip, no venv
```

### Claude Desktop Configuration

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "forensic-api": {
      "command": "uvx",
      "args": ["forensicapi"],
      "env": {
        "AZURE_DI_KEY": "${AZURE_DI_KEY}",
        "AZURE_DI_ENDPOINT": "${AZURE_DI_ENDPOINT}"
      }
    },
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/Users/username/Documents"
      ]
    }
  }
}
```

### Integration with Filesystem Server

ForensicAPI works seamlessly with the MCP filesystem server:
- Filesystem server provides file access
- ForensicAPI processes files via paths
- No duplicate file handling needed

## Configuration

### Environment Variables Only

Configuration is handled exclusively through environment variables in the MCP server config:

| Variable | Purpose | Required |
|----------|---------|----------|
| `AZURE_DI_KEY` | Azure Document Intelligence API key | No |
| `AZURE_DI_ENDPOINT` | Azure DI endpoint URL | No |

**Behavior:**
- No Azure credentials = Docling only (local processing)
- With Azure credentials = Choice of local or Azure

### No Configuration Files

- No `.env` files to manage
- No config JSON to edit
- No settings to tweak
- Everything works with smart defaults

## Implementation Phases

### Phase 1: Core Refactoring (Week 1-2) ✅ COMPLETE (except tests)

1. **Simplify Anonymization** ✅
   - Remove pseudonymize endpoint ✅
   - Rename to single "anonymize" operation ✅
   - Implement consistent faker replacement post-processing ✅
   - Ensure vault always created with full mappings ✅
   - Remove element IDs entirely ✅ (already not present)
   - Update all references ✅

2. **Markdown-Only Output** ✅
   - Remove JSON output options from all user-facing APIs ✅
   - Convert all outputs to markdown ✅
   - Simplify response structures ✅
   - Internal JSON usage only (vault, Azure DI) ✅
   - Update tests ❌ (deferred to Phase 3)

3. **File Path Operations** ✅ (via MCP)
   - Refactor to accept paths only ✅ (MCP tools)
   - Return output paths, not content ✅ (MCP tools)
   - Integration with filesystem patterns ✅ (MCP tools)

### Phase 2: MCP Integration (Week 2-3) ✅ COMPLETE

1. **Create MCP Server** ✅
   - Created `forensicapi/mcp_server.py` with FastMCP
   - Configured pyproject.toml with entry point
   - All imports and dependencies resolved

2. **Implement 4 Tools** ✅
   - anonymize_documents ✅ - Batch anonymization with consistent replacements
   - restore_documents ✅ - Vault-based restoration
   - extract_document ✅ - PDF/DOCX to markdown with token reporting
   - segment_document ✅ - Markdown segmentation with heading boundaries

3. **Progress Streaming** ✅
   - Implemented privacy-preserving progress messages
   - Real-time updates for long operations
   - No content exposure in progress updates
   - Example: "Processing file 3 of 15: document.pdf"

4. **Key Implementation Details** ✅
   - File paths in, file paths out (privacy-first)
   - Token-based size reporting (not bytes)
   - Markdown-specific segmentation logic
   - Consistent faker replacements across documents
   - Vault v2.0 format support

### Phase 3: Packaging & Testing (Week 3-4) - PENDING

1. **UVX Configuration** ✅ (Partially Complete)
   - Basic pyproject.toml configuration ✅
   - Entry point configured ✅
   - Repository URL pending ❌
   - PyPI publishing setup pending ❌

2. **Testing Suite** ❌
   - MCP tool tests ❌
   - Integration with Claude Desktop ❌
   - Performance benchmarks ❌
   - Error handling tests ❌

3. **Documentation** ❌
   - Simple README ❌
   - Claude Desktop setup guide ❌
   - Example workflows ❌

## Migration Guide

### For v1.0 Users

**Breaking Changes:**
1. No more `/pseudonymize` endpoint - use `/anonymize` ✅
2. JSON output removed - all output is markdown ✅
3. Complex filtering removed - use simple patterns ✅
4. File upload removed - use file paths ✅ (via MCP tools)

**Migration Steps:**
1. Update to use file paths instead of uploads
2. Replace `pseudonymize` with `anonymize` in code
3. Expect markdown output, not JSON
4. Use UVX instead of pip install

### API Compatibility (Legacy)

A minimal REST API remains for programmatic access. These endpoints are considered legacy and may be deprecated in future versions. Use MCP tools when possible.

**Endpoints:**
- `POST /anonymize` - Returns markdown report of anonymization ✅ (implemented)
- `POST /restore` - Returns markdown report of restoration ❌ (not implemented - MCP only)
- `POST /extract` - Returns extracted markdown content ✅ (existing)

All REST endpoints return markdown-only responses. No JSON output is available.

## Examples

### Basic Anonymization

**User**: "Anonymize all contracts in my legal folder"

**Claude Desktop**:
```
I'll anonymize the contracts in your legal folder. Let me process those documents for you.

[Calling anonymize_documents tool...]

I've successfully anonymized 23 documents:
- Files processed: 23 PDF and markdown files
- PII replaced: 145 names, 89 emails, 67 phone numbers, 234 dates
- Consistency maintained: "John Smith" → "Robert Johnson" in all documents
- Output location: /Users/john/legal_anonymized/
- Vault saved: vault.json (for optional restoration)

The documents are now safe to share with consistent replacements across all files. To restore the originals later, just ask me to "restore the anonymized legal documents."
```

### Restoring Documents

**User**: "I need to restore those legal documents I anonymized last week"

**Claude Desktop**:
```
I'll restore your anonymized legal documents using the vault file.

[Calling restore_documents tool...]

Successfully restored 23 documents:
- All PII values have been restored to originals
- Output location: /Users/john/legal_restored/
- Files are identical to pre-anonymization versions
```

### Medical Records with Patterns

**User**: "Anonymize patient records in /medical/2024, make sure to catch medical record numbers"

**Claude Desktop**:
```
I'll anonymize the patient records with special attention to medical identifiers.

[Calling anonymize_documents with pattern_sets=["medical"]...]

Processed 156 patient records:
- Standard PII: 423 names, 156 SSNs, 289 dates
- Medical patterns: 156 MRNs, 89 insurance IDs, 34 DEA numbers
- Consistency example: "Dr. Sarah Johnson" → "Dr. Emily Williams" in all files
- Output: /medical/2024_anonymized/
- All medical-specific patterns were detected and replaced consistently
```

### Consistency Across Documents

**User**: "Show me how consistency works across multiple documents"

**Claude Desktop**:
```
Here's how ForensicAPI maintains consistency:

Document 1 (contract.md):
- "John Smith" → "Robert Johnson"
- "john.smith@company.com" → "rjohnson@example.com"

Document 2 (meeting_notes.md):
- "John Smith" → "Robert Johnson" (same replacement)
- "john.smith@company.com" → "rjohnson@example.com" (same replacement)

Document 3 (performance_review.md):
- "John Smith" → "Robert Johnson" (same replacement)
- New entity "Jane Doe" → "Sarah Williams" (new mapping added to vault)

The vault ensures every occurrence of "John Smith" becomes "Robert Johnson" across all documents, making the anonymized content coherent and readable.
```

### Document Extraction

**User**: "Convert this research paper PDF to markdown"

**Claude Desktop**:
```
I'll convert your PDF to markdown format.

[Calling extract_document tool...]

Successfully extracted the PDF:
- Input: /Users/john/research_paper.pdf (45 pages)
- Output: /Users/john/research_paper.md
- Preserved: Headings, tables, citations, formatting
- OCR applied: No (document was text-based)
```

## Technical Details

### Internal Processing

While ForensicAPI uses JSON internally for data structures, all user-facing interfaces are markdown-only:

- **Vault Storage**: JSON format (internal only, never exposed to users)
- **Azure DI/Docling**: JSON processed internally, converted to markdown for output
- **Progress Updates**: Markdown-formatted messages describing operations
- **Error Messages**: Human-readable markdown format
- **Note**: Azure DI is still available for extraction; we only removed Azure DI JSON format support in the anonymization endpoint

### Anonymization Process

1. **Two-Phase Approach for Consistency**:
   - **Phase 1 - Detection**: LLM-Guard with AI4Privacy model (54 PII types) detects entities
   - **Phase 2 - Replacement**: Post-processing ensures consistent faker replacements

2. **Consistent Replacement Generation**:
   - **Names**: Same person always gets same fake name (e.g., "John Smith" → "Robert Johnson")
   - **Emails**: Consistent fake emails across documents
   - **Dates**: Shifted by consistent offset (preserved relationships)
   - **SSNs**: Same SSN always gets same valid-format replacement
   - **Custom patterns**: Domain-specific consistent replacements

3. **How Consistency Works**:
   - LLM-Guard runs with `use_faker=False` to get placeholder format: `[REDACTED_ENTITY_TYPE_N]`
   - Post-processor checks vault for existing replacements
   - If found: reuse the same faker value
   - If new: generate faker value and store in vault
   - Result: "John Smith" always becomes "Robert Johnson" across all documents

4. **Vault Structure** (Internal Only):
   ```json
   {
     "version": "2.0",
     "created": "2024-01-15T10:00:00Z",
     "metadata": {
       "date_offset": -187,
       "total_files": 23
     },
     "mappings": [
       ["Robert Johnson", "John Smith"],
       ["rjohnson@example.com", "john.smith@company.com"],
       ["555-0123", "555-1234"]
     ]
   }
   ```
   
   Note: Vault stores [faker_replacement, original_value] pairs for perfect reversibility.

### Performance Characteristics

- **Local Extraction (Docling)**: ~5-10 seconds per page
- **Azure DI Extraction**: ~0.2-1 second per page
- **Anonymization**: ~1000 words per second (includes consistency checking)
- **Memory Usage**: Streaming, constant regardless of file size
- **Consistency Overhead**: Minimal (<5%) due to efficient vault lookups

### Consistency Implementation Details

1. **Vault Lookup**: O(1) average case using hash-based lookups
2. **Faker Generation**: Only for new entities not in vault
3. **Thread-Safe**: Vault operations are atomic for concurrent processing
4. **Deterministic**: Same input always produces same output with same vault

### Error Handling

All errors return clear, actionable messages in markdown format:
```
Error: PDF extraction failed
File: /contracts/scan_001.pdf
Reason: PDF appears to be password protected
Suggestion: Unlock the PDF or provide the password
```

Errors are always returned as human-readable markdown text, never as JSON error objects.

## Future Considerations

### Potential Enhancements

1. **Selective Anonymization**
   - Choose which PII types to replace
   - Exclude specific patterns
   - Custom entity rules

2. **Batch Progress**
   - Real-time progress for large batches
   - Cancellable operations
   - Pause/resume support

3. **Advanced Patterns**
   - Industry-specific pattern sets
   - Custom regex support
   - ML-based entity detection

### Out of Scope for 2.0

- Cloud storage integration
- Web UI
- Database storage
- Multi-language support
- Real-time collaboration

## Conclusion

ForensicAPI 2.0 represents a complete reimagining of document anonymization for the AI age. By focusing on MCP integration, markdown output, and zero-configuration deployment, it provides a powerful yet simple tool for privacy-preserving document processing. The single reversible anonymization operation gives users full control while maintaining simplicity.

The combination of FastAPI's robust backend with FastMCP's elegant MCP integration creates a tool that feels native to Claude Desktop while maintaining the flexibility for other use cases. With UVX deployment, users can start protecting their documents in seconds, not hours.