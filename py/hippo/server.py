"""MCP server implementation for Hippo."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, cast
from uuid import UUID

import click
import structlog
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .constants import UPVOTE_MULTIPLIER, DOWNVOTE_MULTIPLIER
from .models import Insight, HippoStorage
from .search import InsightSearcher
from .file_storage import FileBasedStorage
from .storage_protocol import StorageProtocol

# 💡: Adding comprehensive logging for MCP server debugging
# MCP servers run in stdio mode which makes debugging tricky - we need
# to log to stderr to avoid interfering with the MCP protocol on stdout
import os

def setup_logging(memory_dir: Path) -> structlog.BoundLogger:
    """
    Set up structured logging configuration based on HIPPO_LOG environment variable.
    
    Args:
        memory_dir: Directory to store log files when HIPPO_LOG is set to a level
        
    Returns:
        Configured structlog logger
    """
    hippo_log = os.environ.get('HIPPO_LOG')
    
    # 💡: Configure structlog processors for consistent structured output
    # Add timestamp, log level, and logger name to all log entries
    processors: List[Any] = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]
    
    if hippo_log:
        # Parse log level from HIPPO_LOG environment variable
        try:
            log_level = getattr(logging, hippo_log.upper())
        except AttributeError:
            # If invalid level, default to INFO and log a warning
            log_level = logging.INFO
            print(f"Warning: Invalid log level '{hippo_log}', using INFO", file=sys.stderr)
        
        # Use memory_dir/hippo.log for log file
        log_file = memory_dir / "hippo.log"
        # Ensure memory directory exists
        memory_dir.mkdir(parents=True, exist_ok=True)
        
        # Configure JSON output for file logging
        processors.append(structlog.processors.JSONRenderer())
        
        # Set up stdlib logging to write to file
        logging.basicConfig(
            level=log_level,
            format='%(message)s',  # Let structlog handle formatting
            filename=str(log_file),  # Ensure it's a string path
            filemode='a',  # Append mode
            force=True  # Force reconfiguration of logging
        )
    else:
        # Default to stderr with ERROR level only to minimize noise
        # Use ConsoleRenderer for human-readable output in error cases
        processors.append(structlog.dev.ConsoleRenderer())
        
        logging.basicConfig(
            level=logging.ERROR,
            format='%(message)s',  # Let structlog handle formatting
            stream=sys.stderr
        )
    
    # Configure structlog (clear any previous configuration)
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=False,  # Don't cache to allow reconfiguration
    )
    
    return cast(structlog.BoundLogger, structlog.get_logger())

# Global logger instance - initialized in main()
_logger: Optional[structlog.BoundLogger] = None


class HippoServer:
    """MCP server for Hippo insight management."""
    
    logger: structlog.BoundLogger  # Type annotation for logger attribute
    
    def __init__(self, storage_path: Optional[Path] = None, *, storage: Optional[StorageProtocol] = None, logger: Optional[structlog.BoundLogger] = None) -> None:
        """Initialize server with either storage path or storage instance."""
        # 💡: Accept logger as parameter to avoid global state dependency
        # Fall back to global logger if none provided for backward compatibility
        if logger is not None:
            self.logger = logger
        elif _logger is not None:
            self.logger = _logger
        else:
            raise ValueError("Logger must be provided either as parameter or global _logger must be initialized")
            
        self.logger.info("server.init.start", status="initializing")
        
        if storage is not None:
            self.logger.debug("server.init.storage", storage_type="provided_instance")
            self.storage: StorageProtocol = storage
        elif storage_path is not None:
            self.logger.info("server.init.storage", storage_type="file_based", path=str(storage_path))
            self.storage = FileBasedStorage(storage_path)
        else:
            self.logger.error("server.init.error", error="no_storage_configured")
            raise ValueError("Must provide either storage_path or storage")
            
        self.logger.debug("server.init.searcher", status="initializing")
        self.searcher = InsightSearcher()
        
        self.logger.debug("server.init.mcp", status="creating_server")
        self.server: Server[Any] = Server("hippo")
        
        # 💡: Track tool call count for periodic metrics logging
        # Log metrics every 10 tool calls to balance observability with log volume
        self.tool_call_count = 0
        self.metrics_interval = 10
        
        self.logger.info("server.init.tools", status="registering")
        # Register MCP tools
        self._register_tools()
        self.logger.info("server.init.complete", status="ready")
    
    def __enter__(self) -> 'HippoServer':
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit - cleanup storage resources."""
        if hasattr(self.storage, '__exit__'):
            self.storage.__exit__(exc_type, exc_val, exc_tb)
        return None  # Don't suppress exceptions
    
    def _register_tools(self) -> None:
        """Register all MCP tools."""
        self.logger.debug("server.tools.register", status="starting")
        
        @self.server.list_tools()  # type: ignore[misc,no-untyped-call]
        async def list_tools() -> List[Tool]:
            """List available tools."""
            self.logger.debug("server.tools.list", event="list_tools_called")
            return [
                Tool(
                    name="hippo_record_insight",
                    description="Record a new insight during consolidation moments",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "The insight content - should be atomic and actionable"
                            },
                            "situation": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": (
                                    "Array of independent situational aspects describing when/where "
                                    "this insight occurred. Include: 1) General activity (e.g. "
                                    "'debugging authentication flow', 'design discussion about hippo'), "
                                    "2) Specific problem/goal (e.g. 'users getting logged out randomly', "
                                    "'defining MCP tool interface'), 3) Additional relevant details "
                                    "(e.g. 'race condition suspected', 'comparing dialogue vs instruction "
                                    "formats'). Each element should be independently meaningful for "
                                    "search matching."
                                )
                            },
                            "importance": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1,
                                "description": (
                                    "AI-assessed importance rating: 0.8+ breakthrough insights, "
                                    "0.6-0.7 useful decisions, 0.4-0.5 incremental observations, "
                                    "0.1-0.3 routine details"
                                )
                            }
                        },
                        "required": ["content", "situation", "importance"]
                    }
                ),
                Tool(
                    name="hippo_search_insights",
                    description="Search for relevant insights based on content and situation",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query for insight content"
                            },
                            "situation_filter": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": (
                                    "Filter results by matching any situation elements using partial "
                                    "matching. Examples: ['debugging authentication'] matches insights "
                                    "with 'debugging authentication flow', ['users getting logged out'] "
                                    "matches specific problem contexts. Can provide multiple filters - "
                                    "results match if ANY situation element partially matches ANY filter."
                                )
                            },
                            "limit": {
                                "type": "object",
                                "properties": {
                                    "offset": {"type": "integer", "default": 0},
                                    "count": {"type": "integer", "default": 10}
                                },
                                "description": (
                                    "Result pagination. Default: {offset: 0, count: 10} returns "
                                    "first 10 results. Examples: {offset: 10, count: 5} for next 5 results"
                                ),
                                "default": {"offset": 0, "count": 10}
                            },
                            "relevance_range": {
                                "type": "object",
                                "properties": {
                                    "min": {"type": "number", "default": 0.1},
                                    "max": {"type": "number"}
                                },
                                "description": (
                                    "Relevance range filter. Examples: {min: 0.6, max: 1.0} for highly "
                                    "relevant insights, {min: 1.0} for top-tier results, {max: 0.4} "
                                    "for lower relevance insights"
                                )
                            }
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="hippo_modify_insight",
                    description="Modify an existing insight's content, situation, or importance",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "uuid": {
                                "type": "string",
                                "description": "UUID of the insight to modify"
                            },
                            "content": {
                                "type": "string",
                                "description": "New insight content (optional - only provide if changing)"
                            },
                            "situation": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "New situational aspects array (optional - only provide if changing)"
                            },
                            "importance": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1,
                                "description": "New importance rating (optional - only provide if changing)"
                            },
                            "reinforce": {
                                "type": "string",
                                "enum": ["upvote", "downvote", "none"],
                                "description": (
                                    "Reinforcement to apply with modification. Default: 'upvote' "
                                    "(since modification usually signals value)"
                                ),
                                "default": "upvote"
                            }
                        },
                        "required": ["uuid"]
                    }
                ),
                Tool(
                    name="hippo_reinforce_insight",
                    description="Apply reinforcement feedback to multiple insights",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "upvotes": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Array of UUIDs to upvote (1.5x importance multiplier)",
                                "default": []
                            },
                            "downvotes": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Array of UUIDs to downvote (0.5x importance multiplier)",
                                "default": []
                            }
                        }
                    }
                ),
            ]
        
        @self.server.call_tool()  # type: ignore[misc,no-untyped-call]
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool calls."""
            import time
            start_time = time.time()
            
            # 💡: Log tool requests at INFO level with sanitized arguments for better metrics tracking
            # Truncate large arguments to keep logs readable while preserving key information
            def sanitize_value(val: Any) -> Any:
                if isinstance(val, str) and len(val) > 100:
                    return f"{val[:100]}..."
                elif isinstance(val, list):
                    if len(val) <= 5:
                        # Small lists: sanitize each item individually
                        return [sanitize_value(item) for item in val]
                    else:
                        # Large lists: show first 5 items with individual sanitization, then count
                        sanitized_items = [sanitize_value(item) for item in val[:5]]
                        return sanitized_items + [f"... +{len(val) - 5} more"]
                else:
                    return val
            
            sanitized_args = {key: sanitize_value(value) for key, value in arguments.items()}
            
            self.logger.info("tool.request", tool=name, args=sanitized_args)
            
            try:
                result = None
                if name == "hippo_record_insight":
                    self.logger.debug("Calling _record_insight")
                    result = await self._record_insight(arguments)
                elif name == "hippo_search_insights":
                    self.logger.debug("Calling _search_insights")
                    result = await self._search_insights(arguments)
                elif name == "hippo_modify_insight":
                    self.logger.debug("Calling _modify_insight")
                    result = await self._modify_insight(arguments)
                elif name == "hippo_reinforce_insight":
                    self.logger.debug("Calling _reinforce_insight")
                    result = await self._reinforce_insight(arguments)
                else:
                    self.logger.warning("tool.unknown", tool=name)
                    result = [TextContent(type="text", text=f"Unknown tool: {name}")]
                
                # 💡: Log successful tool responses with timing for performance analysis
                duration_ms = (time.time() - start_time) * 1000
                result_summary = "success"
                if result and len(result) > 0:
                    # Extract key info from response for metrics
                    text = result[0].text if hasattr(result[0], 'text') else str(result[0])
                    if "Error" in text:
                        result_summary = f"error: {text[:50]}..."
                    elif "UUID:" in text:
                        result_summary = "created_insight"
                    elif "insights" in text:
                        result_summary = "search_results"
                    elif "Modified" in text:
                        result_summary = "modified_insight"
                    elif "reinforcement" in text:
                        result_summary = "applied_reinforcement"
                
                self.logger.info("tool.response", tool=name, result=result_summary, duration_ms=round(duration_ms, 1))
                
                # 💡: Periodic metrics logging to track system health and usage patterns
                # Only log metrics on successful tool calls to avoid noise from errors
                self.tool_call_count += 1
                if self.tool_call_count % self.metrics_interval == 0:
                    await self._log_system_metrics()
                
                return result
                    
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                self.logger.error("tool.error", tool=name, error=str(e), duration_ms=round(duration_ms, 1), exc_info=True)
                return [TextContent(type="text", text=f"Error in {name}: {str(e)}")]
    
    async def _log_system_metrics(self) -> None:
        """Log system metrics for monitoring and analysis."""
        try:
            all_insights = await self.storage.get_all_insights()
            current_active_day = await self.storage.get_current_active_day()
            
            # 💡: Calculate aggregate metrics from existing usage tracking infrastructure
            # Leverage the sophisticated frequency/recency calculations already built into insights
            total_insights = len(all_insights)
            
            # Calculate importance distribution
            importance_scores = [insight.compute_current_importance() for insight in all_insights]
            high_importance = len([s for s in importance_scores if s >= 0.8])
            medium_importance = len([s for s in importance_scores if 0.4 <= s < 0.8])
            low_importance = len([s for s in importance_scores if s < 0.4])
            
            # Calculate access patterns over recent window
            recent_access_counts = []
            total_accesses = 0
            for insight in all_insights:
                frequency = insight.calculate_frequency(current_active_day)
                recent_access_counts.append(frequency)
                # Sum all access counts from daily tracking
                total_accesses += sum(count for _, count in insight.daily_access_counts)
            
            most_accessed = max(recent_access_counts) if recent_access_counts else 0
            avg_frequency = sum(recent_access_counts) / len(recent_access_counts) if recent_access_counts else 0
            
            # Calculate recency distribution
            recency_scores = [insight.calculate_recency_score(current_active_day) for insight in all_insights]
            recently_accessed = len([s for s in recency_scores if s > 0.5])
            
            self.logger.info(
                "system.metrics",
                total_insights=total_insights,
                active_day=current_active_day,
                total_accesses=total_accesses,
                importance_distribution={
                    "high": high_importance,
                    "medium": medium_importance,
                    "low": low_importance
                },
                access_frequency={
                    "average": round(avg_frequency, 2),
                    "max": round(most_accessed, 2)
                },
                recently_accessed=recently_accessed
            )
            
        except Exception as e:
            self.logger.error("system.metrics.error", error=str(e), exc_info=True)
    
    async def _record_insight(self, args: Dict[str, Any]) -> List[TextContent]:
        """Record a new insight."""
        try:
            current_active_day = await self.storage.get_current_active_day()
            
            insight = Insight.create(
                content=args["content"],
                situation=args["situation"],
                importance=args["importance"],
                current_active_day=current_active_day,
            )
            await self.storage.add_insight(insight)
            
            return [TextContent(
                type="text",
                text=f"Recorded insight with UUID: {insight.uuid}"
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error recording insight: {str(e)}"
            )]
    
    async def _search_insights(self, args: Dict[str, Any]) -> List[TextContent]:
        """Search for insights."""
        try:
            # Parse arguments
            query = args.get("query", "")
            situation_filter = args.get("situation_filter")
            limit_dict = args.get("limit", {"offset": 0, "count": 10})
            limit = (limit_dict["offset"], limit_dict["count"])
            
            relevance_range = None
            if "relevance_range" in args:
                rr = args["relevance_range"]
                relevance_range = (rr.get("min", 0.1), rr.get("max"))
            
            # Perform search
            all_insights = await self.storage.get_all_insights()
            current_active_day = await self.storage.get_current_active_day()
            
            results = self.searcher.search(
                insights=all_insights,
                current_active_day=current_active_day,
                query=query,
                situation_filter=situation_filter,
                relevance_range=relevance_range,
                limit=limit,
            )
            
            # Record accesses for insights that were returned
            for search_result in results.insights:
                await self.storage.record_insight_access(search_result.insight.uuid)
            
            # Format results
            output = {
                "insights": [
                    {
                        "uuid": str(r.insight.uuid),
                        "content": r.insight.content,
                        "situation": r.insight.situation,
                        "base_importance": r.insight.importance,
                        "current_importance": r.importance,
                        "relevance": r.relevance,
                        "created_at": r.insight.created_at.isoformat(),
                        "days_since_created": r.insight.days_since_created(),
                        "days_since_importance_modified": r.insight.days_since_importance_modified(),
                    }
                    for r in results.insights
                ],
                "total_matching": results.total_matching,
                "returned_count": results.returned_count,
                "relevance_distribution": results.relevance_distribution,
            }
            
            import json
            return [TextContent(
                type="text",
                text=json.dumps(output, indent=2)
            )]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error searching insights: {str(e)}"
            )]
    
    async def _modify_insight(self, args: Dict[str, Any]) -> List[TextContent]:
        """Modify an existing insight."""
        try:
            uuid = UUID(args["uuid"])
            insights = await self.storage.get_all_insights()
            
            # Find the insight
            insight = None
            for i in insights:
                if i.uuid == uuid:
                    insight = i
                    break
            
            if insight is None:
                return [TextContent(
                    type="text",
                    text=f"Insight not found: {uuid}"
                )]
            
            # Update fields
            insight.update_content(
                content=args.get("content"),
                situation=args.get("situation"),
                importance=args.get("importance"),
            )
            
            # Apply reinforcement
            reinforce = args.get("reinforce", "upvote")
            if reinforce == "upvote":
                insight.apply_reinforcement(UPVOTE_MULTIPLIER)
            elif reinforce == "downvote":
                insight.apply_reinforcement(DOWNVOTE_MULTIPLIER)
            
            # Save the updated insight
            await self.storage.store_insight(insight)
            
            return [TextContent(
                type="text",
                text=f"Modified insight: {uuid}"
            )]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error modifying insight: {str(e)}"
            )]
    
    async def _reinforce_insight(self, args: Dict[str, Any]) -> List[TextContent]:
        """Apply reinforcement to multiple insights."""
        try:
            upvotes = [UUID(u) for u in args.get("upvotes", [])]
            downvotes = [UUID(d) for d in args.get("downvotes", [])]
            
            insights = await self.storage.get_all_insights()
            modified = []
            
            for insight in insights:
                if insight.uuid in upvotes:
                    insight.apply_reinforcement(UPVOTE_MULTIPLIER)
                    modified.append(str(insight.uuid))
                    await self.storage.store_insight(insight)
                elif insight.uuid in downvotes:
                    insight.apply_reinforcement(DOWNVOTE_MULTIPLIER)
                    modified.append(str(insight.uuid))
                    await self.storage.store_insight(insight)
            
            return [TextContent(
                type="text",
                text=f"Applied reinforcement to {len(modified)} insights"
            )]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error applying reinforcement: {str(e)}"
            )]
    
    async def run(self) -> None:
        """Run the MCP server."""
        self.logger.info("server.run.start", status="starting")
        try:
            # 💡: Using create_initialization_options() like the official examples
            # This sets up proper server capabilities and initialization parameters
            options = self.server.create_initialization_options()
            async with stdio_server() as (read_stream, write_stream):
                self.logger.info("server.run.connected", status="connected", mode="stdio")
                await self.server.run(read_stream, write_stream, options, raise_exceptions=True)
        except Exception as e:
            self.logger.error("server.run.error", error=str(e), exc_info=True)
            raise


@click.command()
@click.option(
    '--memory-dir',
    type=click.Path(path_type=Path),
    required=True,
    help='Path to the hippo storage directory'
)
def main(memory_dir: Path) -> None:
    """Run the Hippo MCP server."""
    global _logger
    
    # 💡: Initialize logger first thing in main() to avoid environment variable dependency
    # This ensures proper initialization order and eliminates the need for HIPPO_MEMORY_DIR env var
    _logger = setup_logging(memory_dir)
    
    hippo_log = os.environ.get('HIPPO_LOG')
    if hippo_log:
        log_destination = f"{memory_dir}/hippo.log"
        log_format = "JSON"
    else:
        log_destination = "stderr"
        log_format = "console"
    
    _logger.info(
        "hippo.main.start",
        memory_dir=str(memory_dir),
        log_level=hippo_log or "ERROR",
        log_destination=log_destination,
        log_format=log_format
    )
    
    try:
        # Ensure the parent directory exists
        memory_dir.parent.mkdir(parents=True, exist_ok=True)
        _logger.debug("hippo.main.dir_check", parent_dir=str(memory_dir.parent), status="exists")
        
        server = HippoServer(memory_dir, logger=_logger)
        _logger.info("hippo.main.server_created", status="ready")
        asyncio.run(server.run())
    except Exception as e:
        _logger.error("hippo.main.error", error=str(e), exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()