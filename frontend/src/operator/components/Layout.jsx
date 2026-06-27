import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { Megaphone, Inbox, ScanFace, AudioLines, LogOut } from "lucide-react";
import { cn } from "@/shared/lib/utils";
import { useAuth } from "@/shared/auth/AuthContext";

const NAV = [
  { to: "/ops", label: "Public Reports", icon: Megaphone, end: true },
  { to: "/ops/queue", label: "Review Queue", icon: Inbox },
  { to: "/ops/face", label: "Face Search", icon: ScanFace },
  { to: "/ops/voice", label: "Voice Match", icon: AudioLines },
];

export default function Layout() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();

  return (
    <div className="flex min-h-svh bg-background text-foreground">
      <aside className="sticky top-0 flex h-svh w-60 shrink-0 flex-col border-r border-sidebar-border bg-sidebar">
        <div className="flex h-14 items-center gap-2 px-4">
          <div className="grid size-7 place-items-center rounded-md bg-sig-coral text-white text-sm font-semibold">
            स
          </div>
          <div className="leading-tight">
            <p className="text-sm font-semibold tracking-tight text-sidebar-accent-foreground">SANGAM</p>
            <p className="text-[11px] text-muted-foreground">Lost &amp; Found Center</p>
          </div>
        </div>

        <nav className="flex flex-1 flex-col gap-0.5 px-3 py-3">
          <p className="px-3 pb-1.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            Operator
          </p>
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                  isActive
                    ? "bg-secondary font-semibold text-foreground"
                    : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
                )
              }
            >
              <Icon className="size-4" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-sidebar-border p-3">
          {user && (
            <div className="mb-2 flex items-center gap-2 rounded-md px-2 py-1.5">
              <div className="grid size-7 place-items-center rounded-full bg-secondary text-xs font-semibold uppercase">
                {user.name?.[0] ?? "?"}
              </div>
              <div className="min-w-0 leading-tight">
                <p className="truncate text-xs font-medium">{user.name}</p>
                <p className="text-[11px] capitalize text-muted-foreground">{user.role}</p>
              </div>
            </div>
          )}
          <button
            onClick={() => {
              signOut();
              navigate("/ops/login");
            }}
            className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-sidebar-foreground transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
          >
            <LogOut className="size-4" /> Sign out
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <main className="mx-auto w-full max-w-[1180px] px-8 py-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
