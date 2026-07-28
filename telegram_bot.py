import asyncio
import json
import logging
import os
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Optional
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import Application, CallbackContext, CallbackQueryHandler, MessageHandler, filters, CommandHandler

from config import TELEGRAM_BOT_TOKEN
from database import (
    get_user,
    get_user_by_telegram_id,
    save_feedback,
    get_meal_plan,
    save_person_plan_override,
    update_plan_status,
    save_grocery_list,
)
from agent import handle_feedback, generate_meal_plan

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global state for pending feedback
pending_feedback = {}
DAYS = {
    "mon": "Monday", "monday": "Monday",
    "tue": "Tuesday", "tues": "Tuesday", "tuesday": "Tuesday",
    "wed": "Wednesday", "wednesday": "Wednesday",
    "thu": "Thursday", "thur": "Thursday", "thurs": "Thursday", "thursday": "Thursday",
    "fri": "Friday", "friday": "Friday",
    "sat": "Saturday", "saturday": "Saturday",
    "sun": "Sunday", "sunday": "Sunday",
}


def _is_numeric_chat_id(telegram_id: str) -> bool:
    text = str(telegram_id or "").strip()
    return text.lstrip("-").isdigit()


def _run_async(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, coro).result()


def _callback_parts(callback_data: str) -> tuple[str, str]:
    parts = str(callback_data or "").split("_", 2)
    plan_id = parts[1] if len(parts) > 1 else ""
    person_id = parts[2] if len(parts) > 2 else ""
    return plan_id, person_id


def _feedback_day(text: str) -> Optional[str]:
    lowered = str(text or "").lower()
    for key, day in DAYS.items():
        if key in lowered.split() or key in lowered.replace("-", " ").replace(",", " ").split():
            return day
    return None


def _regenerate_person_day_via_api(user_id: str, plan_id: str, person_id: str, day: str, feedback: str) -> Dict[str, Any]:
    base_url = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000").rstrip("/")
    payload = json.dumps({
        "user_id": str(user_id),
        "plan_id": str(plan_id),
        "person_id": str(person_id),
        "day": day,
        "feedback": feedback,
    }).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}/plan/regenerate-person-day",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.loads(response.read().decode("utf-8"))


def _format_day_update(day_name: str, result: Dict[str, Any]) -> str:
    override = (result or {}).get("override") or {}
    meals = override.get("meals") or []
    lines = [f"✅ Updated {day_name}"]
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


def _save_person_approval(plan_id: str, person_id: str, status: str) -> None:
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


