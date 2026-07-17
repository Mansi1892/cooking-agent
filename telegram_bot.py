import asyncio
import logging
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

    message_lines = ["Your 7-Day Meal Plan\n"]

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
                InlineKeyboardButton("✅ Approve", callback_data=f"approve_{plan.get('plan_id', 'unknown')}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_{plan.get('plan_id', 'unknown')}"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = await bot.send_message(
            chat_id=int(telegram_id),
            text=message_text,
            reply_markup=reply_markup
        )
        
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
        plan_id = callback_data.split("_", 1)[1]
        
        try:
            update_plan_status(plan_id, "approved")
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text("Meal plan approved. Your plan is now finalized.")
            logger.info(f"✅ Plan {plan_id} approved by {telegram_id}")
        except Exception as exc:
            logger.error(f"❌ Error approving plan: {exc}")
            await query.message.reply_text(f"Error approving plan: {exc}")
    
    elif callback_data.startswith("reject_"):
        plan_id = callback_data.split("_", 1)[1]
        
        pending_feedback[telegram_id] = {
            "plan_id": plan_id,
            "state": "awaiting_feedback"
        }
        
        await query.edit_message_text(
            text="❌ Plan rejected. Please type what you'd like to change:",
        )
        
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
    
    try:
        user = get_user_by_telegram_id(telegram_id)
        if not user:
            await update.message.reply_text("❌ User not found. Please start onboarding first.")
            return
        
        user_id = user.get("id", telegram_id)
        
        feedback_data = {
            "plan_id": plan_id,
            "user_id": user_id,
            "feedback_text": feedback_text,
            "rejected_days": [],
            "comments": feedback_text,
        }
        
        save_feedback(plan_id, "User", 3, feedback_text, True)
        
        await update.message.reply_text("⏳ Regenerating meal plan based on your feedback...")
        
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
        "🍽️ Welcome to the AI Meal Planner Bot!\n\n"
        "I'll help you review and approve your weekly meal plans.\n\n"
        f"Your Telegram chat ID is: `{chat_id}`\n"
        "Copy this number into the app's Telegram field.\n\n"
        "Use /help for more commands.",
        parse_mode="Markdown",
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
