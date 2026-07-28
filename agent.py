from langchain.agents import initialize_agent, AgentType
from langchain.memory import ConversationBufferMemory
from langchain_openai import ChatOpenAI
import json
import re
from typing import Dict, List, Any, Tuple, Optional
import os
from datetime import date, timedelta
from dotenv import load_dotenv
from functools import lru_cache

load_dotenv()

from config import GOAL_TARGETS
from database import (
    create_user,
    add_family_member,
    save_meal_plan,
    save_day_meals,
    save_grocery_list,
    get_user,
    get_family_members,
    get_latest_plan,
    get_user_history,
    update_plan_status,
)
from onboarding_utils import normalize_dietary_type, normalize_family_member
from tools import ALL_TOOLS, openai_client, tavily_search


STRICT_VEGETARIAN_BLOCKLIST = (
    "Do not include chicken, meat, fish, seafood, eggs, bone broth, gelatin, or any non-vegetarian ingredient."
)

DIET_BLOCKED_TERMS = {
    "vegetarian": [
        "chicken", "fish", "mutton", "lamb", "beef", "pork", "seafood", "prawn", "shrimp",
        "egg", "eggs", "omelette", "anda", "bakra", "keema", "bone broth", "gelatin",
    ],
    "vegan": [
        "chicken", "fish", "mutton", "lamb", "beef", "pork", "seafood", "prawn", "shrimp",
        "egg", "eggs", "omelette", "anda", "bakra", "keema", "bone broth", "gelatin",
        "milk", "curd", "yogurt", "paneer", "ghee", "cheese", "honey",
    ],
    "eggetarian": [
        "chicken", "fish", "mutton", "lamb", "beef", "pork", "seafood", "prawn", "shrimp",
        "bakra", "keema", "bone broth", "gelatin",
    ],
    "pescatarian": [
        "chicken", "mutton", "lamb", "beef", "pork", "bakra", "keema",
    ],
}

SAFE_MEAL_REPLACEMENTS = {
    "vegetarian": {
        "breakfast": "Besan cheela with mint chutney",
        "lunch": "Rajma masala with rice and salad",
        "dinner": "Paneer tikka with roti and cucumber salad",
    },
    "vegan": {
        "breakfast": "Vegetable poha with peanuts",
        "lunch": "Chana masala with rice and salad",
        "dinner": "Tofu vegetable curry with roti",
    },
    "eggetarian": {
        "breakfast": "Vegetable omelette with toast",
        "lunch": "Rajma masala with rice and salad",
        "dinner": "Paneer tikka with roti and cucumber salad",
    },
    "pescatarian": {
        "breakfast": "Vegetable oats upma",
        "lunch": "Fish curry with rice and salad",
        "dinner": "Dal tadka with roti and vegetables",
    },
}

SAFE_SHOPPING_REPLACEMENTS = {
    "vegetarian": ["Paneer 500g", "Soya chunks 500g", "Dal assorted 1kg", "Curd 500g"],
    "vegan": ["Tofu 500g", "Soya chunks 500g", "Dal assorted 1kg", "Chana 500g"],
    "eggetarian": ["Eggs 1 dozen", "Paneer 500g", "Soya chunks 500g", "Dal assorted 1kg"],
    "pescatarian": ["Fish 800g", "Dal assorted 1kg", "Curd 500g"],
}


def violates_diet(text: Any, dietary_type: Optional[str]) -> bool:
    normalized = normalize_dietary_type(dietary_type) or "normal"
    blocked = DIET_BLOCKED_TERMS.get(normalized, [])
    value = f" {str(text or '').lower()} "
    return any(term in value for term in blocked)


def sanitize_plan_for_diet(plan: Dict[str, Any], dietary_type: Optional[str]) -> Dict[str, Any]:
    normalized = normalize_dietary_type(dietary_type) or "normal"
    replacements = SAFE_MEAL_REPLACEMENTS.get(normalized)
    if not replacements:
        return plan

    for day in plan.get("week_plan") or []:
        for meal_type in ("breakfast", "lunch", "dinner"):
            if violates_diet(day.get(meal_type), normalized):
                day[meal_type] = replacements[meal_type]

    shopping_list = plan.get("shopping_list") or []
    if isinstance(shopping_list, list):
        cleaned = [item for item in shopping_list if not violates_diet(item, normalized)]
        for item in SAFE_SHOPPING_REPLACEMENTS.get(normalized, []):
            if item not in cleaned:
                cleaned.append(item)
        plan["shopping_list"] = cleaned
    return plan


