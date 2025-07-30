"""File-based storage for Hippo insights with concurrent access support."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import time
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from uuid import UUID

import aiofiles
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .models import HippoStorage, Insight

logger = logging.getLogger(__name__)

# 💡: Cache refresh interval - can be tuned based on consistency vs performance needs
CACHE_REFRESH_INTERVAL_SECONDS = 30

# 💡: Debounce window for file events to avoid excessive cache rebuilds during rapid changes
FILE_EVENT_DEBOUNCE_SECONDS = 1.0


class FileBasedStorage:
    """
    File-based storage backend that stores each insight as a separate JSON file.
    
    This implementation provides:
    - Thread-safe concurrent access within a single process
    - Atomic writes to prevent corruption
    - In-memory caching for performance
    - UUID-based filename validation
    """
    
    def __init__(self, directory_path: Path, enable_watching: bool = True) -> None:
        """
        Initialize file-based storage.
        
        Args:
            directory_path: Directory to store insight files and metadata
            enable_watching: Whether to enable file watching for cross-process sync
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
        self._metadata_cache: Optional[Dict[str, Any]] = None
        
        # File watching infrastructure
        # 💡: Track UUIDs we just wrote to avoid refreshing cache on our own changes
        self._recently_written_uuids: Set[str] = set()
        self._recently_written_lock = threading.Lock()
        
        # 💡: Debouncing for file events to prevent excessive cache rebuilds
        self._debounce_timer: Optional[threading.Timer] = None
        self._debounce_lock = threading.Lock()
        
        # File watcher components
        self._observer: Optional[Any] = None
        self._periodic_timer: Optional[threading.Timer] = None
        self._shutdown_requested = False
        self._watching_enabled = enable_watching
        
        # Ensure directories exist
        self.insights_dir.mkdir(parents=True, exist_ok=True)
        
        # Start file watching if enabled
        if enable_watching:
            self._start_file_watching()
    
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
    
    async def _atomic_write_json(self, file_path: Path, data: Dict[str, Any]) -> None:
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
    
    async def _load_metadata(self) -> Dict[str, Any]:
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
        """
        Load all insights from disk into memory cache.
        
        💡: Now delegates to the refresh mechanism for consistency with file watching
        """
        with self._cache_lock:
            if self._cache_loaded:
                return
            
            # Use the same refresh logic as file watching for consistency
            self._refresh_cache_from_disk()
    
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
        
        # Mark as written to avoid unnecessary cache refresh on our own change
        self._mark_uuid_as_written(uuid_str)
        
        # Write to disk atomically
        insight_data = insight.model_dump(mode='json')
        await self._atomic_write_json(file_path, insight_data)
        
        # Update cache
        with self._cache_lock:
            self._insights_cache[uuid_str] = insight
        
        return uuid_str
    
    async def update_insight(self, uuid: UUID, updates: Dict[str, Any]) -> bool:
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
        
        # Mark as written to avoid unnecessary cache refresh on our own change
        self._mark_uuid_as_written(uuid_str)
        
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
    
    async def search_insights(self, query: str, filters: Optional[Dict[str, Any]] = None) -> List[Insight]:
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
    
    def _start_file_watching(self) -> None:
        """
        Start file watching with both event-based and periodic refresh.
        
        💡: Uses hybrid approach - watchdog for fast updates plus periodic safety net
        to handle missed events as documented in file-watching-event-drop.md
        """
        try:
            # Create event handler
            event_handler = _InsightFileEventHandler(self)
            
            # Start watchdog observer
            self._observer = Observer()
            self._observer.schedule(
                event_handler,
                str(self.insights_dir),
                recursive=False
            )
            self._observer.start()
            logger.debug(f"Started file watching on {self.insights_dir}")
            
            # Start periodic refresh timer
            self._schedule_periodic_refresh()
            
        except Exception as e:
            # 💡: If file watching fails, continue without it - the system will still work
            # but won't get cross-process updates until periodic refresh
            logger.warning(f"Failed to start file watching, continuing without real-time updates: {e}", exc_info=True)
    
    def _schedule_periodic_refresh(self) -> None:
        """Schedule the next periodic cache refresh."""
        if self._shutdown_requested:
            return
            
        self._periodic_timer = threading.Timer(
            CACHE_REFRESH_INTERVAL_SECONDS,
            self._periodic_refresh_callback
        )
        self._periodic_timer.start()
    
    def _periodic_refresh_callback(self) -> None:
        """Callback for periodic cache refresh timer."""
        try:
            self._refresh_cache_from_disk()
        except Exception as e:
            logger.warning(f"Periodic cache refresh failed: {e}", exc_info=True)
        finally:
            # Schedule next refresh
            self._schedule_periodic_refresh()
    
    def _on_file_event(self, file_path: str) -> None:
        """
        Handle file system events with debouncing.
        
        Args:
            file_path: Path to the file that changed
        """
        # Extract UUID from filename
        uuid_str = Path(file_path).stem
        
        # Check if this is our own change
        with self._recently_written_lock:
            if uuid_str in self._recently_written_uuids:
                self._recently_written_uuids.discard(uuid_str)
                return  # Skip refresh for our own changes
        
        # Debounce the refresh to avoid excessive rebuilds
        with self._debounce_lock:
            if self._debounce_timer is not None:
                self._debounce_timer.cancel()
            
            self._debounce_timer = threading.Timer(
                FILE_EVENT_DEBOUNCE_SECONDS,
                self._debounced_refresh_callback
            )
            self._debounce_timer.start()
    
    def _debounced_refresh_callback(self) -> None:
        """Callback for debounced cache refresh."""
        try:
            self._refresh_cache_from_disk()
        except Exception as e:
            logger.warning(f"Debounced cache refresh failed: {e}", exc_info=True)
    
    def _refresh_cache_from_disk(self) -> None:
        """
        Refresh the entire cache by scanning the filesystem.
        
        💡: This is our core cache refresh operation - rebuilds everything from disk
        to handle missed events and ensure consistency across processes.
        """
        with self._cache_lock:
            try:
                # Clear current cache
                old_cache = self._insights_cache.copy()
                self._insights_cache.clear()
                
                # Scan insights directory for JSON files
                if not self.insights_dir.exists():
                    self._cache_loaded = True
                    logger.debug("Insights directory does not exist, cache refresh complete")
                    return
                
                loaded_count = 0
                skipped_count = 0
                
                for file_path in self.insights_dir.glob("*.json"):
                    uuid_str = file_path.stem
                    
                    # Validate UUID format
                    if not self._validate_uuid_filename(uuid_str):
                        logger.debug(f"Skipping file with invalid UUID filename: {file_path.name}")
                        skipped_count += 1
                        continue
                    
                    try:
                        # Load insight from file
                        with open(file_path, 'r', encoding='utf-8') as f:
                            insight_data = json.load(f)
                        
                        # Convert to Insight object
                        insight = Insight.model_validate(insight_data)
                        self._insights_cache[uuid_str] = insight
                        loaded_count += 1
                        
                    except (json.JSONDecodeError, ValueError, OSError) as e:
                        # 💡: Skip corrupted files rather than failing entirely
                        logger.warning(f"Failed to load insight from {file_path}: {e}")
                        skipped_count += 1
                        continue
                
                self._cache_loaded = True
                logger.debug(f"Cache refresh complete: loaded {loaded_count} insights, skipped {skipped_count} files")
                
            except Exception as e:
                # 💡: If refresh fails completely, restore old cache to maintain service
                logger.error(f"Cache refresh failed completely, keeping old cache: {e}", exc_info=True)
                self._insights_cache = old_cache
    
    def _mark_uuid_as_written(self, uuid_str: str) -> None:
        """
        Mark a UUID as recently written by us to avoid unnecessary cache refresh.
        
        Args:
            uuid_str: UUID that we just wrote
        """
        with self._recently_written_lock:
            self._recently_written_uuids.add(uuid_str)
    
    def __enter__(self) -> 'FileBasedStorage':
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        """Context manager exit - ensures proper cleanup."""
        self.shutdown()
        return False  # Don't suppress exceptions
    
    def shutdown(self) -> None:
        """
        Gracefully shutdown file watching components.
        
        💡: Important to call this to avoid resource leaks and background threads
        """
        self._shutdown_requested = True
        
        # Stop watchdog observer
        if self._observer and self._observer.is_alive():
            self._observer.stop()
            self._observer.join(timeout=5)
        
        # Cancel timers
        with self._debounce_lock:
            if self._debounce_timer:
                self._debounce_timer.cancel()
        
        if self._periodic_timer:
            self._periodic_timer.cancel()


class _InsightFileEventHandler(FileSystemEventHandler):
    """
    File system event handler for insight JSON files.
    
    💡: Separate class to keep event handling logic isolated and testable
    """
    
    def __init__(self, storage: FileBasedStorage):
        super().__init__()
        self.storage = storage
    
    def on_created(self, event: Any) -> None:
        """Handle file creation events."""
        if not event.is_directory and event.src_path.endswith('.json'):
            self.storage._on_file_event(event.src_path)
    
    def on_modified(self, event: Any) -> None:
        """Handle file modification events."""
        if not event.is_directory and event.src_path.endswith('.json'):
            self.storage._on_file_event(event.src_path)
    
    def on_deleted(self, event: Any) -> None:
        """Handle file deletion events."""
        if not event.is_directory and event.src_path.endswith('.json'):
            self.storage._on_file_event(event.src_path)
