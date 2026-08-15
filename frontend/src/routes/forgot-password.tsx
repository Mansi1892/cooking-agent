import { Link, createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { ArrowRight, Mail, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { hasSupabaseAuthConfig, supabase } from "@/lib/supabase";

export const Route = createFileRoute("/forgot-password")({
  component: ForgotPassword,
});

function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const cleanEmail = email.trim().toLowerCase();
    if (!cleanEmail) {
      toast.error("Enter your email");
      return;
    }
    setSubmitting(true);
    try {
      if (!hasSupabaseAuthConfig()) {
        toast.error("Supabase Auth is not configured");
        return;
      }
      const { error } = await supabase.auth.resetPasswordForEmail(cleanEmail, {
        redirectTo: `${window.location.origin}/reset-password`,
      });
      if (error) throw error;
      toast.success("Reset instructions sent", {
        description: "Check your email for the password reset link.",
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Please try again.";
      toast.error("Reset failed", { description: message });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-6 py-12">
      <form onSubmit={submit} className="w-full max-w-md rounded-xl border border-border bg-surface p-6 shadow-soft">
        <div className="flex items-center gap-3">
          <div className="size-10 rounded-xl bg-primary-light text-primary grid place-items-center">
            <Sparkles className="size-5" />
          </div>
          <div>
            <div className="font-semibold tracking-tight">Smart Meal AI</div>
            <div className="text-xs text-text-light">Account recovery</div>
          </div>
        </div>

        <h1 className="mt-8 text-3xl font-semibold tracking-tight">Forgot password?</h1>
        <p className="mt-2 text-sm text-text-secondary">
          Enter your account email and we will send reset instructions.
        </p>

        <label className="mt-6 flex items-center gap-3 rounded-lg border border-border bg-background px-3.5 py-2.5 focus-within:ring-2 focus-within:ring-primary/25 focus-within:border-primary/40 transition">
          <Mail className="size-4 text-text-light" />
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="Email address"
            className="w-full bg-transparent text-sm outline-none placeholder:text-text-light"
          />
        </label>

        <button
          type="submit"
          disabled={submitting}
          className="mt-6 w-full inline-flex items-center justify-center gap-2 rounded-lg bg-primary text-primary-foreground px-5 py-3 text-sm font-semibold hover:opacity-90 transition shadow-soft disabled:opacity-60"
        >
          {submitting ? "Sending..." : "Send reset instructions"}
          <ArrowRight className="size-4" />
        </button>

        <Link to="/login" className="mt-5 inline-flex text-sm font-medium text-primary hover:opacity-80 transition">
          Back to login
        </Link>
      </form>
    </div>
  );
}
