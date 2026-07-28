import os
import asyncio
import json
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
import uvicorn

from database import (
    create_user,
    get_user,
    get_user_by_email,
    add_family_member,
    replace_family_members,
    get_family_members,
    get_latest_plan,
    get_meal_plan,
    save_feedback,
    get_user_history,
    update_user,
    get_user_credits,
    consume_user_credit,
    add_user_credits,
    list_users,
    get_grocery_list,
    get_person_plan_overrides,
    save_person_plan_override,
    create_credit_request,
    list_credit_requests,
    update_credit_request,
    create_support_ticket,
    list_support_tickets,
    update_support_ticket,
    update_plan_status,
)
from agent import attach_people_plans, generate_meal_plan
from tools import openai_client, tavily_search
from onboarding_utils import normalize_dietary_type, normalize_family_member
from config import TELEGRAM_BOT_TOKEN, WHATSAPP_VERIFY_TOKEN

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
    email: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    weight: Optional[float] = None
    height: Optional[float] = None
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    goal: Optional[str] = "maintenance"
    weekly_budget: Optional[float] = 0
    budget_weekly: Optional[float] = 0
    telegram: Optional[str] = None
    telegram_id: Optional[str] = None
    whatsapp: Optional[str] = None
    whatsapp_number: Optional[str] = None
    dietary_preference: Optional[str] = None
    dietary_preferences: Optional[List[str]] = Field(default_factory=list)
    allergies: Optional[List[str]] = Field(default_factory=list)
    preferences: Optional[List[str]] = Field(default_factory=list)


class FamilyMember(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    goal: Optional[str] = "maintenance"
    gender: Optional[str] = None
    weight: Optional[float] = None
    height: Optional[float] = None
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    diet: Optional[str] = None
    dietary_type: Optional[str] = None
    dietary_preferences: Optional[List[str]] = Field(default_factory=list)
    allergies: Optional[List[str]] = Field(default_factory=list)
    preferences: Optional[List[str]] = Field(default_factory=list)
    telegram: Optional[str] = None
    whatsapp: Optional[str] = None
    whatsapp_number: Optional[str] = None


class OnboardingRequest(BaseModel):
    user: Optional[UserProfile] = None
    family: Optional[List[FamilyMember]] = Field(default_factory=list)
    family_members: Optional[List[FamilyMember]] = Field(default_factory=list)
    name: Optional[str] = None
    email: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    weight: Optional[float] = None
    height: Optional[float] = None
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    goal: Optional[str] = "maintenance"
    weekly_budget: Optional[float] = 0
    budget_weekly: Optional[float] = 0
    telegram: Optional[str] = None
    telegram_id: Optional[str] = None
    whatsapp: Optional[str] = None
    whatsapp_number: Optional[str] = None
    dietary_preference: Optional[str] = None
    dietary_preferences: Optional[List[str]] = Field(default_factory=list)
    allergies: Optional[List[str]] = Field(default_factory=list)
    preferences: Optional[List[str]] = Field(default_factory=list)


class ProfileUpdateRequest(UserProfile):
    family: Optional[List[FamilyMember]] = Field(default_factory=list)


class FeedbackRequest(BaseModel):
    user_id: str
    plan_id: str
    rating: Optional[int] = None
    notes: Optional[str] = None


class GeneratePlanRequest(BaseModel):
    week_start: Optional[str] = None
    week_offset: int = Field(default=0, ge=0, le=1)


class RecipeRequest(BaseModel):
    user_id: str
    meal_name: str
    meal_type: Optional[str] = None
    servings: Optional[int] = None


class PersonDayRegenerateRequest(BaseModel):
    user_id: str
    plan_id: str
    person_id: str
    day: str
    feedback: str


class CreditGrantRequest(BaseModel):
    admin_user_id: str
    admin_password: str
    user_id: str
    amount: int = Field(default=1, ge=1, le=100)


class AdminLoginRequest(BaseModel):
    admin_user_id: str
    admin_password: str


class CreditRequestPayload(BaseModel):
    user_id: str
    requested_credits: int = Field(default=3, ge=1, le=100)
    note: Optional[str] = ""


class CreditRequestGrantPayload(BaseModel):
    admin_user_id: str
    admin_password: str
    request_id: int
    amount: int = Field(default=3, ge=1, le=100)


class SupportTicketPayload(BaseModel):
    user_id: str
    category: str = Field(default="bug", max_length=40)
    title: str = Field(..., min_length=3, max_length=120)
    description: str = Field(..., min_length=10, max_length=3000)
    page_url: Optional[str] = Field(default="", max_length=500)
    severity: str = Field(default="normal", max_length=20)


class SupportTicketStatusPayload(BaseModel):
    admin_user_id: str
    admin_password: str
    ticket_id: int
    status: str = Field(default="resolved")


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


async def send_plan_to_whatsapp_background(whatsapp_number: str, generated_plan: dict) -> None:
    try:
        from whatsapp_bot import send_plan_for_approval

        await asyncio.to_thread(send_plan_for_approval, whatsapp_number, generated_plan)
    except Exception as exc:
        print(f"⚠️ WhatsApp background send failed: {exc}")


def telegram_api(method: str, payload: dict) -> None:
    if not TELEGRAM_BOT_TOKEN:
        print("⚠️ Telegram bot token is not configured")
        return
    data = urllib.parse.urlencode(payload).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}",
        data=data,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            response.read()
    except Exception as exc:
        print(f"⚠️ Telegram API {method} failed: {exc}")


