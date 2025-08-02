//! Hippo: AI-Generated Insights Memory System
//!
//! A Rust implementation of the Hippo memory system for storing and retrieving
//! AI-generated insights with semantic search capabilities.
//!
//! This library provides both a programmatic API for embedding into other applications
//! and a standalone MCP server for direct usage.

pub mod models;
pub mod search;
pub mod storage;

// Re-export main types for convenience
pub use models::{HippoStorage, Insight, InsightId, SearchResult};
pub use search::SearchEngine;
pub use storage::{FileStorage, StorageError};

/// Result type used throughout the library
pub type Result<T> = anyhow::Result<T>;

/// Version information
pub const VERSION: &str = env!("CARGO_PKG_VERSION");
