"""
CoupleHub MCP Server — v2
Wraps the CoupleHub v2 PHP API as MCP tools for Claude/ChatGPT.
"""

import os
import httpx
from fastmcp import FastMCP

API_BASE = "https://host740041.xce.pl/CoupleHub_DEV/api"

mcp = FastMCP("CoupleHub")


def api(method: str, path: str, **kwargs):
    with httpx.Client(timeout=15) as client:
        r = client.request(method, f"{API_BASE}{path}", **kwargs)
        r.raise_for_status()
        return r.json()


# ── RECIPES ──────────────────────────────────────────────────────────────────

@mcp.tool()
def get_recipes(search: str = "", is_side: int | None = None) -> list:
    """
    List all recipes. Filter by name (search) or is_side (0=mains, 1=sides).
    Always call this before scheduling meals to find recipe IDs.
    """
    params = {}
    if search:
        params["search"] = search
    if is_side is not None:
        params["is_side"] = is_side
    return api("GET", "/recipes", params=params)


@mcp.tool()
def get_recipe(id: int) -> dict:
    """Get full recipe details including ingredients, instructions, and ratings."""
    return api("GET", f"/recipes/{id}")


@mcp.tool()
def create_recipe(
    name: str,
    instructions: str,
    ingredients: list,
    prep_time_mins: int | None = None,
    cook_time_mins: int | None = None,
    is_side: bool = False,
    source_url: str | None = None,
    suggested_sides: list | None = None,
) -> dict:
    """
    Create a new recipe. Only call after explicit user approval.
    ingredients: list of dicts with item_name, quantity, unit, category, default_unit.
    All quantities must be per 1 serving.
    suggested_sides: list of recipe name strings.
    """
    return api("POST", "/recipes", json={
        "name": name,
        "instructions": instructions,
        "ingredients": ingredients,
        "prep_time_mins": prep_time_mins,
        "cook_time_mins": cook_time_mins,
        "is_side": is_side,
        "source_url": source_url,
        "suggested_sides": suggested_sides or [],
    })


@mcp.tool()
def update_recipe(
    id: int,
    name: str | None = None,
    instructions: str | None = None,
    ingredients: list | None = None,
    prep_time_mins: int | None = None,
    cook_time_mins: int | None = None,
    is_side: bool | None = None,
    source_url: str | None = None,
    suggested_sides: list | None = None,
) -> dict:
    """Update an existing recipe. Only include fields that need changing."""
    body = {}
    if name is not None: body["name"] = name
    if instructions is not None: body["instructions"] = instructions
    if ingredients is not None: body["ingredients"] = ingredients
    if prep_time_mins is not None: body["prep_time_mins"] = prep_time_mins
    if cook_time_mins is not None: body["cook_time_mins"] = cook_time_mins
    if is_side is not None: body["is_side"] = is_side
    if source_url is not None: body["source_url"] = source_url
    if suggested_sides is not None: body["suggested_sides"] = suggested_sides
    return api("PATCH", f"/recipes/{id}", json=body)


@mcp.tool()
def delete_recipe(id: int) -> dict:
    """Delete a recipe by ID."""
    return api("DELETE", f"/recipes/{id}")


@mcp.tool()
def rate_recipe(recipe_id: int, user_id: int, rating: int, notes: str = "") -> dict:
    """
    Rate a recipe 1-5. user_id: 1=Jakub, 2=Erica.
    Call when user says something like 'that was a 4/5'.
    """
    return api("POST", f"/recipes/{recipe_id}/ratings", json={
        "user_id": user_id,
        "rating": rating,
        "notes": notes or None,
    })


# ── ITEM CATALOGUE ────────────────────────────────────────────────────────────

@mcp.tool()
def get_items(search: str = "", category: str = "") -> list:
    """
    Search the item catalogue. Use before adding recipe ingredients to find
    existing item IDs and default units.
    Categories: produce, meat, dairy, pantry, bakery, frozen, drinks, household, other.
    """
    params = {}
    if search:
        params["search"] = search
    if category:
        params["category"] = category
    return api("GET", "/items", params=params)


