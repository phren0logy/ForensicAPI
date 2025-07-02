#!/usr/bin/env python3
"""
Add element IDs to existing test fixtures.

This script loads existing Azure DI fixture files and adds unique _id fields
to all elements using the same logic as the /extract endpoint.
"""

import json
import os
import sys
from pathlib import Path

# Add parent directory to path to import from routes
sys.path.insert(0, str(Path(__file__).parent.parent))

from routes.extraction import add_ids_to_elements


def process_fixture_file(input_path: str, output_path: str) -> dict:
    """
    Process a single fixture file to add element IDs.
    
    Args:
        input_path: Path to input fixture file
        output_path: Path to output fixture file with IDs
        
    Returns:
        Statistics about the processing
    """
    print(f"Processing {input_path}...")
    
    # Load the fixture
    with open(input_path, 'r') as f:
        data = json.load(f)
    
    # Add IDs to elements
    data_with_ids = add_ids_to_elements(data)
    
    # Save the result
    with open(output_path, 'w') as f:
        json.dump(data_with_ids, f, indent=2)
    
    # Count elements with IDs
    stats = {
        'paragraphs': 0,
        'tables': 0,
        'cells': 0,
        'key_value_pairs': 0,
        'lists': 0,
        'figures': 0,
        'formulas': 0
    }
    
    if 'paragraphs' in data_with_ids:
        stats['paragraphs'] = len([p for p in data_with_ids['paragraphs'] if '_id' in p])
    
    if 'tables' in data_with_ids:
        stats['tables'] = len([t for t in data_with_ids['tables'] if '_id' in t])
        for table in data_with_ids['tables']:
            if 'cells' in table:
                stats['cells'] += len([c for c in table['cells'] if '_id' in c])
    
    if 'keyValuePairs' in data_with_ids:
        stats['key_value_pairs'] = len([kv for kv in data_with_ids['keyValuePairs'] if '_id' in kv])
    
    if 'lists' in data_with_ids:
        stats['lists'] = len([l for l in data_with_ids['lists'] if '_id' in l])
    
    if 'figures' in data_with_ids:
        stats['figures'] = len([f for f in data_with_ids['figures'] if '_id' in f])
    
    if 'formulas' in data_with_ids:
        stats['formulas'] = len([f for f in data_with_ids['formulas'] if '_id' in f])
    
    print(f"  Added IDs to: {stats}")
    
    return stats


def validate_id_uniqueness(fixture_dir: str, pattern: str = "*_with_ids.json"):
    """
    Validate that all IDs are unique across the processed fixtures.
    
    Args:
        fixture_dir: Directory containing fixture files
        pattern: Glob pattern for files to check
    """
    print(f"\nValidating ID uniqueness in {fixture_dir}...")
    
    all_ids = set()
    duplicate_ids = set()
    
    for filepath in Path(fixture_dir).glob(pattern):
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        # Collect all IDs
        if 'paragraphs' in data:
            for para in data['paragraphs']:
                if '_id' in para:
                    if para['_id'] in all_ids:
                        duplicate_ids.add(para['_id'])
                    all_ids.add(para['_id'])
        
        if 'tables' in data:
            for table in data['tables']:
                if '_id' in table:
                    if table['_id'] in all_ids:
                        duplicate_ids.add(table['_id'])
                    all_ids.add(table['_id'])
                
                if 'cells' in table:
                    for cell in table['cells']:
                        if '_id' in cell:
                            if cell['_id'] in all_ids:
                                duplicate_ids.add(cell['_id'])
                            all_ids.add(cell['_id'])
        
        # Check other element types
        for key in ['keyValuePairs', 'lists', 'figures', 'formulas']:
            if key in data:
                for elem in data[key]:
                    if '_id' in elem:
                        if elem['_id'] in all_ids:
                            duplicate_ids.add(elem['_id'])
                        all_ids.add(elem['_id'])
    
    print(f"  Total unique IDs: {len(all_ids)}")
    
    if duplicate_ids:
        print(f"  WARNING: Found {len(duplicate_ids)} duplicate IDs:")
        for dup_id in sorted(duplicate_ids)[:10]:  # Show first 10
            print(f"    - {dup_id}")
        if len(duplicate_ids) > 10:
            print(f"    ... and {len(duplicate_ids) - 10} more")
    else:
        print("  ✓ All IDs are unique")


def main():
    """Process all existing fixtures to add element IDs."""
    fixtures_dir = Path(__file__).parent.parent / "tests" / "fixtures"
    
    if not fixtures_dir.exists():
        print(f"Error: Fixtures directory not found: {fixtures_dir}")
        return 1
    
    # List of fixture files to process
    fixture_files = [
        "batch_1-50.json",
        "batch_51-100.json",
        "batch_101-150.json",
        "batch_151-200.json",
        "batch_201-250.json",
        "batch_251-300.json",
        "batch_301-350.json",
        "batch_351-353.json",
        "ground_truth_result.json"
    ]
    
    total_stats = {
        'files_processed': 0,
        'total_paragraphs': 0,
        'total_tables': 0,
        'total_cells': 0,
        'total_key_value_pairs': 0,
        'total_lists': 0,
        'total_figures': 0,
        'total_formulas': 0
    }
    
    print(f"Adding element IDs to fixtures in {fixtures_dir}")
    print("=" * 60)
    
    for filename in fixture_files:
        input_path = fixtures_dir / filename
        
        if not input_path.exists():
            print(f"Warning: File not found: {input_path}")
            continue
        
        # Create output filename with _with_ids suffix
        name_parts = filename.rsplit('.', 1)
        output_filename = f"{name_parts[0]}_with_ids.{name_parts[1]}"
        output_path = fixtures_dir / output_filename
        
        # Process the file
        stats = process_fixture_file(str(input_path), str(output_path))
        
        # Update totals
        total_stats['files_processed'] += 1
        total_stats['total_paragraphs'] += stats['paragraphs']
        total_stats['total_tables'] += stats['tables']
        total_stats['total_cells'] += stats['cells']
        total_stats['total_key_value_pairs'] += stats['key_value_pairs']
        total_stats['total_lists'] += stats['lists']
        total_stats['total_figures'] += stats['figures']
        total_stats['total_formulas'] += stats['formulas']
    
    print("=" * 60)
    print("Summary:")
    print(f"  Files processed: {total_stats['files_processed']}")
    print(f"  Total elements with IDs added:")
    print(f"    - Paragraphs: {total_stats['total_paragraphs']}")
    print(f"    - Tables: {total_stats['total_tables']}")
    print(f"    - Table cells: {total_stats['total_cells']}")
    print(f"    - Key-value pairs: {total_stats['total_key_value_pairs']}")
    print(f"    - Lists: {total_stats['total_lists']}")
    print(f"    - Figures: {total_stats['total_figures']}")
    print(f"    - Formulas: {total_stats['total_formulas']}")
    
    # Validate uniqueness
    validate_id_uniqueness(str(fixtures_dir))
    
    print("\nDone! New fixtures with IDs have been created.")
    return 0


if __name__ == "__main__":
    sys.exit(main())