from langchain.agents import initialize_agent, AgentType
from langchain.memory import ConversationBufferMemory
from langchain_openai import ChatOpenAI
import json
from typing import Dict, List, Any, Tuple, Optional
import os
from datetime import date
from dotenv import load_dotenv

load_dotenv()

from config import GOAL_TARGETS
from database import (
    create_user,
    add_family_member,
    save_meal_plan,
    save_day_meals,
    get_user,
    get_latest_plan,
    update_plan_status,
)
from tools import ALL_TOOLS, openai_client


def create_agent():
    """Create and return a LangChain ReAct agent with tools and memory."""
    llm = ChatOpenAI(
        model="openai/gpt-4o-mini",
        temperature=0.7,
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url="https://openrouter.ai/api/v1",
        default_headers={
            "HTTP-Referer": "https://meal-planner-ai.com",
            "X-Title": "Meal Planner AI"
        }
    )

    memory = ConversationBufferMemory(
        memory_key="chat_history",
        return_messages=True,
    )

    agent = initialize_agent(
        tools=ALL_TOOLS,
        llm=llm,
        agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
        memory=memory,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=15,
        early_stopping_method="generate",
    )

    return agent


def generate_structured_plan(
    user_id: int,
    agent_result: str,
    goal: str
) -> Dict:
    """Use OpenAI to convert agent text output into structured week plan."""
    try:
        user = get_user(user_id)
        targets = GOAL_TARGETS.get(goal, GOAL_TARGETS["maintenance"])

        prompt = f"""
        Based on this meal planning research:
        {agent_result}

        User: {user.get('name') if user else 'Unknown'}
        Goal: {goal}
        Daily calorie target: {targets['min_calories']}-{targets['max_calories']} kcal
        Daily protein target: {targets['min_protein']}-{targets['max_protein']}g

        Generate a complete 7-day Indian meal plan in this EXACT JSON format.
        Return ONLY valid JSON, no explanation, no markdown:

        {{
            "week_plan": [
                {{
                    "day": "Monday",
                    "breakfast": "Poha with peanuts and vegetables",
                    "breakfast_calories": 300,
                    "breakfast_protein": 10,
                    "lunch": "Dal tadka with chapati and salad",
                    "lunch_calories": 450,
                    "lunch_protein": 20,
                    "dinner": "Palak paneer with rice",
                    "dinner_calories": 400,
                    "dinner_protein": 18,
                    "total_calories": 1150,
                    "total_protein": 48,
                    "fits_goal": true
                }},
                {{
                    "day": "Tuesday",
                    "breakfast": "Oats upma with vegetables",
                    "breakfast_calories": 280,
                    "breakfast_protein": 8,
                    "lunch": "Rajma chawal with curd",
                    "lunch_calories": 480,
                    "lunch_protein": 22,
                    "dinner": "Grilled chicken with sabzi",
                    "dinner_calories": 420,
                    "dinner_protein": 30,
                    "total_calories": 1180,
                    "total_protein": 60,
                    "fits_goal": true
                }},
                {{
                    "day": "Wednesday",
                    "breakfast": "Idli with sambar",
                    "breakfast_calories": 250,
                    "breakfast_protein": 8,
                    "lunch": "Chole with brown rice",
                    "lunch_calories": 460,
                    "lunch_protein": 18,
                    "dinner": "Egg curry with chapati",
                    "dinner_calories": 380,
                    "dinner_protein": 22,
                    "total_calories": 1090,
                    "total_protein": 48,
                    "fits_goal": true
                }},
                {{
                    "day": "Thursday",
                    "breakfast": "Moong dal cheela with chutney",
                    "breakfast_calories": 320,
                    "breakfast_protein": 15,
                    "lunch": "Vegetable khichdi with curd",
                    "lunch_calories": 420,
                    "lunch_protein": 16,
                    "dinner": "Chicken saag with chapati",
                    "dinner_calories": 430,
                    "dinner_protein": 32,
                    "total_calories": 1170,
                    "total_protein": 63,
                    "fits_goal": true
                }},
                {{
                    "day": "Friday",
                    "breakfast": "Banana oats smoothie with nuts",
                    "breakfast_calories": 290,
                    "breakfast_protein": 9,
                    "lunch": "Masoor dal with chapati and salad",
                    "lunch_calories": 440,
                    "lunch_protein": 19,
                    "dinner": "Paneer bhurji with chapati",
                    "dinner_calories": 390,
                    "dinner_protein": 22,
                    "total_calories": 1120,
                    "total_protein": 50,
                    "fits_goal": true
                }},
                {{
                    "day": "Saturday",
                    "breakfast": "Aloo paratha with curd",
                    "breakfast_calories": 380,
                    "breakfast_protein": 10,
                    "lunch": "Fish curry with rice",
                    "lunch_calories": 470,
                    "lunch_protein": 28,
                    "dinner": "Bhindi masala with dal and chapati",
                    "dinner_calories": 380,
                    "dinner_protein": 16,
                    "total_calories": 1230,
                    "total_protein": 54,
                    "fits_goal": true
                }},
                {{
                    "day": "Sunday",
                    "breakfast": "Egg bhurji with toast",
                    "breakfast_calories": 350,
                    "breakfast_protein": 18,
                    "lunch": "Chicken curry with rice and raita",
                    "lunch_calories": 500,
                    "lunch_protein": 32,
                    "dinner": "Vegetable soup with multigrain bread",
                    "dinner_calories": 280,
                    "dinner_protein": 10,
                    "total_calories": 1130,
                    "total_protein": 60,
                    "fits_goal": true
                }}
            ],
            "shopping_list": [
                "Rice 2kg", "Atta 2kg", "Oats 500g",
                "Eggs 2 dozen", "Chicken 1kg", "Fish 500g",
                "Paneer 500g", "Dal assorted 1kg",
                "Tomatoes 1kg", "Onions 1kg", "Spinach 500g",
                "Milk 2L", "Curd 500g",
                "Spices as needed", "Oil 1L"
            ],
            "goal_summary": "This 7-day plan averages 1150 kcal/day and 55g protein/day, supporting your weight loss goal of 1200-1500 kcal/day while keeping meals varied and nutritious."
        }}

        Make all 7 days use the actual recipes found in the research above.
        Adjust the example JSON to use real recipes from the research.
        Return ONLY the JSON object.
        """

        response = openai_client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)
        return result

    except Exception as e:
        print(f"⚠️ Structured plan error: {str(e)}")
        # return fallback plan
        return {
            "week_plan": [
                {
                    "day": day,
                    "breakfast": "Poha with vegetables",
                    "breakfast_calories": 300,
                    "breakfast_protein": 10,
                    "lunch": "Dal chawal with sabzi",
                    "lunch_calories": 450,
                    "lunch_protein": 18,
                    "dinner": "Roti with paneer sabzi",
                    "dinner_calories": 380,
                    "dinner_protein": 16,
                    "total_calories": 1130,
                    "total_protein": 44,
                    "fits_goal": True
                }
                for day in ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
            ],
            "shopping_list": ["Rice", "Dal", "Vegetables", "Paneer", "Spices"],
            "goal_summary": "Basic weight loss meal plan with Indian recipes."
        }


