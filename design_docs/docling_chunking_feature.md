# Docling Chunking Feature Design Document

## Overview

This document outlines the design for adding intelligent document chunking capabilities to the `/extract-local` endpoint using Docling's chunking features. The goal is to provide users with semantically meaningful text chunks suitable for downstream processing in RAG pipelines, vector databases, and LLM applications.

### Key Benefits

1. **Semantic Chunking**: Respects document structure (headings, paragraphs, tables)
2. **Token-Based Control**: Precise control over chunk sizes for LLM context windows
3. **Rich Metadata**: Preserves document structure, page numbers, and bounding boxes
4. **Contextualized Output**: Includes section hierarchy for better semantic understanding

## Technical Specification

### API Changes

#### Request Parameters

The `/extract-local` endpoint will accept additional optional parameters:

```python
@router.post("/extract-local")
async def extract_local(
    file: UploadFile = File(...),
    ocr_enabled: bool = Form(True),
    ocr_lang: str = Form("en"),
    max_pages: Optional[int] = Form(None),
    # New chunking parameters
    enable_chunking: bool = Form(False),
    chunk_min_tokens: int = Form(1000),
    chunk_max_tokens: int = Form(30000),
    merge_peers: bool = Form(True),
):
```

**Parameter Descriptions:**
- `enable_chunking`: Enable document chunking (default: False for backward compatibility)
- `chunk_min_tokens`: Minimum tokens per chunk (default: 1000)
- `chunk_max_tokens`: Maximum tokens per chunk (default: 30000)
- `merge_peers`: Merge sibling elements when possible (default: True)

### Response Format

When chunking is enabled, the response will include an additional `chunks` field:

```json
{
  "markdown_content": "Full document in markdown format...",
  "json_content": {
    // Original Docling document structure
  },
  "chunks": [
    {
      "text": "Section 1 > Subsection 1.1\n\nThe actual chunk content with context...",
      "token_count": 1250,
      "meta": {
        "doc_items": [
          {
            "self_ref": "#/texts/28",
            "label": "text",
            "prov": [{
              "page_no": 2,
              "bbox": {
                "l": 53.29,
                "t": 287.14,
                "r": 295.56,
                "b": 212.37
              }
            }]
          }
        ],
        "headings": ["Section 1", "Subsection 1.1"],
        "origin": {
          "filename": "document.pdf"
        }
      }
    }
    // ... more chunks
  ],
  "metadata": {
    "page_count": 10,
    "processing_type": "docling",
    "processing_time": 2.5,
    "file_size": 1048576,
    "filename": "document.pdf",
    "ocr_applied": false,
    "ocr_enabled": true,
    "ocr_platform": "ocrmac",
    // New chunking metadata
    "chunk_count": 15,
    "chunking_enabled": true,
    "chunk_config": {
      "min_tokens": 1000,
      "max_tokens": 30000,
      "tokenizer": "tiktoken-cl100k_base",
      "merge_peers": true
    }
  }
}
```

### Chunk Structure

Each chunk contains:

1. **`text`**: Contextualized text including section hierarchy
2. **`token_count`**: Number of tokens in the contextualized text
3. **`meta`**: Rich metadata including:
   - `doc_items`: References to source elements with labels and provenance
   - `headings`: Hierarchical section path
   - `origin`: Source document information

## Implementation Details

### Dependencies

Add the following dependency using uv:

```bash
uv add 'docling-core[chunking-openai]'
```

This will install:
- `docling-core` with OpenAI tokenizer support
- `tiktoken` for token counting
- Required chunking components

### Code Architecture

```python
# Import required components
import tiktoken
from docling_core.transforms.chunker.tokenizer.openai import OpenAITokenizer
from docling.chunking import HybridChunker

# Inside extract_local function, after document conversion:
if enable_chunking:
    # Initialize tokenizer with GPT-4's encoding
    tokenizer = OpenAITokenizer(
        tokenizer=tiktoken.get_encoding("cl100k_base"),
        max_tokens=chunk_max_tokens
    )
    
    # Create chunker with configuration
    chunker = HybridChunker(
        tokenizer=tokenizer,
        merge_peers=merge_peers
    )
    
    # Process chunks
    chunks = []
    for chunk in chunker.chunk(result.document):
        # Get contextualized text (includes headings)
        contextualized_text = chunker.contextualize(chunk)
        
        chunks.append({
            "text": contextualized_text,
            "token_count": tokenizer.count_tokens(contextualized_text),
            "meta": chunk.meta.export_json_dict()
        })
    
    # Add to response
    response_data["chunks"] = chunks
    response_data["metadata"]["chunk_count"] = len(chunks)
    response_data["metadata"]["chunking_enabled"] = True
    response_data["metadata"]["chunk_config"] = {
        "min_tokens": chunk_min_tokens,
        "max_tokens": chunk_max_tokens,
        "tokenizer": "tiktoken-cl100k_base",
        "merge_peers": merge_peers
    }
```

