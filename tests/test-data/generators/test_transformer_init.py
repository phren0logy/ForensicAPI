#!/usr/bin/env python3
"""Test transformers NLP engine initialization."""

import sys
sys.path.insert(0, '/Users/andy/Documents/GitHub/forensic-desktop/backend')

try:
    from presidio_analyzer.nlp_engine import TransformersNlpEngine
    
    print("Creating TransformersNlpEngine...")
    engine = TransformersNlpEngine(
        models=[{
            "lang_code": "en",
            "model_name": {
                "transformers": "Isotonic/distilbert_finetuned_ai4privacy_v2",
                "model_kwargs": {
                    "max_length": 512,
                    "aggregation_strategy": "simple"
                }
            }
        }]
    )
    
    print("Loading engine...")
    engine.load()
    
    print("✅ TransformersNlpEngine loaded successfully")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()