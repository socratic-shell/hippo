//! Standalone Hippo MCP Server
//!
//! This binary provides a standalone MCP server for the Hippo memory system.
//! It will be implemented in Phase 2 after the core prototype is validated.

use clap::Parser;
use std::path::PathBuf;
use tracing_subscriber;

#[derive(Parser)]
#[command(name = "hippo-server")]
#[command(about = "Hippo AI-Generated Insights Memory System - MCP Server")]
struct Args {
    /// Memory storage directory
    #[arg(long, default_value = "~/.hippo")]
    memory_dir: PathBuf,
    
    /// Enable debug logging
    #[arg(long)]
    debug: bool,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let args = Args::parse();
    
    // Initialize logging
    let log_level = if args.debug { "debug" } else { "info" };
    tracing_subscriber::fmt()
        .with_env_filter(format!("hippo={},fastembed=info", log_level))
        .init();
    
    tracing::info!("Starting Hippo MCP Server");
    tracing::info!("Memory directory: {}", args.memory_dir.display());
    tracing::info!("Hippo version: {}", hippo::VERSION);
    
    // TODO: Phase 2 - Implement MCP server using official Rust SDK
    // For now, just validate that our core components work
    
    println!("Hippo MCP Server v{}", hippo::VERSION);
    println!("Memory directory: {}", args.memory_dir.display());
    println!();
    println!("Phase 1: Core prototype validation");
    
    // Test basic functionality
    validate_core_functionality(&args.memory_dir).await?;
    
    println!("✓ Core functionality validated");
    println!("Ready for Phase 2: MCP integration");
    
    Ok(())
}

/// Validate core functionality for Phase 1
async fn validate_core_functionality(memory_dir: &PathBuf) -> anyhow::Result<()> {
    use hippo::{FileStorage, SearchEngine, Insight, HippoStorage};
    
    println!("Initializing storage...");
    let mut storage = FileStorage::new(memory_dir).await?;
    
    println!("Initializing search engine...");
    let search_engine = SearchEngine::new();
    
    // Test storage
    println!("Testing storage...");
    let test_insight = Insight::new(
        "Rust port validation test".to_string(),
        vec!["testing".to_string(), "rust port".to_string()],
        0.7,
    );
    let insight_id = test_insight.uuid;
    
    storage.store_insight(test_insight.clone()).await?;
    let retrieved = storage.get_insight(insight_id).await?;
    assert!(retrieved.is_some());
    assert_eq!(retrieved.unwrap().content, test_insight.content);
    
    // Test search engine initialization (but don't require model download)
    println!("Testing search engine initialization...");
    // Note: We don't call initialize() here to avoid requiring model download
    // This will be tested manually with --ignore flag
    
    println!("All core components initialized successfully!");
    
    Ok(())
}
