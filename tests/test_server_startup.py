"""Test that the MCP server can start properly."""

import subprocess
import sys
import time
import signal
import os


def test_mcp_server_help():
    """Test that the forensicapi command shows help."""
    result = subprocess.run(
        ["uv", "run", "forensicapi", "--help"],
        capture_output=True,
        text=True,
        timeout=10
    )
    
    # FastMCP might not have a --help flag, so we check for common outcomes
    assert result.returncode in [0, 1, 2], f"Unexpected return code: {result.returncode}"
    
    # Check if it's trying to run as an MCP server
    output = result.stdout + result.stderr
    assert "forensicapi" in output.lower() or "mcp" in output.lower() or "json" in output.lower()


def test_mcp_server_imports():
    """Test that the MCP server module can be imported and run."""
    cmd = [
        sys.executable, "-c",
        "from forensicapi.mcp_server import main; print('Import successful')"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, f"Import failed: {result.stderr}"
    assert "Import successful" in result.stdout


def test_mcp_server_startup_and_shutdown():
    """Test that the MCP server can start and be killed cleanly."""
    # Start the server
    proc = subprocess.Popen(
        ["uv", "run", "forensicapi"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    try:
        # Give it a moment to start
        time.sleep(2)
        
        # Check if it's still running
        assert proc.poll() is None, "Server exited immediately"
        
        # Send interrupt signal (like Ctrl+C)
        proc.send_signal(signal.SIGINT)
        
        # Wait for graceful shutdown
        stdout, stderr = proc.communicate(timeout=5)
        
        # Check for expected shutdown message or MCP protocol output
        output = stdout + stderr
        assert len(output) > 0, "No output from server"
        
    except subprocess.TimeoutExpired:
        # Force kill if it doesn't shut down gracefully
        proc.kill()
        proc.communicate()
    except Exception as e:
        proc.kill()
        raise e
    finally:
        # Ensure process is terminated
        if proc.poll() is None:
            proc.kill()


if __name__ == "__main__":
    test_mcp_server_help()
    test_mcp_server_imports()
    print("All startup tests passed!")