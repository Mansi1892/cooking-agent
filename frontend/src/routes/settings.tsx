import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { LogOut, RotateCcw, ShieldCheck } from "lucide-react";
import { api } from "@/lib/api";
import { storage } from "@/lib/storage";
import { toast } from "sonner";

export const Route = createFileRoute("/settings")({
  component: Settings,
});

function Settings() {
  const navigate = useNavigate();
  const [profile, setProfile] = useState<any>({});
  const userId = storage.getUserId();
  const authUser = storage.getAuthUser<any>();

  useEffect(() => {
    setProfile(storage.getProfile() || {});
    if (userId) {
      api.getProfile(userId).then((result) => {
        const freshProfile = normalizeProfile(result.profile);
        setProfile(freshProfile);
        storage.setProfile(freshProfile);
        storage.setUserName(freshProfile.name);
        storage.setGoal(freshProfile.goal);
        storage.setCredits(Number(result.profile.credits ?? storage.getCredits()));
        storage.setRole(result.profile.role || storage.getRole());
        storage.setTelegram(freshProfile.telegram || "");
        storage.setWhatsapp(freshProfile.whatsapp || "");
      }).catch(() => {});
    }
  }, [userId]);

  function logout() {
    storage.logout();
    toast.message("Logged out");
    navigate({ to: "/login" });
  }

  async function resetProfile() {
    const existingUserId = storage.getUserId();
    let historyCleared = true;
    if (existingUserId) {
      try {
        await api.clearHistory(existingUserId);
      } catch (error) {
        historyCleared = false;
      }
    }
    storage.resetProfile();
    if (historyCleared) {
      toast.message("Profile reset", { description: "History cleared. Create a fresh profile to continue." });
    } else {
      toast.warning("Profile reset", { description: "Local profile cleared. History cleanup did not finish, but you can recreate onboarding now." });
    }
    navigate({ to: "/onboarding", replace: true });
  }

  return (
    <div className="space-y-6 animate-fade-up max-w-3xl">
      <header>
        <div className="text-[11px] uppercase tracking-wider text-text-light font-medium">Settings</div>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">Account Settings</h1>
        <p className="mt-1 text-sm text-text-secondary">Manage sign-in and app actions.</p>
      </header>

      <section className="rounded-xl border border-border bg-surface shadow-soft p-5">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="size-10 rounded-lg bg-primary-light grid place-items-center text-primary">
              <ShieldCheck className="size-5" />
            </div>
            <div>
              <h2 className="text-sm font-semibold">Signed in</h2>
              <p className="text-sm text-text-secondary mt-1">{authUser?.email || authUser?.name || "Local account"}</p>
              <p className="text-xs text-text-light mt-1">Profile ID: {userId || "Not created yet"}</p>
            </div>
          </div>
          <button onClick={logout} className="inline-flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-sm font-medium text-text-secondary hover:text-destructive hover:border-destructive/30 transition">
            <LogOut className="size-4" /> Logout
          </button>
        </div>
      </section>

      <section className="rounded-xl border border-border bg-surface shadow-soft p-5">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="size-10 rounded-lg bg-destructive/10 grid place-items-center text-destructive">
              <RotateCcw className="size-5" />
            </div>
            <div>
              <h2 className="text-sm font-semibold">Reset Local Profile</h2>
              <p className="text-sm text-text-secondary mt-1">Clear this browser's profile, plan cache, streak, and saved user ID.</p>
            </div>
          </div>
          <button onClick={resetProfile} className="inline-flex items-center gap-2 rounded-lg border border-destructive/30 bg-background px-3 py-2 text-sm font-medium text-destructive hover:bg-destructive/5 transition">
            <RotateCcw className="size-4" /> Reset
          </button>
        </div>
      </section>
    </div>
  );
}

function normalizeProfile(raw: any) {
  return {
    name: raw?.name || "",
    email: raw?.email || "",
    age: Number(raw?.age || 28),
    weight: Number(raw?.weight ?? raw?.weight_kg ?? 70),
    height: Number(raw?.height ?? raw?.height_cm ?? 170),
    goal: raw?.goal || "maintenance",
    weekly_budget: Number(raw?.weekly_budget ?? raw?.budget_weekly ?? 2500),
    telegram: raw?.telegram ?? raw?.telegram_id ?? "",
    whatsapp: raw?.whatsapp ?? raw?.whatsapp_number ?? "",
    dietary_preference: raw?.dietary_preference ?? raw?.dietary_type ?? "Vegetarian",
    allergies: raw?.allergies || [],
    preferences: raw?.preferences || [],
    family: raw?.family || [],
  };
}
