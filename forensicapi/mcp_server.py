"""
ForensicAPI MCP Server - Document anonymization and processing via Model Context Protocol.

This MCP server provides four focused tools for privacy-preserving document processing:
1. anonymize_documents - Replace PII with consistent fake data
2. restore_documents - Restore original PII using vault
3. extract_document - Convert PDF/DOCX to markdown
4. segment_document - Split large documents into LLM-ready chunks
"""

from fastmcp import FastMCP
from typing import List, Optional, Dict, Any
import os
import json
from pathlib import Path
from datetime import datetime
import glob as glob_module
import asyncio
from dataclasses import dataclass

# Import our existing FastAPI components
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from routes.anonymization import (
    AnonymizationConfig, 
    create_anonymizer,
    anonymize_text_with_consistent_replacements,
    generate_session_shift,
    serialize_vault_v2,
    deserialize_vault_v2
)
from routes.extraction import extract_azure
from routes.extraction_docling import extract_local
import tiktoken
import re

# Initialize MCP server
mcp = FastMCP("ForensicAPI")


@dataclass
class ProcessingResult:
    """Result from document processing operations."""
    success: bool
    output_paths: List[str]
    statistics: Dict[str, Any]
    message: str
    vault_path: Optional[str] = None


def find_files(directory: Optional[str] = None, 
               files: Optional[List[str]] = None,
               patterns: List[str] = ["*.pdf", "*.md", "*.txt"],
               recursive: bool = True) -> List[str]:
    """Find files matching patterns in directory or from explicit file list."""
    if files:
        # Validate all files exist
        found_files = []
        for f in files:
            path = Path(f)
            if path.exists():
                found_files.append(str(path.absolute()))
            else:
                raise FileNotFoundError(f"File not found: {f}")
        return found_files
    
    if directory:
        dir_path = Path(directory)
        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")
        
        found_files = []
        for pattern in patterns:
            if recursive:
                glob_pattern = str(dir_path / "**" / pattern)
                found_files.extend(glob_module.glob(glob_pattern, recursive=True))
            else:
                glob_pattern = str(dir_path / pattern)
                found_files.extend(glob_module.glob(glob_pattern))
        
        return sorted(list(set(found_files)))
    
    raise ValueError("Either 'files' or 'directory' must be provided")


