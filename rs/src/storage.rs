//! File-based storage implementation
//!
//! Provides JSON-compatible storage that can read existing Python-generated memories
//! and maintain the same file format for seamless migration.

use crate::models::{HippoMetadata, HippoStorage, Insight, InsightId};
use anyhow::{Context, Result};
use serde_json;
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use thiserror::Error;
use tokio::fs;
use tokio::sync::RwLock;

/// Storage-specific errors
#[derive(Error, Debug)]
pub enum StorageError {
    #[error("Insight not found: {id}")]
    InsightNotFound { id: InsightId },

    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),

    #[error("JSON serialization error: {0}")]
    Json(#[from] serde_json::Error),

    #[error("Storage directory error: {message}")]
    Directory { message: String },
}

/// File-based storage implementation
///
/// Stores insights as individual JSON files in a directory structure.
/// Maintains compatibility with the Python implementation's file format.
pub struct FileStorage {
    /// Base directory for storage
    storage_dir: PathBuf,

    /// In-memory cache of insights (for performance)
    cache: RwLock<HashMap<InsightId, Insight>>,

    /// Whether the cache has been loaded
    cache_loaded: RwLock<bool>,
    
    /// Metadata cache (active day counter, etc.)
    metadata_cache: RwLock<Option<HippoMetadata>>,
}

impl FileStorage {
    /// Create a new file storage instance
    ///
    /// The storage directory will be created if it doesn't exist.
    pub async fn new<P: AsRef<Path>>(storage_dir: P) -> Result<Self, StorageError> {
        let storage_dir = storage_dir.as_ref().to_path_buf();

        // Create storage directory if it doesn't exist
        if !storage_dir.exists() {
            fs::create_dir_all(&storage_dir).await?;
        }

        // Verify it's a directory
        let metadata = fs::metadata(&storage_dir).await?;
        if !metadata.is_dir() {
            return Err(StorageError::Directory {
                message: format!("{} is not a directory", storage_dir.display()),
            });
        }

        Ok(Self {
            storage_dir,
            cache: RwLock::new(HashMap::new()),
            cache_loaded: RwLock::new(false),
            metadata_cache: RwLock::new(None),
        })
    }

    /// Get the file path for an insight
    fn insight_path(&self, id: InsightId) -> PathBuf {
        self.storage_dir.join(format!("{id}.json"))
    }
    
    /// Get the file path for metadata
    fn metadata_path(&self) -> PathBuf {
        self.storage_dir.join("metadata.json")
    }

    /// Load all insights into cache if not already loaded
    async fn ensure_cache_loaded(&self) -> Result<(), StorageError> {
        let cache_loaded = *self.cache_loaded.read().await;
        if cache_loaded {
            return Ok(());
        }

        let mut cache = self.cache.write().await;
        let mut cache_loaded_guard = self.cache_loaded.write().await;

        // Double-check in case another task loaded while we were waiting
        if *cache_loaded_guard {
            return Ok(());
        }

        tracing::info!("Loading insights from {}", self.storage_dir.display());
        let start = std::time::Instant::now();

        // Read all JSON files in the storage directory
        let mut entries = fs::read_dir(&self.storage_dir).await?;
        let mut loaded_count = 0;

        while let Some(entry) = entries.next_entry().await? {
            let path = entry.path();

            // Skip non-JSON files
            if path.extension().and_then(|s| s.to_str()) != Some("json") {
                continue;
            }

            // Try to parse the filename as a UUID
            let filename = path.file_stem().and_then(|s| s.to_str());
            if let Some(filename) = filename {
                if let Ok(uuid) = filename.parse::<InsightId>() {
                    match self.load_insight_from_file(&path).await {
                        Ok(insight) => {
                            cache.insert(uuid, insight);
                            loaded_count += 1;
                        }
                        Err(e) => {
                            tracing::warn!("Failed to load insight from {}: {}", path.display(), e);
                        }
                    }
                }
            }
        }

        let duration = start.elapsed();
        tracing::info!("Loaded {} insights in {:?}", loaded_count, duration);

        *cache_loaded_guard = true;
        Ok(())
    }
    
    /// Load metadata from file, creating default if it doesn't exist
    async fn load_metadata(&self) -> Result<HippoMetadata, StorageError> {
        let mut metadata_guard = self.metadata_cache.write().await;
        
        if let Some(ref metadata) = *metadata_guard {
            return Ok(metadata.clone());
        }
        
        let metadata_path = self.metadata_path();
        
        let metadata = if metadata_path.exists() {
            match fs::read_to_string(&metadata_path).await {
                Ok(content) => {
                    match serde_json::from_str::<HippoMetadata>(&content) {
                        Ok(metadata) => metadata,
                        Err(e) => {
                            tracing::warn!("Failed to parse metadata file, using defaults: {}", e);
                            // Backup corrupted file
                            let backup_path = metadata_path.with_extension("json.backup");
                            if let Err(backup_err) = fs::rename(&metadata_path, &backup_path).await {
                                tracing::warn!("Failed to backup corrupted metadata: {}", backup_err);
                            }
                            HippoMetadata::default()
                        }
                    }
                }
                Err(e) => {
                    tracing::warn!("Failed to read metadata file: {}", e);
                    HippoMetadata::default()
                }
            }
        } else {
            HippoMetadata::default()
        };
        
        *metadata_guard = Some(metadata.clone());
        Ok(metadata)
    }
    