def build_dietary_instruction(dietary_type: Optional[str]) -> str:
    normalized = normalize_dietary_type(dietary_type) or "normal"
    if normalized == "normal":
        return (
            "Dietary requirement: normal balanced diet with no special restriction. "
            "Include vegetarian or non-vegetarian meals as appropriate, while still matching the user's goal, allergies, and stated preferences."
        )
    if normalized == "vegan":
        return (
            "Dietary requirement: vegan only. "
            "Do not include dairy, paneer, curd, ghee, chicken, meat, fish, seafood, eggs, bone broth, gelatin, or honey."
        )
    if normalized == "vegetarian":
        return f"Dietary requirement: vegetarian only. {STRICT_VEGETARIAN_BLOCKLIST}"
    if normalized == "eggetarian":
        return (
            "Dietary requirement: eggetarian / ovo-vegetarian. Eggs are allowed. "
            "Do not include chicken, meat, fish, seafood, bone broth, gelatin, or any animal flesh."
        )
    if normalized == "pescatarian":
        return (
            "Dietary requirement: pescatarian. Fish and seafood are allowed. "
            "Do not include chicken, lamb, mutton, pork, beef, or other land-animal meat."
        )
    if normalized == "keto":
        return (
            "Dietary requirement: keto / low-carb. Keep meals low in carbohydrates. "
            "Avoid rice, wheat, roti, chapati, bread, oats, poha, upma, sugar, potatoes, and high-carb legumes. "
            "Prefer paneer, tofu, eggs, fish, chicken, low-carb vegetables, nuts, seeds, and healthy fats unless restricted elsewhere."
        )
    return f"Dietary requirement: {normalized}."


