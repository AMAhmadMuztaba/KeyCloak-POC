import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function AdminDashboardPage() {
  const { user, orgs, projectsForOrg, selectOrg, selectProject } = useAuth();
  const navigate = useNavigate();

  function enterProject(org, project) {
    selectOrg(org);
    selectProject(project);
    navigate("/dashboard");
  }

  return (
    <div className="page-container">
      <div className="admin-hero">
        <div>
          <div className="admin-hero-badge">⚡ Admin Mode</div>
          <h2 className="page-title">Admin Dashboard</h2>
          <p className="page-subtitle">
            Full visibility across all organisations and projects.
          </p>
        </div>
        <button
          className="btn btn-secondary"
          onClick={() => navigate("/select-org")}
        >
          ← Back to Org Select
        </button>
      </div>

      <div className="info-card" style={{ marginBottom: "2rem" }}>
        <h4>Admin Session</h4>
        <dl>
          <dt>Username</dt>
          <dd>{user?.username}</dd>
          <dt>Email</dt>
          <dd>{user?.email || "—"}</dd>
          <dt>Access Level</dt>
          <dd><span className="badge badge-admin">Administrator</span></dd>
        </dl>
      </div>

      <h3 className="section-title">All Organisations & Projects</h3>

      <div className="admin-org-list">
        {orgs.map((org) => {
          const projects = projectsForOrg(org);
          return (
            <div key={org} className="admin-org-card">
              <div className="admin-org-header">
                <span className="admin-org-icon">🏢</span>
                <h4 className="admin-org-name">{org}</h4>
                <span className="badge badge-user">
                  {projects.length} project{projects.length !== 1 ? "s" : ""}
                </span>
              </div>

              <div className="admin-project-list">
                {projects.length === 0 ? (
                  <p className="text-muted" style={{ padding: "0.5rem 1rem" }}>
                    No projects
                  </p>
                ) : (
                  projects.map((project) => (
                    <div key={project} className="admin-project-row">
                      <span className="admin-project-icon">📂</span>
                      <span className="admin-project-name">{project}</span>
                      <button
                        className="btn btn-sm btn-secondary"
                        onClick={() => enterProject(org, project)}
                      >
                        Enter
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div className="admin-actions-panel">
        <h3 className="section-title">Admin Actions</h3>
        <div className="admin-action-grid">
          {[
            { icon: "👥", label: "Manage Users", desc: "Add / remove org members" },
            { icon: "🏢", label: "Manage Orgs",  desc: "Create new organisations" },
            { icon: "📂", label: "Manage Projects", desc: "Configure projects" },
            { icon: "🔑", label: "Keycloak Admin", desc: "Open Keycloak console",
              href: "http://localhost:8080" },
          ].map(({ icon, label, desc, href }) =>
            href ? (
              <a
                key={label}
                className="admin-action-card"
                href={href}
                target="_blank"
                rel="noreferrer"
              >
                <span className="admin-action-icon">{icon}</span>
                <span className="admin-action-label">{label}</span>
                <span className="admin-action-desc">{desc}</span>
              </a>
            ) : (
              <div key={label} className="admin-action-card">
                <span className="admin-action-icon">{icon}</span>
                <span className="admin-action-label">{label}</span>
                <span className="admin-action-desc">{desc}</span>
              </div>
            )
          )}
        </div>
      </div>
    </div>
  );
}
