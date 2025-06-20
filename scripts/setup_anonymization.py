#!/usr/bin/env python3
"""
Setup script for anonymization dependencies.
Downloads required models for Presidio with privacy-focused BERT.
"""

import subprocess
import sys

def main():
    print("Setting up anonymization dependencies...")
    
    # Note about spaCy model
    print("\n📝 Note: We're using a specialized BERT model (Isotonic/distilbert_finetuned_ai4privacy_v2)")
    print("   instead of spaCy for better PII detection accuracy.")
    print("   spaCy is only needed for basic tokenization if BERT fails to load.")
    
    # Optional: Download minimal spaCy model as fallback
    print("\nDownloading minimal spaCy model as fallback (en_core_web_sm)...")
    try:
        subprocess.check_call([
            sys.executable, "-m", "spacy", "download", "en_core_web_sm"
        ])
        print("✅ spaCy fallback model downloaded successfully")
    except subprocess.CalledProcessError as e:
        print(f"⚠️  Failed to download spaCy model: {e}")
        print("   This is optional - the BERT model will be used for PII detection")
    
    # Pre-download the privacy-focused BERT model
    print("\nPre-downloading privacy-focused BERT model...")
    print("Model: Isotonic/distilbert_finetuned_ai4privacy_v2")
    try:
        from transformers import AutoTokenizer, AutoModelForTokenClassification
        
        model_name = "Isotonic/distilbert_finetuned_ai4privacy_v2"
        print(f"Downloading tokenizer from {model_name}...")
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        
        print(f"Downloading model from {model_name}...")
        model = AutoModelForTokenClassification.from_pretrained(model_name)
        
        print("✅ Privacy-focused BERT model downloaded successfully!")
        print(f"   Model size: ~250MB (smaller than generic BERT)")
        
    except ImportError:
        print("❌ transformers library not installed. Install with:")
        print("   pip install transformers torch")
    except Exception as e:
        print(f"⚠️  Failed to download BERT model: {e}")
        print("   The model will be downloaded on first use")
    
    print("\n✨ Setup complete!")
    print("\nThe anonymization endpoint will use:")
    print("  • Primary: Isotonic/distilbert_finetuned_ai4privacy_v2 (specialized for PII)")
    print("  • Fallback: Pattern-based recognition with custom forensic patterns")
    print("  • Tokenization: spaCy en_core_web_sm (if needed)")

if __name__ == "__main__":
    main()