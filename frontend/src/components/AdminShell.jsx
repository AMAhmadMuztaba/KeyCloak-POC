import { NavLink, Outlet } from "react-router-dom";
import { Building2, Users, Shield, LogOut } from "lucide-react";
import { useAuth } from "../context/AuthContext";

const NAV = [
  { to: "/organisations", label: "Organisations", Icon: Building2 },
  { to: "/users",         label: "Users",         Icon: Users },
  { to: "/roles",         label: "Roles",         Icon: Shield },
];

export default function AdminShell() {
  const { user, logout } = useAuth();
  const initials =
    [user?.firstName, user?.lastName]
      .filter(Boolean)
      .map((s) => s[0].toUpperCase())
      .join("") || (user?.username?.[0]?.toUpperCase() ?? "?");

  return (
    <div className="admin-shell">
      <aside className="admin-sidebar">
        <div className="sidebar-logo">
          <div className="sidebar-logo-mark">KC</div>
          <span className="sidebar-logo-name">Admin</span>
        </div>

        <nav className="sidebar-nav">
          {NAV.map(({ to, label, Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) => `sidebar-link${isActive ? " active" : ""}`}
            >
              <Icon size={15} strokeWidth={2} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-user">
          <div className="user-avatar sidebar-avatar">{initials}</div>
          <div className="sidebar-user-info">
            <p className="sidebar-user-name">
              {[user?.firstName, user?.lastName].filter(Boolean).join(" ") || user?.username}
            </p>
            <p className="sidebar-user-email">{user?.email || user?.username}</p>
          </div>
          <button className="btn-ghost" onClick={logout} title="Sign out" style={{ padding: "0.25rem" }}>
            <LogOut size={14} />
          </button>
        </div>
      </aside>

      <main className="admin-content">
        <div className="admin-content-inner">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
