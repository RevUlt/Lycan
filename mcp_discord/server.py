"""
Lycan Discord MCP Server
HTTP JSON-RPC server that provides Discord tools.
"""

import os
import json
import asyncio
import discord
from aiohttp import web
from typing import Any

# Import tools
from tools.channels import register_channel_tools
from tools.messages import register_message_tools
from tools.roles import register_role_tools
from tools.users import register_user_tools
from tools.server_info import register_server_tools
from tools.web_search import register_web_tools
from tools.invites import register_invite_tools
from tools.threads import register_thread_tools
from tools.voice import register_voice_tools

# Configuration
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
DEFAULT_GUILD_ID = os.getenv("DISCORD_GUILD_ID", "")

# Initialize Discord client
intents = discord.Intents.all()
discord_client = discord.Client(intents=intents)

# Global tool registry
_tools = {}
_discord_ready = asyncio.Event()


@discord_client.event
async def on_ready():
    """Discord client ready."""
    print(f"Discord MCP connected as {discord_client.user}")
    print(f"Default guild: {DEFAULT_GUILD_ID}")
    _discord_ready.set()


async def get_guild(guild_id: str = None):
    """Get a guild by ID or use default."""
    await _discord_ready.wait()
    
    gid = int(guild_id) if guild_id else int(DEFAULT_GUILD_ID)
    guild = discord_client.get_guild(gid)
    if not guild:
        raise ValueError(f"Guild {gid} not found")
    return guild


class MockMCP:
    """Mock MCP object for tool registration."""
    
    def tool(self):
        """Decorator to register a tool."""
        def decorator(func):
            # Extract function info
            name = func.__name__
            doc = func.__doc__ or ""
            
            # Parse docstring for args
            params = {
                "type": "object",
                "properties": {},
                "required": []
            }
            
            # Get function annotations
            annotations = getattr(func, "__annotations__", {})
            for param_name, param_type in annotations.items():
                if param_name == "return":
                    continue
                type_str = "string"
                if param_type == int:
                    type_str = "integer"
                elif param_type == bool:
                    type_str = "boolean"
                
                params["properties"][param_name] = {
                    "type": type_str,
                    "description": f"Parameter: {param_name}"
                }
            
            # Register tool
            _tools[name] = {
                "name": name,
                "description": doc.strip().split("\n")[0] if doc else name,
                "inputSchema": params,
                "function": func
            }
            
            return func
        return decorator


# Create mock MCP and register tools
mock_mcp = MockMCP()
register_channel_tools(mock_mcp, get_guild)
register_message_tools(mock_mcp, get_guild)
register_role_tools(mock_mcp, get_guild)
register_user_tools(mock_mcp, get_guild)
register_server_tools(mock_mcp, get_guild)
register_invite_tools(mock_mcp, get_guild)
register_thread_tools(mock_mcp, get_guild)
register_voice_tools(mock_mcp, get_guild)
register_web_tools(mock_mcp, None)  # Web tools don't need guild


async def handle_jsonrpc(request):
    """Handle JSON-RPC requests."""
    try:
        data = await request.json()
    except:
        return web.json_response({"error": "Invalid JSON"}, status=400)
    
    method = data.get("method", "")
    params = data.get("params", {})
    req_id = data.get("id", 1)
    
    if method == "tools/list":
        # Return list of available tools
        tools_list = [
            {
                "name": t["name"],
                "description": t["description"],
                "inputSchema": t["inputSchema"]
            }
            for t in _tools.values()
        ]
        return web.json_response({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": tools_list}
        })
    
    elif method == "tools/call":
        # Call a specific tool
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        
        if tool_name not in _tools:
            return web.json_response({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Tool not found: {tool_name}"}
            })
        
        try:
            # Wait for Discord to be ready
            await _discord_ready.wait()
            
            # Call the tool function
            func = _tools[tool_name]["function"]
            result = await func(**tool_args)
            
            return web.json_response({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": str(result)}]}
            })
        except Exception as e:
            return web.json_response({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32000, "message": str(e)}
            })
    
    else:
        return web.json_response({
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Unknown method: {method}"}
        })


async def health_check(request):
    """Health check endpoint."""
    return web.json_response({"status": "ok", "tools": len(_tools)})


async def start_discord():
    """Start Discord client."""
    await discord_client.start(DISCORD_TOKEN)


async def start_http():
    """Start HTTP server."""
    app = web.Application()
    app.router.add_post("/mcp", handle_jsonrpc)
    app.router.add_get("/health", health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()
    print(f"MCP HTTP server running on http://0.0.0.0:8080")
    print(f"Registered {len(_tools)} tools")
    
    # Keep running
    while True:
        await asyncio.sleep(3600)


async def main():
    """Run both Discord and HTTP server."""
    # Start both concurrently
    await asyncio.gather(
        start_discord(),
        start_http()
    )


if __name__ == "__main__":
    asyncio.run(main())
