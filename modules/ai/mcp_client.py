"""
Lycan MCP Client (HTTP)
Connects to MCP servers via HTTP and provides tools to the AI model.
"""

import os
import json
import logging
import aiohttp
from typing import Optional

# Logger
logger = logging.getLogger("LYCAN")


class MCPClient:
    """Client that connects to MCP servers via HTTP."""
    
    def __init__(self, config_path: str = "/app/mcp_servers.json"):
        self.config_path = config_path
        self.servers = {}
        self.tools = {}
        
    async def load_config(self) -> dict:
        """Load MCP server configuration."""
        if not os.path.exists(self.config_path):
            logger.warning(f"MCP config not found: {self.config_path}")
            return {"mcpServers": {}}
        
        with open(self.config_path, "r") as f:
            config = json.load(f)
        
        # Expand environment variables
        config_str = json.dumps(config)
        for key, value in os.environ.items():
            config_str = config_str.replace(f"${{{key}}}", value)
        
        return json.loads(config_str)
    
    async def discover_tools(self, name: str, url: str, use_sse: bool = False) -> list:
        """Discover available tools from an MCP server via HTTP or SSE."""
        try:
            async with aiohttp.ClientSession() as session:
                if use_sse:
                    # SSE protocol (for Tavily and similar)
                    headers = {
                        "Content-Type": "application/json",
                        "Accept": "text/event-stream"
                    }
                    async with session.post(
                        url,
                        json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
                        headers=headers
                    ) as resp:
                        if resp.status == 200:
                            # Parse SSE response
                            async for line in resp.content:
                                line = line.decode('utf-8').strip()
                                if line.startswith('data:'):
                                    import json as json_module
                                    try:
                                        data = json_module.loads(line[5:].strip())
                                        if "result" in data and "tools" in data["result"]:
                                            return data["result"]["tools"]
                                    except:
                                        continue
                        logger.warning(f"SSE failed for {name}: {resp.status}")
                else:
                    # Standard JSON-RPC
                    async with session.post(
                        url,
                        json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
                        headers={"Content-Type": "application/json"}
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if "result" in data and "tools" in data["result"]:
                                return data["result"]["tools"]
                        # If JSON-RPC fails with 406, try SSE
                        if resp.status == 406 and not use_sse:
                            logger.info(f"  Retrying {name} with SSE protocol...")
                            return await self.discover_tools(name, url, use_sse=True)
                        logger.warning(f"Failed to get tools from {name}: {resp.status}")
        except Exception as e:
            logger.error(f"Error discovering tools from {name}: {e}")
        return []
    
    async def discover_tools_with_sse_detection(self, name: str, url: str) -> tuple:
        """Discover tools and detect if SSE protocol is needed. Returns (tools, uses_sse)."""
        # First try JSON-RPC
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
                    headers={"Content-Type": "application/json"}
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if "result" in data and "tools" in data["result"]:
                            return (data["result"]["tools"], False)  # JSON-RPC works
                    elif resp.status == 406:
                        # Server requires SSE
                        logger.info(f"  {name} requires SSE protocol, retrying...")
                        tools = await self.discover_tools(name, url, use_sse=True)
                        return (tools, True)
        except Exception as e:
            logger.error(f"Error discovering tools from {name}: {e}")
        return ([], False)
    
    async def connect_all(self):
        """Connect to all configured MCP servers."""
        config = await self.load_config()
        servers = config.get("mcpServers", {})
        
        if not servers:
            logger.warning("No MCP servers configured")
            return
        
        for name, server_config in servers.items():
            url = server_config.get("url", "")
            if not url:
                logger.warning(f"No URL for server {name}, skipping")
                continue
            
            logger.info(f"Connecting to MCP server: {name} at {url}")
            self.servers[name] = url
            
            # Discover tools (will auto-detect SSE if needed)
            tools, uses_sse = await self.discover_tools_with_sse_detection(name, url)
            for tool in tools:
                tool_name = tool.get("name", "")
                if tool_name:
                    self.tools[tool_name] = {
                        "server": name,
                        "url": url,
                        "tool": tool,
                        "sse": uses_sse  # Mark if this server uses SSE
                    }
                    # DEBUG: Print schema for ban_user
                    if "ban" in tool_name.lower():
                        print(f"!!! DEBUG ban_user tool schema: {tool}")
            
            logger.info(f"  Loaded {len(tools)} tools from {name}" + (" (SSE)" if uses_sse else ""))
        
        logger.info(f"Total tools available: {len(self.tools)}")
    
    def get_tools_for_llm(self) -> list:
        """Get tool definitions in Groq/OpenAI function format."""
        functions = []
        
        for name, info in self.tools.items():
            tool = info["tool"]
            
            function = {
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool.get("description", f"Tool: {name}"),
                    "parameters": tool.get("inputSchema", {
                        "type": "object",
                        "properties": {},
                        "required": []
                    })
                }
            }
            functions.append(function)
        
        return functions
    
    async def call_tool(self, name: str, arguments: dict) -> str:
        """Call a tool via HTTP (JSON-RPC or SSE) and return the result."""
        if name not in self.tools:
            return f"Tool '{name}' not found"
        
        info = self.tools[name]
        url = info["url"]
        use_sse = info.get("sse", False)  # Check if this server uses SSE
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Content-Type": "application/json"}
                if use_sse:
                    headers["Accept"] = "text/event-stream"
                
                async with session.post(
                    url,
                    json={
                        "jsonrpc": "2.0",
                        "method": "tools/call",
                        "params": {"name": name, "arguments": arguments},
                        "id": 1
                    },
                    headers=headers
                ) as resp:
                    if resp.status == 200:
                        if use_sse:
                            # Parse SSE response
                            import json as json_module
                            async for line in resp.content:
                                line = line.decode('utf-8').strip()
                                if line.startswith('data:'):
                                    try:
                                        data = json_module.loads(line[5:].strip())
                                        if "result" in data:
                                            content = data["result"].get("content", [])
                                            texts = [c.get("text", "") for c in content if "text" in c]
                                            return "\n".join(texts) if texts else str(data["result"])
                                        elif "error" in data:
                                            return f"Error: {data['error']}"
                                    except:
                                        continue
                            return "No response from SSE"
                        else:
                            data = await resp.json()
                            if "result" in data:
                                content = data["result"].get("content", [])
                                texts = [c.get("text", "") for c in content if "text" in c]
                                return "\n".join(texts) if texts else str(data["result"])
                            elif "error" in data:
                                return f"Error: {data['error']}"
                    return f"HTTP error: {resp.status}"
        except Exception as e:
            return f"Error calling tool '{name}': {e}"
    
    def list_available_tools(self) -> list:
        """List names of available tools."""
        return list(self.tools.keys())


# Global client instance
_mcp_client: Optional[MCPClient] = None


async def get_mcp_client() -> MCPClient:
    """Get or create the global MCP client."""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClient()
        await _mcp_client.connect_all()
    return _mcp_client
