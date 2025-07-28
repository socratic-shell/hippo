"""Basic MCP integration tests for Hippo server."""

import tempfile
from pathlib import Path

import pytest

from hippo.server import HippoServer


@pytest.mark.asyncio
async def test_record_and_search_insight():
    """Test basic record and search functionality with file storage."""
    # Create temporary storage for file-based testing
    with tempfile.TemporaryDirectory() as temp_dir:
        storage_path = Path(temp_dir) / "hippo.json"
        server = HippoServer(storage_path=storage_path)
        
        # Record an insight
        record_result = await server._record_insight({
            "content": "My favorite programming language is Rust",
            "situation": ["programming discussion", "language preferences"],
            "importance": 0.7
        })
        
        # Check recording succeeded
        assert len(record_result) == 1
        assert "Recorded insight with UUID:" in record_result[0].text
        
        # Search for the insight
        search_result = await server._search_insights({
            "query": "programming language Rust",
            "limit": {"offset": 0, "count": 5}
        })
        
        # Check search found it
        assert len(search_result) == 1
        search_text = search_result[0].text
        assert "Rust" in search_text
        assert "programming" in search_text