async def handle_telegram_update(update: dict) -> dict:
    callback = update.get("callback_query") or {}
    message = update.get("message") or {}

    if callback:
        callback_id = callback.get("id")
        data = str(callback.get("data") or "")
        from_user = callback.get("from") or {}
        chat = (callback.get("message") or {}).get("chat") or {}
        chat_id = chat.get("id") or from_user.get("id")
        message_id = (callback.get("message") or {}).get("message_id")

        if callback_id:
            telegram_api("answerCallbackQuery", {"callback_query_id": callback_id})

        if data.startswith("approve_"):
            plan_id = data.split("_", 1)[1]
            update_plan_status(plan_id, "approved")
            if chat_id and message_id:
                telegram_api("editMessageReplyMarkup", {"chat_id": chat_id, "message_id": message_id, "reply_markup": json.dumps({"inline_keyboard": []})})
            if chat_id:
                telegram_api("sendMessage", {"chat_id": chat_id, "text": "Meal plan approved. Your browser/app will refresh to the approved plan."})
            return {"ok": True, "action": "approved", "plan_id": plan_id}

        if data.startswith("reject_"):
            plan_id = data.split("_", 1)[1]
            if chat_id:
                telegram_api(
                    "sendMessage",
                    {
                        "chat_id": chat_id,
                        "text": f"Plan rejected. Reply with:\n/change {plan_id} what you want changed",
                    },
                )
            return {"ok": True, "action": "reject_prompted", "plan_id": plan_id}

    text = str(message.get("text") or "").strip()
    chat = message.get("chat") or {}
    from_user = message.get("from") or {}
    chat_id = chat.get("id") or from_user.get("id")
    telegram_id = str(from_user.get("id") or chat_id or "")

    if text.startswith("/change "):
        parts = text.split(" ", 2)
        if len(parts) < 3:
            if chat_id:
                telegram_api("sendMessage", {"chat_id": chat_id, "text": "Please send: /change PLAN_ID your requested changes"})
            return {"ok": True, "action": "change_missing_feedback"}

        plan_id, feedback_text = parts[1], parts[2].strip()
        user = None
        from database import get_user_by_telegram_id

        user = get_user_by_telegram_id(telegram_id)
        if not user:
            if chat_id:
                telegram_api("sendMessage", {"chat_id": chat_id, "text": "User not found for this Telegram chat ID. Save your chat ID in Profile and try again."})
            return {"ok": False, "action": "user_not_found"}

        if chat_id:
            telegram_api("sendMessage", {"chat_id": chat_id, "text": "Regenerating your meal plan with that feedback..."})
        save_feedback(plan_id, user.get("name") or "Telegram", 3, feedback_text, True)
        updated_plan = generate_meal_plan(int(user.get("id")), feedback_text)
        if updated_plan.get("status") == "success":
            await send_plan_to_telegram_background(str(chat_id), updated_plan)
            return {"ok": True, "action": "regenerated", "plan_id": updated_plan.get("plan_id")}
        if chat_id:
            telegram_api("sendMessage", {"chat_id": chat_id, "text": f"Could not regenerate plan: {updated_plan.get('message') or 'Unknown error'}"})
        return {"ok": False, "action": "regenerate_failed"}

    return {"ok": True, "action": "ignored"}


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    return await handle_telegram_update(await request.json())


