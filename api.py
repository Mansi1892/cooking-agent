import os
import asyncio
import hashlib
import hmac
import json
import secrets
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
import uvicorn

from database import (
    supabase,
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
    clear_user_meal_history,
    create_credit_request,
    list_credit_requests,
    update_credit_request,
    create_support_ticket,
    list_support_tickets,
    update_support_ticket,
    update_plan_status,
    get_user_by_whatsapp_number,
    update_family_member_telegram,
)
from agent import (
    SAFE_MEAL_REPLACEMENTS,
    attach_people_plans,
    feedback_exclusion_instruction,
    generate_meal_plan,
    replace_feedback_exclusions,
    violates_diet,
)
from tools import openai_client, tavily_search
from onboarding_utils import normalize_dietary_type, normalize_family_member
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_BOT_USERNAME, WHATSAPP_VERIFY_TOKEN

app = FastAPI(title="Smart Meal AI API")
GENERATING_USERS = set()
TELEGRAM_SENT_PLAN_IDS = set()
TELEGRAM_PENDING_FEEDBACK = {}
PASSWORD_RESET_TTL_MINUTES = 30
DAYS_BY_FEEDBACK_TOKEN = {
    "mon": "Monday", "monday": "Monday",
    "tue": "Tuesday", "tues": "Tuesday", "tuesday": "Tuesday",
    "wed": "Wednesday", "wednesday": "Wednesday",
    "thu": "Thursday", "thur": "Thursday", "thurs": "Thursday", "thursday": "Thursday",
    "fri": "Friday", "friday": "Friday",
    "sat": "Saturday", "saturday": "Saturday",
    "sun": "Sunday", "sunday": "Sunday",
}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def hash_password(password: str, salt: Optional[str] = None) -> str:
    clean_password = str(password or "")
    if len(clean_password) < 4:
        raise HTTPException(status_code=400, detail="Use at least 4 characters.")
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", clean_password.encode("utf-8"), salt.encode("utf-8"), 120_000).hex()
    return f"pbkdf2_sha256${salt}${digest}"


def verify_password(password: str, stored_hash: Optional[str]) -> bool:
    if not stored_hash or not str(stored_hash).startswith("pbkdf2_sha256$"):
        return False
    try:
        _, salt, expected = str(stored_hash).split("$", 2)
        actual = hash_password(password, salt).split("$", 2)[2]
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def public_profile(user: dict) -> dict:
    clean = dict(user or {})
    clean.pop("password_hash", None)
    clean.pop("password_reset_token", None)
    clean.pop("password_reset_expires_at", None)
    clean["credits"] = get_user_credits(clean)
    clean["role"] = clean.get("role") or "user"
    clean["family"] = get_family_members(clean.get("id"))
    return clean


def build_reset_url(token: str) -> str:
    frontend_url = os.getenv("FRONTEND_PUBLIC_URL") or os.getenv("FRONTEND_DEV_URL") or ""
    base = frontend_url.rstrip("/") or "https://smart-meal-ai-app.vercel.app"
    return f"{base}/reset-password?token={urllib.parse.quote(token)}"


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
    password: Optional[str] = None


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
    password: Optional[str] = None


class ProfileUpdateRequest(UserProfile):
    family: Optional[List[FamilyMember]] = Field(default_factory=list)


class AuthRequest(BaseModel):
    email: str
    password: str
    name: Optional[str] = None


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    password: str


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


class ContactTestPayload(BaseModel):
    value: str = Field(..., min_length=1, max_length=80)


class TelegramConnectRequest(BaseModel):
    user_id: str
    target_type: str = "user"
    family_member_id: Optional[str] = None


async def send_plan_to_telegram_background(telegram_id: str, generated_plan: dict) -> None:
    plan_id = str(generated_plan.get("plan_id") or "")
    recipient_key = str(generated_plan.get("recipient_person_id") or telegram_id)
    sent_key = f"{plan_id}:{telegram_id}:{recipient_key}" if plan_id else ""
    if sent_key and sent_key in TELEGRAM_SENT_PLAN_IDS:
        print(f"Skipping duplicate Telegram send for plan {plan_id} to {telegram_id}")
        return
    if sent_key:
        TELEGRAM_SENT_PLAN_IDS.add(sent_key)
    try:
        from telegram_bot import send_plan_for_approval_async

        await send_plan_for_approval_async(telegram_id, generated_plan)
    except Exception as exc:
        print(f"⚠️ Telegram background send failed: {exc}")


