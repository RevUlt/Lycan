"""
Lycan Bot - AI Module
Cognitive agent with MCP tools and OpenRouter LLM.
"""

import os
import json
import logging
import asyncio
import re
import discord
from discord.ext import commands
from typing import Optional
import openai

from .memory import MemoryManager
from .retrieval import RetrievalEngine
from .personality import LYCAN_SYSTEM_PROMPT
from .mcp_client import MCPClient

# Logger
logger = logging.getLogger("LYCAN")

# Configuration
OWNER_ID = int(os.getenv("LYCAN_OWNER_ID", "0"))
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# Available models (OpenRouter only)
MODELS = {
    # FREE with function calling
    "xiaomi/mimo-v2-flash:free": "xiaomi/mimo-v2-flash:free",
    "mistralai/devstral-2512:free": "mistralai/devstral-2512:free",
    "openai/gpt-oss-120b:free": "openai/gpt-oss-120b:free",
    # Paid
    "anthropic/claude-3.5-sonnet": "anthropic/claude-3.5-sonnet",
    "anthropic/claude-3-haiku": "anthropic/claude-3-haiku",
    "openai/gpt-4o": "openai/gpt-4o",
    "openai/gpt-4o-mini": "openai/gpt-4o-mini",
    "google/gemini-flash-1.5": "google/gemini-flash-1.5",
    "deepseek/deepseek-chat": "deepseek/deepseek-chat",
}

# Command prefix
PREFIX = "!"

# Timeout for LLM calls (seconds) - includes external tool execution
LLM_TIMEOUT = 60


