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

    if text in {"vegetarian", "veg", "veggie", "veggie-only", "vegetarian-only"}:
        return "vegetarian"
    if text in {"vegan", "plant-based", "plant based"}:
        return "vegan"
    if text in {"non-vegetarian", "non vegetarian", "omnivore", "meat-eater", "meat eater"}:
        return "non-vegetarian"
    if text in {"pescatarian", "fish-based", "fish based"}:
        return "non-vegetarian"

    if "vegetarian" in text:
        return "vegetarian"
    if "vegan" in text:
        return "vegan"
    if "non-vegetarian" in text or "non vegetarian" in text or "omnivore" in text:
        return "non-vegetarian"
    if "pesc" in text or "fish" in text:
        return "non-vegetarian"

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
        if "veg" in preference_text or "vegetarian" in preference_text:
            dietary_type = "vegetarian"
        elif "vegan" in preference_text:
            dietary_type = "vegan"
        else:
            dietary_type = "vegetarian"

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
