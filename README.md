# Smart Meal AI

AI-powered meal planning for Indian households. The app has a FastAPI backend, a React/TanStack frontend, Supabase persistence, LangChain-style recipe tooling, and optional Telegram plan approval.

## Current Status

- Frontend dev server: `http://127.0.0.1:8080/`
- Backend API: `http://127.0.0.1:8000`
- Backend health: `GET http://127.0.0.1:8000/health`
- Login route: `http://127.0.0.1:8080/login`

The current login is a local/demo login stored in browser localStorage. It gates the UI, then sends new users to onboarding. Real backend authentication can be added later with Supabase Auth or custom API endpoints.

## Features

- Local login/signup screen before onboarding
- Onboarding for personal profile, family members, goals, budget, allergies, preferences, and Telegram chat ID
- Goals: weight loss, muscle gain, maintenance
- Dietary preferences: vegetarian, eggetarian, vegan, non-vegetarian, pescatarian, keto
- AI-generated 7-day meal plans
- Diet-aware plan generation prompts and diet-aware frontend fallback data
- Grocery list and meal-plan history views
- Telegram bot support for sending plans for approval and collecting feedback
- Supabase-backed storage for users, family members, meal plans, day meals, grocery lists, and feedback

## Architecture

```text
React frontend
  -> FastAPI backend
  -> Supabase persistence
  -> LangChain-style agent/tools
  -> OpenAI/OpenRouter + Tavily + recipe DB
  -> Optional Telegram bot approval flow
```

## Project Structure

```text
cooking-agent/
├── api.py                         # FastAPI routes
├── agent.py                       # Agent orchestration and structured meal-plan generation
├── config.py                      # Goal targets, dietary types, env loading
├── database.py                    # Supabase CRUD helpers
├── ingest.py                      # Recipe seed/ingestion helper
├── onboarding_utils.py            # Diet/family payload normalization
├── telegram_bot.py                # Telegram polling, approval, feedback
├── tools.py                       # Agent tools: recipe search, profile analysis, grocery, Telegram
├── requirements.txt               # Python dependencies
└── frontend/
    ├── src/routes/login.tsx       # Local demo login
    ├── src/routes/onboarding.tsx  # Profile and family onboarding
    ├── src/routes/meal-plans.tsx
    ├── src/routes/grocery.tsx
    ├── src/routes/history.tsx
    ├── src/lib/api.ts
    └── src/lib/storage.ts
```

## Environment

Create `cooking-agent/.env`:

```env
OPENAI_API_KEY=your_openai_or_openrouter_key
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_service_role_key
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key
TAVILY_API_KEY=your_tavily_key
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
```

Do not commit real secrets.

## Backend Setup

This project currently has a local virtualenv named `venv`.

```bash
cd cooking-agent
source venv/bin/activate
pip install -r requirements.txt
```

Start the backend:

```bash
cd cooking-agent
venv/bin/python -m uvicorn api:app --host 127.0.0.1 --port 8000
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Expected:

```json
{"status":"ok"}
```

## Frontend Setup

```bash
cd cooking-agent/frontend
npm install
npm run dev -- --host 127.0.0.1 --port 8080
```

Open:

```text
http://127.0.0.1:8080/
```

## User Flow

1. User opens the frontend.
2. If not logged in locally, user is redirected to `/login`.
3. Login/signup stores a local session.
4. If no backend `user_id` exists yet, user is sent to `/onboarding`.
5. Onboarding saves the user/family profile through the backend.
6. Meal plans are generated and saved using the backend `user_id`.
7. Grocery/history views read the saved plan data or use diet-aware demo fallback data if the backend is unreachable.

## Telegram Flow

Telegram requires a bot and numeric chat ID.

1. Create a bot with Telegram `@BotFather`.
2. Put the token in `.env` as `TELEGRAM_BOT_TOKEN`.
3. Start the bot:

```bash
cd cooking-agent
venv/bin/python telegram_bot.py
```

4. Open your bot in Telegram and send `/start`.
5. The bot replies with your numeric Telegram chat ID.
6. Paste that number into the app's `Telegram chat ID` field.
7. When a plan is generated, the backend sends it to Telegram for approval if a chat ID is saved.

Do not use `@username`; Telegram sending needs the numeric chat ID.

## API Endpoints

- `GET /health`
- `GET /api/health`
- `POST /onboard`
- `POST /api/onboard`
- `POST /plan/generate/{user_id}`
- `POST /api/plan/generate/{user_id}`
- `GET /plan/{plan_id}`
- `GET /api/plan/{plan_id}`
- `GET /grocery/{plan_id}`
- `GET /history/{user_id}`
- `POST /feedback`

## Validation

Backend:

```bash
cd cooking-agent
PYTHONPYCACHEPREFIX=/private/tmp/codex_pycache python3 -m py_compile api.py agent.py database.py tools.py telegram_bot.py onboarding_utils.py config.py
venv/bin/python -m pip check
curl http://127.0.0.1:8000/health
```

Frontend:

```bash
cd cooking-agent/frontend
npm run build
```

## Notes

- The frontend dev server should run on `8080`.
- The backend should run on `8000`.
- If a vegetarian user sees chicken/fish/eggs, clear local storage or reset the profile and generate a new plan; old demo data may be cached in the browser.
- Existing users with `telegram_id` saved as `@username` should be updated to the numeric Telegram chat ID.

## Future Improvements

- Replace local/demo login with real Supabase Auth or backend auth
- Add edit/regenerate controls for individual meals/days
- Add richer grocery persistence and grocery export
- Add automated end-to-end tests
- Add dedicated keto/pescatarian/eggetarian seed recipes for better local DB retrieval
