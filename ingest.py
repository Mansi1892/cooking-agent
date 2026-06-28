import os

from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY must be set in .env")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set in .env")

openai_client = OpenAI(
    api_key=OPENAI_API_KEY,
    base_url="https://openrouter.ai/api/v1"
)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

RECIPES = [
    {
        "name": "Masoor Dal Tadka",
        "content": "Main ingredients: masoor dal, onion, tomato, garlic, cumin, turmeric. Cooking time: 35 minutes. Method: simmer dal until soft, temper cumin and garlic in oil, add tomatoes and spices, mix with dal. Dietary type: vegetarian.",
        "cuisine": "North Indian",
        "dietary_type": "vegetarian",
        "tags": ["dal", "comfort", "protein"]
    },
    {
        "name": "Paneer Butter Masala",
        "content": "Main ingredients: paneer, tomato, cream, cashews, butter, garam masala. Cooking time: 40 minutes. Method: cook tomato gravy with spices, blend until smooth, add paneer cubes and cream. Dietary type: vegetarian.",
        "cuisine": "North Indian",
        "dietary_type": "vegetarian",
        "tags": ["paneer", "rich", "restaurant-style"]
    },
    {
        "name": "Aloo Gobi Sabzi",
        "content": "Main ingredients: potatoes, cauliflower, onion, tomato, ginger, turmeric. Cooking time: 30 minutes. Method: sauté onions and spices, add potatoes and cauliflower, cover and cook until tender. Dietary type: vegetarian.",
        "cuisine": "North Indian",
        "dietary_type": "vegetarian",
        "tags": ["sabzi", "potato", "cauliflower"]
    },
    {
        "name": "Palak Paneer",
        "content": "Main ingredients: spinach, paneer, onion, tomato, garlic, ginger. Cooking time: 35 minutes. Method: blanch spinach, cook onion and tomato, blend spinach, add paneer cubes. Dietary type: vegetarian.",
        "cuisine": "North Indian",
        "dietary_type": "vegetarian",
        "tags": ["spinach", "paneer", "greens"]
    },
    {
        "name": "Chole Masala",
        "content": "Main ingredients: chickpeas, onion, tomato, ginger, garlic, chole masala. Cooking time: 45 minutes. Method: simmer soaked chickpeas with spices, make onion-tomato gravy, combine and cook. Dietary type: vegetarian.",
        "cuisine": "North Indian",
        "dietary_type": "vegetarian",
        "tags": ["chickpeas", "protein", "curry"]
    },
    {
        "name": "Rajma Curry",
        "content": "Main ingredients: rajma, onion, tomato, ginger, garlic, cumin. Cooking time: 50 minutes. Method: cook kidney beans until soft, prepare onion-tomato masala, simmer beans in gravy. Dietary type: vegetarian.",
        "cuisine": "North Indian",
        "dietary_type": "vegetarian",
        "tags": ["kidney beans", "comfort", "protein"]
    },
    {
        "name": "Kadhi Pakora",
        "content": "Main ingredients: besan, yogurt, ginger, garlic, curry leaves, spinach. Cooking time: 35 minutes. Method: whisk yogurt and gram flour, simmer with spices, fry pakoras and add to kadhi. Dietary type: vegetarian.",
        "cuisine": "North Indian",
        "dietary_type": "vegetarian",
        "tags": ["kadhi", "yogurt", "comfort"]
    },
    {
        "name": "Paneer Bhurji",
        "content": "Main ingredients: paneer, onion, tomato, capsicum, turmeric, garam masala. Cooking time: 20 minutes. Method: sauté onion and spices, crumble paneer, cook briefly with vegetables. Dietary type: vegetarian.",
        "cuisine": "North Indian",
        "dietary_type": "vegetarian",
        "tags": ["quick", "protein", "breakfast"]
    },
    {
        "name": "Bhindi Masala",
        "content": "Main ingredients: okra, onion, tomato, cumin, coriander. Cooking time: 30 minutes. Method: sauté okra until crispy, cook with onion and spices. Dietary type: vegetarian.",
        "cuisine": "North Indian",
        "dietary_type": "vegetarian",
        "tags": ["sabzi", "gluten-free", "vegetable"]
    },
    {
        "name": "Baingan Bharta",
        "content": "Main ingredients: eggplant, tomato, onion, garlic, cilantro. Cooking time: 40 minutes. Method: roast eggplant, mash and cook with tomatoes and spices. Dietary type: vegetarian.",
        "cuisine": "North Indian",
        "dietary_type": "vegetarian",
        "tags": ["eggplant", "smoky", "rustic"]
    },
    {
        "name": "Chicken Curry",
        "content": "Main ingredients: chicken, onion, tomato, ginger, garlic, spices. Cooking time: 45 minutes. Method: brown chicken, cook onion-tomato masala, simmer chicken in gravy. Dietary type: non-vegetarian.",
        "cuisine": "North Indian",
        "dietary_type": "non-vegetarian",
        "tags": ["chicken", "curry", "comfort"]
    },
    {
        "name": "Egg Bhurji",
        "content": "Main ingredients: eggs, onion, tomato, green chili, turmeric, coriander. Cooking time: 15 minutes. Method: scramble eggs with sautéed onion and spices. Dietary type: non-vegetarian.",
        "cuisine": "North Indian",
        "dietary_type": "non-vegetarian",
        "tags": ["breakfast", "quick", "protein"]
    },
    {
        "name": "Fish Curry",
        "content": "Main ingredients: fish fillets, tamarind, coconut, tomato, mustard seeds, curry leaves. Cooking time: 35 minutes. Method: temper mustard and curry leaves, simmer fish in spiced coconut-tamarind broth. Dietary type: non-vegetarian.",
        "cuisine": "South Indian",
        "dietary_type": "non-vegetarian",
        "tags": ["fish", "tamarind", "coastal"]
    },
    {
        "name": "Methi Chicken",
        "content": "Main ingredients: chicken, fenugreek leaves, onion, tomato, ginger, garlic. Cooking time: 45 minutes. Method: cook onion-tomato gravy, add chicken and fresh methi leaves, simmer until tender. Dietary type: non-vegetarian.",
        "cuisine": "North Indian",
        "dietary_type": "non-vegetarian",
        "tags": ["chicken", "greens", "savory"]
    },
    {
        "name": "Egg Curry with Coconut",
        "content": "Main ingredients: boiled eggs, coconut, onion, tomato, garam masala. Cooking time: 30 minutes. Method: make coconut masala, add boiled eggs, simmer gently. Dietary type: non-vegetarian.",
        "cuisine": "South Indian",
        "dietary_type": "non-vegetarian",
        "tags": ["egg", "coconut", "rich"]
    },
    {
        "name": "Chicken Saag",
        "content": "Main ingredients: chicken, spinach, onion, tomato, ginger, garlic. Cooking time: 45 minutes. Method: cook spinach puree with spices, add chicken and simmer until done. Dietary type: non-vegetarian.",
        "cuisine": "North Indian",
        "dietary_type": "non-vegetarian",
        "tags": ["chicken", "spinach", "healthy"]
    },
    {
        "name": "Keema Matar",
        "content": "Main ingredients: minced lamb, green peas, onion, tomato, ginger, garam masala. Cooking time: 40 minutes. Method: sauté onion and spices, add keema and peas, cook until tender. Dietary type: non-vegetarian.",
        "cuisine": "North Indian",
        "dietary_type": "non-vegetarian",
        "tags": ["lamb", "peas", "spiced"]
    },
    {
        "name": "Poha",
        "content": "Main ingredients: flattened rice, onion, mustard seeds, curry leaves, peanuts. Cooking time: 20 minutes. Method: rinse poha, temper mustard seeds and curry leaves, mix everything and cook briefly. Dietary type: vegetarian.",
        "cuisine": "North Indian",
        "dietary_type": "vegetarian",
        "tags": ["breakfast", "light", "quick"]
    },
    {
        "name": "Upma",
        "content": "Main ingredients: semolina, mustard seeds, curry leaves, vegetables, peanuts. Cooking time: 20 minutes. Method: roast semolina, sauté vegetables and spices, add water and cook until fluffy. Dietary type: vegetarian.",
        "cuisine": "South Indian",
        "dietary_type": "vegetarian",
        "tags": ["breakfast", "comfort", "savory"]
    },
    {
        "name": "Idli with Sambar",
        "content": "Main ingredients: rice, urad dal, lentils, tamarind, vegetables. Cooking time: 60 minutes including fermentation. Method: ferment batter, steam idlis, prepare sambar with lentils and vegetables. Dietary type: vegetarian.",
        "cuisine": "South Indian",
        "dietary_type": "vegetarian",
        "tags": ["breakfast", "soft", "traditional"]
    },
    {
        "name": "Aloo Paratha",
        "content": "Main ingredients: whole wheat flour, potato, spices, cilantro, butter. Cooking time: 30 minutes. Method: make dough, stuff with spiced potato filling, roll and cook on a griddle. Dietary type: vegetarian.",
        "cuisine": "North Indian",
        "dietary_type": "vegetarian",
        "tags": ["breakfast", "flatbread", "comfort"]
    },
    {
        "name": "Masala Dosa",
        "content": "Main ingredients: rice, urad dal, potato, onion, mustard seeds, curry leaves. Cooking time: 60 minutes including fermentation. Method: prepare dosa batter, make spiced potato filling, spread dosa and fold with stuffing. Dietary type: vegetarian.",
        "cuisine": "South Indian",
        "dietary_type": "vegetarian",
        "tags": ["breakfast", "crispy", "dosa"]
    },
    {
        "name": "Rava Dosa",
        "content": "Main ingredients: semolina, rice flour, yogurt, cumin, green chilies. Cooking time: 30 minutes. Method: whisk batter thin, spread on hot griddle for crispy dosa. Dietary type: vegetarian.",
        "cuisine": "South Indian",
        "dietary_type": "vegetarian",
        "tags": ["breakfast", "crispy", "quick"]
    },
    {
        "name": "Khichdi",
        "content": "Main ingredients: rice, moong dal, vegetables, turmeric. Cooking time: 30 minutes. Method: sauté vegetables and spices, add rice and dal, cook until soft and porridge-like. Dietary type: vegetarian.",
        "cuisine": "Indian",
        "dietary_type": "vegetarian",
        "tags": ["healthy", "comfort", "one-pot"]
    },
    {
        "name": "Daliya Pongal",
        "content": "Main ingredients: broken wheat, moong dal, black pepper, ginger, curry leaves. Cooking time: 30 minutes. Method: roast daliya, cook with dal and water until creamy, temper spices on top. Dietary type: vegetarian.",
        "cuisine": "South Indian",
        "dietary_type": "vegetarian",
        "tags": ["healthy", "breakfast", "porridge"]
    },
    {
        "name": "Sprouts Salad",
        "content": "Main ingredients: moong sprouts, tomato, cucumber, onion, lemon, chaat masala. Cooking time: 15 minutes. Method: combine sprouts and chopped vegetables, toss with lemon and spices. Dietary type: vegetarian.",
        "cuisine": "Indian",
        "dietary_type": "vegetarian",
        "tags": ["healthy", "salad", "raw"]
    },
    {
        "name": "Vegetable Khichdi",
        "content": "Main ingredients: rice, moong dal, mixed vegetables, cumin, turmeric. Cooking time: 35 minutes. Method: sauté vegetables, add rice and dal, cook together until soft. Dietary type: vegetarian.",
        "cuisine": "Indian",
        "dietary_type": "vegetarian",
        "tags": ["healthy", "comfort", "easy"]
    },
    {
        "name": "Rasam",
        "content": "Main ingredients: tamarind, tomato, dal, pepper, cumin, curry leaves. Cooking time: 25 minutes. Method: cook tamarind with tomatoes and spices, strain and finish with tempering. Dietary type: vegetarian.",
        "cuisine": "South Indian",
        "dietary_type": "vegetarian",
        "tags": ["soupy", "comfort", "digestive"]
    },
    {
        "name": "Sambar",
        "content": "Main ingredients: toor dal, vegetables, tamarind, sambar powder, curry leaves. Cooking time: 40 minutes. Method: cook dal, prepare vegetable and tamarind broth, add spices and simmer. Dietary type: vegetarian.",
        "cuisine": "South Indian",
        "dietary_type": "vegetarian",
        "tags": ["lentils", "vegetables", "traditional"]
    },
    {
        "name": "Coconut Chutney",
        "content": "Main ingredients: fresh coconut, green chilies, ginger, tamarind, roasted chana dal. Cooking time: 10 minutes. Method: blend ingredients with water and season. Dietary type: vegetarian.",
        "cuisine": "South Indian",
        "dietary_type": "vegetarian",
        "tags": ["side", "dip", "condiment"]
    },
    {
        "name": "Methi Thepla",
        "content": "Main ingredients: whole wheat flour, fenugreek leaves, yogurt, spices. Cooking time: 30 minutes. Method: knead dough with fenugreek and spices, roll thin and cook on griddle. Dietary type: vegetarian.",
        "cuisine": "North Indian",
        "dietary_type": "vegetarian",
        "tags": ["flatbread", "healthy", "travel-friendly"]
    },
    {
        "name": "Chana Dal Palak",
        "content": "Main ingredients: chana dal, spinach, onion, tomato, ginger, garlic. Cooking time: 40 minutes. Method: cook dal, add chopped spinach and spices, simmer until greens wilt. Dietary type: vegetarian.",
        "cuisine": "North Indian",
        "dietary_type": "vegetarian",
        "tags": ["protein", "greens", "hearty"]
    },
    {
        "name": "Keerai Masiyal",
        "content": "Main ingredients: leafy greens, lentils, tamarind, mustard seeds, garlic. Cooking time: 25 minutes. Method: cook greens with lentils and spices, mash to a textured curry. Dietary type: vegetarian.",
        "cuisine": "South Indian",
        "dietary_type": "vegetarian",
        "tags": ["greens", "side", "low-carb"]
    },
    {
        "name": "Egg Dosa",
        "content": "Main ingredients: dosa batter, eggs, green chili, onion. Cooking time: 20 minutes. Method: spread dosa batter, crack egg on top, cook until done. Dietary type: non-vegetarian.",
        "cuisine": "South Indian",
        "dietary_type": "non-vegetarian",
        "tags": ["breakfast", "egg", "crispy"]
    },
    {
        "name": "Prawn Curry",
        "content": "Main ingredients: prawns, coconut milk, tomato, tamarind, curry leaves. Cooking time: 35 minutes. Method: sauté prawns, cook coconut-tamarind gravy, add prawns and simmer briefly. Dietary type: non-vegetarian.",
        "cuisine": "South Indian",
        "dietary_type": "non-vegetarian",
        "tags": ["seafood", "spicy", "coastal"]
    },
]


def get_embedding(text: str) -> list[float]:
    if not text:
        return []

    try:
        response = openai_client.embeddings.create(
            model="openai/text-embedding-3-small",
            input=text,
        )
        embedding = response.data[0].embedding
        return embedding
    except Exception as exc:
        print(f"⚠️ Error generating embedding: {exc}")
        return []


def ingest_recipes():
    print("📥 Starting recipe ingestion into Supabase recipes table...")

    for index, recipe in enumerate(RECIPES, start=1):
        print(f"⏳ ({index}/{len(RECIPES)}) Generating embedding for {recipe['name']}...")
        embedding = get_embedding(recipe["content"])
        payload = {
            "name": recipe["name"],
            "content": recipe["content"],
            "cuisine": recipe["cuisine"],
            "dietary_type": recipe["dietary_type"],
            "tags": recipe["tags"],
            "embedding": embedding,
        }

        try:
            supabase.table("recipes").insert(payload).execute()
            print(f"✅ Stored recipe: {recipe['name']}")
        except Exception as exc:
            print(f"❌ Failed to store {recipe['name']}: {exc}")

    print(f"\n🎉 Recipe ingestion completed: {len(RECIPES)} recipes attempted.")


if __name__ == "__main__":
    ingest_recipes()
