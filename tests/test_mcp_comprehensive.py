"""Comprehensive MCP integration tests for Hippo server."""

import pytest

from hippo.server import HippoServer
from hippo.mocks import InMemoryStorage, TimeController


@pytest.mark.asyncio
async def test_relevance_histogram():
    """Test search relevance scoring across multiple insights."""
    # Create server with in-memory storage
    storage = InMemoryStorage(initial_active_day=1)
    server = HippoServer(storage=storage)
    
    # Store multiple insights with varying relevance to "Rust programming"
    insights_data = [
        {
            "content": "Rust is my favorite programming language for systems programming",
            "situation": ["programming discussion", "language preferences", "systems work"],
            "importance": 0.9,
            "expected_high_relevance": True
        },
        {
            "content": "Python is great for data science and machine learning projects",
            "situation": ["programming discussion", "data science", "ML work"],
            "importance": 0.8,
            "expected_high_relevance": False
        },
        {
            "content": "Rust's ownership system prevents memory safety issues",
            "situation": ["programming concepts", "memory safety", "systems programming"],
            "importance": 0.8,
            "expected_high_relevance": True
        },
        {
            "content": "Had lunch at a great restaurant today",
            "situation": ["personal life", "food", "daily activities"],
            "importance": 0.3,
            "expected_high_relevance": False
        },
        {
            "content": "Learning Rust's async programming model is challenging but rewarding",
            "situation": ["learning", "async programming", "Rust development"],
            "importance": 0.7,
            "expected_high_relevance": True
        }
    ]
    
    # Record all insights
    for insight_data in insights_data:
        await server._record_insight({
            "content": insight_data["content"],
            "situation": insight_data["situation"],
            "importance": insight_data["importance"]
        })
    
    # Search for "Rust programming"
    search_result = await server._search_insights({
        "query": "Rust programming",
        "limit": {"offset": 0, "count": 10}
    })
    
    # Parse the search results to extract relevance scores
    assert len(search_result) == 1
    search_text = search_result[0].text
    
    # Check that high-relevance insights appear in results
    rust_insights = [d for d in insights_data if d["expected_high_relevance"]]
    for insight_data in rust_insights:
        # Should find key terms from high-relevance insights
        key_terms = insight_data["content"].split()[:3]  # First few words
        found_terms = sum(1 for term in key_terms if term.lower() in search_text.lower())
        assert found_terms > 0, f"Should find terms from: {insight_data['content']}"
    
    # Check that low-relevance insights don't dominate
    assert "lunch" not in search_text.lower(), "Low-relevance insights shouldn't appear prominently"
    assert "restaurant" not in search_text.lower(), "Low-relevance insights shouldn't appear prominently"


@pytest.mark.asyncio
async def test_temporal_scoring_and_storage():
    """Test temporal scoring behavior and storage persistence."""
    # Create server with controlled time environment
    storage = InMemoryStorage(initial_active_day=1)
    time_controller = TimeController(storage)
    server = HippoServer(storage=storage)
    
    # Record an insight on day 1
    day1_result = await server._record_insight({
        "content": "Rust memory safety is crucial for systems programming",
        "situation": ["programming", "memory safety", "systems"],
        "importance": 0.8
    })
    assert "Recorded insight with UUID:" in day1_result[0].text
    
    # Advance time to day 5
    time_controller.advance_days(4)  # Now on day 5
    assert time_controller.get_current_day() == 5
    
    # Record another insight on day 5
    day5_result = await server._record_insight({
        "content": "Rust async programming requires careful lifetime management",
        "situation": ["programming", "async", "lifetimes"],
        "importance": 0.7
    })
    assert "Recorded insight with UUID:" in day5_result[0].text
    
    # Advance time to day 10
    time_controller.advance_days(5)  # Now on day 10
    assert time_controller.get_current_day() == 10
    
    # Search for insights - more recent ones should have higher relevance
    search_result = await server._search_insights({
        "query": "Rust programming",
        "limit": {"offset": 0, "count": 10}
    })
    
    assert len(search_result) == 1
    search_text = search_result[0].text
    
    # Both insights should be found since they're relevant
    assert "memory safety" in search_text or "async programming" in search_text
    
    # Verify storage contains both insights
    all_insights = storage.get_all_insights()
    assert len(all_insights) == 2
    
    # Check that insights have different creation days
    # The creation day is stored in daily_access_counts as the first access
    creation_days = []
    for insight in all_insights:
        if insight.daily_access_counts:
            # First access day is the creation day
            first_access_day = insight.daily_access_counts[0][0]
            creation_days.append(first_access_day)
    
    assert len(creation_days) == 2, "Should have creation days for both insights"
    assert 1 in creation_days, "Should have insight from day 1"
    assert 5 in creation_days, "Should have insight from day 5"
    
    # Verify current active day is maintained
    assert storage.get_current_active_day() == 10


@pytest.mark.asyncio
async def test_situation_filtering():
    """Test situation-based filtering functionality."""
    storage = InMemoryStorage(initial_active_day=1)
    server = HippoServer(storage=storage)
    
    # Record insights with different situations
    await server._record_insight({
        "content": "Rust ownership prevents data races",
        "situation": ["programming", "concurrency", "safety"],
        "importance": 0.8
    })
    
    await server._record_insight({
        "content": "Had a great meeting about project planning",
        "situation": ["work", "meetings", "planning"],
        "importance": 0.6
    })
    
    await server._record_insight({
        "content": "Debugging memory leaks in C++ is painful",
        "situation": ["programming", "debugging", "C++"],
        "importance": 0.7
    })
    
    # Search with situation filter for programming-related insights
    programming_results = await server._search_insights({
        "query": "",
        "situation_filter": ["programming"],
        "limit": {"offset": 0, "count": 10}
    })
    
    assert len(programming_results) == 1
    results_text = programming_results[0].text
    
    # Should find programming-related insights
    assert ("Rust" in results_text or "C++" in results_text), "Should find programming insights"
    # Should not find meeting-related insights
    assert "meeting" not in results_text.lower(), "Should not find non-programming insights"


@pytest.mark.asyncio
async def test_relevance_range_filtering():
    """Test relevance range filtering functionality."""
    storage = InMemoryStorage(initial_active_day=1)
    server = HippoServer(storage=storage)
    
    # Record insights with different importance levels
    await server._record_insight({
        "content": "Critical security vulnerability discovered in authentication system",
        "situation": ["security", "critical", "authentication"],
        "importance": 0.95  # Very high importance
    })
    
    await server._record_insight({
        "content": "Minor UI improvement suggestion for login page",
        "situation": ["UI", "improvement", "login"],
        "importance": 0.3   # Low importance
    })
    
    await server._record_insight({
        "content": "Refactored authentication module for better maintainability",
        "situation": ["refactoring", "authentication", "maintenance"],
        "importance": 0.7   # Medium importance
    })
    
    # Search with high relevance range filter
    high_relevance_results = await server._search_insights({
        "query": "authentication",
        "relevance_range": {"min": 0.8},
        "limit": {"offset": 0, "count": 10}
    })
    
    assert len(high_relevance_results) == 1
    results_text = high_relevance_results[0].text
    
    # Should find high-importance insights
    assert "security vulnerability" in results_text or "Critical" in results_text
    # Should not find low-importance insights
    assert "Minor UI" not in results_text
