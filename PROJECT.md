# Smart Meal AI Project Notes

## Product Scope

Smart Meal AI creates Indian household meal plans from a saved user profile, family members, dietary preference, allergies, budget, and goal. The app supports browser-only planning for users without Telegram and Telegram approval for users who add a numeric Telegram chat ID.

## Current Planning Rules

- Planning weeks run Monday to Sunday.
- Users can generate for `This week` or `Next week`.
- Generating for next week is useful on Saturday/Sunday.
- History groups plans by planning week, so multiple regenerations in one week show as one weekly history entry.
- A history entry can show how many versions were generated for that week.
- Planning streak is counted in weeks, not days.
- Calories and protein shown in summaries are daily averages across the 7-day plan.
- Recent saved meals are passed to the AI as meals to avoid so the next week is not the same menu.
- The Meal Plans page can show one tab per person in the household.
- Each person tab has its own daily calorie/protein target and portion note based on goal, gender, age, weight, height, diet, allergies, and preferences.
- The household still keeps one shared grocery list.

## User Flow

1. User logs in or signs up with email in the local session flow.
2. Existing email restores the saved Supabase profile.
3. New users complete onboarding once.
4. New users receive 3 free meal-plan credits.
5. User chooses this week or next week and generates a plan.
6. If Telegram chat ID is saved, the plan waits for Telegram approval.
7. If Telegram chat ID is not saved, the plan is approved directly in the browser.
8. Approved plans unlock browser recipe buttons.
9. Grocery and history pages read saved Supabase plan data.

## Admin And Credits

- Admin users have unlimited credits.
- Normal users consume 1 credit per new meal-plan generation.
- Regeneration after Telegram rejection is part of review and does not consume a new credit.
- When credits expire, users request more credits from the Meal Plans page.
- The Admin page shows pending credit requests only.
- Admin grants credits from the pending request list.
- The Admin tab is visible only when the current backend profile has `role = 'admin'`.

## Telegram

- Telegram needs a bot token in `.env` and the separate `telegram_bot.py` process running.
- Users must save the numeric chat ID, not `@username`.
- The backend sends generated plans asynchronously so saving a plan is not blocked by Telegram send time.
- Telegram approve marks the plan approved in Supabase.
- Telegram reject asks for feedback, regenerates the plan, and sends a revised plan.

## Data Notes

- Supabase stores users, family members, meal plans, day meals, grocery data, feedback, and credit requests.
- `supabase_family_personalization.sql` adds gender/goal/body-stat fields needed for richer per-person family planning.
- Email should be unique for non-blank user records.
- Old duplicate/null-email test users should be cleaned before enforcing the unique email index.
- User credits should not reset during profile reset/edit flows.

## Local Development

- Backend: `http://127.0.0.1:8000`
- Frontend: `http://localhost:8080`
- Backend command: `venv/bin/python -m uvicorn api:app --host 127.0.0.1 --port 8000`
- Frontend command: `npm run dev -- --host 0.0.0.0 --port 8080`

## Deployment

- Frontend is deployed on Vercel.
- Backend should run as a Python web service on Render/Railway/Fly or similar.
- This repo includes `render.yaml` for Render.
- After backend deployment, set Vercel `VITE_API_URL` to the backend URL and redeploy the frontend.
- Telegram approval buttons need the bot process/webhook strategy to be available in production. The API can send Telegram messages, while callback handling needs `telegram_bot.py` or a webhook-based replacement.

## Validation

```bash
PYTHONPYCACHEPREFIX=/private/tmp/codex_pycache python3 -m py_compile api.py agent.py database.py tools.py telegram_bot.py onboarding_utils.py config.py
```

```bash
cd frontend
npm run build
```

## Next Improvements

- Replace local email session with real Supabase Auth or backend auth.
- Move Telegram callbacks and sends to a durable worker/queue for production.
- Add database migration files for all schema changes.
- Add end-to-end tests for login, onboarding, credits, Telegram approval, and history grouping.
- Add per-meal swap/regenerate controls after a weekly plan is approved.