def run_onboarding(
    user_data: Dict[str, Any],
    family_members: List[Dict[str, Any]]
) -> Tuple[Optional[int], str]:
    """Save user and family members to Supabase during onboarding."""
    try:
        user = create_user(
            name=user_data.get("name", "Unknown"),
            age=user_data.get("age", 0),
            weight_kg=user_data.get("weight_kg", 0),
            height_cm=user_data.get("height_cm", 0),
            goal=user_data.get("goal", "maintenance"),
            telegram_id=user_data.get("telegram_id", ""),
            budget_weekly=user_data.get("budget_weekly", 0),
        )

        if not user or "id" not in user:
            return None, "❌ Failed to create user account."

        user_id = user["id"]
        family_count = 0

        for member in family_members:
            result = add_family_member(
                user_id=user_id,
                name=member.get("name", "Family Member"),
                age=member.get("age", 0),
                dietary_type=member.get("dietary_type", "non-vegetarian"),
                allergies=member.get("allergies", []),
                preferences=member.get("preferences", []),
            )
            if result and "id" in result:
                family_count += 1

        confirmation = (
            f"✅ Onboarding complete!\n"
            f"User ID: {user_id}\n"
            f"Name: {user_data.get('name')}\n"
            f"Family members added: {family_count}"
        )

        return user_id, confirmation

    except Exception as exc:
        return None, f"❌ Onboarding error: {exc}"


