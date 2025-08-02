//! Hippo MCP Server
//!
//! A high-performance Rust implementation of the Hippo AI-Generated Insights Memory System
//! using the Model Context Protocol (MCP) for seamless integration with AI assistants.

use std::future::Future;
use std::path::PathBuf;
use std::sync::Arc;

use anyhow::Result;
use clap::Parser;
use rmcp::{
    handler::server::{router::tool::ToolRouter, tool::Parameters},
    model::*,
    tool, tool_handler, tool_router,
    transport::stdio,
    ErrorData as McpError, ServerHandler, ServiceExt,
};
use tokio::sync::Mutex;
use tracing_subscriber::{self, layer::SubscriberExt, util::SubscriberInitExt, EnvFilter};

use hippo::{
    models::{
        Insight, ModifyInsightParams, RecordInsightParams, ReinforceInsightParams,
        ReinforcementType, SearchInsightsParams,
    },
    FileStorage, HippoStorage, SearchEngine,
};

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

/// Hippo MCP Server implementation
#[derive(Clone)]
pub struct HippoServer {
    storage: Arc<Mutex<FileStorage>>,
    search_engine: Arc<SearchEngine>,
    tool_router: ToolRouter<Self>,
}

#[tool_router]
impl HippoServer {
    /// Create a new Hippo server instance
    pub async fn new(memory_dir: PathBuf) -> Result<Self> {
        let storage = FileStorage::new(&memory_dir).await?;
        let search_engine = SearchEngine::new();

        Ok(Self {
            storage: Arc::new(Mutex::new(storage)),
            search_engine: Arc::new(search_engine),
            tool_router: Self::tool_router(),
        })
    }

    /// Record a new insight during consolidation moments
    #[tool(description = "Record a new insight during consolidation moments")]
    async fn hippo_record_insight(
        &self,
        Parameters(params): Parameters<RecordInsightParams>,
    ) -> Result<CallToolResult, McpError> {
        tracing::info!("Recording new insight: {}", params.content);

        // Validate importance range
        if params.importance < 0.0 || params.importance > 1.0 {
            return Err(McpError::invalid_params(
                "Importance must be between 0.0 and 1.0",
                None,
            ));
        }

        // Create new insight
        let insight = Insight::new(params.content, params.situation, params.importance);
        let insight_id = insight.uuid;

        // Store insight
        let mut storage = self.storage.lock().await;
        storage.store_insight(insight).await.map_err(|e| {
            McpError::internal_error(format!("Failed to store insight: {e}"), None)
        })?;

        Ok(CallToolResult::success(vec![Content::text(format!(
            "Recorded insight with UUID: {insight_id}"
        ))]))
    }

    /// Search for relevant insights based on content and situation
    #[tool(description = "Search for relevant insights based on content and situation")]
    async fn hippo_search_insights(
        &self,
        Parameters(params): Parameters<SearchInsightsParams>,
    ) -> Result<CallToolResult, McpError> {
        tracing::info!("Searching insights for query: {}", params.query);

        let storage = self.storage.lock().await;
        let insights = storage.get_all_insights().await.map_err(|e| {
            McpError::internal_error(format!("Failed to load insights: {e}"), None)
        })?;

        // Apply situation filter if provided
        let filtered_insights: Vec<_> = if let Some(situation_filters) = &params.situation_filter {
            insights
                .into_iter()
                .filter(|insight| {
                    situation_filters.iter().any(|filter| {
                        insight.situation.iter().any(|situation| {
                            situation.to_lowercase().contains(&filter.to_lowercase())
                        })
                    })
                })
                .collect()
        } else {
            insights
        };

        // If no insights match situation filter, return empty results
        if filtered_insights.is_empty() {
            return Ok(CallToolResult::success(vec![Content::text(
                serde_json::to_string_pretty(&serde_json::json!({
                    "results": [],
                    "total_count": 0
                }))
                .unwrap(),
            )]));
        }

        // Perform semantic search
        let relevance_range = params.relevance_range.as_ref();
        let min_relevance = relevance_range.map(|r| r.min).unwrap_or(0.1);
        let max_relevance = relevance_range.and_then(|r| r.max).unwrap_or(f64::INFINITY);

        let situation_filters = params.situation_filter.as_deref().unwrap_or(&[]);

        let limit = params.limit.as_ref();
        let offset = limit.map(|l| l.offset).unwrap_or(0);
        let count = limit.map(|l| l.count).unwrap_or(10);

        let search_results = self
            .search_engine
            .search(
                &params.query,
                &filtered_insights,
                min_relevance,
                max_relevance,
                situation_filters,
                count,
                offset,
            )
            .await
            .map_err(|e| McpError::internal_error(format!("Search failed: {e}"), None))?;

        let total_count = search_results.len();

        let response = serde_json::json!({
            "results": search_results,
            "total_count": total_count
        });

        Ok(CallToolResult::success(vec![Content::text(
            serde_json::to_string_pretty(&response).unwrap(),
        )]))
    }

