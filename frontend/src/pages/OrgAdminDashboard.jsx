import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { apiFetch } from "../api";
import { useToast } from "../hooks/useToast";
import UserSearch from "../components/UserSearch";

export default function OrgAdminDashboard() {
  const { token, user, orgAdminOf } = useAuth();
  const navigate = useNavigate();
  const { toast, Toasts } = useToast();

  const managedOrgs = orgAdminOf;
  const [activeOrg, setActiveOrg] = useState(managedOrgs[0] || "");
  const [activeTab, setActiveTab] = useState("Members");

  return (
    <div className="adm-page">
      {Toasts}

      <div className="adm-header">
        <div>
          <button className="btn-ghost back-btn" onClick={() => navigate("/select-org")}>
            ← Back to App
          </button>
          <h2 className="adm-title">Org Admin</h2>
          <p className="adm-sub">Logged in as <strong>{user?.username}</strong></p>
        </div>
        <span className="role-badge role-org">Org Admin</span>
      </div>

      {managedOrgs.length > 1 && (
        <div className="org-tabs">
          {managedOrgs.map(o => (
            <button
              key={o}
              className={`tab-btn ${activeOrg === o ? "tab-btn--active" : ""}`}
              onClick={() => { setActiveOrg(o); setActiveTab("Members"); }}
            >
              🏢 {o}
            </button>
          ))}
        </div>
      )}

      {activeOrg ? (
        <>
          <div className="tab-bar">
            {["Members", "Projects"].map(t => (
              <button key={t}
                className={`tab-btn ${activeTab === t ? "tab-btn--active" : ""}`}
                onClick={() => setActiveTab(t)}>
                {t}
              </button>
            ))}
          </div>
          <div className="tab-content">
            {activeTab === "Members"  && <MembersTab  token={token} org={activeOrg} toast={toast} />}
            {activeTab === "Projects" && <ProjectsTab token={token} org={activeOrg} toast={toast} />}
          </div>
        </>
      ) : (
        <div className="adm-empty">
          <span>🏢</span>
          <p>You are not an admin of any organisation.</p>
        </div>
      )}
    </div>
  );
}

