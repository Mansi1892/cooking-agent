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
- AI-generated 7-day meal plans with backend summary validation for calories, protein, budget, and variety
- 3 free meal-plan generation credits for every new user
- Admin credit manager for adding credits after free generations are used
- Diet-aware plan generation prompts and diet-aware frontend fallback data
- Approved-only recipe buttons in the browser; recipes are generated on demand from online recipe context and AI
- Auto-refresh on the Meal Plans page while a plan is pending so Telegram approval unlocks recipes without manual reload
- Weekly plan streak calculated from saved Supabase meal plans
- Grocery list and meal-plan history views
- Telegram bot support for sending plans for approval, collecting rejection feedback, and regenerating structured plans
- Settings page for account status, Telegram test message, logout, and local profile reset
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
    ├── src/routes/admin.tsx       # Admin credit manager
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
ADMIN_PASSWORD=change_this_admin_password
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
6. New users start with 3 free meal-plan credits.
7. Meal plans are generated and saved using the backend `user_id`; each successful fresh generation uses 1 credit.
8. Pending plans are sent to Telegram if a numeric chat ID is saved.
9. Approving a plan in Telegram updates Supabase; the browser auto-refreshes and unlocks recipe buttons.
10. Grocery/history views read the saved plan data or use diet-aware demo fallback data if the backend is unreachable.

Telegram rejection/regeneration is treated as part of the same pending plan review and does not consume another credit.

## Credit/Admin Setup

Run this once in Supabase SQL Editor:

```sql
-- see supabase_credit_setup.sql
```

The setup adds:

- `users.credits integer default 3`
- `users.role text default 'user'`

To create the first admin profile, edit `supabase_credit_setup.sql` and replace `11` with the backend user id that should become admin:

```sql
update public.users
set role = 'admin'
where id = 11;
```

Admin users open `/admin`, enter the backend admin user ID and `ADMIN_PASSWORD`, then can view users and add meal-plan credits. If `ADMIN_PASSWORD` is not set locally, the backend uses `admin123` for development only.

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
7. When a plan is generated, the backend queues a Telegram send if a chat ID is saved.
8. Approve keeps the plan visible in Telegram and removes the buttons.
9. Reject asks for text feedback, regenerates a new structured plan, saves it, and sends the revised plan to Telegram.

Do not use `@username`; Telegram sending needs the numeric chat ID.

## Recipes

Recipe generation is intentionally browser-only. Meal cards show a `Recipe` button after a plan has `approved` status. Clicking it calls the backend, searches online recipe context with Tavily, and asks AI for ingredients, steps, prep/cook time, servings, and diet/allergy-aware guidance. Recipes are not sent to Telegram.

## API Endpoints

- `GET /health`
- `GET /api/health`
- `POST /onboard`
- `POST /api/onboard`
- `GET /profile/{user_id}`
- `GET /api/profile/{user_id}`
- `GET /admin/users?admin_user_id={admin_user_id}`
- `GET /api/admin/users?admin_user_id={admin_user_id}`
- `POST /admin/credits`
- `POST /api/admin/credits`
- `POST /plan/generate/{user_id}`
- `POST /api/plan/generate/{user_id}`
- `GET /plan/latest/{user_id}`
- `GET /api/plan/latest/{user_id}`
- `GET /streak/{user_id}`
- `GET /api/streak/{user_id}`
- `POST /recipe/generate`
- `POST /api/recipe/generate`
- `POST /telegram/test/{user_id}`
- `POST /api/telegram/test/{user_id}`
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
- Run `telegram_bot.py` separately whenever you need Approve/Reject buttons to work; the API can send messages, but the bot process listens for callbacks.
- If a vegetarian user sees chicken/fish/eggs, clear local storage or reset the profile and generate a new plan; old demo data may be cached in the browser.
- Existing users with `telegram_id` saved as `@username` should be updated to the numeric Telegram chat ID.

## Future Improvements

- Replace local/demo login with real Supabase Auth or backend auth
- Add edit/regenerate controls for individual meals/days
- Add richer grocery persistence and grocery export
- Add automated end-to-end tests
- Add dedicated keto/pescatarian/eggetarian seed recipes for better local DB retrieval
- Persist generated recipes if users need offline reuse