@mcp.tool()
def create_item(name: str, category: str, default_unit: str) -> dict:
    """Add a new item to the catalogue."""
    return api("POST", "/items", json={
        "name": name,
        "category": category,
        "default_unit": default_unit,
    })


# ── MEAL CALENDAR ─────────────────────────────────────────────────────────────

@mcp.tool()
def get_meal_calendar(from_date: str = "", to_date: str = "") -> dict:
    """
    Get meal entries and calendar events for a date range (YYYY-MM-DD).
    Defaults to current week if no dates provided.
    """
    params = {}
    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date
    return api("GET", "/meal-calendar", params=params)


@mcp.tool()
def upsert_meal_calendar(created_by: int, entries: list) -> dict:
    """
    Schedule one or more meal entries. Use a single call with all entries — never loop.

    Each entry supports three date modes:
    - Single date:  { entry_date: "YYYY-MM-DD", meal_type, recipe_id, servings }
    - Multi-date:   { dates: ["YYYY-MM-DD", ...], meal_type, recipe_id, servings }
    - Recurrence:   { recurrence: { type: "weekly"|"weekdays"|"range", day?: "Monday"..., from, to }, meal_type, ... }

    Eating out: set is_eating_out=true, recipe_id=null, eating_out_note="place name".
    servings defaults to 2.
    """
    return api("POST", "/meal-calendar", json={
        "created_by": created_by,
        "entries": entries,
    })


@mcp.tool()
def update_meal_calendar_entry(
    id: int,
    recipe_id: int | None = None,
    servings: int | None = None,
    is_eating_out: bool | None = None,
    eating_out_note: str | None = None,
) -> dict:
    """
    Update a single meal calendar entry.
    Automatically cleans up unactioned grocery rows when recipe or eating_out changes.
    """
    body = {}
    if recipe_id is not None: body["recipe_id"] = recipe_id
    if servings is not None: body["servings"] = servings
    if is_eating_out is not None: body["is_eating_out"] = is_eating_out
    if eating_out_note is not None: body["eating_out_note"] = eating_out_note
    return api("PATCH", f"/meal-calendar/{id}", json=body)


@mcp.tool()
def delete_meal_calendar_entry(id: int) -> dict:
    """
    Delete a meal calendar entry.
    Automatically cleans up unactioned grocery rows.
    """
    return api("DELETE", f"/meal-calendar/{id}")


# ── CALENDAR EVENTS ───────────────────────────────────────────────────────────

@mcp.tool()
def get_calendar_events(from_date: str = "", to_date: str = "") -> list:
    """List calendar events, optionally filtered by date range (YYYY-MM-DD)."""
    params = {}
    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date
    return api("GET", "/calendar-events", params=params)


@mcp.tool()
def create_calendar_event(
    created_by: int,
    title: str,
    event_date: str | None = None,
    event_time: str | None = None,
    notes: str | None = None,
    dates: list | None = None,
    recurrence: dict | None = None,
) -> dict:
    """
    Create calendar event(s). created_by is mandatory — 1=Jakub, 2=Erica.
    Supports single date (event_date), multiple dates (dates[]), or recurrence rule.
    Recurrence: { type: weekly|weekdays|range, day?: Monday...Sunday, from, to }
    Example — gym every Tuesday: recurrence={ type:weekly, day:Tuesday, from:..., to:... }
    """
    body = {"created_by": created_by, "title": title}
    if event_date: body["event_date"] = event_date
    if event_time: body["event_time"] = event_time
    if notes: body["notes"] = notes
    if dates: body["dates"] = dates
    if recurrence: body["recurrence"] = recurrence
    return api("POST", "/calendar-events", json=body)


@mcp.tool()
def delete_calendar_event(id: int) -> dict:
    """Delete a calendar event by ID."""
    return api("DELETE", f"/calendar-events/{id}")


# ── RECOMMENDED GROCERY ───────────────────────────────────────────────────────

