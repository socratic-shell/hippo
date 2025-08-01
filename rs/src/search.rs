//! Semantic search engine using FastEmbed-rs
//!
//! Provides sentence transformer-based semantic similarity search over insights.
//! Uses the all-MiniLM-L6-v2 model for compatibility with the Python implementation.

use crate::models::{Insight, SearchResult};
use anyhow::{Context, Result};
use fastembed::{EmbeddingModel, TextEmbedding, InitOptions};
use std::sync::Arc;
use tokio::sync::RwLock;

/// Semantic search engine
///
/// Wraps FastEmbed-rs to provide semantic similarity search over insights.
/// Thread-safe and async-ready for use in MCP server.
pub struct SearchEngine {
    /// The embedding model (wrapped for thread safety)
    model: Arc<RwLock<Option<TextEmbedding>>>,
}

impl SearchEngine {
    /// Create a new search engine
    ///
    /// The model will be loaded lazily on first use to optimize startup time.
    pub fn new() -> Self {
        Self {
            model: Arc::new(RwLock::new(None)),
        }
    }
    
    /// Initialize the embedding model
    ///
    /// This is called automatically on first search, but can be called explicitly
    /// to control when the model loading happens (e.g., during startup).
    pub async fn initialize(&self) -> Result<()> {
        let mut model_guard = self.model.write().await;
        
        if model_guard.is_none() {
            tracing::info!("Loading FastEmbed model: all-MiniLM-L6-v2");
            let start = std::time::Instant::now();
            
            // Use the same model as Python implementation for compatibility
            let model = TextEmbedding::try_new(
                InitOptions::new(EmbeddingModel::AllMiniLML6V2)
                    .with_show_download_progress(true)
            )
            .context("Failed to initialize FastEmbed model")?;
            
            let duration = start.elapsed();
            tracing::info!("Model loaded in {:?}", duration);
            
            *model_guard = Some(model);
        }
        
        Ok(())
    }
    
    /// Search for insights similar to the given query
    ///
    /// Returns results sorted by relevance (highest first), filtered by the given
    /// relevance range and situation filters.
    pub async fn search(
        &self,
        query: &str,
        insights: &[Insight],
        relevance_min: f64,
        relevance_max: f64,
        situation_filters: &[String],
        limit: usize,
        offset: usize,
    ) -> Result<Vec<SearchResult>> {
        // Ensure model is loaded
        self.initialize().await?;
        
        let mut model_guard = self.model.write().await;
        let model = model_guard.as_mut().unwrap();
        
        // Generate embedding for the query
        let query_embedding = model
            .embed(vec![query.to_string()], None)?
            .into_iter()
            .next()
            .context("Failed to generate query embedding")?;
        
        // Filter insights by situation if filters are provided
        let filtered_insights: Vec<&Insight> = if situation_filters.is_empty() {
            insights.iter().collect()
        } else {
            insights
                .iter()
                .filter(|insight| {
                    situation_filters.iter().any(|filter| {
                        insight.situation.iter().any(|situation| {
                            situation.to_lowercase().contains(&filter.to_lowercase())
                        })
                    })
                })
                .collect()
        };
        
        if filtered_insights.is_empty() {
            return Ok(Vec::new());
        }
        
        // Generate embeddings for all insight contents
        let insight_texts: Vec<String> = filtered_insights
            .iter()
            .map(|insight| insight.content.clone())
            .collect();
        
        let insight_embeddings = model.embed(insight_texts, None)?;
        
        // Calculate similarities and create search results
        let mut results: Vec<SearchResult> = filtered_insights
            .into_iter()
            .zip(insight_embeddings.into_iter())
            .map(|(insight, embedding)| {
                let similarity = cosine_similarity(&query_embedding, &embedding);
                SearchResult::new(insight.clone(), similarity)
            })
            .filter(|result| result.relevance >= relevance_min && result.relevance <= relevance_max)
            .collect();
        
        // Sort by relevance (highest first)
        results.sort_by(|a, b| b.relevance.partial_cmp(&a.relevance).unwrap());
        
        // Apply pagination
        let end = std::cmp::min(offset + limit, results.len());
        if offset >= results.len() {
            Ok(Vec::new())
        } else {
            Ok(results[offset..end].to_vec())
        }
    }
    
