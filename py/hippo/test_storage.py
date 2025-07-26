"""In-memory storage implementation for testing."""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from .models import Insight
from .storage import HippoStorage


class InMemoryStorage(HippoStorage):
    """In-memory storage implementation for testing without disk I/O."""
    
    def __init__(self, initial_active_day: int = 1):
        """Initialize with empty insights and controllable active day."""
        # 💡: Start with day 1 rather than 0 to make test scenarios more intuitive
        self.insights: List[Insight] = []
        self.current_active_day = initial_active_day
    
    async def load_insights(self) -> List[Insight]:
        """Return current insights list."""
        return self.insights.copy()
    
    async def save_insights(self, insights: List[Insight]) -> None:
        """Update the insights list."""
        self.insights = insights.copy()
    
    async def add_insight(self, insight: Insight) -> None:
        """Add a new insight to the list."""
        self.insights.append(insight)
    
    async def update_insight(self, updated_insight: Insight) -> None:
        """Update an existing insight by UUID."""
        for i, insight in enumerate(self.insights):
            if insight.uuid == updated_insight.uuid:
                self.insights[i] = updated_insight
                return
        raise ValueError(f"Insight with UUID {updated_insight.uuid} not found")
    
    async def get_insight_by_uuid(self, uuid: UUID) -> Optional[Insight]:
        """Get insight by UUID."""
        for insight in self.insights:
            if insight.uuid == uuid:
                return insight
        return None
    
    def get_current_active_day(self) -> int:
        """Return the current active day counter."""
        return self.current_active_day
    
    def advance_active_day(self, days: int = 1) -> None:
        """Advance the active day counter (for testing)."""
        self.current_active_day += days
    
    async def get_all_insights(self) -> List[Insight]:
        """Return all insights."""
        return self.insights.copy()
