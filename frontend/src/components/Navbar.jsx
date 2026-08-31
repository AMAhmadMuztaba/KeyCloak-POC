import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Navbar() {
  const {
    user,
    isSuperAdmin,
    orgAdminOf,
    projectAdminOf,
    hasAnyAdminRole,
    isAdminMode,
    selectedOrg,
    selectedProject,
    getAdminRoute,
    logout,
  } = useAuth();
  const navigate = useNavigate();

  const roleBadge = isSuperAdmin
    ? { label: "Super Admin", cls: "role-badge role-super" }
    : orgAdminOf.length > 0
    ? { label: "Org Admin", cls: "role-badge role-org" }
    : projectAdminOf.length > 0
    ? { label: "Project Admin", cls: "role-badge role-project" }
    : null;

  return (
    <header className="navbar">
      <div className="navbar-left">
        <span className="navbar-logo" onClick={() => navigate("/")} role="button">
          🔐 KeyCLOAK
        </span>

        {selectedOrg && (
          <>
            <span className="breadcrumb-sep">/</span>
            <button
              className="btn-ghost breadcrumb"
              onClick={() => navigate("/select-org")}
            >
              {selectedOrg}
            </button>
          </>
        )}

        {selectedProject && (
          <>
            <span className="breadcrumb-sep">/</span>
            <button
              className="btn-ghost breadcrumb"
              onClick={() => navigate("/select-project")}
            >
              {selectedProject}
            </button>
          </>
        )}

        {isAdminMode && (
          <>
            <span className="breadcrumb-sep">/</span>
            <span className="badge badge-admin">Admin Mode</span>
          </>
        )}
      </div>

      <div className="navbar-right">
        {roleBadge && (
          <span className={roleBadge.cls}>{roleBadge.label}</span>
        )}

        {hasAnyAdminRole && (
          <button
            className="btn btn-ghost-sm"
            onClick={() => navigate(getAdminRoute())}
          >
            ⚡ Admin
          </button>
        )}

        <span className="user-chip">
          {user?.firstName || user?.username}
        </span>
        <button className="btn btn-ghost-sm" onClick={logout}>
          Sign out
        </button>
      </div>
    </header>
  );
}
