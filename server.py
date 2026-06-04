"""
CoupleHub MCP Server — v2
"""

import os
import httpx
from typing import Optional
from fastmcp import FastMCP
from pydantic import BaseModel, Field
from mcp.types import ToolAnnotations

API_BASE = "https://host740041.xce.pl/CoupleHub_DEV/api"
mcp = FastMCP("CoupleHub")

# Annotation presets
READ       = ToolAnnotations(readOnlyHint=True, openWorldHint=True)
WRITE      = ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True)
DESTRUCTIVE = ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=True)


def api(method: str, path: str, **kwargs):
    with httpx.Client(timeout=15) as client:
        r = client.request(method, f"{API_BASE}{path}", **kwargs)
        r.raise_for_status()
        return r.json()


# ── Pydantic models ───────────────────────────────────────────────────────────

class Ingredient(BaseModel):
    item_name: str = Field(description="Name of the ingredient")
    quantity: float = Field(description="Amount per 1 serving")
    unit: str = Field(description="Unit e.g. g, ml, tbsp")
    item_id: Optional[int] = Field(default=None, description="item_lu ID if known — call get_items to find it")
    category: Optional[str] = Field(default=None, description="produce|meat|dairy|pantry|bakery|frozen|drinks|household|other")
    default_unit: Optional[str] = Field(default=None, description="Default unit for this item in item_lu")
    notes: Optional[str] = Field(default=None, description="Optional prep note e.g. diced")


class MealEntry(BaseModel):
    meal_type: str = Field(description="lunch or dinner")
    recipe_id: Optional[int] = Field(default=None, description="Recipe ID from get_recipes. Null if eating out.")
    servings: int = Field(default=2, description="Default 2. Use 1 if one person not eating.")
    is_eating_out: bool = Field(default=False, description="True if eating out. Set recipe_id to null.")
    eating_out_note: Optional[str] = Field(default=None, description="Restaurant or event name when eating out")
    entry_date: Optional[str] = Field(default=None, description="Single date YYYY-MM-DD")
    dates: Optional[list[str]] = Field(default=None, description="Multiple dates as YYYY-MM-DD strings")
    recurrence: Optional[dict] = Field(default=None, description="e.g. {type: weekly, day: Tuesday, from: YYYY-MM-DD, to: YYYY-MM-DD}")


# ── RECIPES ───────────────────────────────────────────────────────────────────

@mcp.tool(annotations=READ)
def get_recipes(search: str = "", is_side: Optional[int] = None) -> list:
    """
    MEAL PLANNING STEP 2. Call once with no filters to get all recipes,
    then semantically match user meal names against results.
    'spag bol' matches 'Spaghetti Bolognese'. Never assume a recipe
    does not exist without calling this first. is_side: 0=mains, 1=sides.
    """
    params = {}
    if search: params["search"] = search
    if is_side is not None: params["is_side"] = is_side
    return api("GET", "/recipes", params=params)


@mcp.tool(annotations=READ)
def get_recipe(id: int) -> dict:
    """Get full recipe with ingredients, instructions, ratings."""
    return api("GET", f"/recipes/{id}")


@mcp.tool(annotations=WRITE)
def create_recipe(
    name: str,
    instructions: str,
    ingredients: list[Ingredient],
    prep_time_mins: Optional[int] = None,
    cook_time_mins: Optional[int] = None,
    is_side: bool = False,
    source_url: Optional[str] = None,
    suggested_sides: Optional[list[str]] = None,
) -> dict:
    """
    MEAL PLANNING STEP 3 — only call after explicit user approval.
    Before calling: call get_items ONCE with no filter to get full catalogue,
    then resolve all ingredients locally in one pass — never search per ingredient.
    All quantities per 1 serving. suggested_sides: list of recipe name strings.
    Never save without user confirmation.
    """
    return api("POST", "/recipes", json={
        "name": name,
        "instructions": instructions,
        "ingredients": [i.model_dump(exclude_none=True) for i in ingredients],
        "prep_time_mins": prep_time_mins,
        "cook_time_mins": cook_time_mins,
        "is_side": is_side,
        "source_url": source_url,
        "suggested_sides": suggested_sides or [],
    })