class AICog(commands.Cog):
    """Lycan's cognitive core - natural conversation with MCP tools."""
    
    def __init__(self, bot):
        self.bot = bot
        
        # Initialize OpenRouter
        self.client = openai.OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY
        ) if OPENROUTER_API_KEY else None
        
        # Current model (devstral has better function calling support)
        self.current_model = "mistralai/devstral-2512:free"
        self.personality = LYCAN_SYSTEM_PROMPT
        
        # Initialize subsystems
        self.memory = MemoryManager(bot)
        self.retrieval = RetrievalEngine()
        self.mcp = MCPClient()
        
        # Active conversations
        self.sessions = {}
        
        # MCP state
        self._mcp_connected = False
        self._mcp_tools = []
        self._tokens_used = 0
        
        # Reasoning mode (off-camera thinking)
        self._reasoning_enabled = False
        
        # Rate limiting (cooldown between responses)
        self._last_response_time = {}  # guild_id -> timestamp
        self._cooldown_seconds = 5  # Soft cooldown
        
        # Confirmations for critical actions
        self._pending_confirmations = {}  # guild_id -> {"action": ..., "args": ..., "expires": ...}
        self._critical_actions = ["ban_user", "kick_user", "delete_channel", "delete_role"]
    
    async def cog_load(self):
        """Called when cog is loaded - load saved settings."""
        await self._load_model_from_db()
    
    async def _ensure_mcp_connected(self):
        """Ensure MCP client is connected."""
        if not self._mcp_connected:
            try:
                logger.info("Connecting to MCP servers...")
                await self.mcp.connect_all()
                self._mcp_tools = self.mcp.get_tools_for_llm()
                self._mcp_connected = True
                logger.info(f"MCP connected. {len(self._mcp_tools)} tools available")
            except Exception as e:
                logger.error(f"MCP connection failed: {e}")
                self._mcp_connected = False
    
    async def reload_mcp(self):
        """Reload MCP connections."""
        self._mcp_connected = False
        self.mcp = MCPClient()
        await self._ensure_mcp_connected()
        return len(self._mcp_tools)
    
    async def _check_model_availability(self, model_id: str) -> bool:
        """Check if a model is available via OpenRouter API."""
        if not OPENROUTER_API_KEY:
            return False
            
        # First check hardcoded list (fast path)
        if model_id in MODELS:
            return True
            
        # Check against OpenRouter API
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://openrouter.ai/api/v1/models",
                    headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"}
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        models = data.get("data", [])
                        # Exact match check
                        for m in models:
                            if m.get("id") == model_id:
                                return True
        except Exception as e:
            logger.error(f"Failed to fetch models from OpenRouter: {e}")
            
        return False

    async def set_model(self, model_name: str) -> bool:
        """Change the current model and persist to database."""
        logger.info(f"DEBUG: set_model called with '{model_name}' (type: {type(model_name)})")
        model_name = model_name.strip()
        
        # 1. Direct match in local list
        if model_name in MODELS:
            logger.info("DEBUG: Found in local MODELS")
            self.current_model = model_name
        
        # 2. Dynamic check via OpenRouter API
        elif await self._check_model_availability(model_name):
            logger.info(f"Model {model_name} valid via OpenRouter API")
            self.current_model = model_name
            # Add to local cache for this session
            MODELS[model_name] = model_name 
        
        # 3. Fallback: Trust the user if format looks valid (provider/model)
        elif "/" in model_name:
            logger.warning(f"Model {model_name} not confirmed by API but has valid format. TRUSTING USER.")
            self.current_model = model_name
            MODELS[model_name] = model_name
            
        else:
            logger.warning(f"DEBUG: Model rejected. '/' in name? {'/' in model_name}")
            return False

        # Persist to database
        try:
            await self.bot.db.execute(
                """INSERT INTO ai_settings (key, value) VALUES ('current_model', $1)
                   ON CONFLICT (key) DO UPDATE SET value = $1""",
                self.current_model
            )
        except Exception as e:
            logger.warning(f"Failed to persist model to DB: {e}")
        return True
    
    async def _load_model_from_db(self):
        """Load saved model from database on startup."""
        try:
            # Create table if not exists
            await self.bot.db.execute("""
                CREATE TABLE IF NOT EXISTS ai_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            # Load model
            row = await self.bot.db.fetchrow(
                "SELECT value FROM ai_settings WHERE key = 'current_model'"
            )
            if row and row['value'] in MODELS:
                self.current_model = row['value']
                logger.info(f"Loaded saved model: {self.current_model}")
        except Exception as e:
            logger.warning(f"Failed to load model from DB: {e}")
    
    async def get_status(self) -> dict:
        """Get current status."""
        credits = await self._get_openrouter_credits()
        return {
            "model": self.current_model,
            "mcp_connected": self._mcp_connected,
            "tools_count": len(self._mcp_tools),
            "sessions": len(self.sessions),
            "tokens_used": self._tokens_used,
            "credits": credits
        }
    
    async def _get_openrouter_credits(self):
        """Get remaining credits from OpenRouter."""
        if not OPENROUTER_API_KEY:
            return None
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://openrouter.ai/api/v1/auth/key",
                    headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"}
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("data", {}).get("limit_remaining")
        except:
            pass
        return None
    
    def _parse_xml_tool_calls(self, content: str) -> list:
        """Parse XML-style tool calls from models that don't support native function calling.
        ROBUST VERSION: Handles spaces, attributes, and nested tags.
        """
        if not content:
            return []
            
        # 1. Basic Cleanup
        # Remove code block markers to avoid interference
        clean_content = content.replace("```xml", "").replace("```", "")
        # Unescape common HTML entities
        clean_content = clean_content.replace("&quot;", '"').replace("&lt;", "<").replace("&gt;", ">")
        
        if "<tool_call>" not in clean_content and "< tool_call >" not in clean_content:
            return []
        
        tool_calls = []
        
        # 2. Extract Blocks (Permissive Regex)
        # Matches <tool_call> ... </tool_call> with spaces allowed
        block_pattern = r'<\s*tool_call\s*>(.*?)<\s*/\s*tool_call\s*>'
        matches = re.findall(block_pattern, clean_content, re.DOTALL | re.IGNORECASE)
        
        logger.info(f"XML Parser: Found {len(matches)} tool_call blocks")
        
        if not matches and ("<tool_call>" in clean_content or "<function=" in clean_content):
            logger.warning(f"XML Parser FAILED to match blocks but found tags. Content sample: {clean_content[:200]}")
        
        for block in matches:
            try:
                func_name = None
                
                # 3. Extract Function Name - Try multiple strategies
                
                # Strategy A: <function>NAME</function> or <name>NAME</name>
                p_tag = r'<\s*(function|function-name|name)\s*>([^<]+)<\s*/\s*(?:\1)\s*>'
                m_tag = re.search(p_tag, block, re.DOTALL | re.IGNORECASE)
                
                # Strategy B: <function=NAME> (Self-closing style or start tag)
                p_attr = r'<\s*function\s*=\s*([^>]+)\s*>'
                m_attr = re.search(p_attr, block, re.DOTALL | re.IGNORECASE)
                
                if m_tag:
                    func_name = m_tag.group(2).strip()
                elif m_attr:
                    func_name = m_attr.group(1).strip()
                
                if not func_name:
                    logger.warning(f"XML Parser: Could not find function name in block: {block[:50]}...")
                    continue
                
                logger.info(f"XML Parser: Found function '{func_name}'")
                
                # 4. Extract Parameters
                params = {}
                
                # Strategy: Split by <parameter=...> or <parameter>...
                # We simply look for ALL regex matches of parameter patterns
                
                # Pattern 1: <parameter=NAME>VALUE</parameter> (or just closing >)
                # We iterate to find them
                p_param_attr = r'<\s*parameter\s*=\s*([^>]+)\s*>(.*?)<\s*/\s*parameter\s*>'
                attr_matches = re.findall(p_param_attr, block, re.DOTALL | re.IGNORECASE)
                
                for p_name, p_val in attr_matches:
                    params[p_name.strip()] = p_val.strip()

                # Pattern 2: <parameter name="NAME">VALUE</parameter> (rare but possible)
                p_param_xml = r'<\s*parameter\s+name=["\']([^"\']+)["\']\s*>(.*?)<\s*/\s*parameter\s*>'
                xml_matches = re.findall(p_param_xml, block, re.DOTALL | re.IGNORECASE)
                
                for p_name, p_val in xml_matches:
                    params[p_name.strip()] = p_val.strip()

                # Pattern 3: <parameter-NAME>VALUE</parameter-NAME> OR <NAME>VALUE</NAME> (if not function)
                # This is harder to distinguish from function name, so we rely on explicit 'parameter' tags mostly.
                # But let's check for "User Style" from logs: <parameter=key> val (no closing?)
                # Actually user logs showed: <parameter=key>val</parameter> - Pattern 1 covers it.
                
                # Special: send_embed_with_fields 'fields' handling
                if 'fields' in params:
                    val = params['fields']
                    if val.strip().startswith('[') or val.strip().startswith('{'):
                         try:
                             params['fields'] = json.loads(val)
                         except:
                             pass
                
                tool_calls.append({
                    "name": func_name,
                    "arguments": params
                })
                
            except Exception as e:
                logger.warning(f"Failed to parse XML tool call block: {e}")
                continue
        
        return tool_calls
    
    def clear_session(self, guild_id: int):
        """Clear conversation history for a guild."""
        if guild_id in self.sessions:
            del self.sessions[guild_id]
    
    def _is_owner(self, user_id: int) -> bool:
        """Security Gate - only owner can interact."""
        return user_id == OWNER_ID
    
    def _is_mention_or_reply(self, message: discord.Message) -> bool:
        """Check if message is directed at bot."""
        if self.bot.user.mentioned_in(message):
            return True
        if message.reference and message.reference.resolved:
            if message.reference.resolved.author.id == self.bot.user.id:
                return True
        return False
    
    def _translate_error(self, tool_name: str, error: str) -> str:
        """Translate technical errors to user-friendly messages."""
        error_lower = error.lower()
        
        # Permission errors
        if "403" in error or "forbidden" in error_lower or "missing permissions" in error_lower:
            return f"No tengo permisos suficientes para ejecutar `{tool_name}`. ¿Podrías revisar mis roles?"
        
        # Not found errors
        if "404" in error or "not found" in error_lower:
            return f"No encontré lo que buscaba para `{tool_name}`. Verifica que existe."
        
        # Rate limit
        if "429" in error or "rate limit" in error_lower:
            return f"Discord me está limitando. Espera un momento antes de intentar `{tool_name}` de nuevo."
        
        # Invalid input
        if "invalid" in error_lower or "bad request" in error_lower:
            # Return the specific error details instead of generic message
            return f"Datos inválidos para `{tool_name}`. Detalles: {error}"
        
        # Connection errors
        if "timeout" in error_lower or "connection" in error_lower:
            return f"Hubo un problema de conexión ejecutando `{tool_name}`. Intenta de nuevo."
        
        # Generic fallback
        return f"Ocurrió un error ejecutando `{tool_name}`. Te envié los detalles por DM."
    
    async def _get_or_create_session(self, guild_id: int) -> list:
        """Get existing chat session or create new one."""
        if guild_id not in self.sessions:
            history = [{"role": "system", "content": self.personality}]
            context = await self.memory.get_buffer(guild_id)
            for msg in context:
                role = "user" if msg["author_id"] == OWNER_ID else "assistant"
                history.append({"role": role, "content": msg["content"]})
            self.sessions[guild_id] = history
        return self.sessions[guild_id]
    
    async def _process_prefix_command(self, content: str, message: discord.Message) -> Optional[str]:
        """Process prefix commands (!)."""
        parts = content[1:].split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        if cmd == "reload" and args.lower() == "mcp":
            count = await self.reload_mcp()
            return f"✅ MCP recargado. {count} herramientas disponibles."
        
        elif cmd == "model":
            if not args:
                free = [k for k in MODELS.keys() if ":free" in k]
                paid = [k for k in MODELS.keys() if ":free" not in k]
                return (
                    f"**Modelo actual:** `{self.current_model}`\n\n"
                    f"**Gratis:**\n" + "\n".join([f"- `{m}`" for m in free]) + "\n\n"
                    f"**Paid:**\n" + "\n".join([f"- `{m}`" for m in paid])
                )
            if await self.set_model(args):
                return f"✅ Modelo cambiado a `{args}`"
            else:
                return f"❌ Modelo `{args}` no encontrado."
        
        elif cmd == "status":
            status = await self.get_status()
            credits_str = f"${status['credits']:.4f}" if status['credits'] is not None else "N/A"
            return (
                f"**Estado de Lycan:**\n"
                f"- Modelo: `{status['model']}`\n"
                f"- MCP: {'✅' if status['mcp_connected'] else '❌'} ({status['tools_count']} tools)\n"
                f"- Sesiones: {status['sessions']}\n"
                f"- Tokens usados: {status['tokens_used']:,}\n"
                f"- Créditos OR: {credits_str}"
            )
        
        elif cmd == "clear":
            self.clear_session(message.guild.id)
            return "✅ Historial limpiado."
        
        elif cmd == "reason":
            if not args:
                status = "✅ Activado" if self._reasoning_enabled else "❌ Desactivado"
                return f"**Razonamiento:** {status}\n\nUsa `!reason 1` para activar o `!reason 0` para desactivar."
            if args in ["1", "on", "true"]:
                self._reasoning_enabled = True
                return "✅ Razonamiento activado. Lycan pensará antes de actuar."
            elif args in ["0", "off", "false"]:
                self._reasoning_enabled = False
                return "✅ Razonamiento desactivado."
            else:
                return "❌ Usa `!reason 1` o `!reason 0`"
        
        return None
    
    async def _process_with_tools(
        self, 
        guild_id: int, 
        content: str,
        guild: discord.Guild,
        channel: discord.TextChannel
    ) -> str:
        """Process message with MCP tool calling."""
        history = await self._get_or_create_session(guild_id)
        
        # Add context about current location to the user message
        context_info = f"[Contexto: Canal actual ID={channel.id}, nombre='{channel.name}']\n"
        enriched_content = context_info + content
        history.append({"role": "user", "content": enriched_content})
        
        # === REASONING STEP (If enabled) ===
        if self._reasoning_enabled:
            logger.info("🧠 Reasoning enabled. Generating thought process...")
            try:
                # Create a temporary chain for thinking
                reasoning_chain = list(history)  # Copy existing history
                reasoning_chain.append({
                    "role": "system",
                    "content": (
                        "🔴 MODO DE RAZONAMIENTO ACTIVO 🔴\n"
                        "ANTES de responder o usar herramientas, ANALIZA la situación:\n"
                        "1. ¿Qué pide el usuario exactamente?\n"
                        "2. ¿Qué herramientas (MCP) necesitas? Revisa sus parámetros requeridos.\n"
                        "3. ¿Falta información? (IDs, nombres, etc)\n"
                        "4. Planifica la secuencia de acciones.\n"
                        "\n"
                        "RESPONDE SOLO CON TU PENSAMIENTO Y PLAN. NO EJECUTES HERRAMIENTAS AÚN."
                    )
                })

                thought_response = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.client.chat.completions.create,
                        model=self.current_model,
                        messages=reasoning_chain,
                        max_tokens=1024,
                        temperature=0.7
                    ),
                    timeout=LLM_TIMEOUT
                )
                
                thought_content = thought_response.choices[0].message.content
                logger.info(f"🧠 PENSAMIENTO: {thought_content}")
                
                # Inject thought into history so the next call sees it
                history.append({
                    "role": "assistant", 
                    "content": f"Opinió/Pensamiento Interno:\n{thought_content}\n\n[Fin del pensamiento, procediendo a ejecutar]"
                })
                
            except Exception as e:
                logger.error(f"⚠️ Reasoning step failed: {e}")
                # We continue even if reasoning fails, falling back to normal behavior
        
        # === MEMORY RETRIEVAL ===
        # Search for relevant memories based on user's message
        user_query = history[-1]["content"] if history else ""
        try:
            memories = await self.retrieval.search(user_query, guild.id, limit=3)
            if memories:
                memory_context = "\n\n## 🧠 MEMORIAS RELEVANTES:\n"
                for mem in memories:
                    memory_context += f"- [{mem.get('timestamp', 'N/A')}] {mem.get('summary', '')}\n"
                
                # Inject memories into the system prompt
                history[0]["content"] = self.personality + memory_context
                logger.info(f"Injected {len(memories)} memories into context")
        except Exception as e:
            logger.warning(f"Memory retrieval failed: {e}")
        
        await self._ensure_mcp_connected()
        tools = self.mcp.get_tools_for_llm()
        
        if not self.client:
            return "❌ OpenRouter no configurado. Agrega OPENROUTER_API_KEY."
        
        # Add guild and channel context to tools
        for tool in tools:
            if "parameters" in tool.get("function", {}):
                params = tool["function"]["parameters"]
                if "properties" in params:
                    if "guild_id" in params["properties"]:
                        params["properties"]["guild_id"]["default"] = str(guild.id)
                    if "channel_id" in params["properties"]:
                        params["properties"]["channel_id"]["default"] = str(channel.id)
        
        # Call LLM with timeout
        # Call LLM with timeout
        logger.info(f"Calling {self.current_model} with {len(tools)} tools")
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.client.chat.completions.create,
                    model=self.current_model,
                    messages=history,
                    tools=tools if tools else None,
                    tool_choice="auto" if tools else None,
                    max_tokens=2048,
                    temperature=0.7
                ),
                timeout=LLM_TIMEOUT
            )
        except asyncio.TimeoutError:
            logger.error(f"LLM call timed out after {LLM_TIMEOUT}s")
            # Remove the user message we just added
            history.pop()
            return f"⏱️ Timeout: El modelo tardó más de {LLM_TIMEOUT}s. Intenta de nuevo o cambia de modelo con `!model`"
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            history.pop()
            return f"❌ Error LLM: {str(e)}"
        
        response_message = response.choices[0].message
        
        # Debug logging
        has_tool_calls = bool(response_message.tool_calls)
        content_preview = (response_message.content or "")[:100]
        logger.info(f"Response: tool_calls={has_tool_calls}, content='{content_preview}...'")
        
        # Update token count
        if hasattr(response, 'usage') and response.usage:
            self._tokens_used += response.usage.total_tokens
        
        # Process tool calls
        if response_message.tool_calls:
            tool_results = []
            
            for tool_call in response_message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)
                
                # Only inject guild_id if the tool expects it (check schema)
                tool_info = self.mcp.tools.get(tool_name, {})
                tool_schema = tool_info.get("tool", {}).get("inputSchema", {})
                tool_properties = tool_schema.get("properties", {})
                if "guild_id" in tool_properties and "guild_id" not in tool_args:
                    tool_args["guild_id"] = str(guild.id)
                
                # === ARGUMENT FILTERING ===
                # Remove any LLM-invented arguments that don't exist in the schema
                valid_args = set(tool_properties.keys())
                original_args = set(tool_args.keys())
                invalid_args = original_args - valid_args
                
                # DEBUG: Log schema info
                print(f"!!! FILTER DEBUG: {tool_name} valid_args={valid_args}, received={original_args}, invalid={invalid_args}")
                if not valid_args:
                    print(f"!!! WARNING: {tool_name} has EMPTY schema - cannot filter!")
                
                if invalid_args:
                    print(f"!!! FILTERING {tool_name}: removing {invalid_args}")
                    logger.warning(f"Filtering invalid args from {tool_name}: {invalid_args}")
                    tool_args = {k: v for k, v in tool_args.items() if k in valid_args}
                
                # === CRITICAL ACTION INTERCEPTION ===
                if tool_name in self._critical_actions:
                    import time as time_module
                    self._pending_confirmations[guild.id] = {
                        "action": tool_name,
                        "args": tool_args,
                        "expires": time_module.time() + 60  # 60 second expiry
                    }
                    logger.info(f"Critical action intercepted: {tool_name}")
                    tool_results.append({
                        "tool_call_id": tool_call.id,
                        "name": tool_name,
                        "result": f"⚠️ CONFIRMACIÓN REQUERIDA: Acción '{tool_name}' con args {tool_args}. Responde 'sí' para ejecutar o 'no' para cancelar."
                    })
                    continue  # Skip actual execution, wait for confirmation
                
                logger.info(f"Executing: {tool_name}")
                result = await self.mcp.call_tool(tool_name, tool_args)
                logger.info(f"Tool Result: {str(result)[:200]}")  # Log first 200 chars of result
                tool_results.append({
                    "tool_call_id": tool_call.id,
                    "name": tool_name,
                    "result": result
                })
            
            # Add to history
            history.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    } for tc in response_message.tool_calls
                ]
            })
            
            for tr in tool_results:
                history.append({
                    "role": "tool",
                    "tool_call_id": tr["tool_call_id"],
                    "content": tr["result"]
                })
            
            # Get final response with timeout
            try:
                final_response = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.client.chat.completions.create,
                        model=self.current_model,
                        messages=history,
                        max_tokens=2048,
                        temperature=0.7
                    ),
                    timeout=LLM_TIMEOUT
                )
                response_text = final_response.choices[0].message.content
                
                if hasattr(final_response, 'usage') and final_response.usage:
                    self._tokens_used += final_response.usage.total_tokens
            except asyncio.TimeoutError:
                logger.error(f"Final LLM call timed out after {LLM_TIMEOUT}s")
                response_text = "⏱️ Timeout al generar respuesta final. Las herramientas se ejecutaron correctamente."
            except Exception as e:
                logger.error(f"Final LLM call failed: {e}")
                response_text = f"❌ Error generando respuesta: {str(e)}"
        else:
            # Check for XML-style tool calls (fallback for models without native function calling)
            xml_tool_calls = self._parse_xml_tool_calls(response_message.content)
            if xml_tool_calls:
                # ... (Existing XML logic, see below we replace it to unify) ...
                # Actually, let's just use response_message.content as response_text for the next block to handle
                response_text = response_message.content
            else:
                response_text = response_message.content
        
        # === FINAL SAFETY CHECK: XML in Final Response ===
        # This catches cases where:
        # 1. Model used native tools, but the confirmation message (response_text) contains NEW XML calls.
        # 2. Model used XML fallback (captured above), and we want to process it here.
        
        final_xml_calls = self._parse_xml_tool_calls(response_text)
        if final_xml_calls:
            logger.info(f"Found {len(final_xml_calls)} XML tool calls in final response. Executing...")
            tool_results = []
            
            for tc in final_xml_calls:
                tool_name = tc["name"]
                tool_args = tc["arguments"]
                
                # Get tool schema for filtering
                tool_info = self.mcp.tools.get(tool_name, {})
                tool_schema = tool_info.get("tool", {}).get("inputSchema", {})
                tool_properties = tool_schema.get("properties", {})
                
                # Add context only if the tool expects it
                if "guild_id" in tool_properties and "guild_id" not in tool_args:
                    tool_args["guild_id"] = str(guild.id)
                if "channel_id" in tool_properties and "channel_id" not in tool_args:
                    tool_args["channel_id"] = str(channel.id)
                
                # Filter out any args not in schema
                valid_args = set(tool_properties.keys())
                if valid_args:
                    invalid_args = set(tool_args.keys()) - valid_args
                    if invalid_args:
                        logger.info(f"Filtering invalid args from {tool_name}: {invalid_args}")
                        tool_args = {k: v for k, v in tool_args.items() if k in valid_args}
                
                logger.info(f"Executing (Post-Check): {tool_name}")
                try:
                    result = await self.mcp.call_tool(tool_name, tool_args)
                    result_str = str(result)
                    
                    # Smart Error Handling
                    # 1. Check for "Tool not found" (Hallucinations)
                    if "not found" in result_str.lower() and "tool" in result_str.lower():
                        import difflib
                        
                        # Find closest match
                        available_tools = list(self.mcp.tools.keys())
                        matches = difflib.get_close_matches(tool_name, available_tools, n=1, cutoff=0.5)
                        
                        suggestion = ""
                        if matches:
                            suggestion = f" ¿Quizás quisiste decir `{matches[0]}`?"
                        
                        friendly_msg = f"No existe la herramienta `{tool_name}`.{suggestion} Usa `list_tools` para ver las disponibles."
                        tool_results.append(f"❌ {friendly_msg}")
                        
                        # Also override the result in history so the LLM sees the correction
                        # (The 'result' variable currently holds the raw string from MCP)
                        result = f"ERROR: Tool '{tool_name}' not found.{suggestion}"

                    # 2. Check for standard errors
                    elif "Error:" in result_str or "'code':" in result_str or "error" in result_str.lower()[:50]:
                        friendly_msg = self._translate_error(tool_name, result_str)
                        tool_results.append(f"❌ {friendly_msg}")
                        # Send technical details via DM
                        try:
                            owner = await self.bot.fetch_user(self._owner_id)
                            await owner.send(f"🔧 **Error técnico en {tool_name}:**\n```{result_str[:1800]}```")
                        except:
                            pass
                        # Send technical details via DM
                        try:
                            owner = await self.bot.fetch_user(self._owner_id)
                            await owner.send(f"🔧 **Error técnico en {tool_name}:**\n```{result_str[:1800]}```")
                        except:
                            pass
                    else:
                        tool_results.append(f"✅ {tool_name}: {result_str[:200]}")
                except Exception as tool_error:
                    error_str = str(tool_error)
                    friendly_msg = self._translate_error(tool_name, error_str)
                    tool_results.append(f"❌ {friendly_msg}")
                    # Send technical details via DM to owner
                    try:
                        owner = await self.bot.fetch_user(self._owner_id)
                        await owner.send(f"🔧 **Error técnico en {tool_name}:**\n```{error_str[:1800]}```")
                    except:
                        pass  # DM failed, just continue
            
            # Replace the XML garbage with the results
            if tool_results:
                response_text = "\n".join(tool_results)
        
        # === CLEANUP: Remove technical garbage from response ===
        # Sometimes models include JSON, code blocks, or tool parameters in their response
        if response_text:
            import re as cleanup_re
            
            # Remove JSON code blocks: ```json ... ```
            response_text = cleanup_re.sub(r'```json\s*\{[^`]*\}\s*```', '', response_text, flags=cleanup_re.DOTALL)
            response_text = cleanup_re.sub(r'```\s*\{[^`]*\}\s*```', '', response_text, flags=cleanup_re.DOTALL)
            
            # Remove standalone JSON objects that look like tool params
            # Pattern: { "channel_id": "...", "title": "...", ... }
            response_text = cleanup_re.sub(r'\{\s*"channel_id"\s*:[^}]+\}', '', response_text, flags=cleanup_re.DOTALL)
            response_text = cleanup_re.sub(r'\{\s*"title"\s*:[^}]+\}', '', response_text, flags=cleanup_re.DOTALL)
            
            # Remove XML tool_call blocks (in case they slip through)
            response_text = cleanup_re.sub(r'<\s*tool_call\s*>.*?<\s*/\s*tool_call\s*>', '', response_text, flags=cleanup_re.DOTALL | cleanup_re.IGNORECASE)
            
            # Clean up excessive whitespace left behind
            response_text = cleanup_re.sub(r'\n{3,}', '\n\n', response_text)
            response_text = response_text.strip()
        
        history.append({"role": "assistant", "content": response_text})
        return response_text or "No response"
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Main entry point - handles all messages."""
        
        # DEBUG: Log every message received
        print(f"!!! MESSAGE RECEIVED from {message.author.name}: {message.content[:50]}...")
        
        # Ignore bots and DMs
        if message.author.bot or not message.guild:
            return
        
        # Security Gate
        if not self._is_owner(message.author.id):
            return
        
        # Check if this message is directed at us (mention or reply)
        is_directed = self._is_mention_or_reply(message)
        
        # Get content and clean mention if present
        content = message.content.strip()
        content = content.replace(f"<@{self.bot.user.id}>", "").strip()
        
        if not content:
            return
        
        # Handle prefix commands (work with or without mention)
        if content.startswith(PREFIX):
            async with message.channel.typing():
                cmd_response = await self._process_prefix_command(content, message)
                if cmd_response:
                    await message.reply(cmd_response)
            return
        
        # For non-prefix messages, only respond if directed at us
        if not is_directed:
            return
        
        import time
        guild_id = message.guild.id
        
        # === CONFIRMATION HANDLING ===
        # Check if this is a confirmation response
        if guild_id in self._pending_confirmations:
            pending = self._pending_confirmations[guild_id]
            content_lower = content.lower().strip()
            
            # Check for confirmation
            if content_lower in ["sí", "si", "yes", "confirmar", "ok"]:
                action = pending["action"]
                args = pending["args"]
                del self._pending_confirmations[guild_id]
                
                # Execute the pending action
                async with message.channel.typing():
                    result = await self.mcp.call_tool(action, args)
                    await message.reply(f"✅ Ejecutado: {result}")
                return
            elif content_lower in ["no", "cancelar", "cancel"]:
                del self._pending_confirmations[guild_id]
                await message.reply("❌ Acción cancelada.")
                return
            # If neither, the confirmation expires and we process normally
            if time.time() > pending.get("expires", 0):
                del self._pending_confirmations[guild_id]
        
        # === RATE LIMITING ===
        now = time.time()
        last_time = self._last_response_time.get(guild_id, 0)
        time_since_last = now - last_time
        
        if time_since_last < self._cooldown_seconds:
            wait_time = self._cooldown_seconds - time_since_last
            logger.info(f"Rate limit: waiting {wait_time:.1f}s")
            await asyncio.sleep(wait_time)
        
        async with message.channel.typing():
            try:
                response_text = await self._process_with_tools(
                    guild_id=message.guild.id,
                    content=content,
                    guild=message.guild,
                    channel=message.channel
                )
                
                # Check if response is an error (send via DM)
                if response_text.startswith("❌") or response_text.startswith("⏱️"):
                    try:
                        await message.author.send(response_text)
                    except:
                        pass  # DMs might be disabled
                    return
                
                # Save to memory
                await self.memory.add_message(
                    guild_id=message.guild.id,
                    author_id=message.author.id,
                    content=content,
                    is_bot=False
                )
                await self.memory.add_message(
                    guild_id=message.guild.id,
                    author_id=self.bot.user.id,
                    content=response_text,
                    is_bot=True
                )
                
                await self.memory.maybe_compress(message.guild.id)
                
                # Send response
                if len(response_text) > 2000:
                    chunks = [response_text[i:i+2000] for i in range(0, len(response_text), 2000)]
                    for chunk in chunks:
                        await message.reply(chunk)
                else:
                    await message.reply(response_text)
                
                # Update rate limit timestamp
                self._last_response_time[guild_id] = time.time()
                
            except Exception as e:
                # Send errors via DM
                try:
                    await message.author.send(f"❌ Error: {str(e)}")
                except:
                    pass


async def setup(bot):
    await bot.add_cog(AICog(bot))

