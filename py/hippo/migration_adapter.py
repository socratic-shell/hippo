"""Migration adapter for transitioning from JSON to file-based storage."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional
from uuid import UUID

from .file_storage import FileBasedStorage
from .models import HippoStorage, Insight
from .storage import JsonStorage

logger = logging.getLogger(__name__)


class HippoStorageAdapter:
    """
    💡: Migration adapter that enables gradual transition from JSON to file-based storage.
    
    This adapter implements a hybrid approach:
    - Reads from both old JSON format and new file format during transition
    - Always writes to new file format to build up the new storage
    - Maintains compatibility with existing JsonStorage interface
    - Supports migration completion detection and cleanup
    
    The migration strategy allows for zero-downtime transition where multiple
    Q CLI sessions can operate during the migration period.
    """
    
    def __init__(
        self, 
        json_file_path: Path, 
        file_storage_dir: Path,
        enable_watching: bool = True
    ) -> None:
        """
        Initialize the migration adapter.
        
        Args:
            json_file_path: Path to the legacy JSON storage file
            file_storage_dir: Directory for the new file-based storage
            enable_watching: Whether to enable file watching for cross-process sync
        """
        self.json_file_path = json_file_path
        self.file_storage_dir = file_storage_dir
        
        # Initialize both storage backends
        self.json_storage = JsonStorage(json_file_path)
        self.file_storage = FileBasedStorage(file_storage_dir, enable_watching)
        
        # Migration state tracking
        self._migration_complete_marker = file_storage_dir / ".migration_complete"
        self._migration_in_progress = False
    
    async def _is_migration_complete(self) -> bool:
        """Check if migration has been completed."""
        return self._migration_complete_marker.exists()
    
    async def _mark_migration_complete(self) -> None:
        """Mark migration as complete by creating marker file."""
        self._migration_complete_marker.touch()
        logger.info("Migration from JSON to file-based storage marked as complete")
    
    async def _migrate_insights_if_needed(self) -> None:
        """
        💡: Migrate insights from JSON to file storage if not already done.
        
        This is called lazily on first access to ensure migration happens
        automatically without requiring explicit user action.
        """
        if await self._is_migration_complete():
            return
        
        if self._migration_in_progress:
            return
        
        self._migration_in_progress = True
        
        try:
            # Check if JSON file exists and has data
            if not self.json_file_path.exists():
                logger.info("No legacy JSON file found, marking migration complete")
                await self._mark_migration_complete()
                return
            
            # Load insights from JSON storage
            json_data = await self.json_storage.load()
            
            if not json_data.insights:
                logger.info("No insights in legacy JSON file, marking migration complete")
                await self._mark_migration_complete()
                return
            
            logger.info(f"Starting migration of {len(json_data.insights)} insights from JSON to file storage")
            
            # Migrate each insight to file storage
            migrated_count = 0
            for insight in json_data.insights:
                try:
                    # Check if insight already exists in file storage
                    existing = await self.file_storage.get_insight(insight.uuid)
                    if existing is None:
                        await self.file_storage.store_insight(insight)
                        migrated_count += 1
                    else:
                        logger.debug(f"Insight {insight.uuid} already exists in file storage, skipping")
                except Exception as e:
                    logger.error(f"Failed to migrate insight {insight.uuid}: {e}")
                    # Continue with other insights rather than failing completely
            
            # Migrate metadata (active day counter)
            try:
                # 💡: Check raw metadata to avoid auto-incrementing the counter
                # get_current_active_day() would increment from 0 to 1 on first call
                metadata = await self.file_storage._load_metadata()
                current_counter = metadata.get("active_day_counter", 0)
                
                if current_counter == 0 and json_data.active_day_counter > 0:
                    # Update the active day counter in file storage
                    metadata["active_day_counter"] = json_data.active_day_counter
                    await self.file_storage._save_metadata()
                    logger.info(f"Migrated active day counter: {json_data.active_day_counter}")
            except Exception as e:
                logger.error(f"Failed to migrate active day counter: {e}")
            
            logger.info(f"Migration complete: {migrated_count} insights migrated to file storage")
            await self._mark_migration_complete()
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            raise
        finally:
            self._migration_in_progress = False
    
    async def _get_insights_from_both_sources(self) -> List[Insight]:
        """
        💡: Get insights from both JSON and file storage, with file storage taking precedence.
        
        During migration, we may have insights in both places. File storage is
        considered the authoritative source since it's where new writes go.
        """
        # Ensure migration has been attempted
        await self._migrate_insights_if_needed()
        
        # If migration is complete, only use file storage
        if await self._is_migration_complete():
            return await self.file_storage.get_all_insights()
        
        # During migration, combine insights from both sources
        file_insights = await self.file_storage.get_all_insights()
        
        # Create a set of UUIDs from file storage for deduplication
        file_uuids = {str(insight.uuid) for insight in file_insights}
        
        # Add insights from JSON that aren't already in file storage
        try:
            json_data = await self.json_storage.load()
            json_insights = [
                insight for insight in json_data.insights 
                if str(insight.uuid) not in file_uuids
            ]
            
            if json_insights:
                logger.debug(f"Found {len(json_insights)} insights only in JSON storage")
            
            return file_insights + json_insights
            
        except Exception as e:
            logger.warning(f"Failed to load from JSON storage during hybrid read: {e}")
            return file_insights
    
    # Public interface methods - always write to file storage, read from both during migration
    
    async def get_insight(self, uuid: UUID) -> Optional[Insight]:
        """Get an insight by UUID from either storage backend."""
        await self._migrate_insights_if_needed()
        
        # Try file storage first (authoritative during migration)
        insight = await self.file_storage.get_insight(uuid)
        if insight is not None:
            return insight
        
        # If migration not complete, also check JSON storage
        if not await self._is_migration_complete():
            try:
                json_data = await self.json_storage.load()
                return json_data.find_by_uuid(uuid)
            except Exception as e:
                logger.warning(f"Failed to check JSON storage for insight {uuid}: {e}")
        
        return None
    
    async def store_insight(self, insight: Insight) -> str:
        """Store an insight (always writes to file storage)."""
        await self._migrate_insights_if_needed()
        return await self.file_storage.store_insight(insight)
    
    async def update_insight(self, uuid: UUID, updates: dict) -> bool:
        """Update an existing insight (always writes to file storage)."""
        await self._migrate_insights_if_needed()
        
        # First check if insight exists in either storage
        existing = await self.get_insight(uuid)
        if existing is None:
            return False
        
        # Update in file storage (this will create it there if it was only in JSON)
        return await self.file_storage.update_insight(uuid, updates)
    
    async def delete_insight(self, uuid: UUID) -> bool:
        """Delete an insight (removes from file storage, JSON storage is read-only)."""
        await self._migrate_insights_if_needed()
        
        # Only delete from file storage since JSON storage is read-only during migration
        return await self.file_storage.delete_insight(uuid)
    
    async def get_all_insights(self) -> List[Insight]:
        """Get all insights from both storage backends."""
        return await self._get_insights_from_both_sources()
    
    async def search_insights(self, query: str, filters: Optional[dict] = None) -> List[Insight]:
        """Search insights across both storage backends."""
        await self._migrate_insights_if_needed()
        
        # If migration is complete, only search file storage
        if await self._is_migration_complete():
            return await self.file_storage.search_insights(query, filters)
        
        # During migration, search both and deduplicate
        file_results = await self.file_storage.search_insights(query, filters)
        file_uuids = {str(insight.uuid) for insight in file_results}
        
        try:
            # Search JSON storage for insights not in file storage
            json_data = await self.json_storage.load()
            json_results = []
            
            # 💡: Simple text search in JSON insights that aren't already in file storage
            # This duplicates some search logic but keeps the migration adapter simple
            query_lower = query.lower()
            for insight in json_data.insights:
                if str(insight.uuid) in file_uuids:
                    continue
                
                # Basic text search in content and situation
                if (query_lower in insight.content.lower() or 
                    query_lower in insight.situation.lower()):
                    json_results.append(insight)
            
            return file_results + json_results
            
        except Exception as e:
            logger.warning(f"Failed to search JSON storage during hybrid search: {e}")
            return file_results
    
    async def get_current_active_day(self) -> int:
        """Get current active day (always from file storage)."""
        await self._migrate_insights_if_needed()
        return await self.file_storage.get_current_active_day()
    
    async def record_insight_access(self, uuid: UUID) -> None:
        """Record insight access (always to file storage)."""
        await self._migrate_insights_if_needed()
        await self.file_storage.record_insight_access(uuid)
    
    # Compatibility methods for JsonStorage interface
    
    async def load(self) -> HippoStorage:
        """Load insights in HippoStorage format for compatibility."""
        await self._migrate_insights_if_needed()
        
        insights = await self._get_insights_from_both_sources()
        active_day = await self.get_current_active_day()
        
        # 💡: Reconstruct HippoStorage format from distributed file storage
        # This maintains compatibility with existing code expecting the old format
        return HippoStorage(
            insights=insights,
            active_day_counter=active_day
        )
    
    async def save(self) -> None:
        """Save method for compatibility - no-op since we save immediately."""
        # File-based storage saves immediately, so this is a no-op
        pass
    
    async def add_insight(self, insight: Insight) -> None:
        """Add an insight for compatibility with JsonStorage interface."""
        await self.store_insight(insight)
    
    # Migration management methods
    
    async def force_complete_migration(self) -> None:
        """
        Force completion of migration and cleanup of JSON file.
        
        This should only be called when you're confident all insights
        have been successfully migrated to file storage.
        """
        await self._migrate_insights_if_needed()
        
        if not await self._is_migration_complete():
            logger.warning("Forcing migration completion without full migration")
            await self._mark_migration_complete()
        
        # Optionally backup and remove the JSON file
        if self.json_file_path.exists():
            backup_path = self.json_file_path.with_suffix('.json.migrated')
            self.json_file_path.rename(backup_path)
            logger.info(f"Legacy JSON file backed up to {backup_path}")
    
    async def get_migration_status(self) -> dict:
        """Get current migration status for debugging/monitoring."""
        json_exists = self.json_file_path.exists()
        migration_complete = await self._is_migration_complete()
        
        json_count = 0
        if json_exists:
            try:
                json_data = await self.json_storage.load()
                json_count = len(json_data.insights)
            except Exception:
                json_count = -1  # Error loading
        
        file_insights = await self.file_storage.get_all_insights()
        file_count = len(file_insights)
        
        return {
            "json_file_exists": json_exists,
            "json_insight_count": json_count,
            "file_insight_count": file_count,
            "migration_complete": migration_complete,
            "migration_in_progress": self._migration_in_progress
        }
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup file watching."""
        # Delegate cleanup to file storage
        if hasattr(self.file_storage, '__exit__'):
            self.file_storage.__exit__(exc_type, exc_val, exc_tb)
