#!/usr/bin/env python3
"""
Generate synthetic Azure DI JSON test data with realistic PII.
These files are safe to commit to the repository.
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
import random

def generate_medical_chart_json():
    """Generate synthetic medical chart with multiple visits."""
    return {
        "status": "succeeded",
        "createdDateTime": "2024-01-15T10:30:00Z",
        "content": """MEDICAL RECORD

Patient: Sarah Johnson
MRN: 98765432
Date of Birth: 03/15/1980
Phone: (555) 234-5678
Address: 123 Medical Center Dr, Boston, MA 02115

VISIT SUMMARY - January 15, 2024
Provider: Dr. Michael Chen, MD License: MD123456
Chief Complaint: Annual physical examination

VISIT SUMMARY - February 20, 2024  
Provider: Dr. Emily Rodriguez, MD License: MD789012
Chief Complaint: Follow-up visit

Patient SSN: 123-45-6789
Insurance ID: ABC123456789""",
        "pages": [
            {
                "pageNumber": 1,
                "angle": 0,
                "width": 8.5,
                "height": 11,
                "unit": "inch",
                "words": [
                    {"content": "Sarah", "boundingBox": [100, 200, 150, 220], "confidence": 0.99},
                    {"content": "Johnson", "boundingBox": [160, 200, 210, 220], "confidence": 0.99},
                    {"content": "98765432", "boundingBox": [100, 240, 180, 260], "confidence": 0.98}
                ],
                "lines": [
                    {"content": "Patient: Sarah Johnson", "boundingBox": [100, 200, 300, 220]},
                    {"content": "MRN: 98765432", "boundingBox": [100, 240, 300, 260]},
                    {"content": "SSN: 123-45-6789", "boundingBox": [100, 280, 300, 300]}
                ]
            },
            {
                "pageNumber": 2,
                "angle": 0,
                "width": 8.5,
                "height": 11,
                "unit": "inch",
                "lines": [
                    {"content": "Provider: Dr. Emily Rodriguez", "boundingBox": [100, 100, 400, 120]},
                    {"content": "MD License: MD789012", "boundingBox": [100, 140, 350, 160]}
                ]
            }
        ],
        "tables": [
            {
                "rowCount": 4,
                "columnCount": 3,
                "cells": [
                    {"rowIndex": 0, "columnIndex": 0, "content": "Visit Date", "kind": "columnHeader"},
                    {"rowIndex": 0, "columnIndex": 1, "content": "Provider", "kind": "columnHeader"},
                    {"rowIndex": 0, "columnIndex": 2, "content": "Diagnosis", "kind": "columnHeader"},
                    {"rowIndex": 1, "columnIndex": 0, "content": "01/15/2024"},
                    {"rowIndex": 1, "columnIndex": 1, "content": "Dr. Michael Chen"},
                    {"rowIndex": 1, "columnIndex": 2, "content": "Annual Physical"},
                    {"rowIndex": 2, "columnIndex": 0, "content": "02/20/2024"},
                    {"rowIndex": 2, "columnIndex": 1, "content": "Dr. Emily Rodriguez"},
                    {"rowIndex": 2, "columnIndex": 2, "content": "Follow-up"}
                ]
            }
        ],
        "keyValuePairs": [
            {"key": {"content": "Patient Name"}, "value": {"content": "Sarah Johnson"}},
            {"key": {"content": "MRN"}, "value": {"content": "98765432"}},
            {"key": {"content": "Phone"}, "value": {"content": "(555) 234-5678"}},
            {"key": {"content": "Email"}, "value": {"content": "sarah.johnson@email.com"}}
        ],
        "analyzeResult": {
            "apiVersion": "2023-07-31",
            "modelId": "prebuilt-layout",
            "stringIndexType": "textElements"
        }
    }


def generate_legal_case_file_json():
    """Generate synthetic legal case file with Bates numbers."""
    return {
        "status": "succeeded",
        "createdDateTime": "2024-03-10T14:20:00Z",
        "content": """UNITED STATES DISTRICT COURT
SOUTHERN DISTRICT OF NEW YORK

