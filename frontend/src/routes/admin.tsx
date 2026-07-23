import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { CheckCircle2, KeyRound, Loader2, LogOut, MessageSquareWarning, Plus, ShieldCheck } from "lucide-react";
import { api, type CreditRequest, type SupportTicket } from "@/lib/api";
import { storage } from "@/lib/storage";
import { toast } from "sonner";

export const Route = createFileRoute("/admin")({
  component: Admin,
});

function Admin() {
  const navigate = useNavigate();
  const [requests, setRequests] = useState<CreditRequest[]>([]);
  const [tickets, setTickets] = useState<SupportTicket[]>([]);
  const [loading, setLoading] = useState(false);
  const [granting, setGranting] = useState<string | null>(null);
  const [updatingTicket, setUpdatingTicket] = useState<number | null>(null);
  const [amounts, setAmounts] = useState<Record<string, number>>({});
  const [adminUserId, setAdminUserId] = useState("");
  const [adminPassword, setAdminPassword] = useState("");
  const [isAdmin, setIsAdmin] = useState(false);

  async function load(nextAdminUserId = adminUserId, nextAdminPassword = adminPassword) {
    setLoading(true);
    try {
      const [requestResult, ticketResult] = await Promise.all([
        api.getCreditRequests(nextAdminUserId, nextAdminPassword),
        api.getSupportTickets(nextAdminUserId, nextAdminPassword, "open"),
      ]);
      setRequests(requestResult.requests);
      setTickets(ticketResult.tickets);
    } catch (error) {
      toast.error("Admin page unavailable", { description: error instanceof Error ? error.message : "Please try again." });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const currentUserId = storage.getUserId();
    if (!currentUserId) {
      navigate({ to: "/login" });
      return;
    }
    api.getProfile(currentUserId).then(async (result) => {
      if (result.profile.role !== "admin") {
        clearAdminAccess();
        toast.error("Admin access required");
        navigate({ to: "/" });
        return;
      }
      const password = "admin123";
      setAdminUserId(currentUserId);
      setAdminPassword(password);
      setIsAdmin(true);
      await load(currentUserId, password);
    }).catch(() => {
      clearAdminAccess();
      navigate({ to: "/" });
    });
  }, [navigate]);

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
    clearAdminAccess();
    setIsAdmin(false);
    setAdminPassword("");
  }

  async function grantRequest(request: CreditRequest) {
    if (!adminUserId || !adminPassword) return;
    const amount = Math.max(1, Number(amounts[`request:${request.id}`] || request.requested_credits || 3));
    setGranting(`request:${request.id}`);
    try {
      await api.grantCreditRequest({ admin_user_id: adminUserId, admin_password: adminPassword, request_id: request.id, amount });
      setRequests((list) => list.filter((item) => item.id !== request.id));
      toast.success("Request approved", { description: `${amount} credits granted.` });
    } catch (error) {
      toast.error("Could not approve request", { description: error instanceof Error ? error.message : "Please try again." });
    } finally {
      setGranting(null);
    }
  }

  async function updateTicket(ticket: SupportTicket, status: "reviewing" | "resolved" | "open") {
    if (!adminUserId || !adminPassword) return;
    setUpdatingTicket(ticket.id);
    try {
      const result = await api.updateSupportTicketStatus({
        admin_user_id: adminUserId,
        admin_password: adminPassword,
        ticket_id: ticket.id,
        status,
      });
      if (status === "resolved") {
        setTickets((list) => list.filter((item) => item.id !== ticket.id));
      } else {
        setTickets((list) => list.map((item) => (item.id === ticket.id ? result.ticket : item)));
      }
      toast.success(status === "resolved" ? "Issue resolved" : "Issue updated");
    } catch (error) {
      toast.error("Could not update issue", { description: error instanceof Error ? error.message : "Please try again." });
    } finally {
      setUpdatingTicket(null);
    }
  }

  return (
    <div className="space-y-6 animate-fade-up">
      <header className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <div className="text-[11px] uppercase tracking-wider text-text-light font-medium">Admin</div>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">Admin Center</h1>
          <p className="mt-1 text-sm text-text-secondary">Manage credit requests and user-submitted support issues.</p>
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
              <p className="mt-1 text-sm text-text-secondary">Use the admin backend user ID and admin password to manage credits and issues.</p>
            </div>
          </div>
          <div className="mt-5 space-y-3">
            <input
              value={adminUserId}
              onChange={(e) => setAdminUserId(e.target.value)}
              placeholder="Admin user ID, e.g. 18"
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
      <>
        <section className="rounded-xl border border-border bg-surface shadow-soft overflow-hidden">
          <div className="p-4 border-b border-border flex items-center justify-between gap-3">
            <div>
              <div className="text-sm font-medium">Pending credit requests</div>
              <p className="mt-0.5 text-xs text-text-light">Users appear here only after they request more credits.</p>
            </div>
            <button onClick={logoutAdmin} className="inline-flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-xs font-medium text-text-secondary hover:text-destructive transition">
              <LogOut className="size-3.5" /> Admin logout
            </button>
          </div>
          {loading ? (
            <div className="p-6 flex items-center gap-2 text-sm text-text-secondary">
              <Loader2 className="size-4 animate-spin" /> Loading requests...
            </div>
          ) : requests.length === 0 ? (
            <div className="p-6 text-sm text-text-secondary">No credit requests yet.</div>
          ) : (
            <div className="divide-y divide-border">
              {requests.map((request) => (
                <article key={request.id} className="p-4 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                  <div>
                    <div className="text-sm font-medium">{request.users?.name || `User ${request.user_id}`}</div>
                    <div className="mt-0.5 text-xs text-text-light">
                      ID {request.user_id} · Current credits {request.users?.credits ?? 0} · Requested {request.requested_credits}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      type="number"
                      min={1}
                      max={100}
                      value={amounts[`request:${request.id}`] ?? request.requested_credits ?? 3}
                      onChange={(e) => setAmounts((current) => ({ ...current, [`request:${request.id}`]: Number(e.target.value || 1) }))}
                      className="w-20 rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary/40 focus:ring-2 focus:ring-primary/20"
                    />
                    <button
                      onClick={() => grantRequest(request)}
                      disabled={granting === `request:${request.id}`}
                      className="inline-flex items-center gap-2 rounded-lg bg-primary text-primary-foreground px-3 py-2 text-sm font-medium hover:opacity-90 disabled:opacity-60 transition"
                    >
                      {granting === `request:${request.id}` ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />}
                      Grant
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>

        <section className="rounded-xl border border-border bg-surface shadow-soft overflow-hidden">
          <div className="p-4 border-b border-border flex items-start justify-between gap-3">
            <div>
              <div className="text-sm font-medium">Open support issues</div>
              <p className="mt-0.5 text-xs text-text-light">User-submitted app errors and meal-plan issues.</p>
            </div>
            <MessageSquareWarning className="size-4 text-primary" />
          </div>
          {loading ? (
            <div className="p-6 flex items-center gap-2 text-sm text-text-secondary">
              <Loader2 className="size-4 animate-spin" /> Loading issues...
            </div>
          ) : tickets.length === 0 ? (
            <div className="p-6 text-sm text-text-secondary">No open issues yet.</div>
          ) : (
            <div className="divide-y divide-border">
              {tickets.map((ticket) => (
                <article key={ticket.id} className="p-4 space-y-3">
                  <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-sm font-medium">{ticket.title}</h3>
                        <span className="rounded-full bg-muted px-2 py-0.5 text-[11px] capitalize text-text-secondary">{ticket.category.replace("_", " ")}</span>
                        <span className="rounded-full bg-primary-light px-2 py-0.5 text-[11px] capitalize text-primary">{ticket.severity}</span>
                      </div>
                      <div className="mt-1 text-xs text-text-light">
                        #{ticket.id} · {ticket.users?.name || `User ${ticket.user_id}`} · {ticket.status}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => updateTicket(ticket, "reviewing")}
                        disabled={updatingTicket === ticket.id || ticket.status === "reviewing"}
                        className="inline-flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-xs font-medium text-text-secondary hover:text-text-primary disabled:opacity-60 transition"
                      >
                        Review
                      </button>
                      <button
                        onClick={() => updateTicket(ticket, "resolved")}
                        disabled={updatingTicket === ticket.id}
                        className="inline-flex items-center gap-2 rounded-lg bg-primary text-primary-foreground px-3 py-2 text-xs font-medium hover:opacity-90 disabled:opacity-60 transition"
                      >
                        {updatingTicket === ticket.id ? <Loader2 className="size-3.5 animate-spin" /> : <CheckCircle2 className="size-3.5" />}
                        Resolve
                      </button>
                    </div>
                  </div>
                  <p className="text-sm text-text-secondary whitespace-pre-wrap">{ticket.description}</p>
                  {ticket.page_url && <div className="truncate text-xs text-text-light">Page: {ticket.page_url}</div>}
                </article>
              ))}
            </div>
          )}
        </section>
      </>
      )}
    </div>
  );
}

function clearAdminAccess() {
  try {
    localStorage.removeItem("mpa_admin_user_id");
    localStorage.removeItem("mpa_admin_password");
    localStorage.removeItem("mpa_admin_ok");
  } catch {}
}
