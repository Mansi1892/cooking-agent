import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
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
const DIET_OPTIONS = ["Vegetarian", "Eggetarian", "Vegan", "Non-vegetarian", "Pescatarian", "Keto"];

function Onboarding() {
  const navigate = useNavigate();
  const authUser = storage.getAuthUser<{ email?: string; name?: string }>();
  const [step, setStep] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [checkingExisting, setCheckingExisting] = useState(true);
  const [userId, setUserId] = useState<string>("");

  const [form, setForm] = useState<OnboardPayload>({
    name: authUser?.name || "",
    age: 28,
    gender: "",
    weight: 70,
    height: 170,
    weekly_budget: 2500,
    telegram: "",
    goal: "maintenance",
    dietary_preference: "Vegetarian",
    allergies: [],
    preferences: [],
    family: [],
  });

  const update = (patch: Partial<OnboardPayload>) => setForm((f) => ({ ...f, ...patch }));
  const personalErrors = validatePersonal(form);
  const familyErrors = validateFamily(form.family ?? []);

  const canNext =
    step === 0 ? Object.keys(personalErrors).length === 0 :
    step === 1 ? Object.keys(familyErrors).length === 0 :
    step === 2 ? true : false;

  useEffect(() => {
    let cancelled = false;
    async function restoreExistingProfile() {
      const storedAuthUser = storage.getAuthUser<{ email?: string; name?: string }>();
      const email = storedAuthUser?.email?.trim().toLowerCase();
      if (!email) {
        setCheckingExisting(false);
        return;
      }

      try {
        const result = await api.getProfileByEmail(email);
        if (cancelled) return;
        const profile = result.profile;
        if (profile?.id) {
          restoreProfile(profile, storedAuthUser);
          toast.success("Profile already exists", { description: "Opening your saved meal planner profile." });
          navigate({ to: "/" });
          return;
        }
      } catch {
        // No saved profile for this email yet, so onboarding should continue.
      }
      if (!cancelled) setCheckingExisting(false);
    }

    restoreExistingProfile();
    return () => {
      cancelled = true;
    };
  }, [navigate]);

  async function submit() {
    const errors = validatePersonal(form);
    if (Object.keys(errors).length > 0) {
      toast.error("Please fix profile details", { description: Object.values(errors)[0] });
      return;
    }
    const memberErrors = validateFamily(form.family ?? []);
    if (Object.keys(memberErrors).length > 0) {
      toast.error("Please fix family members", { description: Object.values(memberErrors)[0] });
      return;
    }
    setSubmitting(true);
    try {
      const authUser = storage.getAuthUser<{ email?: string; name?: string }>();
      const payload = { ...form, email: authUser?.email || form.email || "" };
      const r = await api.onboard(payload);
      const id = r.user_id;
      const currentAuthUser = storage.getAuthUser();
      storage.clearAll();
      storage.setAuthUser(currentAuthUser || {
        name: form.name,
        email: payload.email || "",
        logged_in_at: new Date().toISOString(),
      });
      storage.setCredits(typeof r?.credits === "number" ? r.credits : 3);
      storage.setRole(r?.role || "user");
      setUserId(id);
      storage.setUserId(id);
      storage.setUserName(form.name);
      storage.setGoal(form.goal);
      if (form.telegram) storage.setTelegram(form.telegram);
      storage.setProfile(payload);
      setStep(3);
    } catch (error) {
      toast.error("Profile was not created", { description: error instanceof Error ? error.message : "Please try again." });
    } finally {
      setSubmitting(false);
    }
  }

  if (checkingExisting) {
    return (
      <div className="min-h-screen grid place-items-center bg-background">
        <div className="text-center">
          <div className="mx-auto size-10 rounded-xl bg-primary-light text-primary grid place-items-center">
            <Sparkles className="size-5 animate-pulse" />
          </div>
          <div className="mt-4 text-sm font-medium">Checking your saved profile...</div>
        </div>
      </div>
    );
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
          {step === 3 && <StepSuccess onContinue={() => navigate({ to: "/" })} />}

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

function restoreProfile(profile: any, authUser?: { email?: string; name?: string } | null) {
  const email = profile.email || authUser?.email || "";
  const name = profile.name || authUser?.name || email.split("@")[0] || "Guest";
  storage.setAuthUser({
    name,
    email,
    logged_in_at: new Date().toISOString(),
  });
  storage.setUserId(String(profile.id));
  storage.setUserName(name);
  storage.setGoal(profile.goal || "maintenance");
  storage.setCredits(Number(profile.credits ?? 3));
  storage.setRole(profile.role || "user");
  storage.setTelegram(profile.telegram_id || "");
  storage.setProfile({
    name,
    email,
    age: profile.age,
    gender: profile.gender || "",
    weight: profile.weight_kg,
    height: profile.height_cm,
    weekly_budget: profile.budget_weekly,
    telegram: profile.telegram_id,
    goal: profile.goal,
    dietary_preference: profile.dietary_type,
    allergies: profile.allergies || [],
    preferences: profile.preferences || [],
  });
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

function cleanNumber(value: string) {
  const cleaned = value.replace(/^0+(?=\d)/, "");
  return cleaned === "" ? 0 : Number(cleaned);
}

function validatePersonal(form: OnboardPayload) {
  const errors: Record<string, string> = {};
  if (!form.name?.trim()) errors.name = "Full name is required.";
  if (!form.goal) errors.goal = "Goal is required.";
  if (!form.dietary_preference) errors.dietary_preference = "Dietary preference is required.";
  if (!Number.isFinite(Number(form.age)) || form.age < 1 || form.age > 120) errors.age = "Enter a valid age.";
  if (!Number.isFinite(Number(form.weight)) || form.weight < 20 || form.weight > 300) errors.weight = "Enter a valid weight.";
  if (!Number.isFinite(Number(form.height)) || form.height < 80 || form.height > 250) errors.height = "Enter a valid height.";
  if (Number(form.weekly_budget || 0) < 1500) errors.weekly_budget = "Budget is too low. Please enter at least ₹1500.";
  return errors;
}

function validateFamily(family: FamilyMember[]) {
  const errors: Record<number, string> = {};
  family.forEach((member, index) => {
    if (!member.name?.trim()) errors[index] = "Family member name is required. Delete this row if you do not want to add them.";
    if (!member.diet) errors[index] = "Dietary preference is required.";
    if (!member.goal) errors[index] = "Goal is required for each family member.";
    if (member.age && (member.age < 1 || member.age > 120)) errors[index] = "Enter a valid age for each family member.";
    const weight = Number(member.weight ?? member.weight_kg ?? 0);
    const height = Number(member.height ?? member.height_cm ?? 0);
    if (weight && (weight < 20 || weight > 300)) errors[index] = "Enter a valid weight for each family member.";
    if (height && (height < 80 || height > 250)) errors[index] = "Enter a valid height for each family member.";
  });
  return errors;
}

function ErrorText({ children }: { children: React.ReactNode }) {
  return <div className="text-[11px] text-destructive mt-1">{children}</div>;
}

function StepPersonal({ form, update }: { form: OnboardPayload; update: (p: Partial<OnboardPayload>) => void }) {
  const errors = validatePersonal(form);
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
          {errors.name && <ErrorText>{errors.name}</ErrorText>}
        </Field>
        <Field label="Age">
          <input type="number" className={input()} value={form.age || ""} onChange={(e) => update({ age: cleanNumber(e.target.value) })} />
          {errors.age && <ErrorText>{errors.age}</ErrorText>}
        </Field>
        <Field label="Gender">
          <select className={input()} value={form.gender ?? ""} onChange={(e) => update({ gender: e.target.value })}>
            <option value="">Prefer not to say</option>
            <option value="female">Female</option>
            <option value="male">Male</option>
            <option value="other">Other</option>
          </select>
        </Field>
        <Field label="Weight (kg)">
          <input type="number" className={input()} value={form.weight || ""} onChange={(e) => update({ weight: cleanNumber(e.target.value) })} />
          {errors.weight && <ErrorText>{errors.weight}</ErrorText>}
        </Field>
        <Field label="Height (cm)">
          <input type="number" className={input()} value={form.height || ""} onChange={(e) => update({ height: cleanNumber(e.target.value) })} />
          {errors.height && <ErrorText>{errors.height}</ErrorText>}
        </Field>
        <Field label="Weekly meal budget (INR)" hint="Minimum ₹1500. ₹2500 is a good starting weekly budget.">
          <input type="number" min={1500} step={100} className={input()} value={form.weekly_budget || ""} onChange={(e) => update({ weekly_budget: cleanNumber(e.target.value) })} />
          {errors.weekly_budget && <ErrorText>{errors.weekly_budget}</ErrorText>}
        </Field>
        <Field label="Telegram chat ID (optional)" hint="Open the bot and send /start to get this number">
          <input className={input()} value={form.telegram} onChange={(e) => update({ telegram: e.target.value })} placeholder="123456789" />
        </Field>
      </div>

      <div className="mt-8 grid sm:grid-cols-2 gap-4">
        <Field label="Dietary preference">
          <select className={input()} value={form.dietary_preference ?? "Vegetarian"} onChange={(e) => update({ dietary_preference: e.target.value })}>
            <option value="Vegetarian">Vegetarian</option>
            <option value="Eggetarian">Eggetarian</option>
            <option value="Vegan">Vegan</option>
            <option value="Non-vegetarian">Non-vegetarian</option>
            <option value="Pescatarian">Pescatarian</option>
            <option value="Keto">Keto</option>
          </select>
          {errors.dietary_preference && <ErrorText>{errors.dietary_preference}</ErrorText>}
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
  const errors = validateFamily(family);

  const add = () => update({ family: [...family, { name: "", age: 28, goal: "maintenance", gender: "", weight: 60, height: 165, diet: "Vegetarian", allergies: [], preferences: [], telegram: "" }] });
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
                  {errors[i] && <ErrorText>{errors[i]}</ErrorText>}
                </Field>
                <Field label="Diet">
                  <select className={input()} value={m.diet} onChange={(e) => patch(i, { diet: e.target.value })}>
                    {DIET_OPTIONS.map((diet) => <option key={diet}>{diet}</option>)}
                  </select>
                </Field>
                <Field label="Goal">
                  <select className={input()} value={m.goal ?? "maintenance"} onChange={(e) => patch(i, { goal: e.target.value as FamilyMember["goal"] })}>
                    <option value="weight_loss">Weight Loss</option>
                    <option value="muscle_gain">Muscle Gain</option>
                    <option value="maintenance">Maintenance</option>
                  </select>
                </Field>
                <Field label="Gender">
                  <select className={input()} value={m.gender ?? ""} onChange={(e) => patch(i, { gender: e.target.value })}>
                    <option value="">Prefer not to say</option>
                    <option value="female">Female</option>
                    <option value="male">Male</option>
                    <option value="other">Other</option>
                  </select>
                </Field>
                <Field label="Age">
                  <input className={input()} type="number" value={m.age ?? 0} onChange={(e) => patch(i, { age: cleanNumber(e.target.value) })} />
                </Field>
                <Field label="Weight (kg)">
                  <input className={input()} type="number" value={m.weight ?? m.weight_kg ?? 0} onChange={(e) => patch(i, { weight: cleanNumber(e.target.value) })} />
                </Field>
                <Field label="Height (cm)">
                  <input className={input()} type="number" value={m.height ?? m.height_cm ?? 0} onChange={(e) => patch(i, { height: cleanNumber(e.target.value) })} />
                </Field>
                <Field label="Allergies (comma separated)">
                  <input className={input()} value={(m.allergies ?? []).join(", ")} onChange={(e) => patch(i, { allergies: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })} placeholder="peanuts, shellfish" />
                </Field>
                <Field label="Preferences">
                  <input className={input()} value={(m.preferences ?? []).join(", ")} onChange={(e) => patch(i, { preferences: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })} placeholder="spicy, mediterranean" />
                </Field>
                <Field label="Telegram chat ID (optional)">
                  <input className={input()} value={m.telegram ?? ""} onChange={(e) => patch(i, { telegram: e.target.value })} placeholder="123456789" />
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
  const family = (form.family ?? []).filter((member) => member.name?.trim());
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
            <Row k="Weekly budget" v={`₹${form.weekly_budget}`} />
            {form.telegram && <Row k="Telegram" v={form.telegram} />}
          </dl>
        </section>

        <section className="rounded-xl border border-border bg-surface p-5">
          <div className="flex items-center justify-between">
            <div className="text-sm font-semibold">Family</div>
            <div className="text-[11px] uppercase tracking-wider text-text-light font-medium">Step 2</div>
          </div>
          {family.length === 0 ? (
            <div className="text-sm text-text-light mt-3">No additional members.</div>
          ) : (
            <ul className="mt-4 space-y-2">
              {family.map((m, i) => (
                <li key={i} className="flex items-center gap-3 text-sm">
                  <span className="size-7 rounded-full bg-primary-light text-primary grid place-items-center text-[11px] font-semibold">
                    {m.name.slice(0, 1).toUpperCase()}
                  </span>
                  <span className="font-medium">{m.name}</span>
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

function StepSuccess({ onContinue }: { onContinue: () => void }) {
  return (
    <div className="text-center pt-6 animate-fade-up">
      <div className="mx-auto size-20 rounded-full bg-success/10 text-success grid place-items-center animate-pop-in">
        <Check className="size-10" strokeWidth={3} />
      </div>
      <h2 className="mt-6 text-2xl font-semibold tracking-tight">Profile generated successfully</h2>
      <p className="mt-1.5 text-sm text-text-secondary">Your profile is ready. Let's generate your first plan.</p>
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