Case No: 2024-CR-54321

UNITED STATES OF AMERICA,
    Plaintiff,
v.
ROBERT WILLIAMS,
    Defendant.

MOTION FOR SUMMARY JUDGMENT

Attorney: Jennifer Martinez, Esq.
Bar Number: NY-987654
Address: 456 Court Street, New York, NY 10013
Phone: (212) 555-9876
Email: jmartinez@lawfirm.com

Defendant Information:
Name: Robert Williams
DOB: 07/22/1975
SSN: 987-65-4321
Address: 789 Liberty Ave, Brooklyn, NY 11208

BATES-001234

Filed: March 10, 2024
Judge: Hon. David Thompson""",
        "pages": [
            {
                "pageNumber": 1,
                "angle": 0,
                "width": 8.5,
                "height": 11,
                "unit": "inch",
                "words": [
                    {"content": "2024-CR-54321", "boundingBox": [200, 150, 350, 170], "confidence": 0.99},
                    {"content": "BATES-001234", "boundingBox": [100, 800, 250, 820], "confidence": 0.99}
                ],
                "lines": [
                    {"content": "Case No: 2024-CR-54321", "boundingBox": [100, 150, 350, 170]},
                    {"content": "ROBERT WILLIAMS", "boundingBox": [100, 250, 300, 270]},
                    {"content": "Attorney: Jennifer Martinez, Esq.", "boundingBox": [100, 400, 400, 420]},
                    {"content": "BATES-001234", "boundingBox": [100, 800, 250, 820]}
                ]
            },
            {
                "pageNumber": 2,
                "angle": 0,
                "width": 8.5, 
                "height": 11,
                "unit": "inch",
                "lines": [
                    {"content": "BATES-001235", "boundingBox": [100, 800, 250, 820]}
                ]
            }
        ],
        "keyValuePairs": [
            {"key": {"content": "Case No"}, "value": {"content": "2024-CR-54321"}},
            {"key": {"content": "Defendant"}, "value": {"content": "Robert Williams"}},
            {"key": {"content": "Attorney"}, "value": {"content": "Jennifer Martinez"}},
            {"key": {"content": "Bar Number"}, "value": {"content": "NY-987654"}},
            {"key": {"content": "Filed"}, "value": {"content": "March 10, 2024"}}
        ],
        "analyzeResult": {
            "apiVersion": "2023-07-31",
            "modelId": "prebuilt-layout",
            "stringIndexType": "textElements"
        }
    }


def generate_government_form_json():
    """Generate synthetic government form with tables and checkboxes."""
    return {
        "status": "succeeded",
        "createdDateTime": "2024-02-28T09:15:00Z",
        "content": """DEPARTMENT OF SOCIAL SERVICES
CASE REPORT FORM

Case Number: DSS-2024-78901
Date: February 28, 2024

Client Information:
Name: Maria Garcia
DOB: 05/10/1985
SSN: 456-78-9012
Phone: (555) 345-6789
Address: 321 Oak Street, Apt 4B, San Diego, CA 92101
Email: mgarcia85@email.com

Case Worker: James Wilson
Employee ID: EMP-45678
Department: Family Services

Emergency Contact:
Name: Carlos Garcia
Relationship: Spouse
Phone: (555) 345-9876

Services Requested:
[X] Food Assistance
[X] Housing Support
[ ] Medical Services
[X] Child Care

