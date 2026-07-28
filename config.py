import os
from dotenv import load_dotenv

load_dotenv()

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = "text-embedding-3-small"
LLM_MODEL = "gpt-4o-mini"

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Tavily
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "")

# WhatsApp Cloud API
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN")
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")

# Health goal targets — hardcoded because these are
# standard medical nutrition guidelines, not AI's job
GOAL_TARGETS = {
    "weight_loss": {
        "min_calories": 1200,
        "max_calories": 1500,
        "min_protein": 60,
        "max_protein": 80,
        "description": "Low calorie, moderate protein"
    },
    "muscle_gain": {
        "min_calories": 2000,
        "max_calories": 2500,
        "min_protein": 120,
        "max_protein": 150,
        "description": "High calorie, high protein"
    },
    "maintenance": {
        "min_calories": 1600,
        "max_calories": 2000,
        "min_protein": 80,
        "max_protein": 100,
        "description": "Balanced diet for maintaining weight"
    }
}

# Fixed categories — AI doesn't decide these
DAYS_OF_WEEK = [
    "Monday", "Tuesday", "Wednesday",
    "Thursday", "Friday", "Saturday", "Sunday"
]

DIETARY_TYPES = [
    "vegetarian",
    "vegan",
    "non-vegetarian",
    "pescatarian",
    "keto",
    "eggetarian",
    "diabetic-friendly",
    "gluten-free"
]

# NUTRITION_DB removed — Tavily will search nutrition
# info live per ingredient when needed
