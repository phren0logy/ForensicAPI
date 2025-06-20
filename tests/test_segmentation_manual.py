#!/usr/bin/env python3
"""
Manual test of segmentation endpoints without pytest.
Run this to quickly test the segmentation functionality.
"""

import json
import requests
import time
from pathlib import Path
from typing import Dict, Any


def load_test_file(filename: str) -> Dict[str, Any]:
    """Load a test JSON file."""
    test_data_dir = Path(__file__).parent / "test-data"
    
    # Try synthetic first
    synthetic_path = test_data_dir / "synthetic" / filename
    if synthetic_path.exists():
        with open(synthetic_path, 'r') as f:
            return json.load(f)
    
    # Try anonymized
    anon_path = test_data_dir / "azure-di-json" / "anonymized" / filename  
    if anon_path.exists():
        with open(anon_path, 'r') as f:
            return json.load(f)
    
    raise FileNotFoundError(f"Test file not found: {filename}")


def test_basic_segmentation():
    """Test basic segmentation endpoint."""
    print("\n📄 Testing Basic Segmentation")
    print("-" * 40)
    
    # Load a synthetic test file
    try:
        azure_di_json = load_test_file("medical_chart_multi_visit.json")
        print("✅ Loaded test file: medical_chart_multi_visit.json")
    except FileNotFoundError as e:
        print(f"❌ {e}")
        return False
    
    # Prepare request
    payload = {
        "source_file": "medical_chart_multi_visit.pdf",
        "analysis_result": azure_di_json,
        "min_segment_tokens": 2000,
        "max_segment_tokens": 6000
    }
    
    # Send request
    print("📤 Sending request to /segment...")
    start_time = time.time()
    
    try:
        response = requests.post(
            "http://localhost:8000/segment",
            json=payload,
            timeout=30
        )
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            # Handle both dict with 'segments' key and direct list response
            if isinstance(data, list):
                segments = data
            else:
                segments = data.get("segments", [])
            
            print(f"✅ Success! Got {len(segments)} segments in {elapsed:.2f}s")
            
            # Show segment summary
            total_tokens = sum(seg.get("token_count", 0) for seg in segments)
            print(f"📊 Total tokens: {total_tokens:,}")
            
            # Show first segment preview
            if segments:
                first_seg = segments[0]
                print(f"\n🔍 First segment preview:")
                print(f"   - ID: {first_seg.get('segment_id')}")
                print(f"   - Tokens: {first_seg.get('token_count')}")
                print(f"   - Elements: {len(first_seg.get('elements', []))}")
                
            return True
            
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"   {response.text[:200]}...")
            return False
            
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return False


def test_filtered_segmentation():
    """Test filtered segmentation with different presets."""
    print("\n📄 Testing Filtered Segmentation")
    print("-" * 40)
    
    # Load test file
    try:
        azure_di_json = load_test_file("legal_case_file.json")
        print("✅ Loaded test file: legal_case_file.json")
    except FileNotFoundError as e:
        print(f"❌ {e}")
        return False
    
    # Test each preset
    presets = ["no_filter", "llm_ready", "forensic_extraction", "citation_optimized"]
    results = {}
    
    for preset in presets:
        print(f"\n🔧 Testing preset: {preset}")
        
        payload = {
            "source_file": "legal_case_file.pdf",
            "analysis_result": azure_di_json,
            "filter_config": {
                "filter_preset": preset,
                "include_element_ids": True
            },
            "min_segment_tokens": 2000,
            "max_segment_tokens": 6000
        }
        
        start_time = time.time()
        
        try:
            response = requests.post(
                "http://localhost:8000/segment-filtered",
                json=payload,
                timeout=30
            )
            elapsed = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                metrics = data.get("metrics", {})
                segments = data.get("segments", [])
                
                results[preset] = {
                    "reduction": metrics.get("reduction_percentage", 0),
                    "segments": len(segments),
                    "time": elapsed
                }
                
                print(f"   ✅ Reduction: {metrics.get('reduction_percentage', 0):.1f}%")
                print(f"   📊 Segments: {len(segments)}")
                print(f"   ⏱️  Time: {elapsed:.2f}s")
                
            else:
                print(f"   ❌ Error: {response.status_code}")
                results[preset] = {"error": response.status_code}
                
        except Exception as e:
            print(f"   ❌ Failed: {e}")
            results[preset] = {"error": str(e)}
    
    # Compare results
    print("\n📊 Preset Comparison:")
    print("-" * 40)
    for preset, result in results.items():
        if "error" not in result:
            print(f"{preset:20} → {result['reduction']:6.1f}% reduction, {result['segments']} segments")
    
    return all("error" not in r for r in results.values())


def test_anonymized_if_available():
    """Test with anonymized data if available."""
    print("\n📄 Testing with Anonymized Data")
    print("-" * 40)
    
    # Check for anonymized files
    anon_dir = Path(__file__).parent / "test-data" / "azure-di-json" / "anonymized"
    if not anon_dir.exists():
        print("⏭️  No anonymized data directory found (this is normal)")
        return True
    
    anon_files = list(anon_dir.glob("*.json"))
    if not anon_files:
        print("⏭️  No anonymized files found (this is normal)")
        return True
    
    print(f"🔒 Found {len(anon_files)} anonymized file(s)")
    
    # Test first anonymized file
    test_file = anon_files[0]
    print(f"📁 Testing: {test_file.name}")
    
    with open(test_file, 'r') as f:
        azure_di_json = json.load(f)
    
    payload = {
        "source_file": test_file.name,
        "analysis_result": azure_di_json,
        "filter_config": {
            "filter_preset": "llm_ready",
            "include_element_ids": True
        },
        "min_segment_tokens": 3000,
        "max_segment_tokens": 8000
    }
    
    try:
        response = requests.post(
            "http://localhost:8000/segment-filtered",
            json=payload,
            timeout=60  # Longer timeout for potentially large files
        )
        
        if response.status_code == 200:
            data = response.json()
            segments = data.get("segments", [])
            metrics = data.get("metrics", {})
            
            print(f"✅ Success!")
            print(f"   📊 Segments: {len(segments)}")
            print(f"   🔽 Reduction: {metrics.get('reduction_percentage', 0):.1f}%")
            
            # Count pages
            pages = set()
            for seg in segments:
                for elem in seg.get("elements", []):
                    if "pageNumber" in elem:
                        pages.add(elem["pageNumber"])
            
            print(f"   📄 Pages: {len(pages)}")
            
            return True
        else:
            print(f"❌ Error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False


def main():
    """Run all manual tests."""
    print("🧪 Manual Segmentation Test")
    print("=" * 50)
    
    # Check backend
    print("\n🔍 Checking backend...")
    try:
        response = requests.get("http://localhost:8000/health", timeout=2)
        if response.status_code != 200:
            print("❌ Backend is not healthy!")
            return
    except:
        print("❌ Cannot connect to backend at http://localhost:8000")
        print("   Please start it with: cd backend && uv run run.py")
        return
    
    print("✅ Backend is running")
    
    # Run tests
    tests = [
        ("Basic Segmentation", test_basic_segmentation),
        ("Filtered Segmentation", test_filtered_segmentation),
        ("Anonymized Data", test_anonymized_if_available),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"Running: {test_name}")
        print('='*50)
        
        success = test_func()
        results.append((test_name, success))
    
    # Summary
    print("\n" + "="*50)
    print("📊 SUMMARY")
    print("="*50)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name:30} {status}")
    
    passed = sum(1 for _, success in results if success)
    print(f"\nTotal: {passed}/{len(tests)} passed")


if __name__ == "__main__":
    main()