### Tokenizer Choice

We use tiktoken with `cl100k_base` encoding because:
1. **GPT-4 Compatible**: Same tokenizer used by GPT-4 models
2. **Accurate Counting**: Ensures chunks fit within model context windows
3. **Performance**: Fast and efficient token counting
4. **Wide Support**: Compatible with OpenAI and many other LLM providers

### Chunking Algorithm

The HybridChunker uses the following approach:
1. **Structural Analysis**: Identifies document elements (headings, paragraphs, tables)
2. **Token Budgeting**: Groups elements while respecting min/max token limits
3. **Boundary Detection**: Prefers breaking at structural boundaries (headings)
4. **Peer Merging**: Optionally combines sibling elements of the same type
5. **Contextualization**: Prepends section hierarchy to each chunk

## Performance Considerations

### Processing Time

- **Overhead**: Chunking adds ~10-20% to processing time
- **Scalability**: Linear with document size
- **Optimization**: Tokenizer is cached after first use

### Memory Usage

- **Incremental**: Chunks are processed as a generator
- **Peak Memory**: Proportional to largest chunk (max 30k tokens)
- **Metadata**: Minimal overhead for storing chunk metadata

### Recommended Limits

- **Default Range**: 1000-30000 tokens balances context and coherence
- **Small Documents**: May produce single chunk if under minimum
- **Large Documents**: Efficiently handles 100+ page documents

## Testing Strategy

### Unit Tests

1. **Basic Chunking**
   ```python
   def test_chunking_enabled():
       # Test that chunking produces expected number of chunks
       # Verify chunk structure and metadata
   ```

2. **Token Limits**
   ```python
   def test_chunk_token_limits():
       # Verify chunks respect min/max token counts
       # Test edge cases (very small/large documents)
   ```

3. **Metadata Preservation**
   ```python
   def test_chunk_metadata():
       # Verify all metadata fields are present
       # Test provenance information accuracy
   ```

### Integration Tests

1. **End-to-End Processing**
   - Test with various document types (PDF, DOCX, etc.)
   - Verify backward compatibility when chunking disabled
   - Test OCR + chunking combination

2. **Performance Benchmarks**
   - Measure processing time with/without chunking
   - Monitor memory usage patterns
   - Test with documents of various sizes

### Test Documents

Use existing test PDFs:
- `CDC-VIS-covid-19.pdf`: Multi-page with sections
- `IRS-Form-1099.pdf`: Structured form data
- `Wolke-Lereya-2015-Long-term-effects-of-bullying.pdf`: Academic paper
- `Stoker-Dracula.pdf`: Long narrative text

## Migration Plan

### Phase 1: Feature Introduction (Current)
- Add chunking as opt-in feature (`enable_chunking=False` by default)
- No breaking changes to existing API
- Document feature in API documentation

### Phase 2: Adoption Monitoring
- Track usage of chunking feature
- Gather feedback on token limits and parameters
- Optimize based on real-world usage

### Phase 3: Future Considerations
- Consider making chunking default for new clients
- Add preset configurations (e.g., "rag_optimized", "summary_optimized")
- Support for custom tokenizers

## Error Handling

### Graceful Degradation
- If chunking fails, return unchunked document with warning
- Log chunking errors for debugging
- Include error details in metadata

### Edge Cases
1. **Empty Documents**: Return empty chunks array
2. **Single Element**: May produce single chunk if document is small
3. **Tokenizer Errors**: Fall back to character-based estimation

## Future Enhancements

### Short Term
1. **Chunk Overlap**: Add optional overlap between chunks
2. **Custom Separators**: Allow custom section separators
3. **Filtering**: Pre-filter elements before chunking

### Medium Term
1. **Smart Chunking**: ML-based semantic boundaries
2. **Multi-Modal**: Support for image/table references
3. **Compression**: Optimize chunk text for token efficiency

### Long Term
1. **Streaming**: Stream chunks as they're generated
2. **Caching**: Cache chunks for repeated requests
3. **Analytics**: Track chunk usage patterns

## Security Considerations

1. **Token Limits**: Enforce maximum bounds to prevent DoS
2. **Memory Limits**: Monitor memory usage during chunking
3. **Input Validation**: Validate chunk parameters

## Conclusion

This design provides a robust, backward-compatible approach to adding intelligent chunking to the Docling extraction endpoint. The implementation prioritizes:

- **Flexibility**: Configurable parameters for different use cases
- **Quality**: Semantic chunking with rich metadata
- **Performance**: Efficient processing with minimal overhead
- **Compatibility**: No breaking changes to existing clients

The feature positions the API as a comprehensive solution for document processing in RAG and LLM applications.