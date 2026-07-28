import json
import logging
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from config import WHATSAPP_ACCESS_TOKEN, WHATSAPP_PHONE_NUMBER_ID
logger = logging.getLogger(__name__)
LAST_WHATSAPP_ERROR = ""


def _normalize_phone_number(phone_number: str) -> str:
    return "".join(ch for ch in str(phone_number or "") if ch.isdigit())


def _send_whatsapp_payload(payload: Dict[str, Any], action_label: str, recipient: str) -> bool:
    global LAST_WHATSAPP_ERROR
    LAST_WHATSAPP_ERROR = ""
    request = urllib.request.Request(
        f"https://graph.facebook.com/v25.0/{WHATSAPP_PHONE_NUMBER_ID}/messages",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8", errors="replace")
        logger.info("WhatsApp %s sent to %s: %s", action_label, recipient, body)
        return True
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        LAST_WHATSAPP_ERROR = body
        logger.error("WhatsApp %s failed for %s: HTTP %s %s", action_label, recipient, exc.code, body)
        return False
    except Exception as exc:
        LAST_WHATSAPP_ERROR = str(exc)
        logger.error("WhatsApp %s failed for %s: %s", action_label, recipient, exc)
        return False


def get_last_whatsapp_error() -> str:
    return LAST_WHATSAPP_ERROR


def get_whatsapp_config_error() -> Optional[str]:
    if not WHATSAPP_ACCESS_TOKEN:
        return "WHATSAPP_ACCESS_TOKEN is missing."
    if not WHATSAPP_PHONE_NUMBER_ID:
        return "WHATSAPP_PHONE_NUMBER_ID is missing."
    phone_number_id = _normalize_phone_number(WHATSAPP_PHONE_NUMBER_ID)
    if phone_number_id != str(WHATSAPP_PHONE_NUMBER_ID).strip():
        return "WHATSAPP_PHONE_NUMBER_ID must contain only digits from Meta."
    if len(phone_number_id) <= 10:
        return "WHATSAPP_PHONE_NUMBER_ID looks like a phone number. Use Meta's Phone Number ID from WhatsApp API setup."
    return None


def format_whatsapp_plan_message(plan: Dict[str, Any]) -> str:
    plan_data = plan.get("plan", plan) if isinstance(plan, dict) else {}
    days = _extract_plan_days(plan_data)
    summary = plan_data.get("week_summary") or {}
    grocery_estimate = plan_data.get("grocery_estimate") or {}
    day_count = max(len(days), 1)
    avg_calories = summary.get("avg_calories") or round(sum(float(day.get("calories") or day.get("total_calories") or 0) for day in days) / day_count)
    avg_protein = summary.get("avg_protein") or round(sum(float(day.get("protein") or day.get("total_protein") or 0) for day in days) / day_count)
    grocery_total = summary.get("total_budget") or grocery_estimate.get("total_cost") or plan_data.get("estimated_cost")
    if not grocery_total:
        try:
            from database import get_grocery_list

            plan_id = plan_data.get("plan_id") or plan_data.get("id") or plan.get("plan_id")
            grocery_total = (get_grocery_list(plan_id) or {}).get("estimated_cost")
        except Exception:
            grocery_total = None
    grocery_total = grocery_total or "-"
    lines = [
        "Smart Meal AI weekly plan",
        "",
        f"Avg calories: {avg_calories or '-'} kcal/day",
        f"Avg protein: {avg_protein or '-'}g/day",
        f"Est. groceries: ₹{grocery_total}",
    ]
    return "\n".join(lines)


def _extract_plan_days(plan_data: Dict[str, Any]) -> list[Dict[str, Any]]:
    raw_days = plan_data.get("days") or plan_data.get("week_plan") or plan_data.get("day_meals") or []
    days = []
    for day in raw_days:
        meals = day.get("meals") or []
        meal_by_type = {str(meal.get("type") or "").lower(): meal for meal in meals if isinstance(meal, dict)}
        days.append({
            **day,
            "day": day.get("day") or day.get("day_name") or "Day",
            "breakfast": day.get("breakfast") or (meal_by_type.get("breakfast") or {}).get("name") or "Breakfast",
            "lunch": day.get("lunch") or (meal_by_type.get("lunch") or {}).get("name") or "Lunch",
            "dinner": day.get("dinner") or (meal_by_type.get("dinner") or {}).get("name") or "Dinner",
            "calories": day.get("calories") or day.get("total_calories") or 0,
            "protein": day.get("protein") or day.get("total_protein") or 0,
        })
    return days


def format_whatsapp_day_messages(plan: Dict[str, Any]) -> list[str]:
    plan_data = plan.get("plan", plan) if isinstance(plan, dict) else {}
    days = _extract_plan_days(plan_data)
    messages = []
    for day in days[:7]:
        day_name = day.get("day_name") or day.get("day") or "Day"
        breakfast = day.get("breakfast") or "Breakfast"
        lunch = day.get("lunch") or "Lunch"
        dinner = day.get("dinner") or "Dinner"
        calories = day.get("total_calories") or day.get("calories") or 0
        protein = day.get("total_protein") or day.get("protein") or 0
        messages.append(
            "\n".join(
                [
                    day_name,
                    f"Breakfast: {breakfast}",
                    f"Lunch: {lunch}",
                    f"Dinner: {dinner}",
                    f"{calories} kcal | {protein}g protein",
                ]
            )
        )
    return messages


def send_plan_for_approval(whatsapp_number: str, plan: Dict[str, Any]) -> bool:
    config_error = get_whatsapp_config_error()
    if config_error:
        logger.warning("WhatsApp credentials are not configured correctly; %s", config_error)
        return False

    recipient = _normalize_phone_number(whatsapp_number)
    if not recipient:
        logger.warning("WhatsApp number is empty; skipping plan send")
        return False

    plan_id = str(plan.get("plan_id") or plan.get("id") or "unknown")
    message_text = format_whatsapp_plan_message(plan)

    notice_payload = {
        "messaging_product": "whatsapp",
        "to": recipient,
        "type": "text",
        "text": {"body": message_text},
    }
    notice_sent = _send_whatsapp_payload(notice_payload, "plan notice", recipient)
    day_sent = False
    for day_message in format_whatsapp_day_messages(plan):
        day_sent = _send_whatsapp_payload(
            {
                "messaging_product": "whatsapp",
                "to": recipient,
                "type": "text",
                "text": {"body": day_message},
            },
            "plan day",
            recipient,
        ) or day_sent
    action_sent = _send_whatsapp_payload(
        {
            "messaging_product": "whatsapp",
            "to": recipient,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": "Would you like to use this weekly meal plan?"},
                "action": {
                    "buttons": [
                        {
                            "type": "reply",
                            "reply": {"id": f"approve_{plan_id}", "title": "Approve"},
                        },
                        {
                            "type": "reply",
                            "reply": {"id": f"reject_{plan_id}", "title": "Reject"},
                        },
                    ]
                },
            },
        },
        "plan action buttons",
        recipient,
    )
    return notice_sent or day_sent or action_sent


def send_test_message(whatsapp_number: str) -> bool:
    config_error = get_whatsapp_config_error()
    if config_error:
        logger.warning("WhatsApp credentials are not configured correctly; %s", config_error)
        return False

    recipient = _normalize_phone_number(whatsapp_number)
    if not recipient:
        logger.warning("WhatsApp number is empty; skipping test send")
        return False

    payload = {
        "messaging_product": "whatsapp",
        "to": recipient,
        "type": "text",
        "text": {"body": "Smart Meal AI WhatsApp test message. Your number is connected."},
    }
    return _send_whatsapp_payload(payload, "test message", recipient)


def send_text_message(whatsapp_number: str, text: str) -> bool:
    config_error = get_whatsapp_config_error()
    if config_error:
        logger.warning("WhatsApp credentials are not configured correctly; %s", config_error)
        return False

    recipient = _normalize_phone_number(whatsapp_number)
    if not recipient:
        logger.warning("WhatsApp number is empty; skipping text send")
        return False

    payload = {
        "messaging_product": "whatsapp",
        "to": recipient,
        "type": "text",
        "text": {"body": str(text or "")[:4000]},
    }
    return _send_whatsapp_payload(payload, "text message", recipient)
