import os
from dotenv import load_dotenv
from langchain.tools import tool
from openai import OpenAI
from supabase import create_client
from config import GOAL_TARGETS, DAYS_OF_WEEK
import database as db
import requests

load_dotenv()

# --- clients ---
openai_client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
    default_headers={
        "HTTP-Referer": "https://meal-planner-ai.com",
        "X-Title": "Meal Planner AI"
    }
)

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")


# --- helper: get embedding ---
def get_embedding(text: str) -> list[float]:
    try:
        response = openai_client.embeddings.create(
            model="openai/text-embedding-3-small",
            input=str(text)
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"⚠️ Embedding error: {str(e)}")
        return []


# --- helper: tavily search ---
def tavily_search(query: str, max_results: int = 3) -> list[dict]:
    try:
        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": TAVILY_API_KEY,
                "query": query,
                "max_results": max_results,
                "search_depth": "basic"
            },
            timeout=10
        )
        response.raise_for_status()
        return response.json().get("results", [])
    except Exception as e:
        print(f"⚠️ Tavily error: {str(e)}")
        return []


# --- Tool 1: RAG recipe search ---
@tool
def search_recipes_db(query: str) -> str:
    """Search the local recipe database using semantic similarity.
    Use this first before searching the web.
    Input: a simple text string like 'vegetarian breakfast recipes'"""
    try:
        # handle if agent passes dict instead of string
        if isinstance(query, dict):
            query = query.get("query", "") or query.get("title", "") or str(query)

        if not query:
            return "Please provide a search query string."

        embedding = get_embedding(str(query))
        if not embedding:
            return "Could not generate embedding for recipe search."

        results = supabase.rpc("match_recipes", {
            "query_embedding": embedding,
            "match_count": 5
        }).execute()

        if not results.data:
            return "No recipes found in database for this query."

        formatted = []
        for r in results.data:
            formatted.append(
                f"Recipe: {r['name']}\n"
                f"Cuisine: {r.get('cuisine', 'N/A')}\n"
                f"Dietary: {r.get('dietary_type', 'N/A')}\n"
                f"Details: {r['content']}\n"
            )
        return "\n---\n".join(formatted)

    except Exception as e:
        return f"Database search error: {str(e)}"


# --- Tool 2: Web recipe search ---
@tool
def search_recipes_web(query: str) -> str:
    """Search the internet for recipes and nutrition info.
    Use this when database results are not enough.
    Input: a simple text string like 'healthy Indian dinner recipes'"""
    try:
        if isinstance(query, dict):
            query = query.get("query", "") or str(query)

        results = tavily_search(str(query) + " Indian recipe healthy")
        if not results:
            return "No web results found."

        formatted = []
        for r in results:
            formatted.append(
                f"Source: {r.get('url', 'N/A')}\n"
                f"Content: {r.get('content', 'N/A')}\n"
            )
        return "\n---\n".join(formatted)

    except Exception as e:
        return f"Web search error: {str(e)}"


