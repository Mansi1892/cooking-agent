import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import {
  LayoutDashboard,
  CalendarRange,
  History,
  User,
  Settings as SettingsIcon,
  ShoppingBasket,
  Sparkles,
  Flame,
  LogOut,
  ShieldCheck,
  Coins,
  LifeBuoy,
} from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { storage } from "@/lib/storage";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, exact: true },
  { to: "/meal-plans", label: "Meal Plans", icon: CalendarRange },
  { to: "/grocery", label: "Grocery", icon: ShoppingBasket },
  { to: "/history", label: "History", icon: History },
  { to: "/profile", label: "Profile", icon: User },
  { to: "/settings", label: "Settings", icon: SettingsIcon },
  { to: "/help", label: "Help", icon: LifeBuoy },
];

export function AppSidebar() {
  const navigate = useNavigate();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const [name, setName] = useState("");
  const [goal, setGoal] = useState("");
  const [streak, setStreak] = useState(0);
  const [credits, setCredits] = useState(0);
  const [role, setRole] = useState("user");

  useEffect(() => {
    let cancelled = false;
    function syncProfile() {
      setName(storage.getUserName() || "Guest");
      setGoal(storage.getGoal() || "Maintenance");
      setStreak(storage.getStreak() || 0);
      setCredits(storage.getCredits());
      setRole(storage.getRole());
      const userId = storage.getUserId();
      if (userId) {
        api.getProfile(userId).then((result) => {
          if (cancelled) return;
          const nextCredits = Number(result.profile.credits ?? 0);
          const nextRole = result.profile.role || "user";
          const nextName = result.profile.name || storage.getUserName() || "Guest";
          const nextGoal = result.profile.goal || storage.getGoal() || "maintenance";
          storage.setUserName(nextName);
          storage.setGoal(nextGoal);
          storage.setCredits(nextCredits);
          storage.setRole(nextRole);
          setName(nextName);
          setGoal(nextGoal);
          setCredits(nextCredits);
          setRole(nextRole);
        }).catch(() => {});
        api.getStreak(userId).then((result) => {
          if (cancelled) return;
          storage.setStreak(result.streak);
          setStreak(result.streak);
        }).catch(() => {});
      }
    }

    syncProfile();
    window.addEventListener("mpa-storage-change", syncProfile);
    window.addEventListener("focus", syncProfile);
    return () => {
      cancelled = true;
      window.removeEventListener("mpa-storage-change", syncProfile);
      window.removeEventListener("focus", syncProfile);
    };
  }, [pathname]);

  const isActive = (to: string, exact?: boolean) => (exact ? pathname === to : pathname === to || pathname.startsWith(to + "/"));
  const initials = name.split(" ").map((s) => s[0]).join("").slice(0, 2).toUpperCase() || "U";
  const logout = () => {
    storage.logout();
    navigate({ to: "/login" });
  };

  return (
    <aside className="hidden md:flex w-[240px] shrink-0 flex-col border-r border-border bg-sidebar h-screen sticky top-0">
      <div className="px-5 py-5 flex items-center gap-2">
        <div className="size-9 rounded-xl hero-gradient grid place-items-center text-white shadow-glow">
          <Sparkles className="size-4.5" strokeWidth={2.25} />
        </div>
        <div className="leading-tight">
          <div className="text-[15px] font-semibold tracking-tight">Smart Meal AI</div>
          <div className="text-[11px] text-text-light">v1.0.0 · Premium</div>
        </div>
      </div>

      <nav className="flex-1 px-3 py-2 space-y-0.5">
        {NAV.map((item) => {
          const Icon = item.icon;
          const active = isActive(item.to, item.exact);
          return (
            <Link
              key={item.to}
              to={item.to}
              className={[
                "group flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-all duration-200",
                active
                  ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium"
                  : "text-text-secondary hover:bg-sidebar-accent/60 hover:text-text-primary",
              ].join(" ")}
            >
              <Icon className={"size-4 " + (active ? "text-primary" : "text-text-light group-hover:text-text-secondary")} />
              <span>{item.label}</span>
              {active && <span className="ml-auto size-1.5 rounded-full bg-primary" />}
            </Link>
          );
        })}
        {role === "admin" && (
          <Link
            to="/admin"
            className={[
              "group flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-all duration-200",
              isActive("/admin")
                ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium"
                : "text-text-secondary hover:bg-sidebar-accent/60 hover:text-text-primary",
            ].join(" ")}
          >
            <ShieldCheck className={"size-4 " + (isActive("/admin") ? "text-primary" : "text-text-light group-hover:text-text-secondary")} />
            <span>Admin</span>
            {isActive("/admin") && <span className="ml-auto size-1.5 rounded-full bg-primary" />}
          </Link>
        )}
      </nav>

      <div className="p-3">
        <div className="rounded-xl border border-sidebar-border bg-surface p-3 shadow-soft">
          <div className="flex items-center gap-3">
            <div className="size-9 rounded-full hero-gradient grid place-items-center text-white text-xs font-semibold">
              {initials}
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium truncate">{name}</div>
              <div className="text-[11px] text-text-light capitalize truncate">{goal.replace("_", " ")}</div>
            </div>
          </div>
          <div className="mt-3 flex items-center justify-between rounded-lg bg-primary-light px-2.5 py-1.5">
            <span className="text-[11px] text-primary/80 font-medium">Planning streak</span>
            <span className="text-[12px] text-primary font-semibold flex items-center gap-1">
              <Flame className="size-3" /> {streak} {streak === 1 ? "week" : "weeks"}
            </span>
          </div>
          <div className="mt-2 flex items-center justify-between rounded-lg bg-muted px-2.5 py-1.5">
            <span className="text-[11px] text-text-secondary font-medium">Credits</span>
            <span className="text-[12px] text-text-primary font-semibold flex items-center gap-1">
              <Coins className="size-3" /> {role === "admin" ? "Unlimited" : credits}
            </span>
          </div>
          <button
            onClick={logout}
            className="mt-2 w-full flex items-center justify-center gap-2 rounded-lg border border-border bg-background px-2.5 py-2 text-xs font-medium text-text-secondary hover:text-destructive hover:border-destructive/30 transition"
          >
            <LogOut className="size-3.5" /> Logout
          </button>
        </div>
      </div>
    </aside>
  );
}

