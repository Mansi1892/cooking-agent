import json
import logging
import urllib.request
from typing import Any, Dict

from config import WHATSAPP_ACCESS_TOKEN, WHATSAPP_PHONE_NUMBER_ID
from telegram_bot import format_meal_plan_message

logger = logging.getLogger(__name__)


def _normalize_phone_number(phone_number: str) -> str:
    return "".join(ch for ch in str(phone_number or "") if ch.isdigit())


def send_plan_for_approval(whatsapp_number: str, plan: Dict[str, Any]) -> bool:
    if not WHATSAPP_ACCESS_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        logger.warning("WhatsApp credentials are not configured; skipping plan send")
        return False

    recipient = _normalize_phone_number(whatsapp_number)
    if not recipient:
        logger.warning("WhatsApp number is empty; skipping plan send")
        return False

    plan_id = str(plan.get("plan_id") or plan.get("id") or "unknown")
    message_text = format_meal_plan_message(plan)
    if len(message_text) > 950:
        message_text = message_text[:947] + "..."

    payload = {
        "messaging_product": "whatsapp",
        "to": recipient,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": message_text},
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
    }
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
            response.read()
        logger.info("WhatsApp meal plan sent to %s", recipient)
        return True
    except Exception as exc:
        logger.error("WhatsApp meal plan send failed for %s: %s", recipient, exc)
        return False

