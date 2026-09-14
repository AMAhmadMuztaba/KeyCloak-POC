import { useState, useEffect, useCallback } from "react";
import { NavLink, useParams, Routes, Route, Navigate } from "react-router-dom";
import { ChevronLeft, Plus, Folder, Users, Trash2 } from "lucide-react";
import { getOrgs, createProject, getOrgMembers, getUsers, addOrgMember, removeOrgMember } from "../api";
import Drawer from "../components/Drawer";
import ConfirmModal from "../components/ConfirmModal";

// ── Projects tab ──────────────────────────────────────────────────────────────
function ProjectsTab({ org, projects, onRefresh }) {
  const [open,    setOpen]    = useState(false);
  const [name,    setName]    = useState("");
  const [formErr, setFormErr] = useState(null);
  const [saving,  setSaving]  = useState(false);

  async function handleCreate(e) {
    e.preventDefault();
    if (!name.trim()) { setFormErr("Name is required"); return; }
    setSaving(true); setFormErr(null);
    try {
      await createProject(org, name.trim());
      setOpen(false); setName(""); onRefresh();
    } catch (e) {
      setFormErr(e.message || "Failed to create project");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
        <p className="adm-hint" style={{ margin: 0 }}>Projects within this organisation.</p>
        <button className="btn btn-primary btn-sm" onClick={() => setOpen(true)}>
          <Plus size={14} /> New project
        </button>
      </div>

      {projects.length === 0 ? (
        <div className="adm-empty">
          <span>📁</span>
          <p>No projects yet. Create the first one.</p>
        </div>
      ) : (
        <div className="project-chip-list" style={{ gap: "0.5rem" }}>
          {projects.map((p) => (
            <span key={p} className="project-chip project-chip--lg">
              <Folder size={12} style={{ marginRight: "0.25rem", verticalAlign: "middle" }} />
              {p}
            </span>
          ))}
        </div>
      )}

      <Drawer
        open={open}
        onClose={() => { setOpen(false); setName(""); setFormErr(null); }}
        title="New project"
        description={`Will be created under ${org}.`}
        onSubmit={handleCreate}
        isPending={saving}
        submitLabel="Create"
      >
        <div className="form-field">
          <label className="form-label">Name <span className="req">*</span></label>
          <input
            className="form-input"
            placeholder="my-project"
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoFocus
          />
          {formErr && <p className="error-msg" style={{ marginTop: "0.25rem" }}>{formErr}</p>}
        </div>
      </Drawer>
    </>
  );
}

// ── Members tab ───────────────────────────────────────────────────────────────
function MembersTab({ org }) {
  const [members,  setMembers]  = useState([]);
  const [allUsers, setAllUsers] = useState([]);
  const [loading,  setLoading]  = useState(true);
  const [error,    setError]    = useState(null);
  const [open,     setOpen]     = useState(false);
  const [userId,   setUserId]   = useState("");
  const [saving,   setSaving]   = useState(false);
  const [formErr,  setFormErr]  = useState(null);
  const [pending,  setPending]  = useState(null); // { id, username } to remove
  const [removing, setRemoving] = useState(false);

  const loadMembers = useCallback(() => {
    setLoading(true);
    getOrgMembers(org)
      .then((d) => { setMembers(d.members || []); setError(null); })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [org]);

  useEffect(loadMembers, [loadMembers]);

  function openAdd() {
    setUserId("");
    getUsers()
      .then((d) => setAllUsers(d.users || []))
      .catch(() => setAllUsers([]));
    setOpen(true);
  }

  async function handleAdd(e) {
    e.preventDefault();
    if (!userId) { setFormErr("Select a user"); return; }
    setSaving(true); setFormErr(null);
    try {
      await addOrgMember(org, userId);
      setOpen(false); loadMembers();
    } catch (e) {
      setFormErr(e.message || "Failed to add member");
    } finally {
      setSaving(false);
    }
  }

  async function handleRemove() {
    setRemoving(true);
    try {
      await removeOrgMember(org, pending.id);
      setPending(null); loadMembers();
    } catch (e) {
      setError(e.message);
    } finally {
      setRemoving(false);
    }
  }

  const memberIds = new Set(members.map((m) => m.id));
  const available = allUsers.filter((u) => !memberIds.has(u.id));

  const initials = (m) =>
    [m.firstName, m.lastName].filter(Boolean).map((s) => s[0].toUpperCase()).join("") ||
    (m.username?.[0]?.toUpperCase() ?? "?");

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
        <p className="adm-hint" style={{ margin: 0 }}>Users who belong to this organisation.</p>
        <button className="btn btn-primary btn-sm" onClick={openAdd}>
          <Plus size={14} /> Add member
        </button>
      </div>

      {error && <p className="error-msg">{error}</p>}

      {loading ? (
        Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="skeleton-row" style={{ marginBottom: "0.4rem" }} />
        ))
      ) : members.length === 0 ? (
        <div className="adm-empty">
          <span>👤</span>
          <p>No members yet.</p>
        </div>
      ) : (
        <div className="member-list">
          {members.map((m) => (
            <div key={m.id} className="member-row">
              <div className="user-avatar">{initials(m)}</div>
              <div className="member-info">
                <span className="member-name">
                  {[m.firstName, m.lastName].filter(Boolean).join(" ") || m.username}
                </span>
                <span className="member-email">{m.email || m.username}</span>
              </div>
              <button
                className="btn-ghost btn-ghost-sm"
                onClick={() => setPending(m)}
                title="Remove from org"
              >
                <Trash2 size={13} />
              </button>
            </div>
          ))}
        </div>
      )}

      <Drawer
        open={open}
        onClose={() => { setOpen(false); setFormErr(null); }}
        title="Add member"
        description={`Add an existing user to ${org}.`}
        onSubmit={handleAdd}
        isPending={saving}
        submitLabel="Add"
      >
        <div className="form-field">
          <label className="form-label">User <span className="req">*</span></label>
          <select className="form-select" value={userId} onChange={(e) => setUserId(e.target.value)}>
            <option value="">Select a user…</option>
            {available.map((u) => (
              <option key={u.id} value={u.id}>
                {[u.firstName, u.lastName].filter(Boolean).join(" ") || u.username} ({u.username})
              </option>
            ))}
          </select>
          {formErr && <p className="error-msg" style={{ marginTop: "0.25rem" }}>{formErr}</p>}
        </div>
      </Drawer>

      <ConfirmModal
        open={pending !== null}
        title={`Remove "${pending?.username ?? pending?.firstName}" from ${org}?`}
        body="They will lose access to all projects in this organisation."
        confirmLabel="Remove"
        danger
        isPending={removing}
        onConfirm={handleRemove}
        onClose={() => setPending(null)}
      />
    </>
  );
}

