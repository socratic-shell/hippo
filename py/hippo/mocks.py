"""Test mocks and utilities for Hippo testing."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from .models import Insight, HippoStorage


class InMemoryStorage(HippoStorage):
    """In-memory storage implementation for testing without disk I/O.
    
    Implements StorageProtocol for compatibility with HippoServer.
    """
    
    def __init__(self, initial_active_day: int = 1):
        """Initialize with empty insights and controllable active day."""
        # 💡: Start with day 1 rather than 0 to make test scenarios more intuitive
        # Call parent constructor with proper Pydantic initialization
        super().__init__(
            insights=[],
            active_day_counter=initial_active_day,
            last_calendar_date_used=None
        )
    
    # Legacy JsonStorage compatibility methods
    async def load(self):
        """Return self for compatibility with JsonStorage interface."""
        return self
    
    async def save(self):
        """No-op for in-memory storage."""
        pass
    
    # StorageProtocol implementation
    async def get_all_insights(self) -> List[Insight]:
        """Get all insights from storage."""
        return self.insights
    
    # These methods are now async in the parent class, so we can call them directly
    # No need to override since they already match the protocol
    
    async def store_insight(self, insight: Insight) -> str:
        """Store/update an insight in storage."""
        # For in-memory storage, storing is the same as adding if not exists
        existing = self.find_by_uuid(insight.uuid)
        if existing:
            # Update existing insight
            idx = self.insights.index(existing)
            self.insights[idx] = insight
        else:
            # Add new insight
            self.insights.append(insight)
        
        return str(insight.uuid)
    
    async def record_insight_access(self, uuid: UUID) -> None:
        """Record that an insight was accessed."""
        insight = self.find_by_uuid(uuid)
        if insight:
            insight.record_access(await self.get_current_active_day())
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        return False  # Don't suppress exceptions


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