    /// Get embedding for a single text (useful for testing)
    pub async fn embed_text(&self, text: &str) -> Result<Vec<f32>> {
        self.initialize().await?;
        
        let mut model_guard = self.model.write().await;
        let model = model_guard.as_mut().unwrap();
        
        let embeddings = model.embed(vec![text.to_string()], None)?;
        embeddings
            .into_iter()
            .next()
            .context("Failed to generate embedding")
    }
}

impl Default for SearchEngine {
    fn default() -> Self {
        Self::new()
    }
}

/// Calculate cosine similarity between two embeddings
fn cosine_similarity(a: &[f32], b: &[f32]) -> f64 {
    assert_eq!(a.len(), b.len(), "Embeddings must have the same length");
    
    let dot_product: f32 = a.iter().zip(b.iter()).map(|(x, y)| x * y).sum();
    let norm_a: f32 = a.iter().map(|x| x * x).sum::<f32>().sqrt();
    let norm_b: f32 = b.iter().map(|x| x * x).sum::<f32>().sqrt();
    
    if norm_a == 0.0 || norm_b == 0.0 {
        0.0
    } else {
        (dot_product / (norm_a * norm_b)) as f64
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::Insight;
    
    #[test]
    fn test_cosine_similarity() {
        // Test identical vectors
        let a = vec![1.0, 0.0, 0.0];
        let b = vec![1.0, 0.0, 0.0];
        assert!((cosine_similarity(&a, &b) - 1.0).abs() < 1e-6);
        
        // Test orthogonal vectors
        let a = vec![1.0, 0.0];
        let b = vec![0.0, 1.0];
        assert!(cosine_similarity(&a, &b).abs() < 1e-6);
        
        // Test opposite vectors
        let a = vec![1.0, 0.0];
        let b = vec![-1.0, 0.0];
        assert!((cosine_similarity(&a, &b) + 1.0).abs() < 1e-6);
    }
    
    #[tokio::test]
    async fn test_search_engine_creation() {
        let engine = SearchEngine::new();
        // Should not panic and should be ready for use
        assert!(engine.model.read().await.is_none()); // Model not loaded yet
    }
    
    #[tokio::test]
    #[ignore] // Requires model download, run manually for validation
    async fn test_model_initialization() {
        let engine = SearchEngine::new();
        
        // This will download the model on first run
        let result = engine.initialize().await;
        assert!(result.is_ok(), "Model initialization failed: {:?}", result);
        
        // Should be loaded now
        assert!(engine.model.read().await.is_some());
    }
    
    #[tokio::test]
    #[ignore] // Requires model download, run manually for validation
    async fn test_embedding_generation() {
        let engine = SearchEngine::new();
        
        let embedding = engine.embed_text("This is a test sentence").await;
        assert!(embedding.is_ok(), "Embedding generation failed: {:?}", embedding);
        
        let embedding = embedding.unwrap();
        assert!(!embedding.is_empty(), "Embedding should not be empty");
        assert_eq!(embedding.len(), 384, "all-MiniLM-L6-v2 should produce 384-dimensional embeddings");
    }
    
    #[tokio::test]
    #[ignore] // Requires model download, run manually for validation
    async fn test_semantic_search() {
        let engine = SearchEngine::new();
        
        // Create test insights
        let insights = vec![
            Insight::new(
                "Rust is a systems programming language".to_string(),
                vec!["programming".to_string(), "rust".to_string()],
                0.7,
            ),
            Insight::new(
                "Python is great for data science".to_string(),
                vec!["programming".to_string(), "python".to_string()],
                0.6,
            ),
            Insight::new(
                "Machine learning models need training data".to_string(),
                vec!["machine learning".to_string(), "data".to_string()],
                0.8,
            ),
        ];
        
        // Search for programming-related content
        let results = engine
            .search(
                "programming languages",
                &insights,
                0.0,
                1.0,
                &[],
                10,
                0,
            )
            .await;
        
        assert!(results.is_ok(), "Search failed: {:?}", results);
        let results = results.unwrap();
        
        // Should find programming-related insights with higher relevance
        assert!(!results.is_empty(), "Should find relevant insights");
        assert!(results[0].relevance > 0.3, "Should have reasonable relevance score");
        
        // Results should be sorted by relevance
        for i in 1..results.len() {
            assert!(
                results[i - 1].relevance >= results[i].relevance,
                "Results should be sorted by relevance"
            );
        }
    }
}
