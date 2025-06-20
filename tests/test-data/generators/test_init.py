#!/usr/bin/env python3
"""Test initialization of anonymization engines."""

import sys
sys.path.insert(0, '/Users/andy/Documents/GitHub/forensic-desktop/backend')

from routes.anonymization import initialize_engines

try:
    print("Testing pattern-based initialization...")
    analyzer, anonymizer = initialize_engines(use_bert=False)
    print("✅ Pattern-based engines initialized successfully")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

try:
    print("\nTesting BERT-based initialization...")
    analyzer, anonymizer = initialize_engines(use_bert=True)
    print("✅ BERT-based engines initialized successfully")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()