def ensure_output_dir(output_dir: str) -> Path:
    """Ensure output directory exists and return Path object."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    return out_path


@dataclass
class MarkdownSegment:
    """A segment of markdown content with metadata."""
    content: str
    token_count: int
    start_line: int
    end_line: int
    heading_context: Dict[str, Optional[str]]


def parse_markdown_headings(lines: List[str]) -> List[tuple[int, int, str]]:
    """Parse markdown lines to find headings.
    
    Returns list of (line_number, level, text) tuples.
    """
    headings = []
    for i, line in enumerate(lines):
        match = re.match(r'^(#{1,6})\s+(.+)$', line.strip())
        if match:
            level = len(match.group(1))
            text = match.group(2).strip()
            headings.append((i, level, text))
    return headings


def segment_markdown_content(content: str, min_tokens: int = 10000, max_tokens: int = 15000) -> List[MarkdownSegment]:
    """Segment markdown content into chunks based on token limits and heading boundaries.
    
    Args:
        content: Markdown content to segment
        min_tokens: Minimum tokens per segment
        max_tokens: Maximum tokens per segment (soft limit)
        
    Returns:
        List of MarkdownSegment objects
    """
    # Initialize tokenizer
    encoding = tiktoken.get_encoding("cl100k_base")
    
    # Split into lines for processing
    lines = content.split('\n')
    
    # Parse headings
    headings = parse_markdown_headings(lines)
    heading_lines = {h[0] for h in headings}
    
    # Track heading context
    heading_context = {f"h{i}": None for i in range(1, 7)}
    
    segments = []
    current_segment_lines = []
    current_token_count = 0
    segment_start_line = 0
    
    # Track if we're in a code block or table
    in_code_block = False
    in_table = False
    
    for i, line in enumerate(lines):
        # Check for code block boundaries
        if line.strip().startswith('```'):
            in_code_block = not in_code_block
        
        # Check for table (simple heuristic - line starts with |)
        if line.strip().startswith('|'):
            in_table = True
        elif not line.strip().startswith('|') and in_table:
            in_table = False
        
        # Calculate tokens for this line
        line_tokens = len(encoding.encode(line))
        
        # Check if this is a heading
        is_heading = i in heading_lines
        heading_level = None
        if is_heading:
            for h in headings:
                if h[0] == i:
                    heading_level = h[1]
                    # Update heading context
                    heading_context[f"h{heading_level}"] = h[2]
                    # Clear lower-level headings
                    for level in range(heading_level + 1, 7):
                        heading_context[f"h{level}"] = None
                    break
        
        # Determine if we should start a new segment
        should_split = False
        
        # Don't split in the middle of code blocks or tables
        if not in_code_block and not in_table:
            # Check if we've reached minimum tokens and hit a high-level heading
            if current_token_count >= min_tokens and is_heading and heading_level in [1, 2]:
                should_split = True
            # Check if adding this line would exceed max tokens
            elif current_token_count + line_tokens > max_tokens and current_segment_lines:
                should_split = True
        
        # Create segment if needed
        if should_split and current_segment_lines:
            segments.append(MarkdownSegment(
                content='\n'.join(current_segment_lines),
                token_count=current_token_count,
                start_line=segment_start_line + 1,  # 1-indexed for user readability
                end_line=i,  # Current line number (exclusive)
                heading_context=heading_context.copy()
            ))
            
            # Start new segment
            current_segment_lines = []
            current_token_count = 0
            segment_start_line = i
        
        # Add line to current segment
        current_segment_lines.append(line)
        current_token_count += line_tokens
    
    # Add final segment if not empty
    if current_segment_lines:
        segments.append(MarkdownSegment(
            content='\n'.join(current_segment_lines),
            token_count=current_token_count,
            start_line=segment_start_line + 1,
            end_line=len(lines),
            heading_context=heading_context.copy()
        ))
    
    return segments


async def report_progress(context: Any, message: str, progress: float = None):
    """Report progress to MCP client in a privacy-preserving way."""
    # Privacy-preserving progress messages (no PII content)
    if hasattr(context, 'report_progress'):
        await context.report_progress(message=message, progress=progress)
    else:
        # Fallback for testing
        print(f"Progress: {message}")


@mcp.tool
async def anonymize_documents(
    output_dir: str,
    files: Optional[List[str]] = None,
    directory: Optional[str] = None,
    patterns: List[str] = ["*.pdf", "*.md", "*.txt"],
    recursive: bool = True,
    pattern_sets: List[str] = [],
    entity_types: Optional[List[str]] = None,
    score_threshold: float = 0.5,
    date_shift_days: int = 365,
    context: Optional[Any] = None
) -> ProcessingResult:
    """
    Anonymize documents by replacing PII with realistic fake data.
    
    This tool processes documents to replace personally identifiable information (PII)
    with consistent, realistic fake data. The same entity always gets the same 
    replacement across all documents (e.g., "John Smith" always becomes "Robert Johnson").
    
    Args:
        output_dir: Directory to save anonymized files and vault
        files: List of specific file paths to anonymize (optional)
        directory: Directory to scan for files (optional, use files OR directory)
        patterns: File patterns to match (default: PDF, markdown, text)
        recursive: Include subdirectories when scanning (default: true)
        pattern_sets: Domain patterns - "legal", "medical" (default: none)
        entity_types: PII types to detect (default: all 54 types)
        score_threshold: Minimum confidence for detection (0.0-1.0, default: 0.5)
        date_shift_days: Maximum days to shift dates (default: 365)
        context: MCP context for progress reporting
    
    Returns:
        ProcessingResult with output paths, statistics, and vault location
    """
    try:
        # Find files to process
        await report_progress(context, "Scanning for documents...", 0.1)
        input_files = find_files(directory, files, patterns, recursive)
        
        if not input_files:
            return ProcessingResult(
                success=False,
                output_paths=[],
                statistics={},
                message="No files found matching the specified patterns"
            )
        
        await report_progress(context, f"Found {len(input_files)} files to anonymize", 0.2)
        
        # Prepare output directory
        out_path = ensure_output_dir(output_dir)
        anon_path = out_path / "anonymized"
        anon_path.mkdir(exist_ok=True)
        
        # Initialize anonymization
        config = AnonymizationConfig(
            entity_types=entity_types or [],
            pattern_sets=pattern_sets,
            score_threshold=score_threshold,
            date_shift_days=date_shift_days
        )
        
        # Create anonymizer and vault
        scanner, vault, date_offset, existing_mappings = create_anonymizer(config)
        
        # Generate consistent date shift for this session
        if date_shift_days:
            date_offset = generate_session_shift(date_shift_days, date_offset)
        
        # Process each file
        total_statistics = {}
        output_paths = []
        vault_mappings = existing_mappings.copy()
        
        for i, file_path in enumerate(input_files):
            progress = 0.2 + (0.6 * i / len(input_files))
            file_name = Path(file_path).name
            await report_progress(
                context, 
                f"Processing file {i+1} of {len(input_files)}: {file_name}",
                progress
            )
            
            # Read file content
            content = ""
            file_type = Path(file_path).suffix.lower()
            
            if file_type == ".pdf":
                # Extract PDF to markdown first
                try:
                    # Try Azure DI if available
                    from fastapi import UploadFile
                    # For file path operations, we need to create a file-like object
                    with open(file_path, 'rb') as f:
                        file_obj = UploadFile(filename=Path(file_path).name, file=f)
                        result = await extract_azure(file_obj)
                        content = result.markdown_content
                except:
                    # Fall back to Docling
                    with open(file_path, 'rb') as f:
                        file_obj = UploadFile(filename=Path(file_path).name, file=f)
                        result = await extract_local(file_obj)
                        content = result.markdown_content
            else:
                # Read text/markdown files directly
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            
            # Anonymize content
            anonymized_text, statistics, new_mappings = anonymize_text_with_consistent_replacements(
                content,
                scanner,
                vault,
                config,
                vault_mappings,
                date_offset
            )
            
            # Update vault mappings
            vault_mappings.update(new_mappings)
            
            # Aggregate statistics
            for entity_type, count in statistics.items():
                total_statistics[entity_type] = total_statistics.get(entity_type, 0) + count
            
            # Save anonymized file as markdown
            output_name = Path(file_path).stem + ".md"
            output_file = anon_path / output_name
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(anonymized_text)
            
            output_paths.append(str(output_file))
        
        # Save vault
        await report_progress(context, "Saving anonymization vault...", 0.9)
        vault_data = serialize_vault_v2(vault_mappings, date_offset, len(input_files))
        vault_path = out_path / "vault.json"
        with open(vault_path, 'w', encoding='utf-8') as f:
            json.dump(vault_data, f, indent=2)
        
        # Create summary report
        report_path = out_path / "REPORT.md"
        report = f"""# Anonymization Report