def parse_budget(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


@lru_cache(maxsize=64)
def get_live_grocery_price_context_cached(item_text: str, budget_weekly: int) -> str:
    query = (
        "India online grocery current prices INR "
        f"{item_text[:350]} weekly grocery budget {budget_weekly}"
    )
    results = tavily_search(query, max_results=3)
    snippets = []
    for result in results:
        url = result.get("url", "N/A")
        content = result.get("content", "")
        if content:
            snippets.append(f"Source: {url}\nContent: {content}")
    return "\n---\n".join(snippets)


def get_live_grocery_price_context(items: Any, budget_weekly: int) -> str:
    item_text = ", ".join(str(item) for item in items if str(item).strip())
    if not item_text:
        return ""
    return get_live_grocery_price_context_cached(item_text, budget_weekly)


def estimate_shopping_cost(items: Any, budget_weekly: int = 0) -> Dict[str, Any]:
    shopping_items = [str(item) for item in items if str(item).strip()] if isinstance(items, list) else []
    if not shopping_items:
        return {"total_cost": 0, "source": "no_items", "items": []}

    price_context = get_live_grocery_price_context(shopping_items, budget_weekly)
    if not price_context:
        return {
            "total_cost": budget_weekly if budget_weekly >= 1500 else 0,
            "source": "live_price_unavailable",
            "items": [],
            "note": "Live grocery prices were unavailable, so showing the weekly budget as the planning limit instead of a fake estimate.",
        }

    prompt = f"""
    Estimate the total weekly grocery cost in Indian Rupees using ONLY the outside-world price snippets below.
    If a grocery item does not appear exactly, infer from the closest matching grocery price in the snippets.
    Do not use any internal or hardcoded price table.

    Shopping list:
    {json.dumps(shopping_items, ensure_ascii=False)}

    Outside-world price snippets:
    {price_context}

    Return ONLY valid JSON:
    {{
      "total_cost": 0,
      "items": [
        {{"name": "Rice 2kg", "estimated_cost": 0, "source_url": "https://..."}}
      ],
      "source": "web_search",
      "note": "short note about estimate confidence"
    }}
    """
    try:
        response = openai_client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        parsed = json.loads(response.choices[0].message.content)
        parsed["total_cost"] = parse_budget(parsed.get("total_cost"))
        parsed["source"] = parsed.get("source") or "web_search"
        return parsed
    except Exception as exc:
        return {
            "total_cost": 0,
            "source": "live_price_parse_error",
            "items": [],
            "note": f"Could not parse outside-world grocery estimate: {exc}",
        }


FEEDBACK_EXCLUSION_TERMS = {
    "dal": ["dal", "daal", "lentil", "lentils"],
    "curd": ["curd", "yogurt", "yoghurt", "raita"],
}

FEEDBACK_MEAL_REPLACEMENTS = [
    (r"\bmoong\s+dal\s+(cheela|chilla|chila|chilla)\b", "Besan cheela"),
    (r"\bdal\s+tadka\b", "Chana masala"),
    (r"\bdal\s+chawal\b", "Rajma rice"),
    (r"\bmasoor\s+dal\b", "Rajma curry"),
    (r"\bdal\s+makhani\b", "Paneer makhani"),
    (r"\bdal\s+soup\b", "vegetable soup"),
    (r"\b\w+\s+dal\s+\w+\b", "Besan vegetable cheela"),
    (r"\b\w+\s+dal\b", "chana"),
    (r"\bdal\s+\w+\b", "chana curry"),
    (r"\bkhichdi\b", "vegetable pulao"),
    (r"\bkadhi\b", "besan vegetable curry"),
    (r"\bsambar\b", "tomato chutney"),
    (r"\bcurd\b", "mint chutney"),
    (r"\byogurt\b", "mint chutney"),
    (r"\byoghurt\b", "mint chutney"),
    (r"\braita\b", "cucumber salad"),
    (r"\blentils?\b", "chana"),
]


def extract_feedback_exclusions(feedback_text: str) -> List[str]:
    text = str(feedback_text or "").lower()
    if not text:
        return []
    exclusion_words = ("no ", "without", "avoid", "remove", "don't", "dont", "not include", "exclude")
    if not any(word in text for word in exclusion_words):
        return []
    exclusions = []
    for canonical, terms in FEEDBACK_EXCLUSION_TERMS.items():
        if any(re.search(rf"\b{re.escape(term)}\b", text) for term in terms):
            exclusions.append(canonical)
    return exclusions


def feedback_exclusion_instruction(feedback_text: str) -> str:
    exclusions = extract_feedback_exclusions(feedback_text)
    if not exclusions:
        return ""
    banned_terms = []
    for exclusion in exclusions:
        banned_terms.extend(FEEDBACK_EXCLUSION_TERMS.get(exclusion, [exclusion]))
    return (
        "Hard user exclusions from feedback: "
        f"{', '.join(sorted(set(banned_terms)))}. "
        "Do not include these words or ingredients in any meal, add-on, portion note, or shopping-list item."
    )


def text_has_feedback_exclusion(value: Any, exclusions: List[str]) -> bool:
    text = str(value or "").lower()
    return any(
        re.search(rf"\b{re.escape(term)}\b", text)
        for exclusion in exclusions
        for term in FEEDBACK_EXCLUSION_TERMS.get(exclusion, [exclusion])
    )


def replace_feedback_exclusions(value: Any, exclusions: List[str]) -> str:
    text = str(value or "").strip()
    if not text or not exclusions:
        return text
    for pattern, replacement in FEEDBACK_MEAL_REPLACEMENTS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    if text_has_feedback_exclusion(text, exclusions):
        text = "Chana paneer vegetable bowl with roti and salad"
    text = re.sub(r"\s+", " ", text).strip(" ,")
    return text


def apply_feedback_exclusions(plan: Dict[str, Any], feedback_text: str) -> Dict[str, Any]:
    exclusions = extract_feedback_exclusions(feedback_text)
    if not exclusions:
        return plan
    plan["feedback_exclusions"] = exclusions

    for day in plan.get("week_plan") or []:
        for meal_type in ("breakfast", "lunch", "dinner"):
            day[meal_type] = replace_feedback_exclusions(day.get(meal_type), exclusions)

    shopping_list = plan.get("shopping_list") or []
    if isinstance(shopping_list, list):
        cleaned = [
            str(item)
            for item in shopping_list
            if str(item).strip() and not text_has_feedback_exclusion(item, exclusions)
        ]
        replacements = ["Chana 1kg", "Rajma 1kg", "Soya chunks 500g", "Tofu 500g", "Paneer 500g"]
        for item in replacements:
            if item not in cleaned:
                cleaned.append(item)
        plan["shopping_list"] = cleaned
    return plan


def apply_budget_summary(plan: Dict[str, Any], budget_weekly: int, goal: str) -> Dict[str, Any]:
    days = plan.get("week_plan") or []
    targets = GOAL_TARGETS.get(goal, GOAL_TARGETS["maintenance"])
    exclusions = plan.get("feedback_exclusions") or []
    protein_add_on = "with tofu paneer protein add-on" if exclusions else "with dal curd protein add-on"
    for day in days:
        total_calories = float(day.get("total_calories") or 0)
        total_protein = float(day.get("total_protein") or 0)
        if total_calories < targets["min_calories"] or total_protein < targets["min_protein"]:
            calorie_gap = max(0, targets["min_calories"] - total_calories)
            protein_gap = max(0, targets["min_protein"] - total_protein)
            day["dinner"] = replace_feedback_exclusions(f"{day.get('dinner', '')} {protein_add_on}".strip(), exclusions)
            day["dinner_calories"] = round(float(day.get("dinner_calories") or 0) + calorie_gap)
            day["dinner_protein"] = round(float(day.get("dinner_protein") or 0) + protein_gap)
            day["total_calories"] = round(total_calories + calorie_gap)
            day["total_protein"] = round(total_protein + protein_gap)

    day_count = max(len(days), 1)
    avg_calories = round(sum(float(day.get("total_calories") or 0) for day in days) / day_count)
    avg_protein = round(sum(float(day.get("total_protein") or 0) for day in days) / day_count)
    grocery_estimate = estimate_shopping_cost(plan.get("shopping_list") or [], budget_weekly)
    estimated_cost = parse_budget(grocery_estimate.get("total_cost"))
    within_budget = bool(budget_weekly >= 1500 and estimated_cost and estimated_cost <= budget_weekly)
    plan["grocery_estimate"] = grocery_estimate
    if grocery_estimate.get("note"):
        plan["budget_note"] = grocery_estimate.get("note")
    calorie_score = 35 if targets["min_calories"] <= avg_calories <= targets["max_calories"] else 18
    protein_score = 35 if avg_protein >= targets["min_protein"] else 18
    budget_score = 20 if within_budget or grocery_estimate.get("source") == "live_price_unavailable" else 8
    variety_score = 10 if len({day.get("breakfast") for day in days}) >= 5 else 5
    plan["week_summary"] = {
        "healthy_score": min(100, calorie_score + protein_score + budget_score + variety_score),
        "avg_calories": avg_calories,
        "avg_protein": avg_protein,
        "total_budget": estimated_cost,
        "budget_limit": budget_weekly,
        "raw_estimated_cost": estimated_cost,
        "estimate_source": grocery_estimate.get("source", "web_search"),
        "within_budget": within_budget,
    }
    if budget_weekly >= 1500 and not within_budget:
        plan["goal_summary"] = (
            f"{plan.get('goal_summary', '')} Grocery estimate is still tight for the ₹{budget_weekly} weekly budget; increase budget or reduce variety."
        ).strip()
    return plan


def estimate_person_targets(person: Dict[str, Any]) -> Dict[str, int]:
    goal = person.get("goal") or "maintenance"
    base = GOAL_TARGETS.get(goal, GOAL_TARGETS["maintenance"])
    weight = float(person.get("weight_kg") or 0)
    height = float(person.get("height_cm") or 0)
    age = float(person.get("age") or 30)
    gender = str(person.get("gender") or "").lower()

    if weight and height:
        bmr = (10 * weight) + (6.25 * height) - (5 * age)
        bmr += 5 if gender == "male" else -161 if gender == "female" else -80
        maintenance = max(1200, round(bmr * 1.35))
        if goal == "weight_loss":
            calories = max(base["min_calories"], min(base["max_calories"], maintenance - 350))
        elif goal == "muscle_gain":
            calories = max(base["min_calories"], min(base["max_calories"], maintenance + 250))
        else:
            calories = max(base["min_calories"], min(base["max_calories"], maintenance))
    else:
        calories = round((base["min_calories"] + base["max_calories"]) / 2)

    protein_multiplier = 1.8 if goal == "muscle_gain" else 1.4 if goal == "weight_loss" else 1.1
    protein = max(base["min_protein"], round((weight or 55) * protein_multiplier))
    return {"calories": int(calories), "protein": int(protein)}


def build_people_profiles(user: Dict[str, Any]) -> List[Dict[str, Any]]:
    people = [{
        "id": f"user-{user.get('id')}",
        "name": user.get("name") or "Main profile",
        "relationship": "main",
        "age": user.get("age") or 0,
        "gender": user.get("gender") or "",
        "weight_kg": user.get("weight_kg") or 0,
        "height_cm": user.get("height_cm") or 0,
        "goal": user.get("goal") or "maintenance",
        "dietary_type": normalize_dietary_type(user.get("dietary_type")) or "normal",
        "allergies": user.get("allergies") or [],
        "preferences": user.get("preferences") or [],
    }]
    for member in get_family_members(user.get("id")):
        people.append({
            "id": f"member-{member.get('id') or member.get('name')}",
            "name": member.get("name") or "Family member",
            "relationship": "family",
            "age": member.get("age") or 0,
            "gender": member.get("gender") or "",
            "weight_kg": member.get("weight_kg") or 0,
            "height_cm": member.get("height_cm") or 0,
            "goal": member.get("goal") or user.get("goal") or "maintenance",
            "dietary_type": normalize_dietary_type(member.get("dietary_type")) or normalize_dietary_type(user.get("dietary_type")) or "normal",
            "allergies": member.get("allergies") or [],
            "preferences": member.get("preferences") or [],
        })
    return people


def build_people_preference_context(user: Dict[str, Any]) -> str:
    lines = []
    for person in build_people_profiles(user):
        allergies = ", ".join(person.get("allergies") or []) or "None"
        preferences = ", ".join(person.get("preferences") or []) or "None"
        lines.append(
            f"- {person.get('name')}: goal={person.get('goal') or 'maintenance'}, "
            f"diet={person.get('dietary_type') or 'normal'}, allergies={allergies}, preferences={preferences}"
        )
    return "\n".join(lines) or "None"


def personalize_meal_name(
    name: str,
    meal_type: str,
    goal: str,
    dietary_type: str = "normal",
    exclusions: Optional[List[str]] = None,
) -> str:
    base = str(name or "").strip()
    if not base:
        return base
    base = replace_feedback_exclusions(base, exclusions or [])
    diet = normalize_dietary_type(dietary_type) or "normal"
    if violates_diet(base, diet):
        replacements = SAFE_MEAL_REPLACEMENTS.get(diet) or SAFE_MEAL_REPLACEMENTS.get("vegetarian")
        if replacements:
            base = replacements.get(meal_type.lower(), base)
    if diet == "pescatarian" and meal_type in {"Lunch", "Dinner"} and not text_has_feedback_exclusion(base, exclusions or []):
        lower_base = base.lower()
        if not any(word in lower_base for word in ["fish", "seafood", "prawn", "shrimp"]):
            if meal_type == "Lunch":
                base = "Fish curry with rice and cucumber salad"
            else:
                base = "Grilled fish with vegetables and roti"
    lower = base.lower()
    if goal == "weight_loss":
        if meal_type == "Breakfast":
            return f"Light {base} with extra vegetables"
        if "rice" in lower:
            return base.replace("Rice", "small rice portion").replace("rice", "small rice portion")
        if "chapati" in lower or "roti" in lower:
            return f"{base} with extra salad and smaller roti portion"
        return f"Light {base} with salad"
    if goal == "muscle_gain":
        if any(word in lower for word in ["fish", "paneer", "tofu", "dal", "chana", "rajma", "soya"]):
            return f"High-protein {base}"
        return f"{base} with paneer/tofu protein add-on"
    if goal == "maintenance":
        if base.lower().startswith(("light ", "high-protein ")):
            return base
        return f"Balanced {base}"
    return base


def person_meal(
    meal_type: str,
    day: Dict[str, Any],
    goal: str,
    targets: Dict[str, int],
    dietary_type: str = "normal",
    exclusions: Optional[List[str]] = None,
) -> Dict[str, Any]:
    key = meal_type.lower()
    calories_key = f"{key}_calories"
    protein_key = f"{key}_protein"
    split = {"Breakfast": 0.28, "Lunch": 0.37, "Dinner": 0.35}.get(meal_type, 0.33)
    return {
        "type": meal_type,
        "name": personalize_meal_name(day.get(key, ""), meal_type, goal, dietary_type, exclusions),
        "calories": round(targets["calories"] * split),
        "protein": round(targets["protein"] * split),
        "base_calories": day.get(calories_key, 0),
        "base_protein": day.get(protein_key, 0),
    }


def attach_people_plans(plan: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
    base_days = plan.get("week_plan") or []
    exclusions = plan.get("feedback_exclusions") or []
    plan_status = plan.get("status") or "planned"
    people_plans = []
    people = build_people_profiles(user)
    has_pescatarian = any((person.get("dietary_type") or "") == "pescatarian" for person in people)
    if has_pescatarian and isinstance(plan.get("shopping_list"), list):
        for item in ["Fish fillets 1kg", "Lemon 4", "Fresh coriander 1 bunch"]:
            if item not in plan["shopping_list"]:
                plan["shopping_list"].append(item)
    for person in people:
        targets = estimate_person_targets(person)
        goal = person.get("goal") or "maintenance"
        dietary_type = person.get("dietary_type") or "normal"
        adjusted_days = []
        for day in base_days:
            base_calories = float(day.get("total_calories") or 0)
            base_protein = float(day.get("total_protein") or 0)
            needs_more = targets["calories"] > base_calories or targets["protein"] > base_protein
            if goal == "muscle_gain" and needs_more:
                portion_note = "Add paneer/tofu, sprouts, chana, or extra roti to match this person's muscle-gain target."
            elif goal == "weight_loss":
                portion_note = "Use smaller rice/roti portions and more salad/vegetables for this person's weight-loss target."
            elif needs_more:
                portion_note = "Adjust portions with chana, paneer/tofu, rice, or roti to meet this person's maintenance target."
            else:
                portion_note = "Base portions fit this person's target."
            portion_note = replace_feedback_exclusions(portion_note, exclusions)
            adjusted_days.append({
                "day": day.get("day") or day.get("day_name") or "",
                "calories": targets["calories"],
                "protein": targets["protein"],
                "status": plan_status,
                "portion_note": portion_note,
                "meals": [
                    person_meal("Breakfast", day, goal, targets, dietary_type, exclusions),
                    person_meal("Lunch", day, goal, targets, dietary_type, exclusions),
                    person_meal("Dinner", day, goal, targets, dietary_type, exclusions),
                ],
            })
        people_plans.append({
            "person_id": person["id"],
            "name": person["name"],
            "goal": goal,
            "gender": person.get("gender") or "",
            "dietary_type": person.get("dietary_type") or "normal",
            "target_calories": targets["calories"],
            "target_protein": targets["protein"],
            "days": adjusted_days,
        })
    plan["people_plans"] = people_plans
    return plan


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
        max_iterations=8,
        early_stopping_method="generate",
    )

    return agent


def generate_structured_plan(
    user_id: int,
    agent_result: str,
    goal: str,
    feedback_text: str = "",
    avoid_meals: Optional[List[str]] = None,
) -> Dict:
    """Use OpenAI to convert agent text output into structured week plan."""
    try:
        user = get_user(user_id)
        targets = GOAL_TARGETS.get(goal, GOAL_TARGETS["maintenance"])
        budget_weekly = parse_budget(user.get("budget_weekly") if user else 0)

        prompt = f"""
        Based on this meal planning research:
        {agent_result}

        User: {user.get('name') if user else 'Unknown'}
        Goal: {goal}
        Weekly grocery budget: ₹{budget_weekly}
        Daily calorie target: {targets['min_calories']}-{targets['max_calories']} kcal
        Daily protein target: {targets['min_protein']}-{targets['max_protein']}g
        {build_dietary_instruction(user.get('dietary_type') if user else None)}
        Allergies to avoid: {', '.join(user.get('allergies') or []) if user else 'None'}
        Food preferences: {', '.join(user.get('preferences') or []) if user else 'None'}
        Per-person family preferences and restrictions:
        {build_people_preference_context(user or {})}
        User feedback to apply: {feedback_text or 'None'}
        {feedback_exclusion_instruction(feedback_text)}
        Meals to avoid repeating from recent weeks: {', '.join(avoid_meals or []) or 'None'}

        Generate a complete 7-day Indian meal plan in this EXACT JSON format.
        Every day must meet the user's target range:
        - total_calories must be between {targets['min_calories']} and {targets['max_calories']}
        - total_protein must be at least {targets['min_protein']}g
        - Do not repeat the listed recent meals unless absolutely necessary for diet, allergy, or budget constraints.
        - Make each day meaningfully different from the other days in this generated week.
        - Treat preferences as meal-selection requirements: cuisine, spice level, cooking style, disliked foods, preferred staples, and meal format must influence the dish choices.
        - If a preference conflicts with allergy, dietary type, medical safety, or budget, follow safety/diet/budget first and choose the closest matching alternative.
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
                    "dinner": "Tofu tikka with sabzi",
                    "dinner_calories": 420,
                    "dinner_protein": 26,
                    "total_calories": 1180,
                    "total_protein": 56,
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
                    "dinner": "Soya chunk curry with chapati",
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
                    "dinner": "Tofu saag with chapati",
                    "dinner_calories": 430,
                    "dinner_protein": 28,
                    "total_calories": 1170,
                    "total_protein": 59,
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
                    "lunch": "Kadhi pakora with rice",
                    "lunch_calories": 470,
                    "lunch_protein": 18,
                    "dinner": "Bhindi masala with dal and chapati",
                    "dinner_calories": 380,
                    "dinner_protein": 16,
                    "total_calories": 1230,
                    "total_protein": 54,
                    "fits_goal": true
                }},
                {{
                    "day": "Sunday",
                    "breakfast": "Paneer bhurji with toast",
                    "breakfast_calories": 350,
                    "breakfast_protein": 18,
                    "lunch": "Soya chunk curry with rice and raita",
                    "lunch_calories": 500,
                    "lunch_protein": 30,
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
                "Paneer 500g", "Tofu 500g", "Soya chunks 500g", "Dal assorted 1kg",
                "Tomatoes 1kg", "Onions 1kg", "Spinach 500g",
                "Milk 2L", "Curd 500g",
                "Turmeric powder 100g", "Cumin seeds 100g", "Coriander powder 100g",
                "Garam masala 100g", "Mustard oil 1L"
            ],
            "goal_summary": "This 7-day plan averages 1150 kcal/day and 55g protein/day, supporting your weight loss goal of 1200-1500 kcal/day while keeping meals varied and nutritious."
        }}

        Make all 7 days use the actual recipes found in the research above.
        Adjust the example JSON to use real recipes from the research.
        If user feedback is provided, adjust meal choices accordingly. If the feedback says no, avoid, remove, without, or exclude an ingredient, that is a hard exclusion for the entire regenerated plan.
        Make the final dish names visibly reflect the user's preferences where possible.
        For family members with different preferences, keep the base meal compatible and use portion_note or simple swaps/add-ons in people_plans.
        Do not generate low-calorie weight-loss meals unless the goal is weight_loss.
        For maintenance and muscle_gain, add enough allowed protein and portions to hit targets. Use paneer/tofu/eggs if allowed, chana, rajma, soya chunks, rice/roti, and legumes unless the user's feedback excludes them.
        Plan the full week's grocery list within the ₹{budget_weekly} weekly budget.
        The shopping_list must be realistic for Indian grocery prices and its estimated total must be less than or equal to ₹{budget_weekly}.
        If the budget is tight, reduce premium proteins and choose allowed budget staples like chana, rajma, soya chunks, rice, atta, seasonal vegetables, eggs only if allowed, and paneer/tofu in controlled quantities.
        Prefer budget-friendly Indian staples that are allowed by dietary type, allergies, and user feedback.
        Avoid expensive ingredients like avocado, quinoa, berries, imported cheese, almond milk, almond flour, and broccoli unless the budget clearly allows them.
        Do not repeat the same breakfast, lunch, or dinner across consecutive days.
        Monday, Tuesday, and Wednesday must all have different meal names.
        Keep the full week varied across grains, proteins, vegetables, and cooking styles.
        Keep every meal compliant with the dietary requirement above.
        If the dietary requirement conflicts with any example meal, replace that example meal.
        Return ONLY the JSON object.
        """

        response = openai_client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )

        result = apply_feedback_exclusions(
            sanitize_plan_for_diet(json.loads(response.choices[0].message.content), user.get("dietary_type") if user else None),
            feedback_text,
        )
        result["user_id"] = user_id
        return attach_people_plans(apply_budget_summary(result, budget_weekly, goal), user or {})

    except Exception as e:
        print(f"⚠️ Structured plan error: {str(e)}")
        # return fallback plan
        fallback_days = [
            ("Monday", "Poha with peanuts and vegetables", 320, 11, "Dal chawal with bhindi sabzi", 470, 19, "Palak paneer with phulka", 430, 22),
            ("Tuesday", "Oats upma with mixed vegetables", 300, 10, "Rajma brown rice bowl with salad", 500, 23, "Tofu tikka with vegetable soup", 420, 28),
            ("Wednesday", "Idli with sambar and chutney", 280, 10, "Chole with jeera rice and kachumber", 510, 21, "Soya chunk curry with chapati", 450, 30),
            ("Thursday", "Moong dal cheela with curd", 340, 18, "Vegetable khichdi with cucumber raita", 460, 18, "Matar paneer with millet roti", 470, 25),
            ("Friday", "Paneer bhurji toast with salad", 360, 22, "Masoor dal with rice and cabbage sabzi", 480, 21, "Vegetable pulao with dal soup", 430, 18),
            ("Saturday", "Besan dhokla with green chutney", 310, 14, "Kadhi rice with carrot salad", 500, 19, "Bhindi masala with dal and chapati", 460, 20),
            ("Sunday", "Sprouts chilla with tomato chutney", 330, 20, "Vegetable biryani with raita", 520, 20, "Lauki kofta with phulka and dal soup", 450, 22),
        ]
        fallback_plan = apply_feedback_exclusions(sanitize_plan_for_diet({
            "user_id": user_id,
            "week_plan": [
                {
                    "day": day,
                    "breakfast": breakfast,
                    "breakfast_calories": breakfast_calories,
                    "breakfast_protein": breakfast_protein,
                    "lunch": lunch,
                    "lunch_calories": lunch_calories,
                    "lunch_protein": lunch_protein,
                    "dinner": dinner,
                    "dinner_calories": dinner_calories,
                    "dinner_protein": dinner_protein,
                    "total_calories": breakfast_calories + lunch_calories + dinner_calories,
                    "total_protein": breakfast_protein + lunch_protein + dinner_protein,
                    "fits_goal": True,
                }
                for (
                    day,
                    breakfast,
                    breakfast_calories,
                    breakfast_protein,
                    lunch,
                    lunch_calories,
                    lunch_protein,
                    dinner,
                    dinner_calories,
                    dinner_protein,
                ) in fallback_days
            ],
            "shopping_list": [
                "Rice", "Dal", "Vegetables", "Paneer",
                "Turmeric powder", "Cumin seeds", "Coriander powder", "Garam masala", "Mustard oil"
            ],
            "goal_summary": "Basic weight loss meal plan with Indian recipes."
        }, user.get("dietary_type") if user else None), feedback_text)
        return attach_people_plans(apply_budget_summary(fallback_plan, parse_budget((user or {}).get("budget_weekly") if user else 0), goal), user or {})


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
            dietary_type=user_data.get("dietary_type"),
            dietary_preferences=user_data.get("dietary_preferences"),
            allergies=user_data.get("allergies"),
            preferences=user_data.get("preferences"),
        )

        if not user or "id" not in user:
            return None, "❌ Failed to create user account."

        user_id = user["id"]
        family_count = 0

        for member in family_members:
            normalized_member = normalize_family_member(member)
            result = add_family_member(
                user_id=user_id,
                name=normalized_member.get("name", "Family Member"),
                age=normalized_member.get("age", 0),
                dietary_type=normalized_member.get("dietary_type", "normal"),
                allergies=normalized_member.get("allergies", []),
                preferences=normalized_member.get("preferences", []),
                telegram=normalized_member.get("telegram", ""),
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


def recent_meal_names(user_id: int, limit: int = 42) -> List[str]:
    names: List[str] = []
    for plan in get_user_history(user_id)[:4]:
        for day in plan.get("day_meals") or []:
            for key in ("breakfast", "lunch", "dinner"):
                value = str(day.get(key) or "").strip()
                if value and value not in names:
                    names.append(value)
                if len(names) >= limit:
                    return names
    return names


def generate_meal_plan(user_id: int, feedback_text: str = "", week_start: Optional[str] = None) -> Dict[str, Any]:
    """Generate a 7-day personalized meal plan for a user and family."""
    try:
        user = get_user(user_id)
        if not user:
            return {"status": "error", "message": f"User {user_id} not found"}

        goal = user.get("goal", "maintenance")
        targets = GOAL_TARGETS.get(goal, GOAL_TARGETS["maintenance"])
        dietary_type = normalize_dietary_type(user.get("dietary_type")) or "normal"
        allergies = ", ".join(user.get("allergies") or []) or "None"
        preferences = ", ".join(user.get("preferences") or []) or "None"
        budget_weekly = parse_budget(user.get("budget_weekly"))
        avoid_meals = recent_meal_names(user_id)
        target_week = week_start or str(date.today() - timedelta(days=date.today().weekday()))

        agent_result = f"""
        Fast profile context for meal planning:
        User: {user.get('name')}
        Goal: {goal}
        Target week starts: {target_week}
        Dietary type: {dietary_type}
        Budget: ₹{budget_weekly}
        Calories: {targets['min_calories']}-{targets['max_calories']} kcal/day
        Protein: {targets['min_protein']}-{targets['max_protein']}g/day
        Allergies: {allergies}
        Preferences: {preferences}
        Per-person family preferences and restrictions:
        {build_people_preference_context(user)}
        Feedback: {feedback_text or 'None'}
        {feedback_exclusion_instruction(feedback_text)}
        Recent meals to avoid repeating: {', '.join(avoid_meals) or 'None'}

        Use common Indian home-cooking meals and budget staples. Preferences must affect dish choice, spice level, cuisine style, ingredients, and substitutions. If feedback says no/avoid/without/remove an ingredient, exclude it from all meals and groceries. Do not call tools.
        """

        # convert to structured JSON
        structured_plan = generate_structured_plan(user_id, agent_result, goal, feedback_text, avoid_meals)

        # save to Supabase
        saved_plan = save_meal_plan(
            user_id=user_id,
            goal=goal,
            week_start=target_week,
        )

        plan_id = saved_plan.get("id", 0) if saved_plan else 0

        # save day meals
        if structured_plan.get("week_plan") and plan_id:
            save_day_meals(plan_id, structured_plan["week_plan"])
            print(f"✅ {len(structured_plan['week_plan'])} days saved to Supabase")

        if structured_plan.get("shopping_list") and plan_id:
            estimate = structured_plan.get("grocery_estimate") or {}
            save_grocery_list(plan_id, structured_plan["shopping_list"], parse_budget(estimate.get("total_cost")))
            print("✅ Grocery list saved to Supabase")

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
