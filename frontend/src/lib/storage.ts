// LocalStorage helpers for Smart Meal AI

const KEYS = {
  userId: "mpa_user_id",
  userName: "mpa_user_name",
  userGoal: "mpa_user_goal",
  telegram: "mpa_telegram_id",
  authUser: "mpa_auth_user",
  streak: "mpa_streak",
  profile: "mpa_profile",
  lastPlanId: "mpa_last_plan_id",
  credits: "mpa_credits",
  role: "mpa_role",
} as const;

function read(key: string): string | null {
  if (typeof window === "undefined") return null;
  try { return window.localStorage.getItem(key); } catch { return null; }
}
function write(key: string, value: string | null) {
  if (typeof window === "undefined") return;
  try {
    const previous = window.localStorage.getItem(key);
    if (previous === value) return;
    if (value == null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, value);
    window.dispatchEvent(new CustomEvent("mpa-storage-change", { detail: { key, value } }));
  } catch {}
}

function clearAdminSession() {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem("mpa_admin_user_id");
    window.localStorage.removeItem("mpa_admin_password");
    window.localStorage.removeItem("mpa_admin_ok");
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
  getAuthUser: <T = any>(): T | null => {
    const raw = read(KEYS.authUser);
    if (!raw) return null;
    try { return JSON.parse(raw); } catch { return null; }
  },
  setAuthUser: (data: any) => write(KEYS.authUser, JSON.stringify(data)),
  isLoggedIn: () => !!read(KEYS.authUser),
  logout: () => {
    Object.values(KEYS).forEach((k) => write(k, null));
    clearAdminSession();
  },
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
  getCredits: () => {
    const value = read(KEYS.credits);
    return value == null ? 3 : Number(value || "0");
  },
  setCredits: (n: number) => write(KEYS.credits, String(n)),
  getRole: () => read(KEYS.role) || "user",
  setRole: (v: string) => write(KEYS.role, v),
  resetProfile: () => {
    [
      KEYS.userId,
      KEYS.userName,
      KEYS.userGoal,
      KEYS.telegram,
      KEYS.streak,
      KEYS.profile,
      KEYS.lastPlanId,
      KEYS.credits,
      KEYS.role,
    ].forEach((k) => write(k, null));
  },
  clearAll: () => {
    Object.values(KEYS).forEach((k) => write(k, null));
    clearAdminSession();
  },
};