# --- Tool 3: Profile analyzer ---
@tool
def analyze_profile(user_id: str) -> str:
    """Analyze user and family health profiles.
    Calculates BMR and daily calorie targets for each member.
    Input: user_id as a plain string like '5'"""
    try:
        if isinstance(user_id, dict):
            user_id = user_id.get("user_id", "") or str(user_id)

        user = db.get_user(int(str(user_id).strip()))
        if not user:
            return f"User {user_id} not found."

        members = db.get_family_members(int(str(user_id).strip()))
        summary = []
        summary.append(f"Profile summary for user ID {user_id}: {user['name']}")
        summary.append(f"Goal: {user['goal']}")
        summary.append(f"Weekly Budget: ₹{user.get('budget_weekly', 'N/A')}")
        summary.append("")

        all_members = [user] + (members or [])

        for m in all_members:
            age = m.get("age") or 30
            weight = m.get("weight_kg") or 65
            height = m.get("height_cm") or 165
            name = m.get("name", "Member")

            bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5
            tdee = round(bmr * 1.55)
            goal = user.get("goal", "maintenance")
            targets = GOAL_TARGETS.get(goal, GOAL_TARGETS["maintenance"])

            summary.append(f"{name}:")
            summary.append(f"  Age: {age}, Weight: {weight}kg, Height: {height}cm")
            summary.append(f"  BMR: {round(bmr)} kcal/day")
            summary.append(f"  TDEE: {tdee} kcal/day")
            summary.append(f"  Calorie target: {targets['min_calories']}-{targets['max_calories']} kcal/day")
            summary.append(f"  Protein target: {targets['min_protein']}-{targets['max_protein']}g/day")

            dietary = m.get("dietary_type") or "unspecified"
            allergies = m.get("allergies") or []
            preferences = m.get("preferences") or []

            summary.append(f"  Dietary type: {dietary}")
            summary.append(f"  Allergies: {', '.join(allergies) if allergies else 'None'}")
            summary.append(f"  Preferences: {', '.join(preferences) if preferences else 'None'}")
            summary.append("")

        return "\n".join(summary)

    except Exception as e:
        return f"Profile analysis error: {str(e)}"


# --- Tool 4: Nutrition info ---
@tool
def get_nutrition_info(query: str) -> str:
    """Get live nutrition information for any ingredient or meal.
    Input: ingredient or meal name as a plain string like 'paneer'"""
    try:
        if isinstance(query, dict):
            query = query.get("query", "") or str(query)

        results = tavily_search(
            f"nutrition facts {query} calories protein carbs fat per 100g"
        )
        if not results:
            return f"No nutrition info found for {query}."

        formatted = []
        for r in results[:3]:
            content = r.get("content", "")
            if content:
                formatted.append(content)
        return "\n".join(formatted) if formatted else f"No nutrition data found for {query}."

    except Exception as e:
        return f"Nutrition search error: {str(e)}"


# --- Tool 5: Grocery list generator ---
@tool
def generate_grocery_list(plan_details: str) -> str:
    """Generate a consolidated grocery shopping list from a meal plan.
    Input: meal plan as a plain text string"""
    try:
        if isinstance(plan_details, dict):
            plan_details = str(plan_details)

        prompt = f"""
        Based on this 7-day meal plan, generate a consolidated grocery list.

        Meal Plan:
        {plan_details}

        Return a grocery list grouped by:
        - Vegetables & Fruits
        - Proteins (meat, eggs, dal, paneer)
        - Grains & Staples (rice, atta, oats)
        - Dairy (milk, curd, butter)
        - Spices & Condiments
        - Others

        Include estimated quantity for a family of 4 for one week.
        Estimate total cost in Indian Rupees.
        """

        response = openai_client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content

    except Exception as e:
        return f"Grocery list error: {str(e)}"


# --- Tool 6: Telegram notification ---
@tool
def send_telegram_notification(input_str: str) -> str:
    """Send meal plan to user via Telegram for approval.
    Input format: 'telegram_id|||message'
    Example: '123456789|||Here is your meal plan...'"""
    try:
        if isinstance(input_str, dict):
            telegram_id = str(input_str.get("telegram_id", ""))
            message = str(input_str.get("message", ""))
        else:
            parts = str(input_str).split("|||")
            if len(parts) != 2:
                return "Invalid input. Use format: 'telegram_id|||message'"
            telegram_id = parts[0].strip()
            message = parts[1].strip()

        import asyncio
        from telegram import Bot

        async def send():
            bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
            await bot.send_message(
                chat_id=telegram_id,
                text=message,
                parse_mode="Markdown"
            )

        asyncio.run(send())
        return f"✅ Message sent to Telegram ID: {telegram_id}"

    except Exception as e:
        return f"Telegram error: {str(e)}"


# --- all tools ---
ALL_TOOLS = [
    search_recipes_db,
    search_recipes_web,
    analyze_profile,
    get_nutrition_info,
    generate_grocery_list,
    send_telegram_notification
]
