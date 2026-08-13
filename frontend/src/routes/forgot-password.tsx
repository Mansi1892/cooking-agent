import { Link, createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { ArrowRight, Mail, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";

export const Route = createFileRoute("/forgot-password")({
  component: ForgotPassword,
});

function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [resetUrl, setResetUrl] = useState("");
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
      const result = await api.forgotPassword({ email: cleanEmail });
      setResetUrl(result.reset_url || "");
      toast.success("Reset link created", {
        description: result.reset_url ? "Open the link below to set a new password." : "Check your email for the reset link.",
      });
    } catch (error) {
      toast.error("Reset failed", { description: error instanceof Error ? error.message : "Please try again." });
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
          Enter your account email and we will create a secure reset link.
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
          {submitting ? "Creating link..." : "Create reset link"}
          <ArrowRight className="size-4" />
        </button>

        {resetUrl && (
          <div className="mt-5 rounded-lg border border-primary/20 bg-primary-light/40 p-3 text-sm">
            <div className="font-medium text-text-primary">Reset link</div>
            <a href={resetUrl} className="mt-1 block break-all text-primary hover:opacity-80">
              {resetUrl}
            </a>
          </div>
        )}

        <Link to="/login" className="mt-5 inline-flex text-sm font-medium text-primary hover:opacity-80 transition">
          Back to login
        </Link>
      </form>
    </div>
  );
}