@mcp.tool(annotations=WRITE)
def update_recipe(
    id: int,
    name: Optional[str] = None,
    instructions: Optional[str] = None,
    ingredients: Optional[list[Ingredient]] = None,
    prep_time_mins: Optional[int] = None,
    cook_time_mins: Optional[int] = None,
    is_side: Optional[bool] = None,
    source_url: Optional[str] = None,
    suggested_sides: Optional[list[str]] = None,
) -> dict:
    """
    Update an existing recipe. Only include fields that need changing.
    If ingredients provided, the full list is replaced — confirm with user first.
    """
    body = {}
    if name is not None: body["name"] = name
    if instructions is not None: body["instructions"] = instructions
    if ingredients is not None: body["ingredients"] = [i.model_dump(exclude_none=True) for i in ingredients]
    if prep_time_mins is not None: body["prep_time_mins"] = prep_time_mins
    if cook_time_mins is not None: body["cook_time_mins"] = cook_time_mins
    if is_side is not None: body["is_side"] = is_side
    if source_url is not None: body["source_url"] = source_url
    if suggested_sides is not None: body["suggested_sides"] = suggested_sides
    return api("PATCH", f"/recipes/{id}", json=body)


@mcp.tool(annotations=DESTRUCTIVE)
def delete_recipe(id: int) -> dict:
    """Delete a recipe permanently. Confirm with user before calling."""
    return api("DELETE", f"/recipes/{id}")


@mcp.tool(annotations=WRITE)
def rate_recipe(recipe_id: int, user_id: int, rating: int, notes: str = "") -> dict:
    """
    Rate a recipe 1-5. Call when user says 'that was a 4/5' or similar.
    user_id: 1=Jakub, 2=Erica — identify from conversation context.
    """
    return api("POST", f"/recipes/{recipe_id}/ratings", json={
        "user_id": user_id, "rating": rating, "notes": notes or None,
    })


# ── ITEM CATALOGUE ────────────────────────────────────────────────────────────

@mcp.tool(annotations=READ)
def get_items(search: str = "", category: str = "") -> list:
    """
    Fetch item catalogue. Call ONCE with no filters to get the full list,
    then match ingredients locally — never call per ingredient in a loop.
    If item found in results: use its item_id and default_unit.
    If not found: include category+default_unit in the ingredient so
    item_lu auto-creates on recipe save. No second API call needed.
    Categories: produce|meat|dairy|pantry|bakery|frozen|drinks|household|other.
    """
    params = {}
    if search: params["search"] = search
    if category: params["category"] = category
    return api("GET", "/items", params=params)


@mcp.tool(annotations=WRITE)
def create_item(name: str, category: str, default_unit: str) -> dict:
    """
    Add item to catalogue. Usually not needed directly — items auto-create
    when saving recipes with category+default_unit set on ingredients.
    Use for standalone household items not linked to any recipe.
    """
    return api("POST", "/items", json={"name": name, "category": category, "default_unit": default_unit})


# ── MEAL CALENDAR ─────────────────────────────────────────────────────────────

@mcp.tool(annotations=READ)
def get_meal_calendar(from_date: str = "", to_date: str = "") -> dict:
    """
    Get meal entries and calendar events for a date range (YYYY-MM-DD).
    Defaults to current week. Call when user asks 'what's on this week'
    or before making changes to find entry IDs.
    """
    params = {}
    if from_date: params["from"] = from_date
    if to_date: params["to"] = to_date
    return api("GET", "/meal-calendar", params=params)


@mcp.tool(annotations=WRITE)
def upsert_meal_calendar(created_by: int, entries: list[MealEntry]) -> dict:
    """
    MEAL PLANNING STEP 4. Schedule meals in a SINGLE call with all entries
    batched — never loop one by one. created_by: 1=Jakub, 2=Erica.
    Each entry: entry_date (single), dates[] (multi), or recurrence{}.
    Recurrence: {type: weekly|weekdays|range, day?: Monday..Sunday,
    from: YYYY-MM-DD, to: YYYY-MM-DD}.
    After this succeeds, IMMEDIATELY call generate_recommended_grocery
    with the returned meal_calendar_ids.
    """
    return api("POST", "/meal-calendar", json={
        "created_by": created_by,
        "entries": [e.model_dump(exclude_none=True) for e in entries],
    })