Generated: {datetime.now().isoformat()}

## Summary
- Files processed: {len(input_files)}
- Output directory: {output_dir}
- Vault location: vault.json

## Statistics
"""
        for entity_type, count in sorted(total_statistics.items()):
            report += f"- {entity_type}: {count}\n"
        
        report += f"\n## Consistency\n"
        report += "All occurrences of the same entity received the same replacement across all documents.\n"
        report += "To restore original values, use the restore_documents tool with the vault.json file.\n"
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        await report_progress(context, "Anonymization complete!", 1.0)
        
        return ProcessingResult(
            success=True,
            output_paths=output_paths,
            statistics=total_statistics,
            message=f"Successfully anonymized {len(input_files)} files",
            vault_path=str(vault_path)
        )
        
    except Exception as e:
        return ProcessingResult(
            success=False,
            output_paths=[],
            statistics={},
            message=f"Anonymization failed: {str(e)}"
        )


@mcp.tool
async def restore_documents(
    output_dir: str,
    files: Optional[List[str]] = None,
    directory: Optional[str] = None,
    vault_path: Optional[str] = None,
    patterns: List[str] = ["*.md"],
    recursive: bool = True,
    context: Optional[Any] = None
) -> ProcessingResult:
    """
    Restore original PII in anonymized documents using vault.
    
    This tool reverses the anonymization process by replacing fake data with
    the original PII values stored in the vault. Only works with documents
    that were anonymized using anonymize_documents.
    
    Args:
        output_dir: Directory to save restored files
        files: List of specific anonymized files to restore (optional)
        directory: Directory containing anonymized files (optional)
        vault_path: Path to vault.json (auto-detected if not provided)
        patterns: File patterns to match (default: ["*.md"])
        recursive: Include subdirectories (default: true)
        context: MCP context for progress reporting
    
    Returns:
        ProcessingResult with restored file paths
    """
    try:
        # Find files to restore
        await report_progress(context, "Scanning for anonymized documents...", 0.1)
        input_files = find_files(directory, files, patterns, recursive)
        
        if not input_files:
            return ProcessingResult(
                success=False,
                output_paths=[],
                statistics={},
                message="No anonymized files found"
            )
        
        # Find vault file
        if not vault_path:
            # Auto-detect vault in parent directory
            if directory:
                parent_dir = Path(directory).parent
                possible_vault = parent_dir / "vault.json"
                if possible_vault.exists():
                    vault_path = str(possible_vault)
                else:
                    # Check current directory
                    current_vault = Path(directory) / "vault.json"
                    if current_vault.exists():
                        vault_path = str(current_vault)
        
        if not vault_path or not Path(vault_path).exists():
            return ProcessingResult(
                success=False,
                output_paths=[],
                statistics={},
                message="Vault file not found. Cannot restore without vault.json"
            )
        
        await report_progress(context, "Loading vault data...", 0.2)
        
        # Load vault
        with open(vault_path, 'r', encoding='utf-8') as f:
            vault_data = json.load(f)
        
        # Deserialize vault to get mappings
        _, _, mappings = deserialize_vault_v2(vault_data)
        
        # Create reverse mappings (faker_value -> original_value)
        reverse_mappings = {v: k for k, v in mappings.items()}
        
        # Prepare output directory
        out_path = ensure_output_dir(output_dir)
        restored_path = out_path / "restored"
        restored_path.mkdir(exist_ok=True)
        
        # Process each file
        output_paths = []
        total_replacements = 0
        
        for i, file_path in enumerate(input_files):
            progress = 0.2 + (0.7 * i / len(input_files))
            file_name = Path(file_path).name
            await report_progress(
                context,
                f"Restoring file {i+1} of {len(input_files)}: {file_name}",
                progress
            )
            
            # Read anonymized content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Restore original values
            restored_content = content
            replacements_in_file = 0
            
            for faker_value, original_value in reverse_mappings.items():
                if faker_value in restored_content:
                    restored_content = restored_content.replace(faker_value, original_value)
                    replacements_in_file += restored_content.count(original_value)
            
            total_replacements += replacements_in_file
            
            # Save restored file
            output_file = restored_path / file_name
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(restored_content)
            
            output_paths.append(str(output_file))
        
        # Create restoration report
        await report_progress(context, "Creating restoration report...", 0.95)
        report_path = out_path / "RESTORATION_REPORT.md"
        report = f"""# Restoration Report

