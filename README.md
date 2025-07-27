# Hippo: AI-Generated Insights Memory System

An experiment in collaborative memory through reinforcement learning.

Hippo is a memory system designed to let insights emerge organically through usage patterns. It supplies the LLM with tools to record insights and then later to indicate which ones are useful via up/down-voting (similar to reddit or stack overflow) and to make edits.

## Quick Start

### Connect to Your AI Tool

**For Q CLI:**
```bash
q configure add-server hippo "uv run --directory /path/to/hippo python -m py.hippo.server --hippo-file /path/to/hippo/data/hippo.json"
```

**For Claude Desktop:** Add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "hippo": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/hippo", "python", "-m", "py.hippo.server", "--hippo-file", "/path/to/hippo/data/hippo.json"]
    }
  }
}
```

See [MCP Server Setup](md/mcp-setup.md) for complete installation instructions.

### Alternative: Docker/Podman

```bash
# Build and run
podman build -t hippo-server .
mkdir -p ./data
podman run -d --name hippo -p 8080:8080 -v ./data:/data:Z hippo-server
```

### Using uv directly

```bash
# Install dependencies
uv sync

# Run the server
uv run python -m py.hippo.server --hippo-file ./hippo.json
```

## Documentation

See the `md/` directory for comprehensive documentation:

- [MCP Server Setup](md/mcp-setup.md) - **Connect Hippo to your AI tool**
- [Introduction](md/introduction.md) - What is Hippo and why
- [How to Use It](md/how-to-use.md) - Usage guide for AI assistants
- [Docker Usage](md/docker.md) - Container deployment guide
- [Design Document](md/design-doc.md) - Deep concepts and philosophy

## Testing

Run the integration test suite:

```bash
uv run python -m tests.test_temporal_scoring
```

## Status

Prototype implementation.
