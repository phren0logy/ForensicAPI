from presidio_analyzer import AnalyzerEngine

analyzer = AnalyzerEngine(supported_languages=["en"])

# Test with various SSN formats
# SSNs starting with 000, 666, or 900-999 are invalid
# Also area numbers 734-749 are unassigned
test_texts = [
    "My SSN is 111-22-3333",  # Valid format
    "SSN: 222-33-4444",       # Valid format
    "social security 333-44-5555",  # Valid format
    "123-45-6789",            # This specific number might be invalid
    "001-23-4567",            # Starting with 001 is valid
    "078-05-1120",            # This is Woolworth Wallet SSN (famous invalid)
]

for text in test_texts:
    results = analyzer.analyze(text=text, language="en", entities=["US_SSN"])
    if results:
        print(f"✅ Detected in '{text}': {results[0]}")
    else:
        print(f"❌ NOT detected in '{text}'")
