from onboarding_utils import normalize_family_member


def test_frontend_diet_is_normalized_to_dietary_type():
    member = normalize_family_member({
        "name": "Priya",
        "diet": "Vegetarian",
        "allergies": ["peanuts"],
        "preferences": ["spicy"],
    })

    assert member["dietary_type"] == "vegetarian"
    assert member["allergies"] == ["peanuts"]
    assert member["preferences"] == ["spicy"]


def test_missing_diet_defaults_to_vegetarian_instead_of_non_vegetarian():
    member = normalize_family_member({
        "name": "Asha",
        "preferences": ["home food"],
    })

    assert member["dietary_type"] == "vegetarian"
