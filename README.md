# CoupleHub MCP Server

## What this is
A Model Context Protocol server that wraps your CoupleHub API.
Once deployed, Claude Desktop can call your recipes, meal plans, calendar, and grocery list directly in conversation.

## Files
- `server.py` — the MCP server with all tools
- `wsgi.py` — entry point for your Hostido Python app
- `requirements.txt` — Python dependencies
- `claude_desktop_config.json` — paste this into Claude Desktop config

---

## Step 1: Deploy to Hostido

1. In your hosting panel, go to **Zarządzaj aplikacjami Python → Dodaj aplikację**
2. Set:
   - Python version: **3.12.13**
   - Main directory: e.g. `couplehub_mcp`
   - URL: pick a subdomain or path, e.g. `mcp.host740041.xce.pl`
   - Start file: `wsgi.py`
   - Start function: `app`
3. Upload `server.py`, `wsgi.py`, `requirements.txt` to that directory via FTP/file manager
4. In the Python app panel, install dependencies:
   ```
   pip install -r requirements.txt
   ```
5. Start the app

Test it: visit `https://mcp.host740041.xce.pl/sse` — you should see an SSE stream open.

---

## Step 2: Install Claude Desktop

Download from: https://claude.ai/download

---

## Step 3: Install mcp-proxy (on your machine)

```bash
pip install mcp-proxy
# or
uv tool install mcp-proxy
```

---

## Step 4: Configure Claude Desktop

Find the config file:
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Mac**: `~/Library/Application Support/Claude/claude_desktop_config.json`

Paste this (update the URL to match your actual deployed URL):

```json
{
  "mcpServers": {
    "couplehub": {
      "command": "mcp-proxy",
      "args": ["https://mcp.host740041.xce.pl/sse"]
    }
  }
}
```

Restart Claude Desktop. You should see a 🔧 tools icon — click it to confirm CoupleHub tools are listed.

---

## Available tools

| Tool | What it does |
|------|-------------|
| `get_recipes` | List all recipes, filter by name or side dish |
| `get_recipe` | Full recipe with ingredients and instructions |
| `create_recipe` | Add a new recipe |
| `rate_recipe` | Rate a recipe 1-5 |
| `get_meal_plan` | Get week plan with entries and events |
| `create_meal_plan` | Create a new week shell |
| `upsert_meal_entries` | Set the week's meals |
| `get_calendar_events` | List calendar events by date range |
| `create_calendar_event` | Add a calendar event |
| `delete_calendar_event` | Delete a calendar event |
| `get_grocery_list` | Get grocery list for a meal plan |
| `generate_grocery_list` | Auto-generate grocery list from meal plan |
| `get_ingredients` | Search ingredients by name or category |
