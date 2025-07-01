from presidio_analyzer import AnalyzerEngine

analyzer = AnalyzerEngine(supported_languages=["en"])

test_texts = [
    "123-45-6789",
    "SSN: 123-45-6789",
    "My SSN is 123-45-6789",
    "social security number: 123-45-6789",
    "SSN 123456789",
    "123456789"
]

for text in test_texts:
    results = analyzer.analyze(text=text, language="en", entities=["US_SSN"])
    if results:
        print(f"✅ Detected in '{text}': {results[0]}")
    else:
        print(f"❌ NOT detected in '{text}'")
