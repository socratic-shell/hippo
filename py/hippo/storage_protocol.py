"""Storage protocol interface for Hippo storage implementations."""

from typing import Protocol, List
from uuid import UUID

from .models import Insight


class StorageProtocol(Protocol):
    """Protocol defining the interface that all Hippo storage implementations must follow.
    
    This ensures type safety and consistency between FileBasedStorage, InMemoryStorage,
    and any future storage implementations.
    """
    
    async def get_all_insights(self) -> List[Insight]:
        """Get all insights from storage."""
        ...
    
    async def get_current_active_day(self) -> int:
        """Get the current active day counter."""
        ...
    
    async def add_insight(self, insight: Insight) -> None:
        """Add a new insight to storage."""
        ...
    
    async def store_insight(self, insight: Insight) -> None:
        """Store/update an insight in storage."""
        ...
    
    async def record_insight_access(self, uuid: UUID) -> None:
        """Record that an insight was accessed."""
        ...
    
    def __enter__(self):
        """Context manager entry."""
        ...
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        ...
