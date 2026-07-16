import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import {
  Sparkles, ArrowRight, ArrowLeft, Check, Plus, X, Target, TrendingUp, Minus,
  User as UserIcon, Heart,
} from "lucide-react";
import { api, type FamilyMember, type OnboardPayload } from "@/lib/api";
import { storage } from "@/lib/storage";
import { toast } from "sonner";

export const Route = createFileRoute("/onboarding")({
  component: Onboarding,
});

const STEPS = ["Personal", "Family", "Review", "Success"];

function Onboarding() {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [userId, setUserId] = useState<string>("");

  const [form, setForm] = useState<OnboardPayload>({
    name: "",
    age: 28,
    weight: 70,
    height: 170,
    weekly_budget: 80,
    telegram: "",
    goal: "maintenance",
    dietary_preference: "Vegetarian",
    allergies: [],
    preferences: [],
    family: [],
  });

  const update = (patch: Partial<OnboardPayload>) => setForm((f) => ({ ...f, ...patch }));

  const canNext =
    step === 0 ? form.name.trim().length > 1 && form.age > 0 && form.weight > 0 && form.height > 0 :
    step === 1 ? true :
    step === 2 ? true : false;

  async function submit() {
    setSubmitting(true);
    try {
      let id = "demo-user-" + Math.random().toString(36).slice(2, 8);
      try {
        const r = await api.onboard(form);
        if (r?.user_id) id = r.user_id;
      } catch {
        toast.message("Using demo mode", { description: "Backend unreachable — generated a local demo profile." });
      }
      setUserId(id);
      storage.setUserId(id);
      storage.setUserName(form.name);
      storage.setGoal(form.goal);
      if (form.telegram) storage.setTelegram(form.telegram);
      storage.setProfile(form);
      setStep(3);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen grid lg:grid-cols-[1fr_1.1fr]">
      {/* LEFT */}
      <div className="relative onboard-gradient text-white overflow-hidden hidden lg:flex flex-col p-12 xl:p-16">
        <div className="absolute -top-32 -left-32 size-96 rounded-full bg-white/10 blur-3xl" />
        <div className="absolute -bottom-40 -right-20 size-[28rem] rounded-full bg-white/10 blur-3xl" />
        <div className="relative flex items-center gap-2">
          <div className="size-9 rounded-xl bg-white/15 backdrop-blur grid place-items-center">
            <Sparkles className="size-4" />
          </div>
          <div className="font-semibold tracking-tight">Smart Meal AI</div>
        </div>
        <div className="relative mt-auto">
          <h1 className="text-5xl xl:text-6xl font-semibold tracking-tight leading-[1.05]">
            Plan Smarter.<br />Eat Better.<br />
            <span className="bg-gradient-to-r from-white to-white/60 bg-clip-text text-transparent">Powered by AI.</span>
          </h1>
          <p className="mt-6 text-white/80 max-w-md text-lg">
            Generate personalized meal plans in seconds — tuned to your goals, budget and family.
          </p>
          <div className="mt-10 grid grid-cols-3 gap-3 max-w-md">
            {["Personalized", "Budget-aware", "Family-ready"].map((t) => (
              <div key={t} className="rounded-xl bg-white/10 backdrop-blur border border-white/15 px-3 py-2.5 text-xs font-medium text-center">
                {t}
              </div>
            ))}
          </div>
        </div>
        <div className="relative mt-10 text-xs text-white/60">© Smart Meal AI</div>
      </div>

      {/* RIGHT */}
      <div className="flex flex-col bg-background">
        <div className="p-6 sm:p-10">
          <StepIndicator step={step} />
        </div>
        <div className="flex-1 px-6 sm:px-10 pb-16 max-w-2xl w-full mx-auto">
          {step === 0 && <StepPersonal form={form} update={update} />}
          {step === 1 && <StepFamily form={form} update={update} />}
          {step === 2 && <StepReview form={form} />}
          {step === 3 && <StepSuccess userId={userId} onContinue={() => navigate({ to: "/" })} />}

          {step < 3 && (
            <div className="mt-10 flex items-center justify-between">
              <button
                onClick={() => setStep((s) => Math.max(0, s - 1))}
                disabled={step === 0}
                className="inline-flex items-center gap-2 text-sm text-text-secondary disabled:opacity-40 hover:text-text-primary"
              >
                <ArrowLeft className="size-4" /> Back
              </button>
              {step < 2 ? (
                <button
                  onClick={() => setStep((s) => s + 1)}
                  disabled={!canNext}
                  className="inline-flex items-center gap-2 rounded-lg bg-primary text-primary-foreground px-5 py-2.5 text-sm font-medium hover:opacity-90 transition disabled:opacity-50"
                >
                  Continue <ArrowRight className="size-4" />
                </button>
              ) : (
                <button
                  onClick={submit}
                  disabled={submitting}
                  className="inline-flex items-center gap-2 rounded-lg bg-primary text-primary-foreground px-5 py-2.5 text-sm font-medium hover:opacity-90 transition disabled:opacity-60"
                >
                  {submitting ? "Creating…" : "Create profile"} <Check className="size-4" />
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function StepIndicator({ step }: { step: number }) {
  return (
    <div className="flex items-center gap-3">
      {STEPS.map((label, i) => {
        const active = i === step;
        const done = i < step;
        return (
          <div key={label} className="flex items-center gap-3">
            <div className={[
              "size-7 rounded-full grid place-items-center text-[11px] font-semibold transition",
              done ? "bg-primary text-primary-foreground" :
              active ? "bg-primary-light text-primary ring-4 ring-primary/10" :
              "bg-muted text-text-light",
            ].join(" ")}>
              {done ? <Check className="size-3.5" /> : i + 1}
            </div>
            <span className={"text-xs font-medium hidden sm:inline " + (active ? "text-text-primary" : "text-text-light")}>{label}</span>
            {i < STEPS.length - 1 && <div className="w-6 sm:w-10 h-px bg-border" />}
          </div>
        );
      })}
    </div>
  );
}

function Field({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <label className="block">
      <div className="text-xs font-medium text-text-secondary mb-1.5">{label}</div>
      {children}
      {hint && <div className="text-[11px] text-text-light mt-1">{hint}</div>}
    </label>
  );
}

function input(extra = "") {
  return "w-full rounded-lg border border-border bg-surface px-3.5 py-2.5 text-sm placeholder:text-text-light focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/40 transition " + extra;
}

function StepPersonal({ form, update }: { form: OnboardPayload; update: (p: Partial<OnboardPayload>) => void }) {
  const goals = [
    { id: "weight_loss", title: "Weight Loss", desc: "Lean, sustainable calorie deficit", icon: Minus },
    { id: "muscle_gain", title: "Muscle Gain", desc: "High-protein, surplus calories", icon: TrendingUp },
    { id: "maintenance", title: "Maintenance", desc: "Balanced, steady nutrition", icon: Target },
  ] as const;
  return (
    <div className="animate-fade-up">
      <h2 className="text-2xl font-semibold tracking-tight">Tell us about you</h2>
      <p className="mt-1 text-sm text-text-secondary">We'll use this to tune your weekly plans.</p>

      <div className="mt-7 grid sm:grid-cols-2 gap-4">
        <Field label="Full name">
          <input className={input()} value={form.name} onChange={(e) => update({ name: e.target.value })} placeholder="Mansi Sharma" />
        </Field>
        <Field label="Age">
          <input type="number" className={input()} value={form.age} onChange={(e) => update({ age: Number(e.target.value) })} />
        </Field>
        <Field label="Weight (kg)">
          <input type="number" className={input()} value={form.weight} onChange={(e) => update({ weight: Number(e.target.value) })} />
        </Field>
        <Field label="Height (cm)">
          <input type="number" className={input()} value={form.height} onChange={(e) => update({ height: Number(e.target.value) })} />
        </Field>
        <Field label="Weekly grocery budget (USD)">
          <input type="number" className={input()} value={form.weekly_budget} onChange={(e) => update({ weekly_budget: Number(e.target.value) })} />
        </Field>
        <Field label="Telegram (optional)" hint="For daily plan reminders">
          <input className={input()} value={form.telegram} onChange={(e) => update({ telegram: e.target.value })} placeholder="@username" />
        </Field>
      </div>

      <div className="mt-8 grid sm:grid-cols-2 gap-4">
        <Field label="Dietary preference">
          <select className={input()} value={form.dietary_preference ?? "Vegetarian"} onChange={(e) => update({ dietary_preference: e.target.value })}>
            <option value="Vegetarian">Vegetarian</option>
            <option value="Vegan">Vegan</option>
            <option value="Non-vegetarian">Non-vegetarian</option>
            <option value="Pescatarian">Pescatarian</option>
          </select>
        </Field>
        <Field label="Allergies (comma separated)">
          <input className={input()} value={(form.allergies ?? []).join(", ")} onChange={(e) => update({ allergies: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })} placeholder="peanuts, shellfish" />
        </Field>
        <Field label="Preferences">
          <input className={input()} value={(form.preferences ?? []).join(", ")} onChange={(e) => update({ preferences: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })} placeholder="spicy, mediterranean" />
        </Field>
      </div>

      <div className="mt-4">
        <div className="text-xs font-medium text-text-secondary mb-3">Your goal</div>
        <div className="grid sm:grid-cols-3 gap-3">
          {goals.map((g) => {
            const active = form.goal === g.id;
            const Icon = g.icon;
            return (
              <button
                key={g.id}
                onClick={() => update({ goal: g.id })}
                className={[
                  "text-left rounded-xl border p-4 transition-all duration-200",
                  active
                    ? "border-primary bg-primary-light/60 ring-4 ring-primary/10 scale-[1.02]"
                    : "border-border bg-surface hover:border-primary/40 hover:-translate-y-0.5 hover:shadow-soft",
                ].join(" ")}
              >
                <div className={"size-9 rounded-lg grid place-items-center " + (active ? "bg-primary text-white" : "bg-muted text-text-secondary")}>
                  <Icon className="size-4" />
                </div>
                <div className="mt-3 text-sm font-semibold">{g.title}</div>
                <div className="text-xs text-text-secondary mt-0.5">{g.desc}</div>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function StepFamily({ form, update }: { form: OnboardPayload; update: (p: Partial<OnboardPayload>) => void }) {
  const family = form.family ?? [];

  const add = () => update({ family: [...family, { name: "", diet: "Omnivore", allergies: [], preferences: [], telegram: "" }] });
  const remove = (i: number) => update({ family: family.filter((_, idx) => idx !== i) });
  const patch = (i: number, p: Partial<FamilyMember>) =>
    update({ family: family.map((m, idx) => (idx === i ? { ...m, ...p } : m)) });

  return (
    <div className="animate-fade-up">
      <h2 className="text-2xl font-semibold tracking-tight">Family members</h2>
      <p className="mt-1 text-sm text-text-secondary">Add anyone else you cook for. You can skip this step.</p>

      <div className="mt-7 space-y-3">
        {family.length === 0 && (
          <div className="rounded-xl border border-dashed border-border p-8 text-center">
            <div className="mx-auto size-10 rounded-full bg-primary-light text-primary grid place-items-center">
              <UserIcon className="size-5" />
            </div>
            <div className="mt-3 text-sm font-medium">No family members yet</div>
            <div className="text-xs text-text-light mt-1">Add anyone you'd like included in plans.</div>
          </div>
        )}
        {family.map((m, i) => (
          <div key={i} className="rounded-xl border border-border bg-surface p-4 shadow-soft animate-fade-up">
            <div className="flex items-start justify-between gap-3">
              <div className="grid sm:grid-cols-2 gap-3 flex-1">
                <Field label="Name">
                  <input className={input()} value={m.name} onChange={(e) => patch(i, { name: e.target.value })} placeholder="e.g. Priya" />
                </Field>
                <Field label="Diet">
                  <select className={input()} value={m.diet} onChange={(e) => patch(i, { diet: e.target.value })}>
                    <option>Omnivore</option><option>Vegetarian</option><option>Vegan</option><option>Pescatarian</option><option>Keto</option>
                  </select>
                </Field>
                <Field label="Allergies (comma separated)">
                  <input className={input()} value={(m.allergies ?? []).join(", ")} onChange={(e) => patch(i, { allergies: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })} placeholder="peanuts, shellfish" />
                </Field>
                <Field label="Preferences">
                  <input className={input()} value={(m.preferences ?? []).join(", ")} onChange={(e) => patch(i, { preferences: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })} placeholder="spicy, mediterranean" />
                </Field>
                <Field label="Telegram (optional)">
                  <input className={input()} value={m.telegram ?? ""} onChange={(e) => patch(i, { telegram: e.target.value })} placeholder="@username" />
                </Field>
              </div>
              <button onClick={() => remove(i)} className="size-8 rounded-md hover:bg-muted text-text-light hover:text-destructive grid place-items-center transition">
                <X className="size-4" />
              </button>
            </div>
          </div>
        ))}
        <button onClick={add} className="w-full rounded-xl border border-dashed border-primary/30 text-primary hover:bg-primary-light/50 px-4 py-3 text-sm font-medium inline-flex items-center justify-center gap-2 transition">
          <Plus className="size-4" /> Add family member
        </button>
      </div>
    </div>
  );
}

function StepReview({ form }: { form: OnboardPayload }) {
  return (
    <div className="animate-fade-up">
      <h2 className="text-2xl font-semibold tracking-tight">Review</h2>
      <p className="mt-1 text-sm text-text-secondary">Everything look good?</p>

      <div className="mt-7 space-y-4">
        <section className="rounded-xl border border-border bg-surface p-5">
          <div className="flex items-center justify-between">
            <div className="text-sm font-semibold">Personal</div>
            <div className="text-[11px] uppercase tracking-wider text-text-light font-medium">Step 1</div>
          </div>
          <dl className="mt-4 grid sm:grid-cols-2 gap-3 text-sm">
            <Row k="Name" v={form.name} />
            <Row k="Age" v={String(form.age)} />
            <Row k="Weight" v={`${form.weight} kg`} />
            <Row k="Height" v={`${form.height} cm`} />
            <Row k="Goal" v={form.goal.replace("_", " ")} />
            <Row k="Dietary preference" v={form.dietary_preference || "Not set"} />
            <Row k="Allergies" v={(form.allergies ?? []).join(", ") || "None"} />
            <Row k="Preferences" v={(form.preferences ?? []).join(", ") || "None"} />
            <Row k="Weekly budget" v={`$${form.weekly_budget}`} />
            {form.telegram && <Row k="Telegram" v={form.telegram} />}
          </dl>
        </section>

        <section className="rounded-xl border border-border bg-surface p-5">
          <div className="flex items-center justify-between">
            <div className="text-sm font-semibold">Family</div>
            <div className="text-[11px] uppercase tracking-wider text-text-light font-medium">Step 2</div>
          </div>
          {!form.family || form.family.length === 0 ? (
            <div className="text-sm text-text-light mt-3">No additional members.</div>
          ) : (
            <ul className="mt-4 space-y-2">
              {form.family.map((m, i) => (
                <li key={i} className="flex items-center gap-3 text-sm">
                  <span className="size-7 rounded-full bg-primary-light text-primary grid place-items-center text-[11px] font-semibold">
                    {(m.name || "?").slice(0, 1).toUpperCase()}
                  </span>
                  <span className="font-medium">{m.name || "Unnamed"}</span>
                  <span className="text-text-light capitalize">· {m.diet}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex items-center justify-between border-b border-border last:border-0 pb-2 last:pb-0">
      <dt className="text-text-light">{k}</dt>
      <dd className="font-medium capitalize">{v}</dd>
    </div>
  );
}

function StepSuccess({ userId, onContinue }: { userId: string; onContinue: () => void }) {
  return (
    <div className="text-center pt-6 animate-fade-up">
      <div className="mx-auto size-20 rounded-full bg-success/10 text-success grid place-items-center animate-pop-in">
        <Check className="size-10" strokeWidth={3} />
      </div>
      <h2 className="mt-6 text-2xl font-semibold tracking-tight">You're all set</h2>
      <p className="mt-1.5 text-sm text-text-secondary">Your profile is ready. Let's generate your first plan.</p>
      <div className="mt-6 inline-flex items-center gap-2 rounded-lg border border-border bg-surface px-3.5 py-2 text-xs text-text-secondary">
        <span className="text-text-light">User ID</span>
        <code className="font-mono text-text-primary">{userId}</code>
      </div>
      <div className="mt-8">
        <button onClick={onContinue} className="inline-flex items-center gap-2 rounded-lg bg-primary text-primary-foreground px-5 py-2.5 text-sm font-medium hover:opacity-90 transition">
          Generate my first meal plan <Sparkles className="size-4" />
        </button>
      </div>
      <div className="mt-6 text-xs text-text-light inline-flex items-center gap-1.5">
        <Heart className="size-3 text-destructive" /> Made for you with care
      </div>
    </div>
  );
}
