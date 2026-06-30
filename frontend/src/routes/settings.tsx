import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { LogOut, Save } from "lucide-react";
import { storage } from "@/lib/storage";
import { toast } from "sonner";

export const Route = createFileRoute("/settings")({
  component: Settings,
});

function Settings() {
  const navigate = useNavigate();
  const [profile, setProfile] = useState<any>({});

  useEffect(() => {
    setProfile(storage.getProfile() || { name: storage.getUserName() || "", goal: "maintenance", weekly_budget: 80, telegram: storage.getTelegram() || "" });
  }, []);

  function save() {
    storage.setProfile(profile);
    if (profile.name) storage.setUserName(profile.name);
    if (profile.goal) storage.setGoal(profile.goal);
    if (profile.telegram) storage.setTelegram(profile.telegram);
    toast.success("Settings saved");
  }

  function reset() {
    storage.clearAll();
    toast.message("Profile cleared");
    navigate({ to: "/onboarding" });
  }

  return (
    <div className="space-y-8 animate-fade-up max-w-2xl">
      <header>
        <div className="text-[11px] uppercase tracking-wider text-text-light font-medium">Settings</div>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">Account</h1>
        <p className="mt-1 text-sm text-text-secondary">Update your profile and preferences.</p>
      </header>

      <section className="rounded-2xl border border-border bg-surface shadow-soft p-6 space-y-4">
        <Field label="Name">
          <input className={inp} value={profile.name || ""} onChange={(e) => setProfile({ ...profile, name: e.target.value })} />
        </Field>
        <Field label="Goal">
          <select className={inp} value={profile.goal || "maintenance"} onChange={(e) => setProfile({ ...profile, goal: e.target.value })}>
            <option value="weight_loss">Weight loss</option>
            <option value="muscle_gain">Muscle gain</option>
            <option value="maintenance">Maintenance</option>
          </select>
        </Field>
        <div className="grid sm:grid-cols-2 gap-4">
          <Field label="Weekly budget (USD)">
            <input type="number" className={inp} value={profile.weekly_budget || 0} onChange={(e) => setProfile({ ...profile, weekly_budget: Number(e.target.value) })} />
          </Field>
          <Field label="Telegram">
            <input className={inp} value={profile.telegram || ""} onChange={(e) => setProfile({ ...profile, telegram: e.target.value })} placeholder="@username" />
          </Field>
        </div>
        <div className="pt-2 flex items-center justify-between">
          <button onClick={save} className="inline-flex items-center gap-2 rounded-lg bg-primary text-primary-foreground px-4 py-2.5 text-sm font-medium hover:opacity-90 transition">
            <Save className="size-4" /> Save changes
          </button>
          <button onClick={reset} className="inline-flex items-center gap-2 text-sm text-destructive hover:underline">
            <LogOut className="size-4" /> Reset profile
          </button>
        </div>
      </section>
    </div>
  );
}

const inp = "w-full rounded-lg border border-border bg-surface px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/40 transition";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <div className="text-xs font-medium text-text-secondary mb-1.5">{label}</div>
      {children}
    </label>
  );
}
