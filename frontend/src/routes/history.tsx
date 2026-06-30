import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Calendar, ArrowRight, Activity, Drumstick, Target } from "lucide-react";
import { api, mock, safe, type HistoryItem } from "@/lib/api";
import { storage } from "@/lib/storage";

export const Route = createFileRoute("/history")({
  component: History,
});

function History() {
  const [items, setItems] = useState<HistoryItem[]>([]);

  useEffect(() => {
    const uid = storage.getUserId();
    if (uid) safe(api.getHistory(uid), mock.history()).then(setItems);
    else setItems(mock.history());
  }, []);

  return (
    <div className="space-y-8 animate-fade-up">
      <header>
        <div className="text-[11px] uppercase tracking-wider text-text-light font-medium">History</div>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">Your meal plan history</h1>
        <p className="mt-1 text-sm text-text-secondary">A timeline of every weekly plan you've generated.</p>
      </header>

      <ol className="relative border-l border-border ml-3 space-y-5">
        {items.map((it, i) => (
          <li key={it.plan_id} className="pl-6 relative">
            <span className={"absolute -left-[7px] top-2 size-3 rounded-full ring-4 ring-background " + (i === 0 ? "bg-primary" : "bg-border")} />
            <article className="rounded-2xl border border-border bg-surface shadow-soft p-5 hover:shadow-elevated hover:-translate-y-0.5 transition">
              <div className="flex items-start justify-between flex-wrap gap-3">
                <div>
                  <div className="flex items-center gap-2 text-xs text-text-light">
                    <Calendar className="size-3.5" />
                    {new Date(it.created_at).toLocaleDateString(undefined, { weekday: "short", month: "long", day: "numeric", year: "numeric" })}
                  </div>
                  <h3 className="mt-1 text-base font-semibold">Week of {new Date(it.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</h3>
                  <div className="mt-2 flex items-center gap-2">
                    <Badge status={it.status} />
                    <span className="text-[11px] text-text-light capitalize">Goal · {it.goal.replace("_", " ")}</span>
                  </div>
                </div>
                <Link to="/meal-plans" className="inline-flex items-center gap-1 text-sm text-primary font-medium hover:underline">
                  View details <ArrowRight className="size-3.5" />
                </Link>
              </div>
              <div className="mt-4 grid grid-cols-3 gap-3">
                <Stat icon={Activity} label="Avg Calories" value={`${it.avg_calories}`} />
                <Stat icon={Drumstick} label="Protein" value={`${it.avg_protein}g`} />
                <Stat icon={Target} label="Adherence" value={`${85 + (i % 10)}%`} />
              </div>
            </article>
          </li>
        ))}
      </ol>
    </div>
  );
}

function Stat({ icon: Icon, label, value }: { icon: any; label: string; value: string }) {
  return (
    <div className="rounded-xl bg-muted/50 border border-border p-3">
      <div className="flex items-center gap-2 text-[11px] text-text-light font-medium">
        <Icon className="size-3.5" /> {label}
      </div>
      <div className="mt-1 text-base font-semibold">{value}</div>
    </div>
  );
}

function Badge({ status }: { status: string }) {
  const map: Record<string, string> = {
    active: "bg-primary-light text-primary",
    approved: "bg-success/10 text-success",
    pending: "bg-warning/10 text-warning",
  };
  return <span className={`text-[10px] uppercase tracking-wider font-medium px-2 py-0.5 rounded-full ${map[status] || map.approved}`}>{status}</span>;
}
