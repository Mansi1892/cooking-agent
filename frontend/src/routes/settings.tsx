import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Bell, LogOut, RotateCcw, Send, ShieldCheck, UserCog } from "lucide-react";
import { api } from "@/lib/api";
import { storage } from "@/lib/storage";
import { toast } from "sonner";

export const Route = createFileRoute("/settings")({
  component: Settings,
});

function Settings() {
  const navigate = useNavigate();
  const [profile, setProfile] = useState<any>({});
  const [testingTelegram, setTestingTelegram] = useState(false);
  const [testingWhatsapp, setTestingWhatsapp] = useState(false);
  const [savingWhatsapp, setSavingWhatsapp] = useState(false);
  const [whatsappInput, setWhatsappInput] = useState("");
  const userId = storage.getUserId();
  const authUser = storage.getAuthUser<any>();
  const telegram = profile.telegram || profile.telegram_id || storage.getTelegram() || "";
  const whatsapp = profile.whatsapp || profile.whatsapp_number || storage.getWhatsapp() || "";

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
        setWhatsappInput(freshProfile.whatsapp || "");
      }).catch(() => {});
    }
  }, [userId]);

  useEffect(() => {
    setWhatsappInput(whatsapp || "");
  }, [whatsapp]);

  async function testTelegram() {
    if (!userId) {
      toast.error("Create profile first");
      return;
    }
    if (!telegram) {
      toast.error("Telegram chat ID missing", { description: "Add it from Profile, then test again." });
      return;
    }
    setTestingTelegram(true);
    try {
      const result = await api.updateProfile(userId, { ...profile, telegram });
      const freshProfile = normalizeProfile(result.profile);
      setProfile(freshProfile);
      storage.setProfile(freshProfile);
      storage.setTelegram(freshProfile.telegram || "");
      await api.testTelegram(userId);
      toast.success("Telegram is working", { description: "A test message was sent to your chat." });
    } catch (error) {
      toast.error("Telegram is not working", { description: error instanceof Error ? error.message : "Please check bot token and chat ID." });
    } finally {
      setTestingTelegram(false);
    }
  }

  async function saveWhatsapp() {
    if (!userId) {
      toast.error("Create profile first");
      return false;
    }
    const cleanedWhatsapp = whatsappInput.replace(/\D/g, "");
    if (whatsappInput.trim() && cleanedWhatsapp.length < 10) {
      toast.error("Enter a valid WhatsApp number", { description: "Use country code, no +. Example: 919876543210" });
      return false;
    }
    setSavingWhatsapp(true);
    try {
      const result = await api.updateProfile(userId, {
        ...profile,
        whatsapp: cleanedWhatsapp,
        whatsapp_number: cleanedWhatsapp,
      });
      const freshProfile = normalizeProfile(result.profile);
      setProfile(freshProfile);
      setWhatsappInput(freshProfile.whatsapp || "");
      storage.setProfile(freshProfile);
      storage.setWhatsapp(freshProfile.whatsapp || "");
      toast.success("WhatsApp number saved");
      return true;
    } catch (error) {
      toast.error("WhatsApp number was not saved", { description: error instanceof Error ? error.message : "Please try again." });
      return false;
    } finally {
      setSavingWhatsapp(false);
    }
  }

  async function testWhatsapp() {
    if (!userId) {
      toast.error("Create profile first");
      return;
    }
    const cleanedWhatsapp = whatsappInput.replace(/\D/g, "");
    if (!cleanedWhatsapp) {
      toast.error("WhatsApp number missing", { description: "Add it here, save, then test again." });
      return;
    }
    setTestingWhatsapp(true);
    try {
      if (cleanedWhatsapp !== whatsapp) {
        const saved = await saveWhatsapp();
        if (!saved) return;
      }
      await api.testWhatsapp(userId);
      toast.success("WhatsApp is working", { description: "A test message was sent to your WhatsApp." });
    } catch (error) {
      toast.error("WhatsApp is not working", { description: error instanceof Error ? error.message : "Please check Meta setup and test recipient." });
    } finally {
      setTestingWhatsapp(false);
    }
  }

  function logout() {
    storage.logout();
    toast.message("Logged out");
    navigate({ to: "/login" });
  }

  function resetProfile() {
    storage.resetProfile();
    toast.message("Profile reset", { description: "Create a fresh profile to continue." });
    navigate({ to: "/onboarding" });
  }

  return (
    <div className="space-y-6 animate-fade-up max-w-3xl">
      <header>
        <div className="text-[11px] uppercase tracking-wider text-text-light font-medium">Settings</div>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">Account Settings</h1>
        <p className="mt-1 text-sm text-text-secondary">Manage sign-in, notifications, and app actions.</p>
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

      <section className="rounded-xl border border-border bg-surface shadow-soft p-5 space-y-4">
        <div className="flex items-start gap-3">
          <div className="size-10 rounded-lg bg-primary-light grid place-items-center text-primary">
            <Bell className="size-5" />
          </div>
          <div className="min-w-0 flex-1">
            <h2 className="text-sm font-semibold">Telegram Notifications</h2>
            <p className="text-sm text-text-secondary mt-1">Meal plans are sent to this chat after generation.</p>
          </div>
        </div>

        <div className="rounded-lg border border-border bg-background px-3.5 py-3">
          <div className="text-xs font-medium text-text-secondary">Current chat ID</div>
          <div className="mt-1 text-sm font-medium">{telegram || "Not added"}</div>
        </div>

        <div className="flex flex-wrap gap-3">
          <button onClick={testTelegram} disabled={testingTelegram || !telegram} className="inline-flex items-center gap-2 rounded-lg bg-primary text-primary-foreground px-4 py-2.5 text-sm font-medium hover:opacity-90 transition disabled:opacity-50 disabled:cursor-not-allowed">
            <Send className="size-4" /> {testingTelegram ? "Testing..." : "Send test message"}
          </button>
          <Link to="/profile" className="inline-flex items-center gap-2 rounded-lg border border-border bg-background px-4 py-2.5 text-sm font-medium text-text-secondary hover:text-text-primary transition">
            <UserCog className="size-4" /> Edit profile
          </Link>
        </div>
      </section>

      <section className="rounded-xl border border-border bg-surface shadow-soft p-5 space-y-4">
        <div className="flex items-start gap-3">
          <div className="size-10 rounded-lg bg-primary-light grid place-items-center text-primary">
            <Bell className="size-5" />
          </div>
          <div className="min-w-0 flex-1">
            <h2 className="text-sm font-semibold">WhatsApp Notifications</h2>
            <p className="text-sm text-text-secondary mt-1">Meal plan approve/reject will use this number after WhatsApp sending is enabled.</p>
          </div>
        </div>

        <label className="block">
          <div className="text-xs font-medium text-text-secondary mb-1.5">WhatsApp number</div>
          <input
            value={whatsappInput}
            onChange={(event) => setWhatsappInput(event.target.value)}
            placeholder="919876543210"
            className="w-full rounded-lg border border-border bg-background px-3.5 py-2.5 text-sm outline-none focus:border-primary/40 focus:ring-2 focus:ring-primary/20"
          />
          <div className="mt-1 text-[11px] text-text-light">Use country code, no + or spaces.</div>
        </label>

        <div className="flex flex-wrap gap-3">
          <button onClick={saveWhatsapp} disabled={savingWhatsapp} className="inline-flex items-center gap-2 rounded-lg bg-primary text-primary-foreground px-4 py-2.5 text-sm font-medium hover:opacity-90 transition disabled:opacity-50">
            <Send className="size-4" /> {savingWhatsapp ? "Saving..." : "Save WhatsApp"}
          </button>
          <button onClick={testWhatsapp} disabled={testingWhatsapp || savingWhatsapp || !whatsappInput.replace(/\D/g, "")} className="inline-flex items-center gap-2 rounded-lg border border-border bg-background px-4 py-2.5 text-sm font-medium text-text-secondary hover:text-text-primary transition disabled:opacity-50">
            <Send className="size-4" /> {testingWhatsapp ? "Testing..." : "Send test message"}
          </button>
          <Link to="/profile" className="inline-flex items-center gap-2 rounded-lg border border-border bg-background px-4 py-2.5 text-sm font-medium text-text-secondary hover:text-text-primary transition">
            <UserCog className="size-4" /> Edit full profile
          </Link>
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