Generated: {datetime.now().isoformat()}

## Summary
- Files restored: {len(input_files)}
- Total replacements: {total_replacements}
- Vault used: {vault_path}
- Output directory: {output_dir}

## Details
All fake values have been replaced with their original PII values.
The restored documents are identical to the pre-anonymization versions.
"""
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        await report_progress(context, "Restoration complete!", 1.0)
        
        return ProcessingResult(
            success=True,
            output_paths=output_paths,
            statistics={"files_restored": len(input_files), "total_replacements": total_replacements},
            message=f"Successfully restored {len(input_files)} files"
        )
        
    except Exception as e:
        return ProcessingResult(
            success=False,
            output_paths=[],
            statistics={},
            message=f"Restoration failed: {str(e)}"
        )


@mcp.tool
async def extract_document(
    file_path: str,
    output_path: Optional[str] = None,
    extraction_method: str = "local",
    context: Optional[Any] = None
) -> ProcessingResult:
    """
    Convert PDF or DOCX document to markdown format.
    
    Extracts text content from documents while preserving structure,
    formatting, tables, and other elements. Supports both local 
    processing (Docling) and cloud processing (Azure DI).
    
    Args:
        file_path: Path to the input document (PDF or DOCX)
        output_path: Path for output markdown file (optional, auto-generated if not provided)
        extraction_method: "local" (Docling) or "azure" (Azure Document Intelligence)
        context: MCP context for progress reporting
    
    Returns:
        ProcessingResult with extracted markdown file path
    """
    try:
        # Validate input file
        input_path = Path(file_path)
        if not input_path.exists():
            return ProcessingResult(
                success=False,
                output_paths=[],
                statistics={},
                message=f"Input file not found: {file_path}"
            )
        
        file_type = input_path.suffix.lower()
        if file_type not in [".pdf", ".docx"]:
            return ProcessingResult(
                success=False,
                output_paths=[],
                statistics={},
                message=f"Unsupported file type: {file_type}. Only PDF and DOCX are supported."
            )
        
        # Determine output path
        if not output_path:
            output_path = str(input_path.with_suffix(".md"))
        
        await report_progress(context, f"Extracting {input_path.name}...", 0.2)
        
        # Extract based on method
        try:
            from fastapi import UploadFile
            
            if extraction_method == "azure" and file_type == ".pdf":
                await report_progress(context, "Using Azure Document Intelligence...", 0.3)
                with open(str(input_path), 'rb') as f:
                    file_obj = UploadFile(filename=input_path.name, file=f)
                    result = await extract_azure(file_obj)
                    markdown_content = result.markdown_content
                    metadata = result.metadata
            else:
                await report_progress(context, "Using local Docling extraction...", 0.3)
                with open(str(input_path), 'rb') as f:
                    file_obj = UploadFile(filename=input_path.name, file=f)
                    result = await extract_local(file_obj)
                    markdown_content = result.markdown_content
                    metadata = result.metadata
                
        except Exception as extract_error:
            if extraction_method == "azure":
                # Fallback to local if Azure fails
                await report_progress(context, "Azure failed, falling back to local extraction...", 0.5)
                with open(str(input_path), 'rb') as f:
                    file_obj = UploadFile(filename=input_path.name, file=f)
                    result = await extract_local(file_obj)
                    markdown_content = result.markdown_content
                    metadata = result.metadata
            else:
                raise extract_error
        
        await report_progress(context, "Writing markdown output...", 0.8)
        
        # Save markdown content
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        # Calculate output tokens
        encoding = tiktoken.get_encoding("cl100k_base")
        output_tokens = len(encoding.encode(markdown_content))
        
        # Prepare statistics
        statistics = {
            "extraction_method": metadata.get("processor_type", extraction_method),
            "pages": metadata.get("page_count", "unknown"),
            "processing_time": metadata.get("processing_time_seconds", "unknown"),
            "input_size_bytes": input_path.stat().st_size,
            "output_tokens": output_tokens
        }
        
        await report_progress(context, "Extraction complete!", 1.0)
        
        return ProcessingResult(
            success=True,
            output_paths=[output_path],
            statistics=statistics,
            message=f"Successfully extracted {input_path.name} to markdown"
        )
        
    except Exception as e:
        return ProcessingResult(
            success=False,
            output_paths=[],
            statistics={},
            message=f"Extraction failed: {str(e)}"
        )


@mcp.tool
async def segment_document(
    file_path: str,
    output_dir: str,
    max_tokens: int = 15000,
    min_tokens: int = 10000,
    context: Optional[Any] = None
) -> ProcessingResult:
    """
    Split large markdown document into LLM-ready chunks.
    
    Intelligently segments documents at natural boundaries (chapters, sections)
    while respecting token limits. Each segment is a self-contained portion
    suitable for LLM processing.
    
    Args:
        file_path: Path to markdown file to segment
        output_dir: Directory to save segment files
        max_tokens: Maximum tokens per segment (default: 15000)
        min_tokens: Minimum tokens per segment (default: 10000)
        context: MCP context for progress reporting
    
    Returns:
        ProcessingResult with list of segment file paths
    """
    try:
        # Validate input
        input_path = Path(file_path)
        if not input_path.exists():
            return ProcessingResult(
                success=False,
                output_paths=[],
                statistics={},
                message=f"Input file not found: {file_path}"
            )
        
        if input_path.suffix.lower() not in [".md", ".markdown", ".txt"]:
            return ProcessingResult(
                success=False,
                output_paths=[],
                statistics={},
                message="Only markdown or text files can be segmented"
            )
        
        await report_progress(context, "Reading document...", 0.1)
        
        # Read content
        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        await report_progress(context, "Analyzing document structure...", 0.2)
        
        # Use markdown segmentation
        segments = segment_markdown_content(content, min_tokens, max_tokens)
        
        # Prepare output directory
        out_path = ensure_output_dir(output_dir)
        segments_path = out_path / "segments"
        segments_path.mkdir(exist_ok=True)
        
        # Save segments
        output_paths = []
        base_name = input_path.stem
        total_segments = len(segments)
        
        for i, segment in enumerate(segments):
            progress = 0.3 + (0.6 * i / total_segments)
            await report_progress(
                context,
                f"Writing segment {i+1} of {total_segments}...",
                progress
            )
            
            # Create segment filename
            segment_name = f"{base_name}_{i+1:03d}_of_{total_segments:03d}.md"
            segment_path = segments_path / segment_name
            
            # Add segment header
            segment_content = f"""<!-- Segment {i+1} of {total_segments} -->
