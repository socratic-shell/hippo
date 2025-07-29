"""Test mocks and utilities for Hippo testing."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from .models import Insight, HippoStorage


class InMemoryStorage(HippoStorage):
    """In-memory storage implementation for testing without disk I/O."""
    
    def __init__(self, initial_active_day: int = 1):
        """Initialize with empty insights and controllable active day."""
        # 💡: Start with day 1 rather than 0 to make test scenarios more intuitive
        # Call parent constructor with proper Pydantic initialization
        super().__init__(
            insights=[],
            active_day_counter=initial_active_day,
            last_calendar_date_used=None
        )
    
    async def load(self):
        """Return self for compatibility with JsonStorage interface."""
        return self
    
    async def save(self):
        """No-op for in-memory storage."""
        pass


class TimeController:
    """Controller for managing time in test scenarios."""
    
    def __init__(self, storage: InMemoryStorage):
        """Initialize with storage instance to control."""
        self.storage = storage
    
    def advance_days(self, days: int) -> int:
        """
        Advance the active day counter by the specified number of days.
        
        Args:
            days: Number of days to advance
            
        Returns:
            New current active day
        """
        # 💡: Advance active day counter to simulate passage of time
        # This affects recency and frequency calculations without requiring
        # actual time to pass during tests
        self.storage.active_day_counter += days
        return self.storage.active_day_counter
    
    def set_day(self, day: int) -> int:
        """
        Set the active day counter to a specific value.
        
        Args:
            day: Day to set as current
            
        Returns:
            New current active day
        """
        # 💡: Direct day setting for test scenarios that need specific timing
        self.storage.active_day_counter = day
        return self.storage.active_day_counter
    
    def get_current_day(self) -> int:
        """Get the current active day."""
        return self.storage.active_day_counter
