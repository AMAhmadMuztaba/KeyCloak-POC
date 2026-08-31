import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function OrgSelectPage() {
  const { user, orgs, projectsForOrg, isSuperAdmin, orgAdminOf, selectOrg, enterAdminMode } = useAuth();
  const navigate = useNavigate();

  function handleSelect(org) {
    selectOrg(org);
    navigate("/select-project");
  }

  function handleSuperAdminSkip() {
    enterAdminMode();
    navigate("/super-admin");
  }

  function handleOrgAdminSkip(org, e) {
    e.stopPropagation();
    selectOrg(org);
    enterAdminMode();
    navigate("/org-admin");
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <h2 className="page-title">
          Welcome back, {user?.firstName || user?.username} 👋
        </h2>
        <p className="page-subtitle">Select an organisation to continue.</p>
      </div>

      {isSuperAdmin && (
        <div className="admin-skip-banner">
          <div className="admin-skip-left">
            <span className="admin-skip-icon">⚡</span>
            <div>
              <p className="admin-skip-title">Super Admin Access</p>
              <p className="admin-skip-desc">Manage all organisations, users, and roles globally.</p>
            </div>
          </div>
          <button className="btn btn-admin" onClick={handleSuperAdminSkip}>
            Enter as Super Admin
          </button>
        </div>
      )}

      {orgs.length === 0 ? (
        <div className="empty-state">
          <span className="empty-icon">🏢</span>
          <p>You are not a member of any organisation yet.</p>
          <p className="text-muted">Contact your administrator.</p>
        </div>
      ) : (
        <div className="card-grid">
          {orgs.map((org) => {
            const projects = projectsForOrg(org);
            const isOrgAdmin = !isSuperAdmin && orgAdminOf.includes(org);
            return (
              <div
                key={org}
                className="selection-card"
                onClick={() => handleSelect(org)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => e.key === "Enter" && handleSelect(org)}
              >
                <div className="card-icon">🏢</div>
                <div className="card-body">
                  <h3 className="card-title">{org}</h3>
                  <p className="card-meta">
                    {projects.length} project{projects.length !== 1 ? "s" : ""}
                  </p>
                  {projects.length > 0 && (
                    <div className="card-tags">
                      {projects.slice(0, 3).map((p) => (
                        <span key={p} className="tag">{p}</span>
                      ))}
                      {projects.length > 3 && (
                        <span className="tag">+{projects.length - 3}</span>
                      )}
                    </div>
                  )}
                </div>
                {isOrgAdmin && (
                  <button
                    className="btn btn-admin btn-sm"
                    onClick={(e) => handleOrgAdminSkip(org, e)}
                    title="Open Org Admin Dashboard"
                  >
                    Manage
                  </button>
                )}
                <span className="card-arrow">→</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
