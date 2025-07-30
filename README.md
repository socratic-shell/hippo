# Hippo: AI-Generated Insights Memory System

An experiment in collaborative memory through reinforcement learning.

Hippo is a memory system designed to let insights emerge organically through usage patterns. It supplies the LLM with tools to record insights and then later to indicate which ones are useful via up/down-voting (similar to reddit or stack overflow) and to make edits.

## Prerequisites

- **Python 3.10+**
- **uv** (Python package manager) - Install from [uv installation guide](https://docs.astral.sh/uv/getting-started/installation/)

## Quick Start

### 1. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/socratic-shell/hippo.git
cd hippo

# Install dependencies
uv sync

# For development, also install dev tools (mypy, pytest, ruff)
uv sync --extra dev

# Test the installation
uv run python -m hippo.server --help

# Verify everything works
./verify-install.sh
```

### 2. Connect to Your AI Tool

**For Q CLI:**
```bash
# Create data directory
mkdir -p ~/.hippo

# Add server (replace /path/to/hippo with your actual path)
q configure add-server hippo "uv run --directory /path/to/hippo python -m hippo.server --hippo-file ~/.hippo/hippo.json"

# Add guidance to global context
q context add --global /path/to/hippo/guidance.md
```

**For Claude Desktop:** Add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "hippo": {
      "command": "uv",
      "args": [
        "run", 
        "--directory", 
        "/path/to/hippo", 
        "python", 
        "-m", 
        "hippo.server", 
        "--hippo-file", 
        "~/.hippo/hippo.json"
      ]
    }
  }
}
```

Then add `@/path/to/hippo/guidance.md` to your CLAUDE.md file.

### 3. Alternative: Docker/Podman

```bash
# Build and run
podman build -t hippo-server .
mkdir -p ./data
podman run -d --name hippo -p 8080:8080 -v ./data:/data:Z hippo-server
```

## Documentation

See the `md/` directory for comprehensive documentation:

- [Installation Guide](md/installation.md) - **Complete setup instructions**
- [Introduction](md/introduction.md) - What is Hippo and why
- [Docker Usage](md/docker.md) - Container deployment guide
- [Design Document](md/design/design-doc.md) - Deep concepts and philosophy

## Development

```bash
# Run type checking
uv run mypy py/hippo/

# Run tests
uv run pytest py/hippo/

# Run the server locally
uv run python -m hippo.server --hippo-file ./test-data.json
```

## Status

Prototype implementation.
