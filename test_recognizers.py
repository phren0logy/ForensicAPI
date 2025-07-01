from presidio_analyzer import AnalyzerEngine

analyzer = AnalyzerEngine(supported_languages=["en"])
recognizers = analyzer.registry.recognizers

print("Loaded recognizers:")
for recognizer in recognizers:
    print(f"- {recognizer.__class__.__name__}: {recognizer.supported_entities}")
