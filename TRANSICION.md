# Development Notes — Lycan Bot

> Internal reference document for contributors and future maintainers.

---

## Architecture Overview

Lycan is a **Discord bot with AI capabilities** that can perform real server actions (moderate, create channels, send embeds, manage roles) through MCP (Model Context Protocol) tools.

### Services

| Service | Container | Port | Role |
|---------|-----------|------|------|
| `lycan` | `lycan-bot` | 7000 | Main bot + FastAPI REST |
| `discord-mcp` | `lycan-discord-mcp` | 8080 | MCP server (36 Discord tools) |
| `postgres` | `lycan-db` | 5432 | Persistent storage |

### Dependency Chain

```
lycan-bot ──depends_on──> lycan-db (healthy)
lycan-bot ──depends_on──> lycan-discord-mcp (started)
```

---

## Tech Stack

- **Python 3.12** (`python:3.12-slim` Docker image)
- **PostgreSQL 16** (`postgres:16-alpine`)
- **discord.py** — bot framework
- **FastAPI + uvicorn** — internal REST API
- **asyncpg** — async PostgreSQL driver
- **aiohttp** — async HTTP client
- **openai** SDK — used to call OpenRouter
- **FastMCP** — MCP server framework

---

## Environment Variables

See `.env.example` for the full list. Key variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `DISCORD_TOKEN` | ✅ | Discord bot token |
| `DISCORD_GUILD_ID` | ✅ | Primary server ID |
| `LYCAN_OWNER_ID` | ✅ | Discord user ID allowed to control the bot |
| `DATABASE_URL` | ✅ | PostgreSQL connection string |
| `OPENROUTER_API_KEY` | ✅ | LLM provider API key |
| `MCP_HOST` | Internal | MCP server URL (do not change in Docker) |

---

## AI Module

### Message Processing Flow

1. User mentions Lycan → `on_message` fires
2. If message starts with a prefix command (`!model`, `!status`, `!clear`, `!reload mcp`, `!reason`) → handled directly without LLM call
3. Otherwise → `_process_with_tools()`:
   - Channel context is injected into the message
   - LLM is called with all 36 MCP tools available
   - If response contains native `tool_calls` → execute and reply
   - If response contains `<tool_call>` XML → XML fallback parser executes
   - If plain text → reply directly

### Supported LLM Models (OpenRouter)

| Model | Notes |
|-------|-------|
| `xiaomi/mimo-v2-flash:free` | Works well; uses XML fallback for tool calls |
| `mistralai/devstral-2512:free` | Has known issues with tool call IDs |
| `openai/gpt-oss-120b:free` | Works but slower |

### Bot Commands (Discord)

| Command | Description |
|---------|-------------|
| `!status` | Show current model, MCP status, token count |
| `!model [name]` | View or switch LLM model (persisted in DB) |
| `!clear` | Clear conversation history |
| `!reload mcp` | Reconnect MCP servers |
| `!reason 1\|0` | Toggle reasoning mode (logic pending) |

---

## MCP Discord Tools

The `mcp_discord/tools/` directory contains 36 tools organized by category:

| File | Tools |
|------|-------|
| `channels.py` | `create_channel`, `delete_channel`, `create_category`, `edit_permissions` |
| `messages.py` | `send_message`, `send_embed`, `send_embed_with_fields`, `delete_message`, `pin_message`, `react_to_message`, `fetch_messages` |
| `roles.py` | `create_role`, `delete_role`, `add_role_to_user`, `remove_role`, `list_roles` |
| `server_info.py` | `get_server_info`, `get_channels`, `create_invite`, `get_emojis` |
| `users.py` | `kick_user`, `ban_user`, `timeout_user`, `get_member_info`, `change_nickname` |

### `send_embed_with_fields` — Accepted Formats

The `fields` parameter accepts two formats:

```python
# Pipe format
"Rule1:Content1|Rule2:Content2"

# JSON format
[{"name": "Rule1", "value": "Content1"}, {"name": "Rule2", "value": "Content2"}]
```

---

## Applying Code Changes

```bash
# Rebuild and restart the bot
cd Lycan
sudo docker compose up -d --build lycan

# Rebuild all services (if MCP was also modified)
sudo docker compose up -d --build

# View live logs
sudo docker logs lycan-bot -f

# View MCP logs
sudo docker logs lycan-discord-mcp --tail 30

# Access the database
sudo docker exec -it lycan-db psql -U lycan -d lycan
```

> ⚠️ Using `docker compose restart` alone does **not** apply code changes. Always use `--build`.

---

## Technical Debt & Roadmap

### High Priority

- [ ] Implement `!reason` flag logic (`_reasoning_enabled` flag exists but is unused)
- [ ] Hot-reload support for `mcp_servers.json` to add new MCPs without restart
- [ ] Improve tool selection guidance in LLM context (model sometimes uses `send_message` instead of `send_embed`)

### Medium Priority

- [ ] Persist conversation history in PostgreSQL
- [ ] Implement ChromaDB-based semantic memory (`retrieval.py` is a stub)
- [ ] Add Tavily MCP for web search capabilities
- [ ] Tool execution verification — retry on failure

### Long-term

- [ ] Web dashboard (`web/` directory exists but is empty)
- [ ] Visible reasoning UI (similar to Claude's thinking blocks)
- [ ] RBAC — granular permissions per Discord role for bot commands

---

## Known Issues

| Issue | Root Cause | Workaround |
|-------|-----------|------------|
| Devstral returns 400 on tool calls | OpenRouter/Mistral bug with tool call IDs | Use `xiaomi/mimo-v2-flash:free` instead |
| Model uses `send_message` instead of `send_embed` | Weak tool selection by model | Prompt improvement planned |
| XML tool calls shown as plain text | Parser format mismatch | Parser now handles both XML and native formats |
