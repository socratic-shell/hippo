# Hippo: AI-Generated Insights Memory System

An MCP server that implements an AI memory system using reinforcement learning to surface valuable insights from conversations.

## Installation

```bash
# Install proto toolchain manager
curl -L https://moonrepo.dev/install/proto.sh | bash

# Install uv via proto
proto install

# Install dependencies
cd hippo
uv sync
```

## Usage

Run the MCP server:

```bash
uv run hippo-server --hippo-file /path/to/hippo.json
```

Or use the installed script after `uv sync`:

```bash
hippo-server --hippo-file /path/to/hippo.json
```

## Development

Run type checking:

```bash
uv run mypy py/hippo
```

Run tests:

```bash
uv run pytest
```

## MCP Tools

The server provides four MCP tools:

- `hippo_record_insight` - Record new insights during consolidation moments
- `hippo_search_insights` - Search insights with fuzzy context matching
- `hippo_modify_insight` - Modify existing insights
- `hippo_reinforce_insight` - Apply upvotes/downvotes to insights

See the [design documentation](src/design-doc.md) for detailed specifications.