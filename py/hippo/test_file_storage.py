"""Tests for FileBasedStorage implementation."""

import asyncio
import tempfile
from pathlib import Path
from uuid import uuid4

from .file_storage import FileBasedStorage
from .models import Insight


async def test_basic_operations():
    """Test basic CRUD operations with FileBasedStorage."""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # 💡: Disable file watching in tests to avoid background threads
        with FileBasedStorage(Path(temp_dir), enable_watching=False) as storage:
            
            # Create a test insight
            insight = Insight.create(
                content="Test insight content",
                situation=["testing", "file storage"],
                importance=0.8,
                current_active_day=1
            )
        
        # Store the insight
        uuid_str = await storage.store_insight(insight)
        print(f"Stored insight with UUID: {uuid_str}")
        
        # Retrieve the insight
        retrieved = await storage.get_insight(insight.uuid)
        assert retrieved is not None
        assert retrieved.content == "Test insight content"
        assert retrieved.situation == ["testing", "file storage"]
        assert retrieved.importance == 0.8
        print("✓ Store and retrieve works")
        
        # Update the insight
        success = await storage.update_insight(insight.uuid, {
            "content": "Updated content",
            "importance": 0.9
        })
        assert success
        
        # Verify update
        updated = await storage.get_insight(insight.uuid)
        assert updated.content == "Updated content"
        assert updated.importance == 0.9
        print("✓ Update works")
        
        # Test get_all_insights
        all_insights = await storage.get_all_insights()
        assert len(all_insights) == 1
        assert all_insights[0].uuid == insight.uuid
        print("✓ Get all insights works")
        
        # Test search
        results = await storage.search_insights("Updated")
        assert len(results) == 1
        assert results[0].uuid == insight.uuid
        print("✓ Search works")
        
        # Test delete
        deleted = await storage.delete_insight(insight.uuid)
        assert deleted
        
        # Verify deletion
        retrieved_after_delete = await storage.get_insight(insight.uuid)
        assert retrieved_after_delete is None
        
        all_after_delete = await storage.get_all_insights()
        assert len(all_after_delete) == 0
        print("✓ Delete works")
        
        print("All basic operations passed!")


async def test_active_day_tracking():
    """Test active day counter functionality."""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        with FileBasedStorage(Path(temp_dir), enable_watching=False) as storage:
            
            # First call should return 1
            day1 = await storage.get_current_active_day()
            assert day1 == 1
            
            # Same day should return same number
            day1_again = await storage.get_current_active_day()
        assert day1_again == 1
        
        print("✓ Active day tracking works")


async def test_file_structure():
    """Test that files are created in the expected structure."""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        storage_dir = Path(temp_dir)
        with FileBasedStorage(storage_dir, enable_watching=False) as storage:
            
            # Create an insight
            insight = Insight.create(
                content="Test content",
                situation=["test"],
                importance=0.5,
                current_active_day=1
            )
        
        await storage.store_insight(insight)
        
        # Trigger metadata creation by calling get_current_active_day
        await storage.get_current_active_day()
        
        # Check file structure
        insights_dir = storage_dir / "insights"
        assert insights_dir.exists()
        
        insight_file = insights_dir / f"{insight.uuid}.json"
        assert insight_file.exists()
        
        metadata_file = storage_dir / "metadata.json"
        assert metadata_file.exists()
        
        print("✓ File structure is correct")


async def test_file_watching_enabled():
    """Test that file watching can be enabled without hanging."""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # 💡: Test that file watching starts and shuts down cleanly
        with FileBasedStorage(Path(temp_dir), enable_watching=True) as storage:
            
            # Create a test insight
            insight = Insight.create(
                content="Test with watching enabled",
                situation=["testing", "file watching"],
                importance=0.7,
                current_active_day=1
            )
            
            # Store and retrieve to ensure basic functionality works
            uuid_str = await storage.store_insight(insight)
            retrieved = await storage.get_insight(insight.uuid)
            
            assert retrieved is not None
            assert retrieved.content == "Test with watching enabled"
            
        print("✓ File watching enabled/disabled cleanly")


if __name__ == "__main__":
    async def run_tests():
        await test_basic_operations()
        await test_active_day_tracking() 
        await test_file_structure()
        await test_file_watching_enabled()
        print("All tests passed!")
    
    asyncio.run(run_tests())