// ── Org detail shell ──────────────────────────────────────────────────────────
export default function OrgDetailPage() {
  const { org } = useParams();
  const [orgData,  setOrgData]  = useState(null);
  const [loading,  setLoading]  = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    getOrgs()
      .then((d) => setOrgData((d.orgs || []).find((o) => o.name === org) ?? null))
      .finally(() => setLoading(false));
  }, [org]);

  useEffect(load, [load]);

  return (
    <>
      <div>
        <NavLink to="/organisations" className="back-link">
          <ChevronLeft size={14} /> Organisations
        </NavLink>
        <div className="adm-header" style={{ marginBottom: 0 }}>
          <div>
            <h1 className="adm-title">{org}</h1>
            {!loading && (
              <p className="adm-sub">
                {orgData?.projects?.length ?? 0} project{orgData?.projects?.length !== 1 ? "s" : ""}
              </p>
            )}
          </div>
        </div>
      </div>

      <div className="tab-bar">
        <NavLink to="projects" className={({ isActive }) => `tab-nav-link${isActive ? " active" : ""}`}>
          <Folder size={13} /> Projects
        </NavLink>
        <NavLink to="members" className={({ isActive }) => `tab-nav-link${isActive ? " active" : ""}`}>
          <Users size={13} /> Members
        </NavLink>
      </div>

      <Routes>
        <Route index element={<Navigate to="projects" replace />} />
        <Route path="projects" element={
          <ProjectsTab org={org} projects={orgData?.projects ?? []} onRefresh={load} />
        } />
        <Route path="members" element={<MembersTab org={org} />} />
      </Routes>
    </>
  );
}
