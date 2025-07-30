"""Integration tests for temporal scoring behavior."""

import asyncio
import math
from typing import Dict, Any

from hippo.server import HippoServer
from hippo.mocks import InMemoryStorage, TimeController
from hippo.constants import (
    RECENCY_DECAY_RATE,
    FREQUENCY_WINDOW_DAYS,
    UPVOTE_MULTIPLIER,
    DOWNVOTE_MULTIPLIER,
)


class TestTemporalScoring:
    """Integration tests for temporal scoring through MCP server interface."""
    
    def setup_method(self):
        """Set up test environment for each test."""
        self.storage = InMemoryStorage()
        
        # Create server with our in-memory storage directly
        # No FileBasedStorage created, no threads, no cleanup needed
        self.server = HippoServer(storage=self.storage)
        
        self.time_ctrl = TimeController(self.storage)
    
    def teardown_method(self):
        """Clean up after each test."""
        # Use HippoServer's context manager exit for proper cleanup
        self.server.__exit__(None, None, None)
    
    async def create_insight(self, content: str, situation: list = None, importance: float = 0.8) -> str:
        """Helper to create insight and return UUID."""
        if situation is None:
            situation = ["testing"]
        
        args = {
            "content": content,
            "situation": situation,
            "importance": importance,
        }
        
        result = await self.server._record_insight(args)
        # Extract UUID from result text (format: "Created insight: uuid")
        return result[0].text.split(": ")[1]
    
    async def search_insights(self, query: str = "", situation_filter: list = None) -> Dict[str, Any]:
        """Helper to search insights and return parsed results."""
        args = {
            "query": query,
            "situation_filter": situation_filter or [],
            "limit": {"offset": 0, "count": 10},
        }
        
        result = await self.server._search_insights(args)
        import json
        return json.loads(result[0].text)
    
    async def test_recency_decay_over_time(self):
        """Test that recency score decays exponentially over time."""
        # Create insight on day 1
        insight_uuid = await self.create_insight("test insight for recency")
        
        # Search immediately - should have high recency (close to 1.0)
        results = await self.search_insights("test insight")
        initial_relevance = results["insights"][0]["relevance"]
        
        # Advance 10 days and search again
        self.time_ctrl.advance_days(10)
        results = await self.search_insights("test insight")
        day_10_relevance = results["insights"][0]["relevance"]
        
        # Advance another 10 days (20 total)
        self.time_ctrl.advance_days(10)
        results = await self.search_insights("test insight")
        day_20_relevance = results["insights"][0]["relevance"]
        
        # Relevance should decrease over time due to recency decay
        assert initial_relevance > day_10_relevance > day_20_relevance
        
        # Verify exponential decay pattern
        # Expected recency at day 10: exp(-0.05 * 10) ≈ 0.606
        # Expected recency at day 20: exp(-0.05 * 20) ≈ 0.368
        expected_recency_10 = math.exp(-RECENCY_DECAY_RATE * 10)
        expected_recency_20 = math.exp(-RECENCY_DECAY_RATE * 20)
        
        print(f"Initial relevance: {initial_relevance:.3f}")
        print(f"Day 10 relevance: {day_10_relevance:.3f} (expected recency: {expected_recency_10:.3f})")
        print(f"Day 20 relevance: {day_20_relevance:.3f} (expected recency: {expected_recency_20:.3f})")
    
    async def test_frequency_calculation_with_window(self):
        """Test frequency calculation using 30-day sliding window."""
        # Create insight
        insight_uuid = await self.create_insight("frequency test insight")
        
        # Access it multiple times on different days within 30-day window
        for day in [1, 3, 5, 7, 10]:
            self.time_ctrl.set_day(day)
            await self.search_insights("frequency test")  # This records access
        
        # Check frequency at day 10 (should include all accesses)
        self.time_ctrl.set_day(10)
        results = await self.search_insights("frequency test")
        day_10_relevance = results["insights"][0]["relevance"]
        
        # Jump to day 40 (beyond 30-day window from first access)
        self.time_ctrl.set_day(40)
        results = await self.search_insights("frequency test")
        day_40_relevance = results["insights"][0]["relevance"]
        
        # Access again on day 40 to create recent activity
        await self.search_insights("frequency test")
        results = await self.search_insights("frequency test")
        day_40_with_access_relevance = results["insights"][0]["relevance"]
        
        print(f"Day 10 relevance (5 accesses in window): {day_10_relevance:.3f}")
        print(f"Day 40 relevance (old accesses outside window): {day_40_relevance:.3f}")
        print(f"Day 40 with new access: {day_40_with_access_relevance:.3f}")
        
        # Frequency should be higher when recent accesses are in the window
        assert day_40_with_access_relevance > day_40_relevance
    
    async def test_reinforcement_learning(self):
        """Test upvote/downvote reinforcement effects."""
        # Create insight
        insight_uuid = await self.create_insight("reinforcement test", importance=0.5)
        
        # Get baseline relevance
        results = await self.search_insights("reinforcement test")
        baseline_relevance = results["insights"][0]["relevance"]
        baseline_importance = results["insights"][0]["current_importance"]  # Use current_importance
        
        # Upvote the insight
        args = {"uuid": insight_uuid, "reinforce": "upvote"}
        await self.server._modify_insight(args)
        
        # Check relevance after upvote
        results = await self.search_insights("reinforcement test")
        upvoted_relevance = results["insights"][0]["relevance"]
        upvoted_importance = results["insights"][0]["current_importance"]  # Use current_importance
        
        # Create another insight to test downvote
        downvote_uuid = await self.create_insight("downvote test", importance=0.5)
        
        # Downvote it
        args = {"uuid": downvote_uuid, "reinforce": "downvote"}
        await self.server._modify_insight(args)
        
        # Check relevance after downvote
        results = await self.search_insights("downvote test")
        downvoted_relevance = results["insights"][0]["relevance"]
        downvoted_importance = results["insights"][0]["current_importance"]  # Use current_importance
        
        print(f"Baseline: relevance={baseline_relevance:.3f}, importance={baseline_importance:.3f}")
        print(f"Upvoted: relevance={upvoted_relevance:.3f}, importance={upvoted_importance:.3f}")
        print(f"Downvoted: relevance={downvoted_relevance:.3f}, importance={downvoted_importance:.3f}")
        
        # Verify reinforcement effects (with floating point tolerance)
        expected_upvoted = min(1.0, baseline_importance * UPVOTE_MULTIPLIER)
        expected_downvoted = baseline_importance * DOWNVOTE_MULTIPLIER
        
        assert abs(upvoted_importance - expected_upvoted) < 0.001
        assert abs(downvoted_importance - expected_downvoted) < 0.001
        assert upvoted_relevance > baseline_relevance
        assert downvoted_relevance < baseline_relevance
    
    async def test_search_distribution_accuracy(self):
        """Test that search distribution matches actual relevance scores."""
        # Create insights with different characteristics
        insights = [
            ("high importance recent", ["testing"], 0.9),
            ("medium importance old", ["debugging"], 0.6),
            ("low importance recent", ["coding"], 0.3),
        ]
        
        uuids = []
        for content, situation, importance in insights:
            uuid = await self.create_insight(content, situation, importance)
            uuids.append(uuid)
        
        # Access some insights to create different recency/frequency patterns
        await self.search_insights("high importance")  # Access first insight
        
        self.time_ctrl.advance_days(15)
        await self.search_insights("low importance")   # Access third insight
        
        self.time_ctrl.advance_days(10)  # Now at day 26
        
        # Get search results and distribution
        results = await self.search_insights("")  # Search all
        distribution = results["relevance_distribution"]
        
        # Verify distribution bins match actual relevance scores
        actual_relevances = [insight["relevance"] for insight in results["insights"]]
        
        # Count insights in each bin manually
        expected_distribution = {
            "below_0.2": 0,
            "0.2_to_0.4": 0,
            "0.4_to_0.6": 0,
            "0.6_to_0.8": 0,
            "0.8_to_1.0": 0,
            "above_1.0": 0,
        }
        
        for relevance in actual_relevances:
            if relevance < 0.2:
                expected_distribution["below_0.2"] += 1
            elif relevance < 0.4:
                expected_distribution["0.2_to_0.4"] += 1
            elif relevance < 0.6:
                expected_distribution["0.4_to_0.6"] += 1
            elif relevance < 0.8:
                expected_distribution["0.6_to_0.8"] += 1
            elif relevance <= 1.0:
                expected_distribution["0.8_to_1.0"] += 1
            else:
                expected_distribution["above_1.0"] += 1
        
        print(f"Actual relevances: {[f'{r:.3f}' for r in actual_relevances]}")
        print(f"Expected distribution: {expected_distribution}")
        print(f"Actual distribution: {distribution}")
        
        # Distribution should match our manual calculation
        assert distribution == expected_distribution


# Example of how to run tests
async def run_tests():
    """Run all temporal scoring tests."""
    test_instance = TestTemporalScoring()
    
    tests = [
        test_instance.test_recency_decay_over_time,
        test_instance.test_frequency_calculation_with_window,
        test_instance.test_reinforcement_learning,
        test_instance.test_search_distribution_accuracy,
    ]
    
    for test in tests:
        print(f"\n=== Running {test.__name__} ===")
        test_instance.setup_method()  # Fresh setup for each test
        try:
            await test()
            print("✅ PASSED")
        except Exception as e:
            print(f"❌ FAILED: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(run_tests())