function MembersTab({ token, org, toast }) {
  const [members, setMembers]       = useState([]);
  const [loading, setLoading]       = useState(true);
  const [removing, setRemoving]     = useState(null);
  const [adding, setAdding]         = useState(false);
  const [managingId, setManagingId] = useState(null);

  async function load() {
    setLoading(true);
    try {
      const d = await apiFetch(`/api/admin/org/${org}/members`, "GET", undefined, token);
      setMembers(d.members);
    } catch (e) {
      toast.error(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { setManagingId(null); load(); }, [org]);

  async function addMember(user) {
    setAdding(true);
    try {
      await apiFetch(`/api/admin/org/${org}/members/${user.id}`, "PUT", undefined, token);
      toast.success(`${user.username} added to ${org}`);
      await load();
    } catch (e) {
      toast.error(e.message);
    } finally {
      setAdding(false);
    }
  }

  async function removeMember(m) {
    if (!confirm(`Remove ${m.username} from ${org}?`)) return;
    setRemoving(m.id);
    try {
      await apiFetch(`/api/admin/org/${org}/members/${m.id}`, "DELETE", undefined, token);
      toast.success(`${m.username} removed from ${org}`);
      setMembers(prev => prev.filter(x => x.id !== m.id));
    } catch (e) {
      toast.error(e.message);
    } finally {
      setRemoving(null);
    }
  }

  if (managingId) {
    return (
      <OrgMemberPanel
        userId={managingId}
        org={org}
        token={token}
        toast={toast}
        onBack={() => { setManagingId(null); load(); }}
      />
    );
  }

  const memberIds = members.map(m => m.id);

  return (
    <div className="adm-section">
      <div className="adm-add-block">
        <p className="adm-block-label">Add member to <strong>{org}</strong></p>
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
                className="btn btn-secondary btn-sm"
                onClick={() => setManagingId(m.id)}
              >
                Manage →
              </button>
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

function OrgMemberPanel({ userId, org, token, toast, onBack }) {
  const [profile, setProfile]   = useState(null);
  const [allProjs, setAllProjs] = useState([]);
  const [loading, setLoading]   = useState(true);
  const [busy, setBusy]         = useState(false);

  async function load() {
    try {
      const [memberRes, projRes] = await Promise.all([
        apiFetch(`/api/admin/org/${org}/members/${userId}`, "GET", undefined, token),
        apiFetch(`/api/admin/org/${org}/projects`, "GET", undefined, token),
      ]);
      setProfile(memberRes);
      setAllProjs(projRes.projects || []);
    } catch (e) {
      toast.error(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [userId, org]);

  async function addToProject(project) {
    setBusy(true);
    try {
      await apiFetch(`/api/admin/project/${org}/${project}/members/${userId}`, "PUT", undefined, token);
      toast.success(`Added to ${project}`);
      await load();
    } catch (e) {
      toast.error(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function removeFromProject(project) {
    setBusy(true);
    try {
      await apiFetch(`/api/admin/project/${org}/${project}/members/${userId}`, "DELETE", undefined, token);
      toast.success(`Removed from ${project}`);
      await load();
    } catch (e) {
      toast.error(e.message);
    } finally {
      setBusy(false);
    }
  }

  if (loading) return (
    <div className="adm-section">
      <div className="skeleton-list">{[1,2,3].map(i => <div key={i} className="skeleton-row" />)}</div>
    </div>
  );

  const userProjects = profile?.projects || [];
  const projsNotIn   = allProjs.filter(p => !userProjects.includes(p));

  return (
    <div className="adm-section">
      <div className="panel-header">
        <button className="btn btn-ghost-sm" onClick={onBack}>← All Members</button>
        <div className="panel-user-info">
          <span className="user-avatar user-avatar--lg">
            {(profile?.username?.[0] || "?").toUpperCase()}
          </span>
          <div>
            <div className="panel-username">{profile?.username}</div>
            <div className="panel-email">{profile?.email || "—"}</div>
          </div>
        </div>
      </div>

      <div className="mgmt-card">
        <div className="mgmt-card-title">Projects in <strong>{org}</strong></div>

        <div className="project-tags" style={{ marginBottom: "0.75rem" }}>
          {userProjects.map(p => (
            <span key={p} className="proj-tag">
              <span className="proj-tag-name">📂 {p}</span>
              <button
                className="tag-remove"
                disabled={busy}
                title="Remove from project"
                onClick={() => removeFromProject(p)}
              >×</button>
            </span>
          ))}
          {userProjects.length === 0 && (
            <span className="text-muted" style={{ fontSize: "0.82rem" }}>
              Not a member of any project in {org} yet.
            </span>
          )}
        </div>

        {projsNotIn.length > 0 && (
          <select
            className="form-select"
            disabled={busy}
            value=""
            onChange={e => e.target.value && addToProject(e.target.value)}
          >
            <option value="">+ Add to project…</option>
            {projsNotIn.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
        )}

        {allProjs.length === 0 && (
          <p className="text-muted" style={{ fontSize: "0.82rem" }}>No projects in {org}.</p>
        )}
      </div>
    </div>
  );
}

function ProjectsTab({ token, org, toast }) {
  const [projects, setProjects] = useState([]);
  const [loading, setLoading]   = useState(true);
  const [name, setName]         = useState("");
  const [creating, setCreating] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const d = await apiFetch(`/api/admin/org/${org}/projects`, "GET", undefined, token);
      setProjects(d.projects || []);
    } catch (e) {
      toast.error(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function create() {
    if (!name.trim()) return;
    setCreating(true);
    try {
      await apiFetch(`/api/admin/org/${org}/projects`, "POST", { name: name.trim() }, token);
      toast.success(`Project "${name}" created in ${org}`);
      setName("");
      await load();
    } catch (e) {
      toast.error(e.message);
    } finally {
      setCreating(false);
    }
  }

  useEffect(() => { load(); }, [org]);

  return (
    <div className="adm-section">
      <div className="adm-add-block">
        <p className="adm-block-label">Create project in <strong>{org}</strong></p>
        <div className="adm-create-bar">
          <input
            className="form-input"
            placeholder="Project name…"
            value={name}
            onChange={e => setName(e.target.value)}
            onKeyDown={e => e.key === "Enter" && create()}
          />
          <button className="btn btn-primary" onClick={create} disabled={creating || !name.trim()}>
            {creating ? "Creating…" : "+ Create"}
          </button>
        </div>
      </div>

      {loading ? (
        <div className="skeleton-list">
          {[1,2].map(i => <div key={i} className="skeleton-row" />)}
        </div>
      ) : (
        <div className="project-chip-list">
          {projects.map(p => <span key={p} className="project-chip project-chip--lg">{p}</span>)}
          {projects.length === 0 && <p className="text-muted">No projects yet.</p>}
        </div>
      )}
    </div>
  );
}
