# Testing Documentation

## Test Suite Overview

ForensicAPI includes a comprehensive test suite following FastMCP conventions:

### Test Files

1. **test_mcp_server.py** - Basic MCP server tests
   - Server initialization
   - Tool registration
   - Import verification

2. **test_server_startup.py** - Server startup and lifecycle tests
   - CLI help command
   - Import verification
   - Server startup/shutdown

3. **test_integration.py** - Integration tests
   - CLI invocation
   - Tool accessibility
   - Package functionality

## Running Tests

### All Tests
```bash
uv run pytest tests/ -v
```

### Specific Test File
```bash
uv run pytest tests/test_mcp_server.py -v
```

### With Coverage
```bash
uv run pytest tests/ --cov=forensicapi
```

## Test Philosophy

Following FastMCP conventions:
- Focus on functionality over complex mocking
- Test that tools are registered and accessible
- Verify server can start and respond to MCP protocol
- Integration tests ensure the package works when installed

## Continuous Integration

Tests run automatically via GitHub Actions on:
- Every push to main branch
- Every pull request
- Before PyPI releases

## Known Issues

- Some warnings from dependencies (spacy/weasel) - these are harmless
- Complex mocking of async MCP tools is avoided in favor of integration tests

## Adding New Tests

When adding new MCP tools:
1. Add the tool name to the expected tools list in `test_mcp_server.py`
2. Create integration tests that use the tool
3. Ensure tests pass before committing