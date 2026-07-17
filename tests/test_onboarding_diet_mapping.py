from onboarding_utils import normalize_dietary_type, normalize_family_member


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


def test_missing_diet_defaults_to_normal_instead_of_restrictive_diet():
    member = normalize_family_member({
        "name": "Asha",
        "preferences": ["home food"],
    })

    assert member["dietary_type"] == "normal"


def test_non_vegetarian_is_not_misread_as_vegetarian():
    assert normalize_dietary_type("Non-vegetarian") == "non-vegetarian"


def test_preference_text_checks_specific_diets_before_veg_substrings():
    vegan_member = normalize_family_member({"name": "Dev", "preferences": ["vegan"]})
    non_veg_member = normalize_family_member({"name": "Ria", "preferences": ["non vegetarian"]})

    assert vegan_member["dietary_type"] == "vegan"
    assert non_veg_member["dietary_type"] == "non-vegetarian"


def test_pescatarian_and_keto_are_first_class_diet_types():
    assert normalize_dietary_type("no preference") == "normal"
    assert normalize_dietary_type("Pescatarian") == "pescatarian"
    assert normalize_dietary_type("fish based") == "pescatarian"
    assert normalize_dietary_type("Keto") == "keto"
    assert normalize_dietary_type("low-carb") == "keto"
    assert normalize_dietary_type("Eggetarian") == "eggetarian"
    assert normalize_dietary_type("ovo vegetarian") == "eggetarian"


def test_preference_text_detects_pescatarian_and_keto():
    fish_member = normalize_family_member({"name": "Nia", "preferences": ["fish based meals"]})
    keto_member = normalize_family_member({"name": "Sam", "preferences": ["low carb"]})
    egg_member = normalize_family_member({"name": "Avi", "preferences": ["eggetarian"]})

    assert fish_member["dietary_type"] == "pescatarian"
    assert keto_member["dietary_type"] == "keto"
    assert egg_member["dietary_type"] == "eggetarian"