def generate_meal_plan(user_id: int) -> Dict[str, Any]:
    """Generate a 7-day personalized meal plan for a user and family."""
    try:
        agent = create_agent()

        user = get_user(user_id)
        if not user:
            return {"status": "error", "message": f"User {user_id} not found"}

        goal = user.get("goal", "maintenance")
        targets = GOAL_TARGETS.get(goal, GOAL_TARGETS["maintenance"])

        prompt = f"""
You are helping create a 7-day meal plan for user ID {user_id} ({user.get('name')}).
Goal: {goal}
Calorie target: {targets['min_calories']}-{targets['max_calories']} kcal/day
Protein target: {targets['min_protein']}-{targets['max_protein']}g/day

Follow these steps IN ORDER using the available tools:

Step 1: Call analyze_profile with input "{user_id}"
Step 2: Call search_recipes_db with input "Indian breakfast recipes weight loss"
Step 3: Call search_recipes_db with input "Indian lunch dinner recipes healthy protein"
Step 4: Call search_recipes_web with input "7 day Indian meal plan weight loss 1200 calories"

After completing all steps, provide a summary of the best recipes found
that can be used for a 7-day meal plan meeting the calorie and protein targets.

IMPORTANT: Always pass tool inputs as plain text strings only.
"""

        print("🤖 Agent gathering recipes and profile info...")
        agent_result = agent.run(prompt)
        print(f"✅ Agent completed. Converting to structured plan...")

        # convert to structured JSON
        structured_plan = generate_structured_plan(user_id, agent_result, goal)

        # save to Supabase
        saved_plan = save_meal_plan(
            user_id=user_id,
            goal=goal,
            week_start=str(date.today()),
        )

        plan_id = saved_plan.get("id", 0) if saved_plan else 0

        # save day meals
        if structured_plan.get("week_plan") and plan_id:
            save_day_meals(plan_id, structured_plan["week_plan"])
            print(f"✅ {len(structured_plan['week_plan'])} days saved to Supabase")

        structured_plan["plan_id"] = plan_id
        structured_plan["user_id"] = user_id
        structured_plan["status"] = "success"

        return structured_plan

    except Exception as exc:
        return {
            "status": "error",
            "message": f"Error generating meal plan: {exc}",
            "week_plan": [],
            "plan_id": None
        }


def handle_feedback(plan_id: str, feedback: Dict[str, Any]) -> Dict[str, Any]:
    """Handle user feedback and regenerate rejected days."""
    try:
        agent = create_agent()
        rejected_days = feedback.get("rejected_days", [])

        if not rejected_days:
            update_plan_status(plan_id, "approved")
            return {
                "status": "success",
                "message": "Plan approved!",
                "plan_id": plan_id,
            }

        comments = feedback.get("comments", "")
        prompt = f"""
        User rejected these days: {', '.join(rejected_days)}
        Feedback: {comments}

        Step 1: Search search_recipes_db with input "alternative healthy Indian meals"
        Step 2: Search search_recipes_web with input "healthy Indian meal alternatives"
        Step 3: Suggest new meals for the rejected days addressing the feedback
        """

        result = agent.run(prompt)
        update_plan_status(plan_id, "approved")

        return {
            "status": "success",
            "plan_id": plan_id,
            "message": "Plan regenerated!",
            "regenerated_days": rejected_days,
            "updated_plan": result,
        }

    except Exception as exc:
        return {
            "status": "error",
            "message": f"Error: {exc}",
        }


if __name__ == "__main__":
    print("✅ agent.py loaded.")