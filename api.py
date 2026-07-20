import os
from datetime import date, datetime, timedelta
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
import uvicorn

from database import (
    create_user,
    get_user,
    add_family_member,
    get_latest_plan,
    save_feedback,
    get_user_history,
    update_user,
    get_user_credits,
    consume_user_credit,
    add_user_credits,
    list_users,
)
from agent import generate_meal_plan
from tools import openai_client, tavily_search
from onboarding_utils import normalize_dietary_type, normalize_family_member

app = FastAPI(title="Smart Meal AI API")
GENERATING_USERS = set()
TELEGRAM_SENT_PLAN_IDS = set()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Pydantic Models ---

class UserProfile(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    weight: Optional[float] = None
    height: Optional[float] = None
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    goal: Optional[str] = "maintenance"
    weekly_budget: Optional[float] = 0
    budget_weekly: Optional[float] = 0
    telegram: Optional[str] = None
    telegram_id: Optional[str] = None
    dietary_preference: Optional[str] = None
    dietary_preferences: Optional[List[str]] = Field(default_factory=list)
    allergies: Optional[List[str]] = Field(default_factory=list)
    preferences: Optional[List[str]] = Field(default_factory=list)


class FamilyMember(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    diet: Optional[str] = None
    dietary_type: Optional[str] = None
    dietary_preferences: Optional[List[str]] = Field(default_factory=list)
    allergies: Optional[List[str]] = Field(default_factory=list)
    preferences: Optional[List[str]] = Field(default_factory=list)
    telegram: Optional[str] = None


class OnboardingRequest(BaseModel):
    user: Optional[UserProfile] = None
    family: Optional[List[FamilyMember]] = Field(default_factory=list)
    family_members: Optional[List[FamilyMember]] = Field(default_factory=list)
    name: Optional[str] = None
    age: Optional[int] = None
    weight: Optional[float] = None
    height: Optional[float] = None
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    goal: Optional[str] = "maintenance"
    weekly_budget: Optional[float] = 0
    budget_weekly: Optional[float] = 0
    telegram: Optional[str] = None
    telegram_id: Optional[str] = None
    dietary_preference: Optional[str] = None
    dietary_preferences: Optional[List[str]] = Field(default_factory=list)
    allergies: Optional[List[str]] = Field(default_factory=list)
    preferences: Optional[List[str]] = Field(default_factory=list)


class FeedbackRequest(BaseModel):
    user_id: str
    plan_id: str
    rating: Optional[int] = None
    notes: Optional[str] = None


class RecipeRequest(BaseModel):
    user_id: str
    meal_name: str
    meal_type: Optional[str] = None
    servings: Optional[int] = None


class CreditGrantRequest(BaseModel):
    admin_user_id: str
    admin_password: str
    user_id: str
    amount: int = Field(default=1, ge=1, le=100)


class AdminLoginRequest(BaseModel):
    admin_user_id: str
    admin_password: str


async def send_plan_to_telegram_background(telegram_id: str, generated_plan: dict) -> None:
    plan_id = str(generated_plan.get("plan_id") or "")
    if plan_id and plan_id in TELEGRAM_SENT_PLAN_IDS:
        print(f"Skipping duplicate Telegram send for plan {plan_id}")
        return
    if plan_id:
        TELEGRAM_SENT_PLAN_IDS.add(plan_id)
    try:
        from telegram_bot import send_plan_for_approval_async

        await send_plan_for_approval_async(telegram_id, generated_plan)
    except Exception as exc:
        print(f"⚠️ Telegram background send failed: {exc}")


# --- Health Check ---

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/health")
async def api_health():
    return {"status": "ok"}


@app.post("/recipe/generate")
async def generate_recipe(payload: RecipeRequest):
    user = get_user(payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    meal_name = (payload.meal_name or "").strip()
    if not meal_name:
        raise HTTPException(status_code=400, detail="Meal name is required")

    family_count = 0
    try:
        from database import get_family_members

        family_count = len(get_family_members(payload.user_id) or [])
    except Exception:
        family_count = 0
    servings = payload.servings or max(1, family_count + 1)
    diet = user.get("dietary_type") or "normal"
    allergies = ", ".join(user.get("allergies") or []) or "None"
    preferences = ", ".join(user.get("preferences") or []) or "None"

    results = tavily_search(f"{meal_name} Indian recipe ingredients steps", max_results=3)
    web_context = "\n---\n".join(
        f"Source: {r.get('url', 'N/A')}\nContent: {r.get('content', '')}"
        for r in results
        if r.get("content")
    )

    prompt = f"""
    Create a practical home-cooking recipe for this meal using the online recipe context.
    Meal: {meal_name}
    Meal type: {payload.meal_type or 'Meal'}
    Servings: {servings}
    Diet: {diet}
    Allergies to avoid: {allergies}
    Preferences: {preferences}

    Online recipe context:
    {web_context or 'No online context found; use standard Indian home-cooking knowledge.'}

    Return ONLY valid JSON:
    {{
      "title": "Recipe title",
      "servings": {servings},
      "prep_time": "10 min",
      "cook_time": "20 min",
      "ingredients": ["item with quantity"],
      "steps": ["step 1"],
      "nutrition_note": "short note",
      "source_urls": ["https://..."]
    }}
    """
    try:
        response = openai_client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        recipe = response.choices[0].message.content
        import json

        return {"recipe": json.loads(recipe)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Recipe generation failed: {exc}")


@app.post("/api/recipe/generate")
async def api_generate_recipe(payload: RecipeRequest):
    return await generate_recipe(payload)


# --- Onboarding ---

@app.post("/onboard")
async def onboard(payload: OnboardingRequest):
    if payload.user is not None:
        user_data = payload.user.dict(exclude_unset=True)
        family_payload = [
            member.dict(exclude_unset=True)
            for member in (payload.family or [])
        ]
    else:
        user_data = payload.dict(
            exclude={"user", "family", "family_members"},
            exclude_unset=True
        )
        family_payload = [
            member.dict(exclude_unset=True)
            for member in (payload.family or payload.family_members or [])
        ]

    user_name = user_data.get("name") or "Unknown"
    age = user_data.get("age") or 0
    weight_kg = user_data.get("weight_kg") or user_data.get("weight") or 0
    height_cm = user_data.get("height_cm") or user_data.get("height") or 0
    goal = user_data.get("goal") or "maintenance"
    budget_weekly = parse_budget(user_data.get("budget_weekly") or user_data.get("weekly_budget") or 0)
    if not str(user_name).strip() or user_name == "Unknown":
        raise HTTPException(status_code=400, detail="Full name is required.")
    if not goal:
        raise HTTPException(status_code=400, detail="Goal is required.")
    if not is_in_range(age, 1, 120):
        raise HTTPException(status_code=400, detail="Enter a valid age.")
    if not is_in_range(weight_kg, 20, 300):
        raise HTTPException(status_code=400, detail="Enter a valid weight.")
    if not is_in_range(height_cm, 80, 250):
        raise HTTPException(status_code=400, detail="Enter a valid height.")
    if budget_weekly < 1500:
        raise HTTPException(status_code=400, detail="Weekly meal budget is too low. Minimum is ₹1500.")
    telegram_id = user_data.get("telegram_id") or user_data.get("telegram") or ""
    dietary_preference = user_data.get("dietary_preference") or None
    dietary_preferences = (
        [dietary_preference]
        if dietary_preference and isinstance(dietary_preference, str)
        else []
    )
    dietary_type = normalize_dietary_type(
        dietary_preference
        or user_data.get("dietary_preferences")
        or user_data.get("preferences")
    ) or "normal"
    allergies = user_data.get("allergies") or []
    preferences = user_data.get("preferences") or []

    user = create_user(
        name=user_name,
        age=age,
        weight_kg=weight_kg,
        height_cm=height_cm,
        goal=goal,
        telegram_id=telegram_id,
        budget_weekly=budget_weekly,
        dietary_type=dietary_type,
        dietary_preferences=dietary_preferences,
        allergies=allergies,
        preferences=preferences,
    )

    if not user or "id" not in user:
        raise HTTPException(status_code=500, detail="Failed to create user")

    normalized_family = [
        normalize_family_member(m)
        for m in family_payload
        if str((m or {}).get("name") or "").strip()
    ]
    family_count = 0
    for member in normalized_family:
        result = add_family_member(
            user_id=user["id"],
            name=member.get("name", "Family Member"),
            age=member.get("age", 0),
            dietary_type=member.get("dietary_type", "normal"),
            allergies=member.get("allergies", []),
            preferences=member.get("preferences", []),
        )
        if result and "id" in result:
            family_count += 1

    user_record = {
        "name": user_name,
        "age": age,
        "weight_kg": weight_kg,
        "height_cm": height_cm,
        "goal": goal,
        "telegram_id": telegram_id,
        "budget_weekly": budget_weekly,
        "dietary_type": dietary_type,
        "dietary_preferences": dietary_preferences,
        "allergies": allergies,
        "preferences": preferences,
    }

    confirmation = (
        f"✅ Onboarding complete!\n"
        f"User ID: {user['id']}\n"
        f"Name: {user_name}\n"
        f"Family members added: {family_count}"
    )

    return {
        "user_id": user["id"],
        "message": confirmation,
        "family_members_added": family_count,
        "credits": get_user_credits(user),
        "role": user.get("role") or "user",
    }


@app.post("/api/onboard")
async def api_onboard(payload: OnboardingRequest):
    return await onboard(payload)


@app.get("/profile/{user_id}")
async def get_profile(user_id: str):
    user = get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user["credits"] = get_user_credits(user)
    user["role"] = user.get("role") or "user"
    return {"profile": user}


@app.get("/api/profile/{user_id}")
async def api_get_profile(user_id: str):
    return await get_profile(user_id)


@app.put("/profile/{user_id}")
async def update_profile(user_id: str, payload: UserProfile):
    existing = get_user(user_id)
    if not existing:
        raise HTTPException(status_code=404, detail="User not found")

    user_data = payload.dict(exclude_unset=True)
    budget_weekly = parse_budget(user_data.get("budget_weekly") or user_data.get("weekly_budget") or existing.get("budget_weekly") or 0)
    if budget_weekly < 1500:
        raise HTTPException(status_code=400, detail="Weekly meal budget is too low. Minimum is ₹1500.")

    dietary_preference = user_data.get("dietary_preference")
    dietary_preferences = (
        [dietary_preference]
        if dietary_preference and isinstance(dietary_preference, str)
        else user_data.get("dietary_preferences") or existing.get("dietary_preferences") or []
    )
    updates = {
        "name": user_data.get("name", existing.get("name")),
        "age": user_data.get("age", existing.get("age")),
        "weight_kg": user_data.get("weight_kg") or user_data.get("weight") or existing.get("weight_kg"),
        "height_cm": user_data.get("height_cm") or user_data.get("height") or existing.get("height_cm"),
        "goal": user_data.get("goal", existing.get("goal")),
        "telegram_id": user_data.get("telegram_id") or user_data.get("telegram") or "",
        "budget_weekly": budget_weekly,
        "dietary_type": normalize_dietary_type(
            dietary_preference
            or user_data.get("dietary_preferences")
            or existing.get("dietary_type")
        ) or existing.get("dietary_type") or "normal",
        "dietary_preferences": dietary_preferences,
        "allergies": user_data.get("allergies", existing.get("allergies") or []),
        "preferences": user_data.get("preferences", existing.get("preferences") or []),
    }
    if not str(updates["name"] or "").strip():
        raise HTTPException(status_code=400, detail="Full name is required.")

    updated = update_user(user_id, updates)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update profile")
    return {"profile": updated}


@app.put("/api/profile/{user_id}")
async def api_update_profile(user_id: str, payload: UserProfile):
    return await update_profile(user_id, payload)


def require_admin(admin_user_id: str, admin_password: str):
    expected_password = os.getenv("ADMIN_PASSWORD", "admin123")
    if not admin_password or admin_password != expected_password:
        raise HTTPException(status_code=401, detail="Invalid admin password")
    admin = get_user(admin_user_id)
    if not admin:
        raise HTTPException(status_code=404, detail="Admin profile not found")
    if (admin.get("role") or "user") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return admin


@app.post("/admin/login")
async def admin_login(payload: AdminLoginRequest):
    admin = require_admin(payload.admin_user_id, payload.admin_password)
    return {
        "admin": {
            "id": str(admin.get("id") or ""),
            "name": admin.get("name") or "Admin",
            "role": admin.get("role") or "admin",
        }
    }


@app.post("/api/admin/login")
async def api_admin_login(payload: AdminLoginRequest):
    return await admin_login(payload)


@app.get("/admin/users")
async def admin_users(admin_user_id: str, admin_password: str):
    require_admin(admin_user_id, admin_password)
    users = list_users()
    normalized = []
    for user in users:
        normalized.append({
            "id": str(user.get("id") or ""),
            "name": user.get("name") or "Unnamed",
            "goal": user.get("goal") or "maintenance",
            "telegram_id": user.get("telegram_id") or "",
            "budget_weekly": parse_budget(user.get("budget_weekly")),
            "credits": get_user_credits(user),
            "role": user.get("role") or "user",
            "created_at": user.get("created_at") or "",
        })
    return {"users": normalized}


@app.get("/api/admin/users")
async def api_admin_users(admin_user_id: str, admin_password: str):
    return await admin_users(admin_user_id, admin_password)


@app.post("/admin/credits")
async def admin_add_credits(payload: CreditGrantRequest):
    require_admin(payload.admin_user_id, payload.admin_password)
    updated = add_user_credits(payload.user_id, payload.amount)
    if not updated:
        raise HTTPException(status_code=500, detail="Unable to add credits. Check Supabase credits column.")
    return {"profile": updated, "credits": get_user_credits(updated)}


@app.post("/api/admin/credits")
async def api_admin_add_credits(payload: CreditGrantRequest):
    return await admin_add_credits(payload)


def parse_budget(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0


def is_in_range(value, min_value: float, max_value: float) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return min_value <= number <= max_value


def format_plan_for_ui(plan: dict, user: dict) -> dict:
    week_plan = plan.get("week_plan") or []
    days = []
    for day in week_plan:
        days.append({
            "day": day.get("day") or day.get("day_name") or "",
            "calories": day.get("total_calories", 0),
            "protein": day.get("total_protein", 0),
            "status": "planned",
            "meals": [
                {
                    "type": "Breakfast",
                    "name": day.get("breakfast", ""),
                    "calories": day.get("breakfast_calories", 0),
                    "protein": day.get("breakfast_protein", 0),
                },
                {
                    "type": "Lunch",
                    "name": day.get("lunch", ""),
                    "calories": day.get("lunch_calories", 0),
                    "protein": day.get("lunch_protein", 0),
                },
                {
                    "type": "Dinner",
                    "name": day.get("dinner", ""),
                    "calories": day.get("dinner_calories", 0),
                    "protein": day.get("dinner_protein", 0),
                },
            ],
        })

    return {
        "id": str(plan.get("plan_id") or ""),
        "user_id": str(plan.get("user_id") or user.get("id") or ""),
        "status": plan.get("status", "ready"),
        "week_summary": plan.get("week_summary") or {
            "healthy_score": 0,
            "avg_calories": 0,
            "avg_protein": 0,
            "total_budget": parse_budget(user.get("budget_weekly")),
        },
        "days": days,
        "goal_summary": plan.get("goal_summary", ""),
        "budget_note": plan.get("budget_note", ""),
        "grocery_estimate": plan.get("grocery_estimate", {}),
        "shopping_list": plan.get("shopping_list", []),
    }


def format_saved_plan_for_ui(plan: dict, user: dict) -> dict:
    day_rows = plan.get("day_meals") or []
    days = []
    for day in day_rows:
        days.append({
            "day": day.get("day_name") or "",
            "calories": day.get("total_calories", 0),
            "protein": day.get("total_protein", 0),
            "status": plan.get("status", "planned"),
            "meals": [
                {
                    "type": "Breakfast",
                    "name": day.get("breakfast", ""),
                    "calories": day.get("breakfast_calories", 0),
                    "protein": day.get("breakfast_protein", 0),
                },
                {
                    "type": "Lunch",
                    "name": day.get("lunch", ""),
                    "calories": day.get("lunch_calories", 0),
                    "protein": day.get("lunch_protein", 0),
                },
                {
                    "type": "Dinner",
                    "name": day.get("dinner", ""),
                    "calories": day.get("dinner_calories", 0),
                    "protein": day.get("dinner_protein", 0),
                },
            ],
        })

    day_count = max(len(days), 1)
    avg_calories = round(sum(day["calories"] for day in days) / day_count)
    avg_protein = round(sum(day["protein"] for day in days) / day_count)
    return {
        "id": str(plan.get("id") or ""),
        "user_id": str(user.get("id") or plan.get("user_id") or ""),
        "status": plan.get("status", "ready"),
        "created_at": plan.get("created_at") or plan.get("week_start"),
        "week_summary": {
            "healthy_score": 90 if days else 0,
            "avg_calories": avg_calories,
            "avg_protein": avg_protein,
            "total_budget": parse_budget(user.get("budget_weekly")),
        },
        "days": days,
        "goal_summary": "",
        "shopping_list": [],
    }


def format_history_item(plan: dict, user: dict) -> dict:
    formatted = format_saved_plan_for_ui(plan, user)
    summary = formatted.get("week_summary") or {}
    return {
        "plan_id": formatted.get("id") or str(plan.get("id") or ""),
        "created_at": formatted.get("created_at") or datetime.utcnow().isoformat(),
        "status": formatted.get("status") or "ready",
        "goal": user.get("goal") or "maintenance",
        "avg_calories": summary.get("avg_calories") or 0,
        "avg_protein": summary.get("avg_protein") or 0,
    }


def calculate_plan_streak(history: list) -> int:
    week_starts = set()
    for plan in history or []:
        raw = plan.get("week_start") or plan.get("created_at")
        if not raw:
            continue
        try:
            parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00")).date()
        except ValueError:
            try:
                parsed = date.fromisoformat(str(raw)[:10])
            except ValueError:
                continue
        week_start = parsed - timedelta(days=parsed.weekday())
        week_starts.add(week_start)

    if not week_starts:
        return 0

    current = date.today() - timedelta(days=date.today().weekday())
    if current not in week_starts:
        latest = max(week_starts)
        if latest < current - timedelta(days=7):
            return 0
        current = latest

    streak = 0
    while current in week_starts:
        streak += 1
        current -= timedelta(days=7)
    return streak


# --- Meal Plan ---

@app.post("/plan/generate/{user_id}")
async def plan_generate(user_id: str, background_tasks: BackgroundTasks):
    if user_id in GENERATING_USERS:
        raise HTTPException(status_code=409, detail="A meal plan is already being generated. Please wait.")
    user = get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if parse_budget(user.get("budget_weekly")) < 1500:
        raise HTTPException(status_code=400, detail="Weekly meal budget is too low. Please update Profile with at least ₹1500.")
    if "credits" not in user:
        raise HTTPException(status_code=500, detail="Credits are not configured yet. Run supabase_credit_setup.sql in Supabase.")
    is_admin = (user.get("role") or "user") == "admin"
    if not is_admin and get_user_credits(user) <= 0:
        raise HTTPException(status_code=402, detail="You have used your 3 free meal plan credits. Please ask admin to add more credits.")

    GENERATING_USERS.add(user_id)
    try:
        generated_plan = generate_meal_plan(int(user_id))
        if not generated_plan:
            raise HTTPException(status_code=500, detail="Plan generation failed")
        credit_result = {"ok": True, "credits": get_user_credits(user), "unlimited": True} if is_admin else consume_user_credit(user_id)
        if not credit_result.get("ok"):
            raise HTTPException(status_code=500, detail=credit_result.get("error") or "Unable to consume meal plan credit.")
        plan = format_plan_for_ui(generated_plan, user)
        plan["credits_remaining"] = credit_result.get("credits", 0)
        plan["credits_unlimited"] = is_admin

        telegram_id = str(user.get("telegram_id") or "").strip()
        if telegram_id:
            background_tasks.add_task(send_plan_to_telegram_background, telegram_id, generated_plan)

        return {"plan": plan, "telegram_queued": bool(telegram_id), "credits_remaining": credit_result.get("credits", 0), "credits_unlimited": is_admin}
    finally:
        GENERATING_USERS.discard(user_id)


@app.post("/api/plan/generate/{user_id}")
async def api_plan_generate(user_id: str, background_tasks: BackgroundTasks):
    return await plan_generate(user_id, background_tasks)


@app.get("/plan/latest/{user_id}")
async def latest_plan(user_id: str):
    user = get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    plan = get_latest_plan(int(user_id)) if user_id.isdigit() else None
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return {"plan": format_saved_plan_for_ui(plan, user)}


@app.get("/api/plan/latest/{user_id}")
async def api_latest_plan(user_id: str):
    return await latest_plan(user_id)


@app.get("/streak/{user_id}")
async def get_streak(user_id: str):
    user = get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    history = get_user_history(user_id)
    return {"streak": calculate_plan_streak(history)}


@app.get("/api/streak/{user_id}")
async def api_get_streak(user_id: str):
    return await get_streak(user_id)


@app.post("/telegram/test/{user_id}")
async def telegram_test(user_id: str):
    user = get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    telegram_id = str(user.get("telegram_id") or "").strip()
    if not telegram_id:
        raise HTTPException(status_code=400, detail=f"Telegram chat ID is not added in backend profile for user {user_id}. Save Profile again.")
    try:
        from telegram_bot import send_test_message_async

        sent = bool(await send_test_message_async(telegram_id))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Telegram test failed: {exc}")
    if not sent:
        raise HTTPException(status_code=400, detail="Telegram message was not sent. Check bot token, chat ID, and whether you started the bot.")
    return {"sent": True}


@app.post("/api/telegram/test/{user_id}")
async def api_telegram_test(user_id: str):
    return await telegram_test(user_id)


@app.get("/plan/{plan_id}")
async def get_plan(plan_id: str):
    plan = get_latest_plan(int(plan_id)) if plan_id.isdigit() else None
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return {"plan": plan}


@app.get("/api/plan/{plan_id}")
async def api_get_plan(plan_id: str):
    return await get_plan(plan_id)


# --- Grocery ---

@app.get("/grocery/{plan_id}")
async def get_grocery(plan_id: str):
    plan = get_latest_plan(int(plan_id)) if plan_id.isdigit() else None
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    grocery = plan.get("grocery_list") or []
    return {"grocery": grocery}


@app.get("/api/grocery/{plan_id}")
async def api_get_grocery(plan_id: str):
    return await get_grocery(plan_id)


# --- Feedback ---

@app.post("/feedback")
async def feedback(payload: FeedbackRequest):
    saved = save_feedback(
        payload.plan_id,
        payload.user_id,
        payload.rating,
        payload.notes,
        False
    )
    return {"saved": bool(saved)}


@app.post("/api/feedback")
async def api_feedback(payload: FeedbackRequest):
    return await feedback(payload)


# --- History ---

@app.get("/history/{user_id}")
async def history(user_id: str):
    user = get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    hist = get_user_history(user_id)
    return {"history": [format_history_item(plan, user) for plan in hist]}


@app.get("/api/history/{user_id}")
async def api_history(user_id: str):
    return await history(user_id)


if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
