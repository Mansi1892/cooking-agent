import { Link, createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { ArrowRight, LockKeyhole, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";

export const Route = createFileRoute("/reset-password")({
  component: ResetPassword,
});

function ResetPassword() {
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const token = typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("token") || "" : "";

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!token) {
      toast.error("Reset token is missing");
      return;
    }
    if (password.trim().length < 4) {
      toast.error("Use at least 4 characters");
      return;
    }
    if (password !== confirm) {
      toast.error("Passwords do not match");
      return;
    }
    setSubmitting(true);
    try {
      await api.resetPassword({ token, password: password.trim() });
      toast.success("Password updated", { description: "You can login with your new password now." });
      navigate({ to: "/login" });
    } catch (error) {
      toast.error("Reset failed", { description: error instanceof Error ? error.message : "Please request a new reset link." });
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
            <div className="text-xs text-text-light">Set new password</div>
          </div>
        </div>

        <h1 className="mt-8 text-3xl font-semibold tracking-tight">Create a new password</h1>
        <p className="mt-2 text-sm text-text-secondary">
          Choose a password you will use next time you sign in.
        </p>

        <div className="mt-6 space-y-3">
          <PasswordField value={password} onChange={setPassword} placeholder="New password" />
          <PasswordField value={confirm} onChange={setConfirm} placeholder="Confirm password" />
        </div>

        <button
          type="submit"
          disabled={submitting || !token}
          className="mt-6 w-full inline-flex items-center justify-center gap-2 rounded-lg bg-primary text-primary-foreground px-5 py-3 text-sm font-semibold hover:opacity-90 transition shadow-soft disabled:opacity-60"
        >
          {submitting ? "Updating..." : "Update password"}
          <ArrowRight className="size-4" />
        </button>

        {!token && (
          <p className="mt-4 text-sm text-destructive">
            This reset link is missing a token. Please request a new one.
          </p>
        )}

        <Link to="/login" className="mt-5 inline-flex text-sm font-medium text-primary hover:opacity-80 transition">
          Back to login
        </Link>
      </form>
    </div>
  );
}

function PasswordField({ value, onChange, placeholder }: { value: string; onChange: (value: string) => void; placeholder: string }) {
  return (
    <label className="flex items-center gap-3 rounded-lg border border-border bg-background px-3.5 py-2.5 focus-within:ring-2 focus-within:ring-primary/25 focus-within:border-primary/40 transition">
      <LockKeyhole className="size-4 text-text-light" />
      <input
        type="password"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-transparent text-sm outline-none placeholder:text-text-light"
      />
    </label>
  );
}
