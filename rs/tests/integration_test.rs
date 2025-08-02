//! Integration tests for Hippo Rust implementation
//!
//! These tests validate the core functionality without requiring external dependencies
//! like model downloads. Tests that require the FastEmbed model are marked with #[ignore].

use hippo::{FileStorage, HippoStorage, Insight, SearchEngine};
use tempfile::TempDir;
use uuid::Uuid;

/// Test basic storage operations
#[tokio::test]
async fn test_storage_integration() {
    let temp_dir = TempDir::new().unwrap();
    let mut storage = FileStorage::new(temp_dir.path()).await.unwrap();

    // Create test insights
    let insight1 = Insight::new(
        "Rust provides memory safety without garbage collection".to_string(),
        vec!["rust".to_string(), "memory safety".to_string()],
        0.8,
    );

    let insight2 = Insight::new(
        "FastEmbed-rs offers significant startup performance improvements".to_string(),
        vec!["fastembed".to_string(), "performance".to_string()],
        0.7,
    );

    // Store insights
    storage.store_insight(insight1.clone()).await.unwrap();
    storage.store_insight(insight2.clone()).await.unwrap();

    // Retrieve all insights
    let all_insights = storage.get_all_insights().await.unwrap();
    assert_eq!(all_insights.len(), 2);

    // Test individual retrieval
    let retrieved1 = storage.get_insight(insight1.uuid).await.unwrap();
    assert!(retrieved1.is_some());
    assert_eq!(retrieved1.unwrap().content, insight1.content);

    // Test reinforcement
    storage
        .apply_reinforcement(vec![insight1.uuid], vec![insight2.uuid])
        .await
        .unwrap();

    let updated1 = storage.get_insight(insight1.uuid).await.unwrap().unwrap();
    let updated2 = storage.get_insight(insight2.uuid).await.unwrap().unwrap();

    assert_eq!(updated1.current_importance, 1.0); // 0.8 * 1.5, capped at 1.0
    assert_eq!(updated2.current_importance, 0.35); // 0.7 * 0.5
}

/// Test search engine creation and basic operations (without model)
#[tokio::test]
async fn test_search_engine_basic() {
    let engine = SearchEngine::new();

    // Should create without error
    // Model loading is tested separately with #[ignore]

    // Test with empty insights (should return empty results, not crash)
    let insights = vec![];
    let results = engine
        .search("test query", &insights, 1, 0.0, 1.0, &[], 10, 0)
        .await;

    // Should fail gracefully when model is not loaded and there are insights to process
    // But with empty insights, it should return empty results without trying to load model
    if insights.is_empty() {
        assert!(results.is_ok());
        assert!(results.unwrap().is_empty());
    } else {
        assert!(results.is_err());
    }
}

/// Test JSON compatibility with Python format
#[tokio::test]
async fn test_json_compatibility() {
    use chrono::{DateTime, Utc};
    use serde_json;

    // Create an insight with known values
    let mut insight = Insight::new(
        "Test insight for JSON compatibility".to_string(),
        vec!["json".to_string(), "compatibility".to_string()],
        0.75,
    );

    // Set specific timestamp for reproducible test
    let test_time = DateTime::parse_from_rfc3339("2025-08-01T10:00:00Z")
        .unwrap()
        .with_timezone(&Utc);
    insight.created_at = test_time;
    insight.importance_modified_at = test_time;

    // Serialize to JSON
    let json = serde_json::to_string_pretty(&insight).unwrap();

    // Verify expected fields are present
    assert!(json.contains("\"uuid\""));
    assert!(json.contains("\"content\""));
    assert!(json.contains("\"situation\""));
    assert!(json.contains("\"base_importance\""));
    assert!(json.contains("\"current_importance\""));
    assert!(json.contains("\"created_at\""));
    assert!(json.contains("\"importance_modified_at\""));

    // Deserialize back
    let deserialized: Insight = serde_json::from_str(&json).unwrap();
    assert_eq!(deserialized, insight);
}

/// Test file persistence across storage instances
#[tokio::test]
async fn test_file_persistence() {
    let temp_dir = TempDir::new().unwrap();
    let insight = Insight::new(
        "Persistent test insight".to_string(),
        vec!["persistence".to_string()],
        0.6,
    );
    let insight_id = insight.uuid;

    // Store with first instance
    {
        let mut storage = FileStorage::new(temp_dir.path()).await.unwrap();
        storage.store_insight(insight.clone()).await.unwrap();
    }

    // Load with second instance
    {
        let storage = FileStorage::new(temp_dir.path()).await.unwrap();
        let retrieved = storage.get_insight(insight_id).await.unwrap();
        assert!(retrieved.is_some());
        assert_eq!(retrieved.unwrap(), insight);
    }
}

/// Test error handling
#[tokio::test]
async fn test_error_handling() {
    let temp_dir = TempDir::new().unwrap();
    let mut storage = FileStorage::new(temp_dir.path()).await.unwrap();

    // Test retrieving non-existent insight
    let non_existent_id = Uuid::new_v4();
    let result = storage.get_insight(non_existent_id).await.unwrap();
    assert!(result.is_none());

    // Test updating non-existent insight
    let fake_insight = Insight::new("Non-existent".to_string(), vec!["fake".to_string()], 0.5);
    let result = storage.update_insight(fake_insight).await;
    assert!(result.is_err());
}

