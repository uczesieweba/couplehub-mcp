# CoupleHub MCP Server

## Deploy to Render

1. Push this repo to GitHub
2. Go to render.com → New → Web Service
3. Connect your GitHub repo
4. Render auto-detects render.yaml and deploys
5. Your MCP server will be at: https://couplehub-mcp.onrender.com/sse

## Connect to ChatGPT

In ChatGPT settings → Connectors (or Tools) → Add MCP server:
- URL: https://couplehub-mcp.onrender.com/sse

## Connect to Claude Desktop

Install mcp-proxy, then add to claude_desktop_config.json:
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

## Available Tools

| Tool | What it does |
|------|-------------|
| get_recipes | List all recipes, filter by name or side dish |
| get_recipe | Full recipe with ingredients and instructions |
| create_recipe | Add a new recipe |
| rate_recipe | Rate a recipe 1-5 |
| get_meal_plan | Get week plan with entries and events |
| create_meal_plan | Create a new week shell |
| upsert_meal_entries | Set the week's meals |
| get_calendar_events | List calendar events by date range |
| create_calendar_event | Add a calendar event |
| delete_calendar_event | Delete a calendar event |
| get_grocery_list | Get grocery list for a meal plan |
| generate_grocery_list | Auto-generate grocery list from meal plan |
| get_ingredients | Search ingredients by name or category |
