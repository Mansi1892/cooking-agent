// Smart Meal AI API client
// Backend at http://localhost:8000

const BASE_URL = (typeof window !== "undefined" && (window as any).__MPA_API__) || "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });
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

export type FamilyMember = {
  name: string;
  age?: number;
  diet?: string;
  allergies?: string[];
  preferences?: string[];
};

export type OnboardPayload = {
  name: string;
  age: number;
  weight: number;
  height: number;
  goal: "weight_loss" | "muscle_gain" | "maintenance";
  weekly_budget: number;
  telegram?: string;
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
    meals: Array<{
      type: string;
      name: string;
      calories: number;
      protein: number;
      prep_time?: number;
    }>;
  }>;
};

export type HistoryItem = {
  plan_id: string;
  created_at: string;
  status: string;
  goal: string;
  avg_calories: number;
  avg_protein: number;
};

export type GroceryGroup = {
  category: string;
  items: Array<{ name: string; quantity: string; checked?: boolean }>;
};

export const api = {
  health: () => request<{ status: string }>("/health"),
  onboard: (data: OnboardPayload) => request<{ user_id: string }>("/onboard", { method: "POST", body: JSON.stringify(data) }),
  generatePlan: (userId: string) => request<MealPlan>(`/plan/generate/${userId}`, { method: "POST" }),
  getPlan: (planId: string) => request<MealPlan>(`/plan/${planId}`),
  getHistory: (userId: string) => request<HistoryItem[]>(`/history/${userId}`),
  getGrocery: (planId: string) => request<GroceryGroup[]>(`/grocery/${planId}`),
  feedback: (payload: any) => request<{ ok: boolean }>("/feedback", { method: "POST", body: JSON.stringify(payload) }),
};

// Mock data used when API is unreachable so the UI is always portfolio-worthy
export const mock = {
  plan: (): MealPlan => ({
    id: "mock-plan-1",
    user_id: "mock-user",
    status: "ready",
    created_at: new Date().toISOString(),
    week_summary: { healthy_score: 92, avg_calories: 2050, avg_protein: 138, total_budget: 84 },
    days: ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"].map((day, i) => ({
      day,
      calories: 1900 + ((i * 73) % 350),
      protein: 120 + ((i * 11) % 35),
      status: i < 2 ? "completed" : "planned",
      meals: [
        { type: "Breakfast", name: "Greek yogurt parfait, berries, granola", calories: 380, protein: 24, prep_time: 5 },
        { type: "Lunch", name: "Grilled chicken bowl, quinoa, avocado", calories: 620, protein: 48, prep_time: 20 },
        { type: "Dinner", name: "Pan-seared salmon, roasted veg", calories: 720, protein: 52, prep_time: 25 },
        { type: "Snack", name: "Almonds & apple", calories: 230, protein: 8, prep_time: 1 },
      ],
    })),
  }),
  history: (): HistoryItem[] => Array.from({ length: 6 }).map((_, i) => ({
    plan_id: `plan-${i+1}`,
    created_at: new Date(Date.now() - i * 7 * 86400000).toISOString(),
    status: i === 0 ? "active" : "approved",
    goal: ["weight_loss","muscle_gain","maintenance"][i % 3],
    avg_calories: 1900 + (i * 35),
    avg_protein: 125 + (i * 4),
  })),
  grocery: (): GroceryGroup[] => [
    { category: "Vegetables", items: [
      { name: "Spinach", quantity: "300g" }, { name: "Broccoli", quantity: "2 heads" },
      { name: "Avocado", quantity: "4" }, { name: "Bell peppers", quantity: "5" }] },
    { category: "Proteins", items: [
      { name: "Chicken breast", quantity: "1.2 kg" }, { name: "Salmon fillet", quantity: "600g" },
      { name: "Eggs", quantity: "1 dozen" }, { name: "Greek yogurt", quantity: "1 kg" }] },
    { category: "Grains", items: [
      { name: "Quinoa", quantity: "500g" }, { name: "Rolled oats", quantity: "800g" }] },
    { category: "Fruits", items: [
      { name: "Berries mix", quantity: "500g" }, { name: "Apples", quantity: "8" }, { name: "Bananas", quantity: "10" }] },
    { category: "Dairy", items: [
      { name: "Almond milk", quantity: "2 L" }, { name: "Feta cheese", quantity: "200g" }] },
    { category: "Spices", items: [
      { name: "Black pepper", quantity: "1 jar" }, { name: "Smoked paprika", quantity: "1 jar" }] },
  ],
};

export async function safe<T>(p: Promise<T>, fallback: T): Promise<T> {
  try { return await p; } catch { return fallback; }
}