async def send_plan_to_whatsapp_background(whatsapp_number: str, generated_plan: dict) -> bool:
    try:
        from whatsapp_bot import send_plan_for_approval

        sent = bool(await asyncio.to_thread(send_plan_for_approval, whatsapp_number, generated_plan))
        if not sent:
            print("⚠️ WhatsApp plan send returned false")
        return sent
    except Exception as exc:
        print(f"⚠️ WhatsApp background send failed: {exc}")
        return False


def telegram_recipients_for_user(user: dict) -> list[dict]:
    recipients = []
    main_telegram = str(user.get("telegram_id") or "").strip()
    if main_telegram:
        recipients.append({
            "telegram_id": main_telegram,
            "person_id": f"user-{user.get('id')}",
            "name": user.get("name") or "Main profile",
        })
    for member in get_family_members(user.get("id")) or []:
        member_telegram = str(member.get("telegram") or member.get("telegram_id") or "").strip()
        if member_telegram:
            recipients.append({
                "telegram_id": member_telegram,
                "person_id": f"member-{member.get('id') or member.get('name')}",
                "name": member.get("name") or "Family member",
            })
    deduped = {}
    for recipient in recipients:
        deduped[f"{recipient.get('person_id')}:{recipient.get('telegram_id')}"] = recipient
    return list(deduped.values())


def plan_for_telegram_recipient(generated_plan: dict, recipient: dict) -> dict:
    person_id = str(recipient.get("person_id") or "")
    person_plan = next(
        (person for person in generated_plan.get("people_plans", []) if str(person.get("person_id")) == person_id),
        None,
    )
    if not person_plan:
        return generated_plan

    personalized_days = []
    for day in person_plan.get("days") or []:
        meals = {str(meal.get("type") or "").lower(): meal for meal in day.get("meals") or []}
        personalized_days.append({
            "day": day.get("day") or "",
            "breakfast": (meals.get("breakfast") or {}).get("name") or "",
            "breakfast_calories": (meals.get("breakfast") or {}).get("calories") or 0,
            "breakfast_protein": (meals.get("breakfast") or {}).get("protein") or 0,
            "lunch": (meals.get("lunch") or {}).get("name") or "",
            "lunch_calories": (meals.get("lunch") or {}).get("calories") or 0,
            "lunch_protein": (meals.get("lunch") or {}).get("protein") or 0,
            "dinner": (meals.get("dinner") or {}).get("name") or "",
            "dinner_calories": (meals.get("dinner") or {}).get("calories") or 0,
            "dinner_protein": (meals.get("dinner") or {}).get("protein") or 0,
            "total_calories": day.get("calories") or person_plan.get("target_calories") or 0,
            "total_protein": day.get("protein") or person_plan.get("target_protein") or 0,
        })

    personalized = dict(generated_plan)
    personalized["week_plan"] = personalized_days
    personalized["recipient_name"] = recipient.get("name") or person_plan.get("name")
    personalized["recipient_goal"] = person_plan.get("goal")
    personalized["recipient_person_id"] = recipient.get("person_id") or person_plan.get("person_id")
    return personalized


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


def telegram_callback_parts(data: str) -> tuple[str, str]:
    parts = str(data or "").split("_", 2)
    plan_id = parts[1] if len(parts) > 1 else ""
    person_id = parts[2] if len(parts) > 2 else ""
    return plan_id, person_id


def format_day_update_message(day_name: str, result: dict) -> str:
    override = (result or {}).get("override") or {}
    meals = override.get("meals") or []
    lines = [f"Updated {day_name}"]
    for meal in meals:
        meal_type = meal.get("type") or "Meal"
        name = meal.get("name") or ""
        calories = meal.get("calories")
        protein = meal.get("protein")
        suffix = ""
        if calories or protein:
            suffix = f" ({calories or '-'} kcal, {protein or '-'}g protein)"
        lines.append(f"{meal_type}: {name}{suffix}")
    if override.get("calories") or override.get("protein"):
        lines.append(f"{override.get('calories') or '-'} kcal | {override.get('protein') or '-'}g protein")
    return "\n".join(lines)


def feedback_meal_type(text: str) -> Optional[str]:
    tokens = str(text or "").lower().replace("-", " ").replace(",", " ").split()
    if "breakfast" in tokens or "bf" in tokens:
        return "Breakfast"
    if "lunch" in tokens:
        return "Lunch"
    if "dinner" in tokens:
        return "Dinner"
    return None


