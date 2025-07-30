# MCP Server Setup

This guide shows you how to connect Hippo to your AI tool via the Model Context Protocol (MCP).

## Quick Setup Commands

### For Q CLI

Add Hippo to your Q CLI configuration:

```bash
# Create data directory
mkdir -p ~/.hippo

# Add server (replace /path/to/hippo with your actual path)
q configure add-server hippo "uv run --directory /path/to/hippo python -m hippo.server --hippo-file ~/.hippo/hippo.json"

# Add guidance to global context
q context add --global /path/to/hippo/guidance.md
```

### For Claude Desktop

Add this to your Claude Desktop configuration file:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`  
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "hippo": {
      "command": "uv",
      "args": [
        "run", 
        "--directory", "/path/to/hippo",
        "python", "-m", "hippo.server", 
        "--hippo-file", "~/.hippo/hippo.json"
      ]
    }
  }
}
```

Or using Docker:

```json
{
  "mcpServers": {
    "hippo": {
      "command": "podman",
      "args": [
        "run", "--rm", "-i",
        "-v", "/path/to/hippo/data:/data:Z",
        "hippo-server",
        "uv", "run", "python", "-m", "hippo.server",
        "--hippo-file", "/data/hippo.json"
      ]
    }
  }
}
```

## Setup Steps

### 1. Choose Your Installation Method

**Option A: Direct Installation (Recommended)**
```bash
# Clone the repository
git clone https://github.com/socratic-shell/hippo.git
cd hippo

# Install dependencies
uv sync

# Create data directory
mkdir -p data

# Test the server
uv run python -m py.hippo.server --hippo-file ./data/hippo.json
```

**Option B: Docker Installation**
```bash
# Clone the repository
git clone https://github.com/socratic-shell/hippo.git
cd hippo

# Build the image
podman build -t hippo-server .
# or: docker build -t hippo-server .

# Create data directory
mkdir -p data

# Test the server
podman run --rm -i -v ./data:/data:Z hippo-server
# or: docker run --rm -i -v ./data:/data hippo-server
```

### 2. Configure Your AI Tool

Use the appropriate configuration from the "Quick Setup Commands" section above, replacing `/path/to/hippo` with your actual installation path.

### 3. Restart Your AI Tool

After updating the configuration, restart your AI tool to load the Hippo MCP server.

### 4. Test the Connection

In your AI tool, try using one of the Hippo tools:

```
Can you search for any existing insights about "memory systems"?
```

The AI should respond using the `hippo_search_insights` tool. If you get an error about the tool not being available, check your configuration and paths.

## Troubleshooting

### "Command not found" errors

- **uv not found**: Install uv with `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **podman/docker not found**: Install your preferred container runtime
- **Path issues**: Use absolute paths in your configuration

### "Permission denied" errors

- **Linux/macOS**: Ensure the data directory is writable: `chmod 755 data`
- **SELinux systems**: Use the `:Z` flag in volume mounts for containers

### "Server not responding" errors

- Test the server manually first: `uv run python -m py.hippo.server --hippo-file ./data/hippo.json`
- Check that the hippo.json file is created and writable
- Verify all paths in your configuration are correct

### "Tool not available" errors

- Restart your AI tool after configuration changes
- Check the AI tool's logs for MCP connection errors
- Verify the server starts without errors when run manually

## Data Storage

Hippo stores all insights in a single JSON file specified by `--hippo-file`. This file:

- Is created automatically if it doesn't exist
- Should be backed up regularly (it contains all your insights)
- Can be moved or copied to different machines
- Grows over time as you record more insights

## Security Notes

- The hippo.json file contains your conversation insights - treat it as sensitive data
- When using Docker, the container runs as root by default - consider user mapping for production
- MCP servers run locally and don't send data over the network
