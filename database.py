import os
from datetime import datetime

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError(
        "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env"
    )

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def create_user(name, age, weight_kg, height_cm, goal, telegram_id, budget_weekly):
    payload = {
        "name": name,
        "age": age,
        "weight_kg": weight_kg,
        "height_cm": height_cm,
        "goal": goal,
        "telegram_id": telegram_id,
        "budget_weekly": budget_weekly,
    }

    try:
        result = supabase.table("users").insert(payload).select("*").execute()
        return result.data[0] if result.data else {}
    except Exception as exc:
        print(f"⚠️ Error creating user: {exc}")
        return {}


def get_user(user_id):
    try:
        result = supabase.table("users").select("*").eq("id", user_id).single().execute()
        return result.data or {}
    except Exception as exc:
        print(f"⚠️ Error fetching user {user_id}: {exc}")
        return {}


def add_family_member(user_id, name, age, dietary_type, allergies, preferences):
    payload = {
        "user_id": user_id,
        "name": name,
        "age": age,
        "dietary_type": dietary_type,
        "allergies": allergies or [],
        "preferences": preferences or [],
    }

    try:
        result = supabase.table("family_members").insert(payload).select("*").execute()
        return result.data[0] if result.data else {}
    except Exception as exc:
        print(f"⚠️ Error adding family member: {exc}")
        return {}


def get_family_members(user_id):
    try:
        result = supabase.table("family_members").select("*").eq("user_id", user_id).execute()
        return result.data or []
    except Exception as exc:
        print(f"⚠️ Error fetching family members: {exc}")
        return []


def save_meal_plan(user_id, goal, week_start):
    payload = {
        "user_id": user_id,
        "week_start": week_start,
        "goal": goal,
        "status": "pending",
        "approved_at": None,
    }

    try:
        result = supabase.table("meal_plans").insert(payload).select("*").execute()
        return result.data[0] if result.data else {}
    except Exception as exc:
        print(f"⚠️ Error saving meal plan: {exc}")
        return {}


def save_day_meals(plan_id, days):
    if not isinstance(days, list):
        return []

    payload = []
    for day in days:
        payload.append({
            "plan_id": plan_id,
            "day_name": day.get("day_name") or day.get("day") or "",
            "breakfast": day.get("breakfast", ""),
            "breakfast_calories": day.get("breakfast_calories", 0),
            "breakfast_protein": day.get("breakfast_protein", 0),
            "lunch": day.get("lunch", ""),
            "lunch_calories": day.get("lunch_calories", 0),
            "lunch_protein": day.get("lunch_protein", 0),
            "dinner": day.get("dinner", ""),
            "dinner_calories": day.get("dinner_calories", 0),
            "dinner_protein": day.get("dinner_protein", 0),
            "total_calories": day.get("total_calories", 0),
            "total_protein": day.get("total_protein", 0),
        })

    try:
        result = supabase.table("day_meals").insert(payload).select("*").execute()
        return result.data or []
    except Exception as exc:
        print(f"⚠️ Error saving day meals: {exc}")
        return []


def get_meal_plan(plan_id):
    try:
        result = (
            supabase.table("meal_plans")
            .select("*, day_meals(*)")
            .eq("id", plan_id)
            .single()
            .execute()
        )
        return result.data or {}
    except Exception as exc:
        print(f"⚠️ Error fetching meal plan: {exc}")
        return {}


def save_grocery_list(plan_id, items, estimated_cost):
    payload = {
        "plan_id": plan_id,
        "items": items or [],
        "estimated_cost": estimated_cost,
    }

    try:
        result = supabase.table("grocery_lists").insert(payload).select("*").execute()
        return result.data[0] if result.data else {}
    except Exception as exc:
        print(f"⚠️ Error saving grocery list: {exc}")
        return {}


def get_grocery_list(plan_id):
    try:
        result = (
            supabase.table("grocery_lists")
            .select("*")
            .eq("plan_id", plan_id)
            .execute()
        )
        grocery_lists = result.data or []
        return grocery_lists[0] if grocery_lists else {}
    except Exception as exc:
        print(f"⚠️ Error fetching grocery list: {exc}")
        return {}


def save_feedback(plan_id, member_name, rating, comment, regenerate_flag):
    payload = {
        "plan_id": plan_id,
        "member_name": member_name,
        "rating": rating,
        "comment": comment,
        "regenerate_flag": regenerate_flag,
    }

    try:
        result = supabase.table("feedback").insert(payload).select("*").execute()
        return result.data[0] if result.data else {}
    except Exception as exc:
        print(f"⚠️ Error saving feedback: {exc}")
        return {}


def get_latest_plan(user_id):
    try:
        result = (
            supabase.table("meal_plans")
            .select("*, day_meals(*)")
            .eq("user_id", user_id)
            .order("week_start", desc=True)
            .limit(1)
            .execute()
        )
        plans = result.data or []
        return plans[0] if plans else {}
    except Exception as exc:
        print(f"⚠️ Error fetching latest plan: {exc}")
        return {}


def update_plan_status(plan_id, status):
    update_data = {"status": status}

    if status == "approved":
        update_data["approved_at"] = datetime.utcnow().isoformat()

    try:
        result = (
            supabase.table("meal_plans")
            .update(update_data)
            .eq("id", plan_id)
            .select("*")
            .execute()
        )
        return result.data[0] if result.data else {}
    except Exception as exc:
        print(f"⚠️ Error updating plan status: {exc}")
        return {}


def get_user_history(user_id):
    try:
        result = (
            supabase.table("meal_plans")
            .select("*, day_meals(*)")
            .eq("user_id", user_id)
            .order("week_start", desc=True)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        print(f"⚠️ Error fetching user history for {user_id}: {exc}")
        return []