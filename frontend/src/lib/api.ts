// Smart Meal AI API client
// Frontend and backend are served through the same Vite dev server via /api proxy.

const BASE_URL =
  (typeof window !== "undefined" && (window as any).__MPA_API__) ||
  import.meta.env.VITE_API_URL ||
  "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = buildApiUrl(path, BASE_URL);
  let res: Response;
  try {
    res = await fetch(url, requestInit(init));
  } catch (error) {
    const sameOriginUrl = buildApiUrl(path, "/api");
    if (sameOriginUrl !== url) {
      try {
        res = await fetch(sameOriginUrl, requestInit(init));
      } catch {
        throw normalizeNetworkError(error);
      }
    } else {
      throw normalizeNetworkError(error);
    }
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      detail = (j as any).detail || (j as any).message || detail;
    } catch {}
    throw new Error(detail || `Request failed (${res.status})`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

function requestInit(init?: RequestInit): RequestInit {
  return {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  };
}

function buildApiUrl(path: string, baseUrl: string) {
  const base = baseUrl.replace(/\/$/, "");
  const suffix = path.startsWith("/") ? path : `/${path}`;
  if (/^https?:\/\//i.test(base)) return `${base}${suffix}`;
  if (typeof window === "undefined") return `${base}${suffix}`;
  return new URL(`${base}${suffix}`, window.location.origin).toString();
}

function normalizeNetworkError(error: unknown) {
  const raw = error instanceof Error ? error.message : String(error || "");
  if (/load failed|failed to fetch|networkerror|fetch failed/i.test(raw)) {
    return new Error("Network request failed. Please refresh the app and try again on the Vercel link.");
  }
  return error instanceof Error ? error : new Error(raw || "Network request failed.");
}

export type FamilyMember = {
  id?: string | number;
  name: string;
  age?: number;
  goal?: "weight_loss" | "muscle_gain" | "maintenance";
  gender?: string;
  weight?: number;
  height?: number;
  weight_kg?: number;
  height_cm?: number;
  diet?: string;
  allergies?: string[];
  preferences?: string[];
  telegram?: string;
  whatsapp?: string;
  whatsapp_number?: string;
};

export type OnboardPayload = {
  name: string;
  email?: string;
  password?: string;
  age: number;
  gender?: string;
  weight: number;
  height: number;
  goal: "weight_loss" | "muscle_gain" | "maintenance";
  weekly_budget: number;
  telegram?: string;
  whatsapp?: string;
  whatsapp_number?: string;
  dietary_preference?: string;
  allergies?: string[];
  preferences?: string[];
  family?: FamilyMember[];
};

export type MealPlan = {
  id: string;
  user_id: string;
  status: string;
  created_at?: string;
  week_summary?: {
    healthy_score: number;
    avg_calories: number;
    avg_protein: number;
    total_budget: number;
  };
  days?: Array<{
    day: string;
    calories: number;
    protein: number;
    status?: string;
    portion_note?: string;
    meals: Array<{
      type: string;
      name: string;
      calories: number;
      protein: number;
      prep_time?: number;
    }>;
  }>;
  people_plans?: Array<{
    person_id: string;
    name: string;
    goal: string;
    gender?: string;
    dietary_type?: string;
    target_calories: number;
    target_protein: number;
    days: MealPlan["days"];
  }>;
};

export type UserProfile = OnboardPayload & {
  id: string;
  role?: "user" | "admin" | string;
  credits?: number;
  budget_weekly?: number;
  telegram_id?: string;
  whatsapp_number?: string;
  dietary_type?: string;
  created_at?: string;
};

export type CreditRequest = {
  id: number;
  user_id: string;
  requested_credits: number;
  status: string;
  note?: string;
  created_at?: string;
  users?: {
    id: string;
    name: string;
    email?: string;
    credits?: number;
    role?: string;
  };
};

export type SupportTicket = {
  id: number;
  user_id: string;
  category: string;
  title: string;
  description: string;
  page_url?: string;
  severity: string;
  status: string;
  created_at?: string;
  resolved_at?: string;
  users?: {
    id: string;
    name: string;
    email?: string;
    role?: string;
  };
};

export type HistoryItem = {
  plan_id: string;
  created_at: string;
  week_start?: string;
  status: string;
  goal: string;
  avg_calories: number;
  avg_protein: number;
  version_count?: number;
};

export type GroceryGroup = {
  category: string;
  items: Array<{ name: string; quantity: string; checked?: boolean }>;
};

export type Recipe = {
  title: string;
  servings: number;
  prep_time?: string;
  cook_time?: string;
  ingredients: string[];
  steps: string[];
  nutrition_note?: string;
  source_urls?: string[];
};

export const api = {
  health: () => request<{ status: string }>("/health"),
  signupCheck: (payload: { email: string; password: string; name?: string }) => request<{ ok: boolean }>("/auth/signup-check", { method: "POST", body: JSON.stringify(payload) }),
  onboard: (data: OnboardPayload) => request<{ user_id: string; credits?: number; role?: string }>("/onboard", { method: "POST", body: JSON.stringify(data) }),
  getProfile: (userId: string) => request<{ profile: UserProfile }>(`/profile/${userId}`),
  getProfileByEmail: (email: string) => request<{ profile: UserProfile }>(`/profile/by-email/${encodeURIComponent(email)}`),
  updateProfile: (userId: string, data: OnboardPayload) => request<{ profile: any }>(`/profile/${userId}`, { method: "PUT", body: JSON.stringify(data) }),
  generatePlan: (userId: string, payload?: { week_offset?: number; week_start?: string }) => request<MealPlan | { plan: MealPlan; telegram_sent?: boolean; telegram_queued?: boolean; whatsapp_queued?: boolean; whatsapp_sent?: boolean; telegram_error?: string; auto_approved?: boolean; credits_remaining?: number; credits_unlimited?: boolean }>(`/plan/generate/${userId}`, { method: "POST", body: JSON.stringify(payload || { week_offset: 0 }) }),
  getLatestPlan: (userId: string) => request<{ plan: MealPlan }>(`/plan/latest/${userId}`),
  getStreak: (userId: string) => request<{ streak: number }>(`/streak/${userId}`),
  adminLogin: (payload: { admin_user_id: string; admin_password: string }) => request<{ admin: { id: string; name: string; role: string } }>("/admin/login", { method: "POST", body: JSON.stringify(payload) }),
  requestCredits: (payload: { user_id: string; requested_credits?: number; note?: string }) => request<{ request: CreditRequest }>("/credit-requests", { method: "POST", body: JSON.stringify(payload) }),
  getCreditRequests: (adminUserId: string, adminPassword: string) => request<{ requests: CreditRequest[] }>(`/admin/credit-requests?admin_user_id=${encodeURIComponent(adminUserId)}&admin_password=${encodeURIComponent(adminPassword)}`),
  grantCreditRequest: (payload: { admin_user_id: string; admin_password: string; request_id: number; amount: number }) => request<{ profile: UserProfile; credits: number }>("/admin/credit-requests/grant", { method: "POST", body: JSON.stringify(payload) }),
  createSupportTicket: (payload: { user_id: string; category: string; title: string; description: string; page_url?: string; severity?: string }) => request<{ ticket: SupportTicket }>("/support/tickets", { method: "POST", body: JSON.stringify(payload) }),
  getSupportTickets: (adminUserId: string, adminPassword: string, status = "open") => request<{ tickets: SupportTicket[] }>(`/admin/support-tickets?admin_user_id=${encodeURIComponent(adminUserId)}&admin_password=${encodeURIComponent(adminPassword)}&status=${encodeURIComponent(status)}`),
  updateSupportTicketStatus: (payload: { admin_user_id: string; admin_password: string; ticket_id: number; status: string }) => request<{ ticket: SupportTicket }>("/admin/support-tickets/status", { method: "POST", body: JSON.stringify(payload) }),
  generateRecipe: (payload: { user_id: string; meal_name: string; meal_type?: string }) => request<{ recipe: Recipe }>("/recipe/generate", { method: "POST", body: JSON.stringify(payload) }),
  regeneratePersonDay: (payload: { user_id: string; plan_id: string; person_id: string; day: string; feedback: string }) => request<{ plan: MealPlan; override: any }>("/plan/regenerate-person-day", { method: "POST", body: JSON.stringify(payload) }),
  getTelegramBotLink: () => request<{ url: string }>("/telegram/bot-link"),
  testTelegram: (userId: string) => request<{ sent: boolean }>(`/telegram/test/${userId}`, { method: "POST" }),
  testWhatsapp: (userId: string) => request<{ sent: boolean }>(`/whatsapp/test/${userId}`, { method: "POST" }),
  testTelegramContact: (value: string) => request<{ sent: boolean }>("/telegram/test-contact", { method: "POST", body: JSON.stringify({ value }) }),
  testWhatsappContact: (value: string) => request<{ sent: boolean }>("/whatsapp/test-contact", { method: "POST", body: JSON.stringify({ value }) }),
  getPlan: (planId: string) => request<MealPlan>(`/plan/${planId}`),
  getHistory: async (userId: string) => {
    const response = await request<HistoryItem[] | { history: HistoryItem[] }>(`/history/${userId}`);
    return Array.isArray(response) ? response : response.history || [];
  },
  clearHistory: (userId: string) => request<{ deleted_plans: number }>(`/history/${userId}`, { method: "DELETE" }),
  getGrocery: async (planId: string) => {
    const response = await request<GroceryGroup[] | { grocery: GroceryGroup[] }>(`/grocery/${planId}`);
    return Array.isArray(response) ? response : response.grocery || [];
  },
  feedback: (payload: any) => request<{ ok: boolean }>("/feedback", { method: "POST", body: JSON.stringify(payload) }),
};

function normalizeDiet(profile?: Partial<OnboardPayload> | null) {
  const raw = String(profile?.dietary_preference || "").toLowerCase();
  if (raw.includes("normal") || raw.includes("regular") || raw.includes("no preference")) return "normal";
  if (raw.includes("vegan")) return "vegan";
  if (raw.includes("non")) return "non-vegetarian";
  if (raw.includes("pesc")) return "pescatarian";
  if (raw.includes("keto")) return "keto";
  if (raw.includes("eggetarian") || raw.includes("eggitarian") || raw.includes("ovo")) return "eggetarian";
  if (raw.includes("vegetarian") || raw === "veg") return "vegetarian";
  return "normal";
}

function demoMeals(profile?: Partial<OnboardPayload> | null) {
  const diet = normalizeDiet(profile);
  if (diet === "vegan") {
    return [
      { type: "Breakfast", name: "Besan cheela, mint chutney, sprouts", calories: 360, protein: 22, prep_time: 15 },
      { type: "Lunch", name: "Chole bowl, brown rice, cucumber salad", calories: 620, protein: 26, prep_time: 25 },
      { type: "Dinner", name: "Tofu tikka, roasted vegetables, dal soup", calories: 690, protein: 38, prep_time: 25 },
      { type: "Snack", name: "Almonds & apple", calories: 230, protein: 8, prep_time: 1 },
    ];
  }
  if (diet === "pescatarian") {
    return [
      { type: "Breakfast", name: "Idli, sambar, coconut chutney", calories: 380, protein: 18, prep_time: 15 },
      { type: "Lunch", name: "Fish curry, brown rice, cucumber salad", calories: 650, protein: 42, prep_time: 25 },
      { type: "Dinner", name: "Paneer tikka, roasted vegetables, dal soup", calories: 700, protein: 40, prep_time: 25 },
      { type: "Snack", name: "Greek yogurt & berries", calories: 220, protein: 18, prep_time: 2 },
    ];
  }
  if (diet === "eggetarian") {
    return [
      { type: "Breakfast", name: "Egg bhurji, spinach, whole wheat toast", calories: 390, protein: 26, prep_time: 12 },
      { type: "Lunch", name: "Rajma bowl, brown rice, cucumber salad", calories: 620, protein: 30, prep_time: 25 },
      { type: "Dinner", name: "Paneer tikka, roasted vegetables, dal soup", calories: 720, protein: 42, prep_time: 25 },
      { type: "Snack", name: "Boiled eggs & fruit", calories: 220, protein: 16, prep_time: 8 },
    ];
  }
  if (diet === "keto") {
    return [
      { type: "Breakfast", name: "Paneer bhurji, sauteed spinach", calories: 430, protein: 32, prep_time: 15 },
      { type: "Lunch", name: "Chicken tikka salad, avocado, cucumber", calories: 650, protein: 52, prep_time: 20 },
      { type: "Dinner", name: "Palak paneer, cauliflower rice", calories: 700, protein: 44, prep_time: 25 },
      { type: "Snack", name: "Walnuts & cheese cubes", calories: 260, protein: 12, prep_time: 1 },
    ];
  }
  if (diet === "non-vegetarian") {
    return [
      { type: "Breakfast", name: "Egg bhurji, vegetable saute", calories: 400, protein: 28, prep_time: 12 },
      { type: "Lunch", name: "Grilled chicken bowl, quinoa, avocado", calories: 650, protein: 52, prep_time: 20 },
      { type: "Dinner", name: "Fish curry, roasted vegetables", calories: 700, protein: 48, prep_time: 25 },
      { type: "Snack", name: "Greek yogurt & berries", calories: 220, protein: 18, prep_time: 2 },
    ];
  }
  if (diet === "normal") {
    return [
      { type: "Breakfast", name: "Vegetable omelette, toast, fruit", calories: 420, protein: 28, prep_time: 12 },
      { type: "Lunch", name: "Chicken dal bowl, rice, cucumber salad", calories: 660, protein: 48, prep_time: 25 },
      { type: "Dinner", name: "Paneer tikka, mixed vegetables, roti", calories: 690, protein: 38, prep_time: 25 },
      { type: "Snack", name: "Greek yogurt & berries", calories: 220, protein: 18, prep_time: 2 },
    ];
  }
  return [
    { type: "Breakfast", name: "Moong dal cheela, mint chutney, curd", calories: 380, protein: 24, prep_time: 15 },
    { type: "Lunch", name: "Rajma bowl, brown rice, cucumber salad", calories: 620, protein: 30, prep_time: 25 },
    { type: "Dinner", name: "Paneer tikka, roasted vegetables, dal soup", calories: 720, protein: 42, prep_time: 25 },
    { type: "Snack", name: "Almonds & apple", calories: 230, protein: 8, prep_time: 1 },
  ];
}

function demoMealsForDay(profile: Partial<OnboardPayload> | null | undefined, dayIndex: number) {
  const diet = normalizeDiet(profile);
  const vegetarianWeek = [
    ["Moong dal cheela, mint chutney, curd", "Rajma bowl, brown rice, cucumber salad", "Paneer tikka, roasted vegetables, dal soup", "Almonds & apple"],
    ["Vegetable poha with peanuts", "Chole, jeera rice, kachumber salad", "Palak paneer, phulka, carrot salad", "Greek yogurt & berries"],
    ["Idli, sambar, coconut chutney", "Masoor dal, millet roti, bhindi", "Tofu matar curry, quinoa pulao", "Roasted makhana"],
    ["Oats upma with vegetables", "Kadhi, brown rice, cucumber raita", "Soya chunk curry, chapati, salad", "Fruit chaat"],
    ["Paneer bhurji toast", "Dal tadka, rice, cabbage sabzi", "Vegetable khichdi, curd, pickle", "Peanut chaat"],
    ["Besan dhokla, coriander chutney", "Matar paneer, phulka, salad", "Mixed dal dosa, sambar", "Buttermilk & walnuts"],
    ["Sprouts chilla, tomato chutney", "Vegetable biryani, raita, salad", "Lauki kofta, chapati, dal soup", "Banana & peanut butter"],
  ];
  const veganWeek = [
    ["Besan cheela, mint chutney, sprouts", "Chole bowl, brown rice, cucumber salad", "Tofu tikka, roasted vegetables, dal soup", "Almonds & apple"],
    ["Vegetable poha with peanuts", "Rajma, millet rice, salad", "Soy chunk curry, phulka, greens", "Roasted chana"],
    ["Ragi dosa, sambar", "Masoor dal, quinoa, bhindi", "Tofu palak, cauliflower sabzi", "Fruit & peanut chaat"],
    ["Oats upma with vegetables", "Kala chana bowl, brown rice", "Mixed veg curry, dal soup", "Coconut yogurt"],
    ["Sprouts salad toast", "Moong dal khichdi, salad", "Tofu bhurji, millet roti", "Makhana"],
    ["Dhokla, green chutney", "Chickpea pulao, cucumber salad", "Sambar, idli, stir-fried beans", "Nuts & dates"],
    ["Besan oats pancakes", "Lobia curry, rice, salad", "Vegetable stew, appam", "Apple & almonds"],
  ];
  const eggetarianWeek = [
    ["Egg bhurji, spinach, whole wheat toast", "Rajma bowl, brown rice, cucumber salad", "Paneer tikka, roasted vegetables, dal soup", "Boiled eggs & fruit"],
    ["Masala omelette, toast", "Chole, rice, salad", "Palak paneer, phulka", "Greek yogurt"],
    ["Idli, sambar", "Egg curry, brown rice, salad", "Tofu stir fry, quinoa", "Roasted makhana"],
    ["Oats veggie omelette", "Dal tadka, chapati, sabzi", "Paneer bhurji, salad", "Boiled egg chaat"],
    ["Egg dosa, chutney", "Kadhi rice, cucumber salad", "Soya curry, millet roti", "Fruit bowl"],
    ["Scrambled eggs, sauteed vegetables", "Matar paneer, phulka", "Vegetable khichdi, curd", "Nuts & apple"],
    ["Egg paratha, curd", "Chana masala, rice", "Palak tofu, chapati", "Protein smoothie"],
  ];
  const nonVegWeek = [
    ["Egg bhurji, vegetable saute", "Grilled chicken bowl, quinoa, avocado", "Fish curry, roasted vegetables", "Greek yogurt & berries"],
    ["Omelette, toast, fruit", "Chicken tikka wrap, salad", "Dal, rice, grilled prawns", "Boiled eggs"],
    ["Idli, sambar", "Fish curry, brown rice, salad", "Chicken saag, phulka", "Peanut chaat"],
    ["Oats upma", "Chicken dal bowl, cucumber salad", "Paneer tikka, vegetables", "Yogurt & nuts"],
    ["Masala eggs, spinach", "Mutton curry, rice, salad", "Fish tikka, dal soup", "Fruit bowl"],
    ["Dosa, egg podi", "Chicken biryani, raita", "Tofu vegetable stir fry", "Roasted chana"],
    ["Vegetable omelette", "Prawn curry, rice, salad", "Chicken soup, millet roti", "Greek yogurt"],
  ];
  const pescatarianWeek = [
    ["Idli, sambar, coconut chutney", "Fish curry, brown rice, cucumber salad", "Paneer tikka, roasted vegetables, dal soup", "Greek yogurt & berries"],
    ["Poha with peanuts", "Prawn pulao, salad", "Palak paneer, phulka", "Roasted makhana"],
    ["Oats upma", "Grilled fish, quinoa, kachumber", "Dal tadka, rice, sabzi", "Fruit & nuts"],
    ["Besan cheela, curd", "Fish tikka wrap, salad", "Tofu curry, millet roti", "Yogurt"],
    ["Dosa, sambar", "Rajma rice, salad", "Prawn curry, cauliflower sabzi", "Apple & almonds"],
    ["Paneer toast", "Fish biryani, raita", "Vegetable khichdi, dal soup", "Peanut chaat"],
    ["Sprouts chilla", "Fish stew, appam", "Soya curry, chapati", "Berries & yogurt"],
  ];
  const ketoWeek = [
    ["Paneer bhurji, sauteed spinach", "Chicken tikka salad, avocado, cucumber", "Palak paneer, cauliflower rice", "Walnuts & cheese cubes"],
    ["Masala omelette, mushrooms", "Paneer tikka salad, avocado", "Fish curry, sauteed greens", "Greek yogurt"],
    ["Tofu scramble, spinach", "Chicken lettuce bowls", "Egg curry, cauliflower rice", "Almonds"],
    ["Cheese omelette", "Paneer makhani, cucumber salad", "Grilled chicken, broccoli", "Coconut yogurt"],
    ["Egg bhurji, avocado", "Fish tikka salad", "Tofu palak, sauteed beans", "Cheese cubes"],
    ["Paneer pancakes", "Chicken soup, greens", "Mushroom paneer curry", "Walnuts"],
    ["Spinach omelette", "Prawn salad, avocado", "Palak chicken, cauliflower mash", "Almond butter celery"],
  ];
  const mealsByDiet = diet === "vegan" ? veganWeek :
    diet === "eggetarian" ? eggetarianWeek :
    diet === "non-vegetarian" || diet === "normal" ? nonVegWeek :
    diet === "pescatarian" ? pescatarianWeek :
    diet === "keto" ? ketoWeek :
    vegetarianWeek;
  const names = mealsByDiet[dayIndex % mealsByDiet.length];
  const base = demoMeals(profile);
  return base.map((meal, index) => ({ ...meal, name: names[index] || meal.name }));
}

function demoGrocery(profile?: Partial<OnboardPayload> | null): GroceryGroup[] {
  const diet = normalizeDiet(profile);
  const proteins: GroceryGroup["items"] =
    diet === "vegan" ? [
      { name: "Soya chunks", quantity: "500g" }, { name: "Chickpeas", quantity: "500g" },
      { name: "Moong dal", quantity: "500g" }, { name: "Tofu", quantity: "400g" },
    ] :
    diet === "pescatarian" ? [
      { name: "Fish fillets", quantity: "500g" }, { name: "Paneer", quantity: "300g" },
      { name: "Curd", quantity: "1 kg" }, { name: "Dal assorted", quantity: "700g" },
    ] :
    diet === "keto" ? [
      { name: "Paneer", quantity: "500g" }, { name: "Eggs", quantity: "1 dozen" },
      { name: "Chicken breast", quantity: "600g" }, { name: "Peanuts", quantity: "500g" },
    ] :
    diet === "eggetarian" ? [
      { name: "Eggs", quantity: "1 dozen" }, { name: "Paneer", quantity: "400g" },
      { name: "Moong dal", quantity: "500g" }, { name: "Rajma", quantity: "500g" },
    ] :
    diet === "non-vegetarian" || diet === "normal" ? [
      { name: "Chicken breast", quantity: "700g" }, { name: "Eggs", quantity: "1 dozen" },
      { name: "Dal assorted", quantity: "700g" }, { name: "Curd", quantity: "1 kg" },
    ] : [
      { name: "Paneer", quantity: "400g" }, { name: "Soya chunks", quantity: "500g" },
      { name: "Rajma", quantity: "500g" }, { name: "Moong dal", quantity: "500g" },
    ];
  const grains = diet === "keto" ? [
    { name: "Cauliflower", quantity: "1 kg" }, { name: "Cabbage", quantity: "1 kg" },
  ] : [
    { name: "Rice", quantity: "2 kg" }, { name: "Atta", quantity: "2 kg" },
    { name: "Rolled oats", quantity: "500g" },
  ];
  const dairy = diet === "vegan" ? [
    { name: "Peanuts", quantity: "500g" }, { name: "Coconut milk", quantity: "400ml" },
  ] : [
    { name: "Milk", quantity: "2 L" }, { name: "Curd", quantity: "1 kg" },
  ];

  return [
    { category: "Vegetables", items: [
      { name: "Spinach", quantity: "300g" }, { name: "Tomatoes", quantity: "1 kg" },
      { name: "Onions", quantity: "1 kg" }, { name: "Seasonal vegetables", quantity: "2 kg" }] },
    { category: "Proteins", items: proteins },
    { category: diet === "keto" ? "Low-carb staples" : "Grains", items: grains },
    { category: "Fruits", items: [
      { name: "Apples", quantity: "6" }, { name: "Bananas", quantity: "12" }, { name: "Guava", quantity: "1 kg" }] },
    { category: diet === "vegan" ? "Dairy alternatives" : "Dairy", items: dairy },
    { category: "Spices & condiments", items: [
      { name: "Turmeric powder", quantity: "100g" },
      { name: "Cumin seeds", quantity: "100g" },
      { name: "Coriander powder", quantity: "100g" },
      { name: "Garam masala", quantity: "100g" },
      { name: "Mustard oil", quantity: "1 L" },
    ] },
  ];
}

// Mock data used when API is unreachable so the UI is always portfolio-worthy
export const mock = {
  plan: (profile?: Partial<OnboardPayload> | null): MealPlan => {
    const budget = Number(profile?.weekly_budget || 0);
    return {
      id: "mock-plan-1",
      user_id: "mock-user",
      status: "ready",
      created_at: new Date().toISOString(),
      week_summary: { healthy_score: 92, avg_calories: 2050, avg_protein: 138, total_budget: budget },
      days: ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"].map((day, i) => ({
        day,
        calories: 1900 + ((i * 73) % 350),
        protein: 120 + ((i * 11) % 35),
        status: i < 2 ? "completed" : "planned",
        meals: demoMealsForDay(profile, i),
      })),
    };
  },
  history: (): HistoryItem[] => Array.from({ length: 6 }).map((_, i) => ({
    plan_id: `plan-${i+1}`,
    created_at: new Date(Date.now() - i * 7 * 86400000).toISOString(),
    status: i === 0 ? "active" : "approved",
    goal: ["weight_loss","muscle_gain","maintenance"][i % 3],
    avg_calories: 1900 + (i * 35),
    avg_protein: 125 + (i * 4),
  })),
  grocery: (profile?: Partial<OnboardPayload> | null): GroceryGroup[] => demoGrocery(profile),
};

export async function safe<T>(p: Promise<T>, fallback: T): Promise<T> {
  try { return await p; } catch { return fallback; }
}
