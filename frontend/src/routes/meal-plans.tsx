import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import {
  Sparkles, ChevronDown, ChevronUp, Clock, Flame, CheckCircle2, Loader2, ArrowRight, BookOpen, X, CalendarRange,
} from "lucide-react";
import { api, type MealPlan, type Recipe } from "@/lib/api";
import { storage } from "@/lib/storage";
import { toast } from "sonner";

export const Route = createFileRoute("/meal-plans")({
  component: MealPlans,
});

const STEPS = [
  "Analyzing profile",
  "Finding recipes",
  "Optimizing nutrition",
  "Calculating calories",
  "Building grocery list",
  "Saving your plan",
];

const APPROVAL_TOAST_IDS = new Set<string>();

function showApprovalToastOnce(planId: string, description: string) {
  if (!planId || APPROVAL_TOAST_IDS.has(planId)) return;
  APPROVAL_TOAST_IDS.add(planId);
  toast.success("Plan approved", {
    id: `plan-approved-${planId}`,
    description,
  });
}

function MealPlans() {
  const [plan, setPlan] = useState<MealPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [recipeLoading, setRecipeLoading] = useState(false);
  const [recipe, setRecipe] = useState<Recipe | null>(null);
  const [progress, setProgress] = useState(0);
  const [openDay, setOpenDay] = useState<string | null>("Monday");
  const [credits, setCredits] = useState(storage.getCredits());
  const [role, setRole] = useState(storage.getRole());
  const [creditRequested, setCreditRequested] = useState(false);
  const [weekOffset, setWeekOffset] = useState(0);
  const [activePersonId, setActivePersonId] = useState<string>("");
  const [regeneratingDay, setRegeneratingDay] = useState<string>("");

  useEffect(() => {
    const userId = storage.getUserId();
    if (userId) {
      api.getProfile(userId).then((result) => {
        const nextCredits = Number(result.profile.credits ?? 0);
        storage.setCredits(nextCredits);
        storage.setRole(result.profile.role || "user");
        setCredits(nextCredits);
        setRole(result.profile.role || "user");
      }).catch(() => {});
    }
    if (userId) {
      api.getLatestPlan(userId).then((r) => setPlan(r.plan)).catch(() => setPlan(null)).finally(() => setLoading(false));
    } else {
      setPlan(null);
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const userId = storage.getUserId();
    if (!userId || plan?.status === "approved") return;
    const timer = window.setInterval(() => {
      api.getLatestPlan(userId).then((result) => {
        setPlan(result.plan);
        const planId = String(result.plan.id || "");
        if (result.plan.status === "approved") {
          showApprovalToastOnce(planId, "Recipes are unlocked.");
        }
      }).catch(() => {});
    }, 5000);
    return () => window.clearInterval(timer);
  }, [plan?.id, plan?.status]);

  async function generate() {
    if (generating) return;
    const isAdmin = role === "admin";
    if (storage.getUserId() && !isAdmin && credits <= 0) {
      toast.error("No meal plan credits left", { description: "You used your 3 free credits. Please ask admin to add more credits." });
      return;
    }
    setGenerating(true);
    setProgress(0);
    const userId = storage.getUserId();
    if (!userId) {
      toast.error("Create profile first");
      setGenerating(false);
      return;
    }
    // simulated progress
    const ticker = setInterval(() => {
      setProgress((p) => (p < 90 ? p + 5 : p));
    }, 350);
    try {
      let newPlan: MealPlan;
      try {
        const result = await api.generatePlan(userId, { week_offset: weekOffset });
        newPlan = "plan" in result ? result.plan : result;
        const planId = String(newPlan.id || "");
        if ("credits_remaining" in result && typeof result.credits_remaining === "number") {
          storage.setCredits(result.credits_remaining);
          setCredits(result.credits_remaining);
        }
        if ("telegram_sent" in result && result.telegram_sent) {
          toast.success("Sent to Telegram for approval");
        } else if ("telegram_queued" in result && result.telegram_queued) {
          toast.success("Telegram send queued", { description: "Your plan will arrive shortly." });
        } else if ("auto_approved" in result && result.auto_approved) {
          showApprovalToastOnce(planId, "No Telegram chat ID found, so the plan was finalized here.");
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : "";
        if (message.toLowerCase().includes("credit")) {
          toast.error("No meal plan credits left", { description: message });
          return;
        }
        toast.error("Could not generate plan", { description: message || "Backend unavailable. Please try again." });
        return;
      }
      setPlan(newPlan);
      setActivePersonId(newPlan.people_plans?.[0]?.person_id || "");
      storage.setLastPlanId(newPlan.id);
      setProgress(100);
      if (newPlan.status !== "approved") {
        toast.success("Your meal plan is ready");
      }
    } finally {
      clearInterval(ticker);
      setTimeout(() => setGenerating(false), 400);
    }
  }

  async function requestMoreCredits() {
    const userId = storage.getUserId();
    if (!userId) return;
    try {
      await api.requestCredits({ user_id: userId, requested_credits: 3, note: "User requested more meal plan credits." });
      setCreditRequested(true);
      toast.success("Credit request sent", { description: "Admin can now approve it from the Admin page." });
    } catch (error) {
      toast.error("Could not request credits", { description: error instanceof Error ? error.message : "Please try again." });
    }
  }

  async function openRecipe(meal: { name: string; type: string }) {
    const userId = storage.getUserId();
    if (!userId) return;
    setRecipe(null);
    setRecipeLoading(true);
    try {
      const result = await api.generateRecipe({ user_id: userId, meal_name: meal.name, meal_type: meal.type });
      setRecipe(result.recipe);
    } catch (error) {
      toast.error("Recipe not ready", { description: error instanceof Error ? error.message : "Please try again." });
    } finally {
      setRecipeLoading(false);
    }
  }

  async function changePersonDay(day: string) {
    const userId = storage.getUserId();
    if (!userId || !plan?.id || !activePerson?.person_id) return;
    const feedback = window.prompt(`What should change for ${activePerson.name}'s ${day}?`, "Make it lighter and avoid repeating meals");
    if (!feedback?.trim()) return;
    const key = `${activePerson.person_id}:${day}`;
    setRegeneratingDay(key);
    try {
      const result = await api.regeneratePersonDay({
        user_id: userId,
        plan_id: plan.id,
        person_id: activePerson.person_id,
        day,
        feedback: feedback.trim(),
      });
      setPlan(result.plan);
      setActivePersonId(activePerson.person_id);
      toast.success("Updated this person's day", { description: `${activePerson.name}'s ${day} was regenerated.` });
    } catch (error) {
      toast.error("Could not update this day", { description: error instanceof Error ? error.message : "Please try again." });
    } finally {
      setRegeneratingDay("");
    }
  }

  if (loading) return <SkeletonPage />;

  const s = plan?.week_summary ?? { healthy_score: 0, avg_calories: 0, avg_protein: 0, total_budget: 0 };
  const recipesUnlocked = plan?.status === "approved";
  const isAdmin = role === "admin";
  const peoplePlans = plan?.people_plans ?? [];
  const activePerson = peoplePlans.find((person) => person.person_id === activePersonId) || peoplePlans[0];
  const displayDays = activePerson?.days || plan?.days || [];

  return (
    <div className="space-y-8 animate-fade-up">
      <header className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <div className="text-[11px] uppercase tracking-wider text-text-light font-medium">Meal Plans</div>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">Your weekly plan</h1>
          <p className="mt-1 text-text-secondary text-sm">Generated by AI, balanced to your goal and budget.</p>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <div className="rounded-lg border border-border bg-surface px-3 py-2 text-sm">
            <span className="text-text-light">Credits</span> <span className="font-semibold">{isAdmin ? "Unlimited" : credits}</span>
          </div>
          <select
            value={weekOffset}
            onChange={(event) => setWeekOffset(Number(event.target.value))}
            disabled={generating}
            className="h-10 rounded-lg border border-border bg-surface px-3 text-sm font-medium text-text-primary outline-none focus:ring-2 focus:ring-primary/20 disabled:opacity-60"
            aria-label="Planning week"
          >
            <option value={0}>This week</option>
            <option value={1}>Next week</option>
          </select>
          <button
            onClick={!isAdmin && credits <= 0 ? requestMoreCredits : generate}
            disabled={generating || creditRequested}
            className="inline-flex items-center gap-2 rounded-lg bg-primary text-primary-foreground px-4 py-2.5 text-sm font-medium hover:opacity-90 transition disabled:opacity-60 shadow-soft"
          >
            {generating ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
            {generating ? "Generating…" : !isAdmin && credits <= 0 ? (creditRequested ? "Request sent" : "Ask admin for credits") : "Generate new plan"}
          </button>
        </div>
      </header>

      {generating && (
        <section className="rounded-2xl border border-border bg-surface shadow-soft p-6">
          <div className="flex items-center justify-between">
            <div className="text-sm font-semibold">Crafting your plan</div>
            <div className="text-xs text-text-light">AI is working</div>
          </div>
          <div className="mt-4 h-1.5 rounded-full bg-muted overflow-hidden">
            <div className="h-full hero-gradient transition-all duration-300" style={{ width: `${progress}%` }} />
          </div>
          <ul className="mt-5 grid sm:grid-cols-2 gap-2">
            {STEPS.map((label, i) => {
              const reached = progress >= ((i + 1) / STEPS.length) * 100;
              return (
                <li key={label} className="flex items-center gap-2 text-sm">
                  {reached ? <CheckCircle2 className="size-4 text-success" /> : <Loader2 className="size-4 animate-spin text-primary" />}
                  <span className={reached ? "text-text-primary" : "text-text-secondary"}>{label}</span>
                </li>
              );
            })}
          </ul>
        </section>
      )}

      {!isAdmin && credits <= 0 && !generating && (
        <section className="rounded-2xl border border-warning/30 bg-warning/10 p-5 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-sm font-semibold">Credits expired</h2>
            <p className="mt-1 text-sm text-text-secondary">Please request more credits to generate another meal plan.</p>
          </div>
          <button onClick={requestMoreCredits} disabled={creditRequested} className="inline-flex items-center gap-2 rounded-lg bg-primary text-primary-foreground px-4 py-2.5 text-sm font-medium hover:opacity-90 disabled:opacity-60 transition">
            {creditRequested ? "Request sent" : "Request credits"}
          </button>
        </section>
      )}

      {!plan && !generating ? (
        <section className="rounded-2xl border border-border bg-surface shadow-soft p-6">
          <div className="flex items-start gap-3">
            <div className="size-10 rounded-lg bg-primary-light grid place-items-center text-primary">
              <CalendarRange className="size-5" />
            </div>
            <div>
              <h2 className="text-sm font-semibold">No meal plan yet</h2>
              <p className="mt-1 text-sm text-text-secondary">Generate your first weekly meal plan to see meals, summary, grocery, and recipes here.</p>
            </div>
          </div>
        </section>
      ) : plan && (
        <>
          {/* Summary */}
          {peoplePlans.length > 0 && (
            <section className="rounded-2xl border border-border bg-surface shadow-soft p-4">
              <div className="flex items-center gap-2 overflow-x-auto pb-1">
                {peoplePlans.map((person) => {
                  const active = (activePerson?.person_id || "") === person.person_id;
                  return (
                    <button
                      key={person.person_id}
                      onClick={() => setActivePersonId(person.person_id)}
                      className={[
                        "shrink-0 rounded-lg border px-3.5 py-2 text-sm font-medium transition",
                        active ? "border-primary bg-primary text-primary-foreground" : "border-border bg-background hover:bg-muted",
                      ].join(" ")}
                    >
                      {person.name}
                    </button>
                  );
                })}
              </div>
              {activePerson && (
                <div className="mt-3 text-xs text-text-secondary capitalize">
                  {activePerson.goal.replace("_", " ")} · {activePerson.dietary_type?.replace("_", " ")} · target {activePerson.target_calories} kcal / {activePerson.target_protein}g protein daily
                </div>
              )}
            </section>
          )}

          {/* Summary */}
          <section className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
            <SummaryStat label="Healthy Score" value={`${s.healthy_score}`} unit="/100" tone="success" />
            <SummaryStat label="Daily Calories" value={(activePerson?.target_calories || s.avg_calories).toLocaleString()} unit="kcal" tone="primary" />
            <SummaryStat label="Daily Protein" value={`${activePerson?.target_protein || s.avg_protein}g`} tone="accent" />
            <SummaryStat label="Est. Grocery Cost" value={`₹${s.total_budget.toLocaleString()}`} tone="warning" />
          </section>

          {/* Days */}
          <section className="space-y-3">
            {displayDays.map((d) => {
              const open = openDay === d.day;
              const proteinPct = Math.min(100, (d.protein / 180) * 100);
              const calPct = Math.min(100, (d.calories / 2500) * 100);
              return (
                <article key={d.day} className="rounded-2xl border border-border bg-surface shadow-soft overflow-hidden">
                  <button onClick={() => setOpenDay(open ? null : d.day)} className="w-full p-5 flex items-center gap-4 text-left hover:bg-muted/30 transition">
                    <div className="relative size-12 shrink-0">
                      <svg viewBox="0 0 36 36" className="size-12">
                        <circle cx="18" cy="18" r="15.5" fill="none" stroke="var(--border)" strokeWidth="3" />
                        <circle cx="18" cy="18" r="15.5" fill="none" stroke="var(--primary)" strokeWidth="3"
                          strokeDasharray={`${(calPct * 97) / 100} 97`} strokeLinecap="round" transform="rotate(-90 18 18)" />
                      </svg>
                      <div className="absolute inset-0 grid place-items-center text-[10px] font-semibold">{Math.round(calPct)}%</div>
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <h3 className="text-base font-semibold">{d.day}</h3>
                        <Badge status={d.status || "planned"} />
                      </div>
                      <div className="text-xs text-text-secondary mt-0.5">{d.calories} kcal · {d.protein}g protein · {d.meals.length} meals</div>
                      <div className="mt-2 h-1 rounded-full bg-muted overflow-hidden">
                        <div className="h-full bg-success" style={{ width: `${proteinPct}%` }} />
                      </div>
                    </div>
                    {open ? <ChevronUp className="size-4 text-text-light" /> : <ChevronDown className="size-4 text-text-light" />}
                  </button>
                  <div className={"grid transition-all duration-300 " + (open ? "grid-rows-[1fr]" : "grid-rows-[0fr]")}>
                    <div className="overflow-hidden">
                      <div className="px-5 pb-5 grid sm:grid-cols-2 gap-3 border-t border-border pt-4">
                        {"portion_note" in d && d.portion_note && (
                          <div className="sm:col-span-2 rounded-xl border border-primary/20 bg-primary-light/40 px-4 py-3 text-sm text-text-secondary flex items-start justify-between gap-3">
                            <span>{d.portion_note}</span>
                            {activePerson && (
                              <button
                                onClick={() => changePersonDay(d.day)}
                                disabled={regeneratingDay === `${activePerson.person_id}:${d.day}`}
                                className="shrink-0 inline-flex items-center gap-1.5 rounded-lg border border-primary/25 bg-surface px-3 py-1.5 text-xs font-medium text-primary hover:bg-primary-light disabled:opacity-60 transition"
                              >
                                {regeneratingDay === `${activePerson.person_id}:${d.day}` ? <Loader2 className="size-3 animate-spin" /> : <Sparkles className="size-3" />}
                                Change this day
                              </button>
                            )}
                          </div>
                        )}
                        {d.meals.map((m, idx) => (
                          <div key={idx} className="rounded-xl border border-border p-4 hover:shadow-elevated hover:-translate-y-0.5 transition">
                            <div className="flex items-center justify-between">
                              <span className="text-[11px] uppercase tracking-wider text-primary font-semibold">{m.type}</span>
                              <span className="text-[11px] text-text-light inline-flex items-center gap-1"><Clock className="size-3" />{m.prep_time ?? 10}m</span>
                            </div>
                            <div className="mt-2 text-sm font-medium leading-snug">{m.name}</div>
                            <div className="mt-3 flex items-center gap-3 text-xs text-text-secondary">
                              <span className="inline-flex items-center gap-1"><Flame className="size-3 text-warning" />{m.calories} kcal</span>
                              <span>·</span>
                              <span>{m.protein}g protein</span>
                            </div>
                            {recipesUnlocked && (
                              <button onClick={() => openRecipe(m)} className="mt-4 inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-xs font-medium text-text-secondary hover:text-primary hover:border-primary/30 transition">
                                <BookOpen className="size-3.5" /> Recipe
                              </button>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </article>
              );
            })}
          </section>

          <section className="rounded-2xl border border-border bg-primary-light/40 p-6 flex flex-wrap items-center justify-between gap-4">
            <div>
              <h3 className="font-semibold">Ready to shop?</h3>
              <p className="text-sm text-text-secondary mt-0.5">Your grocery list is grouped and ready to print or export.</p>
            </div>
            <Link to="/grocery" className="inline-flex items-center gap-2 rounded-lg bg-primary text-primary-foreground px-4 py-2.5 text-sm font-medium hover:opacity-90 transition">
              Open grocery list <ArrowRight className="size-4" />
            </Link>
          </section>
        </>
      )}

      {(recipeLoading || recipe) && (
        <div className="fixed inset-0 z-50 bg-black/30 backdrop-blur-sm grid place-items-center p-4">
          <div className="w-full max-w-2xl max-h-[85vh] overflow-auto rounded-2xl border border-border bg-surface shadow-elevated p-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="text-[11px] uppercase tracking-wider text-primary font-semibold">Recipe</div>
                <h2 className="mt-1 text-xl font-semibold">{recipe?.title || "Finding recipe..."}</h2>
                {recipe && <p className="mt-1 text-sm text-text-secondary">{recipe.servings} servings · {recipe.prep_time || "Prep"} · {recipe.cook_time || "Cook"}</p>}
              </div>
              <button onClick={() => { setRecipe(null); setRecipeLoading(false); }} className="rounded-lg border border-border p-2 hover:bg-muted transition">
                <X className="size-4" />
              </button>
            </div>
            {recipeLoading && <div className="mt-6 flex items-center gap-2 text-sm text-text-secondary"><Loader2 className="size-4 animate-spin" /> Searching online and building recipe...</div>}
            {recipe && (
              <div className="mt-5 grid gap-5">
                <section>
                  <h3 className="text-sm font-semibold">Ingredients</h3>
                  <ul className="mt-2 space-y-1.5 text-sm text-text-secondary">
                    {recipe.ingredients.map((item, i) => <li key={i}>• {item}</li>)}
                  </ul>
                </section>
                <section>
                  <h3 className="text-sm font-semibold">Steps</h3>
                  <ol className="mt-2 space-y-2 text-sm text-text-secondary">
                    {recipe.steps.map((step, i) => <li key={i}>{i + 1}. {step}</li>)}
                  </ol>
                </section>
                {recipe.nutrition_note && <p className="rounded-xl bg-primary-light/50 p-3 text-sm text-text-secondary">{recipe.nutrition_note}</p>}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function SummaryStat({ label, value, unit, tone }: { label: string; value: string; unit?: string; tone: "primary"|"accent"|"warning"|"success" }) {
  const tones: Record<string, string> = {
    primary: "from-indigo-500/10 to-violet-500/10",
    accent: "from-cyan-500/10 to-sky-500/10",
    warning: "from-amber-500/10 to-orange-500/10",
    success: "from-emerald-500/10 to-teal-500/10",
  };
  return (
    <div className={`rounded-xl border border-border bg-gradient-to-br ${tones[tone]} bg-surface p-4 shadow-soft`}>
      <div className="text-xs text-text-secondary font-medium">{label}</div>
      <div className="mt-1.5 text-2xl font-semibold tracking-tight">
        {value}{unit && <span className="text-sm font-normal text-text-light ml-1">{unit}</span>}
      </div>
    </div>
  );
}

function Badge({ status }: { status: string }) {
  const map: Record<string, string> = {
    completed: "bg-success/10 text-success",
    active: "bg-primary-light text-primary",
    planned: "bg-muted text-text-secondary",
    approved: "bg-success/10 text-success",
  };
  return <span className={`text-[10px] font-medium uppercase tracking-wider px-2 py-0.5 rounded-full ${map[status] || map.planned}`}>{status}</span>;
}

function SkeletonPage() {
  return (
    <div className="space-y-6">
      <div className="h-8 w-64 skeleton rounded-md" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-24 skeleton rounded-xl" />)}
      </div>
      {Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-20 skeleton rounded-2xl" />)}
    </div>
  );
}
