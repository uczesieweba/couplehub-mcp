# CoupleHub MCP Server

## Local/staging backend authentication

Configure `COUPLEHUB_API_BASE` explicitly (there is no production default) and
`COUPLEHUB_API_TOKEN` in the server environment. The PHP runtime must have the
same token. The server adds the Bearer header automatically; ChatGPT does not
need the PHP token in its prompts or tool arguments. Keep secrets outside Git.
HTTPS is required except for a loopback development backend. Redirects are not
followed, to avoid forwarding credentials to another destination.

Tests: `python -m unittest discover -s tests -v` after installing requirements.

For the cloud onboarding runtime, start local MariaDB and import the development
dump first, then run `python tests/integration_auth.py`. This test starts temporary
loopback PHP and SSE MCP servers, generates a token only in memory, overrides
database settings to the local socket, checks rejection cases, and verifies MCP
reads plus temporary chore CRUD/cleanup. It stops its test servers afterward.
It does not connect to production or test ChatGPT's hosted connector/OAuth flow.

MCP client authentication now defaults to Auth0 and fails closed without its
configuration. See [AUTH0_SETUP.md](AUTH0_SETUP.md) for tenant/application setup,
household access restrictions and the remaining hosted verification steps.
The companion PHP branch now implements dashboard browser sessions, but their
real hosted Auth0 round trip remains a prerequisite for a production rollout.
Nothing in this change deploys or modifies production.

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
