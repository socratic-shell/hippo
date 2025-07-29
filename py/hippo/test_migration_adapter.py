"""Tests for the migration adapter."""

import asyncio
import tempfile
from pathlib import Path

import pytest

from .migration_adapter import HippoStorageAdapter
from .models import HippoStorage, Insight


class TestMigrationAdapter:
    """Test the migration adapter functionality."""
    
    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for testing."""
        with tempfile.TemporaryDirectory() as json_dir, \
             tempfile.TemporaryDirectory() as file_dir:
            yield Path(json_dir), Path(file_dir)
    
    @pytest.fixture
    def sample_insights(self):
        """Create sample insights for testing."""
        return [
            Insight.create(
                content="Test insight 1",
                situation=["Testing migration", "Phase 3"],
                importance=0.8,
                current_active_day=1
            ),
            Insight.create(
                content="Test insight 2", 
                situation=["Testing file storage", "Migration adapter"],
                importance=0.6,
                current_active_day=1
            )
        ]
    
    async def test_migration_with_empty_json(self, temp_dirs):
        """Test migration when JSON file doesn't exist."""
        json_dir, file_dir = temp_dirs
        json_file = json_dir / "insights.json"
        
        adapter = HippoStorageAdapter(json_file, file_dir, enable_watching=False)
        
        # Should complete migration immediately since no JSON file exists
        insights = await adapter.get_all_insights()
        assert insights == []
        
        status = await adapter.get_migration_status()
        assert status["json_file_exists"] is False
        assert status["migration_complete"] is True
        assert status["json_insight_count"] == 0
        assert status["file_insight_count"] == 0
    
    async def test_migration_with_json_data(self, temp_dirs, sample_insights):
        """Test migration from JSON file with existing data."""
        json_dir, file_dir = temp_dirs
        json_file = json_dir / "insights.json"
        
        # Create JSON file with sample data
        json_data = HippoStorage(
            insights=sample_insights,
            active_day_counter=5
        )
        
        with open(json_file, 'w') as f:
            f.write(json_data.model_dump_json())
        
        adapter = HippoStorageAdapter(json_file, file_dir, enable_watching=False)
        
        # First access should trigger migration
        insights = await adapter.get_all_insights()
        assert len(insights) == 2
        
        # Verify insights were migrated
        for original in sample_insights:
            migrated = await adapter.get_insight(original.uuid)
            assert migrated is not None
            assert migrated.content == original.content
            assert migrated.situation == original.situation
        
        # Verify active day counter was migrated
        # 💡: Check raw metadata to avoid auto-incrementing the counter
        metadata = await adapter.file_storage._load_metadata()
        assert metadata["active_day_counter"] == 5
        
        # Verify migration status
        status = await adapter.get_migration_status()
        assert status["migration_complete"] is True
        assert status["json_insight_count"] == 2
        assert status["file_insight_count"] == 2
    
    async def test_hybrid_read_during_migration(self, temp_dirs, sample_insights):
        """Test reading from both sources during migration."""
        json_dir, file_dir = temp_dirs
        json_file = json_dir / "insights.json"
        
        # Create JSON file with one insight
        json_insight = sample_insights[0]
        json_data = HippoStorage(insights=[json_insight])
        
        with open(json_file, 'w') as f:
            f.write(json_data.model_dump_json())
        
        adapter = HippoStorageAdapter(json_file, file_dir, enable_watching=False)
        
        # Add a different insight directly to file storage
        file_insight = sample_insights[1]
        await adapter.file_storage.store_insight(file_insight)
        
        # Prevent automatic migration completion for this test
        adapter._migration_complete_marker.unlink(missing_ok=True)
        
        # Should see both insights
        all_insights = await adapter.get_all_insights()
        assert len(all_insights) == 2
        
        uuids = {str(insight.uuid) for insight in all_insights}
        assert str(json_insight.uuid) in uuids
        assert str(file_insight.uuid) in uuids
    
    async def test_write_operations_go_to_file_storage(self, temp_dirs, sample_insights):
        """Test that all write operations go to file storage."""
        json_dir, file_dir = temp_dirs
        json_file = json_dir / "insights.json"
        
        # Create JSON file with existing data
        json_data = HippoStorage(insights=[sample_insights[0]])
        with open(json_file, 'w') as f:
            f.write(json_data.model_dump_json())
        
        adapter = HippoStorageAdapter(json_file, file_dir, enable_watching=False)
        
        # Add new insight - should go to file storage
        new_insight = sample_insights[1]
        await adapter.store_insight(new_insight)
        
        # Verify it's in file storage
        file_insight = await adapter.file_storage.get_insight(new_insight.uuid)
        assert file_insight is not None
        assert file_insight.content == new_insight.content
        
        # Update existing insight - should migrate to file storage
        original_uuid = sample_insights[0].uuid
        await adapter.update_insight(original_uuid, {"content": "Updated content"})
        
        # Verify update is in file storage
        updated_insight = await adapter.file_storage.get_insight(original_uuid)
        assert updated_insight is not None
        assert updated_insight.content == "Updated content"
    
    async def test_search_across_both_sources(self, temp_dirs, sample_insights):
        """Test searching across both JSON and file storage."""
        json_dir, file_dir = temp_dirs
        json_file = json_dir / "insights.json"
        
        # Create JSON file with one insight
        json_insight = sample_insights[0]
        json_data = HippoStorage(insights=[json_insight])
        
        with open(json_file, 'w') as f:
            f.write(json_data.model_dump_json())
        
        adapter = HippoStorageAdapter(json_file, file_dir, enable_watching=False)
        
        # Add different insight to file storage
        file_insight = sample_insights[1]
        await adapter.file_storage.store_insight(file_insight)
        
        # Prevent automatic migration completion
        adapter._migration_complete_marker.unlink(missing_ok=True)
        
        # Search should find insights from both sources
        results = await adapter.search_insights("Test")
        assert len(results) == 2
        
        # Search for specific content should work
        results = await adapter.search_insights("insight 1")
        assert len(results) == 1
        assert results[0].uuid == json_insight.uuid
        
        results = await adapter.search_insights("file storage")
        assert len(results) == 1
        assert results[0].uuid == file_insight.uuid
    
    async def test_migration_deduplication(self, temp_dirs, sample_insights):
        """Test that migration doesn't create duplicates."""
        json_dir, file_dir = temp_dirs
        json_file = json_dir / "insights.json"
        
        # Create JSON file with insights
        json_data = HippoStorage(insights=sample_insights)
        with open(json_file, 'w') as f:
            f.write(json_data.model_dump_json())
        
        adapter = HippoStorageAdapter(json_file, file_dir, enable_watching=False)
        
        # Manually add one insight to file storage first
        await adapter.file_storage.store_insight(sample_insights[0])
        
        # Now trigger migration - should not duplicate the existing insight
        insights = await adapter.get_all_insights()
        assert len(insights) == 2
        
        # Verify no duplicates by checking UUIDs
        uuids = [str(insight.uuid) for insight in insights]
        assert len(uuids) == len(set(uuids))  # No duplicates
    
    async def test_force_complete_migration(self, temp_dirs, sample_insights):
        """Test forcing migration completion and cleanup."""
        json_dir, file_dir = temp_dirs
        json_file = json_dir / "insights.json"
        
        # Create JSON file
        json_data = HippoStorage(insights=sample_insights)
        with open(json_file, 'w') as f:
            f.write(json_data.model_dump_json())
        
        adapter = HippoStorageAdapter(json_file, file_dir, enable_watching=False)
        
        # Trigger migration
        await adapter.get_all_insights()
        
        # Force completion and cleanup
        await adapter.force_complete_migration()
        
        # JSON file should be backed up
        backup_file = json_file.with_suffix('.json.migrated')
        assert backup_file.exists()
        assert not json_file.exists()
        
        # Migration should be marked complete
        status = await adapter.get_migration_status()
        assert status["migration_complete"] is True
    
    async def test_compatibility_interface(self, temp_dirs, sample_insights):
        """Test compatibility with JsonStorage interface."""
        json_dir, file_dir = temp_dirs
        json_file = json_dir / "insights.json"
        
        adapter = HippoStorageAdapter(json_file, file_dir, enable_watching=False)
        
        # Test add_insight compatibility method
        await adapter.add_insight(sample_insights[0])
        
        # Test load compatibility method
        storage = await adapter.load()
        assert isinstance(storage, HippoStorage)
        assert len(storage.insights) == 1
        assert storage.insights[0].uuid == sample_insights[0].uuid
        
        # Test save compatibility method (should be no-op)
        await adapter.save()  # Should not raise
    
    async def test_concurrent_migration_safety(self, temp_dirs, sample_insights):
        """Test that concurrent migration attempts are handled safely."""
        json_dir, file_dir = temp_dirs
        json_file = json_dir / "insights.json"
        
        # Create JSON file
        json_data = HippoStorage(insights=sample_insights)
        with open(json_file, 'w') as f:
            f.write(json_data.model_dump_json())
        
        adapter = HippoStorageAdapter(json_file, file_dir, enable_watching=False)
        
        # Trigger multiple concurrent migrations
        tasks = [
            adapter.get_all_insights(),
            adapter.get_all_insights(),
            adapter.get_all_insights()
        ]
        
        results = await asyncio.gather(*tasks)
        
        # All should return the same results
        for result in results:
            assert len(result) == 2
        
        # Should only have migrated once
        status = await adapter.get_migration_status()
        assert status["file_insight_count"] == 2
        assert status["migration_complete"] is True
    
    async def test_error_handling_during_migration(self, temp_dirs):
        """Test error handling when JSON file is corrupted."""
        json_dir, file_dir = temp_dirs
        json_file = json_dir / "insights.json"
        
        # Create corrupted JSON file
        with open(json_file, 'w') as f:
            f.write("{ invalid json content")
        
        adapter = HippoStorageAdapter(json_file, file_dir, enable_watching=False)
        
        # Should handle corruption gracefully
        insights = await adapter.get_all_insights()
        assert insights == []
        
        # Should still mark migration as complete
        status = await adapter.get_migration_status()
        assert status["migration_complete"] is True
    
    async def test_context_manager_support(self, temp_dirs):
        """Test context manager support for cleanup."""
        json_dir, file_dir = temp_dirs
        json_file = json_dir / "insights.json"
        
        # Should work as context manager
        with HippoStorageAdapter(json_file, file_dir, enable_watching=False) as adapter:
            insights = await adapter.get_all_insights()
            assert insights == []
        
        # Context manager should exit cleanly
