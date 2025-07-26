"""Data models for Hippo insights."""

from __future__ import annotations

import math
from datetime import datetime, timezone, date
from typing import List, Optional, Tuple
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Insight(BaseModel):
    """An insight generated during AI-human collaboration."""
    
    uuid: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for the insight"
    )
    content: str = Field(
        description="The insight content - should be atomic and actionable"
    )
    situation: List[str] = Field(
        description="Array of independent situational aspects describing when/where this insight occurred"
    )
    importance: float = Field(
        ge=0.0,
        le=1.0,
        description="AI-assessed importance rating: 0.8+ breakthrough, 0.6-0.7 useful, 0.4-0.5 incremental, 0.1-0.3 routine"
    )
    created_at: datetime = Field(
        description="When the insight was first generated (never changes)"
    )
    content_last_modified_at: datetime = Field(
        description="When the content or context was last edited"
    )
    importance_last_modified_at: datetime = Field(
        description="When the importance was last explicitly changed (upvote/downvote)"
    )
    daily_access_counts: List[Tuple[int, int]] = Field(
        default_factory=list,
        description="List of (active_day, access_count) pairs, max 90 entries, oldest first. Active days are calendar days when the system was actually used (vacation-proof)."
    )
    
    @classmethod
    def create(
        cls,
        content: str,
        situation: List[str],
        importance: float,
        current_active_day: int,
    ) -> Insight:
        """Create a new insight with current timestamp and record creation as first access."""
        now = datetime.now(timezone.utc)
        insight = cls(
            content=content,
            situation=situation,
            importance=importance,
            created_at=now,
            content_last_modified_at=now,
            importance_last_modified_at=now,
        )
        # 💡: Treat creation as the first access event - this eliminates the need for
        # special handling of never-accessed insights in recency calculations
        insight.daily_access_counts = [(current_active_day, 1)]
        return insight
    
    def compute_current_importance(self) -> float:
        """
        Compute the current importance based on temporal decay.
        
        Formula: current_importance = base_importance * recency_factor
        where recency_factor = 0.9 ^ days_since_importance_last_modified
        """
        now = datetime.now(timezone.utc)
        days_elapsed = (now - self.importance_last_modified_at).total_seconds() / 86400
        recency_factor = math.pow(0.9, days_elapsed)
        return self.importance * recency_factor
    
    def days_since_created(self) -> float:
        """Calculate days since creation."""
        now = datetime.now(timezone.utc)
        return (now - self.created_at).total_seconds() / 86400
    
    def days_since_importance_modified(self) -> float:
        """Calculate days since importance was last modified."""
        now = datetime.now(timezone.utc)
        return (now - self.importance_last_modified_at).total_seconds() / 86400
    
    def apply_reinforcement(self, multiplier: float) -> None:
        """
        Apply reinforcement (upvote/downvote) to the insight.
        
        Args:
            multiplier: Importance multiplier (1.5 for upvote, 0.5 for downvote)
        """
        current_importance = self.compute_current_importance()
        self.importance = min(1.0, current_importance * multiplier)  # Cap at 1.0
        self.importance_last_modified_at = datetime.now(timezone.utc)
    
    def record_access(self, current_active_day: int) -> None:
        """
        Record an access to this insight on the given active day.
        
        Args:
            current_active_day: The current active day counter
        """
        # 💡: Using active day counter instead of calendar time to handle vacation periods
        # where the system isn't used - insights don't decay during inactive periods
        
        # Find today's entry in the access counts list
        if self.daily_access_counts and self.daily_access_counts[-1][0] == current_active_day:
            # Increment existing entry for today
            day, count = self.daily_access_counts[-1]
            self.daily_access_counts[-1] = (day, count + 1)
        else:
            # Add new entry for today
            self.daily_access_counts.append((current_active_day, 1))
        
        # Trim list to max 90 entries (remove oldest)
        if len(self.daily_access_counts) > 90:
            self.daily_access_counts.pop(0)
    
    def calculate_frequency(self, current_active_day: int, window_days: int = 30) -> float:
        """
        Calculate frequency as accesses per active day over a recent window.
        
        Args:
            current_active_day: Current active day counter
            window_days: Number of recent active days to consider (default 30)
            
        Returns:
            Average accesses per active day over the recent window, or 0.0 if no access history
        """
        if not self.daily_access_counts:
            return 0.0
        
        # 💡: Use recent window instead of full history to avoid frequency dilution
        # from long gaps. An insight accessed twice in 30 days should have higher
        # frequency than one accessed once in 1 day.
        window_start = current_active_day - window_days + 1
        recent_entries = [
            (day, count) for day, count in self.daily_access_counts 
            if day >= window_start
        ]
        
        if not recent_entries:
            return 0.0
        
        oldest_recent_day = recent_entries[0][0]
        newest_recent_day = recent_entries[-1][0]
        recent_days_spanned = newest_recent_day - oldest_recent_day + 1
        total_recent_accesses = sum(count for _, count in recent_entries)
        
        return total_recent_accesses / recent_days_spanned
    
    def calculate_recency_score(self, current_active_day: int, decay_rate: float = 0.05) -> float:
        """
        Calculate recency score using exponential decay based on active days since last access.
        
        Args:
            current_active_day: Current active day counter
            decay_rate: Decay rate per active day (default 0.05)
            
        Returns:
            Recency score between 0.0 and 1.0
        """
        if not self.daily_access_counts:
            # This should never happen since creation records first access,
            # but handle gracefully just in case
            return 0.0
        
        last_access_day = self.daily_access_counts[-1][0]
        active_days_since_access = current_active_day - last_access_day
        return math.exp(-decay_rate * active_days_since_access)
    
    def update_content(
        self,
        content: Optional[str] = None,
        situation: Optional[List[str]] = None,
        importance: Optional[float] = None,
    ) -> None:
        """Update insight content and/or metadata."""
        if content is not None:
            self.content = content
            self.content_last_modified_at = datetime.now(timezone.utc)
        if situation is not None:
            self.situation = situation
            self.content_last_modified_at = datetime.now(timezone.utc)
        if importance is not None:
            self.importance = importance


class HippoStorage(BaseModel):
    """Storage format for Hippo insights."""
    
    insights: List[Insight] = Field(
        default_factory=list,
        description="List of all insights in the system"
    )
    active_day_counter: int = Field(
        default=0,
        description="Counter of active days - increments each calendar day the system is used"
    )
    last_calendar_date_used: Optional[date] = Field(
        default=None,
        description="Last calendar date the system was used (to detect new active days)"
    )
    
    def get_current_active_day(self) -> int:
        """
        Get the current active day, incrementing the counter if this is a new calendar day.
        
        Returns:
            Current active day counter
        """
        today = date.today()
        
        # If this is the first use ever, or a new calendar day, increment counter
        if self.last_calendar_date_used != today:
            self.active_day_counter += 1
            self.last_calendar_date_used = today
        
        return self.active_day_counter
    
    def add_insight(self, insight: Insight) -> None:
        """Add a new insight to storage."""
        self.insights.append(insight)
    
    def find_by_uuid(self, uuid: UUID) -> Optional[Insight]:
        """Find an insight by UUID."""
        for insight in self.insights:
            if insight.uuid == uuid:
                return insight
        return None
    
    def remove_by_uuid(self, uuid: UUID) -> bool:
        """Remove an insight by UUID. Returns True if found and removed."""
        for i, insight in enumerate(self.insights):
            if insight.uuid == uuid:
                del self.insights[i]
                return True
        return False