@app.post("/api/telegram/webhook")
async def api_telegram_webhook(request: Request):
    return await telegram_webhook(request)


def verify_whatsapp_webhook(request: Request) -> Response:
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    expected_token = WHATSAPP_VERIFY_TOKEN or "smartmeal_whatsapp_verify"

    if mode == "subscribe" and token == expected_token and challenge:
        return Response(content=challenge, media_type="text/plain")
    raise HTTPException(status_code=403, detail="WhatsApp webhook verification failed")


async def handle_whatsapp_update(update: dict) -> dict:
    entry = (update.get("entry") or [{}])[0]
    change = ((entry.get("changes") or [{}])[0]).get("value") or {}
    messages = change.get("messages") or []
    if not messages:
        return {"ok": True, "action": "ignored"}

    message = messages[0]
    button = message.get("button") or {}
    interactive = message.get("interactive") or {}
    button_reply = interactive.get("button_reply") or {}
    text_body = (message.get("text") or {}).get("body") or ""
    action_id = button_reply.get("id") or button.get("payload") or text_body

    if str(action_id).startswith("approve_"):
        plan_id = str(action_id).split("_", 1)[1]
        update_plan_status(plan_id, "approved")
        return {"ok": True, "action": "approved", "plan_id": plan_id}

    if str(action_id).startswith("reject_"):
        plan_id = str(action_id).split("_", 1)[1]
        return {"ok": True, "action": "reject_prompted", "plan_id": plan_id}

    return {"ok": True, "action": "ignored"}


@app.get("/whatsapp/webhook")
async def whatsapp_webhook_verify(request: Request):
    return verify_whatsapp_webhook(request)


@app.get("/api/whatsapp/webhook")
async def api_whatsapp_webhook_verify(request: Request):
    return verify_whatsapp_webhook(request)


@app.post("/whatsapp/webhook")
async def whatsapp_webhook(request: Request):
    return await handle_whatsapp_update(await request.json())


@app.post("/api/whatsapp/webhook")
async def api_whatsapp_webhook(request: Request):
    return await whatsapp_webhook(request)


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
    email = str(user_data.get("email") or "").strip().lower()
    age = user_data.get("age") or 0
    gender = user_data.get("gender") or ""
    weight_kg = user_data.get("weight_kg") or user_data.get("weight") or 0
    height_cm = user_data.get("height_cm") or user_data.get("height") or 0
    goal = user_data.get("goal") or "maintenance"
    budget_weekly = parse_budget(user_data.get("budget_weekly") or user_data.get("weekly_budget") or 0)
    if not str(user_name).strip() or user_name == "Unknown":
        raise HTTPException(status_code=400, detail="Full name is required.")
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email is required. Please sign up or login again.")
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
    whatsapp_number = user_data.get("whatsapp_number") or user_data.get("whatsapp") or ""
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

    updates = {
        "name": user_name,
        "email": email,
        "age": age,
        "gender": gender,
        "weight_kg": weight_kg,
        "height_cm": height_cm,
        "goal": goal,
        "telegram_id": telegram_id,
        "whatsapp_number": whatsapp_number,
        "budget_weekly": budget_weekly,
        "dietary_type": dietary_type,
        "dietary_preferences": dietary_preferences,
        "allergies": allergies,
        "preferences": preferences,
    }

    if get_user_by_email(email):
        raise HTTPException(status_code=409, detail="An account already exists for this email. Please login instead of signing up again.")

    user = create_user(
        name=user_name,
        email=email,
        age=age,
        gender=gender,
        weight_kg=weight_kg,
        height_cm=height_cm,
        goal=goal,
        telegram_id=telegram_id,
        whatsapp_number=whatsapp_number,
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
            telegram=member.get("telegram", ""),
            whatsapp=member.get("whatsapp", "") or member.get("whatsapp_number", ""),
            goal=member.get("goal", "maintenance"),
            gender=member.get("gender", ""),
            weight_kg=member.get("weight_kg", 0),
            height_cm=member.get("height_cm", 0),
        )
        if result and "id" in result:
            family_count += 1

    user_record = {
        "name": user_name,
        "email": email,
        "age": age,
        "gender": gender,
        "weight_kg": weight_kg,
        "height_cm": height_cm,
        "goal": goal,
        "telegram_id": telegram_id,
        "whatsapp_number": whatsapp_number,
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


@app.get("/profile/by-email/{email}")
async def get_profile_by_email(email: str):
    user = get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="Account not found")
    user["credits"] = get_user_credits(user)
    user["role"] = user.get("role") or "user"
    user["family"] = get_family_members(user.get("id"))
    return {"profile": user}


