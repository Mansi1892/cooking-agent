from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from agent import run_onboarding, generate_meal_plan, handle_feedback
from database import (
    get_user,
    get_meal_plan,
    get_grocery_list
)

app = FastAPI(
    title="Cooking Agent API",
    description="AI-powered 7-day Indian meal planner backend",
    version="1.0.0"
)


# -------------------------
# Request Models
# -------------------------

class FamilyMember(BaseModel):
    name: str
    age: int
    gender: str
    height_cm: float
    weight_kg: float
    activity_level: str
    goal: str
    dietary_restrictions: Optional[List[str]] = []


class OnboardingRequest(BaseModel):
    name: str
    age: int
    gender: str
    height_cm: float
    weight_kg: float
    activity_level: str
    goal: str
    dietary_restrictions: Optional[List[str]] = []
    family_members: Optional[List[FamilyMember]] = []


class MealPlanRequest(BaseModel):
    user_id: str


class FeedbackRequest(BaseModel):
    plan_id: str
    feedback: str


# -------------------------
# Health Check
# -------------------------

@app.get("/")
def root():
    return {
        "message": "Cooking Agent Backend is running",
        "status": "healthy"
    }


@app.get("/health")
def health_check():
    return {
        "status": "ok"
    }


# -------------------------
# Onboarding API
# -------------------------

@app.post("/onboarding")
def onboarding(request: OnboardingRequest):
    try:
        user_data = {
            "name": request.name,
            "age": request.age,
            "gender": request.gender,
            "height_cm": request.height_cm,
            "weight_kg": request.weight_kg,
            "activity_level": request.activity_level,
            "goal": request.goal,
            "dietary_restrictions": request.dietary_restrictions
        }

        family_members = [
            member.model_dump()
            for member in request.family_members
        ]

        result = run_onboarding(user_data, family_members)

        return {
            "message": "Onboarding completed successfully",
            "data": result
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Onboarding failed: {str(e)}"
        )


# -------------------------
# Generate Meal Plan API
# -------------------------

@app.post("/meal-plan/generate")
def create_meal_plan(request: MealPlanRequest):
    try:
        user = get_user(request.user_id)

        if not user:
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )

        result = generate_meal_plan(request.user_id)

        return {
            "message": "Meal plan generated successfully",
            "data": result
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Meal plan generation failed: {str(e)}"
        )


# -------------------------
# Get Meal Plan API
# -------------------------

@app.get("/meal-plan/{plan_id}")
def fetch_meal_plan(plan_id: str):
    try:
        plan = get_meal_plan(plan_id)

        if not plan:
            raise HTTPException(
                status_code=404,
                detail="Meal plan not found"
            )

        return {
            "data": plan
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch meal plan: {str(e)}"
        )


# -------------------------
# Feedback API
# -------------------------

@app.post("/meal-plan/feedback")
def submit_feedback(request: FeedbackRequest):
    try:
        result = handle_feedback(
            plan_id=request.plan_id,
            feedback=request.feedback
        )

        return {
            "message": "Feedback handled successfully",
            "data": result
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Feedback handling failed: {str(e)}"
        )


# -------------------------
# Grocery List API
# -------------------------

@app.get("/grocery-list/{plan_id}")
def fetch_grocery_list(plan_id: str):
    try:
        grocery_list = get_grocery_list(plan_id)

        if not grocery_list:
            raise HTTPException(
                status_code=404,
                detail="Grocery list not found"
            )

        return {
            "data": grocery_list
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch grocery list: {str(e)}"
        )