import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import {
  Sparkles, ArrowRight, ArrowLeft, Check, Plus, X, Target, TrendingUp, Minus,
  User as UserIcon, Heart, MessageCircle, Send,
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
    age: 0,
    gender: "",
    weight: 0,
    height: 0,
    weekly_budget: 0,
    telegram: "",
    whatsapp: "",
    goal: "" as OnboardPayload["goal"],
    dietary_preference: "",
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
      if (storage.getResetOnboardingUserId()) {
        setCheckingExisting(false);
        return;
      }
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
      const resetUserId = storage.getResetOnboardingUserId();
      const payload = sanitizePayload({
        ...form,
        email: authUser?.email || form.email || "",
      });
      if (!payload.email?.trim()) {
        toast.error("Please login again", { description: "Your email session was missing, so the profile cannot be saved." });
        navigate({ to: "/login" });
        return;
      }
      const result = resetUserId
        ? await api.updateProfile(resetUserId, payload)
        : await api.onboard(payload);
      const id = resetUserId || ("user_id" in result ? result.user_id : String(result.profile?.id || ""));
      const currentAuthUser = storage.getAuthUser();
      const currentCredits = storage.getCredits();
      const currentRole = storage.getRole();
      const updatedProfile = "profile" in result ? result.profile : null;
      storage.clearAll();
      storage.setAuthUser({
        ...(currentAuthUser || {}),
        name: form.name,
        email: payload.email || "",
        logged_in_at: new Date().toISOString(),
      });
      storage.setCredits(Number(updatedProfile?.credits ?? ("credits" in result ? result.credits : currentCredits)));
      storage.setRole(updatedProfile?.role || ("role" in result ? result.role : currentRole));
      setUserId(id);
      storage.setUserId(id);
      storage.setUserName(updatedProfile?.name || form.name);
      storage.setGoal(updatedProfile?.goal || form.goal);
      if (payload.telegram) storage.setTelegram(payload.telegram);
      if (payload.whatsapp) storage.setWhatsapp(payload.whatsapp);
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
  storage.setWhatsapp(profile.whatsapp_number || "");
  storage.setProfile({
    name,
    email,
    age: profile.age,
    gender: profile.gender || "",
    weight: profile.weight_kg,
    height: profile.height_cm,
    weekly_budget: profile.budget_weekly,
    telegram: profile.telegram_id,
    whatsapp: profile.whatsapp_number,
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

function connectButtonClass() {
  return "shrink-0 inline-flex items-center gap-2 rounded-lg bg-primary text-primary-foreground px-3 py-2 text-sm font-medium hover:opacity-90 transition shadow-soft disabled:opacity-50 disabled:cursor-not-allowed";
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

async function sendContactTest(channel: "Telegram" | "WhatsApp", value?: string, telegramValue?: string) {
  const cleanValue = channel === "WhatsApp"
    ? String(value || "").replace(/\D/g, "")
    : String(value || "").trim();
  if (!cleanValue) {
    toast.error(`${channel} value missing`, {
      description: channel === "Telegram"
        ? "Paste the Telegram chat ID first."
        : "Paste the WhatsApp number with country code first.",
    });
    return false;
  }
  if (channel === "WhatsApp") {
    const cleanTelegram = String(telegramValue || "").replace(/\D/g, "");
    if (cleanTelegram && cleanValue === cleanTelegram) {
      toast.error("Use WhatsApp number here", {
        description: "This looks like the Telegram chat ID. Enter the WhatsApp number with country code, for example 919876543210.",
      });
      return false;
    }
  }
  try {
    if (channel === "Telegram") await api.testTelegramContact(cleanValue);
    else await api.testWhatsappContact(cleanValue);
    toast.success(`${channel} connected`, { description: "A test message was sent." });
    return true;
  } catch (error) {
    toast.error(`${channel} connection failed`, {
      description: error instanceof Error ? error.message : "Please check the value and try again.",
    });
    return false;
  }
}

async function openTelegramBot() {
  try {
    const result = await api.getTelegramBotLink();
    window.open(result.url, "_blank", "noopener,noreferrer");
    toast.success("Telegram bot opened", { description: "Tap Start, copy the chat ID, then paste it here." });
  } catch (error) {
    toast.error("Could not open bot", { description: error instanceof Error ? error.message : "Please check Telegram bot setup." });
  }
}

async function copyTelegramInvite(name?: string) {
  const person = name?.trim() || "there";
  const message = `Hi ${person}, please connect Telegram for Smart Meal AI:\n\n1. Open this bot link:\nhttps://t.me/cooking_agent_1892_bot\n\n2. Tap Start or send /start\n\n3. The bot will reply with a Telegram chat ID.\n\n4. Send that chat ID back to me.\n\nI will add it to your Smart Meal AI family profile so you can approve/reject your own meal plan.`;
  try {
    await navigator.clipboard.writeText(message);
    toast.success("Invite copied", { description: "Send it to the family member." });
  } catch {
    toast.error("Could not copy invite");
  }
}

function StepPersonal({ form, update }: { form: OnboardPayload; update: (p: Partial<OnboardPayload>) => void }) {
  const errors = validatePersonal(form);
  const [allergiesText, setAllergiesText] = useState((form.allergies ?? []).join(", "));
  const [preferencesText, setPreferencesText] = useState((form.preferences ?? []).join(", "));
  const [connecting, setConnecting] = useState<"" | "telegram" | "whatsapp">("");
  async function connect(channel: "Telegram" | "WhatsApp", value?: string) {
    setConnecting(channel.toLowerCase() as "telegram" | "whatsapp");
    try {
      await sendContactTest(channel, value, form.telegram);
    } finally {
      setConnecting("");
    }
  }
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
          <input className={input()} value={form.name} onChange={(e) => update({ name: e.target.value })} placeholder="Enter full name" />
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
        <Field label="Telegram chat ID (optional)" hint="Enter the Telegram chat ID, then use Send test to verify it.">
          <div className="flex gap-2">
            <input className={input()} value={form.telegram} onChange={(e) => update({ telegram: e.target.value.replace(/[^\d-]/g, "") })} placeholder="e.g. 8892259333" />
            <button type="button" onClick={() => connect("Telegram", form.telegram)} disabled={connecting !== ""} className={connectButtonClass()}>
              <Send className="size-4" /> {connecting === "telegram" ? "Sending" : "Send test"}
            </button>
          </div>
          <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-text-light">
            <button type="button" onClick={openTelegramBot} className="text-primary font-medium hover:underline">Open bot</button>
            <span>Tap Start or send /start. The bot replies with your chat ID; paste that number here.</span>
          </div>
        </Field>
        <Field label="WhatsApp number (optional)" hint="Use country code, no +. Example: 919876543210">
          <input className={input()} value={form.whatsapp ?? ""} onChange={(e) => update({ whatsapp: e.target.value.replace(/\D/g, "") })} placeholder="Optional" />
          <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-warning">
            <span className="inline-flex items-center gap-1 rounded-md border border-warning/30 bg-warning/10 px-2 py-1 font-medium"><MessageCircle className="size-3" /> Coming soon</span>
            <span>You can save the number now; WhatsApp approvals will be enabled later.</span>
          </div>
        </Field>
      </div>

      <div className="mt-8 grid sm:grid-cols-2 gap-4">
        <Field label="Dietary preference">
          <select className={input()} value={form.dietary_preference ?? ""} onChange={(e) => update({ dietary_preference: e.target.value })}>
            <option value="">Select dietary preference</option>
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
          <input
            className={input()}
            value={allergiesText}
            onChange={(e) => {
              setAllergiesText(e.target.value);
              update({ allergies: splitList(e.target.value) });
            }}
            placeholder="Optional"
          />
        </Field>
        <Field label="Preferences">
          <input
            className={input()}
            value={preferencesText}
            onChange={(e) => {
              setPreferencesText(e.target.value);
              update({ preferences: splitList(e.target.value) });
            }}
            placeholder="Optional"
          />
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
  const [connecting, setConnecting] = useState("");

  const add = () => update({ family: [...family, { name: "", age: 0, goal: "" as FamilyMember["goal"], gender: "", weight: 0, height: 0, diet: "", allergies: [], preferences: [], telegram: "", whatsapp: "" }] });
  const remove = (i: number) => update({ family: family.filter((_, idx) => idx !== i) });
  const patch = (i: number, p: Partial<FamilyMember>) =>
    update({ family: family.map((m, idx) => (idx === i ? { ...m, ...p } : m)) });
  async function connect(channel: "Telegram" | "WhatsApp", value: string | undefined, key: string, telegramValue?: string) {
    setConnecting(key);
    try {
      await sendContactTest(channel, value, telegramValue || form.telegram);
    } finally {
      setConnecting("");
    }
  }

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
                  <select className={input()} value={m.diet ?? ""} onChange={(e) => patch(i, { diet: e.target.value })}>
                    <option value="">Select dietary preference</option>
                    {DIET_OPTIONS.map((diet) => <option key={diet}>{diet}</option>)}
                  </select>
                </Field>
                <Field label="Goal">
                  <select className={input()} value={m.goal ?? ""} onChange={(e) => patch(i, { goal: e.target.value as FamilyMember["goal"] })}>
                    <option value="">Select goal</option>
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
                  <input className={input()} type="number" value={m.age || ""} onChange={(e) => patch(i, { age: cleanNumber(e.target.value) })} />
                </Field>
                <Field label="Weight (kg)">
                  <input className={input()} type="number" value={(m.weight ?? m.weight_kg) || ""} onChange={(e) => patch(i, { weight: cleanNumber(e.target.value) })} />
                </Field>
                <Field label="Height (cm)">
                  <input className={input()} type="number" value={(m.height ?? m.height_cm) || ""} onChange={(e) => patch(i, { height: cleanNumber(e.target.value) })} />
                </Field>
                <Field label="Allergies (comma separated)">
                  <input className={input()} value={(m as any)._allergiesText ?? (m.allergies ?? []).join(", ")} onChange={(e) => patch(i, { allergies: splitList(e.target.value), _allergiesText: e.target.value } as any)} placeholder="Optional" />
                </Field>
                <Field label="Preferences">
                  <input className={input()} value={(m as any)._preferencesText ?? (m.preferences ?? []).join(", ")} onChange={(e) => patch(i, { preferences: splitList(e.target.value), _preferencesText: e.target.value } as any)} placeholder="Optional" />
                </Field>
                <Field label="Telegram chat ID (optional)">
                  <div className="flex gap-2">
                    <input className={input()} value={m.telegram ?? ""} onChange={(e) => patch(i, { telegram: e.target.value.replace(/[^\d-]/g, "") })} placeholder={form.telegram ? `Use main: ${form.telegram}` : "e.g. 8892259333"} />
                    <button type="button" onClick={() => connect("Telegram", m.telegram || form.telegram, `telegram-${i}`)} disabled={connecting !== ""} className={connectButtonClass()}>
                      <Send className="size-4" /> {connecting === `telegram-${i}` ? "Sending" : "Send test"}
                    </button>
                  </div>
                  <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-text-light">
                    <button type="button" onClick={openTelegramBot} className="text-primary font-medium hover:underline">Open bot</button>
                    <button type="button" onClick={() => copyTelegramInvite(m.name)} className="text-primary font-medium hover:underline">Copy invite</button>
                    <span>They open bot, tap Start or send /start, then send you the chat ID shown by the bot.</span>
                  </div>
                </Field>
                <Field label="WhatsApp number (optional)">
                  <input className={input()} value={m.whatsapp ?? ""} onChange={(e) => patch(i, { whatsapp: e.target.value.replace(/\D/g, "") })} placeholder={form.whatsapp ? `Use main: ${form.whatsapp}` : "Optional"} />
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-warning">
                    <span className="inline-flex items-center gap-1 rounded-md border border-warning/30 bg-warning/10 px-2 py-1 font-medium"><MessageCircle className="size-3" /> Coming soon</span>
                    <span>Saved now for future WhatsApp approvals.</span>
                  </div>
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
            {form.whatsapp && <Row k="WhatsApp" v={form.whatsapp} />}
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

function splitList(value: string) {
  return value.split(",").map((s) => s.trim()).filter(Boolean);
}

function sanitizePayload(payload: OnboardPayload): OnboardPayload {
  return {
    ...payload,
    whatsapp_number: payload.whatsapp || payload.whatsapp_number || "",
    allergies: payload.allergies ?? [],
    preferences: payload.preferences ?? [],
    family: (payload.family ?? [])
      .filter((member) => member.name?.trim())
      .map(({ _allergiesText, _preferencesText, ...member }: any) => ({
        ...member,
        whatsapp_number: member.whatsapp || member.whatsapp_number || "",
        allergies: member.allergies ?? [],
        preferences: member.preferences ?? [],
      })),
  };
}

function StepSuccess({ onContinue }: { userId: string; onContinue: () => void }) {
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
