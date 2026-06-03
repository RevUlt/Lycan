"""
Web Search tools using Tavily API.
Provides internet search capabilities for Lycan.
"""

import os
import aiohttp
import logging

logger = logging.getLogger("MCP-DISCORD")

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")


def register_web_tools(mcp_server, bot):
    """Register web search tools."""
    
    @mcp_server.tool()
    async def web_search(query: str, max_results: int = 5) -> str:
        """
        Search the internet for current information.
        Use this for real-time data, news, or anything not in training data.
        
        Args:
            query: The search query (be specific for better results)
            max_results: Maximum number of results to return (1-10)
        
        Returns:
            Search results with titles, URLs, and content snippets
        """
        if not TAVILY_API_KEY:
            return "Error: TAVILY_API_KEY not configured"
        
        max_results = max(1, min(10, max_results))
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": TAVILY_API_KEY,
                        "query": query,
                        "max_results": max_results,
                        "include_answer": True
                    }
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        # Format results
                        output = []
                        
                        # Include AI-generated answer if available
                        if data.get("answer"):
                            output.append(f"**Resumen:** {data['answer']}\n")
                        
                        # Include search results
                        results = data.get("results", [])
                        for i, r in enumerate(results, 1):
                            title = r.get("title", "Sin título")
                            url = r.get("url", "")
                            content = r.get("content", "")[:300]
                            output.append(f"**{i}. {title}**\n{url}\n{content}\n")
                        
                        return "\n".join(output) if output else "No se encontraron resultados"
                    else:
                        return f"Error en búsqueda: HTTP {resp.status}"
        except Exception as e:
            logger.error(f"Web search error: {e}")
            return f"Error: {e}"
    
    @mcp_server.tool()
    async def web_extract(url: str) -> str:
        """
        Extract content from a specific URL.
        Use this to get detailed information from a webpage.
        
        Args:
            url: The URL to extract content from
        
        Returns:
            Extracted text content from the webpage
        """
        if not TAVILY_API_KEY:
            return "Error: TAVILY_API_KEY not configured"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.tavily.com/extract",
                    json={
                        "api_key": TAVILY_API_KEY,
                        "urls": [url]
                    }
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        logger.info(f"web_extract response keys: {list(data.keys())}")
                        results = data.get("results", [])
                        logger.info(f"web_extract results count: {len(results)}")
                        if results:
                            content = results[0].get("raw_content", "")
                            if content:
                                return content[:2000]
                            return "No content in raw_content field"
                        # Check if there's an error
                        if "error" in data:
                            return f"Tavily error: {data['error']}"
                        return f"No se pudo extraer contenido. Response: {str(data)[:200]}"
                    else:
                        body = await resp.text()
                        return f"Error: HTTP {resp.status} - {body[:100]}"
        except Exception as e:
            logger.error(f"Web extract error: {e}")
            return f"Error: {e}"
    
    logger.info("Web search tools registered (Tavily)")
