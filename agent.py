from langchain.agents import initialize_agent, AgentType
from langchain.memory import ConversationBufferMemory
from langchain_community.chat_models import ChatOpenAI
import json
from typing import Dict, List, Any, Tuple, Optional

from config import LLM_MODEL, GOAL_TARGETS, OPENAI_API_KEY
from database import (
    create_user,
    add_family_member,
    save_meal_plan,
    save_day_meals,
    get_user,
    get_latest_plan,
    update_plan_status,
)
from tools import ALL_TOOLS

SYSTEM_PROMPT = """You are a professional nutritionist and meal planning AI assistant.
Your job is to create personalized weekly meal plans for families based on 
their health goals, dietary restrictions, and ingredient preferences.
Always consider every family member's needs when planning meals.
Use the search tools to find relevant recipes before generating plans.
Always validate that the plan meets the calorie and protein targets.

When creating meal plans:
1. Analyze the user's profile and family members using the analyze_profile tool
2. Search for recipes using search_recipes_db tool for database recipes
3. Search for recipes using search_recipes_web tool for additional options
4. Generate a 7-day meal plan respecting all dietary restrictions
5. Ensure the plan meets calorie and protein targets for each person
6. Provide meal options for breakfast, lunch, and dinner
7. Consider budget constraints and ingredient availability
8. Save the plan to Supabase using the grocery list tool
9. Send notifications using the Telegram tool when the plan is ready

Always be thorough in your analysis and provide detailed reasoning for your choices."""


def create_agent():
    """Create and return a LangChain ReAct agent with tools and memory."""
    llm = ChatOpenAI(
        model=LLM_MODEL,
        temperature=0.7,
        api_key=OPENAI_API_KEY,
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
        max_iterations=10,
        early_stopping_method="generate",
    )

    #agent.system_message = SYSTEM_PROMPT

    return agent


def run_onboarding(user_data: Dict[str, Any], family_members: List[Dict[str, Any]]) -> Tuple[Optional[str], str]:
    """
    Save user and family members to Supabase during onboarding.
    
    Args:
        user_data: Dictionary with keys: name, age, weight_kg, height_cm, goal, telegram_id, budget_weekly
        family_members: List of dictionaries with keys: name, age, dietary_type, allergies, preferences
    
    Returns:
        Tuple of (user_id, confirmation_message)
    """
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
            f"✅ Onboarding complete! User ID: {user_id}\n"
            f"User: {user_data.get('name', 'Unknown')}\n"
            f"Family members added: {family_count}"
        )

        return user_id, confirmation

    except Exception as exc:
        return None, f"❌ Onboarding error: {exc}"


def generate_meal_plan(user_id: str) -> Dict[str, Any]:
    """
    Generate a 7-day personalized meal plan for a user and their family.
    
    Args:
        user_id: The Supabase user ID
    
    Returns:
        Dictionary containing the generated meal plan with all meals and nutrition info
    """
    agent = create_agent()

    user = get_user(user_id)
    if not user:
        return {"status": "error", "message": f"User {user_id} not found"}

    prompt = f"""
    Please create a comprehensive 7-day meal plan for user ID {user_id} (name: {user.get('name', 'Unknown')}).
    
    User details:
    - Goal: {user.get('goal', 'maintenance')}
    - Budget per week: ₹{user.get('budget_weekly', 'not specified')}
    - Dietary preferences: {user.get('dietary_type', 'not specified')}
    
    Steps:
    1. First, analyze the user profile including all family members using the analyze_profile tool
    2. Search for recipes in the database using search_recipes_db with relevant queries
    3. Also search the web for Indian recipes using search_recipes_web for more options
    4. Create a detailed 7-day meal plan respecting all dietary restrictions and goals
    5. For each day, provide breakfast, lunch, and dinner with calorie and protein info
    6. Generate a grocery list using the generate_grocery_list tool
    7. Return the complete meal plan as a structured JSON
    
    The meal plan should:
    - Meet the calorie targets for each person based on their goal
    - Provide sufficient protein for everyone
    - Respect all dietary restrictions and allergies
    - Stay within budget constraints
    - Include variety and nutritious options
    - Be practical and easy to prepare
    """

    try:
        result = agent.run(prompt)

        saved_plan = save_meal_plan(
            user_id=user_id,
            goal=user.get("goal", "maintenance"),
            week_start="2026-06-28",
        )

        if not saved_plan or "id" not in saved_plan:
            return {"status": "error", "message": "Failed to save meal plan to Supabase"}

        plan_id = saved_plan["id"]

        try:
            plan_data = json.loads(result) if isinstance(result, str) else result
        except (json.JSONDecodeError, TypeError):
            plan_data = {
                "summary": result,
                "status": "pending",
                "plan_id": plan_id,
            }

        return {
            "status": "success",
            "plan_id": plan_id,
            "user_id": user_id,
            "plan": plan_data,
            "message": "Meal plan generated successfully. Pending approval.",
        }

    except Exception as exc:
        return {
            "status": "error",
            "message": f"Error generating meal plan: {exc}",
        }


def handle_feedback(plan_id: str, feedback: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle user feedback on a meal plan and regenerate rejected days.
    
    Args:
        plan_id: The Supabase meal_plan ID
        feedback: Dictionary with keys like rejected_days, comments, ratings
    
    Returns:
        Dictionary with the updated meal plan
    """
    agent = create_agent()

    plan = get_latest_plan(feedback.get("user_id"))
    if not plan or plan.get("id") != plan_id:
        return {"status": "error", "message": f"Plan {plan_id} not found"}

    rejected_days = feedback.get("rejected_days", [])
    if not rejected_days:
        update_plan_status(plan_id, "approved")
        return {
            "status": "success",
            "message": "Plan approved! No changes needed.",
            "plan_id": plan_id,
        }

    comments = feedback.get("comments", "")
    user_id = feedback.get("user_id", "")

    prompt = f"""
    The user has provided feedback on meal plan {plan_id}. 
    
    Rejected days: {', '.join(rejected_days)}
    User comments: {comments}
    
    Please:
    1. Analyze the feedback and understand what needs to change
    2. Search for better recipe options using search_recipes_db and search_recipes_web
    3. Regenerate meals for only the rejected days, keeping approved days unchanged
    4. Ensure the new options address the user's concerns
    5. Return the updated meal plan focusing on the regenerated days
    
    Regenerate meals for: {', '.join(rejected_days)}
    """

    try:
        result = agent.run(prompt)

        try:
            updated_plan = json.loads(result) if isinstance(result, str) else result
        except (json.JSONDecodeError, TypeError):
            updated_plan = {
                "summary": result,
                "regenerated_days": rejected_days,
                "plan_id": plan_id,
            }

        update_plan_status(plan_id, "approved")

        return {
            "status": "success",
            "plan_id": plan_id,
            "message": "Meal plan regenerated successfully.",
            "regenerated_days": rejected_days,
            "updated_plan": updated_plan,
        }

    except Exception as exc:
        return {
            "status": "error",
            "message": f"Error regenerating meal plan: {exc}",
        }


if __name__ == "__main__":
    print("✅ agent.py loaded. Use create_agent() to initialize the ReAct agent.")
