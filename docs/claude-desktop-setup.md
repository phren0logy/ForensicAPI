# Claude Desktop Setup Guide

This guide walks you through setting up ForensicAPI with Claude Desktop for privacy-preserving document processing.

## Prerequisites

- Claude Desktop installed
- macOS, Windows, or Linux

## Step 1: Install UVX

UVX is required to run ForensicAPI. It's a modern Python application installer that handles everything automatically.

### macOS/Linux

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Windows

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

After installation, restart your terminal or run:
- macOS/Linux: `source ~/.bashrc` (or `~/.zshrc`)
- Windows: Restart PowerShell

## Step 2: Test ForensicAPI

Verify the installation works:

```bash
uvx forensicapi --help
```

You should see the ForensicAPI help message.

## Step 3: Configure Claude Desktop

### Find Your Configuration File

The location depends on your operating system:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

**Note**: If the file doesn't exist, create it with the configuration below.

### Basic Configuration (Local Processing Only)

Edit the configuration file to add ForensicAPI:

```json
{
  "mcpServers": {
    "forensic-api": {
      "command": "uvx",
      "args": ["forensicapi"]
    }
  }
}
```

**Alternative**: If you have ForensicAPI installed locally via pip, you can use:
```json
{
  "mcpServers": {
    "forensic-api": {
      "command": "forensicapi"
    }
  }
}
```

### Advanced Configuration (With Azure Document Intelligence)

For faster PDF processing, add Azure credentials:

```json
{
  "mcpServers": {
    "forensic-api": {
      "command": "uvx",
      "args": ["forensicapi"],
      "env": {
        "AZURE_DI_KEY": "your-api-key-here",
        "AZURE_DI_ENDPOINT": "https://your-resource.cognitiveservices.azure.com/"
      }
    }
  }
}
```

**Getting Azure Credentials:**
1. Create an Azure account (free tier available)
2. Create a "Document Intelligence" resource
3. Copy the KEY and ENDPOINT from the resource page

### Configuration with Filesystem Access

ForensicAPI works great with the filesystem MCP server:

```json
{
  "mcpServers": {
    "forensic-api": {
      "command": "uvx",
      "args": ["forensicapi"]
    },
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/Users/yourname/Documents"
      ]
    }
  }
}
```

This allows Claude to:
1. Read files using the filesystem server
2. Process them with ForensicAPI
3. Save results back to disk

## Step 4: Restart Claude Desktop

After saving the configuration:

1. Quit Claude Desktop completely
2. Start Claude Desktop again
3. Look for the hammer icon (🔨) in the chat interface - this indicates MCP servers are loaded
4. You should see "forensic-api" in the MCP servers list

## Step 5: First Use

Test the integration:

```
You: "Can you help me anonymize documents?"

Claude: "Yes! I have access to ForensicAPI which can help anonymize your documents. 
I can:
- Anonymize PDFs, Word docs, and other formats
- Ensure consistent replacements (same name → same fake name everywhere)
- Create a secure vault for restoration
- Process entire folders at once

What documents would you like me to anonymize?"
```

## Common Workflows

### Single Document Anonymization

```
You: "Anonymize the contract at /Users/john/contract.pdf"

Claude: [Uses anonymize_documents tool]
Result: Creates /Users/john/output/anonymized/contract.md with vault.json
```

### Batch Processing

```
You: "Anonymize all PDFs in my legal folder"

Claude: [Uses anonymize_documents with directory parameter]
Result: Processes all PDFs, maintains consistency across documents
```

### Extract and Analyze

```
You: "Extract and summarize /Reports/annual-report.pdf"

Claude: [Uses extract_document, then segment_document if needed]
Result: Markdown version ready for analysis
```

## Troubleshooting

### "MCP server not found"

1. Check the configuration file path is correct
2. Ensure JSON syntax is valid (no trailing commas)
3. Restart Claude Desktop

### "uvx: command not found"

UVX isn't in your PATH. Try:
- Restart your terminal
- Run the install command again
- Check installation: `which uvx` (macOS/Linux) or `where uvx` (Windows)

### "Model download in progress"

The first anonymization downloads the AI4Privacy model (134MB). This is one-time only.

### Azure Errors

- Check your API key and endpoint are correct
- Ensure the endpoint includes `https://` and trailing `/`
- Verify your Azure subscription is active

## Security Notes

- **Vault files**: Keep `vault.json` files secure - they contain restoration mappings
- **Local processing**: Use local mode for maximum privacy
- **Azure credentials**: Never share your API keys
- **Output review**: Always check anonymized content before sharing

## Advanced Tips

### Custom Working Directory

To change where ForensicAPI runs:

```json
{
  "mcpServers": {
    "forensic-api": {
      "command": "uvx",
      "args": ["forensicapi"],
      "cwd": "/Users/yourname/Documents/secure"
    }
  }
}
```

### Debug Mode

For troubleshooting:

```json
{
  "mcpServers": {
    "forensic-api": {
      "command": "uvx",
      "args": ["forensicapi", "--debug"]
    }
  }
}
```

### Multiple Instances

Run separate instances for different security levels:

```json
{
  "mcpServers": {
    "forensic-api-public": {
      "command": "uvx",
      "args": ["forensicapi"],
      "cwd": "/Users/yourname/Public"
    },
    "forensic-api-private": {
      "command": "uvx",
      "args": ["forensicapi"],
      "cwd": "/Users/yourname/Private"
    }
  }
}
```

## Getting Help

- **GitHub Issues**: [Report bugs or request features](https://github.com/yourusername/forensicapi/issues)
- **Implementation Details**: See [implementation_plan.md](../design_docs/implementation_plan.md)
- **API Reference**: See [api-reference.md](api-reference.md)

---

Ready to protect your sensitive documents? Start using ForensicAPI in Claude Desktop today!