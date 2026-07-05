import { NavLink, Outlet } from "react-router-dom";
import clsx from "clsx";
import {
  LayoutDashboard,
  ListOrdered,
  Cog,
  Boxes,
  Skull,
  KeyRound,
  ScrollText,
  LogOut,
  Moon,
  Sun,
  Zap,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useProject } from "../context/ProjectContext";
import { useRealtime } from "../hooks/useRealtime";
import { useTheme } from "../hooks/useTheme";
import { Select } from "./ui/Input";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/queues", label: "Queues", icon: ListOrdered },
  { to: "/jobs", label: "Jobs", icon: Cog },
  { to: "/workers", label: "Workers", icon: Boxes },
  { to: "/dead-letter", label: "Dead Letters", icon: Skull },
  { to: "/api-keys", label: "API Keys", icon: KeyRound },
  { to: "/audit-log", label: "Audit Log", icon: ScrollText },
];

export function Layout() {
  const { user, logout } = useAuth();
  const { organization, project, projects, setProjectId } = useProject();
  const { connected } = useRealtime();
  const { theme, toggle } = useTheme();

  return (
    <div className="min-h-screen flex flex-col lg:flex-row">
      <aside className="lg:w-64 shrink-0 border-b-[3px] lg:border-b-0 lg:border-r-[3px] border-nb-ink bg-nb-paper p-4 flex lg:flex-col gap-4">
        <div className="flex items-center gap-2">
          <div className="nb-border bg-nb-yellow h-9 w-9 flex items-center justify-center shrink-0">
            <Zap size={18} strokeWidth={2.5} />
          </div>
          <div className="hidden lg:block min-w-0">
            <div className="font-black leading-tight">Job Scheduler</div>
            <div className="text-[11px] text-nb-ink/60 truncate">{organization?.name ?? "…"}</div>
          </div>
        </div>

        <nav className="flex lg:flex-col gap-1.5 flex-1 overflow-x-auto lg:overflow-visible">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                clsx(
                  "nb-border nb-shadow-sm nb-press px-3 py-2 font-bold text-sm whitespace-nowrap flex items-center gap-2",
                  isActive ? "bg-nb-yellow" : "bg-nb-paper hover:bg-nb-bg",
                )
              }
            >
              <item.icon size={16} className="shrink-0" />
              <span className="hidden lg:inline">{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="hidden lg:flex flex-col gap-2 mt-auto">
          <div className="flex items-center gap-2 text-xs font-bold">
            <span className={clsx("h-2.5 w-2.5 nb-border", connected ? "bg-nb-lime" : "bg-nb-red")} />
            {connected ? "Live" : "Reconnecting…"}
          </div>
          {projects.length > 0 && (
            <Select value={project?.id ?? ""} onChange={(e) => setProjectId(e.target.value)} className="w-full">
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </Select>
          )}
          <div className="text-xs truncate" title={user?.email}>
            {user?.email}
          </div>
          <div className="flex gap-2">
            <button
              onClick={toggle}
              title="Toggle theme"
              className="nb-border nb-shadow-sm nb-press bg-nb-paper px-3 py-2 flex items-center justify-center"
            >
              {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
            </button>
            <button
              onClick={logout}
              className="nb-border nb-shadow-sm nb-press bg-nb-paper px-3 py-2 flex-1 flex items-center justify-center gap-1.5 font-bold text-sm"
            >
              <LogOut size={15} /> Log out
            </button>
          </div>
        </div>
      </aside>

      <main className="flex-1 p-4 lg:p-8 overflow-x-hidden">
        <Outlet />
      </main>
    </div>
  );
}
