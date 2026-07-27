import { createFileRoute } from "@tanstack/react-router";
import { AlertCircle, CheckCircle2, HelpCircle, Loader2, Send } from "lucide-react";
import { useMemo, useState } from "react";
import { api } from "@/lib/api";
import { storage } from "@/lib/storage";
import { toast } from "sonner";

export const Route = createFileRoute("/help")({
  component: Help,
});

const CATEGORIES = [
  { value: "bug", label: "Bug or error" },
  { value: "meal_plan", label: "Meal plan issue" },
  { value: "grocery", label: "Grocery list issue" },
  { value: "telegram", label: "Telegram issue" },
  { value: "account", label: "Account or login" },
  { value: "billing", label: "Credits or billing" },
  { value: "other", label: "Other" },
];

const SEVERITIES = [
  { value: "normal", label: "Normal" },
  { value: "high", label: "High" },
  { value: "urgent", label: "Urgent" },
  { value: "low", label: "Low" },
];

function Help() {
  const [category, setCategory] = useState("bug");
  const [severity, setSeverity] = useState("normal");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submittedId, setSubmittedId] = useState<number | null>(null);

  const pageUrl = useMemo(() => (typeof window !== "undefined" ? window.location.href : ""), []);
  const hasEnoughDetails = title.trim().length >= 3 && description.trim().length >= 10;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (submitting) return;
    let userId = storage.getUserId();
    if (!userId) {
      const authUser = storage.getAuthUser<{ email?: string; name?: string }>();
      const email = authUser?.email?.trim().toLowerCase();
      if (email) {
        try {
          const result = await api.getProfileByEmail(email);
          const profile = result.profile;
          userId = String(profile.id);
          storage.setUserId(userId);
          storage.setUserName(profile.name || authUser?.name || email);
          storage.setGoal(profile.goal || "maintenance");
          storage.setCredits(Number(profile.credits ?? storage.getCredits()));
          storage.setRole(profile.role || "user");
          storage.setTelegram(profile.telegram_id || "");
        } catch {
          toast.error("Profile not found", { description: "Please login again or complete signup before submitting an issue." });
          return;
        }
      } else {
        toast.error("Please login first");
        return;
      }
    }
    if (!hasEnoughDetails) {
      toast.error("Add a short title and details");
      return;
    }
    setSubmitting(true);
    try {
      const result = await api.createSupportTicket({
        user_id: userId,
        category,
        severity,
        title: title.trim(),
        description: description.trim(),
        page_url: pageUrl,
      });
      setSubmittedId(result.ticket.id);
      setTitle("");
      setDescription("");
      toast.success("Issue submitted", { description: "Admin can now review it from the Admin page." });
    } catch (error) {
      toast.error("Could not submit issue", { description: error instanceof Error ? error.message : "Please try again." });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-6 animate-fade-up">
      <header className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <div className="text-[11px] uppercase tracking-wider text-text-light font-medium">Help</div>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">Report an issue</h1>
          <p className="mt-1 text-sm text-text-secondary">Send app errors, wrong meal results, Telegram issues, or account problems to admin.</p>
        </div>
        <div className="inline-flex items-center gap-2 rounded-lg bg-primary-light px-3 py-2 text-sm font-medium text-primary">
          <HelpCircle className="size-4" /> Support
        </div>
      </header>

      {submittedId && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800 flex items-start gap-2">
          <CheckCircle2 className="mt-0.5 size-4 shrink-0" />
          <div>
            <div className="font-medium">Issue #{submittedId} was submitted.</div>
            <div className="mt-0.5 text-emerald-700">You can continue using the app while admin checks it.</div>
          </div>
        </div>
      )}

      <form onSubmit={submit} className="rounded-xl border border-border bg-surface shadow-soft p-5 max-w-3xl">
        <div className="grid gap-4 md:grid-cols-2">
          <label className="space-y-1.5">
            <span className="text-sm font-medium">Issue type</span>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-sm outline-none focus:border-primary/40 focus:ring-2 focus:ring-primary/20"
            >
              {CATEGORIES.map((item) => (
                <option key={item.value} value={item.value}>{item.label}</option>
              ))}
            </select>
          </label>
          <label className="space-y-1.5">
            <span className="text-sm font-medium">Priority</span>
            <select
              value={severity}
              onChange={(e) => setSeverity(e.target.value)}
              className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-sm outline-none focus:border-primary/40 focus:ring-2 focus:ring-primary/20"
            >
              {SEVERITIES.map((item) => (
                <option key={item.value} value={item.value}>{item.label}</option>
              ))}
            </select>
          </label>
        </div>

        <label className="mt-4 block space-y-1.5">
          <span className="text-sm font-medium">Title</span>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Example: Grocery list is empty after approval"
            className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-sm outline-none focus:border-primary/40 focus:ring-2 focus:ring-primary/20"
          />
        </label>

        <label className="mt-4 block space-y-1.5">
          <span className="text-sm font-medium">Details</span>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={7}
            placeholder="Tell us what happened, what you expected, and any error message you saw."
            className="w-full resize-none rounded-lg border border-border bg-background px-3 py-2.5 text-sm outline-none focus:border-primary/40 focus:ring-2 focus:ring-primary/20"
          />
        </label>

        <div className="mt-4 rounded-lg border border-border bg-muted px-3 py-2.5 text-xs text-text-secondary flex gap-2">
          <AlertCircle className="mt-0.5 size-3.5 shrink-0 text-text-light" />
          <span>Current page is attached automatically: {pageUrl || "Unavailable"}</span>
        </div>

        <button disabled={submitting} className="mt-5 inline-flex items-center gap-2 rounded-lg bg-primary text-primary-foreground px-4 py-2.5 text-sm font-medium hover:opacity-90 disabled:opacity-60 transition">
          {submitting ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}
          Submit issue
        </button>
      </form>
    </div>
  );
}