def meal_requests_soup(text: str) -> bool:
    return "soup" in str(text or "").lower().replace("-", " ").replace(",", " ").split()


def save_person_approval(plan_id: str, person_id: str, status: str) -> None:
    if not person_id:
        update_plan_status(plan_id, status)
        return
    save_person_plan_override(
        plan_id=plan_id,
        person_id=person_id,
        person_name="",
        day_name="__approval__",
        override={"approval_status": status},
        feedback=f"Telegram {status}",
    )


def telegram_review_keyboard(plan_id: str, person_id: str = "") -> str:
    return json.dumps({
        "inline_keyboard": [[
            {"text": "✅ Approve", "callback_data": f"approve_{plan_id}_{person_id or ''}"},
            {"text": "❌ Reject", "callback_data": f"reject_{plan_id}_{person_id or ''}"},
        ]]
    })


def sanitize_person_day_override(override: dict, person: dict, feedback: str, current_day: Optional[dict] = None) -> dict:
    dietary_type = normalize_dietary_type(person.get("dietary_type")) or "normal"
    replacements = SAFE_MEAL_REPLACEMENTS.get(dietary_type) or SAFE_MEAL_REPLACEMENTS.get("vegetarian", {})
    cleaned = {**(override or {})}
    requested_meal = feedback_meal_type(feedback)
    current_meals = {
        str(meal.get("type") or ""): meal
        for meal in ((current_day or {}).get("meals") or [])
    }
    meals = []
    for meal in cleaned.get("meals") or []:
        meal_type = str(meal.get("type") or "Meal")
        key = meal_type.lower()
        if requested_meal and meal_type != requested_meal and meal_type in current_meals:
            meals.append(current_meals[meal_type])
            continue
        meal_name = str(meal.get("name") or "")
        if requested_meal == meal_type and meal_requests_soup(feedback) and "soup" not in meal_name.lower():
            meal_name = "High-protein vegetable soup with paneer and whole grain toast"
        if violates_diet(meal_name, dietary_type):
            meal_name = replacements.get(key, meal_name)
        meal_name = replace_feedback_exclusions(meal_name, [term for term in ("dal", "curd") if term in feedback.lower()])
        meals.append({**meal, "name": meal_name})
    cleaned["meals"] = meals
    if cleaned.get("portion_note"):
        cleaned["portion_note"] = replace_feedback_exclusions(cleaned.get("portion_note"), [term for term in ("dal", "curd") if term in feedback.lower()])
    return cleaned


def feedback_day_name(text: str) -> Optional[str]:
    tokens = str(text or "").lower().replace("-", " ").replace(",", " ").split()
    for token in tokens:
        if token in DAYS_BY_FEEDBACK_TOKEN:
            return DAYS_BY_FEEDBACK_TOKEN[token]
    return None


def telegram_connect_secret() -> bytes:
    return (TELEGRAM_BOT_TOKEN or os.getenv("ADMIN_PASSWORD", "smart-meal-ai")).encode("utf-8")


def sign_telegram_connect(parts: list[str]) -> str:
    raw = ":".join(str(part) for part in parts)
    return hmac.new(telegram_connect_secret(), raw.encode("utf-8"), hashlib.sha256).hexdigest()[:10]


def build_telegram_connect_code(user_id: str, target_type: str = "user", family_member_id: Optional[str] = None) -> str:
    clean_user_id = str(user_id or "").strip()
    clean_target = "family" if target_type == "family" else "user"
    clean_family_id = str(family_member_id or "0").strip() if clean_target == "family" else "0"
    prefix = "smaf" if clean_target == "family" else "smau"
    signature = sign_telegram_connect([prefix, clean_user_id, clean_family_id])
    return f"{prefix}_{clean_user_id}_{clean_family_id}_{signature}"


def parse_telegram_connect_code(code: str) -> Optional[dict]:
    parts = str(code or "").strip().split("_")
    if len(parts) != 4 or parts[0] not in {"smau", "smaf"}:
        return None
    prefix, user_id, family_member_id, signature = parts
    expected = sign_telegram_connect([prefix, user_id, family_member_id])
    if not hmac.compare_digest(signature, expected):
        return None
    return {
        "target_type": "family" if prefix == "smaf" else "user",
        "user_id": user_id,
        "family_member_id": None if family_member_id == "0" else family_member_id,
    }