async def _send_person_review_buttons(message, plan_id: str, person_id: str) -> None:
    keyboard = [[
        InlineKeyboardButton("✅ Approve", callback_data=f"approve_{plan_id}_{person_id or ''}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"reject_{plan_id}_{person_id or ''}"),
    ]]
    await message.reply_text(
        "Approve this update?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def _safe_remove_reply_markup(query) -> None:
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except BadRequest as exc:
        if "Message is not modified" in str(exc):
            logger.info("Telegram reply markup already unchanged")
            return
        raise


def format_meal_plan_message(plan: Dict[str, Any]) -> str:
    """
    Format a meal plan dictionary as a readable Telegram message.
    
    Args:
        plan: Dictionary containing meal plan data
    
    Returns:
        Formatted message string
    """
    if isinstance(plan, dict):
        if "error" in plan or "status" in plan and plan["status"] == "error":
            return f"❌ Error generating plan: {plan.get('message', 'Unknown error')}"
        
        plan_data = plan.get("plan", plan)
    else:
        plan_data = plan

    recipient_name = plan.get("recipient_name") if isinstance(plan, dict) else ""
    recipient_goal = plan.get("recipient_goal") if isinstance(plan, dict) else ""
    heading = f"Your 7-Day Meal Plan for {recipient_name}" if recipient_name else "Your 7-Day Meal Plan"
    if recipient_goal:
        heading += f" ({str(recipient_goal).replace('_', ' ')})"
    message_lines = [f"{heading}\n"]

    days = []
    if isinstance(plan_data, dict):
        days = plan_data.get("days") or plan_data.get("week_plan") or []
    
    if days:
        for day in days:
            day_name = day.get("day_name") or day.get("day", "Unknown")
            message_lines.append(f"\n{day_name}")
            message_lines.append(f"Breakfast: {day.get('breakfast', 'N/A')}")
            message_lines.append(f"Lunch: {day.get('lunch', 'N/A')}")
            message_lines.append(f"Dinner: {day.get('dinner', 'N/A')}")
            
            calories = day.get("total_calories", 0)
            protein = day.get("total_protein", 0)
            if calories > 0:
                message_lines.append(f"{calories} kcal | {protein}g protein")
    else:
        if isinstance(plan_data, str):
            message_lines.append(plan_data)
        else:
            message_lines.append(str(plan_data))

    message_lines.append("\n\nPlease review and provide feedback:")
    return "\n".join(message_lines)


async def send_plan_for_approval_async(telegram_id: str, plan: Dict[str, Any]) -> Optional[int]:
    """
    Send a formatted meal plan to user's Telegram with Approve/Reject buttons.
    
    Args:
        telegram_id: User's Telegram ID
        plan: Meal plan dictionary
    
    Returns:
        Message ID if sent, None otherwise
    """
    try:
        if not TELEGRAM_BOT_TOKEN:
            logger.warning("Telegram bot token is not configured; skipping plan send")
            return None
        if not _is_numeric_chat_id(telegram_id):
            logger.warning("Telegram chat ID must be numeric. Got: %s", telegram_id)
            return None

        from telegram import Bot
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        
        message_text = format_meal_plan_message(plan)
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"approve_{plan.get('plan_id', 'unknown')}_{plan.get('recipient_person_id', '')}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_{plan.get('plan_id', 'unknown')}_{plan.get('recipient_person_id', '')}"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = None
        for attempt in range(2):
            try:
                message = await bot.send_message(
                    chat_id=int(telegram_id),
                    text=message_text,
                    reply_markup=reply_markup,
                    connect_timeout=30,
                    read_timeout=30,
                    write_timeout=30,
                    pool_timeout=30,
                )
                break
            except Exception as exc:
                if attempt == 0 and "timed out" in str(exc).lower():
                    logger.warning("Telegram send timed out for %s; retrying once", telegram_id)
                    await asyncio.sleep(2)
                    continue
                raise
        if not message:
            return None
        
        logger.info(f"✅ Meal plan sent to {telegram_id}, message_id: {message.message_id}")
        return message.message_id
        
    except Exception as exc:
        logger.error(f"❌ Error sending plan to {telegram_id}: {exc}")
        return None


def send_plan_for_approval(telegram_id: str, plan: Dict[str, Any]) -> Optional[int]:
    return _run_async(send_plan_for_approval_async(telegram_id, plan))


async def send_test_message_async(telegram_id: str) -> bool:
    try:
        if not TELEGRAM_BOT_TOKEN:
            logger.warning("Telegram bot token is not configured; skipping test send")
            return False
        if not _is_numeric_chat_id(telegram_id):
            logger.warning("Telegram chat ID must be numeric. Got: %s", telegram_id)
            return False

        from telegram import Bot
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        await bot.send_message(
            chat_id=int(telegram_id),
            text="Smart Meal AI test message received. Telegram is connected.",
        )
        logger.info("Telegram test message sent to %s", telegram_id)
        return True
    except Exception as exc:
        logger.error("Telegram test send failed for %s: %s", telegram_id, exc)
        return False


def send_test_message(telegram_id: str) -> bool:
    return _run_async(send_test_message_async(telegram_id))


async def send_grocery_list_async(telegram_id: str, grocery_list: list) -> bool:
    """
    Send a formatted grocery list to user's Telegram.
    
    Args:
        telegram_id: User's Telegram ID
        grocery_list: List of grocery items
    
    Returns:
        True if sent successfully, False otherwise
    """
    try:
        if not TELEGRAM_BOT_TOKEN:
            logger.warning("Telegram bot token is not configured; skipping grocery send")
            return False
        if not _is_numeric_chat_id(telegram_id):
            logger.warning("Telegram chat ID must be numeric. Got: %s", telegram_id)
            return False

        from telegram import Bot
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        
        message_lines = ["Grocery List\n"]
        
        categories = {
            "vegetables": [],
            "proteins": [],
            "grains": [],
            "spices": [],
            "dairy": [],
        }
        
        for item in grocery_list:
            item_lower = item.lower()
            added = False
            for category in categories:
                if category in item_lower:
                    categories[category].append(item)
                    added = True
                    break
            if not added:
                categories["vegetables"].append(item)
        
        for category, items in categories.items():
            if items:
                message_lines.append(f"\n{category.title()}")
                for item in items:
                    message_lines.append(f"  • {item}")
        
        message_text = "\n".join(message_lines)
        
        await bot.send_message(
            chat_id=int(telegram_id),
            text=message_text
        )
        
        logger.info(f"✅ Grocery list sent to {telegram_id}")
        return True
        
    except Exception as exc:
        logger.error(f"❌ Error sending grocery list to {telegram_id}: {exc}")
        return False


def send_grocery_list(telegram_id: str, grocery_list: list) -> bool:
    return _run_async(send_grocery_list_async(telegram_id, grocery_list))


async def handle_approval_callback(update: Update, context: CallbackContext) -> None:
    """
    Handle when user taps Approve or Reject button.
    
    Args:
        update: Telegram update object
        context: Callback context
    """
    query = update.callback_query
    try:
        await query.answer()
    except BadRequest as exc:
        if "Query is too old" in str(exc):
            logger.warning("Ignoring expired Telegram callback query")
            return
        raise
    
    callback_data = query.data
    telegram_id = str(query.from_user.id)
    logger.info("Telegram callback received from %s: %s", telegram_id, callback_data)
    
    if callback_data.startswith("approve_"):
        plan_id, person_id = _callback_parts(callback_data)
        
        try:
            _save_person_approval(plan_id, person_id, "approved")
            await _safe_remove_reply_markup(query)
            await query.message.reply_text("Meal plan approved for this person.")
            logger.info(f"✅ Plan {plan_id} approved by {telegram_id} for person {person_id}")
        except Exception as exc:
            logger.error(f"❌ Error approving plan: {exc}")
            await query.message.reply_text(f"Error approving plan: {exc}")
    
    elif callback_data.startswith("reject_"):
        plan_id, person_id = _callback_parts(callback_data)
        
        pending_feedback[telegram_id] = {
            "plan_id": plan_id,
            "person_id": person_id,
            "state": "awaiting_feedback"
        }
        
        try:
            await _safe_remove_reply_markup(query)
        except BadRequest as exc:
            logger.warning("Could not remove reject buttons: %s", exc)
        await query.message.reply_text("Plan rejected. Reply with what you want changed.")
        
        logger.info(f"Plan {plan_id} rejected by {telegram_id}, awaiting feedback")


async def handle_feedback_message(update: Update, context: CallbackContext) -> None:
    """
    Handle text feedback from user after rejection.
    
    Args:
        update: Telegram update object
        context: Callback context
    """
    telegram_id = str(update.message.from_user.id)
    feedback_text = update.message.text
    
    if telegram_id not in pending_feedback:
        return
    
    feedback_state = pending_feedback.get(telegram_id)
    if feedback_state.get("state") != "awaiting_feedback":
        return
    
    plan_id = feedback_state.get("plan_id")
    person_id = feedback_state.get("person_id")
    
    try:
        plan_record = get_meal_plan(plan_id)
        user_id = plan_record.get("user_id")
        if not user_id:
            user = get_user_by_telegram_id(telegram_id)
            user_id = user.get("id") if user else None
        if not user_id:
            await update.message.reply_text("❌ Meal plan not found. Please generate a fresh plan.")
            return

        feedback_data = {
            "plan_id": plan_id,
            "user_id": user_id,
            "feedback_text": feedback_text,
            "rejected_days": [],
            "comments": feedback_text,
        }
        
        save_feedback(plan_id, "User", 3, feedback_text, True)
        
        await update.message.reply_text("⏳ Regenerating meal plan based on your feedback...")

        day_name = _feedback_day(feedback_text)
        if person_id and day_name:
            result = _regenerate_person_day_via_api(str(user_id), str(plan_id), str(person_id), day_name, feedback_text)
            await update.message.reply_text(_format_day_update(day_name, result))
            await _send_person_review_buttons(update.message, str(plan_id), str(person_id))
            del pending_feedback[telegram_id]
            return
        
        updated_result = generate_meal_plan(int(user_id), feedback_text)
        
        if updated_result.get("status") == "success":
            await update.message.reply_text("✅ Meal plan regenerated! Sending updated plan...")
            
            await send_plan_for_approval_async(telegram_id, updated_result)
        else:
            await update.message.reply_text(f"❌ Error regenerating plan: {updated_result.get('message')}")
        
        del pending_feedback[telegram_id]
        logger.info(f"✅ Feedback from {telegram_id} processed, plan regenerated")
        
    except Exception as exc:
        logger.error(f"❌ Error handling feedback: {exc}")
        await update.message.reply_text(f"❌ Error processing feedback: {exc}")
        if telegram_id in pending_feedback:
            del pending_feedback[telegram_id]


async def start_command(update: Update, context: CallbackContext) -> None:
    """Handle /start command."""
    chat_id = update.effective_chat.id if update.effective_chat else update.message.from_user.id
    await update.message.reply_text(
        "Welcome to Smart Meal AI.\n\n"
        "Use this Telegram chat ID in the app:\n"
        f"{chat_id}\n\n"
        "Paste it into the Telegram chat ID field, then tap Send test.",
    )


async def help_command(update: Update, context: CallbackContext) -> None:
    """Handle /help command."""
    await update.message.reply_text(
        "📚 **Available Commands**\n\n"
        "/start - Start the bot\n"
        "/onboard - Begin onboarding process\n"
        "/help - Show this help message\n\n"
        "**How it works:**\n"
        "1. Use /onboard to provide your family details\n"
        "2. I'll generate a personalized 7-day meal plan\n"
        "3. Approve or reject the plan\n"
        "4. Provide feedback if needed for regeneration"
    )


def start_bot() -> None:
    """
    Start the Telegram bot with all handlers registered.
    Runs polling to listen for updates.
    """
    try:
        if not TELEGRAM_BOT_TOKEN:
            raise RuntimeError("TELEGRAM_BOT_TOKEN not found in .env")
        
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("help", help_command))
        
        application.add_handler(CallbackQueryHandler(handle_approval_callback))
        
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_feedback_message))
        
        logger.info("🚀 Starting Telegram bot polling...")
        application.run_polling(drop_pending_updates=True)
        
    except Exception as exc:
        logger.error(f"❌ Error starting bot: {exc}")
        raise


if __name__ == "__main__":
    start_bot()
