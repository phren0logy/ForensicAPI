# Anonymization Endpoint Improvements

## Overview

This document outlines the planned improvements to the anonymization endpoints to address issues with false positives, date formatting, spacing, and overall accuracy.

## Current Issues

1. **Over-detection of Names**: Common words like "Meeting Notes", "Project Phoenix", "Overview" are being incorrectly detected as PERSON entities
2. **Poor Date Formatting**: Dates are replaced with `[DATE_SHIFTED_314d]` instead of realistic dates
3. **Spacing Issues**: Anonymized text has missing spaces between replacements
4. **Excessive False Positives**: Too many non-PII elements are being detected and anonymized

## Root Causes

1. **Custom Pattern Recognizers**: The custom regex patterns for name detection are too broad:
   ```python
   Pattern(regex=r"\b([A-Z][a-z]+\s+){1,3}[A-Z][a-z]+\b", score=0.85)
   ```
   This matches any sequence of capitalized words, including headings and proper nouns that aren't names.

2. **Low Score Threshold**: The default Presidio score threshold is too low (0.0-0.2), accepting many low-confidence detections

3. **Date Handling**: Current implementation doesn't parse or format dates properly

4. **Operator Configuration**: Using one operator config per entity type instead of per detection causes spacing issues

## Implementation Plan

### Phase 1: Remove Custom Recognizers

**Changes:**
1. Delete the `get_custom_recognizers()` function entirely
2. Remove the following code from `initialize_engines()`:
   ```python
   # Remove this block:
   for recognizer in get_custom_recognizers():
       analyzer_engine.registry.add_recognizer(recognizer)
   ```

**Rationale:**
- The BERT model (Isotonic/distilbert_finetuned_ai4privacy_v2) is already trained on PII detection
- Custom patterns are causing false positives
- Presidio's built-in recognizers + BERT model are sufficient

### Phase 2: Add Score Threshold Configuration

**Changes:**
1. Add to `AnonymizationConfig`:
   ```python
   score_threshold: float = Field(
       default=0.5, 
       ge=0.0, 
       le=1.0, 
       description="Minimum confidence score for entity detection (0.0-1.0)"
   )
   ```

2. Update `anonymize_text_field()` to use the threshold:
   ```python
   results = analyzer.analyze(
       text=text, 
       language="en", 
       entities=entity_types, 
       score_threshold=score_threshold
   )
   ```

**Rationale:**
- Presidio documentation recommends 0.5-0.7 for reducing false positives
- This is a built-in Presidio feature designed for this purpose
- Allows users to adjust sensitivity as needed

### Phase 3: Improve Date Anonymization

**Changes:**
1. Add imports:
   ```python
   from dateutil import parser as date_parser
   from datetime import datetime, timedelta
   ```

2. Enhance `get_consistent_replacement()` for DATE_TIME:
   ```python
   elif entity_type == "DATE_TIME":
       # Parse the original date
       try:
           parsed_date = date_parser.parse(original_value)
           
           # Get or create consistent shift for this session
           if "date_shift_days" not in replacement_mappings:
               replacement_mappings["date_shift_days"] = random.randint(-date_shift_days, date_shift_days)
           
           shift = replacement_mappings["date_shift_days"]
           shifted_date = parsed_date + timedelta(days=shift)
           
           # Format based on original format hints
           if len(original_value) <= 10:  # Likely just a date
               replacement = shifted_date.strftime("%B %d, %Y")
           else:  # Date and time
               replacement = shifted_date.strftime("%B %d, %Y at %I:%M %p")
       except:
           # Fallback for unparseable dates
           replacement = fake.date_this_year().strftime("%B %d, %Y")
   ```

**Rationale:**
- Provides realistic, readable dates
- Maintains temporal relationships with consistent shifting
- Follows Presidio's custom operator pattern

### Phase 4: Fix Spacing Issue

**Problem:** Current code creates one operator config per entity TYPE, causing all entities of that type to use the same replacement.

