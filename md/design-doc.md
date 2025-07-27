# Hippo MVP Design Document

*AI-Generated Salient Insights - Minimal Viable Prototype*

## Core Hypothesis

**Can AI-generated insights + reinforcement learning + embracing messiness actually surface more valuable knowledge than traditional structured memory systems?**

The key insights: 
- **Generate insights cheaply and frequently** - let AI create many insights without perfect organization
- **Let natural selection through reinforcement determine what survives** - user feedback shapes what becomes prominent
- **Embrace the mess** - don't try to create highly structured taxonomies or perfect categorization
- **Trust temporal scoring** - let time, usage patterns, and reinforcement naturally organize knowledge

This approach contrasts with traditional knowledge management that emphasizes upfront structure, careful categorization, and manual curation. Instead, Hippo bets that organic emergence through usage patterns can be more effective than imposed structure.

## MVP Scope

### What It Does
1. **Automatic Insight Generation**: AI generates insights continuously during conversation at natural moments (consolidation, "make it so", "ah-ha!" moments, pattern recognition)
2. **Simple Storage**: Single JSON file with configurable path
3. **Natural Decay**: Insights lose relevance over time unless reinforced
4. **Reinforcement**: During consolidation moments, user can upvote/downvote insights
5. **Context-Aware Search**: Retrieval considers both content and situational context with fuzzy matching

### What It Doesn't Do (Yet)
- Graph connections between insights
- Complex reinforcement algorithms
- Cross-session learning
- Memory hierarchy (generic vs project-specific)
- Automatic insight detection triggers

## Temporal Scoring System

### Core Concept
Insights are ranked using a composite relevance score that combines four factors based on research in information retrieval systems. This ensures recently accessed, frequently used, and important insights surface first while maintaining contextual relevance.

### Composite Relevance Formula
```
relevance = 0.30 × recency + 0.20 × frequency + 0.35 × importance + 0.15 × context
```

**Weighting Rationale:**
- **Importance (35%)**: Highest weight - user feedback through reinforcement learning
- **Recency (30%)**: Second highest - recently accessed insights are more likely relevant
- **Frequency (20%)**: Regular usage indicates ongoing value
- **Context (15%)**: Situational matching for query relevance

### Temporal Factors

#### Recency Score
Exponential decay based on days since last access:
```
recency = exp(-0.05 × days_since_last_access)
```
- Recent access (day 0): score ≈ 1.0
- One week old: score ≈ 0.7
- One month old: score ≈ 0.2

#### Frequency Score
Uses 30-day sliding window to prevent dilution from ancient history:
```
frequency = total_accesses_in_last_30_days / 30
```
- Normalized to 0-1 range with maximum reasonable frequency cap
- Prevents "funny frequency behavior" where long gaps reduce scores

#### Active Day System
Time advances only when system is actively used, making scoring "vacation-proof":
- Calendar days without usage don't advance temporal calculations
- Ensures insights don't decay during periods of non-use
- Maintains relevance relationships based on actual usage patterns

### Reinforcement Learning

#### Importance Modification
- **Upvote**: `new_importance = min(1.0, current_importance × 1.5)`
- **Downvote**: `new_importance = current_importance × 0.5`
- **Decay**: `current_importance = base_importance × 0.9^days_since_reinforcement`

#### Learning Principle
User feedback (upvotes/downvotes) directly modifies importance, which has the highest weight in relevance calculation. This creates a feedback loop where valuable insights become more prominent over time.

### Search Architecture

#### Two-Phase Process
1. **Scoring Phase**: Compute relevance for all insights with minimal filtering
2. **Filtering Phase**: Apply user-specified relevance ranges and pagination

#### Distribution Metadata
Search returns relevance distribution across all insights for the given query/situation, helping clients understand what additional data exists beyond filtered results.

#### Semantic Matching
- **Content**: Uses sentence transformers for semantic similarity with substring boost
- **Situation**: Combines exact matching (high score) with semantic similarity fallback
- **Thresholds**: Content and situation relevance must exceed 0.4 to be considered matches

## Data Model

```json
{
  "active_day_counter": 15,
  "last_calendar_date_used": "2025-07-26", 
  "insights": [
    {
      "uuid": "abc123-def456-789",
      "content": "User prefers dialogue format over instruction lists",
      "situation": ["design discussion", "collaboration patterns"],
      "base_importance": 0.8,
      "created_at": "2025-07-23T17:00:00Z",
      "importance_last_modified_at": "2025-07-25T10:30:00Z",
      "daily_access_counts": [
        [1, 3],   // Active day 1: 3 accesses
        [5, 2],   // Active day 5: 2 accesses  
        [15, 1]   // Active day 15: 1 access
      ]
    }
  ]
}
```

### Key Design Principles

**Active Day System**: Time only advances when system is used, preventing decay during vacations or periods of non-use.

**Bounded Storage**: Access history limited to recent entries (typically 90) to prevent unbounded growth while maintaining sufficient data for frequency calculations.

**Reinforcement Decay**: Importance modifications decay over time, requiring ongoing reinforcement to maintain high relevance.