@mcp.tool(annotations=WRITE)
def update_meal_calendar_entry(
    id: int,
    recipe_id: Optional[int] = None,
    servings: Optional[int] = None,
    is_eating_out: Optional[bool] = None,
    eating_out_note: Optional[str] = None,
) -> dict:
    """
    Update a single meal entry. Get entry id from get_meal_calendar first.
    Automatically cleans unactioned grocery rows when recipe or eating_out changes.
    """
    body = {}
    if recipe_id is not None: body["recipe_id"] = recipe_id
    if servings is not None: body["servings"] = servings
    if is_eating_out is not None: body["is_eating_out"] = is_eating_out
    if eating_out_note is not None: body["eating_out_note"] = eating_out_note
    return api("PATCH", f"/meal-calendar/{id}", json=body)


@mcp.tool(annotations=DESTRUCTIVE)
def delete_meal_calendar_entry(id: int) -> dict:
    """
    Delete a meal entry. Auto-cleans unactioned grocery rows.
    Get entry id from get_meal_calendar first.
    """
    return api("DELETE", f"/meal-calendar/{id}")


# ── CALENDAR EVENTS ───────────────────────────────────────────────────────────

@mcp.tool(annotations=READ)
def get_calendar_events(from_date: str = "", to_date: str = "") -> list:
    """List calendar events by date range. Call before creating to avoid duplicates."""
    params = {}
    if from_date: params["from"] = from_date
    if to_date: params["to"] = to_date
    return api("GET", "/calendar-events", params=params)


@mcp.tool(annotations=WRITE)
def create_calendar_event(
    created_by: int,
    title: str,
    event_date: Optional[str] = None,
    event_time: Optional[str] = None,
    notes: Optional[str] = None,
    dates: Optional[list[str]] = None,
    recurrence_type: Optional[str] = None,
    recurrence_day: Optional[str] = None,
    recurrence_from: Optional[str] = None,
    recurrence_to: Optional[str] = None,
) -> dict:
    """
    Create calendar event(s). created_by MANDATORY: 1=Jakub, 2=Erica.
    Always identify the speaker — this drives whose name shows on the UI.
    Single event: event_date (YYYY-MM-DD).
    Multiple dates: dates[] list.
    Recurring (e.g. 'gym every Tuesday for Jakub'):
      recurrence_type=weekly, recurrence_day=Tuesday,
      recurrence_from=YYYY-MM-DD, recurrence_to=YYYY-MM-DD.
    Types: weekly (needs recurrence_day), weekdays, range.
    Never loop — always use recurrence for repeating events.
    event_time: HH:MM 24hr format.
    """
    body = {"created_by": created_by, "title": title}
    if event_date: body["event_date"] = event_date
    if event_time: body["event_time"] = event_time
    if notes: body["notes"] = notes
    if dates: body["dates"] = dates
    if recurrence_type:
        body["recurrence"] = {"type": recurrence_type}
        if recurrence_day: body["recurrence"]["day"] = recurrence_day
        if recurrence_from: body["recurrence"]["from"] = recurrence_from
        if recurrence_to: body["recurrence"]["to"] = recurrence_to
    return api("POST", "/calendar-events", json=body)


@mcp.tool(annotations=WRITE)
def delete_calendar_event(id: int) -> dict:
    """Delete a calendar event. Get id from get_calendar_events first."""
    return api("DELETE", f"/calendar-events/{id}")


# ── RECOMMENDED GROCERY ───────────────────────────────────────────────────────

@mcp.tool(annotations=WRITE)
def generate_recommended_grocery(created_by: int, meal_calendar_ids: list[int]) -> dict:
    """
    MEAL PLANNING STEP 5. Call immediately after upsert_meal_calendar
    using the meal_calendar_ids from that response.
    After success tell user: 'Open the app to review your grocery list.'
    Never list grocery items in chat — the app handles review and promotion.
    created_by: 1=Jakub, 2=Erica.
    """
    return api("POST", "/recommended-grocery/generate", json={
        "created_by": created_by,
        "meal_calendar_ids": meal_calendar_ids,
    })


@mcp.tool(annotations=READ)
def get_recommended_grocery(from_date: str = "", to_date: str = "") -> list:
    """Get pending grocery recommendations not yet promoted or rejected."""
    params = {}
    if from_date: params["from"] = from_date
    if to_date: params["to"] = to_date
    return api("GET", "/recommended-grocery", params=params)


