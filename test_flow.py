from dotenv import load_dotenv
load_dotenv()

import json
from database import create_user, add_family_member, get_user, get_family_members
from tools import analyze_profile, search_recipes_db, get_nutrition_info
from agent import create_agent, generate_meal_plan

print("\n🧪 FULL FLOW TEST\n" + "="*50)

# Step 1 — create user
print("\n📝 Step 1: Creating user...")
user = create_user(
    name="Mansi",
    age=30,
    weight_kg=60,
    height_cm=162,
    goal="weight_loss",
    telegram_id="123456789",
    budget_weekly=2000
)
print(f"✅ User created: {user['name']} (ID: {user['id']})")
user_id = user["id"]

# Step 2 — add family member
print("\n👨‍👩‍👧 Step 2: Adding family member...")
member = add_family_member(
    user_id=user_id,
    name="Rahul",
    age=32,
    dietary_type="non-vegetarian",
    allergies=[],
    preferences=["North Indian", "spicy"]
)
print(f"✅ Member added: {member['name']}")

# Step 3 — analyze profile
print("\n🧠 Step 3: Analyzing health profile...")
profile = analyze_profile.invoke(str(user_id))
print(f"✅ Profile:\n{profile}")

# Step 4 — RAG recipe search
print("\n🔍 Step 4: Testing RAG search...")
recipes = search_recipes_db.invoke("healthy vegetarian breakfast low calorie")
print(f"✅ Recipes found:\n{recipes[:400]}...")

# Step 5 — nutrition info
print("\n🥗 Step 5: Testing nutrition search...")
nutrition = get_nutrition_info.invoke("paneer")
print(f"✅ Nutrition info:\n{nutrition[:300]}...")

# Step 6 — generate meal plan
print("\n🍽️ Step 6: Generating 7-day meal plan...")
print("(This takes 20-30 seconds...)")
plan = generate_meal_plan(user_id)
print(f"✅ Plan generated!")
print(f"   Plan ID: {plan.get('plan_id', 'N/A')}")
print(f"   Days: {len(plan.get('week_plan', []))}")

if plan.get('week_plan'):
    day1 = plan['week_plan'][0]
    print(f"\n📅 Monday preview:")
    print(f"   Breakfast: {day1.get('breakfast', 'N/A')}")
    print(f"   Lunch: {day1.get('lunch', 'N/A')}")
    print(f"   Dinner: {day1.get('dinner', 'N/A')}")
    print(f"   Calories: {day1.get('total_calories', 'N/A')} kcal")
    print(f"   Protein: {day1.get('total_protein', 'N/A')}g")

print("\n" + "="*50)
print("🎉 Full flow test complete!")
print("="*50)