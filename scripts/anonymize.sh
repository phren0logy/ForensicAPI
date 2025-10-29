#!/bin/bash

# Document Anonymization Script
# Uses the FastAPI anonymization endpoint to anonymize documents via command line
# Supports stateless operation with vault persistence for consistent anonymization

set -euo pipefail

# Configuration
API_URL="http://127.0.0.1:8000/anonymization/anonymize"
DEFAULT_DATE_SHIFT=365

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

usage() {
    cat << EOF
Usage: $0 [OPTIONS] <file_to_anonymize>

OPTIONS:
    -v, --vault FILE        Use vault file for consistent anonymization across documents
    -o, --output FILE       Output file (default: stdout)
    -d, --date-shift DAYS   Maximum days to shift dates (default: $DEFAULT_DATE_SHIFT)
    -p, --patterns SETS     Pattern sets to enable (comma-separated: legal,medical)
    -e, --entities TYPES    Entity types to detect (comma-separated, default: all)
    -t, --threshold NUM     Detection threshold 0.0-1.0 (default: 0.5)
    -s, --stats             Show detailed statistics
    -h, --help              Show this help message

EXAMPLES:
    # Simple anonymization
    $0 document.txt

    # With vault persistence for consistency across multiple documents
    $0 -v vault.json document1.txt
    $0 -v vault.json document2.txt

    # Enable legal and medical pattern detection
    $0 -p legal,medical -d 180 legal_document.pdf

    # Custom entity types only
    $0 -e "PERSON,EMAIL_ADDRESS,PHONE_NUMBER" document.txt

    # Save to file with statistics
    $0 -s -o anonymized.txt document.txt

NOTES:
    - The FastAPI server must be running on $API_URL
    - Vault files enable consistent anonymization (same name = same fake name)
    - Supports 54 PII types via AI4Privacy BERT model
    - Preserves markdown formatting and document structure
EOF
}

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1" >&2
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1" >&2
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

check_server() {
    if ! curl -s "$API_URL" > /dev/null 2>&1; then
        log_error "Cannot connect to FastAPI server at $API_URL"
        log_error "Please start the server with: uv run run.py"
        exit 1
    fi
}

escape_json() {
    local input="$1"
    # Escape quotes and convert newlines to \n
    echo "$input" | sed 's/"/\\"/g' | tr '\n' '\t' | sed 's/\t/\\n/g'
}

parse_entity_types() {
    local types="$1"
    if [ -n "$types" ]; then
        # Convert comma-separated to JSON array
        echo "[$types]" | sed 's/,/","/g' | sed 's/\[/["/' | sed 's/\]/"]/'
    else
        echo "null"
    fi
}

parse_pattern_sets() {
    local sets="$1"
    if [ -n "$sets" ]; then
        # Convert comma-separated to JSON array
        echo "[$sets]" | sed 's/,/","/g' | sed 's/\[/["/' | sed 's/\]/"]/'
    else
        echo "[]"
    fi
}

main() {
    local input_file=""
    local output_file=""
    local vault_file=""
    local date_shift="$DEFAULT_DATE_SHIFT"
    local pattern_sets=""
    local entity_types=""
    local threshold="0.5"
    local show_stats=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                usage
                exit 0
                ;;
            -v|--vault)
                vault_file="$2"
                shift 2
                ;;
            -o|--output)
                output_file="$2"
                shift 2
                ;;
            -d|--date-shift)
                date_shift="$2"
                shift 2
                ;;
            -p|--patterns)
                pattern_sets="$2"
                shift 2
                ;;
            -e|--entities)
                entity_types="$2"
                shift 2
                ;;
            -t|--threshold)
                threshold="$2"
                shift 2
                ;;
            -s|--stats)
                show_stats=true
                shift
                ;;
            -*)
                log_error "Unknown option: $1"
                usage
                exit 1
                ;;
            *)
                if [ -z "$input_file" ]; then
                    input_file="$1"
                else
                    log_error "Multiple input files specified"
                    exit 1
                fi
                shift
                ;;
        esac
    done

    # Validate arguments
    if [ -z "$input_file" ]; then
        log_error "Input file is required"
        usage
        exit 1
    fi

    if [ ! -f "$input_file" ]; then
        log_error "Input file '$input_file' not found"
        exit 1
    fi

    # Check server availability
    check_server

    log_info "Anonymizing document: $input_file"

    # Prepare content
    local content
    content=$(escape_json "$(cat "$input_file")")

    # Prepare vault data if provided
    local vault_data="null"
    if [ -n "$vault_file" ] && [ -f "$vault_file" ]; then
        vault_data=$(cat "$vault_file")
        log_info "Using existing vault: $vault_file"
    elif [ -n "$vault_file" ]; then
        log_info "Creating new vault: $vault_file"
    fi

    # Parse pattern sets
    local patterns_json
    patterns_json=$(parse_pattern_sets "$pattern_sets")

    # Build request JSON - only include entity_types if explicitly provided
    local request
    if [ -n "$entity_types" ]; then
        local entities_json
        entities_json=$(parse_entity_types "$entity_types")
        read -r -d '' request << EOF || true
{
  "content": "$content",
  "config": {
    "anonymize_all_strings": true,
    "entity_types": $entities_json,
    "date_shift_days": $date_shift,
    "score_threshold": $threshold,
    "pattern_sets": $patterns_json
  },
  "vault_data": $vault_data
}
EOF
    else
        read -r -d '' request << EOF || true
{
  "content": "$content",
  "config": {
    "anonymize_all_strings": true,
    "date_shift_days": $date_shift,
    "score_threshold": $threshold,
    "pattern_sets": $patterns_json
  },
  "vault_data": $vault_data
}
EOF
    fi

    log_info "Sending anonymization request..."

    # Make API request
    local result
    if ! result=$(curl -s -X POST "$API_URL" \
        -H "Content-Type: application/json" \
        -d "$request"); then
        log_error "Failed to connect to anonymization API"
        exit 1
    fi

    # Check for API errors
    if echo "$result" | jq -e '.detail' > /dev/null 2>&1; then
        local error_detail
        error_detail=$(echo "$result" | jq -r '.detail')
        log_error "API Error: $error_detail"
        exit 1
    fi

    # Extract anonymized content
    local anonymized_content
    if ! anonymized_content=$(echo "$result" | jq -r '.anonymized_content'); then
        log_error "Failed to parse API response"
        exit 1
    fi

    # Output result
    if [ -n "$output_file" ]; then
        echo "$anonymized_content" > "$output_file"
        log_info "Anonymized content saved to: $output_file"
    else
        echo "$anonymized_content"
    fi

    # Save vault if specified
    if [ -n "$vault_file" ]; then
        echo "$result" | jq '.vault_data' > "$vault_file"
        log_info "Vault data saved to: $vault_file"
    fi

    # Show statistics if requested
    if [ "$show_stats" = true ]; then
        log_info "Anonymization Statistics:"
        echo "$result" | jq '.statistics' >&2
    fi

    log_info "Anonymization completed successfully"
}

# Run main function with all arguments
main "$@"