@mcp.tool()
def generate_recommended_grocery(created_by: int, meal_calendar_ids: list) -> dict:
    """
    Generate grocery recommendations from scheduled meal entries.
    Call after upsert_meal_calendar with the returned meal_calendar_ids.
    After this, tell the user to open the app to review — do not list items in chat.
    """
    return api("POST", "/recommended-grocery/generate", json={
        "created_by": created_by,
        "meal_calendar_ids": meal_calendar_ids,
    })


@mcp.tool()
def get_recommended_grocery(from_date: str = "", to_date: str = "") -> list:
    """Get pending grocery recommendations (not yet promoted or rejected)."""
    params = {}
    if from_date: params["from"] = from_date
    if to_date: params["to"] = to_date
    return api("GET", "/recommended-grocery", params=params)


@mcp.tool()
def add_recommended_grocery(
    item_name: str,
    quantity: float,
    unit: str,
    created_by: int = 3,
    item_id: int | None = None,
) -> dict:
    """Manually add an item to the recommended grocery list (no meal link)."""
    return api("POST", "/recommended-grocery", json={
        "created_by": created_by,
        "item_id": item_id,
        "item_name": item_name,
        "quantity": quantity,
        "unit": unit,
    })


@mcp.tool()
def promote_recommended_grocery(item_ids: list, created_by: int = 3) -> dict:
    """Promote recommended items to the active grocery list."""
    return api("POST", "/recommended-grocery/promote", json={
        "created_by": created_by,
        "item_ids": item_ids,
    })


@mcp.tool()
def reject_recommended_grocery(item_ids: list) -> dict:
    """Reject recommended items — already have them."""
    return api("POST", "/recommended-grocery/reject", json={"item_ids": item_ids})


# ── GROCERY LIST ──────────────────────────────────────────────────────────────

@mcp.tool()
def get_grocery_list() -> list:
    """Get the active shopping list (items not yet bought or removed)."""
    return api("GET", "/grocery-list")


@mcp.tool()
def add_grocery_list_item(
    item_name: str,
    quantity: float,
    unit: str,
    created_by: int = 3,
    item_id: int | None = None,
) -> dict:
    """
    Add an item directly to the grocery list — skips recommended stage.
    Use for non-recipe items like toilet paper, household goods.
    """
    return api("POST", "/grocery-list", json={
        "created_by": created_by,
        "item_id": item_id,
        "item_name": item_name,
        "quantity": quantity,
        "unit": unit,
    })


@mcp.tool()
def mark_grocery_bought(ids: list) -> dict:
    """Mark grocery list items as purchased. Pass list of row IDs."""
    return api("POST", "/grocery-list/bought", json={"ids": ids})


@mcp.tool()
def remove_grocery_list_item(ids: list) -> dict:
    """Remove items from grocery list (found in pantry / changed mind). Pass list of row IDs."""
    return api("POST", "/grocery-list/remove", json={"ids": ids})


# ── RECEIPTS ──────────────────────────────────────────────────────────────────

@mcp.tool()
def upload_receipt(image_base64: str, created_by: int = 3, media_type: str = "image/jpeg") -> dict:
    """
    Upload a receipt photo. Returns receipt_id.
    Then parse the image, call update_receipt with metadata, then confirm_receipt.
    """
    return api("POST", "/receipts", json={
        "image_base64": image_base64,
        "created_by": created_by,
        "media_type": media_type,
    })


@mcp.tool()
def update_receipt(
    id: int,
    store_name: str | None = None,
    purchased_at: str | None = None,
    total_amount: float | None = None,
) -> dict:
    """Update receipt metadata after parsing the image."""
    body = {}
    if store_name is not None: body["store_name"] = store_name
    if purchased_at is not None: body["purchased_at"] = purchased_at
    if total_amount is not None: body["total_amount"] = total_amount
    return api("PATCH", f"/receipts/{id}", json=body)


@mcp.tool()
def confirm_receipt(id: int) -> dict:
    """Mark receipt as parsed and confirmed."""
    return api("POST", f"/receipts/{id}/confirm")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    mcp.run(
        transport="sse",
        host="0.0.0.0",
        port=port,
    )
