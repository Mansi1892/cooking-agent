# Smart Meal AI

AI-powered meal planning for Indian households. The app has a FastAPI backend, a React/TanStack frontend, Supabase persistence, LangChain-style recipe tooling, and optional Telegram plan approval.

## Current Status

- Frontend dev server: `http://localhost:8080/`
- Backend API: `http://127.0.0.1:8000`
- Backend health: `GET http://127.0.0.1:8000/health`
- Login route: `http://localhost:8080/login`

The current login is a local browser session backed by a Supabase user profile lookup. It is not full password authentication yet, but it does prevent duplicate signup by email, clears stale local cache when switching accounts, and restores the correct backend profile on login. Real backend authentication can be added later with Supabase Auth or custom API endpoints.

## Features

- Local login/signup screen before onboarding, with email-based profile restore
- Onboarding for personal profile, family members, goals, budget, allergies, preferences, and Telegram chat ID
- Family member personalization: each person can have their own goal, gender, age, weight, height, diet, allergies, and preferences
- Goals: weight loss, muscle gain, maintenance
- Dietary preferences: vegetarian, eggetarian, vegan, non-vegetarian, pescatarian, keto
- AI-generated 7-day meal plans with backend summary validation for calories, protein, budget, and variety
- Week selector on Meal Plans: generate for this week or next week, useful for Saturday/Sunday planning
- Weekly history is grouped by Monday-Sunday planning week, so regenerations in the same week do not create duplicate history cards
- Meal-plan summaries show average daily calories and average daily protein, not weekly totals
- Recent saved meals are passed back into the AI prompt so the next weekly menu avoids repeating the same dishes
- Meal Plans can show person tabs for the main user and family members, with per-person calorie/protein targets and portion notes
- 3 free meal-plan generation credits for every new user
- Request-based admin credit manager for adding credits after free generations are used
- Diet-aware plan generation prompts
- Approved-only recipe buttons in the browser; recipes are generated on demand from online recipe context and AI
- Auto-refresh on the Meal Plans page while a plan is pending so Telegram approval unlocks recipes without manual reload
- No-Telegram auto approval: users without a Telegram chat ID get an approved browser plan immediately
- Weekly planning streak calculated from saved Supabase meal-plan weeks
- Grocery list and meal-plan history views
- Telegram bot support for sending plans for approval, collecting rejection feedback, and regenerating structured plans; Telegram sends are fired asynchronously after plan save
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
    ├── src/routes/login.tsx       # Local email session and profile restore
    ├── src/routes/admin.tsx       # Pending credit request manager
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
npm run dev -- --host 0.0.0.0 --port 8080
```

Open:

```text
http://localhost:8080/
```

## Deployment

The frontend and backend deploy separately:

- Frontend: Vercel
- Backend API: Render/Railway/Fly-style Python web service
- Database: Supabase

Current Vercel frontend deployment:

```text
https://frontend-orpin-zeta-59.vercel.app
```

### Backend On Render

The repo includes `render.yaml` for a Render web service.

1. Open Render and create a new Blueprint/Web Service from the GitHub repo.
2. Use the repo root as the backend root, not `frontend`.
3. Render should use:

```bash
pip install -r requirements.txt
uvicorn api:app --host 0.0.0.0 --port $PORT
```

4. Add these Render environment variables:

```env
OPENAI_API_KEY=...
SUPABASE_URL=...
SUPABASE_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
TAVILY_API_KEY=...
TELEGRAM_BOT_TOKEN=...
ADMIN_PASSWORD=...
```

5. After Render gives a backend URL, verify:

```bash
curl https://your-render-api-url/health
```

Expected:

```json
{"status":"ok"}
```

6. In Vercel project settings, add:

```env
VITE_API_URL=https://your-render-api-url
```

Then redeploy the Vercel frontend.

## User Flow

1. User opens the frontend.
2. If not logged in locally, user is redirected to `/login`.
3. Login/signup stores a local session and clears stale cached profile/plan/admin state before switching users.
4. If no backend `user_id` exists yet, user is sent to `/onboarding`.
5. Onboarding saves the user/family profile through the backend.
6. New users start with 3 free meal-plan credits.
7. On Meal Plans, the user chooses `This week` or `Next week` before generation.
8. Meal plans are generated and saved using the backend `user_id`; each successful fresh generation uses 1 credit.
9. If a numeric Telegram chat ID is saved, the plan stays pending and is sent to Telegram for approval.
10. If no Telegram chat ID is saved, the plan is marked approved immediately and browser recipe buttons unlock.
11. Approving a Telegram plan updates Supabase; the browser auto-refreshes and unlocks recipe buttons.
12. Grocery/history views read saved Supabase plan data. If no plan exists, they show empty states instead of demo grocery/history data.

Telegram rejection/regeneration is treated as part of the same pending plan review and does not consume another credit.

## Weekly Planning Rules

Planning weeks run Monday to Sunday.

- `This week` saves the plan against the current Monday.
- `Next week` saves the plan against the next Monday.
- The backend accepts only this week or next week for normal generation, preventing accidental old-week plans.
- History shows one card per week. If the user generates or regenerates more than once in the same week, the history card shows the number of versions for that week.
- The planning streak counts consecutive planned weeks, not days. A `1 week` streak means there is a saved plan for the current planning week.
- Average calories and protein are daily averages across the 7-day plan.
- The AI receives recent saved meal names and is instructed to avoid repeating those dishes in the new week.

## Credit/Admin Setup

Run this once in Supabase SQL Editor:

```sql
-- see supabase_credit_setup.sql
```

The setup adds:

- `users.email text`
- `users.credits integer default 3`
- `users.role text default 'user'`
- `credit_requests` for request-based credit grants
- a unique non-blank email index after old duplicate/null email users are cleaned

To create the first admin profile, edit `supabase_credit_setup.sql` and replace the sample id with the backend user id that should become admin:

```sql
update public.users
set role = 'admin'
where id = 18;
```

Admin users see the `/admin` tab. Normal users do not see it, and direct `/admin` navigation redirects away unless the current backend profile has `role = 'admin'`.

Credits are request-based:

1. A normal user spends the 3 free generations.
2. The Meal Plans page shows a request button.
3. The user requests more credits.
4. The admin page shows only pending credit requests.
5. Admin grants credits from that request list.

The backend still exposes manual admin credit endpoints for API compatibility, but the frontend uses the request workflow.

## Family Personalization Setup

Run this once in Supabase SQL Editor:

```sql
-- see supabase_family_personalization.sql
```

The setup adds:

- `users.gender`
- `family_members.goal`
- `family_members.gender`
- `family_members.weight_kg`
- `family_members.height_cm`

The app has fallback handling if these columns are not present yet, but production personalization works best after running the migration.

Family meal planning rules:

- The household still receives one shared grocery list.
- The Meal Plans page shows tabs for each person.
- Each person tab uses that person's goal, gender, age, weight, height, diet, allergies, and preferences.
- People with compatible goals/diets can share the same meal base with different portions.
- People with different goals receive different calorie/protein targets and portion notes.
- Future improvement: persist every person/day plan in a dedicated table for deeper per-person regenerate history.

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
7. When a plan is generated, the backend starts an asynchronous Telegram send if a chat ID is saved.
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
- `POST /credit-requests`
- `POST /api/credit-requests`
- `GET /admin/credit-requests`
- `GET /api/admin/credit-requests`
- `POST /admin/credit-requests/grant`
- `POST /api/admin/credit-requests/grant`
- `POST /plan/generate/{user_id}` with optional JSON body `{ "week_offset": 0 }` for this week or `{ "week_offset": 1 }` for next week
- `POST /api/plan/generate/{user_id}` with the same optional body
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
- Logout and login clear local user/profile/plan/admin cache before switching accounts.
- If a vegetarian user sees chicken/fish/eggs, confirm the saved profile dietary preference and generate a new plan; old plans remain in history.
- Existing users with `telegram_id` saved as `@username` should be updated to the numeric Telegram chat ID.
- Grocery cost is AI-estimated from the generated plan and budget context. It is not a live grocery-cart checkout against a retailer.

## Future Improvements

- Replace local email session with real Supabase Auth or backend auth
- Move Telegram/background jobs to a durable worker/queue for production reliability
- Add database migrations and seed scripts instead of one-off SQL snippets
- Add edit/regenerate controls for individual meals/days
- Add richer grocery persistence and grocery export
- Add automated end-to-end tests
- Add dedicated keto/pescatarian/eggetarian seed recipes for better local DB retrieval
- Persist generated recipes if users need offline reuse
