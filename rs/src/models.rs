//! Core data models for the Hippo memory system
//!
//! These models maintain JSON compatibility with the Python implementation
//! to ensure seamless migration of existing memories.

use crate::constants::{
    FREQUENCY_WINDOW_DAYS, IMPORTANCE_DECAY_FACTOR, MAX_DAILY_ACCESS_ENTRIES, RECENCY_DECAY_RATE,
};
use chrono::{DateTime, NaiveDate, Utc};
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

/// Unique identifier for insights
pub type InsightId = Uuid;

/// Core insight data structure
///
/// Maintains exact JSON compatibility with Python implementation for seamless migration.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Insight {
    /// Unique identifier
    pub uuid: InsightId,

    /// The insight content - should be atomic and actionable
    pub content: String,

    /// Array of independent situational aspects describing when/where this insight occurred
    pub situation: Vec<String>,

    /// AI-assessed importance rating
    /// - 0.8+ breakthrough insights
    /// - 0.6-0.7 useful decisions  
    /// - 0.4-0.5 incremental observations
    /// - 0.1-0.3 routine details
    pub base_importance: f64,

    /// Current importance after reinforcement learning adjustments
    pub importance: f64,

    /// When this insight was created
    pub created_at: DateTime<Utc>,

    /// When importance was last modified (for decay calculations)
    pub importance_modified_at: DateTime<Utc>,
    
    /// Daily access counts: Vec<(active_day, count)>
    /// Tracks how many times this insight was accessed on each active day
    pub daily_access_counts: Vec<(u32, u32)>,
}

impl Insight {
    /// Create a new insight with the given content, situation, and importance
    pub fn new(content: String, situation: Vec<String>, importance: f64) -> Self {
        let now = Utc::now();
        let uuid = Uuid::new_v4();

        let insight = Self {
            uuid,
            content,
            situation,
            base_importance: importance,
            importance,
            created_at: now,
            importance_modified_at: now,
            daily_access_counts: Vec::new(),
        };
        
        tracing::debug!("Created new insight with daily_access_counts: {:?}", insight.daily_access_counts);
        insight
    }

    /// Apply reinforcement (upvote = 1.5x, downvote = 0.5x multiplier)
    pub fn apply_reinforcement(&mut self, upvote: bool) {
        let multiplier = if upvote { 1.5 } else { 0.5 };
        self.importance = (self.importance * multiplier).min(1.0);
        self.importance_modified_at = Utc::now();
    }

    /// Calculate days since creation (for relevance scoring)
    pub fn days_since_created(&self) -> f64 {
        let duration = Utc::now().signed_duration_since(self.created_at);
        duration.num_milliseconds() as f64 / (1000.0 * 60.0 * 60.0 * 24.0)
    }

    /// Calculate days since importance was last modified (for decay)
    pub fn days_since_importance_modified(&self) -> f64 {
        let duration = Utc::now().signed_duration_since(self.importance_modified_at);
        duration.num_milliseconds() as f64 / (1000.0 * 60.0 * 60.0 * 24.0)
    }
    
    /// Compute current importance with temporal decay
    /// Formula: current_importance = importance * (0.9 ^ days_since_modified)
    pub fn compute_current_importance(&self) -> f64 {
        let days_elapsed = self.days_since_importance_modified();
        let decay_factor = IMPORTANCE_DECAY_FACTOR.powf(days_elapsed);
        self.importance * decay_factor
    }
    
    /// Record an access to this insight on the given active day
    pub fn record_access(&mut self, current_active_day: u32) {
        tracing::debug!("Recording access for insight {} on day {}", self.uuid, current_active_day);
        
        // Find today's entry in the access counts list
        if let Some(last_entry) = self.daily_access_counts.last_mut() {
            if last_entry.0 == current_active_day {
                // Increment existing entry for today
                last_entry.1 += 1;
                tracing::debug!("Incremented access count to {} for day {}", last_entry.1, current_active_day);
                return;
            }
        }
        
        // Add new entry for today
        self.daily_access_counts.push((current_active_day, 1));
        tracing::debug!("Added new access entry: ({}, 1)", current_active_day);
        
        // Trim list to max entries (remove oldest)
        if self.daily_access_counts.len() > MAX_DAILY_ACCESS_ENTRIES {
            self.daily_access_counts.remove(0);
            tracing::debug!("Trimmed access counts to {} entries", MAX_DAILY_ACCESS_ENTRIES);
        }
    }
    
