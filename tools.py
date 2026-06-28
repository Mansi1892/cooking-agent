import json
import re
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from langchain.tools import tool
from langchain_community.tools import TavilySearchResults
from openai import OpenAI
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

from config import (
    EMBEDDING_MODEL,
    GOAL_TARGETS,
    LLM_MODEL,
    OPENAI_API_KEY,
    TAVILY_API_KEY,
    TELEGRAM_BOT_TOKEN,
    DAYS_OF_WEEK,
)
from database import get_family_members, get_user, save_grocery_list, supabase

load_dotenv()

openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
telegram_bot = Bot(token=TELEGRAM_BOT_TOKEN) if TELEGRAM_BOT_TOKEN else None


def _clean_response_text(text: str) -> str:
    if not text:
        return ""
    cleaned = text.strip()
    if cleaned.startswith("```") and cleaned.endswith("```"):
        cleaned = cleaned.strip("`")
    return cleaned


def _format_recipe_results(items: List[Dict[str, Any]]) -> str:
    if not items:
        return "No matching recipes found."

    lines = []
    for idx, item in enumerate(items, start=1):
        name = item.get("name", "Unknown recipe")
        cuisine = item.get("cuisine", "Indian")
        diet = item.get("dietary_type", "General")
        tags = ", ".join(item.get("tags", []))
        description = item.get("content", "").replace("\n", " ").strip()
        lines.append(
            f"{idx}. {name} ({cuisine}, {diet})\n   Tags: {tags or 'none'}\n   {description[:180].strip()}"
        )
    return "\n\n".join(lines)


def _format_profile(member: Dict[str, Any], default_goal: str) -> str:
    name = member.get("name", "Member")
    age = member.get("age", 0)
    weight = member.get("weight_kg", 0)
    height = member.get("height_cm", 0)
    gender = member.get("gender", "male").lower()
    dietary_type = member.get("dietary_type", "unspecified")
    goal = member.get("goal", default_goal)

    if gender == "female":
        bmr = 10 * weight + 6.25 * height - 5 * age - 161
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age + 5

    tdee = round(bmr * 1.55)
    target = GOAL_TARGETS.get(goal, GOAL_TARGETS["maintenance"])

    return (
        f"{name}: age {age}, gender {gender}, diet {dietary_type}\n"
        f"  BMR: {int(bmr)} kcal/day\n"
        f"  TDEE (moderate activity): {tdee} kcal/day\n"
        f"  Goal: {goal} → calorie target {target['min_calories']}-{target['max_calories']} kcal, "
        f"protein target {target['min_protein']}-{target['max_protein']} g"
    )


def _parse_family_size(text: str) -> int:
    match = re.search(r"family\s+of\s+(\d+)", text, re.IGNORECASE)
    return int(match.group(1)) if match else 4


def _parse_plan_id(text: str) -> Optional[int]:
    match = re.search(r"plan[_ ]?id\s*[:=]\s*(\d+)", text, re.IGNORECASE)
    return int(match.group(1)) if match else None


def _extract_ingredients(meal_plan: str) -> Dict[str, List[str]]:
    prompt = (
        "Extract ingredients from the meal plan below. Return JSON with categories vegetables, proteins, grains, spices, dairy. "
        "Only return ingredient names, no quantities or instructions.\n\n"
        f"Meal plan:\n{meal_plan}"
    )

    if not openai_client:
        return {k: [] for k in ["vegetables", "proteins", "grains", "spices", "dairy"]}

    try:
        response = openai_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful ingredient extractor."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
        )
        raw = _clean_response_text(response.choices[0].message.content)
        data = json.loads(raw)
        return {
            "vegetables": data.get("vegetables", []),
            "proteins": data.get("proteins", []),
            "grains": data.get("grains", []),
            "spices": data.get("spices", []),
            "dairy": data.get("dairy", []),
        }
    except json.JSONDecodeError:
        categories = {k: [] for k in ["vegetables", "proteins", "grains", "spices", "dairy"]}
        for line in raw.splitlines():
            parts = line.split(":", 1)
            if len(parts) != 2:
                continue
            key = parts[0].strip().lower()
            if key in categories:
                categories[key] = [item.strip() for item in parts[1].split(",") if item.strip()]
        return categories
    except Exception as exc:
        print(f"⚠️ Error extracting ingredients: {exc}")
        return {k: [] for k in ["vegetables", "proteins", "grains", "spices", "dairy"]}


