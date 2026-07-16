# AI Meal Planner

An AI-powered meal-planning application that helps users create personalized weekly meal plans for Indian households using a LangChain-based RAG agent, FastAPI backend services, Supabase persistence, and a React/Vite frontend.

## 1. Overview

This project combines:
- a Python FastAPI backend for onboarding, meal-plan generation, history, and grocery-list access
- a LangChain-based agent that researches recipes, analyzes user profile data, and prepares meal-plan recommendations
- Supabase-backed persistence for users, family members, meal plans, day-by-day meals, grocery lists, and feedback
- a modern frontend experience built with Vite and React
- Telegram bot integration for plan approval and feedback workflows

## 2. Features

- Personalized 7-day meal planning based on user goals such as weight loss, muscle gain, or maintenance
- Family-aware planning with dietary preferences and allergy awareness
- Recipe retrieval from a local Supabase-backed knowledge base plus web research
- Grocery-list generation for the planned meals
- Telegram bot support for plan review, approval, and feedback
- REST API endpoints for onboarding, meal-plan generation, and history lookup
- Clean frontend experience for dashboard, meal-plan browsing, grocery viewing, and history

## 3. Architecture and Request Flow

1. A user completes onboarding through the frontend or API.
2. The FastAPI backend stores user and family details in Supabase.
3. The LangChain agent uses tools such as recipe search, profile analysis, nutrition lookups, and grocery generation.
4. The agent produces a structured 7-day meal plan and saves it to Supabase.
5. The frontend displays the generated meal plan and grocery data.
6. The Telegram bot can send the plan for approval and handle feedback/regeneration.

Typical request flow:
- Frontend or client calls `/onboard`
- Backend creates user/family records and triggers onboarding logic
- Client calls `/plan/generate/{user_id}` or `/meal-plan/generate`
- Agent builds a plan and stores it in Supabase
- Frontend reads the plan and grocery list from the API

## 4. Technology Stack

### Backend
- Python 3.9+
- FastAPI
- Uvicorn
- LangChain
- OpenAI API / OpenRouter-compatible chat model
- Supabase Python client
- python-dotenv
- Pydantic

### Frontend
- React
- Vite
- TypeScript
- Tailwind CSS
- TanStack Router / React Query

### Integrations
- Telegram Bot API
- Tavily web search
- Supabase Postgres + vector support

## 5. Project Folder Structure

```text
cooking-agent/
├── api.py                  # FastAPI application and REST endpoints
├── agent.py                # LangChain agent orchestration and plan generation
├── config.py               # Environment variable loading and app constants
├── database.py             # Supabase CRUD helpers
├── ingest.py               # Recipe ingestion and embedding seeding
├── tools.py                # LangChain tools used by the agent
├── telegram_bot.py         # Telegram bot handlers and messaging logic
├── requirements.txt        # Python dependencies
├── frontend/               # React/Vite frontend application
│   └── package.json
└── README.md               # Project documentation
```

## 6. Prerequisites

Before running the project, make sure you have:
- Python 3.9 or newer
- Node.js and npm
- A Supabase project with the necessary tables and RPC support
- OpenAI-compatible API credentials
- Tavily API credentials
- A Telegram bot token

## 7. Backend Setup Instructions

1. Create and activate a virtual environment:

```bash
cd cooking-agent
python3 -m venv .venv
source .venv/bin/activate
```

2. Install Python dependencies:

```bash
pip install -r requirements.txt
```

3. Copy the environment template and fill in the required values:

```bash
cp .env.example .env
```

4. Configure your Supabase and API credentials in `.env`.

## 8. Frontend Setup Instructions

1. Move into the frontend folder:

```bash
cd frontend
```

2. Install frontend dependencies:

```bash
npm install
```

## 9. Environment Variables Required

Create a `.env` file using the following placeholder values:

```env
OPENAI_API_KEY=your_openai_api_key_here
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_service_role_key_here
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key_here
TAVILY_API_KEY=your_tavily_api_key_here
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
```

> Only placeholder values should be used. Do not commit real secrets.

## 10. How to Run the FastAPI Backend

From the repository root:

```bash
cd cooking-agent
source .venv/bin/activate
python -m uvicorn api:app --host 127.0.0.1 --port 8000 --reload
```

The API will be available at:
- http://127.0.0.1:8000

## 11. How to Run the Frontend

From the frontend folder:

```bash
cd cooking-agent/frontend
npm run dev -- --host 127.0.0.1
```

The frontend dev server will be available at:
- http://127.0.0.1:8081

## 12. How to Run the Telegram Bot

From the repository root:

```bash
cd cooking-agent
source .venv/bin/activate
python telegram_bot.py
```

The bot will start polling Telegram for commands and callback updates.

## 13. API Endpoints

The FastAPI backend currently exposes these routes:

### Health
- `GET /health`

### Onboarding
- `POST /onboard`

### Meal plan generation
- `POST /plan/generate/{user_id}`

### Plan retrieval
- `GET /plan/{plan_id}`

### Grocery list
- `GET /grocery/{plan_id}`

### Feedback
- `POST /feedback`

### History
- `GET /history/{user_id}`

## 14. Testing Instructions

Run backend checks and import validation:

```bash
cd cooking-agent
source .venv/bin/activate
python -m py_compile api.py agent.py database.py tools.py telegram_bot.py
```

Run frontend validation:

```bash
cd cooking-agent/frontend
npm run build
```

## 15. Future Improvements

- Add richer meal-plan personalization using more detailed health metrics
- Improve the agent prompt and retrieval quality for better recipe matching
- Add user authentication and role-based access control
- Add support for more cuisines and dietary restrictions
- Improve frontend state management and plan editing workflows
- Add automated end-to-end tests for onboarding and meal-plan generation

## License

This project is for personal and educational use unless otherwise specified.
