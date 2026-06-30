import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Pencil, Target, Activity, Flame, User as UserIcon } from "lucide-react";
import { storage } from "@/lib/storage";

export const Route = createFileRoute("/profile")({
  component: Profile,
});

function Profile() {
  const [profile, setProfile] = useState<any>(null);
  const [streak, setStreak] = useState(0);

  useEffect(() => {
    setProfile(storage.getProfile() || { name: storage.getUserName() || "Guest", goal: storage.getGoal() || "maintenance", weight: 70, height: 170, age: 28, weekly_budget: 80, family: [] });
    setStreak(storage.getStreak() || 5);
  }, []);

  if (!profile) return null;
  const bmi = profile.weight && profile.height ? (profile.weight / Math.pow(profile.height / 100, 2)).toFixed(1) : "—";
  const initials = (profile.name || "U").split(" ").map((s: string) => s[0]).join("").slice(0, 2).toUpperCase();

  return (
    <div className="space-y-8 animate-fade-up">
      <header className="rounded-2xl border border-border bg-surface shadow-soft p-6 sm:p-8 flex flex-wrap items-center gap-6">
        <div className="size-20 rounded-2xl hero-gradient text-white text-2xl font-semibold grid place-items-center shadow-glow">
          {initials}
        </div>
        <div className="flex-1 min-w-0">
          <h1 className="text-2xl font-semibold tracking-tight">{profile.name}</h1>
          <p className="text-sm text-text-secondary capitalize mt-0.5">Goal · {String(profile.goal).replace("_", " ")} · {streak}-day streak 🔥</p>
        </div>
        <Link to="/settings" className="inline-flex items-center gap-2 rounded-lg border border-border bg-surface px-4 py-2.5 text-sm font-medium hover:bg-muted transition">
          <Pencil className="size-4" /> Edit profile
        </Link>
      </header>

      <section className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <Stat icon={Target} label="Weight" value={`${profile.weight} kg`} />
        <Stat icon={Activity} label="Height" value={`${profile.height} cm`} />
        <Stat icon={Flame} label="BMI" value={bmi} />
        <Stat icon={UserIcon} label="Age" value={`${profile.age}`} />
      </section>

      <section className="grid lg:grid-cols-2 gap-5">
        <div className="rounded-2xl border border-border bg-surface shadow-soft p-6">
          <h3 className="text-sm font-semibold">Health preferences</h3>
          <div className="mt-4 flex flex-wrap gap-2">
            {["High-protein", "Mediterranean", "Low sugar", "Whole foods", "Plant-forward"].map((t) => (
              <span key={t} className="text-xs font-medium px-2.5 py-1 rounded-full bg-primary-light text-primary">{t}</span>
            ))}
          </div>
          <h3 className="mt-6 text-sm font-semibold">Allergies</h3>
          <div className="mt-3 flex flex-wrap gap-2">
            {["Peanuts"].map((t) => (
              <span key={t} className="text-xs font-medium px-2.5 py-1 rounded-full bg-destructive/10 text-destructive">{t}</span>
            ))}
          </div>
        </div>

        <div className="rounded-2xl border border-border bg-surface shadow-soft p-6">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold">Family members</h3>
            <span className="text-xs text-text-light">{(profile.family ?? []).length} added</span>
          </div>
          <ul className="mt-4 space-y-2">
            {(profile.family ?? []).length === 0 && (
              <li className="text-sm text-text-light">No family members yet.</li>
            )}
            {(profile.family ?? []).map((m: any, i: number) => (
              <li key={i} className="flex items-center gap-3 rounded-lg border border-border p-3">
                <span className="size-9 rounded-full bg-primary-light text-primary grid place-items-center text-xs font-semibold">
                  {(m.name || "?").slice(0,1).toUpperCase()}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium truncate">{m.name || "Unnamed"}</div>
                  <div className="text-xs text-text-light capitalize">{m.diet}</div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </section>
    </div>
  );
}

function Stat({ icon: Icon, label, value }: { icon: any; label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4 shadow-soft">
      <div className="flex items-center gap-2 text-[11px] text-text-light font-medium uppercase tracking-wider">
        <Icon className="size-3.5" /> {label}
      </div>
      <div className="mt-1.5 text-xl font-semibold">{value}</div>
    </div>
  );
}
