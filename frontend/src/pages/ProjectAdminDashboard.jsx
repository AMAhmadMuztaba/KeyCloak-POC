import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { apiFetch } from "../api";
import { useToast } from "../hooks/useToast";
import UserSearch from "../components/UserSearch";

export default function ProjectAdminDashboard() {
  const { token, user, projectAdminOf } = useAuth();
  const navigate = useNavigate();
  const { toast, Toasts } = useToast();
  const [activeIdx, setActiveIdx] = useState(0);
  const project = projectAdminOf[activeIdx];

  return (
    <div className="adm-page">
      {Toasts}

      <div className="adm-header">
        <div>
          <button className="btn-ghost back-btn" onClick={() => navigate("/select-org")}>
            ← Back to App
          </button>
          <h2 className="adm-title">Project Admin</h2>
          <p className="adm-sub">Logged in as <strong>{user?.username}</strong></p>
        </div>
        <span className="role-badge role-project">Project Admin</span>
      </div>

      {projectAdminOf.length === 0 ? (
        <div className="adm-empty">
          <span>📂</span>
          <p>You are not a project admin of any project.</p>
        </div>
      ) : (
        <>
          {projectAdminOf.length > 1 && (
            <div className="org-tabs">
              {projectAdminOf.map((p, i) => (
                <button
                  key={`${p.org}/${p.project}`}
                  className={`tab-btn ${activeIdx === i ? "tab-btn--active" : ""}`}
                  onClick={() => setActiveIdx(i)}
                >
                  📂 {p.org} / {p.project}
                </button>
              ))}
            </div>
          )}

          {project && (
            <ProjectMembersPanel
              key={`${project.org}/${project.project}`}
              token={token}
              org={project.org}
              projectName={project.project}
              toast={toast}
            />
          )}
        </>
      )}
    </div>
  );
}

function ProjectMembersPanel({ token, org, projectName, toast }) {
  const [members, setMembers]   = useState([]);
  const [loading, setLoading]   = useState(true);
  const [removing, setRemoving] = useState(null);
  const [adding, setAdding]     = useState(false);

  async function load() {
    setLoading(true);
    try {
      const d = await apiFetch(
        `/api/admin/project/${org}/${projectName}/members`,
        "GET", undefined, token
      );
      setMembers(d.members);
    } catch (e) {
      toast.error(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [org, projectName]);

  async function addMember(user) {
    setAdding(true);
    try {
      await apiFetch(
        `/api/admin/project/${org}/${projectName}/members/${user.id}`,
        "PUT", undefined, token
      );
      toast.success(`${user.username} added to ${projectName}`);
      await load();
    } catch (e) {
      toast.error(e.message);
    } finally {
      setAdding(false);
    }
  }

  async function removeMember(m) {
    if (!confirm(`Remove ${m.username} from ${projectName}?`)) return;
    setRemoving(m.id);
    try {
      await apiFetch(
        `/api/admin/project/${org}/${projectName}/members/${m.id}`,
        "DELETE", undefined, token
      );
      toast.success(`${m.username} removed`);
      setMembers(prev => prev.filter(x => x.id !== m.id));
    } catch (e) {
      toast.error(e.message);
    } finally {
      setRemoving(null);
    }
  }

  const memberIds = members.map(m => m.id);

  return (
    <div className="adm-section">
      <div className="project-panel-title">
        <span className="project-panel-org">{org}</span>
        <span className="project-panel-sep">/</span>
        <span className="project-panel-name">{projectName}</span>
      </div>

      <div className="adm-add-block">
        <p className="adm-block-label">Add member to <strong>{projectName}</strong></p>
        <UserSearch
          token={token}
          exclude={memberIds}
          placeholder="Search by username or email…"
          onSelect={adding ? undefined : addMember}
        />
        {adding && <p className="text-muted" style={{ fontSize: "0.82rem" }}>Adding…</p>}
      </div>

      {loading ? (
        <div className="skeleton-list">
          {[1,2,3].map(i => <div key={i} className="skeleton-row" />)}
        </div>
      ) : members.length === 0 ? (
        <div className="adm-empty adm-empty--sm">
          <span>👥</span><p>No members yet. Add one above.</p>
        </div>
      ) : (
        <div className="member-list">
          {members.map(m => (
            <div key={m.id} className="member-row">
              <span className="user-avatar">{(m.username?.[0] || "?").toUpperCase()}</span>
              <div className="member-info">
                <span className="member-name">{m.username}</span>
                <span className="member-email">{m.email}</span>
              </div>
              <button
                className="btn btn-danger btn-sm"
                disabled={removing === m.id}
                onClick={() => removeMember(m)}
              >
                {removing === m.id ? "…" : "Remove"}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
