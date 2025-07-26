"""Constants for Hippo insight management system."""

# Temporal scoring parameters
FREQUENCY_WINDOW_DAYS = 30
"""Number of recent active days to consider for frequency calculation."""

RECENCY_DECAY_RATE = 0.05
"""Decay rate per active day for recency scoring (default 0.05)."""

# Storage limits
MAX_DAILY_ACCESS_ENTRIES = 90
"""Maximum number of daily access count entries to store per insight."""

# Reinforcement parameters
UPVOTE_MULTIPLIER = 1.5
"""Multiplier applied to importance when insight is upvoted."""

DOWNVOTE_MULTIPLIER = 0.5
"""Multiplier applied to importance when insight is downvoted."""

# Search relevance formula weights
RELEVANCE_WEIGHT_RECENCY = 0.30
"""Weight for recency component in search relevance formula."""

RELEVANCE_WEIGHT_FREQUENCY = 0.20
"""Weight for frequency component in search relevance formula."""

RELEVANCE_WEIGHT_IMPORTANCE = 0.35
"""Weight for importance component in search relevance formula."""

RELEVANCE_WEIGHT_CONTEXT = 0.15
"""Weight for context (situation matching) component in search relevance formula."""

# Frequency normalization
MAX_REASONABLE_FREQUENCY = 10.0
"""Maximum reasonable frequency (accesses per day) for normalization to 0-1 range."""

# Search filtering thresholds
CONTENT_MATCH_THRESHOLD = 0.4
"""Minimum content relevance score to consider a match."""

SITUATION_MATCH_THRESHOLD = 0.4
"""Minimum situation relevance score to consider a match."""
