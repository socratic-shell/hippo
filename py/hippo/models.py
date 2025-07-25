"""Data models for Hippo insights."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import List, Optional
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
    
    @classmethod
    def create(
        cls,
        content: str,
        situation: List[str],
        importance: float,
    ) -> Insight:
        """Create a new insight with current timestamp."""
        now = datetime.now(timezone.utc)
        return cls(
            content=content,
            situation=situation,
            importance=importance,
            created_at=now,
            content_last_modified_at=now,
            importance_last_modified_at=now,
        )
    
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