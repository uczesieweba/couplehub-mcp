# CoupleHub MCP Server — Documentation

## Overview

The CoupleHub MCP (Model Context Protocol) server exposes the CoupleHub PHP API as AI-callable tools. It allows AI assistants (Claude, ChatGPT) to read and write meal plans, recipes, calendar events, and grocery lists on your behalf during conversation.

---

## Architecture

```
You (mobile/desktop)
        ↓
AI Assistant (ChatGPT / Claude)
        ↓
MCP Server (Render)
https://couplehub-mcp.onrender.com
        ↓
CoupleHub PHP API (Hostido, Poland)
https://host740041.xce.pl/CoupleHub_DEV/api
        ↓
MariaDB Database
```

---

## MCP Server

### Hosting
- **Platform:** Render.com (free tier)
- **URL:** https://couplehub-mcp.onrender.com
- **SSE endpoint:** https://couplehub-mcp.onrender.com/sse
- **Runtime:** Python 3, fastmcp library
- **Transport:** SSE (Server-Sent Events)

### GitHub Repository
- https://github.com/uczesieweba/couplehub-mcp
- Render auto-deploys on every push to main

### Files
| File | Purpose |
|------|---------|
| `server.py` | MCP server — all tool definitions |
| `requirements.txt` | Python dependencies (fastmcp, httpx) |
| `render.yaml` | Render deployment config |

### Start Command
```
python server.py
```

### Key Behaviour
- Binds to `0.0.0.0` on the `$PORT` environment variable provided by Render
- Pings every 15 seconds to keep SSE connection alive
- **Free tier sleeps after ~15 minutes of inactivity** — first request after sleep will time out. Open https://couplehub-mcp.onrender.com/sse in a browser to wake it, then retry.
- To keep always-on: upgrade Render to paid ($7/month) or use UptimeRobot free tier to ping the endpoint every 5 minutes

---

## PHP API (CoupleHub)

### Hosting
- **Platform:** Hostido shared hosting (Poland)
- **Base URL:** https://host740041.xce.pl/CoupleHub_DEV/api
- **Runtime:** PHP / MariaDB
- **Auth:** Bearer token (currently bypassed — unauthenticated requests default to user_id=3)

### Auth Config
Located at: `public_html/CoupleHub_DEV/api/config/auth.php`

Current behaviour: if no valid Bearer token is provided, defaults to `user_id = 3` (couplehub_agent). Jakub and Erica's tokens still work if provided.

```
token_jakub  → user_id 1
token_erica  → user_id 2
(no token)   → user_id 3 (couplehub_agent)
```

---

## Available MCP Tools

### Recipes
| Tool | Description |
|------|-------------|
| `get_recipes(search, is_side)` | List all recipes. Filter by name or is_side (0=mains, 1=sides) |
| `get_recipe(id)` | Full recipe with ingredients, instructions, ratings |
| `create_recipe(name, instructions, ingredients, ...)` | Create a new recipe |
| `rate_recipe(recipe_id, user_id, rating, notes)` | Rate a recipe 1–5 |

### Meal Calendar
| Tool | Description |
|------|-------------|
| `get_meal_calendar(from_date, to_date)` | Get week view — entries + calendar events |
| `upsert_meal_calendar(created_by, entries)` | Schedule meals — single, multi-date, or recurrence |
| `update_meal_calendar_entry(id, ...)` | Update a single entry |
| `delete_meal_calendar_entry(id)` | Delete entry — auto-cleans unactioned grocery rows |

### Calendar Events
| Tool | Description |
|------|-------------|
| `get_calendar_events(from_date, to_date)` | List events in date range |
| `create_calendar_event(event_date, title, event_time, notes, created_by)` | Add an event — created_by mandatory |
| `delete_calendar_event(id)` | Delete an event |

### Recommended Grocery
| Tool | Description |
|------|-------------|
| `generate_recommended_grocery(created_by, meal_calendar_ids)` | Generate recommendations from scheduled meals |
| `get_recommended_grocery()` | List pending recommendations |
| `add_recommended_grocery(item_name, quantity, unit)` | Manual add to recommended list |
| `promote_recommended_grocery(item_ids)` | Move items to active grocery list |
| `reject_recommended_grocery(item_ids)` | Reject items (already have them) |

### Grocery List
| Tool | Description |
|------|-------------|
| `get_grocery_list()` | Active shopping list |
| `add_grocery_list_item(item_name, quantity, unit)` | Direct add — skips recommended stage |
| `mark_grocery_bought(ids)` | Mark items as purchased |
| `remove_grocery_list_item(ids)` | Remove items from list |

### Item Catalogue
| Tool | Description |
|------|-------------|
| `get_items(search, category)` | Search item catalogue |
| `create_item(name, category, default_unit)` | Add item to catalogue |

### Receipts
| Tool | Description |
|------|-------------|
| `upload_receipt(image_base64)` | Upload receipt photo |
| `update_receipt(id, store_name, purchased_at, total_amount)` | Update parsed metadata |
| `confirm_receipt(id)` | Mark receipt as confirmed |

---

## Connecting to ChatGPT

1. Wake the server: open https://couplehub-mcp.onrender.com/sse in browser
2. In ChatGPT: **Settings → Connectors → Add MCP Server**
3. Enter URL: `https://couplehub-mcp.onrender.com/sse`
4. Save and test

**Known issue:** ChatGPT mobile app has an intermittent bug where MCP calls fail silently and return cached data. If this happens, clear ChatGPT cache or remove and re-add the connector.

---

## Connecting to Claude Desktop (future)

Install mcp-proxy, then add to `claude_desktop_config.json`:

- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **Mac:** `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "couplehub": {
      "command": "mcp-proxy",
      "args": ["https://couplehub-mcp.onrender.com/sse"]
    }
  }
}
```

---

## Redeploying / Updating

1. Edit files in GitHub repo
2. Render auto-deploys within ~2 minutes
3. Monitor logs at render.com dashboard

To manually trigger redeploy: Render dashboard → your service → **Manual Deploy**

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| ChatGPT times out | Render sleeping | Open /sse in browser to wake, retry |
| ChatGPT returns stale data | ChatGPT mobile cache bug | Clear app cache, remove/re-add connector |
| 401 from PHP API | Auth config issue | Check auth.php on Hostido |
| Render deploy fails | Code error | Check deploy logs on Render dashboard |
| SSE stream shows nothing | Server crashed | Check Render logs, redeploy |
