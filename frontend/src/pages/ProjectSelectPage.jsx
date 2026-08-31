import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function ProjectSelectPage() {
  const {
    selectedOrg,
    projectsForOrg,
    isSuperAdmin,
    isOrgAdminOf,
    isProjectAdminOf,
    getAdminRoute,
    selectProject,
    enterAdminMode,
  } = useAuth();
  const navigate = useNavigate();

  const projects = projectsForOrg(selectedOrg || "");

  function handleProject(project) {
    selectProject(project);
    navigate("/dashboard");
  }

  function handleTopAdminSkip() {
    enterAdminMode();
    navigate(getAdminRoute());
  }

  function handleProjectAdminSkip(e) {
    e.stopPropagation();
    enterAdminMode();
    navigate("/project-admin");
  }

  const isTopAdmin   = isSuperAdmin || isOrgAdminOf(selectedOrg);
  const topAdminLabel = isSuperAdmin ? "Enter as Super Admin" : `Manage ${selectedOrg}`;
  const topAdminDesc  = isSuperAdmin
    ? "Manage all organisations, users, and roles."
    : `Manage members and projects inside ${selectedOrg}.`;

  return (
    <div className="page-container">
      <div className="page-header">
        <div className="breadcrumb-row">
          <button className="btn-ghost" onClick={() => navigate("/select-org")}>
            ← {selectedOrg}
          </button>
        </div>
        <h2 className="page-title">Select a Project</h2>
        <p className="page-subtitle">
          Choose which project to enter in <strong>{selectedOrg}</strong>.
        </p>
      </div>

      {/* Skip banner for Super Admin or Org Admin */}
      {isTopAdmin && (
        <div className="admin-skip-banner">
          <div className="admin-skip-left">
            <span className="admin-skip-icon">⚡</span>
            <div>
              <p className="admin-skip-title">
                {isSuperAdmin ? "Super Admin" : "Org Admin"} Access
              </p>
              <p className="admin-skip-desc">{topAdminDesc}</p>
            </div>
          </div>
          <button className="btn btn-admin" onClick={handleTopAdminSkip}>
            {topAdminLabel}
          </button>
        </div>
      )}

      {projects.length === 0 ? (
        <div className="empty-state">
          <span className="empty-icon">📂</span>
          <p>No projects found in <strong>{selectedOrg}</strong>.</p>
        </div>
      ) : (
        <div className="card-grid">
          {projects.map((project) => {
            const isProjAdmin = !isTopAdmin && isProjectAdminOf(selectedOrg, project);
            return (
              <div
                key={project}
                className="selection-card"
                onClick={() => handleProject(project)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => e.key === "Enter" && handleProject(project)}
              >
                <div className="card-icon">📂</div>
                <div className="card-body">
                  <h3 className="card-title">{project}</h3>
                  <p className="card-meta">{selectedOrg}</p>
                </div>
                {isProjAdmin && (
                  <button
                    className="btn btn-admin btn-sm"
                    onClick={handleProjectAdminSkip}
                    title="Open Project Admin Dashboard"
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
