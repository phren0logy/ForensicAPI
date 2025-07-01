# LLM-Guard Migration Summary

## What Changed

### Dependencies
- **Removed**: presidio-analyzer, presidio-anonymizer, spacy, spacy-huggingface-pipelines
- **Added**: llm-guard>=0.3.16
- **Kept**: faker, python-dateutil (for custom date shifting)

### Core Implementation
- **Before**: Direct Presidio with spaCy NER (7 PII types)
- **After**: LLM-Guard with AI4Privacy BERT model (54 PII types, 97.8% F1 score)

### Key Features Preserved
1. **Date Shifting**: Custom post-processor maintains temporal relationships
2. **Session Isolation**: New Vault instance per request
3. **Azure DI Structure**: Recursive JSON processing unchanged
4. **API Compatibility**: Same endpoints, request/response formats

### New Capabilities
- 54 PII types vs 7 (including financial, medical, technical entities)
- Better accuracy with specialized AI4Privacy model
- Built-in support for deanonymization (future feature)
- Cleaner codebase with less configuration

## Testing the Changes

1. **Restart the server**: The old server process needs to be restarted to load LLM-Guard
   ```bash
   uv run run.py
   ```

2. **Test health endpoint**:
   ```bash
   curl http://localhost:8000/anonymization/health
   ```
   Should show: `"model": "Isotonic/distilbert_finetuned_ai4privacy_v2"`

3. **Run integration tests**:
   ```bash
   uv run pytest tests/test_llm_guard_integration.py
   ```

## What to Expect

### First Request
- Model download: ~134MB on first use (one-time)
- Initialization: 3-5 seconds
- Subsequent requests: Similar performance to Presidio

### Detection Improvements
The AI4Privacy model detects many more entity types:
- Personal: Names, ages, gender, occupations
- Financial: Credit cards, bank accounts, financial amounts
- Medical: Diagnoses, medications, conditions
- Technical: IP addresses, API keys, crypto wallets
- Legal: Case numbers, court names

### Date Handling
- LLM-Guard generates random dates by default
- Our post-processor applies consistent shifts to maintain temporal relationships
- All dates in a session shift by the same amount

## Future Enhancements

1. **Deanonymization**: Leverage vault for reversible anonymization with encrypted keys
2. **Custom Patterns**: Add domain-specific regex patterns
3. **Multi-language**: Enable Chinese support (already in LLM-Guard)
4. **Performance**: ONNX optimization for production