def telegram_bot_link(code: str) -> str:
    username = str(TELEGRAM_BOT_USERNAME or "").strip().lstrip("@")
    if not username and TELEGRAM_BOT_TOKEN:
        try:
            with urllib.request.urlopen(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe", timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
                username = ((payload.get("result") or {}).get("username") or "").strip()
        except Exception as exc:
            print(f"⚠️ Telegram getMe failed: {exc}")
    if not username:
        raise HTTPException(status_code=500, detail="Telegram bot username could not be detected. Check TELEGRAM_BOT_TOKEN.")
    return f"https://t.me/{username}?start={urllib.parse.quote(code)}"


def handle_telegram_connect(code: str, telegram_id: str, chat_id: str) -> bool:
    parsed = parse_telegram_connect_code(code)
    if not parsed:
        return False
    if parsed["target_type"] == "family":
        member = update_family_member_telegram(parsed["family_member_id"], telegram_id)
        name = member.get("name") if member else "Family member"
        if chat_id:
            telegram_api("sendMessage", {"chat_id": chat_id, "text": f"Telegram connected for {name}. You will receive Smart Meal AI plans here."})
        return bool(member)
    user = update_user(parsed["user_id"], {"telegram_id": telegram_id})
    name = user.get("name") if user else "your profile"
    if chat_id:
        telegram_api("sendMessage", {"chat_id": chat_id, "text": f"Telegram connected for {name}. You will receive Smart Meal AI plans here."})
    return bool(user)


def whatsapp_send_text(whatsapp_number: str, text: str) -> bool:
    try:
        from whatsapp_bot import send_text_message

        return bool(send_text_message(whatsapp_number, text))
    except Exception as exc:
        print(f"⚠️ WhatsApp text send failed: {exc}")
        return False


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
            plan_id, person_id = telegram_callback_parts(data)
            save_person_approval(plan_id, person_id, "approved")
            if chat_id and message_id:
                telegram_api("editMessageReplyMarkup", {"chat_id": chat_id, "message_id": message_id, "reply_markup": json.dumps({"inline_keyboard": []})})
            if chat_id:
                telegram_api("sendMessage", {"chat_id": chat_id, "text": "Meal plan approved for this person. Your browser/app will refresh."})
            return {"ok": True, "action": "approved", "plan_id": plan_id}

        if data.startswith("reject_"):
            plan_id, person_id = telegram_callback_parts(data)
            telegram_key = str(from_user.get("id") or chat_id or "")
            if telegram_key:
                TELEGRAM_PENDING_FEEDBACK[telegram_key] = {"plan_id": plan_id, "person_id": person_id}
            if chat_id:
                telegram_api(
                    "sendMessage",
                    {
                        "chat_id": chat_id,
                        "text": "Plan rejected. Reply with what you want changed.",
                    },
                )
            return {"ok": True, "action": "reject_prompted", "plan_id": plan_id}

    text = str(message.get("text") or "").strip()
    chat = message.get("chat") or {}
    from_user = message.get("from") or {}
    chat_id = chat.get("id") or from_user.get("id")
    telegram_id = str(from_user.get("id") or chat_id or "")

    if text.startswith("/start"):
        parts = text.split(maxsplit=1)
        if len(parts) > 1 and handle_telegram_connect(parts[1], telegram_id, str(chat_id or "")):
            return {"ok": True, "action": "telegram_connected"}
        if chat_id:
            telegram_api("sendMessage", {"chat_id": chat_id, "text": f"Welcome to Smart Meal AI. Your Telegram is ready. Chat ID: {telegram_id}"})
        return {"ok": True, "action": "start"}

    if telegram_id in TELEGRAM_PENDING_FEEDBACK and text and not text.startswith("/"):
        feedback_state = TELEGRAM_PENDING_FEEDBACK.pop(telegram_id)
        plan_id = feedback_state.get("plan_id") if isinstance(feedback_state, dict) else feedback_state
        person_id = feedback_state.get("person_id") if isinstance(feedback_state, dict) else ""
        feedback_text = text
        plan_record = get_meal_plan(plan_id)
        user_id = plan_record.get("user_id")
        if not user_id:
            if chat_id:
                telegram_api("sendMessage", {"chat_id": chat_id, "text": "Could not find the meal plan to update. Please generate a fresh plan."})
            return {"ok": False, "action": "plan_not_found"}
        if chat_id:
            telegram_api("sendMessage", {"chat_id": chat_id, "text": "Regenerating your meal plan with that feedback..."})
        save_feedback(plan_id, "Telegram", 3, feedback_text, True)
        day_name = feedback_day_name(feedback_text)
        if person_id and day_name:
            result = await regenerate_person_day(PersonDayRegenerateRequest(
                user_id=str(user_id),
                plan_id=str(plan_id),
                person_id=str(person_id),
                day=day_name,
                feedback=feedback_text,
            ))
            if chat_id:
                telegram_api("sendMessage", {"chat_id": chat_id, "text": format_day_update_message(day_name, result)})
                telegram_api("sendMessage", {
                    "chat_id": chat_id,
                    "text": "Approve this update?",
                    "reply_markup": telegram_review_keyboard(str(plan_id), str(person_id)),
                })
            return {"ok": True, "action": "person_day_regenerated", "plan_id": plan_id, "day": day_name, "result": result}
        updated_plan = generate_meal_plan(int(user_id), feedback_text)
        if updated_plan.get("status") == "success":
            await send_plan_to_telegram_background(str(chat_id), updated_plan)
            return {"ok": True, "action": "regenerated", "plan_id": updated_plan.get("plan_id")}
        if chat_id:
            telegram_api("sendMessage", {"chat_id": chat_id, "text": f"Could not regenerate plan: {updated_plan.get('message') or 'Unknown error'}"})
        return {"ok": False, "action": "regenerate_failed"}

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


@app.post("/telegram/connect-link")
async def telegram_connect_link(payload: TelegramConnectRequest):
    if not get_user(payload.user_id):
        raise HTTPException(status_code=404, detail="Profile not found")
    if payload.target_type == "family" and not payload.family_member_id:
        raise HTTPException(status_code=400, detail="Family member ID is required")
    code = build_telegram_connect_code(payload.user_id, payload.target_type, payload.family_member_id)
    return {"url": telegram_bot_link(code), "code": code}


@app.post("/api/telegram/connect-link")
async def api_telegram_connect_link(payload: TelegramConnectRequest):
    return await telegram_connect_link(payload)


@app.get("/telegram/bot-link")
async def telegram_open_bot_link():
    return {"url": telegram_bot_link("start")}


@app.get("/api/telegram/bot-link")
async def api_telegram_open_bot_link():
    return await telegram_open_bot_link()


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
    from_number = str(message.get("from") or "")
    button = message.get("button") or {}
    interactive = message.get("interactive") or {}
    button_reply = interactive.get("button_reply") or {}
    text_body = str((message.get("text") or {}).get("body") or "").strip()
    action_id = button_reply.get("id") or button.get("payload") or text_body

    action_text = str(action_id).strip()
    lowered = action_text.lower()

    def latest_plan_id_for_whatsapp() -> str:
        user = get_user_by_whatsapp_number(from_number)
        latest = get_latest_plan(user.get("id")) if user else {}
        return str(latest.get("id") or "").strip()

    if action_text.startswith("approve_") or lowered == "approve" or lowered.startswith("approve "):
        plan_id = action_text.split("_", 1)[1] if action_text.startswith("approve_") else (action_text.split(" ", 1)[1].strip() if " " in action_text else latest_plan_id_for_whatsapp())
        plan_id = "".join(ch for ch in plan_id if ch.isdigit()) or latest_plan_id_for_whatsapp()
        if not plan_id:
            return {"ok": False, "action": "missing_plan_id"}
        update_plan_status(plan_id, "approved")
        if from_number:
            whatsapp_send_text(from_number, "Meal plan approved. Your browser/app will refresh to the approved plan.")
        return {"ok": True, "action": "approved", "plan_id": plan_id}

    if action_text.startswith("reject_") or lowered == "reject" or lowered.startswith("reject "):
        plan_id = action_text.split("_", 1)[1] if action_text.startswith("reject_") else (action_text.split(" ", 1)[1].strip() if " " in action_text else latest_plan_id_for_whatsapp())
        plan_id = "".join(ch for ch in plan_id if ch.isdigit()) or latest_plan_id_for_whatsapp()
        if not plan_id:
            return {"ok": False, "action": "missing_plan_id"}
        if from_number:
            whatsapp_send_text(
                from_number,
                (
                    "Plan rejected. What would you like to change?\n"
                    "Reply like: change make dinner lighter\n"
                    "You can mention meals, spice level, budget, calories, or ingredients to avoid."
                ),
            )
        return {"ok": True, "action": "reject_prompted", "plan_id": plan_id}

    if lowered.startswith("change ") or lowered.startswith("/change "):
        user = get_user_by_whatsapp_number(from_number)
        plan_id = latest_plan_id_for_whatsapp()
        parts = text_body.split(" ", 2)
        if len(parts) >= 3 and parts[1].strip().isdigit():
            plan_id, feedback_text = parts[1].strip(), parts[2].strip()
        else:
            feedback_text = text_body.split(" ", 1)[1].strip() if " " in text_body else ""
        if not feedback_text:
            if from_number:
                whatsapp_send_text(from_number, "Please reply like: change make dinner lighter")
            return {"ok": True, "action": "change_missing_feedback"}

        if not user:
            if from_number:
                whatsapp_send_text(from_number, "User not found for this WhatsApp number. Save your WhatsApp number in Profile and try again.")
            return {"ok": False, "action": "user_not_found"}
        if not plan_id:
            whatsapp_send_text(from_number, "I could not find your latest meal plan. Please generate a new plan first.")
            return {"ok": False, "action": "missing_plan_id"}

        whatsapp_send_text(from_number, "Regenerating your meal plan with that feedback...")
        save_feedback(plan_id, user.get("name") or "WhatsApp", 3, feedback_text, True)
        updated_plan = generate_meal_plan(int(user.get("id")), feedback_text)
        if updated_plan.get("status") == "success":
            await send_plan_to_whatsapp_background(from_number, updated_plan)
            return {"ok": True, "action": "regenerated", "plan_id": updated_plan.get("plan_id")}
        whatsapp_send_text(from_number, f"Could not regenerate plan: {updated_plan.get('message') or 'Unknown error'}")
        return {"ok": False, "action": "regenerate_failed"}

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


# --- Auth ---

@app.post("/auth/signup-check")
async def signup_check(payload: AuthRequest):
    email = str(payload.email or "").strip().lower()
    password = str(payload.password or "")
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email is required.")
    if len(password.strip()) < 4:
        raise HTTPException(status_code=400, detail="Use at least 4 characters.")
    if get_user_by_email(email):
        raise HTTPException(status_code=409, detail="Account already exists. Please login instead.")
    return {"ok": True}


@app.post("/api/auth/signup-check")
async def api_signup_check(payload: AuthRequest):
    return await signup_check(payload)


@app.post("/auth/login")
async def login(payload: AuthRequest):
    email = str(payload.email or "").strip().lower()
    password = str(payload.password or "")
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email is required.")
    if len(password.strip()) < 4:
        raise HTTPException(status_code=400, detail="Use at least 4 characters.")

    user = get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="Account not found. Please sign up first.")

    stored_hash = user.get("password_hash")
    if stored_hash:
        if not verify_password(password, stored_hash):
            raise HTTPException(status_code=401, detail="Incorrect password.")
    else:
        updated = update_user(user.get("id"), {"password_hash": hash_password(password)})
        if not updated:
            raise HTTPException(status_code=500, detail="Password columns are missing. Run supabase_auth_setup.sql in Supabase.")
        user = updated

    return {"profile": public_profile(user)}