    /// Calculate frequency as accesses per active day over a recent window
    pub fn calculate_frequency(&self, current_active_day: u32, window_days: u32) -> f64 {
        if self.daily_access_counts.is_empty() {
            return 0.0;
        }
        
        // Use recent window instead of full history to avoid frequency dilution
        let window_start = current_active_day.saturating_sub(window_days - 1);
        let recent_entries: Vec<_> = self.daily_access_counts
            .iter()
            .filter(|(day, _)| *day >= window_start)
            .collect();
            
        if recent_entries.is_empty() {
            return 0.0;
        }
        
        let oldest_recent_day = recent_entries.first().unwrap().0;
        let newest_recent_day = recent_entries.last().unwrap().0;
        let recent_days_spanned = newest_recent_day - oldest_recent_day + 1;
        let total_recent_accesses: u32 = recent_entries.iter().map(|(_, count)| *count).sum();
        
        total_recent_accesses as f64 / recent_days_spanned as f64
    }
    
    /// Calculate frequency using default window
    pub fn calculate_frequency_default(&self, current_active_day: u32) -> f64 {
        self.calculate_frequency(current_active_day, FREQUENCY_WINDOW_DAYS)
    }
    
    /// Calculate recency score using exponential decay based on active days since last access
    pub fn calculate_recency_score(&self, current_active_day: u32, decay_rate: f64) -> f64 {
        if self.daily_access_counts.is_empty() {
            // This should never happen since creation records first access,
            // but handle gracefully just in case
            return 0.0;
        }
        
        let last_access_day = self.daily_access_counts.last().unwrap().0;
        let active_days_since_access = current_active_day - last_access_day;
        (-decay_rate * active_days_since_access as f64).exp()
    }
    
    /// Calculate recency score using default decay rate
    pub fn calculate_recency_score_default(&self, current_active_day: u32) -> f64 {
        self.calculate_recency_score(current_active_day, RECENCY_DECAY_RATE)
    }
}

/// Search result with relevance scoring
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SearchResult {
    /// The matching insight
    pub insight: Insight,

    /// Semantic similarity score (0.0 to 1.0+)
    pub relevance: f64,

    /// Additional computed fields for API compatibility
    pub days_since_created: f64,
    pub days_since_importance_modified: f64,
}

impl SearchResult {
    /// Create a search result from an insight and relevance score
    pub fn new(insight: Insight, relevance: f64) -> Self {
        let days_since_created = insight.days_since_created();
        let days_since_importance_modified = insight.days_since_importance_modified();

        Self {
            insight,
            relevance,
            days_since_created,
            days_since_importance_modified,
        }
    }
}

/// Main storage interface trait
///
/// Abstracts over different storage backends (file-based, database, etc.)
#[async_trait::async_trait]
pub trait HippoStorage: Send + Sync {
    /// Store a new insight
    async fn store_insight(&mut self, insight: Insight) -> crate::Result<()>;

    /// Retrieve an insight by ID
    async fn get_insight(&self, id: InsightId) -> crate::Result<Option<Insight>>;

    /// Update an existing insight
    async fn update_insight(&mut self, insight: Insight) -> crate::Result<()>;

    /// Get all insights (for search operations)
    async fn get_all_insights(&self) -> crate::Result<Vec<Insight>>;

    /// Apply reinforcement to multiple insights
    async fn apply_reinforcement(
        &mut self,
        upvotes: Vec<InsightId>,
        downvotes: Vec<InsightId>,
    ) -> crate::Result<()>;
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_insight_creation() {
        let content = "Test insight content".to_string();
        let situation = vec!["testing".to_string(), "unit tests".to_string()];
        let importance = 0.7;

        let insight = Insight::new(content.clone(), situation.clone(), importance);

        assert_eq!(insight.content, content);
        assert_eq!(insight.situation, situation);
        assert_eq!(insight.base_importance, importance);
        assert_eq!(insight.importance, importance);
        assert!(insight.uuid != Uuid::nil());
    }

    #[test]
    fn test_reinforcement() {
        let mut insight = Insight::new("Test".to_string(), vec!["test".to_string()], 0.6);

        // Test upvote
        insight.apply_reinforcement(true);
        assert!((insight.importance - 0.9).abs() < 1e-10); // 0.6 * 1.5

        // Test downvote
        insight.apply_reinforcement(false);
        assert!((insight.importance - 0.45).abs() < 1e-10); // 0.9 * 0.5

        // Test importance cap at 1.0
        let mut high_insight = Insight::new(
            "High importance".to_string(),
            vec!["important".to_string()],
            0.8,
        );
        high_insight.apply_reinforcement(true);
        assert_eq!(high_insight.importance, 1.0); // Capped at 1.0
    }

