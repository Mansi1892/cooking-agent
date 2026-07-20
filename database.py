import os
from datetime import datetime

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

FREE_PLAN_CREDITS = 3
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError(
        "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env"
    )

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def create_user(name, age, weight_kg, height_cm, goal, telegram_id, budget_weekly, dietary_type=None, dietary_preferences=None, allergies=None, preferences=None, email=None):
    payload = {
        "name": name,
        "email": (email or "").strip().lower(),
        "age": age,
        "weight_kg": weight_kg,
        "height_cm": height_cm,
        "goal": goal,
        "telegram_id": telegram_id,
        "budget_weekly": budget_weekly,
        "credits": FREE_PLAN_CREDITS,
        "role": "user",
    }

    if dietary_type:
        payload["dietary_type"] = dietary_type
    if dietary_preferences:
        payload["dietary_preferences"] = dietary_preferences
    if allergies:
        payload["allergies"] = allergies
    if preferences:
        payload["preferences"] = preferences

    try:
        result = supabase.table("users").insert(payload).select("*").execute()
        user_record = result.data[0] if result.data else {}
        if dietary_type and "dietary_type" not in user_record:
            user_record["dietary_type"] = dietary_type
        if dietary_preferences and "dietary_preferences" not in user_record:
            user_record["dietary_preferences"] = dietary_preferences
        if allergies and "allergies" not in user_record:
            user_record["allergies"] = allergies
        if preferences and "preferences" not in user_record:
            user_record["preferences"] = preferences
        return user_record
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


def get_user_by_email(email):
    clean_email = (email or "").strip().lower()
    if not clean_email:
        return {}
    try:
        result = (
            supabase.table("users")
            .select("*")
            .eq("email", clean_email)
            .order("id", desc=True)
            .limit(1)
            .execute()
        )
        users = result.data or []
        return users[0] if users else {}
    except Exception as exc:
        print(f"⚠️ Error fetching user with email {clean_email}: {exc}")
        return {}


def get_user_by_telegram_id(telegram_id):
    try:
        result = (
            supabase.table("users")
            .select("*")
            .eq("telegram_id", str(telegram_id))
            .single()
            .execute()
        )
        return result.data or {}
    except Exception as exc:
        print(f"⚠️ Error fetching user with Telegram ID {telegram_id}: {exc}")
        return {}


def update_user(user_id, updates):
    allowed = {
        "name",
        "email",
        "age",
        "weight_kg",
        "height_cm",
        "goal",
        "telegram_id",
        "budget_weekly",
        "dietary_type",
        "dietary_preferences",
        "allergies",
        "preferences",
        "credits",
        "role",
    }
    payload = {key: value for key, value in (updates or {}).items() if key in allowed}
    if not payload:
        return get_user(user_id)
    try:
        result = (
            supabase.table("users")
            .update(payload)
            .eq("id", user_id)
            .select("*")
            .execute()
        )
        return result.data[0] if result.data else {}
    except Exception as exc:
        print(f"⚠️ Error updating user {user_id}: {exc}")
        return {}


def get_user_credits(user):
    try:
        return int(user.get("credits", FREE_PLAN_CREDITS))
    except (TypeError, ValueError):
        return FREE_PLAN_CREDITS


def consume_user_credit(user_id):
    user = get_user(user_id)
    credits = get_user_credits(user)
    if credits <= 0:
        return {"ok": False, "credits": credits, "error": "No meal plan credits remaining."}

    try:
        result = (
            supabase.table("users")
            .update({"credits": credits - 1})
            .eq("id", user_id)
            .select("*")
            .execute()
        )
        updated = result.data[0] if result.data else {}
        return {"ok": True, "credits": get_user_credits(updated)}
    except Exception as exc:
        print(f"⚠️ Error consuming credit for user {user_id}: {exc}")
        return {"ok": False, "credits": credits, "error": "Credits column is not configured in Supabase."}


def add_user_credits(user_id, amount):
    user = get_user(user_id)
    if not user:
        return {}
    credits = get_user_credits(user)
    try:
        result = (
            supabase.table("users")
            .update({"credits": credits + int(amount)})
            .eq("id", user_id)
            .select("*")
            .execute()
        )
        return result.data[0] if result.data else {}
    except Exception as exc:
        print(f"⚠️ Error adding credits for user {user_id}: {exc}")
        return {}


def create_credit_request(user_id, requested_credits=3, note=""):
    user = get_user(user_id)
    if not user:
        return {}
    try:
        existing = (
            supabase.table("credit_requests")
            .select("*")
            .eq("user_id", user_id)
            .eq("status", "pending")
            .limit(1)
            .execute()
        )
        if existing.data:
            return existing.data[0]
        payload = {
            "user_id": user_id,
            "requested_credits": int(requested_credits or 3),
            "status": "pending",
            "note": note or "",
        }
        result = supabase.table("credit_requests").insert(payload).select("*").execute()
        return result.data[0] if result.data else {}
    except Exception as exc:
        print(f"⚠️ Error creating credit request for user {user_id}: {exc}")
        return {}


def list_credit_requests(status="pending"):
    try:
        query = supabase.table("credit_requests").select("*, users(id,name,email,credits,role)").order("id", desc=True)
        if status:
            query = query.eq("status", status)
        result = query.execute()
        return result.data or []
    except Exception as exc:
        print(f"⚠️ Error listing credit requests: {exc}")
        return []


def update_credit_request(request_id, updates):
    try:
        result = (
            supabase.table("credit_requests")
            .update(updates or {})
            .eq("id", request_id)
            .select("*")
            .execute()
        )
        return result.data[0] if result.data else {}
    except Exception as exc:
        print(f"⚠️ Error updating credit request {request_id}: {exc}")
        return {}


def list_users():
    try:
        result = (
            supabase.table("users")
            .select("id,name,goal,telegram_id,budget_weekly,credits,role,created_at")
            .order("id", desc=True)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        print(f"⚠️ Error listing users: {exc}")
        return []


def add_family_member(user_id, name, age, dietary_type, allergies, preferences, telegram=""):
    payload = {
        "user_id": user_id,
        "name": name,
        "age": age,
        "dietary_type": dietary_type,
        "allergies": allergies or [],
        "preferences": preferences or [],
    }

    if telegram:
        payload["telegram"] = telegram

    try:
        result = supabase.table("family_members").insert(payload).select("*").execute()
        return result.data[0] if result.data else {}
    except Exception as exc:
        print(f"⚠️ Error adding family member: {exc}")
        fallback_payload = {k: v for k, v in payload.items() if k != "telegram"}
        try:
            result = supabase.table("family_members").insert(fallback_payload).select("*").execute()
            return result.data[0] if result.data else {}
        except Exception as exc2:
            print(f"⚠️ Error adding family member fallback: {exc2}")
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
            .order("id", desc=True)
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
            .order("id", desc=True)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        print(f"⚠️ Error fetching user history for {user_id}: {exc}")
        return []
