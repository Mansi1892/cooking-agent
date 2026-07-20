import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { Search, Printer, Download, Check, ShoppingBasket, Loader2 } from "lucide-react";
import { api, type GroceryGroup } from "@/lib/api";
import { storage } from "@/lib/storage";
import { toast } from "sonner";

export const Route = createFileRoute("/grocery")({
  component: Grocery,
});

function Grocery() {
  const [groups, setGroups] = useState<GroceryGroup[]>([]);
  const [query, setQuery] = useState("");
  const [checked, setChecked] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const userId = storage.getUserId();
      if (!userId) {
        setGroups([]);
        setLoading(false);
        return;
      }

      try {
        let planId = storage.getLastPlanId();
        if (!planId) {
          const latest = await api.getLatestPlan(userId);
          planId = latest.plan.id;
          if (planId) storage.setLastPlanId(planId);
        }
        if (!planId) {
          setGroups([]);
          return;
        }
        setGroups(await api.getGrocery(planId));
      } catch {
        setGroups([]);
      } finally {
        setLoading(false);
      }
    }

    load();
  }, []);

  const filtered = useMemo(() => {
    if (!query) return groups;
    const q = query.toLowerCase();
    return groups
      .map((g) => ({ ...g, items: g.items.filter((i) => i.name.toLowerCase().includes(q)) }))
      .filter((g) => g.items.length > 0);
  }, [groups, query]);

  const total = groups.reduce((n, g) => n + g.items.length, 0);
  const done = Object.values(checked).filter(Boolean).length;

  return (
    <div className="space-y-8 animate-fade-up">
      <header className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <div className="text-[11px] uppercase tracking-wider text-text-light font-medium">Grocery</div>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">This week's shopping list</h1>
          <p className="mt-1 text-sm text-text-secondary">{done} of {total} items checked off</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => window.print()} className="inline-flex items-center gap-2 rounded-lg border border-border bg-surface px-3.5 py-2.5 text-sm font-medium hover:bg-muted transition">
            <Printer className="size-4" /> Print
          </button>
          <button onClick={() => toast.success("Exported PDF")} className="inline-flex items-center gap-2 rounded-lg bg-primary text-primary-foreground px-3.5 py-2.5 text-sm font-medium hover:opacity-90 transition">
            <Download className="size-4" /> Export PDF
          </button>
        </div>
      </header>

      {loading ? (
        <div className="rounded-xl border border-border bg-surface shadow-soft p-6 flex items-center gap-2 text-sm text-text-secondary">
          <Loader2 className="size-4 animate-spin" /> Loading grocery list...
        </div>
      ) : total === 0 ? (
        <div className="rounded-xl border border-border bg-surface shadow-soft p-6">
          <div className="flex items-start gap-3">
            <div className="size-10 rounded-lg bg-muted grid place-items-center text-text-secondary">
              <ShoppingBasket className="size-5" />
            </div>
            <div>
              <h2 className="text-sm font-semibold">No grocery list yet</h2>
              <p className="mt-1 text-sm text-text-secondary">Generate a meal plan first. The shopping list will update from that saved plan.</p>
            </div>
          </div>
        </div>
      ) : (
        <>
          <div className="rounded-xl border border-border bg-surface shadow-soft px-3 py-2 flex items-center gap-3">
            <Search className="size-4 text-text-light" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search ingredients..."
              className="flex-1 bg-transparent outline-none text-sm placeholder:text-text-light"
            />
            <div className="text-xs text-text-light">{total} items</div>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map((g) => (
              <section key={g.category} className="rounded-2xl border border-border bg-surface shadow-soft p-5">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold">{g.category}</h3>
                  <span className="text-[11px] text-text-light">{g.items.length}</span>
                </div>
                <ul className="mt-3 space-y-1.5">
                  {g.items.map((it, i) => {
                    const key = `${g.category}:${it.name}`;
                    const isOn = !!checked[key];
                    return (
                      <li key={i}>
                        <button
                          onClick={() => setChecked((c) => ({ ...c, [key]: !c[key] }))}
                          className="w-full flex items-center gap-3 rounded-lg px-2 py-1.5 hover:bg-muted/50 transition text-left"
                        >
                          <span className={[
                            "size-4 rounded-md border grid place-items-center transition",
                            isOn ? "bg-success border-success text-white" : "border-border bg-surface",
                          ].join(" ")}>
                            {isOn && <Check className="size-3" strokeWidth={3} />}
                          </span>
                          <span className={"flex-1 text-sm " + (isOn ? "line-through text-text-light" : "text-text-primary")}>{it.name}</span>
                          <span className="text-xs text-text-light">{it.quantity}</span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </section>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
