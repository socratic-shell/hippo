//! Constants for Hippo insight management system
//!
//! These constants match the Python implementation for compatibility.

// Temporal scoring parameters

/// Number of recent active days to consider for frequency calculation.
pub const FREQUENCY_WINDOW_DAYS: u32 = 30;

/// Decay rate per active day for recency scoring.
pub const RECENCY_DECAY_RATE: f64 = 0.05;

/// Importance decay factor per day (0.9^days_since_modified).
pub const IMPORTANCE_DECAY_FACTOR: f64 = 0.9;

// Storage limits

/// Maximum number of daily access count entries to store per insight.
pub const MAX_DAILY_ACCESS_ENTRIES: usize = 90;

// Reinforcement parameters

/// Multiplier applied to importance when insight is upvoted.
pub const UPVOTE_MULTIPLIER: f64 = 1.5;

/// Multiplier applied to importance when insight is downvoted.
pub const DOWNVOTE_MULTIPLIER: f64 = 0.5;

// Search relevance formula weights

/// Weight for recency component in search relevance formula.
pub const RELEVANCE_WEIGHT_RECENCY: f64 = 0.30;

/// Weight for frequency component in search relevance formula.
pub const RELEVANCE_WEIGHT_FREQUENCY: f64 = 0.20;

/// Weight for importance component in search relevance formula.
pub const RELEVANCE_WEIGHT_IMPORTANCE: f64 = 0.35;

/// Weight for context (situation matching) component in search relevance formula.
pub const RELEVANCE_WEIGHT_CONTEXT: f64 = 0.15;

// Frequency normalization

/// Maximum reasonable frequency (accesses per day) for normalization to 0-1 range.
pub const MAX_REASONABLE_FREQUENCY: f64 = 10.0;

// Search filtering thresholds

/// Minimum content relevance score to consider a match.
pub const CONTENT_MATCH_THRESHOLD: f64 = 0.4;

/// Minimum situation relevance score to consider a match.
pub const SITUATION_MATCH_THRESHOLD: f64 = 0.4;
