"""JSON file storage for Hippo insights."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import aiofiles

from .models import HippoStorage, Insight


class JsonStorage:
    """Async JSON file storage for insights."""
    
    def __init__(self, file_path: Path) -> None:
        """Initialize storage with file path."""
        self.file_path = file_path
        self._data: Optional[HippoStorage] = None
    
    async def load(self) -> HippoStorage:
        """Load insights from JSON file, creating if necessary."""
        if self._data is not None:
            return self._data
            
        if not self.file_path.exists():
            self._data = HippoStorage()
            await self.save()
            return self._data
        
        try:
            async with aiofiles.open(self.file_path, 'r') as f:
                content = await f.read()
                data = json.loads(content)
                self._data = HippoStorage.model_validate(data)
        except (json.JSONDecodeError, ValueError) as e:
            # If file is corrupted, start fresh but backup the old one
            backup_path = self.file_path.with_suffix('.json.backup')
            self.file_path.rename(backup_path)
            self._data = HippoStorage()
            await self.save()
            
        return self._data
    
    async def save(self) -> None:
        """Save current insights to JSON file."""
        if self._data is None:
            return
            
        # Ensure directory exists
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write to temporary file first for atomicity
        temp_path = self.file_path.with_suffix('.json.tmp')
        
        async with aiofiles.open(temp_path, 'w') as f:
            json_data = self._data.model_dump_json(
                indent=2,
                by_alias=False,
            )
            await f.write(json_data)
        
        # Atomic rename
        temp_path.rename(self.file_path)
    
    async def add_insight(self, insight: Insight) -> None:
        """Add an insight and save to disk."""
        data = await self.load()
        await data.add_insight(insight)
        await self.save()
    
    async def update_insight(self, insight: Insight) -> bool:
        """Update an existing insight. Returns True if found."""
        data = await self.load()
        existing = data.find_by_uuid(insight.uuid)
        if existing is None:
            return False
        
        # Replace with updated version
        data.remove_by_uuid(insight.uuid)
        await data.add_insight(insight)
        await self.save()
        return True
    
    async def get_all_insights(self) -> list[Insight]:
        """Get all insights from storage."""
        data = await self.load()
        return data.insights