/// Test pagination and filtering (without model)
#[tokio::test]
async fn test_search_parameters() {
    let engine = SearchEngine::new();
    let insights = vec![
        Insight::new("First insight".to_string(), vec!["first".to_string()], 0.8),
        Insight::new(
            "Second insight".to_string(),
            vec!["second".to_string()],
            0.7,
        ),
        Insight::new("Third insight".to_string(), vec!["third".to_string()], 0.6),
    ];

    // Test with situation filters that match nothing - should return empty without loading model
    let result = engine
        .search(
            "test",
            &insights,
            1,
            0.0,
            1.0,
            &["nonexistent".to_string()], // Filter that matches nothing
            10,
            0,
        )
        .await;

    // Should succeed with empty results because no insights match the filter
    assert!(result.is_ok());
    assert!(result.unwrap().is_empty());

    // Note: We don't test model loading failure here since FastEmbed might
    // be available and working in the test environment. The model loading
    // tests are marked with #[ignore] for manual testing.
}

// Tests that require model download - run manually with: cargo test -- --ignored
#[tokio::test]
#[ignore]
async fn test_model_loading_performance() {
    use std::time::Instant;

    let engine = SearchEngine::new();

    println!("Testing model loading performance...");
    let start = Instant::now();

    engine.initialize().await.unwrap();

    let duration = start.elapsed();
    println!("Model loaded in: {duration:?}");

    // Should be significantly faster than Python (target: < 1s)
    assert!(
        duration.as_millis() < 2000,
        "Model loading took too long: {duration:?}"
    );
}

#[tokio::test]
#[ignore]
async fn test_embedding_accuracy() {
    let engine = SearchEngine::new();

    // Test semantic similarity
    let embedding1 = engine
        .embed_text("Rust programming language")
        .await
        .unwrap();
    let embedding2 = engine.embed_text("Rust systems programming").await.unwrap();
    let embedding3 = engine.embed_text("Python data science").await.unwrap();

    // Calculate similarities manually
    fn cosine_similarity(a: &[f32], b: &[f32]) -> f64 {
        let dot: f32 = a.iter().zip(b).map(|(x, y)| x * y).sum();
        let norm_a: f32 = a.iter().map(|x| x * x).sum::<f32>().sqrt();
        let norm_b: f32 = b.iter().map(|x| x * x).sum::<f32>().sqrt();
        (dot / (norm_a * norm_b)) as f64
    }

    let sim_rust = cosine_similarity(&embedding1, &embedding2);
    let sim_different = cosine_similarity(&embedding1, &embedding3);

    // Rust-related texts should be more similar than unrelated texts
    assert!(
        sim_rust > sim_different,
        "Rust similarity ({sim_rust}) should be higher than different topics ({sim_different})"
    );

    // Both should be reasonable similarity scores
    assert!(sim_rust > 0.3, "Rust similarity too low: {sim_rust}");
    assert!(sim_rust < 1.0, "Rust similarity too high: {sim_rust}");
}

#[tokio::test]
#[ignore]
async fn test_full_search_integration() {
    let temp_dir = TempDir::new().unwrap();
    let mut storage = FileStorage::new(temp_dir.path()).await.unwrap();
    let engine = SearchEngine::new();

    // Create test insights
    let insights = vec![
        Insight::new(
            "Rust provides memory safety without garbage collection".to_string(),
            vec!["rust".to_string(), "memory".to_string()],
            0.8,
        ),
        Insight::new(
            "Python is excellent for rapid prototyping and data analysis".to_string(),
            vec!["python".to_string(), "data".to_string()],
            0.7,
        ),
        Insight::new(
            "FastEmbed-rs significantly improves startup performance".to_string(),
            vec!["fastembed".to_string(), "performance".to_string()],
            0.9,
        ),
    ];

    // Store insights
    for insight in &insights {
        storage.store_insight(insight.clone()).await.unwrap();
    }

    // Search for Rust-related content
    let results = engine
        .search("memory safety programming", &insights, 1, 0.0, 1.0, &[], 10, 0)
        .await
        .unwrap();

    assert!(!results.is_empty(), "Should find relevant results");

    // The Rust insight should be most relevant
    let top_result = &results[0];
    assert!(top_result.insight.content.contains("Rust"));
    assert!(
        top_result.relevance > 0.3,
        "Relevance should be reasonable: {}",
        top_result.relevance
    );

    // Test situation filtering
    let filtered_results = engine
        .search(
            "programming",
            &insights,
            1,
            0.0,
            1.0,
            &["rust".to_string()],
            10,
            0,
        )
        .await
        .unwrap();

    // Should only return Rust-related insights
    assert_eq!(filtered_results.len(), 1);
    assert!(filtered_results[0].insight.content.contains("Rust"));
}
