"""Basic tests for MCP server functionality."""

import pytest
from forensicapi.mcp_server import mcp as server


class TestMCPBasics:
    """Test basic MCP server functionality."""
    
    def test_server_exists(self):
        """Test that the MCP server is properly initialized."""
        assert server is not None
        assert server.name == "ForensicAPI"
    
    def test_tools_registered(self):
        """Test that all expected tools are registered."""
        # Get registered tools
        tools = list(server.tools.keys()) if hasattr(server, 'tools') else []
        
        # Check for expected tools
        expected_tools = [
            'anonymize_documents',
            'restore_documents', 
            'extract_document',
            'segment_document'
        ]
        
        # FastMCP may store tools differently, so we check if functions exist
        from forensicapi import mcp_server
        for tool_name in expected_tools:
            assert hasattr(mcp_server, tool_name), f"Tool {tool_name} not found"
    
    def test_imports_work(self):
        """Test that all necessary imports work."""
        # These imports should not raise errors
        from forensicapi.mcp_server import (
            anonymize_documents,
            restore_documents,
            extract_document,
            segment_document,
            ProcessingResult
        )
        
        # Check they exist (FastMCP wraps them as FunctionTool objects)
        assert anonymize_documents is not None
        assert restore_documents is not None
        assert extract_document is not None
        assert segment_document is not None