    /// Modify an existing insight's content, situation, or importance
    #[tool(description = "Modify an existing insight's content, situation, or importance")]
    async fn hippo_modify_insight(
        &self,
        Parameters(params): Parameters<ModifyInsightParams>,
    ) -> Result<CallToolResult, McpError> {
        tracing::info!("Modifying insight: {}", params.uuid);

        let mut storage = self.storage.lock().await;

        // Get existing insight
        let mut insight = storage
            .get_insight(params.uuid)
            .await
            .map_err(|e| {
                McpError::internal_error(format!("Failed to retrieve insight: {e}"), None)
            })?
            .ok_or_else(|| McpError::invalid_params("Insight not found", None))?;

        // Apply modifications
        if let Some(content) = params.content {
            insight.content = content;
        }

        if let Some(situation) = params.situation {
            insight.situation = situation;
        }

        if let Some(importance) = params.importance {
            if !(0.0..=1.0).contains(&importance) {
                return Err(McpError::invalid_params(
                    "Importance must be between 0.0 and 1.0",
                    None,
                ));
            }
            insight.base_importance = importance;
            insight.current_importance = importance;
        }

        // Apply reinforcement
        match params.reinforce {
            ReinforcementType::Upvote => insight.apply_reinforcement(true),
            ReinforcementType::Downvote => insight.apply_reinforcement(false),
            ReinforcementType::None => {}
        }

        // Update storage
        storage.update_insight(insight).await.map_err(|e| {
            McpError::internal_error(format!("Failed to update insight: {e}"), None)
        })?;

        Ok(CallToolResult::success(vec![Content::text(format!(
            "Modified insight: {}",
            params.uuid
        ))]))
    }

    /// Apply reinforcement feedback to multiple insights
    #[tool(description = "Apply reinforcement feedback to multiple insights")]
    async fn hippo_reinforce_insight(
        &self,
        Parameters(params): Parameters<ReinforceInsightParams>,
    ) -> Result<CallToolResult, McpError> {
        tracing::info!(
            "Applying reinforcement: {} upvotes, {} downvotes",
            params.upvotes.len(),
            params.downvotes.len()
        );

        let mut storage = self.storage.lock().await;
        storage
            .apply_reinforcement(params.upvotes, params.downvotes)
            .await
            .map_err(|e| {
                McpError::internal_error(format!("Failed to apply reinforcement: {e}"), None)
            })?;

        Ok(CallToolResult::success(vec![Content::text(
            "Applied reinforcement feedback",
        )]))
    }
}

#[tool_handler]
impl ServerHandler for HippoServer {
    fn get_info(&self) -> ServerInfo {
        ServerInfo {
            protocol_version: ProtocolVersion::V_2024_11_05,
            capabilities: ServerCapabilities::builder()
                .enable_tools()
                .build(),
            server_info: Implementation::from_build_env(),
            instructions: Some(
                "Hippo AI-Generated Insights Memory System. Use this server to record, search, modify, and reinforce AI-generated insights. The system uses semantic search with FastEmbed for high-performance retrieval and reinforcement learning for importance scoring.".to_string()
            ),
        }
    }
}

#[tokio::main]
async fn main() -> Result<()> {
    let args = Args::parse();

    // Initialize logging
    let log_level = std::env::var("HIPPO_LOG")
        .unwrap_or_else(|_| if args.debug { "debug" } else { "info" }.to_string());
    
    // Create log file in memory directory
    let log_file = tracing_appender::rolling::never(&args.memory_dir, "hippo.log");
    let (non_blocking_file, _guard) = tracing_appender::non_blocking(log_file);
    
    // Set up logging to both console and file
    let env_filter = EnvFilter::from_default_env()
        .add_directive(format!("hippo={log_level}").parse()?)
        .add_directive("fastembed=info".parse()?);
    
    tracing_subscriber::registry()
        .with(tracing_subscriber::fmt::layer().with_writer(std::io::stderr))  // Console output
        .with(tracing_subscriber::fmt::layer().with_writer(non_blocking_file).with_ansi(false))  // File output
        .with(env_filter)
        .init();
    
    // Keep the guard alive for the duration of the program
    std::mem::forget(_guard);

    tracing::info!("Starting Hippo MCP Server v{}", hippo::VERSION);
    tracing::info!("Memory directory: {}", args.memory_dir.display());

    // Expand tilde in path
    let memory_dir = if args.memory_dir.starts_with("~") {
        let home = std::env::var("HOME").unwrap_or_else(|_| "/tmp".to_string());
        PathBuf::from(args.memory_dir.to_string_lossy().replace("~", &home))
    } else {
        args.memory_dir
    };

    // Create server instance
    let server = HippoServer::new(memory_dir).await?;

    // Start MCP server with stdio transport
    let service = server.serve(stdio()).await?;

    tracing::info!("Hippo MCP Server ready");
    service.waiting().await?;

    Ok(())
}
