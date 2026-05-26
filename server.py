"""
CoupleHub MCP Server
Wraps the CoupleHub API as MCP tools for Claude Desktop.
"""

import httpx
from mcp.server.fastmcp import FastMCP

API_BASE = "https://host740041.xce.pl/CoupleHub_DEV/api"

mcp = FastMCP("CoupleHub")


def api(method: str, path: str, **kwargs):
    """Make a request to the CoupleHub API."""
    with httpx.Client(timeout=15) as client:
        r = client.request(method, f"{API_BASE}{path}", **kwargs)
        r.raise_for_status()
        return r.json()


# ── RECIPES ──────────────────────────────────────────────────────────────────

@mcp.tool()
def get_recipes(search: str = "", is_side: int | None = None) -> list:
    """
    List all recipes. Optionally filter by name (search) or whether it's a
    side dish (is_side=0 for mains, is_side=1 for sides).
    """
    params = {}
    if search:
        params["search"] = search
    if is_side is not None:
        params["is_side"] = is_side
    return api("GET", "/recipes", params=params)


@mcp.tool()
def get_recipe(id: int) -> dict:
    """
    Get full recipe details including ingredients, instructions, and ratings.
    """
    return api("GET", f"/recipes/{id}")


@mcp.tool()
def create_recipe(
    name: str,
    instructions: str = "",
    prep_time_mins: int | None = None,
    cook_time_mins: int | None = None,
    is_side: bool = False,
    source_url: str | None = None,
    ingredients: list | None = None,
    suggested_sides: list | None = None,
) -> dict:
    """
    Create a new recipe. ingredients is a list of dicts with keys:
    name, category, quantity, unit. suggested_sides is a list of recipe names.
    """
    body = {
        "name": name,
        "instructions": instructions,
        "prep_time_mins": prep_time_mins,
        "cook_time_mins": cook_time_mins,
        "is_side": is_side,
        "source_url": source_url,
        "ingredients": ingredients or [],
        "suggested_sides": suggested_sides or [],
    }
    return api("POST", "/recipes", json=body)


@mcp.tool()
def rate_recipe(recipe_id: int, user_id: int, rating: int, notes: str = "") -> dict:
    """
    Rate a recipe 1-5. user_id: 1=Jakub, 2=Erica.
    """
    return api("POST", f"/recipes/{recipe_id}/ratings", json={
        "user_id": user_id,
        "rating": rating,
        "notes": notes or None,
    })


# ── MEAL PLANS ────────────────────────────────────────────────────────────────

@mcp.tool()
def get_meal_plan(date: str) -> dict:
    """
    Get the full week meal plan for a given date (YYYY-MM-DD).
    Returns meal entries and calendar events for that week.
    """
    return api("GET", f"/meal-plans/{date}")


@mcp.tool()
def create_meal_plan(week_start: str, user_id: int = 3) -> dict:
    """
    Create a new meal plan shell for a week starting on week_start (YYYY-MM-DD).
    """
    return api("POST", "/meal-plans", json={"week_start": week_start, "user_id": user_id})


@mcp.tool()
def upsert_meal_entries(meal_plan_id: int, entries: list) -> dict:
    """
    Set meal entries for a week. Each entry is a dict with keys:
    day_of_week (Monday..Sunday), meal_type (lunch|dinner),
    recipe_id (int or null), servings (int), is_eating_out (bool),
    eating_out_note (str or null).
    """
    return api("POST", f"/meal-plans/{meal_plan_id}/entries", json={"entries": entries})


# ── CALENDAR ──────────────────────────────────────────────────────────────────

@mcp.tool()
def get_calendar_events(from_date: str = "", to_date: str = "") -> list:
    """
    List calendar events. Optionally filter by date range (YYYY-MM-DD).
    """
    params = {}
    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date
    return api("GET", "/calendar-events", params=params)


@mcp.tool()
def create_calendar_event(
    event_date: str,
    title: str,
    event_time: str | None = None,
    notes: str | None = None,
    user_id: int = 3,
) -> dict:
    """
    Create a calendar event. event_date is YYYY-MM-DD, event_time is HH:MM (optional).
    """
    return api("POST", "/calendar-events", json={
        "event_date": event_date,
        "title": title,
        "event_time": event_time,
        "notes": notes,
        "user_id": user_id,
    })


@mcp.tool()
def delete_calendar_event(id: int) -> dict:
    """Delete a calendar event by ID."""
    return api("DELETE", f"/calendar-events/{id}")


# ── GROCERY ───────────────────────────────────────────────────────────────────

@mcp.tool()
def get_grocery_list(meal_plan_id: int) -> dict:
    """Get the grocery list for a meal plan."""
    return api("GET", f"/grocery-lists/{meal_plan_id}")


@mcp.tool()
def generate_grocery_list(meal_plan_id: int) -> dict:
    """Generate a grocery list from a meal plan's recipes."""
    return api("POST", f"/grocery-lists/{meal_plan_id}/generate")


@mcp.tool()
def get_ingredients(search: str = "", category: str = "") -> list:
    """
    List all ingredients. Optionally filter by name or category.
    Categories: produce, meat, dairy, pantry, bakery, frozen, drinks, household, other.
    """
    params = {}
    if search:
        params["search"] = search
    if category:
        params["category"] = category
    return api("GET", "/ingredients", params=params)


if __name__ == "__main__":
    mcp.run(transport="sse")
