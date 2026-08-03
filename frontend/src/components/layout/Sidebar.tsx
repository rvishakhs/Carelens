import { clsx } from "clsx";
import {
  BarChart3,
  Calendar,
  ClipboardList,
  FileStack,
  Heart,
  LayoutDashboard,
  LogOut,
  Pill,
  Settings,
  Sparkles,
  Users,
  UsersRound,
} from "lucide-react";
import { NavLink } from "react-router-dom";

import { Avatar } from "@/components/ui/Avatar";
import { useAuthStore } from "@/store/authStore";

const NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/residents", label: "Residents", icon: Users },
  { to: "/care-records", label: "Care Records", icon: ClipboardList },
  { to: "/care-plans", label: "Care Plans", icon: FileStack },
  { to: "/medications", label: "Medications", icon: Pill },
  { to: "/ai-insights", label: "AI Insights", icon: Sparkles },
  { to: "/reports", label: "Reports", icon: BarChart3 },
  { to: "/calendar", label: "Calendar", icon: Calendar },
  { to: "/staff", label: "Staff", icon: UsersRound },
  { to: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);

  return (
    <aside className="flex h-full w-64 shrink-0 flex-col bg-brand-900">
      <div className="flex items-center gap-2 px-6 py-6">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-500">
          <Heart className="h-4 w-4 text-white" fill="white" />
        </div>
        <span className="text-lg font-semibold text-white">CareLens</span>
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto px-3 scrollbar-none">
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              clsx(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                isActive ? "bg-brand-600 text-white" : "text-brand-100/80 hover:bg-brand-800 hover:text-white",
              )
            }
          >
            <Icon className="h-[18px] w-[18px]" />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-white/10 p-3">
        <div className="flex items-center gap-3 rounded-lg px-2 py-2">
          <Avatar initials={user?.initials ?? "?"} colorClass="bg-brand-400 text-brand-950" size="sm" />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-white">{user?.name}</p>
            <p className="truncate text-xs text-brand-200">{user?.role}</p>
          </div>
          <button
            onClick={logout}
            title="Log out"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-brand-200 hover:bg-brand-800 hover:text-white"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </aside>
  );
}