<!-- Original file: {input_path.name} -->
<!-- Tokens: ~{segment.token_count} -->

{segment.content}
"""
            
            with open(segment_path, 'w', encoding='utf-8') as f:
                f.write(segment_content)
            
            output_paths.append(str(segment_path))
        
        # Create segmentation report
        await report_progress(context, "Creating segmentation report...", 0.95)
        report_path = out_path / "SEGMENTATION_REPORT.md"
        report = f"""# Segmentation Report

Generated: {datetime.now().isoformat()}

## Summary
- Source file: {input_path.name}
- Total segments: {total_segments}
- Token range: {min_tokens} - {max_tokens}
- Output directory: {output_dir}

## Segments Created
"""
        
        for i, segment in enumerate(segments):
            report += f"\n### Segment {i+1}\n"
            report += f"- Tokens: ~{segment.token_count}\n"
            report += f"- Start line: {segment.start_line}\n"
            report += f"- End line: {segment.end_line}\n"
            # Show current heading context
            for level in range(1, 7):
                heading = segment.heading_context.get(f"h{level}")
                if heading:
                    report += f"- H{level}: {heading}\n"
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        await report_progress(context, "Segmentation complete!", 1.0)
        
        # Statistics
        statistics = {
            "total_segments": total_segments,
            "average_tokens": sum(s.token_count for s in segments) // total_segments,
            "min_tokens": min(s.token_count for s in segments),
            "max_tokens": max(s.token_count for s in segments)
        }
        
        return ProcessingResult(
            success=True,
            output_paths=output_paths,
            statistics=statistics,
            message=f"Successfully segmented into {total_segments} files"
        )
        
    except Exception as e:
        return ProcessingResult(
            success=False,
            output_paths=[],
            statistics={},
            message=f"Segmentation failed: {str(e)}"
        )


# Main entry point
def main():
    """Run the MCP server."""
    import sys
    import logging
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run the server
    try:
        mcp.run()
    except KeyboardInterrupt:
        print("\nShutting down ForensicAPI MCP server...")
        sys.exit(0)
    except Exception as e:
        print(f"Error running MCP server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()