@app.post("/api/auth/login")
async def api_login(payload: AuthRequest):
    return await login(payload)


@app.post("/auth/forgot-password")
async def forgot_password(payload: ForgotPasswordRequest):
    email = str(payload.email or "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email is required.")
    user = get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="Account not found. Please sign up first.")

    token = secrets.token_urlsafe(32)
    expires_at = (datetime.utcnow() + timedelta(minutes=PASSWORD_RESET_TTL_MINUTES)).isoformat()
    updated = update_user(user.get("id"), {
        "password_reset_token": token,
        "password_reset_expires_at": expires_at,
    })
    if not updated:
        raise HTTPException(status_code=500, detail="Password reset columns are missing. Run supabase_auth_setup.sql in Supabase.")

    reset_url = build_reset_url(token)
    return {
        "sent": True,
        "reset_url": reset_url,
        "message": "Password reset link generated.",
    }


@app.post("/api/auth/forgot-password")
async def api_forgot_password(payload: ForgotPasswordRequest):
    return await forgot_password(payload)


@app.post("/auth/reset-password")
async def reset_password(payload: ResetPasswordRequest):
    token = str(payload.token or "").strip()
    password = str(payload.password or "")
    if not token:
        raise HTTPException(status_code=400, detail="Reset token is missing.")
    if len(password.strip()) < 4:
        raise HTTPException(status_code=400, detail="Use at least 4 characters.")

    try:
        result = (
            supabase.table("users")
            .select("*")
            .eq("password_reset_token", token)
            .limit(1)
            .execute()
        )
        users = result.data or []
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Password reset lookup failed: {exc}")

    if not users:
        raise HTTPException(status_code=400, detail="Reset link is invalid or already used.")

    user = users[0]
    expires_raw = user.get("password_reset_expires_at")
    try:
        expires_at = datetime.fromisoformat(str(expires_raw).replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        expires_at = datetime.utcnow() - timedelta(seconds=1)
    if expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Reset link has expired. Please request a new one.")

    updated = update_user(user.get("id"), {
        "password_hash": hash_password(password),
        "password_reset_token": None,
        "password_reset_expires_at": None,
    })
    if not updated:
        raise HTTPException(status_code=500, detail="Password reset failed. Run supabase_auth_setup.sql in Supabase.")
    return {"ok": True}


@app.post("/api/auth/reset-password")
async def api_reset_password(payload: ResetPasswordRequest):
    return await reset_password(payload)


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
    password = str(user_data.get("password") or "").strip()

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
        auth_fields={"password_hash": hash_password(password)} if password else None,
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
        "people_plans": attach_people_plans({"week_plan": day_rows, "status": plan.get("status", "planned")}, user).get("people_plans", []),
    }
    return apply_person_plan_overrides(formatted)


