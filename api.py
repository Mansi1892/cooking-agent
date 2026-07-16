from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
import uvicorn

from database import (
    create_user,
    get_user,
    add_family_member,
    save_meal_plan,
    get_latest_plan,
    save_grocery_list,
    save_feedback,
    get_user_history,
)
from agent import run_onboarding, generate_meal_plan

app = FastAPI(title="Cooking Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class UserProfile(BaseModel):
    name: str
    email: Optional[str]
    timezone: Optional[str]
    dietary_preferences: Optional[List[str]] = Field(default_factory=list)


class FamilyMember(BaseModel):
    name: str
    age: Optional[int]
    dietary_preferences: Optional[List[str]] = Field(default_factory=list)


class OnboardingRequest(BaseModel):
    user: UserProfile
    family: Optional[List[FamilyMember]] = Field(default_factory=list)


class FeedbackRequest(BaseModel):
    user_id: str
    plan_id: str
    rating: Optional[int]
    notes: Optional[str]


@app.on_event("startup")
async def startup_event():
    # Basic sanity check: try to import DB functions and agent
    try:
        _ = get_user
    except Exception:
        raise


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/onboard")
async def onboard(payload: OnboardingRequest):
    # Create user and family members, then run onboarding agent
    user_data = payload.user.dict()
    user = create_user(user_data)
    for member in payload.family:
        add_family_member(user_id=user["id"], member=member.dict())
    # Run onboarding agent (async-friendly wrapper inside agent module)
    plan = run_onboarding(user["id"])  # returns initial plan dict or id
    return {"user": user, "plan": plan}


@app.post("/plan/generate/{user_id}")
async def plan_generate(user_id: str):
    user = get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    plan = generate_meal_plan(user_id)
    if not plan:
        raise HTTPException(status_code=500, detail="Plan generation failed")
    saved = save_meal_plan(user_id=user_id, plan=plan)
    return {"plan": plan, "saved": saved}


@app.get("/plan/{plan_id}")
async def get_plan(plan_id: str):
    plan = get_latest_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return {"plan": plan}


@app.get("/grocery/{plan_id}")
async def get_grocery(plan_id: str):
    plan = get_latest_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    grocery = plan.get("grocery_list") or []
    # Optionally persist grocery list
    save_grocery_list(plan_id=plan_id, grocery_list=grocery)
    return {"grocery": grocery}


@app.post("/feedback")
async def feedback(payload: FeedbackRequest):
    saved = save_feedback(payload.user_id, payload.plan_id, payload.dict())
    return {"saved": bool(saved)}


@app.get("/history/{user_id}")
async def history(user_id: str):
    hist = get_user_history(user_id)
    return {"history": hist}


if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
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