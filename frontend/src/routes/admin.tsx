import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Coins, KeyRound, Loader2, LogOut, Plus, ShieldCheck, UserRound } from "lucide-react";
import { api, type AdminUser } from "@/lib/api";
import { toast } from "sonner";

export const Route = createFileRoute("/admin")({
  component: Admin,
});

function Admin() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(false);
  const [granting, setGranting] = useState<string | null>(null);
  const [amounts, setAmounts] = useState<Record<string, number>>({});
  const [adminUserId, setAdminUserId] = useState(() => localStorage.getItem("mpa_admin_user_id") || "");
  const [adminPassword, setAdminPassword] = useState(() => localStorage.getItem("mpa_admin_password") || "");
  const [isAdmin, setIsAdmin] = useState(() => localStorage.getItem("mpa_admin_ok") === "true");

  async function load(nextAdminUserId = adminUserId, nextAdminPassword = adminPassword) {
    setLoading(true);
    try {
      const result = await api.getAdminUsers(nextAdminUserId, nextAdminPassword);
      setUsers(result.users);
    } catch (error) {
      toast.error("Admin page unavailable", { description: error instanceof Error ? error.message : "Please try again." });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (isAdmin && adminUserId && adminPassword) load();
  }, []);

  async function login(e: React.FormEvent) {
    e.preventDefault();
    const cleanId = adminUserId.trim();
    const cleanPassword = adminPassword.trim();
    if (!cleanId || !cleanPassword) {
      toast.error("Enter admin user ID and password");
      return;
    }
    setLoading(true);
    try {
      await api.adminLogin({ admin_user_id: cleanId, admin_password: cleanPassword });
      localStorage.setItem("mpa_admin_user_id", cleanId);
      localStorage.setItem("mpa_admin_password", cleanPassword);
      localStorage.setItem("mpa_admin_ok", "true");
      setIsAdmin(true);
      await load(cleanId, cleanPassword);
      toast.success("Admin access granted");
    } catch (error) {
      toast.error("Admin login failed", { description: error instanceof Error ? error.message : "Check user ID, password, and role." });
    } finally {
      setLoading(false);
    }
  }

  function logoutAdmin() {
    localStorage.removeItem("mpa_admin_user_id");
    localStorage.removeItem("mpa_admin_password");
    localStorage.removeItem("mpa_admin_ok");
    setIsAdmin(false);
    setUsers([]);
    setAdminPassword("");
  }

  async function addCredits(user: AdminUser) {
    const amount = Math.max(1, Number(amounts[user.id] || 1));
    if (!adminUserId || !adminPassword) return;
    setGranting(user.id);
    try {
      const result = await api.addCredits({ admin_user_id: adminUserId, admin_password: adminPassword, user_id: user.id, amount });
      setUsers((list) => list.map((item) => item.id === user.id ? { ...item, credits: result.credits } : item));
      toast.success("Credits added", { description: `${amount} credit${amount === 1 ? "" : "s"} added to ${user.name}.` });
    } catch (error) {
      toast.error("Could not add credits", { description: error instanceof Error ? error.message : "Please try again." });
    } finally {
      setGranting(null);
    }
  }

  return (
    <div className="space-y-6 animate-fade-up">
      <header className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <div className="text-[11px] uppercase tracking-wider text-text-light font-medium">Admin</div>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">Credit manager</h1>
          <p className="mt-1 text-sm text-text-secondary">Users get 3 free meal plan credits. Add more credits when needed.</p>
        </div>
        <div className="inline-flex items-center gap-2 rounded-lg bg-primary-light px-3 py-2 text-sm font-medium text-primary">
          <ShieldCheck className="size-4" /> Admin profile
        </div>
      </header>

      {!isAdmin && (
        <form onSubmit={login} className="rounded-xl border border-border bg-surface shadow-soft p-5 max-w-md">
          <div className="flex items-start gap-3">
            <div className="size-10 rounded-lg bg-primary-light grid place-items-center text-primary">
              <KeyRound className="size-5" />
            </div>
            <div>
              <h2 className="text-sm font-semibold">Admin login</h2>
              <p className="mt-1 text-sm text-text-secondary">Use Mansi's backend user ID and the admin password to manage credits.</p>
            </div>
          </div>
          <div className="mt-5 space-y-3">
            <input
              value={adminUserId}
              onChange={(e) => setAdminUserId(e.target.value)}
              placeholder="Admin user ID, e.g. 11"
              className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-sm outline-none focus:border-primary/40 focus:ring-2 focus:ring-primary/20"
            />
            <input
              type="password"
              value={adminPassword}
              onChange={(e) => setAdminPassword(e.target.value)}
              placeholder="Admin password"
              className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-sm outline-none focus:border-primary/40 focus:ring-2 focus:ring-primary/20"
            />
          </div>
          <button disabled={loading} className="mt-5 inline-flex items-center gap-2 rounded-lg bg-primary text-primary-foreground px-4 py-2.5 text-sm font-medium hover:opacity-90 disabled:opacity-60 transition">
            {loading ? <Loader2 className="size-4 animate-spin" /> : <ShieldCheck className="size-4" />}
            Open credit manager
          </button>
          <p className="mt-3 text-xs text-text-light">Default local password is admin123 unless ADMIN_PASSWORD is set in .env.</p>
        </form>
      )}

      {isAdmin && (
      <section className="rounded-xl border border-border bg-surface shadow-soft overflow-hidden">
        <div className="p-4 border-b border-border flex items-center justify-between gap-3">
          <div className="text-sm font-medium">Credit users</div>
          <button onClick={logoutAdmin} className="inline-flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-xs font-medium text-text-secondary hover:text-destructive transition">
            <LogOut className="size-3.5" /> Admin logout
          </button>
        </div>
        {loading ? (
          <div className="p-6 flex items-center gap-2 text-sm text-text-secondary">
            <Loader2 className="size-4 animate-spin" /> Loading users...
          </div>
        ) : users.length === 0 ? (
          <div className="p-6 text-sm text-text-secondary">No users found.</div>
        ) : (
          <div className="divide-y divide-border">
            {users.map((user) => (
              <article key={user.id} className="p-4 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div className="flex items-start gap-3 min-w-0">
                  <div className="size-10 rounded-lg bg-muted grid place-items-center text-text-secondary">
                    <UserRound className="size-5" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h2 className="text-sm font-semibold truncate">{user.name}</h2>
                      {user.role === "admin" && <span className="text-[10px] uppercase tracking-wider rounded-full bg-primary-light text-primary px-2 py-0.5">Admin</span>}
                    </div>
                    <div className="mt-1 text-xs text-text-light">
                      ID {user.id} · {user.goal.replace("_", " ")} · Budget ₹{Math.round(user.budget_weekly || 0)}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <div className="rounded-lg bg-muted px-3 py-2 min-w-[92px]">
                    <div className="text-[10px] uppercase tracking-wider text-text-light">Credits</div>
                    <div className="mt-0.5 flex items-center gap-1 text-sm font-semibold">
                      <Coins className="size-3.5 text-primary" /> {user.credits}
                    </div>
                  </div>
                  <input
                    type="number"
                    min={1}
                    max={100}
                    value={amounts[user.id] ?? 1}
                    onChange={(e) => setAmounts((current) => ({ ...current, [user.id]: Number(e.target.value || 1) }))}
                    className="w-20 rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary/40 focus:ring-2 focus:ring-primary/20"
                  />
                  <button
                    onClick={() => addCredits(user)}
                    disabled={granting === user.id}
                    className="inline-flex items-center gap-2 rounded-lg bg-primary text-primary-foreground px-3 py-2 text-sm font-medium hover:opacity-90 disabled:opacity-60 transition"
                  >
                    {granting === user.id ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />}
                    Add
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
      )}
    </div>
  );
}