FORM ID: DSS-FORM-2024-001""",
        "pages": [
            {
                "pageNumber": 1,
                "angle": 0,
                "width": 8.5,
                "height": 11,
                "unit": "inch",
                "selectionMarks": [
                    {"state": "selected", "boundingBox": [50, 600, 70, 620], "confidence": 0.99},
                    {"state": "selected", "boundingBox": [50, 630, 70, 650], "confidence": 0.99},
                    {"state": "unselected", "boundingBox": [50, 660, 70, 680], "confidence": 0.99},
                    {"state": "selected", "boundingBox": [50, 690, 70, 710], "confidence": 0.99}
                ]
            }
        ],
        "tables": [
            {
                "rowCount": 5,
                "columnCount": 2,
                "cells": [
                    {"rowIndex": 0, "columnIndex": 0, "content": "Field", "kind": "columnHeader"},
                    {"rowIndex": 0, "columnIndex": 1, "content": "Value", "kind": "columnHeader"},
                    {"rowIndex": 1, "columnIndex": 0, "content": "Client Name"},
                    {"rowIndex": 1, "columnIndex": 1, "content": "Maria Garcia"},
                    {"rowIndex": 2, "columnIndex": 0, "content": "Case Number"},
                    {"rowIndex": 2, "columnIndex": 1, "content": "DSS-2024-78901"},
                    {"rowIndex": 3, "columnIndex": 0, "content": "Case Worker"},
                    {"rowIndex": 3, "columnIndex": 1, "content": "James Wilson"},
                    {"rowIndex": 4, "columnIndex": 0, "content": "Department"},
                    {"rowIndex": 4, "columnIndex": 1, "content": "Family Services"}
                ]
            }
        ],
        "keyValuePairs": [
            {"key": {"content": "Case Number"}, "value": {"content": "DSS-2024-78901"}},
            {"key": {"content": "Client Name"}, "value": {"content": "Maria Garcia"}},
            {"key": {"content": "SSN"}, "value": {"content": "456-78-9012"}},
            {"key": {"content": "Case Worker"}, "value": {"content": "James Wilson"}},
            {"key": {"content": "Employee ID"}, "value": {"content": "EMP-45678"}}
        ],
        "analyzeResult": {
            "apiVersion": "2023-07-31",
            "modelId": "prebuilt-layout",
            "stringIndexType": "textElements"
        }
    }


def generate_edge_case_json():
    """Generate edge case with missing/partial data."""
    return {
        "status": "succeeded",
        "createdDateTime": "2024-04-01T16:45:00Z",
        "content": """[PARTIALLY READABLE DOCUMENT]

Name: J█████ Sm███
ID: ███-██-4567
Date: ██/██/2024

Contact Information:
Phone: (5██) ███-████
Email: j████@████.com

Notes: Document partially damaged by water.
Some information may be missing or illegible.

Reference: DAMAGED-DOC-2024-001""",
        "pages": [
            {
                "pageNumber": 1,
                "angle": 0,
                "width": 8.5,
                "height": 11,
                "unit": "inch",
                "words": [
                    {"content": "J", "boundingBox": [100, 200, 110, 220], "confidence": 0.65},
                    {"content": "Sm", "boundingBox": [200, 200, 220, 220], "confidence": 0.70}
                ],
                "lines": [
                    {"content": "Name: J█████ Sm███", "boundingBox": [100, 200, 300, 220]},
                    {"content": "ID: ███-██-4567", "boundingBox": [100, 240, 300, 260]}
                ]
            }
        ],
        "tables": [],
        "keyValuePairs": [
            {"key": {"content": "Reference"}, "value": {"content": "DAMAGED-DOC-2024-001"}}
        ],
        "analyzeResult": {
            "apiVersion": "2023-07-31",
            "modelId": "prebuilt-layout",
            "stringIndexType": "textElements",
            "warnings": [
                {"code": "PARTIAL_TEXT", "message": "Some text may be illegible due to document quality"}
            ]
        }
    }


def main():
    """Generate all synthetic test files."""
    output_dir = Path(__file__).parent.parent / "synthetic"
    output_dir.mkdir(exist_ok=True)
    
    test_files = {
        "medical_chart_multi_visit.json": generate_medical_chart_json(),
        "legal_case_file.json": generate_legal_case_file_json(),
        "government_form.json": generate_government_form_json(),
        "edge_case_damaged.json": generate_edge_case_json()
    }
    
    for filename, data in test_files.items():
        output_path = output_dir / filename
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"✅ Generated: {output_path}")
    
    print(f"\n✨ Generated {len(test_files)} synthetic test files in {output_dir}")
    print("\nThese files contain realistic but fake PII and are safe to commit to the repository.")


if __name__ == "__main__":
    main()