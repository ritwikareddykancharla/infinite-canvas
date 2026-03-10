"""
InfiniteCanvas MCP Server — exposes scene control tools via the
Model Context Protocol so any MCP client (Claude Code, ADK McpToolset, etc.)
can orchestrate the liquid movie.

Transport: stdio (default) or SSE (set MCP_TRANSPORT=sse and MCP_PORT=<port>).

Run locally:
    python -m adk.mcp_server

Add to Claude Code:
    claude mcp add --transport stdio infinite-canvas -- python backend/adk/mcp_server.py

Or add to .mcp.json:
    {
      "mcpServers": {
        "infinite-canvas": {
          "type": "stdio",
          "command": "python",
          "args": ["backend/adk/mcp_server.py"]
        }
      }
    }
"""

import asyncio
import json
import logging
import os
import sys

logger = logging.getLogger(__name__)

# ── Tool implementations (self-contained, no FastAPI dependency) ──────────────

GENRES = ["noir", "romcom", "horror", "scifi"]
BEATS = ["opening", "confrontation", "climax"]

PERSONALITY_READS = {
    "noir": "You gravitate toward shadows. A storyteller of moral ambiguity who finds truth in the darkness.",
    "romcom": "You believe in connection. An optimist who sees beauty in vulnerability and human warmth.",
    "horror": "You embrace tension. A fearless explorer drawn to the edges of comfort and safety.",
    "scifi": "You chase wonder. A visionary who looks beyond the present into infinite possibility.",
}


def _change_scene(genre: str, beat_index: int = 0) -> dict:
    if genre not in GENRES:
        return {"error": f"Invalid genre '{genre}'. Valid: {GENRES}"}
    beat_name = BEATS[min(beat_index, len(BEATS) - 1)]
    return {
        "genre": genre,
        "beat": beat_name,
        "beat_index": BEATS.index(beat_name),
        "video_url": f"/assets/video/{genre}_{beat_name}.mp4",
        "status": "scene_changed",
    }


def _get_available_genres() -> dict:
    return {
        "genres": {
            "noir": "Shadows, moral ambiguity, jazz undertones",
            "romcom": "Golden light, warmth, piano melodies",
            "horror": "Cold dread, ambient drone, darkness",
            "scifi": "Neon cyan, synth music, wonder and awe",
        },
        "beats": {
            "opening": "Establishing the scene and characters (beat_index=0)",
            "confrontation": "Rising tension and conflict (beat_index=1)",
            "climax": "Peak emotional moment (beat_index=2)",
        },
    }


def _generate_director_commentary(narrative_history: list) -> dict:
    if not narrative_history:
        return {"commentary": "No narrative history to analyze yet."}

    genre_counts: dict[str, int] = {}
    for entry in narrative_history:
        g = entry.get("genre", "noir")
        genre_counts[g] = genre_counts.get(g, 0) + 1

    dominant = max(genre_counts, key=genre_counts.get)
    total = len(narrative_history)
    distribution = {g: round(c / total * 100) for g, c in genre_counts.items()}

    return {
        "dominant_genre": dominant,
        "personality_read": PERSONALITY_READS.get(dominant, "A unique directorial voice."),
        "genre_distribution": distribution,
        "total_choices": total,
        "narrative_arc": [e.get("genre") for e in narrative_history],
    }


# ── MCP server definition ─────────────────────────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "name": "change_scene",
        "description": (
            "Change the InfiniteCanvas liquid movie to a specific genre and story beat. "
            "Returns the video URL and scene metadata."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "genre": {
                    "type": "string",
                    "description": "Target genre: noir | romcom | horror | scifi",
                    "enum": GENRES,
                },
                "beat_index": {
                    "type": "integer",
                    "description": "Story beat: 0=opening, 1=confrontation, 2=climax",
                    "minimum": 0,
                    "maximum": 2,
                    "default": 0,
                },
            },
            "required": ["genre"],
        },
    },
    {
        "name": "get_available_genres",
        "description": "List all available genres and story beats with cinematic descriptions.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "generate_director_commentary",
        "description": (
            "Analyze a viewer's narrative history and produce a personality read "
            "and genre distribution breakdown."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "narrative_history": {
                    "type": "array",
                    "description": "Ordered list of scene choices: [{genre, beat}, ...]",
                    "items": {
                        "type": "object",
                        "properties": {
                            "genre": {"type": "string"},
                            "beat": {"type": "string"},
                        },
                    },
                }
            },
            "required": ["narrative_history"],
        },
    },
]


async def _handle_tool_call(name: str, arguments: dict) -> str:
    """Dispatch a tool call and return a JSON string result."""
    if name == "change_scene":
        result = _change_scene(
            genre=arguments.get("genre", "noir"),
            beat_index=arguments.get("beat_index", 0),
        )
    elif name == "get_available_genres":
        result = _get_available_genres()
    elif name == "generate_director_commentary":
        result = _generate_director_commentary(
            narrative_history=arguments.get("narrative_history", [])
        )
    else:
        result = {"error": f"Unknown tool: {name}"}

    return json.dumps(result)


async def _run_stdio_server():
    """Run MCP server over stdio transport."""
    try:
        from mcp.server import Server
        from mcp.server.stdio import stdio_server
        import mcp.types as types
    except ImportError:
        logger.error("mcp package not installed. Run: pip install mcp")
        sys.exit(1)

    server = Server("infinite-canvas")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name=t["name"],
                description=t["description"],
                inputSchema=t["inputSchema"],
            )
            for t in TOOL_DEFINITIONS
        ]

    @server.call_tool()
    async def call_tool(
        name: str, arguments: dict
    ) -> list[types.TextContent]:
        result = await _handle_tool_call(name, arguments)
        return [types.TextContent(type="text", text=result)]

    async with stdio_server() as (read_stream, write_stream):
        logger.info("InfiniteCanvas MCP server running on stdio")
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


async def _run_sse_server(port: int):
    """Run MCP server over SSE transport (HTTP)."""
    try:
        from mcp.server import Server
        from mcp.server.sse import SseServerTransport
        import mcp.types as types
        from starlette.applications import Starlette
        from starlette.routing import Route, Mount
        import uvicorn
    except ImportError as e:
        logger.error(f"Missing dependency for SSE transport: {e}")
        sys.exit(1)

    server = Server("infinite-canvas")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name=t["name"],
                description=t["description"],
                inputSchema=t["inputSchema"],
            )
            for t in TOOL_DEFINITIONS
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
        result = await _handle_tool_call(name, arguments)
        return [types.TextContent(type="text", text=result)]

    sse = SseServerTransport("/messages/")

    async def handle_sse(request):
        async with sse.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await server.run(
                streams[0], streams[1], server.create_initialization_options()
            )

    starlette_app = Starlette(
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ]
    )

    logger.info(f"InfiniteCanvas MCP server running on SSE at port {port}")
    config = uvicorn.Config(starlette_app, host="0.0.0.0", port=port)
    srv = uvicorn.Server(config)
    await srv.serve()


def main():
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    transport = os.environ.get("MCP_TRANSPORT", "stdio").lower()
    port = int(os.environ.get("MCP_PORT", "8001"))

    if transport == "sse":
        asyncio.run(_run_sse_server(port))
    else:
        asyncio.run(_run_stdio_server())


if __name__ == "__main__":
    main()