def _estimate_quantities(categories: Dict[str, List[str]], family_size: int) -> List[str]:
    estimates = []
    base = {
        "vegetables": "1.5 kg",
        "proteins": "1 kg",
        "grains": "1 kg",
        "spices": "150 g",
        "dairy": "1 liter",
    }
    multiplier = max(1.0, family_size / 4)

    for category, items in categories.items():
        if not items:
            continue
        qty = base.get(category, "1 unit")
        if qty.endswith("kg"):
            amount = float(qty.replace(" kg", "")) * multiplier
            qty_text = f"{amount:.1f} kg"
        elif qty.endswith("g"):
            amount = float(qty.replace(" g", "")) * multiplier
            qty_text = f"{int(amount)} g"
        elif qty.endswith("liter"):
            amount = float(qty.replace(" liter", "")) * multiplier
            qty_text = f"{amount:.1f} liter"
        else:
            qty_text = qty
        estimates.append(f"{category.title()}: {', '.join(sorted(set(items)))} ({qty_text})")
    return estimates


@tool
def search_recipes_db(query: str) -> str:
    """Search Supabase recipe embeddings for relevant Indian recipes."""
    if not openai_client:
        return "OpenAI client is not configured."

    try:
        embedding_response = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=query)
        embedding = embedding_response.data[0].embedding
    except Exception as exc:
        print(f"⚠️ Error generating embedding: {exc}")
        return "Could not generate embedding for recipe search."

    try:
        result = supabase.rpc("match_recipes", {"query_embedding": embedding, "match_count": 5}).execute()
        recipes = result.data or []
        return _format_recipe_results(recipes)
    except Exception as exc:
        print(f"⚠️ Error querying Supabase: {exc}")
        return "Could not search recipes in the database."


@tool
def search_recipes_web(query: str) -> str:
    """Search the web for Indian recipes and nutrition info."""
    try:
        tavily_tool = TavilySearchResults(max_results=5, search_depth="advanced")
        results = tavily_tool.run(f"Indian recipes and nutrition information for {query}")
        return _clean_response_text(results)
    except Exception as exc:
        print(f"⚠️ Error searching recipes on the web: {exc}")
        return "Could not fetch web recipe results at this time."


@tool
def analyze_profile(user_id: str) -> str:
    """Analyze a user profile and family members to estimate calorie targets."""
    user = get_user(user_id)
    if not user:
        return f"No user found for ID {user_id}."

    family = get_family_members(user_id)
    default_goal = user.get("goal", "maintenance")
    profiles = [user] + family
    lines = [f"Profile summary for user ID {user_id}: {user.get('name', 'Unknown')}\n"]

    for member in profiles:
        lines.append(_format_profile(member, default_goal))

    return "\n\n".join(lines)


@tool
def get_nutrition_info(item: str) -> str:
    """Fetch nutrition facts for an ingredient or meal from the web."""
    try:
        tavily_tool = TavilySearchResults(max_results=3, search_depth="advanced")
        results = tavily_tool.run(f"Nutrition facts for {item}: calories, protein, carbs, fat")
        return _clean_response_text(results)
    except Exception as exc:
        print(f"⚠️ Error fetching nutrition info: {exc}")
        return "Could not fetch nutrition information at this time."


@tool
def generate_grocery_list(meal_plan: str) -> str:
    """Generate a grocery list from a meal plan and save it to Supabase."""
    categories = _extract_ingredients(meal_plan)
    family_size = _parse_family_size(meal_plan)
    plan_id = _parse_plan_id(meal_plan)

    shopping_list = _estimate_quantities(categories, family_size)
    if not shopping_list:
        return "No ingredients could be extracted from the meal plan."

    cost = round(60 * family_size * max(1, len(shopping_list)) / 10, 2)
    saved = save_grocery_list(plan_id, shopping_list, cost)
    status = "saved successfully" if saved else "failed to save"

    return "\n".join([
        "Grocery list:",
        *shopping_list,
        f"Plan ID: {plan_id or 'unknown'}",
        f"Estimated cost: ₹{cost}",
        f"Save status: {status}",
    ])


@tool
def send_telegram_notification(message: str, telegram_id: str) -> str:
    """Send a Telegram notification with approve and reject buttons."""
    if not telegram_bot:
        return f"Telegram bot is not configured for {telegram_id}."

    try:
        keyboard = [
            [InlineKeyboardButton("Approve", callback_data="approve")],
            [InlineKeyboardButton("Reject", callback_data="reject")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        telegram_bot.send_message(chat_id=int(telegram_id), text=message, reply_markup=reply_markup)
        return f"Telegram notification sent to {telegram_id}."
    except Exception as exc:
        print(f"⚠️ Error sending Telegram notification: {exc}")
        return f"Failed to send Telegram notification to {telegram_id}."


ALL_TOOLS = [
    search_recipes_db,
    search_recipes_web,
    analyze_profile,
    get_nutrition_info,
    generate_grocery_list,
    send_telegram_notification,
]

__all__ = ["ALL_TOOLS"] + [tool_item.name for tool_item in ALL_TOOLS]
