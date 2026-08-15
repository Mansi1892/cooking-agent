import { Link, createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { ArrowRight, LockKeyhole, Mail, Sparkles, UserRound } from "lucide-react";
import { toast } from "sonner";
import { storage } from "@/lib/storage";
import { api } from "@/lib/api";
import { hasSupabaseAuthConfig, supabase } from "@/lib/supabase";

export const Route = createFileRoute("/login")({
  component: Login,
});

function Login() {
  const navigate = useNavigate();
  const [name, setName] = useState(storage.getUserName() || "");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"login" | "signup">("login");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const cleanEmail = email.trim().toLowerCase();
    const cleanName = name.trim() || cleanEmail.split("@")[0] || "Guest";
    if (!cleanEmail) {
      toast.error("Enter your email");
      return;
    }
    if (password.trim().length < 4) {
      toast.error("Use at least 4 characters");
      return;
    }

    if (mode === "login") {
      try {
        if (!hasSupabaseAuthConfig()) {
          toast.error("Supabase Auth is not configured");
          return;
        }
        const { data, error } = await supabase.auth.signInWithPassword({
          email: cleanEmail,
          password: password.trim(),
        });
        if (error) throw new Error(formatAuthError(error.message));
        const result = await api.getProfileByEmail(cleanEmail);
        saveProfileSession(result.profile, cleanEmail, data.user?.user_metadata?.full_name || cleanName);
      } catch (error) {
        toast.error("Login failed", { description: error instanceof Error ? error.message : "Please check your email and password." });
        return;
      }
      toast.success("Welcome back");
      navigate({ to: "/" });
      return;
    }

    try {
      await api.signupCheck({ email: cleanEmail, password: password.trim(), name: cleanName });
      if (!hasSupabaseAuthConfig()) {
        toast.error("Supabase Auth is not configured");
        return;
      }
      const { data, error } = await supabase.auth.signUp({
        email: cleanEmail,
        password: password.trim(),
        options: {
          data: { full_name: cleanName },
          emailRedirectTo: `${window.location.origin}/login`,
        },
      });
      if (error) throw new Error(formatAuthError(error.message));
      if (data.user && Array.isArray(data.user.identities) && data.user.identities.length === 0) {
        throw new Error("Account already exists. Please login instead.");
      }
    } catch (error) {
      toast.error("Sign up failed", { description: error instanceof Error ? error.message : "Please try again." });
      return;
    }

    try {
      const result = await api.getProfileByEmail(cleanEmail);
      saveProfileSession(result.profile, cleanEmail, cleanName);
      toast.success("Account linked", { description: "Your existing meal profile is connected to Supabase login." });
      navigate({ to: "/" });
      return;
    } catch {
      // New auth account without a meal profile yet should continue onboarding.
    }

    storage.clearAll();
    storage.setAuthUser({
      name: cleanName,
      email: cleanEmail,
      logged_in_at: new Date().toISOString(),
    });
    storage.setUserName(cleanName);
    toast.success("Account started", { description: "Finish your profile to activate meal planning." });
    navigate({ to: "/onboarding" });
  }

  return (
    <div className="min-h-screen grid lg:grid-cols-[1.05fr_0.95fr] bg-background">
      <section className="relative hidden lg:flex overflow-hidden bg-[radial-gradient(circle_at_20%_15%,rgba(16,185,129,0.28),transparent_28%),radial-gradient(circle_at_80%_25%,rgba(59,130,246,0.24),transparent_30%),linear-gradient(135deg,#101828,#12312b_58%,#0f172a)] text-white">
        <div className="absolute inset-0 bg-[url('https://images.unsplash.com/photo-1490645935967-10de6ba17061?auto=format&fit=crop&w=1800&q=80')] bg-cover bg-center opacity-35" />
        <div className="absolute inset-0 bg-slate-950/45" />
        <div className="relative flex flex-col justify-between p-12 xl:p-16 w-full">
          <div className="flex items-center gap-3">
            <div className="size-10 rounded-xl bg-white/15 backdrop-blur grid place-items-center">
              <Sparkles className="size-5" />
            </div>
            <div>
              <div className="font-semibold tracking-tight">Smart Meal AI</div>
              <div className="text-xs text-white/60">Personal weekly planning</div>
            </div>
          </div>
          <div className="max-w-xl pb-10">
            <div className="inline-flex items-center rounded-full bg-white/12 border border-white/15 px-3 py-1 text-xs font-medium backdrop-blur">
              Saved plans, grocery lists, and family profiles
            </div>
            <h1 className="mt-5 text-5xl xl:text-6xl font-semibold tracking-tight leading-[1.02]">
              Come back to meals that already know you.
            </h1>
            <p className="mt-5 text-lg text-white/78 max-w-lg">
              Sign in, finish onboarding once, then keep generating plans against the same saved profile.
            </p>
          </div>
        </div>
      </section>

      <main className="flex items-center justify-center px-6 py-10">
        <form onSubmit={submit} className="w-full max-w-md">
          <div className="lg:hidden mb-8 flex items-center gap-3">
            <div className="size-10 rounded-xl bg-primary-light text-primary grid place-items-center">
              <Sparkles className="size-5" />
            </div>
            <div className="font-semibold tracking-tight">Smart Meal AI</div>
          </div>

          <div className="mb-8">
            <div className="text-[11px] uppercase tracking-wider text-primary font-semibold">Account</div>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight">
              {mode === "signup" ? "Create your account" : "Welcome back"}
            </h2>
            <p className="mt-2 text-sm text-text-secondary">
              Your profile stays linked to generated meal plans after onboarding.
            </p>
          </div>

          <div className="grid grid-cols-2 rounded-lg bg-muted p-1 mb-5">
            <button type="button" onClick={() => setMode("login")} className={tab(mode === "login")}>Login</button>
            <button type="button" onClick={() => setMode("signup")} className={tab(mode === "signup")}>Sign up</button>
          </div>

          <div className="space-y-3">
            {mode === "signup" && (
              <Field icon={UserRound}>
                <input className={input()} value={name} onChange={(e) => setName(e.target.value)} placeholder="Full name" />
              </Field>
            )}
            <Field icon={Mail}>
              <input type="email" className={input()} value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email address" />
            </Field>
            <Field icon={LockKeyhole}>
              <input type="password" className={input()} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Password" />
            </Field>
          </div>

          <button className="mt-6 w-full inline-flex items-center justify-center gap-2 rounded-lg bg-primary text-primary-foreground px-5 py-3 text-sm font-semibold hover:opacity-90 transition shadow-soft">
            {mode === "signup" ? "Create account" : "Login"} <ArrowRight className="size-4" />
          </button>

          {mode === "login" && (
            <div className="mt-4 text-right">
              <Link to="/forgot-password" className="text-sm font-medium text-primary hover:opacity-80 transition">
                Forgot password?
              </Link>
            </div>
          )}

          <p className="mt-4 text-xs text-text-light leading-relaxed">
            Supabase Auth protects your email/password. New users finish profile setup after signup.
          </p>
        </form>
      </main>
    </div>
  );
}