@app.get("/api/profile/by-email/{email}")
async def api_get_profile_by_email(email: str):
    return await get_profile_by_email(email)


@app.get("/profile/{user_id}")
async def get_profile(user_id: str):
    user = get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user["credits"] = get_user_credits(user)
    user["role"] = user.get("role") or "user"
    user["family"] = get_family_members(user_id)
    return {"profile": user}


@app.get("/api/profile/{user_id}")
async def api_get_profile(user_id: str):
    return await get_profile(user_id)


@app.put("/profile/{user_id}")
async def update_profile(user_id: str, payload: ProfileUpdateRequest):
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
    telegram_update = user_data.get("telegram_id")
    if telegram_update is None:
        telegram_update = user_data.get("telegram")
    if telegram_update is None:
        telegram_update = existing.get("telegram_id") or ""
    whatsapp_update = user_data.get("whatsapp_number")
    if whatsapp_update is None:
        whatsapp_update = user_data.get("whatsapp")
    if whatsapp_update is None:
        whatsapp_update = existing.get("whatsapp_number") or ""

    updates = {
        "name": user_data.get("name", existing.get("name")),
        "email": user_data.get("email") or existing.get("email", ""),
        "age": user_data.get("age", existing.get("age")),
        "gender": user_data.get("gender", existing.get("gender") or ""),
        "weight_kg": user_data.get("weight_kg") or user_data.get("weight") or existing.get("weight_kg"),
        "height_cm": user_data.get("height_cm") or user_data.get("height") or existing.get("height_cm"),
        "goal": user_data.get("goal", existing.get("goal")),
        "telegram_id": str(telegram_update).strip(),
        "whatsapp_number": str(whatsapp_update).strip(),
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
    normalized_family = [
        normalize_family_member(member)
        for member in (user_data.get("family") or [])
        if str((member or {}).get("name") or "").strip()
    ]
    saved_family = replace_family_members(user_id, normalized_family)
    updated["family"] = saved_family
    return {"profile": updated}


@app.put("/api/profile/{user_id}")
async def api_update_profile(user_id: str, payload: ProfileUpdateRequest):
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


@app.post("/credit-requests")
async def request_credits(payload: CreditRequestPayload):
    user = get_user(payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if (user.get("role") or "user") == "admin":
        raise HTTPException(status_code=400, detail="Admin users have unlimited credits.")
    request = create_credit_request(payload.user_id, payload.requested_credits, payload.note or "")
    if not request:
        raise HTTPException(status_code=500, detail="Could not create credit request. Run the credit_requests Supabase setup.")
    return {"request": request}


@app.post("/api/credit-requests")
async def api_request_credits(payload: CreditRequestPayload):
    return await request_credits(payload)


@app.get("/admin/credit-requests")
async def admin_credit_requests(admin_user_id: str, admin_password: str):
    require_admin(admin_user_id, admin_password)
    return {"requests": list_credit_requests("pending")}


@app.get("/api/admin/credit-requests")
async def api_admin_credit_requests(admin_user_id: str, admin_password: str):
    return await admin_credit_requests(admin_user_id, admin_password)


@app.post("/admin/credit-requests/grant")
async def admin_grant_credit_request(payload: CreditRequestGrantPayload):
    require_admin(payload.admin_user_id, payload.admin_password)
    requests = list_credit_requests("pending")
    request = next((item for item in requests if int(item.get("id")) == int(payload.request_id)), None)
    if not request:
        raise HTTPException(status_code=404, detail="Pending credit request not found")
    user_id = request.get("user_id")
    updated = add_user_credits(user_id, payload.amount)
    if not updated:
        raise HTTPException(status_code=500, detail="Unable to add credits")
    update_credit_request(payload.request_id, {
        "status": "approved",
        "granted_credits": payload.amount,
        "resolved_at": datetime.utcnow().isoformat(),
    })
    return {"profile": updated, "credits": get_user_credits(updated)}


@app.post("/api/admin/credit-requests/grant")
async def api_admin_grant_credit_request(payload: CreditRequestGrantPayload):
    return await admin_grant_credit_request(payload)


@app.post("/support/tickets")
async def create_ticket(payload: SupportTicketPayload):
    user = get_user(payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    allowed_categories = {"bug", "meal_plan", "grocery", "telegram", "account", "billing", "other"}
    allowed_severity = {"low", "normal", "high", "urgent"}
    category = payload.category if payload.category in allowed_categories else "other"
    severity = payload.severity if payload.severity in allowed_severity else "normal"
    ticket = create_support_ticket(
        payload.user_id,
        category,
        payload.title,
        payload.description,
        payload.page_url or "",
        severity,
    )
    if not ticket:
        raise HTTPException(status_code=500, detail="Could not create support ticket. Run supabase_support_setup.sql in Supabase.")
    return {"ticket": ticket}


@app.post("/api/support/tickets")
async def api_create_ticket(payload: SupportTicketPayload):
    return await create_ticket(payload)


@app.get("/admin/support-tickets")
async def admin_support_tickets(admin_user_id: str, admin_password: str, status: str = "open"):
    require_admin(admin_user_id, admin_password)
    return {"tickets": list_support_tickets(status)}


@app.get("/api/admin/support-tickets")
async def api_admin_support_tickets(admin_user_id: str, admin_password: str, status: str = "open"):
    return await admin_support_tickets(admin_user_id, admin_password, status)


@app.post("/admin/support-tickets/status")
async def admin_update_support_ticket(payload: SupportTicketStatusPayload):
    require_admin(payload.admin_user_id, payload.admin_password)
    allowed_status = {"open", "reviewing", "resolved"}
    if payload.status not in allowed_status:
        raise HTTPException(status_code=400, detail="Invalid ticket status")
    updates = {"status": payload.status}
    if payload.status == "resolved":
        updates["resolved_at"] = datetime.utcnow().isoformat()
    else:
        updates["resolved_at"] = None
    ticket = update_support_ticket(payload.ticket_id, updates)
    if not ticket:
        raise HTTPException(status_code=404, detail="Support ticket not found")
    return {"ticket": ticket}


@app.post("/api/admin/support-tickets/status")
async def api_admin_update_support_ticket(payload: SupportTicketStatusPayload):
    return await admin_update_support_ticket(payload)


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
        "people_plans": plan.get("people_plans", []),
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
    formatted = {
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
        "people_plans": attach_people_plans({"week_plan": day_rows}, user).get("people_plans", []),
    }
    return apply_person_plan_overrides(formatted)


def apply_person_plan_overrides(plan: dict) -> dict:
    plan_id = str(plan.get("id") or "")
    if not plan_id:
        return plan
    overrides = get_person_plan_overrides(plan_id)
    if not overrides:
        return plan
    lookup = {
        (str(item.get("person_id") or ""), str(item.get("day_name") or "")): item.get("override") or {}
        for item in overrides
    }
    for person in plan.get("people_plans") or []:
        person_id = str(person.get("person_id") or "")
        for index, day in enumerate(person.get("days") or []):
            override = lookup.get((person_id, str(day.get("day") or "")))
            if override:
                merged = {**day, **override, "status": "updated"}
                person["days"][index] = merged
    return plan


def format_history_item(plan: dict, user: dict) -> dict:
    formatted = format_saved_plan_for_ui(plan, user)
    summary = formatted.get("week_summary") or {}
    week_start = normalize_week_start(plan.get("week_start") or formatted.get("created_at"))
    return {
        "plan_id": formatted.get("id") or str(plan.get("id") or ""),
        "created_at": formatted.get("created_at") or datetime.utcnow().isoformat(),
        "week_start": week_start.isoformat() if week_start else formatted.get("created_at") or datetime.utcnow().date().isoformat(),
        "status": formatted.get("status") or "ready",
        "goal": user.get("goal") or "maintenance",
        "avg_calories": summary.get("avg_calories") or 0,
        "avg_protein": summary.get("avg_protein") or 0,
    }


def normalize_week_start(raw) -> Optional[date]:
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00")).date()
    except ValueError:
        try:
            parsed = date.fromisoformat(str(raw)[:10])
        except ValueError:
            return None
    return parsed - timedelta(days=parsed.weekday())


def resolve_requested_week_start(payload: Optional[GeneratePlanRequest]) -> date:
    current_week = date.today() - timedelta(days=date.today().weekday())
    if payload and payload.week_start:
        parsed = normalize_week_start(payload.week_start)
        if not parsed:
            raise HTTPException(status_code=400, detail="Invalid week start.")
        allowed = {current_week, current_week + timedelta(days=7)}
        if parsed not in allowed:
            raise HTTPException(status_code=400, detail="You can generate plans for this week or next week only.")
        return parsed
    offset = payload.week_offset if payload else 0
    return current_week + timedelta(days=7 * offset)


def history_sort_key(plan: dict):
    status_rank = 1 if str(plan.get("status", "")).lower() == "approved" else 0
    try:
        created = datetime.fromisoformat(str(plan.get("created_at") or "").replace("Z", "+00:00"))
    except ValueError:
        created = datetime.min
    try:
        plan_id = int(plan.get("id") or 0)
    except (TypeError, ValueError):
        plan_id = 0
    return (status_rank, created, plan_id)


def summarize_weekly_history(history: list, user: dict) -> list:
    grouped = {}
    counts = {}

    for plan in history or []:
        week_start = normalize_week_start(plan.get("week_start") or plan.get("created_at"))
        if not week_start:
            continue
        key = week_start.isoformat()
        counts[key] = counts.get(key, 0) + 1
        if key not in grouped or history_sort_key(plan) > history_sort_key(grouped[key]):
            grouped[key] = plan

    items = []
    for key, plan in grouped.items():
        item = format_history_item(plan, user)
        item["week_start"] = key
        item["version_count"] = counts.get(key, 1)
        items.append(item)

    return sorted(items, key=lambda item: item.get("week_start", ""), reverse=True)


def format_grocery_groups(items) -> list:
    if not isinstance(items, list):
        return []
    if items and all(not isinstance(item, dict) for item in items):
        normalized = []
        for item in items:
            text = str(item).strip()
            if not text:
                continue
            parts = text.rsplit(" ", 1)
            if len(parts) == 2 and any(char.isdigit() for char in parts[1]):
                normalized.append({"name": parts[0], "quantity": parts[1]})
            else:
                normalized.append({"name": text, "quantity": ""})
        return [{"category": "Groceries", "items": normalized}] if normalized else []
    groups = []
    for group in items:
        if not isinstance(group, dict):
            continue
        category = group.get("category") or group.get("name") or "Other"
        raw_items = group.get("items") or []
        normalized_items = []
        for item in raw_items:
            if isinstance(item, dict):
                name = item.get("name") or item.get("item") or ""
                quantity = item.get("quantity") or item.get("qty") or ""
            else:
                name = str(item)
                quantity = ""
            if name:
                normalized_items.append({"name": name, "quantity": quantity})
        if normalized_items:
            groups.append({"category": category, "items": normalized_items})
    return groups


def grocery_from_day_meals(plan: dict) -> list:
    day_meals = plan.get("day_meals") or []
    names = []
    for day in day_meals:
        for key in ("breakfast", "lunch", "dinner"):
            meal = str(day.get(key) or "").strip()
            if meal:
                names.append(meal)
    if not names:
        return []

    text = " ".join(names).lower()
    groups = [
        ("Grains", [
            ("Rice", "2 kg", ["rice", "chawal", "biryani"]),
            ("Atta", "2 kg", ["chapati", "phulka", "roti", "paratha"]),
            ("Oats", "500g", ["oats"]),
            ("Poha", "500g", ["poha"]),
        ]),
        ("Proteins", [
            ("Dal", "1 kg", ["dal", "sambar"]),
            ("Rajma", "500g", ["rajma"]),
            ("Chana", "500g", ["chana", "chole"]),
            ("Soya chunks", "500g", ["soya"]),
            ("Paneer", "500g", ["paneer"]),
            ("Tofu", "500g", ["tofu"]),
            ("Eggs", "1 dozen", ["egg"]),
            ("Chicken", "1 kg", ["chicken"]),
            ("Fish", "800g", ["fish"]),
        ]),
        ("Vegetables", [
            ("Onions", "1 kg", ["onion"]),
            ("Tomatoes", "1 kg", ["tomato"]),
            ("Spinach", "500g", ["palak", "spinach"]),
            ("Bhindi", "500g", ["bhindi"]),
            ("Mixed seasonal vegetables", "2 kg", ["vegetable", "sabzi", "khichdi", "upma", "pulao"]),
        ]),
        ("Dairy", [
            ("Curd", "1 kg", ["curd", "raita", "kadhi"]),
            ("Milk", "2 L", ["milk"]),
        ]),
        ("Spices & condiments", [
            ("Turmeric powder", "100g", ["dal", "sabzi", "curry", "masala"]),
            ("Cumin seeds", "100g", ["jeera", "dal", "rice"]),
            ("Garam masala", "100g", ["masala", "curry"]),
            ("Mustard oil", "1 L", ["sabzi", "curry", "masala"]),
        ]),
    ]
    result = []
    for category, candidates in groups:
        items = [
            {"name": name, "quantity": quantity}
            for name, quantity, keywords in candidates
            if any(keyword in text for keyword in keywords)
        ]
        if items:
            result.append({"category": category, "items": items})
    return result


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
async def plan_generate(user_id: str, payload: Optional[GeneratePlanRequest] = None):
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
        week_start = resolve_requested_week_start(payload)
        generated_plan = generate_meal_plan(int(user_id), week_start=week_start.isoformat())
        if not generated_plan:
            raise HTTPException(status_code=500, detail="Plan generation failed")
        credit_result = {"ok": True, "credits": get_user_credits(user), "unlimited": True} if is_admin else consume_user_credit(user_id)
        if not credit_result.get("ok"):
            raise HTTPException(status_code=500, detail=credit_result.get("error") or "Unable to consume meal plan credit.")
        plan = format_plan_for_ui(generated_plan, user)
        plan["credits_remaining"] = credit_result.get("credits", 0)
        plan["credits_unlimited"] = is_admin

        telegram_id = str(user.get("telegram_id") or "").strip()
        whatsapp_number = str(user.get("whatsapp_number") or "").strip()
        needs_external_approval = bool(telegram_id or whatsapp_number)
        if needs_external_approval:
            plan["status"] = "pending"
            for day in plan.get("days") or []:
                day["status"] = "pending"
            if whatsapp_number:
                asyncio.create_task(send_plan_to_whatsapp_background(whatsapp_number, generated_plan))
            if telegram_id:
                asyncio.create_task(send_plan_to_telegram_background(telegram_id, generated_plan))
        else:
            plan_id = str(generated_plan.get("plan_id") or plan.get("id") or "").strip()
            if plan_id:
                update_plan_status(plan_id, "approved")
            plan["status"] = "approved"
            for day in plan.get("days") or []:
                day["status"] = "approved"

        return {
            "plan": plan,
            "telegram_queued": bool(telegram_id),
            "whatsapp_queued": bool(whatsapp_number),
            "auto_approved": not needs_external_approval,
            "credits_remaining": credit_result.get("credits", 0),
            "credits_unlimited": is_admin,
        }
    finally:
        GENERATING_USERS.discard(user_id)


@app.post("/api/plan/generate/{user_id}")
async def api_plan_generate(user_id: str, payload: Optional[GeneratePlanRequest] = None):
    return await plan_generate(user_id, payload)


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


@app.post("/whatsapp/test/{user_id}")
async def whatsapp_test(user_id: str):
    user = get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    whatsapp_number = str(user.get("whatsapp_number") or "").strip()
    if not whatsapp_number:
        raise HTTPException(status_code=400, detail=f"WhatsApp number is not added in backend profile for user {user_id}. Save WhatsApp again.")
    try:
        from whatsapp_bot import send_test_message

        sent = bool(await asyncio.to_thread(send_test_message, whatsapp_number))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"WhatsApp test failed: {exc}")
    if not sent:
        raise HTTPException(status_code=400, detail="WhatsApp message was not sent. Check Meta token, phone number ID, and test recipient setup.")
    return {"sent": True}


@app.post("/api/whatsapp/test/{user_id}")
async def api_whatsapp_test(user_id: str):
    return await whatsapp_test(user_id)


@app.get("/plan/{plan_id}")
async def get_plan(plan_id: str):
    plan = get_meal_plan(int(plan_id)) if plan_id.isdigit() else None
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return {"plan": plan}


@app.get("/api/plan/{plan_id}")
async def api_get_plan(plan_id: str):
    return await get_plan(plan_id)


@app.post("/plan/regenerate-person-day")
async def regenerate_person_day(payload: PersonDayRegenerateRequest):
    user = get_user(payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    plan_record = get_meal_plan(int(payload.plan_id)) if str(payload.plan_id).isdigit() else None
    if not plan_record:
        raise HTTPException(status_code=404, detail="Plan not found")
    if str(plan_record.get("user_id")) != str(payload.user_id):
        raise HTTPException(status_code=403, detail="Plan does not belong to this user")

    formatted = format_saved_plan_for_ui(plan_record, user)
    person = next((p for p in formatted.get("people_plans", []) if str(p.get("person_id")) == str(payload.person_id)), None)
    if not person:
        raise HTTPException(status_code=404, detail="Person tab not found")
    current_day = next((d for d in person.get("days", []) if str(d.get("day")) == str(payload.day)), None)
    if not current_day:
        raise HTTPException(status_code=404, detail="Day not found")

    prompt = f"""
    Regenerate only this person's day meal plan. Do not modify any other person or day.

    Person:
    Name: {person.get('name')}
    Goal: {person.get('goal')}
    Gender: {person.get('gender') or 'not specified'}
    Diet: {person.get('dietary_type')}
    Daily calorie target: {person.get('target_calories')} kcal
    Daily protein target: {person.get('target_protein')}g

    Day: {payload.day}
    Current meals:
    {current_day}

    User feedback:
    {payload.feedback}

    Return ONLY valid JSON:
    {{
      "day": "{payload.day}",
      "calories": 0,
      "protein": 0,
      "portion_note": "short note",
      "meals": [
        {{"type": "Breakfast", "name": "meal", "calories": 0, "protein": 0}},
        {{"type": "Lunch", "name": "meal", "calories": 0, "protein": 0}},
        {{"type": "Dinner", "name": "meal", "calories": 0, "protein": 0}}
      ]
    }}
    """
    try:
        response = openai_client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        import json
        override = json.loads(response.choices[0].message.content)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Person day regeneration failed: {exc}")

    override["day"] = payload.day
    override["status"] = "updated"
    save_person_plan_override(
        plan_id=payload.plan_id,
        person_id=payload.person_id,
        person_name=person.get("name") or "",
        day_name=payload.day,
        override=override,
        feedback=payload.feedback,
    )
    updated_plan = format_saved_plan_for_ui(get_meal_plan(int(payload.plan_id)), user)
    return {"plan": updated_plan, "override": override}


@app.post("/api/plan/regenerate-person-day")
async def api_regenerate_person_day(payload: PersonDayRegenerateRequest):
    return await regenerate_person_day(payload)


# --- Grocery ---

@app.get("/grocery/{plan_id}")
async def get_grocery(plan_id: str):
    plan = get_meal_plan(int(plan_id)) if plan_id.isdigit() else None
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    saved_grocery = get_grocery_list(plan.get("id") or plan_id)
    grocery = format_grocery_groups(saved_grocery.get("items") if saved_grocery else [])
    if not grocery:
        grocery = format_grocery_groups(plan.get("grocery_list") or plan.get("shopping_list") or [])
    if not grocery:
        grocery = grocery_from_day_meals(plan)
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
    return {"history": summarize_weekly_history(hist, user)}


@app.get("/api/history/{user_id}")
async def api_history(user_id: str):
    return await history(user_id)


if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
