import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function DashboardPage() {
  const {
    user,
    selectedOrg,
    selectedProject,
    isSuperAdmin,
    orgAdminOf,
    projectAdminOf,
    isProjectAdminOf,
    hasAnyAdminRole,
    getAdminRoute,
  } = useAuth();
  const navigate = useNavigate();

  const isProjectAdmin = selectedOrg && selectedProject
    ? isProjectAdminOf(selectedOrg, selectedProject)
    : false;

  const roleLabel = isSuperAdmin
    ? "super-admin"
    : orgAdminOf.includes(selectedOrg)
    ? "org-admin"
    : isProjectAdmin
    ? "project-admin"
    : "user";

  const roleCls = isSuperAdmin
    ? "role-badge role-super"
    : orgAdminOf.includes(selectedOrg)
    ? "role-badge role-org"
    : isProjectAdmin
    ? "role-badge role-project"
    : "badge badge-user";

  return (
    <div className="page-container">
      <div className="dashboard-hero">
        <div className="dashboard-hero-text">
          <p className="dashboard-label">
            {selectedOrg} / {selectedProject}
          </p>
          <h2 className="page-title">Project Dashboard</h2>
          <p className="page-subtitle">
            You are logged in as <strong>{user?.username}</strong> in{" "}
            <strong>{selectedProject}</strong>.
          </p>
        </div>
        <div className="dashboard-actions">
          <button className="btn btn-secondary" onClick={() => navigate("/select-project")}>
            Switch Project
          </button>
          <button className="btn btn-secondary" onClick={() => navigate("/select-org")}>
            Switch Org
          </button>
          {hasAnyAdminRole && (
            <button className="btn btn-admin" onClick={() => navigate(getAdminRoute())}>
              ⚡ Admin Panel
            </button>
          )}
        </div>
      </div>

      <div className="info-grid">
        <div className="info-card">
          <h4>Session Info</h4>
          <dl>
            <dt>Username</dt>
            <dd>{user?.username}</dd>
            <dt>Email</dt>
            <dd>{user?.email || "—"}</dd>
            <dt>Name</dt>
            <dd>{[user?.firstName, user?.lastName].filter(Boolean).join(" ") || "—"}</dd>
            <dt>Role</dt>
            <dd><span className={roleCls}>{roleLabel}</span></dd>
          </dl>
        </div>

        <div className="info-card">
          <h4>Current Context</h4>
          <dl>
            <dt>Organisation</dt>
            <dd>{selectedOrg}</dd>
            <dt>Project</dt>
            <dd>{selectedProject}</dd>
          </dl>
        </div>

        {isProjectAdmin && (
          <div className="info-card info-card--highlight">
            <h4>Project Admin</h4>
            <p className="text-muted" style={{ fontSize: "0.875rem", marginBottom: "1rem" }}>
              You manage this project.
            </p>
            <button className="btn btn-primary" onClick={() => navigate("/project-admin")}>
              Manage Members
            </button>
          </div>
        )}

        <div className="info-card">
          <h4>Quick Links</h4>
          <ul className="quick-links">
            <li>📊 Analytics</li>
            <li>⚙️ Settings</li>
            <li>👥 Members</li>
            <li>📦 Deployments</li>
          </ul>
        </div>
      </div>

      {/* ── Security / MFA ── */}
      <div className="security-section">
        <div className="security-header">
          <div>
            <h3 className="security-title">🔐 Two-Factor Authentication</h3>
            <p className="security-sub">Add an extra layer of security to your account.</p>
          </div>
          <button className="btn btn-primary" onClick={() => navigate("/security")}>
            Manage MFA →
          </button>
        </div>
      </div>
    </div>
  );
}