export function MobileTabBar() {
  const navigate = useNavigate();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const [role, setRole] = useState(storage.getRole());
  useEffect(() => {
    function syncRole() {
      setRole(storage.getRole());
      const userId = storage.getUserId();
      if (userId) {
        api.getProfile(userId).then((result) => {
          const nextRole = result.profile.role || "user";
          storage.setRole(nextRole);
          setRole(nextRole);
        }).catch(() => {});
      }
    }
    syncRole();
    window.addEventListener("mpa-storage-change", syncRole);
    window.addEventListener("focus", syncRole);
    return () => {
      window.removeEventListener("mpa-storage-change", syncRole);
      window.removeEventListener("focus", syncRole);
    };
  }, [pathname]);
  const items = role === "admin"
    ? [
        NAV[0],
        NAV[1],
        NAV[2],
        { to: "/admin", label: "Admin", icon: ShieldCheck },
      ]
    : [
        NAV[0],
        NAV[1],
        NAV[2],
        NAV.find((item) => item.to === "/help")!,
      ];
  const logout = () => {
    storage.logout();
    navigate({ to: "/login" });
  };
  return (
    <nav className="md:hidden fixed bottom-0 inset-x-0 z-40 glass border-t border-border">
      <div className="grid grid-cols-5">
        {items.map((it) => {
          const Icon = it.icon;
          const active = it.exact ? pathname === it.to : pathname.startsWith(it.to);
          return (
            <Link key={it.to} to={it.to} className="flex flex-col items-center gap-1 py-2.5">
              <Icon className={"size-5 " + (active ? "text-primary" : "text-text-light")} />
              <span className={"text-[10px] " + (active ? "text-primary font-medium" : "text-text-light")}>{it.label}</span>
            </Link>
          );
        })}
        <button onClick={logout} className="flex flex-col items-center gap-1 py-2.5">
          <LogOut className="size-5 text-text-light" />
          <span className="text-[10px] text-text-light">Logout</span>
        </button>
      </div>
    </nav>
  );
}
