"""MCP server implementation for Hippo."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

import click
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .models import Insight
from .search import InsightSearcher
from .storage import JsonStorage


class HippoServer:
    """MCP server for Hippo insight management."""
    
    def __init__(self, storage_path: Path) -> None:
        """Initialize server with storage path."""
        self.storage = JsonStorage(storage_path)
        self.searcher = InsightSearcher()
        self.server = Server("hippo")
        
        # Register MCP tools
        self._register_tools()
    
    def _register_tools(self) -> None:
        """Register all MCP tools."""
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """List available tools."""
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
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool calls."""
            
            if name == "hippo_record_insight":
                return await self._record_insight(arguments)
            elif name == "hippo_search_insights":
                return await self._search_insights(arguments)
            elif name == "hippo_modify_insight":
                return await self._modify_insight(arguments)
            elif name == "hippo_reinforce_insight":
                return await self._reinforce_insight(arguments)
            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]
    
    async def _record_insight(self, args: Dict[str, Any]) -> List[TextContent]:
        """Record a new insight."""
        try:
            insight = Insight.create(
                content=args["content"],
                situation=args["situation"],
                importance=args["importance"],
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
            storage_data = await self.storage.load()
            results = self.searcher.search(
                storage=storage_data,
                query=query,
                situation_filter=situation_filter,
                relevance_range=relevance_range,
                limit=limit,
            )
            
            # Save storage after recording accesses
            await self.storage.save()
            
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
                "importance_distribution": results.importance_distribution,
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
                insight.apply_reinforcement(1.5)
            elif reinforce == "downvote":
                insight.apply_reinforcement(0.5)
            
            # Save
            await self.storage.update_insight(insight)
            
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
                    insight.apply_reinforcement(1.5)
                    modified.append(str(insight.uuid))
                    await self.storage.update_insight(insight)
                elif insight.uuid in downvotes:
                    insight.apply_reinforcement(0.5)
                    modified.append(str(insight.uuid))
                    await self.storage.update_insight(insight)
            
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
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(read_stream, write_stream, {})


@click.command()
@click.option(
    '--hippo-file',
    type=click.Path(path_type=Path),
    required=True,
    help='Path to the hippo.json storage file'
)
def main(hippo_file: Path) -> None:
    """Run the Hippo MCP server."""
    server = HippoServer(hippo_file)
    asyncio.run(server.run())


if __name__ == "__main__":
    main()