    #[test]
    fn test_days_calculation() {
        let insight = Insight::new("Test".to_string(), vec!["test".to_string()], 0.5);

        // Should be very close to 0 for a just-created insight
        assert!(insight.days_since_created() < 0.001);
        assert!(insight.days_since_importance_modified() < 0.001);
    }
}

// MCP Tool Parameter Structs

/// Parameters for recording a new insight
#[derive(Debug, Deserialize, JsonSchema)]
pub struct RecordInsightParams {
    /// The insight content - should be atomic and actionable
    pub content: String,
    /// Array of independent situational aspects describing when/where this insight occurred
    pub situation: Vec<String>,
    /// AI-assessed importance rating: 0.8+ breakthrough insights, 0.6-0.7 useful decisions, 0.4-0.5 incremental observations, 0.1-0.3 routine details
    pub importance: f64,
}

/// Parameters for searching insights
#[derive(Debug, Deserialize, JsonSchema)]
pub struct SearchInsightsParams {
    /// Search query for insight content
    pub query: String,
    /// Filter results by matching any situation elements using partial matching
    #[serde(default)]
    pub situation_filter: Option<Vec<String>>,
    /// Relevance range filter
    #[serde(default)]
    pub relevance_range: Option<RelevanceRange>,
    /// Result pagination
    #[serde(default)]
    pub limit: Option<PaginationLimit>,
}

/// Relevance range filter
#[derive(Debug, Deserialize, JsonSchema)]
pub struct RelevanceRange {
    #[serde(default = "default_min_relevance")]
    pub min: f64,
    pub max: Option<f64>,
}

fn default_min_relevance() -> f64 {
    0.1
}

/// Pagination parameters
#[derive(Debug, Deserialize, JsonSchema)]
pub struct PaginationLimit {
    #[serde(default)]
    pub offset: usize,
    #[serde(default = "default_count")]
    pub count: usize,
}

fn default_count() -> usize {
    10
}

/// Parameters for modifying an existing insight
#[derive(Debug, Deserialize, JsonSchema)]
pub struct ModifyInsightParams {
    /// UUID of the insight to modify
    pub uuid: InsightId,
    /// New insight content (optional - only provide if changing)
    pub content: Option<String>,
    /// New situational aspects array (optional - only provide if changing)
    pub situation: Option<Vec<String>>,
    /// New importance rating (optional - only provide if changing)
    pub importance: Option<f64>,
    /// Reinforcement to apply with modification
    #[serde(default = "default_reinforce")]
    pub reinforce: ReinforcementType,
}

/// Parameters for reinforcement feedback
#[derive(Debug, Deserialize, JsonSchema)]
pub struct ReinforceInsightParams {
    /// Array of UUIDs to upvote (1.5x importance multiplier)
    #[serde(default)]
    pub upvotes: Vec<InsightId>,
    /// Array of UUIDs to downvote (0.5x importance multiplier)
    #[serde(default)]
    pub downvotes: Vec<InsightId>,
}

/// Reinforcement type for modifications
#[derive(Debug, Deserialize, JsonSchema)]
#[serde(rename_all = "lowercase")]
pub enum ReinforcementType {
    Upvote,
    Downvote,
    None,
}

fn default_reinforce() -> ReinforcementType {
    ReinforcementType::Upvote
}

/// Metadata for tracking global state like logical days
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HippoMetadata {
    /// Logical day counter that increments each calendar day
    pub active_day_counter: u32,
    
    /// Last calendar date when the system was used (ISO format)
    pub last_calendar_date_used: Option<String>,
}

impl Default for HippoMetadata {
    fn default() -> Self {
        Self {
            active_day_counter: 0,
            last_calendar_date_used: None,
        }
    }
}

impl HippoMetadata {
    /// Get the current active day, incrementing if it's a new calendar day
    /// Sets `updated` to true if the active day counter was incremented
    pub fn get_current_active_day(&mut self, updated: &mut bool) -> u32 {
        let today = chrono::Utc::now().date_naive();
        let today_str = today.to_string();
        
        // Check if this is a new calendar day
        let is_new_day = match &self.last_calendar_date_used {
            None => true,
            Some(last_date_str) => {
                match NaiveDate::parse_from_str(last_date_str, "%Y-%m-%d") {
                    Ok(last_date) => last_date != today,
                    Err(_) => true, // If we can't parse, treat as new day
                }
            }
        };
        
        if is_new_day {
            self.active_day_counter += 1;
            self.last_calendar_date_used = Some(today_str);
            *updated = true;
        }
        
        self.active_day_counter
    }
}
