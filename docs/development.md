# Development Guide

This guide covers development setup and testing for ForensicAPI.

## Prerequisites

- Python 3.13+
- uv (for dependency management)
- Node.js (for MCP Inspector)

## Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/forensicapi.git
cd forensicapi
```

2. Install dependencies:
```bash
uv sync --all-extras
```

3. Set up environment variables (optional, for Azure DI):
```bash
cp .env.example .env
# Edit .env with your Azure credentials
```

## Running Tests

### Unit Tests

Run the test suite:
```bash
uv run pytest tests/ -v
```

Run specific tests:
```bash
uv run pytest tests/test_mcp_server.py::TestAnonymizeDocuments -v
```

### MCP Inspector Testing

The easiest way to test MCP tools interactively is using MCP Inspector:

1. Install MCP Inspector:
```bash
npm install -g @modelcontextprotocol/inspector
```

2. Run ForensicAPI with MCP Inspector:
```bash
uv run fastmcp dev forensicapi.mcp_server:mcp
```

This will:
- Start the MCP server
- Open MCP Inspector in your browser
- Allow you to test all tools interactively

### Manual Testing

Test the CLI directly:
```bash
# Run the MCP server
uv run forensicapi

# In another terminal, test with a client
# (requires an MCP client implementation)
```

## Development Workflow

### Adding New Tools

1. Define the tool in `forensicapi/mcp_server.py`:
```python
@mcp.tool()
async def my_new_tool(param1: str, param2: int = 10) -> str:
    """Tool description for MCP clients."""
    # Implementation
    return f"Processed {param1} with {param2}"
```

2. Add tests in `tests/test_mcp_server.py`:
```python
def test_my_new_tool():
    result = my_new_tool("test", 20)
    assert "Processed test with 20" in result
```

3. Test with MCP Inspector:
```bash
uv run fastmcp dev forensicapi.mcp_server:mcp
```

### Code Style

We use:
- Black for formatting (line length: 100)
- Type hints for all public functions
- Docstrings for all tools and public functions

Format code:
```bash
uv run black . --line-length 100
```

### Building for Distribution

1. Update version in `pyproject.toml`

2. Build the package:
```bash
python -m build
```

3. Test the build locally:
```bash
pip install dist/forensicapi-*.whl
forensicapi --help
```

## Debugging

### Enable Debug Logging

Set environment variable:
```bash
export FORENSICAPI_DEBUG=true
uv run forensicapi
```

### Common Issues

**Import Errors**
- Ensure you're in the project root
- Run with `uv run` to use the correct environment

**MCP Inspector Connection Issues**
- Check that port 5173 is available
- Try specifying a different port: `fastmcp dev --port 5174`

**Azure DI Timeouts**
- Reduce batch size in code
- Check Azure service status
- Verify credentials are correct

## Testing Different Transports

### STDIO (Default)
```bash
uv run forensicapi
```

### HTTP Transport (Future)
```python
# In mcp_server.py
if __name__ == "__main__":
    import os
    if os.getenv("MCP_TRANSPORT") == "http":
        mcp.run(transport="http", port=8080)
    else:
        mcp.run()  # STDIO
```

## Publishing

Releases are automated via GitHub Actions:

1. Update version in `pyproject.toml`
2. Commit and push changes
3. Create and push a tag:
```bash
git tag v2.0.0
git push origin v2.0.0
```

GitHub Actions will:
- Run tests
- Build the package
- Publish to PyPI (requires PyPI trusted publisher setup)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Run the test suite
5. Submit a pull request

See [CONTRIBUTING.md](../CONTRIBUTING.md) for detailed guidelines.