**Solution:**
1. Create individual operator configs for each detection:
   ```python
   # Instead of creating operators dict by type, create for each result
   for i, result in enumerate(filtered_results):
       entity_type = result.entity_type
       original_text = text[result.start:result.end]
       
       if use_consistent:
           replacement = get_consistent_replacement(
               entity_type, original_text, date_shift_days
           )
       else:
           # Generate unique replacement for each detection
           replacement = generate_replacement(entity_type)
       
       # Store replacement for this specific result
       result.replacement = replacement
   ```

2. Use the anonymizer with individual replacements

**Rationale:**
- Preserves original spacing between words
- Each detection gets proper handling

### Phase 5: Add Optional Decision Process

**Changes:**
1. Add to `AnonymizationConfig`:
   ```python
   return_decision_process: bool = Field(
       default=False, 
       description="Include detailed detection reasoning in response"
   )
   ```

2. Update `anonymize_text_field()`:
   ```python
   results = analyzer.analyze(
       text=text, 
       language="en", 
       entities=entity_types, 
       score_threshold=score_threshold,
       return_decision_process=return_decision_process
   )
   ```

3. Include decision process in response when requested

**Rationale:**
- Helps debug false positives
- Built-in Presidio feature
- Optional to avoid overhead when not needed

### Phase 6: Refactor Function Signatures

**Changes:**
1. Update `anonymize_text_field()` signature:
   ```python
   def anonymize_text_field(
       text: str, 
       analyzer: AnalyzerEngine, 
       anonymizer: AnonymizerEngine, 
       config: AnonymizationConfig
   ) -> tuple[str, Dict[str, int], Optional[Dict]]:
   ```

2. Update all callers to pass config object instead of individual parameters

**Rationale:**
- Cleaner API
- Easier to add new configuration options
- Ensures all endpoints benefit from improvements

## Testing Strategy

1. **Unit Tests**: Update existing tests to verify:
   - No false positives on common headings
   - Proper date formatting
   - Correct spacing preservation
   - Score threshold filtering

2. **Integration Tests**: Test with various document types:
   - Markdown documents
   - Azure DI JSON
   - Mixed content with real and fake PII

3. **Performance Tests**: Ensure changes don't significantly impact performance

## Breaking Changes & Migration Guide

### API Changes

1. **Function Signature Change**:
   - Old: `anonymize_text_field(text, analyzer, anonymizer, entity_types, use_consistent, date_shift_days, use_bert)`
   - New: `anonymize_text_field(text, analyzer, anonymizer, config)`
   - Callers must pass a config object instead of individual parameters

2. **Removed Features**:
   - Custom pattern recognizers (BATES_NUMBER, CASE_NUMBER, MEDICAL_RECORD_NUMBER) - use BERT model detection only
   - `use_bert` parameter - BERT is now always used
   - Individual parameter passing - must use config object

3. **Changed Defaults**:
   - Score threshold now defaults to 0.5 (was effectively 0.0)
   - This will detect fewer false positives but may miss some edge cases

### Code to Remove

1. **Delete entire `get_custom_recognizers()` function** (lines 121-189)
2. **Delete `ENTITY_TYPE_MAPPING` constant** (lines 74-118) - no longer needed without custom recognizers
3. **Remove custom entity types from default config**:
   - Remove: BATES_NUMBER, CASE_NUMBER, MEDICAL_RECORD_NUMBER
   - Keep only Presidio built-in types
4. **Remove pattern-based fallback in `initialize_engines()`**
5. **Remove `use_bert` parameter throughout** - BERT is now mandatory

### Update Required for Callers

Any code calling the anonymization endpoints must:
1. Remove BATES_NUMBER, CASE_NUMBER from entity_types lists
2. Expect different date formats in output (realistic dates vs [DATE_SHIFTED_X])
3. Adjust for potentially fewer detections due to higher score threshold

## Future Considerations

1. **Model Alternatives**: While keeping current model, monitor for better ai4privacy models
2. **Language Support**: Current implementation is English-only
3. **Custom Entity Types**: May need to support additional PII types in future
4. **Performance Optimization**: Consider caching analyzed results for repeated text

## Implementation Order

1. Remove custom recognizers (highest impact on false positives)
2. Add score threshold configuration
3. Fix spacing issue
4. Improve date anonymization  
5. Add decision process debugging
6. Refactor function signatures

This order prioritizes the most impactful fixes first while maintaining system stability throughout the changes.