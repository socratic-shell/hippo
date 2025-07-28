"""File-based storage for Hippo insights with concurrent access support."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional
from uuid import UUID

import aiofiles

from .models import HippoStorage, Insight


class FileBasedStorage:
    """
    File-based storage backend that stores each insight as a separate JSON file.
    
    This implementation provides:
    - Thread-safe concurrent access within a single process
    - Atomic writes to prevent corruption
    - In-memory caching for performance
    - UUID-based filename validation
    """
    
    def __init__(self, directory_path: Path) -> None:
        """
        Initialize file-based storage.
        
        Args:
            directory_path: Directory to store insight files and metadata
        """
        self.directory_path = directory_path
        self.insights_dir = directory_path / "insights"
        self.metadata_file = directory_path / "metadata.json"
        
        # 💡: Using RLock (reentrant lock) to allow multiple readers but exclusive writers.
        # This prevents race conditions when multiple threads access the cache simultaneously.
        self._cache_lock = threading.RLock()
        self._insights_cache: Dict[str, Insight] = {}
        self._cache_loaded = False
        
        # Metadata cache (active day counter, etc.)
        self._metadata_cache: Optional[Dict] = None
        
        # Ensure directories exist
        self.insights_dir.mkdir(parents=True, exist_ok=True)
    
    def _validate_uuid_filename(self, uuid_str: str) -> bool:
        """
        Validate that a string is a valid UUID for use as filename.
        
        Args:
            uuid_str: String to validate
            
        Returns:
            True if valid UUID string, False otherwise
        """
        try:
            UUID(uuid_str)
            return True
        except ValueError:
            return False
    
    def _get_insight_path(self, uuid: UUID) -> Path:
        """Get the file path for an insight given its UUID."""
        return self.insights_dir / f"{uuid}.json"
    
    async def _atomic_write_json(self, file_path: Path, data: dict) -> None:
        """
        Atomically write JSON data to a file using temp file + rename.
        
        This prevents partial reads if the write is interrupted.
        
        Args:
            file_path: Target file path
            data: Dictionary to write as JSON
        """
        # 💡: Using tempfile in same directory ensures atomic rename works across filesystems.
        # os.replace() is atomic on all platforms when source and dest are on same filesystem.
        temp_fd, temp_path = tempfile.mkstemp(
            suffix='.tmp',
            prefix=f'{file_path.stem}_',
            dir=file_path.parent
        )
        
        try:
            # Write to temporary file
            with os.fdopen(temp_fd, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            
            # Atomic rename
            os.replace(temp_path, file_path)
        except Exception:
            # Clean up temp file if something went wrong
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise
    
    async def _load_metadata(self) -> Dict:
        """Load metadata (active day counter, etc.) from metadata file."""
        if self._metadata_cache is not None:
            return self._metadata_cache
        
        if not self.metadata_file.exists():
            # Initialize with defaults
            self._metadata_cache = {
                "active_day_counter": 0,
                "last_calendar_date_used": None
            }
            await self._save_metadata()
            return self._metadata_cache
        
        try:
            async with aiofiles.open(self.metadata_file, 'r') as f:
                content = await f.read()
                self._metadata_cache = json.loads(content)
        except (json.JSONDecodeError, OSError) as e:
            # If corrupted, start fresh but backup
            backup_path = self.metadata_file.with_suffix('.json.backup')
            if self.metadata_file.exists():
                self.metadata_file.rename(backup_path)
            
            self._metadata_cache = {
                "active_day_counter": 0,
                "last_calendar_date_used": None
            }
            await self._save_metadata()
        
        return self._metadata_cache
    
    async def _save_metadata(self) -> None:
        """Save metadata to disk atomically."""
        if self._metadata_cache is None:
            return
        
        await self._atomic_write_json(self.metadata_file, self._metadata_cache)
    
    async def _load_insights_cache(self) -> None:
        """Load all insights from disk into memory cache."""
        with self._cache_lock:
            if self._cache_loaded:
                return
            
            self._insights_cache.clear()
            
            # Scan insights directory for JSON files
            if not self.insights_dir.exists():
                self._cache_loaded = True
                return
            
            for file_path in self.insights_dir.glob("*.json"):
                uuid_str = file_path.stem
                
                # Validate filename is a UUID
                if not self._validate_uuid_filename(uuid_str):
                    continue
                
                try:
                    async with aiofiles.open(file_path, 'r') as f:
                        content = await f.read()
                        insight_data = json.loads(content)
                        insight = Insight.model_validate(insight_data)
                        self._insights_cache[uuid_str] = insight
                except (json.JSONDecodeError, ValueError, OSError) as e:
                    # Skip corrupted files but log the issue
                    # In a production system, we might want proper logging here
                    continue
            
            self._cache_loaded = True
    
    async def get_insight(self, uuid: UUID) -> Optional[Insight]:
        """
        Get an insight by UUID.
        
        Args:
            uuid: UUID of the insight to retrieve
            
        Returns:
            Insight if found, None otherwise
        """
        await self._load_insights_cache()
        
        with self._cache_lock:
            return self._insights_cache.get(str(uuid))
    
    async def store_insight(self, insight: Insight) -> str:
        """
        Store an insight to disk and update cache.
        
        Args:
            insight: Insight to store
            
        Returns:
            UUID string of the stored insight
        """
        await self._load_insights_cache()
        
        uuid_str = str(insight.uuid)
        file_path = self._get_insight_path(insight.uuid)
        
        # Write to disk atomically
        insight_data = insight.model_dump(mode='json')
        await self._atomic_write_json(file_path, insight_data)
        
        # Update cache
        with self._cache_lock:
            self._insights_cache[uuid_str] = insight
        
        return uuid_str
    
    async def update_insight(self, uuid: UUID, updates: dict) -> bool:
        """
        Update an existing insight.
        
        Args:
            uuid: UUID of insight to update
            updates: Dictionary of fields to update
            
        Returns:
            True if insight was found and updated, False otherwise
        """
        await self._load_insights_cache()
        
        uuid_str = str(uuid)
        
        with self._cache_lock:
            insight = self._insights_cache.get(uuid_str)
            if insight is None:
                return False
            
            # Apply updates to the insight
            insight.update_content(
                content=updates.get('content'),
                situation=updates.get('situation'),
                importance=updates.get('importance')
            )
        
        # Save updated insight
        await self.store_insight(insight)
        return True
    
    async def delete_insight(self, uuid: UUID) -> bool:
        """
        Delete an insight by UUID.
        
        Args:
            uuid: UUID of insight to delete
            
        Returns:
            True if insight was found and deleted, False otherwise
        """
        await self._load_insights_cache()
        
        uuid_str = str(uuid)
        file_path = self._get_insight_path(uuid)
        
        with self._cache_lock:
            if uuid_str not in self._insights_cache:
                return False
            
            # Remove from cache
            del self._insights_cache[uuid_str]
        
        # Remove file if it exists
        try:
            file_path.unlink()
        except OSError:
            # File might not exist, that's okay
            pass
        
        return True
    
    async def get_all_insights(self) -> List[Insight]:
        """
        Get all insights from storage.
        
        Returns:
            List of all insights
        """
        await self._load_insights_cache()
        
        with self._cache_lock:
            return list(self._insights_cache.values())
    
    async def search_insights(self, query: str, filters: Optional[dict] = None) -> List[Insight]:
        """
        Search insights by content and situation.
        
        Args:
            query: Search query string
            filters: Optional filters to apply
            
        Returns:
            List of matching insights
        """
        insights = await self.get_all_insights()
        
        # Simple text search implementation
        # 💡: This is a basic implementation - in production we might want
        # more sophisticated search with indexing, stemming, etc.
        query_lower = query.lower()
        results = []
        
        for insight in insights:
            # Search in content
            if query_lower in insight.content.lower():
                results.append(insight)
                continue
            
            # Search in situation
            for situation_item in insight.situation:
                if query_lower in situation_item.lower():
                    results.append(insight)
                    break
        
        return results
    
    async def get_current_active_day(self) -> int:
        """
        Get the current active day, incrementing counter if this is a new calendar day.
        
        Returns:
            Current active day counter
        """
        metadata = await self._load_metadata()
        today = date.today()
        
        # Convert stored date string back to date object if it exists
        last_date = None
        if metadata.get("last_calendar_date_used"):
            try:
                last_date = date.fromisoformat(metadata["last_calendar_date_used"])
            except ValueError:
                pass
        
        # If this is a new calendar day, increment counter
        if last_date != today:
            metadata["active_day_counter"] += 1
            metadata["last_calendar_date_used"] = today.isoformat()
            await self._save_metadata()
        
        return metadata["active_day_counter"]
    
    async def record_insight_access(self, uuid: UUID) -> None:
        """
        Record an access to an insight for frequency tracking.
        
        Args:
            uuid: UUID of the accessed insight
        """
        current_active_day = await self.get_current_active_day()
        insight = await self.get_insight(uuid)
        
        if insight is not None:
            insight.record_access(current_active_day)
            await self.store_insight(insight)
    
    # Compatibility methods to match the existing JsonStorage interface
    async def load(self) -> HippoStorage:
        """
        Load insights in HippoStorage format for compatibility.
        
        This method provides backward compatibility with the existing JsonStorage interface.
        """
        insights = await self.get_all_insights()
        metadata = await self._load_metadata()
        
        # Convert date string back to date object
        last_date = None
        if metadata.get("last_calendar_date_used"):
            try:
                last_date = date.fromisoformat(metadata["last_calendar_date_used"])
            except ValueError:
                pass
        
        return HippoStorage(
            insights=insights,
            active_day_counter=metadata["active_day_counter"],
            last_calendar_date_used=last_date
        )
    
    async def save(self) -> None:
        """Save method for compatibility - no-op since we save immediately."""
        # 💡: File-based storage saves immediately on each operation,
        # so this compatibility method is a no-op
        pass
    
    async def add_insight(self, insight: Insight) -> None:
        """Add an insight for compatibility with JsonStorage interface."""
        await self.store_insight(insight)
