// LocalStorage helpers for Smart Meal AI

const KEYS = {
  userId: "mpa_user_id",
  userName: "mpa_user_name",
  userGoal: "mpa_user_goal",
  telegram: "mpa_telegram_id",
  streak: "mpa_streak",
  profile: "mpa_profile",
  lastPlanId: "mpa_last_plan_id",
} as const;

function read(key: string): string | null {
  if (typeof window === "undefined") return null;
  try { return window.localStorage.getItem(key); } catch { return null; }
}
function write(key: string, value: string | null) {
  if (typeof window === "undefined") return;
  try {
    if (value == null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, value);
  } catch {}
}

export const storage = {
  keys: KEYS,
  getUserId: () => read(KEYS.userId),
  setUserId: (v: string) => write(KEYS.userId, v),
  getUserName: () => read(KEYS.userName),
  setUserName: (v: string) => write(KEYS.userName, v),
  getGoal: () => read(KEYS.userGoal),
  setGoal: (v: string) => write(KEYS.userGoal, v),
  getTelegram: () => read(KEYS.telegram),
  setTelegram: (v: string) => write(KEYS.telegram, v),
  getStreak: () => Number(read(KEYS.streak) || "0"),
  setStreak: (n: number) => write(KEYS.streak, String(n)),
  getProfile: <T = any>(): T | null => {
    const raw = read(KEYS.profile);
    if (!raw) return null;
    try { return JSON.parse(raw); } catch { return null; }
  },
  setProfile: (data: any) => write(KEYS.profile, JSON.stringify(data)),
  getLastPlanId: () => read(KEYS.lastPlanId),
  setLastPlanId: (v: string) => write(KEYS.lastPlanId, v),
  clearAll: () => Object.values(KEYS).forEach((k) => write(k, null)),
};