    /// Save metadata to file atomically
    async fn save_metadata(&self, metadata: &HippoMetadata) -> Result<(), StorageError> {
        let metadata_path = self.metadata_path();
        let temp_path = metadata_path.with_extension("json.tmp");
        
        let content = serde_json::to_string_pretty(metadata)
            .map_err(StorageError::Json)?;
            
        fs::write(&temp_path, content).await
            .map_err(StorageError::Io)?;
            
        fs::rename(&temp_path, &metadata_path).await
            .map_err(StorageError::Io)?;
            
        // Update cache
        *self.metadata_cache.write().await = Some(metadata.clone());
        
        Ok(())
    }

    /// Load a single insight from a file
    async fn load_insight_from_file(&self, path: &Path) -> Result<Insight, StorageError> {
        let content = fs::read_to_string(path).await?;
        let insight: Insight = serde_json::from_str(&content)?;
        Ok(insight)
    }

    /// Save a single insight to a file
    async fn save_insight_to_file(&self, insight: &Insight) -> Result<(), StorageError> {
        let path = self.insight_path(insight.uuid);
        let content = serde_json::to_string_pretty(insight)?;
        fs::write(path, content).await?;
        Ok(())
    }
    
    /// Get the current active day, incrementing if it's a new calendar day
    pub async fn get_current_active_day(&self) -> Result<u32, StorageError> {
        let mut metadata = self.load_metadata().await?;
        let mut updated = false;
        let current_day = metadata.get_current_active_day(&mut updated);
        
        // Save metadata only if it was updated (new day)
        if updated {
            self.save_metadata(&metadata).await?;
        }
        
        Ok(current_day)
    }
    
    /// Record access to an insight for frequency tracking
    pub async fn record_insight_access(&mut self, insight_id: InsightId, current_active_day: u32) -> Result<(), StorageError> {
        self.ensure_cache_loaded().await?;
        
        let mut cache = self.cache.write().await;
        if let Some(insight) = cache.get_mut(&insight_id) {
            insight.record_access(current_active_day);
            
            // Save the updated insight to disk
            self.save_insight_to_file(insight).await?;
        }
        
        Ok(())
    }
}

#[async_trait::async_trait]
impl HippoStorage for FileStorage {
    async fn store_insight(&mut self, insight: Insight) -> crate::Result<()> {
        // Save to file
        self.save_insight_to_file(&insight)
            .await
            .context("Failed to save insight to file")?;

        // Update cache
        self.ensure_cache_loaded().await?;
        let mut cache = self.cache.write().await;
        cache.insert(insight.uuid, insight);

        Ok(())
    }

    async fn get_insight(&self, id: InsightId) -> crate::Result<Option<Insight>> {
        self.ensure_cache_loaded().await?;
        let cache = self.cache.read().await;
        Ok(cache.get(&id).cloned())
    }

    async fn update_insight(&mut self, insight: Insight) -> crate::Result<()> {
        // Check if insight exists
        if self.get_insight(insight.uuid).await?.is_none() {
            return Err(StorageError::InsightNotFound { id: insight.uuid }.into());
        }

        // Save to file
        self.save_insight_to_file(&insight)
            .await
            .context("Failed to update insight file")?;

        // Update cache
        let mut cache = self.cache.write().await;
        cache.insert(insight.uuid, insight);

        Ok(())
    }

    async fn get_all_insights(&self) -> crate::Result<Vec<Insight>> {
        self.ensure_cache_loaded().await?;
        let cache = self.cache.read().await;
        Ok(cache.values().cloned().collect())
    }

