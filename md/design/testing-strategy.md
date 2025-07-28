# Testing Strategy

## Quick Start

```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v
```

## Philosophy

We test **MCP tool functionality directly**, not end-to-end LLM workflows. This keeps tests fast, reliable, and focused on the core API that MCP clients depend on.

## Approach

**Direct method calls**: Tests invoke the internal async methods (`_record_insight`, `_search_insights`, etc.) rather than going through MCP protocol overhead.

**Isolated storage**: Each test uses a fresh temporary directory that's automatically cleaned up.

**What we test**: The four MCP tools, storage persistence, search relevance, and error handling.

**What we don't test**: LLM prompt interpretation, tool selection, or multi-turn conversations.

Tests live in `tests/` and follow standard pytest conventions.
