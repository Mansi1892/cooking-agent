from typing import Any, Dict, List, Optional


def normalize_dietary_type(value: Any) -> Optional[str]:
    """Normalize incoming diet values from the UI or API into backend dietary types."""
    if value is None:
        return None

    if isinstance(value, list):
        value = " ".join(str(v) for v in value if v)

    text = str(value).strip().lower()
    if not text:
        return None

    text = text.replace("_", "-")

    if text in {"normal", "normal-diet", "normal diet", "regular", "regular-diet", "regular diet", "balanced", "no-preference", "no preference", "none"}:
        return "normal"
    if text in {"non-vegetarian", "non vegetarian", "omnivore", "meat-eater", "meat eater"}:
        return "non-vegetarian"
    if text in {"pescatarian", "pescetarian", "fish-based", "fish based"}:
        return "pescatarian"
    if text in {"keto", "ketogenic", "low-carb", "low carb"}:
        return "keto"
    if text in {"eggetarian", "eggitarian", "ovo-vegetarian", "ovo vegetarian", "egg-vegetarian", "egg vegetarian"}:
        return "eggetarian"
    if text in {"vegetarian", "veg", "veggie", "veggie-only", "vegetarian-only"}:
        return "vegetarian"
    if text in {"vegan", "plant-based", "plant based"}:
        return "vegan"

    if "normal diet" in text or "regular diet" in text or "no preference" in text:
        return "normal"
    if "non-vegetarian" in text or "non vegetarian" in text or "omnivore" in text:
        return "non-vegetarian"
    if "pesc" in text or "fish" in text:
        return "pescatarian"
    if "keto" in text or "ketogenic" in text or "low-carb" in text or "low carb" in text:
        return "keto"
    if "eggetarian" in text or "eggitarian" in text or "ovo-vegetarian" in text or "ovo vegetarian" in text or "egg vegetarian" in text:
        return "eggetarian"
    if "vegan" in text:
        return "vegan"
    if "vegetarian" in text:
        return "vegetarian"

    return None


def normalize_family_member(member: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a family member payload from the UI into the backend format."""
    if not isinstance(member, dict):
        member = {}

    dietary_type = normalize_dietary_type(
        member.get("dietary_type")
        or member.get("dietary_preferences")
        or member.get("food_preference")
        or member.get("diet")
    )

    if not dietary_type:
        preferences = member.get("preferences") or []
        if isinstance(preferences, str):
            preferences = [preferences]
        preference_text = " ".join(str(p).lower() for p in preferences if p)
        if "normal diet" in preference_text or "regular diet" in preference_text or "no preference" in preference_text:
            dietary_type = "normal"
        elif "non-vegetarian" in preference_text or "non vegetarian" in preference_text or "omnivore" in preference_text:
            dietary_type = "non-vegetarian"
        elif "pesc" in preference_text or "fish" in preference_text:
            dietary_type = "pescatarian"
        elif "keto" in preference_text or "ketogenic" in preference_text or "low-carb" in preference_text or "low carb" in preference_text:
            dietary_type = "keto"
        elif "eggetarian" in preference_text or "eggitarian" in preference_text or "ovo-vegetarian" in preference_text or "ovo vegetarian" in preference_text or "egg vegetarian" in preference_text:
            dietary_type = "eggetarian"
        elif "vegan" in preference_text:
            dietary_type = "vegan"
        elif "veg" in preference_text or "vegetarian" in preference_text:
            dietary_type = "vegetarian"
        else:
            dietary_type = "normal"

    allergies = member.get("allergies") or []
    if isinstance(allergies, str):
        allergies = [allergies]

    preferences = member.get("preferences") or []
    if isinstance(preferences, str):
        preferences = [preferences]

    return {
        "name": member.get("name", "Family Member"),
        "age": member.get("age", 0),
        "dietary_type": dietary_type,
        "allergies": allergies,
        "preferences": preferences,
        "telegram": member.get("telegram", ""),
    }