**Situational Context**: Multi-element situation arrays enable flexible matching against various contextual filters.

## System Constants

Core parameters that tune the temporal scoring behavior:

- **Recency decay rate**: 0.05 per active day
- **Frequency window**: 30 active days  
- **Upvote multiplier**: 1.5×
- **Downvote multiplier**: 0.5×
- **Relevance weights**: 30% recency, 20% frequency, 35% importance, 15% context
- **Match thresholds**: 0.4 for content and situation relevance
- **Maximum reasonable frequency**: 10 accesses per day (for normalization)

## Philosophy: Embracing Messiness

Traditional knowledge management systems emphasize structure: taxonomies, categories, tags, hierarchies. Hippo takes the opposite approach - **embrace the mess** and let value emerge organically.

**Why Embrace Messiness:**
- **Cognitive overhead**: Structured systems require constant categorization decisions
- **Premature optimization**: We often don't know what will be valuable until later
- **Natural emergence**: Usage patterns reveal value better than upfront planning
- **Reduced friction**: No need to "file" insights perfectly before storing them

**How Messiness Works in Hippo:**
- **Situational context** instead of rigid categories - insights tagged with when/where they occurred
- **Fuzzy matching** - "debugging React" can surface "debugging authentication" insights  
- **Temporal scoring** - let time and usage naturally separate wheat from chaff
- **Reinforcement learning** - user feedback shapes what becomes prominent over time

The bet: A messy system with good search and temporal scoring will outperform a perfectly organized system that's too expensive to maintain.

## Implementation Architecture

### MCP Server Interface
Hippo implements the Model Context Protocol (MCP) providing tools for:
- **record_insight**: Create new insights with content, situation, and importance
- **search_insights**: Query insights with semantic and situational filters  
- **modify_insight**: Update content or apply reinforcement (upvote/downvote)

### Storage Layer
- **JSON file storage**: Single configurable file for persistence
- **In-memory operations**: All temporal calculations performed in memory
- **Bounded growth**: Access history automatically pruned to prevent unbounded storage

### Search Engine
- **Semantic similarity**: Uses sentence transformers for content matching
- **Situational matching**: Combines exact and semantic matching for context
- **Composite scoring**: Real-time relevance calculation using temporal factors
- **Distribution metadata**: Provides relevance distribution for client insight

## Testing Strategy

### Integration Testing Philosophy
Tests validate behavior through stable MCP interfaces rather than internal implementation details:

- **Temporal scenarios**: Create insights, advance time, verify scoring changes
- **Controllable time**: Test time controller allows arbitrary day advancement
- **In-memory storage**: Tests run without disk I/O for speed and isolation
- **Realistic workflows**: Tests mirror actual usage patterns

### Key Test Coverage
- **Recency decay**: Validates exponential decay over time
- **Frequency windows**: Confirms 30-day sliding window prevents dilution
- **Reinforcement learning**: Verifies upvote/downvote effects on importance
- **Search distribution**: Ensures metadata accurately reflects available data

## Future Considerations

### Potential Enhancements
- **Graph connections**: Link related insights for enhanced discovery
- **Automatic triggers**: Detect natural insight generation moments
- **Cross-session learning**: Adapt scoring based on usage patterns
- **Memory hierarchy**: Separate generic vs project-specific insights

## Key Design Decisions

### Active Day System
Time advances only when the system is actively used, making all temporal calculations "vacation-proof". This ensures insights don't decay during periods of non-use while maintaining meaningful temporal relationships.

### Composite Relevance Scoring  
Rather than simple recency or frequency ranking, Hippo uses a research-based weighted formula combining multiple factors. This provides more nuanced ranking that reflects actual insight value.

### Reinforcement Learning Integration
User feedback directly modifies importance scores, which carry the highest weight in relevance calculation. This creates a feedback loop where valuable insights become more prominent over time.

### Situational Context Matching
Insights include multi-element situation arrays enabling flexible contextual search. This allows matching against various aspects of when/where insights occurred.

### Bounded Storage Growth
Access history is automatically pruned to prevent unbounded growth while maintaining sufficient data for accurate frequency calculations.

## Research Foundation

The temporal scoring system is based on established research in information retrieval systems, specifically the principle that relevance should combine:

- **Temporal factors**: Recency and frequency of access
- **Content factors**: Semantic similarity and importance  
- **Context factors**: Situational relevance to current query

The specific weighting (30/20/35/15%) reflects the relative importance of these factors for knowledge management systems where user feedback (importance) should dominate over purely temporal factors.

## Validation Approach

The system includes comprehensive integration tests that validate temporal behavior through realistic scenarios:

- Create insights with known characteristics
- Advance time using controllable test infrastructure  
- Verify that relevance scores change as expected
- Confirm that reinforcement learning affects ranking appropriately

This testing approach ensures the temporal scoring system behaves correctly over time and validates the core hypothesis that AI-generated insights + user reinforcement can surface valuable knowledge effectively.

---

*For detailed API specifications and implementation details, consult the source code and test suite.*
