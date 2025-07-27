# How to Use Hippo

*Simple setup guide for the Hippo AI memory system*

## Installation

1. **Install the MCP server** (specific installation instructions depend on your setup)
2. **Configure your AI client** to connect to the Hippo MCP server
3. **Set storage path** - Hippo will create a JSON file to store insights

## User Prompt Addition

Add something like this to your user prompt or system configuration:

```
You have access to a memory system called Hippo through MCP tools. Use it to:

1. **Record insights** during natural consolidation moments (when we checkpoint work, 
   say "make it so", or wrap up substantial conversations). Generate insights about 
   what we discovered, decided, or learned.

2. **Search for relevant insights** when users ask questions, when they seem to be 
   referencing past conversations, or when you want to verify information you're 
   about to share. Surface relevant insights naturally in your responses.

3. **Suggest reinforcement** during consolidation - analyze which insights were 
   actually useful in our session and suggest upvotes/downvotes based on usage patterns.

The system embraces messiness - don't worry about perfect categorization. Use 
situational context (when/where insights occurred) rather than rigid categories. 
Let temporal scoring and user feedback naturally organize knowledge over time.
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
