import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
import uvicorn

from database import (
    create_user,
    get_user,
    add_family_member,
    get_latest_plan,
    save_feedback,
    get_user_history,
)
from agent import run_onboarding, generate_meal_plan
from onboarding_utils import normalize_family_member

app = FastAPI(title="Smart Meal AI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Pydantic Models ---

class UserProfile(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    weight: Optional[float] = None
    height: Optional[float] = None
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    goal: Optional[str] = "maintenance"
    weekly_budget: Optional[float] = 0
    budget_weekly: Optional[float] = 0
    telegram: Optional[str] = None
    telegram_id: Optional[str] = None
    dietary_preference: Optional[str] = None
    dietary_preferences: Optional[List[str]] = Field(default_factory=list)
    allergies: Optional[List[str]] = Field(default_factory=list)
    preferences: Optional[List[str]] = Field(default_factory=list)


class FamilyMember(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    diet: Optional[str] = None
    dietary_type: Optional[str] = None
    dietary_preferences: Optional[List[str]] = Field(default_factory=list)
    allergies: Optional[List[str]] = Field(default_factory=list)
    preferences: Optional[List[str]] = Field(default_factory=list)
    telegram: Optional[str] = None


class OnboardingRequest(BaseModel):
    user: Optional[UserProfile] = None
    family: Optional[List[FamilyMember]] = Field(default_factory=list)
    family_members: Optional[List[FamilyMember]] = Field(default_factory=list)
    name: Optional[str] = None
    age: Optional[int] = None
    weight: Optional[float] = None
    height: Optional[float] = None
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    goal: Optional[str] = "maintenance"
    weekly_budget: Optional[float] = 0
    budget_weekly: Optional[float] = 0
    telegram: Optional[str] = None
    telegram_id: Optional[str] = None
    dietary_preference: Optional[str] = None
    dietary_preferences: Optional[List[str]] = Field(default_factory=list)
    allergies: Optional[List[str]] = Field(default_factory=list)
    preferences: Optional[List[str]] = Field(default_factory=list)


class FeedbackRequest(BaseModel):
    user_id: str
    plan_id: str
    rating: Optional[int] = None
    notes: Optional[str] = None


# --- Health Check ---

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/health")
async def api_health():
    return {"status": "ok"}


# --- Onboarding ---

@app.post("/onboard")
async def onboard(payload: OnboardingRequest):
    if payload.user is not None:
        user_data = payload.user.dict(exclude_unset=True)
        family_payload = [
            member.dict(exclude_unset=True)
            for member in (payload.family or [])
        ]
    else:
        user_data = payload.dict(
            exclude={"user", "family", "family_members"},
            exclude_unset=True
        )
        family_payload = [
            member.dict(exclude_unset=True)
            for member in (payload.family or payload.family_members or [])
        ]

    user_name = user_data.get("name") or "Unknown"
    age = user_data.get("age") or 0
    weight_kg = user_data.get("weight_kg") or user_data.get("weight") or 0
    height_cm = user_data.get("height_cm") or user_data.get("height") or 0
    goal = user_data.get("goal") or "maintenance"
    budget_weekly = user_data.get("budget_weekly") or user_data.get("weekly_budget") or 0
    telegram_id = user_data.get("telegram_id") or user_data.get("telegram") or ""
    dietary_preference = user_data.get("dietary_preference") or None
    dietary_preferences = (
        [dietary_preference]
        if dietary_preference and isinstance(dietary_preference, str)
        else []
    )
    allergies = user_data.get("allergies") or []
    preferences = user_data.get("preferences") or []

    user = create_user(
        name=user_name,
        age=age,
        weight_kg=weight_kg,
        height_cm=height_cm,
        goal=goal,
        telegram_id=telegram_id,
        budget_weekly=budget_weekly,
    )

    if not user or "id" not in user:
        raise HTTPException(status_code=500, detail="Failed to create user")

    normalized_family = [normalize_family_member(m) for m in family_payload]
    family_count = 0
    for member in normalized_family:
        result = add_family_member(
            user_id=user["id"],
            name=member.get("name", "Family Member"),
            age=member.get("age", 0),
            dietary_type=member.get("dietary_type", "vegetarian"),
            allergies=member.get("allergies", []),
            preferences=member.get("preferences", []),
        )
        if result and "id" in result:
            family_count += 1

    user_record = {
        "name": user_name,
        "age": age,
        "weight_kg": weight_kg,
        "height_cm": height_cm,
        "goal": goal,
        "telegram_id": telegram_id,
        "budget_weekly": budget_weekly,
    }

    user_id, confirmation = run_onboarding(user_record, normalized_family)

    return {
        "user_id": user["id"],
        "message": confirmation,
        "family_members_added": family_count,
    }


@app.post("/api/onboard")
async def api_onboard(payload: OnboardingRequest):
    return await onboard(payload)


# --- Meal Plan ---

@app.post("/plan/generate/{user_id}")
async def plan_generate(user_id: str):
    user = get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    plan = generate_meal_plan(int(user_id))
    if not plan:
        raise HTTPException(status_code=500, detail="Plan generation failed")

    return {"plan": plan}


@app.post("/api/plan/generate/{user_id}")
async def api_plan_generate(user_id: str):
    return await plan_generate(user_id)


@app.get("/plan/{plan_id}")
async def get_plan(plan_id: str):
    plan = get_latest_plan(int(plan_id)) if plan_id.isdigit() else None
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return {"plan": plan}


@app.get("/api/plan/{plan_id}")
async def api_get_plan(plan_id: str):
    return await get_plan(plan_id)


# --- Grocery ---

@app.get("/grocery/{plan_id}")
async def get_grocery(plan_id: str):
    plan = get_latest_plan(int(plan_id)) if plan_id.isdigit() else None
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    grocery = plan.get("grocery_list") or []
    return {"grocery": grocery}


@app.get("/api/grocery/{plan_id}")
async def api_get_grocery(plan_id: str):
    return await get_grocery(plan_id)


# --- Feedback ---

@app.post("/feedback")
async def feedback(payload: FeedbackRequest):
    saved = save_feedback(
        payload.plan_id,
        payload.user_id,
        payload.rating,
        payload.notes,
        False
    )
    return {"saved": bool(saved)}


@app.post("/api/feedback")
async def api_feedback(payload: FeedbackRequest):
    return await feedback(payload)


# --- History ---

@app.get("/history/{user_id}")
async def history(user_id: str):
    hist = get_user_history(user_id)
    return {"history": hist}


@app.get("/api/history/{user_id}")
async def api_history(user_id: str):
    return await history(user_id)


if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)