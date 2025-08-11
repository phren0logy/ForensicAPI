# ForensicAPI 2.0 Implementation Plan - MCP-First Design

## Executive Summary

ForensicAPI 2.0 transforms document processing into an MCP-first service optimized for Claude Desktop and other AI assistants. The core focus is document anonymization with reversible vault-based PII replacement. By leveraging FastMCP with FastAPI as the backend and UVX for deployment, users can install and use ForensicAPI in seconds without Python knowledge.

**Key Features:**
- Zero-config local processing with Docling
- Optional Azure DI for 10-50x faster processing
- Single "anonymize" operation (always reversible)
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
5. **Markdown**: All outputs in markdown format for LLM consumption

### What's New in 2.0

- **Removed**: Separate pseudonymize endpoint, JSON outputs, complex filtering, element IDs
- **Added**: UVX deployment, MCP tools, markdown-only output, privacy-first design
- **Changed**: "Anonymize" now always reversible (vault-based)
- **Simplified**: Four focused tools instead of many endpoints, no element tracking

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
   - **Docling**: Local PDF extraction (default)
   - **Azure DI**: Cloud PDF extraction (optional, faster)
   - **LLM-Guard**: PII detection and replacement

## MCP Tools

### Tool Design Philosophy

- Each tool has a single, clear purpose
- File paths in, file paths out (no content exposure to LLM)
- Smart defaults for all parameters
- Clear, actionable error messages
- Privacy-preserving progress updates

### 1. `anonymize_documents`

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

### 2. `restore_documents`

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

### 3. `extract_document`

**Purpose**: Convert PDF/DOCX to markdown

```typescript
interface ExtractDocumentParams {
  file_path: string;           // Input document
  output_path?: string;        // Optional output path
  extraction_method?: string;  // "local" (default) or "azure"
}
```

**Features:**
- Automatic OCR for scanned PDFs
- Preserves document structure
- Handles tables and formatting

### 4. `segment_document`

**Purpose**: Split large documents into LLM-ready chunks

```typescript
interface SegmentDocumentParams {
  file_path: string;       // Markdown file to segment
  output_dir: string;      // Directory for chunks
  max_tokens?: number;     // Tokens per chunk (default: 15000)
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

### Phase 1: Core Refactoring (Week 1-2)

1. **Simplify Anonymization**
   - Remove pseudonymize endpoint
   - Rename to single "anonymize" operation
   - Ensure vault always created
   - Remove element IDs entirely
   - Update all references

2. **Markdown-Only Output**
   - Remove JSON output options from all user-facing APIs
   - Convert all outputs to markdown
   - Simplify response structures
   - Internal JSON usage only (vault, Azure DI)
   - Update tests

3. **File Path Operations**
   - Refactor to accept paths only
   - Return output paths, not content
   - Integration with filesystem patterns

### Phase 2: MCP Integration (Week 2-3)

1. **Create MCP Server**
   ```python
   # forensicapi/mcp_server.py
   from fastmcp import FastMCP
   
   mcp = FastMCP("ForensicAPI")
   
   @mcp.tool
   async def anonymize_documents(
       files: Optional[List[str]] = None,
       directory: Optional[str] = None,
       output_dir: str,
       patterns: List[str] = ["*.pdf", "*.md", "*.txt"],
       recursive: bool = True,
       pattern_sets: List[str] = []
   ) -> DocumentsResult:
       """Anonymize documents, replacing PII with realistic fake data."""
       # Implementation
   ```

2. **Implement 4 Tools**
   - anonymize_documents
   - restore_documents
   - extract_document
   - segment_document

3. **Progress Streaming**
   - Use MCP progress callbacks
   - Real-time updates for long operations
   - Privacy-preserving status messages (no content exposure)
   - Example: "Processing page 15 of 45..." not "Found SSN 123-45-6789"

### Phase 3: Packaging & Testing (Week 3-4)

1. **UVX Configuration**
   ```toml
   # pyproject.toml
   [project]
   name = "forensicapi"
   version = "2.0.0"
   
   [project.scripts]
   forensicapi = "forensicapi.mcp_server:main"
   
   [project.urls]
   Repository = "https://github.com/your/forensicapi"
   ```

2. **Testing Suite**
   - MCP tool tests
   - Integration with Claude Desktop
   - Performance benchmarks
   - Error handling

3. **Documentation**
   - Simple README
   - Claude Desktop setup guide
   - Example workflows

## Migration Guide

### For v1.0 Users

**Breaking Changes:**
1. No more `/pseudonymize` endpoint - use `/anonymize`
2. JSON output removed - all output is markdown
3. Complex filtering removed - use simple patterns
4. File upload removed - use file paths

**Migration Steps:**
1. Update to use file paths instead of uploads
2. Replace `pseudonymize` with `anonymize` in code
3. Expect markdown output, not JSON
4. Use UVX instead of pip install

### API Compatibility (Legacy)

A minimal REST API remains for programmatic access. These endpoints are considered legacy and may be deprecated in future versions. Use MCP tools when possible.

**Endpoints:**
- `POST /anonymize` - Returns markdown report of anonymization
- `POST /restore` - Returns markdown report of restoration
- `POST /extract` - Returns extracted markdown content

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
- Output location: /Users/john/legal_anonymized/
- Vault saved: vault.json (for optional restoration)

The documents are now safe to share. To restore the originals later, just ask me to "restore the anonymized legal documents."
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
- Output: /medical/2024_anonymized/
- All medical-specific patterns were detected and replaced
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

### Anonymization Process

1. **PII Detection**: LLM-Guard with AI4Privacy model (54 PII types)
2. **Replacement Generation**: 
   - Names: Realistic fake names via Faker
   - Emails: Valid-format fake emails
   - Dates: Shifted by random days (preserved relationships)
   - SSNs: Valid-format with secure random
   - Custom patterns: Domain-specific replacements

3. **Vault Structure** (Internal Only):
   ```json
   {
     "version": "2.0",
     "created": "2024-01-15T10:00:00Z",
     "metadata": {
       "date_offset": -187,
       "total_files": 23
     },
     "mappings": [
       {
         "type": "PERSON",
         "original": "John Smith",
         "replacement": "Robert Johnson"
       }
     ]
   }
   ```
   
   Note: This JSON structure is used internally for vault storage. Users never interact with JSON directly.

### Performance Characteristics

- **Local Extraction (Docling)**: ~5-10 seconds per page
- **Azure DI Extraction**: ~0.2-1 second per page
- **Anonymization**: ~1000 words per second
- **Memory Usage**: Streaming, constant regardless of file size

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