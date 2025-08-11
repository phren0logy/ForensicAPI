"""Integration test to verify the package works when installed."""

import subprocess
import json
import tempfile
from pathlib import Path


def test_forensicapi_cli_runs():
    """Test that the forensicapi CLI can be invoked."""
    # Try to run the CLI with a short timeout
    # MCP servers expect JSON-RPC input on stdin
    test_input = json.dumps({
        "jsonrpc": "2.0",
        "method": "initialize",
        "params": {},
        "id": 1
    })
    
    result = subprocess.run(
        ["uv", "run", "forensicapi"],
        input=test_input,
        capture_output=True,
        text=True,
        timeout=5
    )
    
    # Check that it started and responded (or waiting for more input)
    assert result.returncode == 0 or "jsonrpc" in result.stdout.lower() or len(result.stdout) > 0
    

def test_mcp_tools_accessible():
    """Test that MCP tools can be imported and used."""
    code = """
import asyncio
from forensicapi.mcp_server import mcp, ProcessingResult

# Test that we can access the server
print(f"Server name: {mcp.name}")

# Test that ProcessingResult works
result = ProcessingResult(
    success=True,
    output_paths=["/test/path"],
    statistics={"test": 1},
    message="Test successful"
)
print(f"Result created: {result.success}")
"""
    
    result = subprocess.run(
        ["uv", "run", "python", "-c", code],
        capture_output=True,
        text=True,
        timeout=10
    )
    
    assert result.returncode == 0, f"Failed to run test code: {result.stderr}"
    assert "Server name: ForensicAPI" in result.stdout
    assert "Result created: True" in result.stdout


if __name__ == "__main__":
    test_forensicapi_cli_runs()
    test_mcp_tools_accessible()
    print("✅ All integration tests passed!")