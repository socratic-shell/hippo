"""Time control utilities for testing temporal behavior."""

from __future__ import annotations

from .test_storage import InMemoryStorage


class TestTimeController:
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
        self.storage.advance_active_day(days)
        return self.storage.get_current_active_day()
    
    def set_day(self, day: int) -> int:
        """
        Set the active day counter to a specific value.
        
        Args:
            day: Active day to set
            
        Returns:
            New current active day
        """
        self.storage.current_active_day = day
        return day
    
    def get_current_day(self) -> int:
        """Get the current active day."""
        return self.storage.get_current_active_day()
    
    def reset_to_day_one(self) -> int:
        """Reset time back to day 1."""
        return self.set_day(1)