def apply_person_plan_overrides(plan: dict) -> dict:
    plan_id = str(plan.get("id") or "")
    if not plan_id:
        return plan
    overrides = get_person_plan_overrides(plan_id)
    if not overrides:
        return plan
    approvals = {
        str(item.get("person_id") or ""): (item.get("override") or {}).get("approval_status")
        for item in overrides
        if str(item.get("day_name") or "") == "__approval__"
    }
    lookup = {
        (str(item.get("person_id") or ""), str(item.get("day_name") or "")): item.get("override") or {}
        for item in overrides
        if str(item.get("day_name") or "") != "__approval__"
    }
    for person in plan.get("people_plans") or []:
        person_id = str(person.get("person_id") or "")
        person_status = approvals.get(person_id)
        if person_status:
            person["status"] = person_status
        for index, day in enumerate(person.get("days") or []):
            override = lookup.get((person_id, str(day.get("day") or "")))
            if override:
                merged = {**day, **override, "status": person_status or "updated"}
                person["days"][index] = merged
            elif person_status:
                person["days"][index] = {**day, "status": person_status}
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


def friendly_whatsapp_error(raw_error: str) -> str:
    error_text = str(raw_error or "")
    lower = error_text.lower()
    if "recipient phone number not in allowed list" in lower or "131030" in lower:
        return "This WhatsApp number is not in Meta's allowed test recipient list. Add this family member number in Meta WhatsApp API testing recipients, then try Connect again."
    if "phone_number_id" in lower or "unsupported post request" in lower:
        return "WhatsApp Phone Number ID looks incorrect. Use Meta's Phone Number ID, not your phone number."
    if "access token" in lower or "oauth" in lower:
        return "WhatsApp access token was rejected or expired. Generate a fresh Meta token and update .env/Vercel."
    return "WhatsApp message was not sent. Check Meta token, phone number ID, and test recipient setup."


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

        telegram_recipients = telegram_recipients_for_user(user)
        whatsapp_number = str(user.get("whatsapp_number") or "").strip()
        whatsapp_sent = False
        needs_external_approval = bool(telegram_recipients or whatsapp_number)
        if needs_external_approval:
            plan["status"] = "pending"
            for day in plan.get("days") or []:
                day["status"] = "pending"
            for person in plan.get("people_plans") or []:
                person["status"] = "pending"
                for day in person.get("days") or []:
                    day["status"] = "pending"
            if whatsapp_number:
                whatsapp_sent = await send_plan_to_whatsapp_background(whatsapp_number, generated_plan)
            for recipient in telegram_recipients:
                telegram_id = recipient.get("telegram_id")
                personalized_plan = plan_for_telegram_recipient(generated_plan, recipient)
                print(f"Queueing Telegram plan {generated_plan.get('plan_id')} for {recipient.get('name')} at {telegram_id}")
                asyncio.create_task(send_plan_to_telegram_background(telegram_id, personalized_plan))
        else:
            plan_id = str(generated_plan.get("plan_id") or plan.get("id") or "").strip()
            if plan_id:
                update_plan_status(plan_id, "approved")
            plan["status"] = "approved"
            for day in plan.get("days") or []:
                day["status"] = "approved"

        return {
            "plan": plan,
            "telegram_queued": bool(telegram_recipients),
            "telegram_recipient_count": len(telegram_recipients),
            "whatsapp_queued": bool(whatsapp_number),
            "whatsapp_sent": whatsapp_sent,
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


@app.post("/telegram/test-contact")
async def telegram_test_contact(payload: ContactTestPayload):
    telegram_id = str(payload.value or "").strip()
    if not telegram_id:
        raise HTTPException(status_code=400, detail="Telegram chat ID is required.")
    try:
        from telegram_bot import send_test_message_async

        sent = bool(await send_test_message_async(telegram_id))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Telegram test failed: {exc}")
    if not sent:
        raise HTTPException(status_code=400, detail="Telegram message was not sent. Check chat ID and make sure you started the bot.")
    return {"sent": True}


@app.post("/api/telegram/test-contact")
async def api_telegram_test_contact(payload: ContactTestPayload):
    return await telegram_test_contact(payload)


@app.post("/whatsapp/test/{user_id}")
async def whatsapp_test(user_id: str):
    user = get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    whatsapp_number = str(user.get("whatsapp_number") or "").strip()
    if not whatsapp_number:
        raise HTTPException(status_code=400, detail=f"WhatsApp number is not added in backend profile for user {user_id}. Save WhatsApp again.")
    try:
        from whatsapp_bot import get_last_whatsapp_error, get_whatsapp_config_error, send_test_message

        config_error = get_whatsapp_config_error()
        if config_error:
            raise HTTPException(status_code=400, detail=config_error)
        sent = bool(await asyncio.to_thread(send_test_message, whatsapp_number))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"WhatsApp test failed: {exc}")
    if not sent:
        raise HTTPException(status_code=400, detail=friendly_whatsapp_error(get_last_whatsapp_error()))
    return {"sent": True}


