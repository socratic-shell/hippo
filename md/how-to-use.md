# How to Use Hippo

*Simple setup guide for the Hippo AI memory system*

## Installation

1. **Install the MCP server** (specific installation instructions depend on your setup)
2. **Configure your AI client** to connect to the Hippo MCP server
3. **Set storage path** - Hippo will create a JSON file to store insights

## User Prompt Addition

Add something like this to your user prompt or system configuration:

```
{{#include ../guidance.md}}
```

## Key Principles

- **Generate insights frequently** - during consolidation moments, not continuously
- **Use situational context** - describe when/where insights occurred, not abstract categories  
- **Trust the temporal scoring** - recent, frequent, and reinforced insights will surface naturally
- **Embrace messiness** - don't over-organize, let usage patterns reveal value
- **Surface insights naturally** - weave relevant past insights into responses when helpful

## Tool Overview

- **record_insight**: Store new insights with content, situation, and importance rating
- **search_insights**: Find relevant insights using content and situational filters
- **modify_insight**: Update insights or apply reinforcement (upvote/downvote)

The system handles temporal scoring, relevance calculation, and natural decay automatically.
