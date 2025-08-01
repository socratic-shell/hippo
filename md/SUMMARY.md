# Summary

- [Introduction](./introduction.md)

# User's guide

- [Installation](./installation.md)

# Design and implementation (for contributors)

- [Design Document](./design/design-doc.md)
    - [Example Dialog](./design/example-dialog.md)
    - [Delegate Experiment](./design/experiment-dialog.md)
- [Testing strategy](./design/testing-strategy.md)

# Appendices

- [Research documents]() <!-- Claude: consult these references when discussing if the seem relevant -->
    - [Rust alternatives for sentence-transformers enable 12x faster startup (Claude AI)](research/rust-sentence-transformers-alternatives-claude-ai.md) <!-- Comprehensive analysis of Rust alternatives to Python sentence-transformers for CLI applications. Evaluates FastEmbed, ONNX Runtime, Candle, and Model2Vec for all-MiniLM-L6-v2 deployment. Focuses on startup performance (100-500ms vs 6s Python), production readiness, and practical implementation strategies. FastEmbed emerges as top recommendation for direct Python-to-Rust ports with 12-60x startup improvement. -->
    - [Rust Equivalents for Python sentence-transformers with all-MiniLM-L6-v2 (Gemini)](research/rust-sentence-transformers-alternatives-gemini.md) <!-- Production-ready CLI assessment of Rust ML ecosystem for sentence embeddings. Detailed technical analysis of FastEmbed-rs, candle_embed, ort (ONNX Runtime), and rust-bert. Covers model compatibility, startup optimization, maturity assessment, and implementation best practices. Primary recommendation: FastEmbed-rs for direct all-MiniLM-L6-v2 support with quantized models and ONNX Runtime optimization. -->
    - [Temporal frequency scoring with decay functions in information retrieval systems](research/temporary-frequent-scoring.md) <!-- Comprehensive analysis of mathematical foundations for temporal scoring in IR systems. Covers exponential decay functions, sliding windows, hybrid approaches, and advanced data structures like TELII. Includes practical implementation strategies for different scales, framework integration patterns, and performance optimization techniques. Essential for understanding the mathematical basis of Hippo's temporal scoring system. -->
    - [The Complete User's Guide to Testing MCP Servers with Promptfoo](research/guide-to-testing-mcp-servers-with-promptfoo.md) <!-- Complete guide for testing MCP servers using promptfoo framework. Covers setup, configuration, multi-step workflows, memory testing, tool invocation validation, conversational flows, and debugging strategies. Includes practical examples for e-commerce, SaaS, and financial services. Valuable for understanding how to comprehensively test MCP server implementations like Hippo. -->
    - [File watching for UUID-based storage is feasible with watchdog](research/file-watching-watch.md)
    - [Watchdog Event Handling: Coalescing and Dropping Reference](./research/file-watching-event-drop.md)