    async fn apply_reinforcement(
        &mut self,
        upvotes: Vec<InsightId>,
        downvotes: Vec<InsightId>,
    ) -> crate::Result<()> {
        self.ensure_cache_loaded().await?;
        let mut cache = self.cache.write().await;

        // Apply upvotes
        for id in upvotes {
            if let Some(insight) = cache.get_mut(&id) {
                insight.apply_reinforcement(true);
                self.save_insight_to_file(insight)
                    .await
                    .context("Failed to save upvoted insight")?;
            }
        }

        // Apply downvotes
        for id in downvotes {
            if let Some(insight) = cache.get_mut(&id) {
                insight.apply_reinforcement(false);
                self.save_insight_to_file(insight)
                    .await
                    .context("Failed to save downvoted insight")?;
            }
        }

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;


    async fn create_test_storage() -> (FileStorage, TempDir) {
        let temp_dir = TempDir::new().unwrap();
        let storage = FileStorage::new(temp_dir.path()).await.unwrap();
        (storage, temp_dir)
    }

    #[tokio::test]
    async fn test_metadata_active_day() {
        let temp_dir = TempDir::new().unwrap();
        let storage = FileStorage::new(temp_dir.path()).await.unwrap();
        
        // First call should return day 1
        let day1 = storage.get_current_active_day().await.unwrap();
        assert_eq!(day1, 1);
        
        // Second call on same day should return same day
        let day1_again = storage.get_current_active_day().await.unwrap();
        assert_eq!(day1_again, 1);
        
        // Check that metadata file was created
        let metadata_path = temp_dir.path().join("metadata.json");
        assert!(metadata_path.exists());
        
        // Check metadata content
        let content = std::fs::read_to_string(&metadata_path).unwrap();
        let metadata: HippoMetadata = serde_json::from_str(&content).unwrap();
        assert_eq!(metadata.active_day_counter, 1);
        assert!(metadata.last_calendar_date_used.is_some());
    }

    #[tokio::test]
    async fn test_storage_creation() {
        let temp_dir = TempDir::new().unwrap();
        let storage = FileStorage::new(temp_dir.path()).await;
        assert!(storage.is_ok());
    }

    #[tokio::test]
    async fn test_store_and_retrieve_insight() {
        let (mut storage, _temp_dir) = create_test_storage().await;

        let insight = Insight::new("Test insight".to_string(), vec!["test".to_string()], 0.7);
        let id = insight.uuid;

        // Store insight
        storage.store_insight(insight.clone()).await.unwrap();

        // Retrieve insight
        let retrieved = storage.get_insight(id).await.unwrap();
        assert!(retrieved.is_some());
        assert_eq!(retrieved.unwrap(), insight);
    }

    #[tokio::test]
    async fn test_update_insight() {
        let (mut storage, _temp_dir) = create_test_storage().await;

        let mut insight = Insight::new(
            "Original content".to_string(),
            vec!["test".to_string()],
            0.7,
        );
        let id = insight.uuid;

        // Store original
        storage.store_insight(insight.clone()).await.unwrap();

        // Update content
        insight.content = "Updated content".to_string();
        storage.update_insight(insight.clone()).await.unwrap();

        // Verify update
        let retrieved = storage.get_insight(id).await.unwrap().unwrap();
        assert_eq!(retrieved.content, "Updated content");
    }

    #[tokio::test]
    async fn test_update_nonexistent_insight() {
        let (mut storage, _temp_dir) = create_test_storage().await;

        let insight = Insight::new("Test".to_string(), vec!["test".to_string()], 0.7);

        // Try to update non-existent insight
        let result = storage.update_insight(insight).await;
        assert!(result.is_err());
    }

    #[tokio::test]
    async fn test_get_all_insights() {
        let (mut storage, _temp_dir) = create_test_storage().await;

        let insight1 = Insight::new("First".to_string(), vec!["test".to_string()], 0.6);
        let insight2 = Insight::new("Second".to_string(), vec!["test".to_string()], 0.7);

        storage.store_insight(insight1.clone()).await.unwrap();
        storage.store_insight(insight2.clone()).await.unwrap();

        let all_insights = storage.get_all_insights().await.unwrap();
        assert_eq!(all_insights.len(), 2);

        let ids: Vec<_> = all_insights.iter().map(|i| i.uuid).collect();
        assert!(ids.contains(&insight1.uuid));
        assert!(ids.contains(&insight2.uuid));
    }

    #[tokio::test]
    async fn test_reinforcement() {
        let (mut storage, _temp_dir) = create_test_storage().await;

        let insight = Insight::new("Test insight".to_string(), vec!["test".to_string()], 0.6);
        let id = insight.uuid;

        storage.store_insight(insight).await.unwrap();

        // Apply upvote
        storage.apply_reinforcement(vec![id], vec![]).await.unwrap();

        let updated = storage.get_insight(id).await.unwrap().unwrap();
        assert!((updated.current_importance - 0.9).abs() < 1e-10); // 0.6 * 1.5

        // Apply downvote
        storage.apply_reinforcement(vec![], vec![id]).await.unwrap();

        let updated = storage.get_insight(id).await.unwrap().unwrap();
        assert!((updated.current_importance - 0.45).abs() < 1e-10); // 0.9 * 0.5
    }

    #[tokio::test]
    async fn test_file_persistence() {
        let temp_dir = TempDir::new().unwrap();
        let insight = Insight::new(
            "Persistent insight".to_string(),
            vec!["persistence".to_string()],
            0.8,
        );
        let id = insight.uuid;

        // Store with first storage instance
        {
            let mut storage = FileStorage::new(temp_dir.path()).await.unwrap();
            storage.store_insight(insight.clone()).await.unwrap();
        }

        // Retrieve with second storage instance (should load from file)
        {
            let storage = FileStorage::new(temp_dir.path()).await.unwrap();
            let retrieved = storage.get_insight(id).await.unwrap();
            assert!(retrieved.is_some());
            assert_eq!(retrieved.unwrap(), insight);
        }
    }
}
