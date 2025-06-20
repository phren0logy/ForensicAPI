#!/usr/bin/env python3
"""
Run segmentation tests with synthetic and anonymized data.

This script:
1. Checks if the FastAPI backend is running
2. Runs the segmentation tests
3. Generates a summary report
"""

import subprocess
import sys
import time
import requests
import json
from pathlib import Path


def check_backend_health():
    """Check if FastAPI backend is running."""
    try:
        response = requests.get("http://localhost:8000/health", timeout=2)
        return response.status_code == 200
    except:
        return False


def main():
    print("🧪 Forensic Desktop Segmentation Test Runner")
    print("=" * 50)
    
    # Check if backend is running
    print("\n1️⃣ Checking FastAPI backend...")
    if not check_backend_health():
        print("❌ Backend is not running!")
        print("   Please start it with: cd backend && uv run run.py")
        return 1
    
    print("✅ Backend is running")
    
    # Run the tests
    print("\n2️⃣ Running segmentation tests...")
    print("-" * 50)
    
    test_commands = [
        # Basic segmentation with synthetic data
        ("Basic Segmentation", [
            "pytest", "-xvs", 
            "tests/test_segmentation_with_real_data.py::TestRealDataSegmentation::test_basic_segmentation_synthetic"
        ]),
        
        # Filtered segmentation with all presets
        ("Filtered Segmentation", [
            "pytest", "-xvs",
            "tests/test_segmentation_with_real_data.py::TestRealDataSegmentation::test_filtered_segmentation_all_presets"
        ]),
        
        # Performance benchmarks
        ("Performance Benchmarks", [
            "pytest", "-xvs",
            "tests/test_segmentation_with_real_data.py::TestRealDataSegmentation::test_performance_benchmarks"
        ]),
        
        # Element ID preservation
        ("Element ID Preservation", [
            "pytest", "-xvs",
            "tests/test_segmentation_with_real_data.py::TestRealDataSegmentation::test_element_id_preservation"
        ]),
        
        # Test with anonymized data if available
        ("Anonymized Data", [
            "pytest", "-xvs",
            "tests/test_segmentation_with_real_data.py::TestRealDataSegmentation::test_anonymized_data_if_available"
        ]),
    ]
    
    results = {}
    
    for test_name, cmd in test_commands:
        print(f"\n🔍 Running: {test_name}")
        
        # Run with uv
        full_cmd = ["uv", "run"] + cmd
        
        result = subprocess.run(
            full_cmd,
            capture_output=True,
            text=True
        )
        
        success = result.returncode == 0
        results[test_name] = {
            "success": success,
            "return_code": result.returncode
        }
        
        if success:
            print(f"✅ {test_name} passed")
        else:
            print(f"❌ {test_name} failed")
            if "SKIPPED" in result.stdout:
                print("   (Test was skipped - this may be normal)")
                results[test_name]["skipped"] = True
    
    # Generate summary report
    print("\n3️⃣ Generating summary report...")
    print("-" * 50)
    
    # Try to run the summary generator
    subprocess.run(
        ["uv", "run", "pytest", "-xvs", 
         "tests/test_segmentation_with_real_data.py::test_generate_summary_report"],
        capture_output=True
    )
    
    # Print final summary
    print("\n📊 Test Summary:")
    print("-" * 50)
    
    passed = sum(1 for r in results.values() if r["success"])
    skipped = sum(1 for r in results.values() if r.get("skipped", False))
    failed = len(results) - passed
    
    print(f"✅ Passed: {passed}")
    print(f"⏭️  Skipped: {skipped}")
    print(f"❌ Failed: {failed - skipped}")
    
    # Check for test results
    results_dir = Path("tests/test_results")
    if results_dir.exists():
        print(f"\n📁 Test results saved in: {results_dir}")
        
        # List result files
        synthetic_results = list((results_dir / "synthetic").rglob("*.json")) if (results_dir / "synthetic").exists() else []
        if synthetic_results:
            print(f"\n   Synthetic test results: {len(synthetic_results)} files")
            for f in synthetic_results[:5]:  # Show first 5
                print(f"     - {f.name}")
        
        anon_results = list((results_dir / "anonymized").rglob("*.json")) if (results_dir / "anonymized").exists() else []
        if anon_results:
            print(f"\n   Anonymized test results: {len(anon_results)} files (gitignored)")
    
    # Return appropriate exit code
    return 0 if failed == skipped else 1


if __name__ == "__main__":
    sys.exit(main())