function saveProfileSession(profile: any, email: string, fallbackName: string) {
  storage.clearAll();
  storage.setAuthUser({
    name: profile.name || fallbackName,
    email,
    logged_in_at: new Date().toISOString(),
  });
  storage.setUserId(String(profile.id));
  storage.setUserName(profile.name || fallbackName);
  storage.setGoal(profile.goal || "maintenance");
  storage.setCredits(Number(profile.credits ?? 3));
  storage.setRole(profile.role || "user");
  storage.setTelegram(profile.telegram_id || "");
  storage.setWhatsapp(profile.whatsapp_number || "");
  storage.setProfile({
    name: profile.name || fallbackName,
    email,
    age: profile.age,
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

function Field({ icon: Icon, children }: { icon: any; children: React.ReactNode }) {
  return (
    <label className="flex items-center gap-3 rounded-lg border border-border bg-surface px-3.5 py-2.5 focus-within:ring-2 focus-within:ring-primary/25 focus-within:border-primary/40 transition">
      <Icon className="size-4 text-text-light" />
      {children}
    </label>
  );
}

function input() {
  return "w-full bg-transparent text-sm outline-none placeholder:text-text-light";
}

function tab(active: boolean) {
  return [
    "rounded-md px-3 py-2 text-sm font-medium transition",
    active ? "bg-surface shadow-soft text-text-primary" : "text-text-secondary hover:text-text-primary",
  ].join(" ");
}

function formatAuthError(message: string) {
  if (/email not confirmed/i.test(message)) {
    return "Email is not confirmed. Please open the confirmation email from Supabase, or confirm this user in Supabase Auth for local testing.";
  }
  if (/invalid login credentials/i.test(message)) {
    return "Incorrect email or password.";
  }
  if (/rate limit/i.test(message)) {
    return "Supabase email rate limit is exceeded. Please wait or use the test SQL password reset.";
  }
  return message;
}
