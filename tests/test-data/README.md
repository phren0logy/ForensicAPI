# Test Data for Forensic Desktop Application

This directory contains anonymized test data derived from real Azure Document Intelligence (Azure DI) extraction outputs. All PII has been removed using the anonymization endpoint.

## Directory Structure

```
test-data/
├── synthetic/              # Synthetic test data (SAFE TO COMMIT)
│   ├── medical_chart_multi_visit.json
│   ├── legal_case_file.json
│   ├── government_form.json
│   └── edge_case_damaged.json
├── azure-di-json/          # Anonymized real data (GITIGNORED)
│   └── (your anonymized files here)
├── generators/             # Scripts for generating test data
│   ├── generate_synthetic_test_data.py
│   ├── test_with_synthetic.py
│   └── test_anonymization.py
├── anonymization-config.yaml
└── README.md
```

## Important: Data Safety

- **✅ SAFE TO COMMIT**: Files in `synthetic/` contain fake PII and are safe
- **❌ DO NOT COMMIT**: Files in `azure-di-json/` may contain patterns from real documents
- The `.gitignore` is configured to exclude `azure-di-json/*.json` while allowing `synthetic/*.json`

## Using the Anonymization Script

### Prerequisites

1. Ensure the backend is running with Presidio dependencies installed:

   ```bash
   cd backend
   uv sync  # Installs all dependencies including Presidio
   uv run run.py
   ```

2. For BERT-based NER (optional but recommended), the first run will download the Isotonic/distilbert_finetuned_ai4privacy_v2 model (~250MB). This model is specifically fine-tuned for PII detection.

### Testing Workflow

1. **Test with synthetic data first** (recommended):

   ```bash
   cd test-data/generators
   python test_with_synthetic.py
   ```

   This validates the endpoint works correctly with known test cases.

2. **Generate synthetic test data** (if needed):

   ```bash
   python generate_synthetic_test_data.py
   ```

3. **Anonymize real Azure DI JSON**:

   ```bash
   python test_anonymization.py /path/to/real/azure-di.json
   ```

   Output goes to `test-data/azure-di-json/` (gitignored)

4. **Anonymize with custom output path**:
   ```bash
   python test_anonymization.py input.json output_anonymized.json
   ```

## Anonymization Features

The anonymization endpoint detects and replaces:

### Standard PII

- **Names**: Replaced with realistic fake names
- **Dates**: Shifted by random amount (preserving relative timing)
- **SSNs**: Replaced with valid-format fake SSNs
- **Phone Numbers**: Replaced with fake phone numbers
- **Email Addresses**: Replaced with fake emails
- **Locations**: Replaced with fake city names

### Forensic Document Patterns

- **Bates Numbers**: e.g., `BATES-001234` → `ANON-789456`
- **Case Numbers**: e.g., `2024-CR-12345` → `2025-CR-67890`
- **Medical Record Numbers**: e.g., `MRN12345678` → `MRN87654321`
- **Medical License Numbers**: e.g., `MD987654` → `MD123456`

### Consistency Features

- Same name always gets same replacement throughout document
- Azure DI structure fully preserved
- Element IDs and relationships maintained
- Page numbers and positions unchanged

## Configuration Options

Edit the config in `test_anonymization.py`:

```python
"config": {
    "preserve_structure": True,          # Keep Azure DI structure
    "entity_types": [...],              # Which PII types to detect
    "date_shift_days": 365,             # Max days to shift dates
    "consistent_replacements": True,     # Same value → same replacement
    "use_bert_ner": True                # Use BERT for better accuracy
}
```

## Performance Notes

- **Pattern-based only**: Fast, ~1-2 seconds per document
- **With BERT NER**: More accurate, ~5-10 seconds per document
- **First BERT run**: Downloads Isotonic/distilbert_finetuned_ai4privacy_v2 model (~250MB), one-time ~1-2 minutes
- **Model advantage**: This model is specifically trained on privacy datasets and performs better than generic NER models for PII detection

## Security Notes

- Never commit real (non-anonymized) Azure DI JSON to the repository
- Always verify anonymization before committing test files
- The anonymization is one-way (no deanonymization support)
- Mappings are not stored (each run generates new fake data)