@mcp.tool(annotations=WRITE)
def add_recommended_grocery(
    item_name: str,
    quantity: float,
    unit: str,
    created_by: int = 3,
    item_id: Optional[int] = None,
) -> dict:
    """Manually add an item to recommended list with no meal link."""
    return api("POST", "/recommended-grocery", json={
        "created_by": created_by, "item_id": item_id,
        "item_name": item_name, "quantity": quantity, "unit": unit,
    })


@mcp.tool(annotations=WRITE)
def promote_recommended_grocery(item_ids: list[int], created_by: int = 3) -> dict:
    """
    Move recommended items to active grocery list.
    item_ids: list of item_lu IDs (not row IDs).
    All pending rows for those items promoted in one operation.
    """
    return api("POST", "/recommended-grocery/promote", json={
        "created_by": created_by, "item_ids": item_ids,
    })


@mcp.tool(annotations=WRITE)
def reject_recommended_grocery(item_ids: list[int]) -> dict:
    """
    Reject recommended items — already have them.
    item_ids: list of item_lu IDs. Call when user says 'we have X already'.
    """
    return api("POST", "/recommended-grocery/reject", json={"item_ids": item_ids})


# ── GROCERY LIST ──────────────────────────────────────────────────────────────

@mcp.tool(annotations=READ)
def get_grocery_list() -> list:
    """Get active shopping list. Call when user asks what's on the list."""
    return api("GET", "/grocery-list")


@mcp.tool(annotations=WRITE)
def add_grocery_list_item(
    item_name: str,
    quantity: float,
    unit: str,
    created_by: int = 3,
    item_id: Optional[int] = None,
    is_urgent: int = 0,
) -> dict:
    """
    Add item directly to grocery list — skips recommended stage.
    Use for non-recipe items: toilet paper, household goods, anything
    the user says to add to the shopping list not from a recipe.
    is_urgent=1 triggers an EMERGENCY GROCERY card on today's calendar.
    Set is_urgent=1 when user says: 'urgently', 'running out', 'need today',
    'need tomorrow', 'emergency', 'ASAP'.
    """
    return api("POST", "/grocery-list", json={
        "created_by": created_by, "item_id": item_id,
        "item_name": item_name, "quantity": quantity, "unit": unit,
        "is_urgent": is_urgent,
    })


@mcp.tool(annotations=WRITE)
def mark_grocery_bought(ids: list[int]) -> dict:
    """
    Mark grocery list rows as purchased.
    ids: grocery_list row IDs (not item_lu IDs) from get_grocery_list.
    """
    return api("POST", "/grocery-list/bought", json={"ids": ids})


@mcp.tool(annotations=WRITE)
def remove_grocery_list_item(ids: list[int]) -> dict:
    """
    Remove items from grocery list — found in pantry or changed mind.
    ids: grocery_list row IDs from get_grocery_list.
    """
    return api("POST", "/grocery-list/remove", json={"ids": ids})


# ── RECEIPTS ──────────────────────────────────────────────────────────────────

@mcp.tool(annotations=WRITE)
def upload_receipt(image_base64: str, created_by: int = 3, media_type: str = "image/jpeg") -> dict:
    """
    RECEIPT STEP 1. Upload photo as base64. Returns receipt_id.
    Next: parse image in chat, call update_receipt with metadata,
    confirm with user, then call confirm_receipt.
    """
    return api("POST", "/receipts", json={
        "image_base64": image_base64, "created_by": created_by, "media_type": media_type,
    })


@mcp.tool(annotations=WRITE)
def update_receipt(
    id: int,
    store_name: Optional[str] = None,
    purchased_at: Optional[str] = None,
    total_amount: Optional[float] = None,
) -> dict:
    """
    RECEIPT STEP 2. Update metadata after parsing photo.
    purchased_at: YYYY-MM-DD HH:MM:SS. Only include parsed fields.
    """
    body = {}
    if store_name is not None: body["store_name"] = store_name
    if purchased_at is not None: body["purchased_at"] = purchased_at
    if total_amount is not None: body["total_amount"] = total_amount
    return api("PATCH", f"/receipts/{id}", json=body)


@mcp.tool(annotations=WRITE)
def confirm_receipt(id: int) -> dict:
    """RECEIPT STEP 3. Mark receipt confirmed. Only after user approves parsed details."""
    return api("POST", f"/receipts/{id}/confirm")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    mcp.run(transport="sse", host="0.0.0.0", port=port)
