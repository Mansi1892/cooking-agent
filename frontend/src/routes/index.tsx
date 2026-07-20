import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import {
  Sparkles, Flame, Target, Wallet, Activity, Drumstick,
  ArrowRight, Heart, ChevronRight, Plus, CalendarRange,
} from "lucide-react";
import { storage } from "@/lib/storage";
import { api, mock, safe, type MealPlan } from "@/lib/api";

export const Route = createFileRoute("/")({
  component: Dashboard,
});

function greeting() {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

function Dashboard() {
  const navigate = useNavigate();
  const [name, setName] = useState("there");
  const [userId, setUserId] = useState<string | null>(null);
  const [plan, setPlan] = useState<MealPlan | null>(null);
  const [streak, setStreak] = useState(0);

  useEffect(() => {
    const uid = storage.getUserId();
    setUserId(uid);
    setName((storage.getUserName() || "there").split(" ")[0]);
    setStreak(storage.getStreak() || 0);
    if (!storage.isLoggedIn()) {
      navigate({ to: "/login" });
      return;
    }
    if (!uid) {
      navigate({ to: "/onboarding" });
      return;
    }
    if (uid) {
      safe(api.getLatestPlan(uid).then((r) => r.plan), mock.plan(storage.getProfile())).then(setPlan);
      api.getStreak(uid).then((result) => {
        storage.setStreak(result.streak);
        setStreak(result.streak);
      }).catch(() => {});
    } else {
      setPlan(mock.plan(storage.getProfile()));
    }
  }, [navigate]);

  const summary = plan?.week_summary ?? mock.plan(storage.getProfile()).week_summary!;

  return (
    <div className="space-y-8 animate-fade-up">
      {/* Header */}
      <header className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-3xl sm:text-4xl font-semibold tracking-tight">
            {greeting()}, {name} <span className="inline-block animate-pop-in">👋</span>
          </h1>
          <p className="mt-1.5 text-text-secondary">Today's focus — stay consistent, you're on a {streak}-week planning streak.</p>
        </div>
        <Link to="/meal-plans" className="hidden sm:inline-flex items-center gap-2 rounded-lg bg-primary text-primary-foreground px-4 py-2.5 text-sm font-medium hover:opacity-90 transition shadow-soft">
          <Sparkles className="size-4" /> Generate Plan
        </Link>
      </header>

      {/* Metrics */}
      <section className="grid grid-cols-2 lg:grid-cols-5 gap-3 sm:gap-4">
        <MetricCard icon={Activity} tint="primary" label="Avg Daily Calories" value={summary.avg_calories.toLocaleString()} unit="kcal" delta="+2.1%" />
        <MetricCard icon={Drumstick} tint="accent" label="Avg Daily Protein" value={`${summary.avg_protein}g`} delta="+8g" />
        <MetricCard icon={Wallet} tint="warning" label="Est. Grocery Cost" value={`₹${summary.total_budget.toLocaleString()}`} />
        <MetricCard icon={Heart} tint="success" label="Healthy Score" value={`${summary.healthy_score}`} unit="/100" delta="+4" deltaPositive />
        <MetricCard icon={Flame} tint="error" label="Planning Streak" value={`${streak}`} unit={streak === 1 ? "week" : "weeks"} />
      </section>

      {/* Hero AI Card */}
      <section className="relative overflow-hidden rounded-2xl hero-gradient text-white shadow-glow">
        <div className="absolute -top-20 -right-20 size-80 rounded-full bg-white/10 blur-3xl" />
        <div className="absolute bottom-0 left-0 size-72 rounded-full bg-white/10 blur-3xl" />
        <div className="relative p-6 sm:p-10 grid lg:grid-cols-[1.4fr_1fr] gap-8 items-center">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full bg-white/15 backdrop-blur px-3 py-1 text-[11px] font-medium uppercase tracking-wider">
              <Sparkles className="size-3" /> AI Planner
            </div>
            <h2 className="mt-4 text-2xl sm:text-4xl font-semibold tracking-tight leading-tight">
              Ready for this week's<br /> AI meal plan?
            </h2>
            <p className="mt-3 text-white/80 max-w-md text-sm sm:text-base">
              Personalized to your goal, budget, allergies and family. Generated in seconds.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Link to="/meal-plans" className="inline-flex items-center gap-2 rounded-lg bg-white text-primary px-4 py-2.5 text-sm font-semibold hover:bg-white/95 transition">
                Generate Plan <ArrowRight className="size-4" />
              </Link>
              <Link to="/history" className="inline-flex items-center gap-2 rounded-lg bg-white/10 backdrop-blur border border-white/20 px-4 py-2.5 text-sm font-medium hover:bg-white/15 transition">
                View History
              </Link>
            </div>
          </div>
          <div className="hidden lg:block">
            <div className="rounded-2xl bg-white/10 backdrop-blur-md border border-white/15 p-5 space-y-3">
              {[
                { l: "Analyzing profile", v: 100 },
                { l: "Finding recipes", v: 100 },
                { l: "Optimizing nutrition", v: 88 },
                { l: "Calculating calories", v: 64 },
                { l: "Building grocery list", v: 32 },
              ].map((step) => (
                <div key={step.l}>
                  <div className="flex justify-between text-[11px] text-white/80 mb-1">
                    <span>{step.l}</span><span>{step.v}%</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-white/15 overflow-hidden">
                    <div className="h-full bg-white rounded-full transition-all duration-700" style={{ width: `${step.v}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Recent plan + Quick actions */}
      <section className="grid lg:grid-cols-[1.5fr_1fr] gap-5">
        <div className="rounded-2xl border border-border bg-surface shadow-soft p-6">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-[11px] uppercase tracking-wider text-text-light font-medium">This Week</div>
              <h3 className="text-lg font-semibold mt-1">Current Meal Plan</h3>
            </div>
            <Link to="/meal-plans" className="text-sm text-primary font-medium inline-flex items-center hover:underline">
              View all <ChevronRight className="size-4" />
            </Link>
          </div>
          <div className="mt-5 grid grid-cols-2 sm:grid-cols-4 gap-3">
            {(plan?.days ?? []).slice(0, 4).map((d) => (
              <div key={d.day} className="rounded-xl border border-border p-3 hover:shadow-elevated hover:-translate-y-0.5 transition">
                <div className="text-[11px] uppercase tracking-wider text-text-light font-medium">{d.day.slice(0,3)}</div>
                <div className="mt-2 text-base font-semibold">{d.calories} <span className="text-xs font-normal text-text-light">kcal</span></div>
                <div className="text-xs text-text-secondary">{d.protein}g protein</div>
                <div className="mt-3 h-1 rounded-full bg-muted overflow-hidden">
                  <div className="h-full bg-success" style={{ width: `${Math.min(100, (d.protein / 180) * 100)}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-2xl border border-border bg-surface shadow-soft p-6 flex flex-col gap-3">
          <div className="text-[11px] uppercase tracking-wider text-text-light font-medium">Quick actions</div>
          <QuickRow icon={CalendarRange} label="Open Meal Plans" to="/meal-plans" />
          <QuickRow icon={Plus} label="Add Family Member" to="/profile" />
          <QuickRow icon={Target} label="Update Goal" to="/profile" />
          <QuickRow icon={Wallet} label="Edit Weekly Budget" to="/settings" />
        </div>
      </section>
    </div>
  );
}

function MetricCard({
  icon: Icon, tint, label, value, unit, delta, deltaPositive,
}: { icon: any; tint: "primary"|"accent"|"warning"|"success"|"error"; label: string; value: string; unit?: string; delta?: string; deltaPositive?: boolean }) {
  const tintMap: Record<string, string> = {
    primary: "bg-primary-light text-primary",
    accent: "bg-cyan-50 text-accent",
    warning: "bg-amber-50 text-warning",
    success: "bg-emerald-50 text-success",
    error: "bg-rose-50 text-destructive",
  };
  return (
    <div className="rounded-xl border border-border bg-surface p-4 shadow-soft hover:shadow-elevated hover:-translate-y-0.5 transition">
      <div className="flex items-center justify-between">
        <div className={`size-8 rounded-lg grid place-items-center ${tintMap[tint]}`}>
          <Icon className="size-4" />
        </div>
        {delta && (
          <span className={`text-[11px] font-medium ${deltaPositive ? "text-success" : "text-text-light"}`}>{delta}</span>
        )}
      </div>
      <div className="mt-3 text-xs text-text-light font-medium">{label}</div>
      <div className="mt-0.5 text-xl font-semibold tracking-tight">
        {value}{unit && <span className="text-xs font-normal text-text-light ml-1">{unit}</span>}
      </div>
    </div>
  );
}

function QuickRow({ icon: Icon, label, to }: { icon: any; label: string; to: string }) {
  return (
    <Link to={to} className="group flex items-center gap-3 rounded-lg border border-border px-3 py-2.5 hover:border-primary/40 hover:bg-primary-light/40 transition">
      <div className="size-8 rounded-md bg-primary-light text-primary grid place-items-center">
        <Icon className="size-4" />
      </div>
      <span className="text-sm font-medium">{label}</span>
      <ChevronRight className="ml-auto size-4 text-text-light group-hover:text-primary transition" />
    </Link>
  );
}
