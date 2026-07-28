// LocalStorage helpers for Smart Meal AI

const KEYS = {
  appVersion: "mpa_app_version",
  userId: "mpa_user_id",
  userName: "mpa_user_name",
  userGoal: "mpa_user_goal",
  telegram: "mpa_telegram_id",
  whatsapp: "mpa_whatsapp_number",
  authUser: "mpa_auth_user",
  streak: "mpa_streak",
  profile: "mpa_profile",
  lastPlanId: "mpa_last_plan_id",
  credits: "mpa_credits",
  role: "mpa_role",
  resetOnboardingUserId: "mpa_reset_onboarding_user_id",
} as const;

const APP_STORAGE_VERSION = "2026-07-27-clean-profile-forms-v1";

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
  ensureFreshVersion: () => {
    const current = read(KEYS.appVersion);
    if (current === APP_STORAGE_VERSION) return false;
    Object.values(KEYS).forEach((k) => {
      if (k !== KEYS.appVersion) write(k, null);
    });
    clearAdminSession();
    write(KEYS.appVersion, APP_STORAGE_VERSION);
    return true;
  },
  getUserId: () => read(KEYS.userId),
  setUserId: (v: string) => write(KEYS.userId, v),
  getUserName: () => read(KEYS.userName),
  setUserName: (v: string) => write(KEYS.userName, v),
  getGoal: () => read(KEYS.userGoal),
  setGoal: (v: string) => write(KEYS.userGoal, v),
  getTelegram: () => read(KEYS.telegram),
  setTelegram: (v: string) => write(KEYS.telegram, v),
  getWhatsapp: () => read(KEYS.whatsapp),
  setWhatsapp: (v: string) => write(KEYS.whatsapp, v),
  getAuthUser: <T = any>(): T | null => {
    const raw = read(KEYS.authUser);
    if (!raw) return null;
    try { return JSON.parse(raw); } catch { return null; }
  },
  setAuthUser: (data: any) => write(KEYS.authUser, JSON.stringify(data)),
  isLoggedIn: () => !!read(KEYS.authUser),
  logout: () => {
    Object.values(KEYS).forEach((k) => write(k, null));
    write(KEYS.appVersion, APP_STORAGE_VERSION);
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
  getResetOnboardingUserId: () => read(KEYS.resetOnboardingUserId),
  setResetOnboardingUserId: (v: string) => write(KEYS.resetOnboardingUserId, v),
  clearResetOnboardingUserId: () => write(KEYS.resetOnboardingUserId, null),
  resetProfile: () => {
    const existingUserId = read(KEYS.userId);
    if (existingUserId) write(KEYS.resetOnboardingUserId, existingUserId);
    [
      KEYS.userId,
      KEYS.userName,
      KEYS.userGoal,
      KEYS.telegram,
      KEYS.whatsapp,
      KEYS.streak,
      KEYS.profile,
      KEYS.lastPlanId,
    ].forEach((k) => write(k, null));
  },
  clearAll: () => {
    Object.values(KEYS).forEach((k) => write(k, null));
    write(KEYS.appVersion, APP_STORAGE_VERSION);
    clearAdminSession();
  },
};
