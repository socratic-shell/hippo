# Hippo: AI-Generated Insights Memory System

*An experiment in collaborative memory through reinforcement learning*

## Overview

Hippo is a memory system designed for AI-human collaboration that automatically generates insights during conversations and uses reinforcement learning to surface the most valuable ones over time.

## Core Hypothesis

**AI-generated insights + user reinforcement > manual curation**

Traditional memory systems require users to manually decide what to remember. Hippo tests whether AI can generate insights automatically during natural conversation, then use user feedback to learn which insights are truly valuable.

## Key Features

1. **Automatic Generation**: AI generates insights during consolidation moments ("Make it so", checkpointing)
2. **Temporal Decay**: Insights lose relevance over time unless reinforced
3. **Reinforcement Learning**: User feedback (upvotes/downvotes) affects future surfacing
4. **Context-Aware Search**: Retrieval considers both content and situational context
5. **Hybrid Workflow**: AI suggests reinforcement based on usage patterns, user confirms

## What Makes It Different

- **No manual curation burden** - insights generated automatically
- **Learning from usage** - reinforcement based on what actually proves helpful
- **Contextual matching** - finds insights from similar situations
- **Natural integration** - works within existing consolidation workflows

## Implementation

Hippo is implemented as an MCP (Model Context Protocol) server providing tools for:
- Recording insights with importance ratings
- Searching insights with semantic context matching  
- Reinforcing insights through user feedback
- Modifying insights as understanding evolves

## Status

Currently in design phase with comprehensive specifications ready for implementation. See the [Design Document](./design-doc.md) for technical details.