@app.post("/api/whatsapp/test/{user_id}")
async def api_whatsapp_test(user_id: str):
    return await whatsapp_test(user_id)


@app.post("/whatsapp/test-contact")
async def whatsapp_test_contact(payload: ContactTestPayload):
    whatsapp_number = "".join(ch for ch in str(payload.value or "") if ch.isdigit())
    if not whatsapp_number:
        raise HTTPException(status_code=400, detail="WhatsApp number is required.")
    if len(whatsapp_number) < 10:
        raise HTTPException(status_code=400, detail="Enter WhatsApp number with country code, no + or spaces.")
    try:
        from whatsapp_bot import get_last_whatsapp_error, get_whatsapp_config_error, send_test_message

        config_error = get_whatsapp_config_error()
        if config_error:
            raise HTTPException(status_code=400, detail=config_error)
        sent = bool(await asyncio.to_thread(send_test_message, whatsapp_number))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"WhatsApp test failed: {exc}")
    if not sent:
        raise HTTPException(status_code=400, detail=friendly_whatsapp_error(get_last_whatsapp_error()))
    return {"sent": True}


@app.post("/api/whatsapp/test-contact")
async def api_whatsapp_test_contact(payload: ContactTestPayload):
    return await whatsapp_test_contact(payload)


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
    requested_meal = feedback_meal_type(payload.feedback)
    meal_scope_instruction = (
        f"Only change {requested_meal}. Keep the other meals exactly the same as current meals."
        if requested_meal
        else "You may adjust the full day if needed."
    )

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
    {feedback_exclusion_instruction(payload.feedback)}

    Hard rules:
    - {meal_scope_instruction}
    - If the user asks for soup for a specific meal, that exact meal must be soup.
    - Follow the person's diet exactly. Vegetarian must not include fish, chicken, meat, seafood, or eggs unless diet is eggetarian.
    - If feedback excludes an ingredient, do not include that ingredient or synonyms in any meal or portion note.

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
        override = sanitize_person_day_override(override, person, payload.feedback, current_day)
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


@app.delete("/history/{user_id}")
async def clear_history(user_id: str):
    user = get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return clear_user_meal_history(user_id)


@app.delete("/api/history/{user_id}")
async def api_clear_history(user_id: str):
    return await clear_history(user_id)


if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
