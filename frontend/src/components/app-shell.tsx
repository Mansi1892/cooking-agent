import type { ReactNode } from "react";
import { Link, useRouterState } from "@tanstack/react-router";
import { Sparkles } from "lucide-react";
import { AppSidebar, MobileTabBar } from "./app-sidebar";

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const hideChrome = pathname.startsWith("/onboarding");

  if (hideChrome) return <>{children}</>;

  return (
    <div className="min-h-screen w-full bg-background flex">
      <AppSidebar />
      <div className="flex-1 min-w-0 flex flex-col">
        <main className="flex-1 w-full">
          <div className="mx-auto w-full max-w-[1200px] px-5 sm:px-8 py-6 sm:py-10 pb-24 md:pb-12">
            {children}
          </div>
        </main>
      </div>
      <MobileTabBar />
      <Link
        to="/meal-plans"
        className="md:hidden fixed bottom-20 right-5 z-40 rounded-full hero-gradient text-white px-5 py-3 shadow-glow text-sm font-medium flex items-center gap-2"
      >
        <Sparkles className="size-4" /> Generate
      </Link>
    </div>
  );
}
