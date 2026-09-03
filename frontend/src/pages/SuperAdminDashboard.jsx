import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { apiFetch } from "../api";
import { useToast } from "../hooks/useToast";
import UserSearch from "../components/UserSearch";

const TABS = ["Organizations", "Users", "Roles", "Authentication"];

const MEMBERSHIP_APIS = [
  { key: "org:members:read",       label: "Read Org Members",      method: "GET",        path: "/api/admin/org/:org/members" },
  { key: "org:members:add",        label: "Add Org Member",        method: "PUT",        path: "/api/admin/org/:org/members/:userId" },
  { key: "org:members:remove",     label: "Remove Org Member",     method: "DELETE",     path: "/api/admin/org/:org/members/:userId" },
  { key: "project:members:read",   label: "Read Project Members",  method: "GET",        path: "/api/admin/project/:org/:project/members" },
  { key: "project:members:add",    label: "Add Project Member",    method: "PUT",        path: "/api/admin/project/:org/:project/members/:userId" },
  { key: "project:members:remove", label: "Remove Project Member", method: "DELETE",     path: "/api/admin/project/:org/:project/members/:userId" },
  { key: "users:list",             label: "List Users",            method: "GET",        path: "/api/admin/super/users" },
  { key: "users:create",           label: "Create User",           method: "POST",       path: "/api/admin/super/users" },
  { key: "users:groups",           label: "Manage User Groups",    method: "PUT/DELETE", path: "/api/admin/super/users/:userId/groups" },
  { key: "users:roles",            label: "Manage User Roles",     method: "POST/DELETE",path: "/api/admin/super/users/:userId/roles" },
  { key: "orgs:list",              label: "List Organisations",    method: "GET",        path: "/api/admin/super/orgs" },
  { key: "orgs:create",            label: "Create Organisation",   method: "POST",       path: "/api/admin/super/orgs" },
  { key: "projects:create",        label: "Create Project",        method: "POST",       path: "/api/admin/super/orgs/:org/projects" },
  { key: "roles:list",             label: "List Roles",            method: "GET",        path: "/api/admin/super/roles" },
  { key: "roles:create",           label: "Create Role",           method: "POST",       path: "/api/admin/super/roles" },
];

export default function SuperAdminDashboard() {
  const { token, user } = useAuth();
  const navigate        = useNavigate();
  const [tab, setTab]   = useState("Organizations");
  const { toast, Toasts } = useToast();

  return (
    <div className="adm-page">
      {Toasts}

      <div className="adm-header">
        <div>
          <button className="btn-ghost back-btn" onClick={() => navigate("/select-org")}>
            ← Back to App
          </button>
          <h2 className="adm-title">Super Admin</h2>
          <p className="adm-sub">Logged in as <strong>{user?.username}</strong></p>
        </div>
        <span className="role-badge role-super">Super Admin</span>
      </div>

      <div className="tab-bar">
        {TABS.map(t => (
          <button key={t} className={`tab-btn ${tab === t ? "tab-btn--active" : ""}`}
            onClick={() => setTab(t)}>{t}</button>
        ))}
      </div>

      <div className="tab-content">
        {tab === "Organizations" && <OrgsTab token={token} toast={toast} />}
        {tab === "Users"         && <UsersTab token={token} toast={toast} />}
        {tab === "Roles"         && <RolesTab token={token} toast={toast} />}
        {tab === "Authentication" && <AuthTab token={token} />}
      </div>
    </div>
  );
}

// ── Organizations ─────────────────────────────────────────────────────────────
function OrgsTab({ token, toast }) {
  const [orgs, setOrgs]         = useState([]);
  const [loading, setLoading]   = useState(true);
  const [newOrg, setNewOrg]     = useState("");
  const [creating, setCreating] = useState(false);
  const [addProj, setAddProj]   = useState({});  // orgName → draft name
  const [addingProj, setAddingProj] = useState(null);

  async function load() {
    setLoading(true);
    try {
      const d = await apiFetch("/api/admin/super/orgs", "GET", undefined, token);
      setOrgs(d.orgs);
    } catch (e) {
      toast.error(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function createOrg() {
    const name = newOrg.trim();
    if (!name) return;
    setCreating(true);
    try {
      await apiFetch("/api/admin/super/orgs", "POST", { name }, token);
      setNewOrg("");
      toast.success(`Organisation "${name}" created`);
      await load();
    } catch (e) {
      toast.error(e.message);
    } finally {
      setCreating(false);
    }
  }

  async function createProject(org) {
    const name = (addProj[org] || "").trim();
    if (!name) return;
    setAddingProj(org);
    try {
      await apiFetch(`/api/admin/super/orgs/${org}/projects`, "POST", { name }, token);
      setAddProj(p => ({ ...p, [org]: "" }));
      toast.success(`Project "${name}" added to ${org}`);
      await load();
    } catch (e) {
      toast.error(e.message);
    } finally {
      setAddingProj(null);
    }
  }

  return (
    <div className="adm-section">
      {/* Create org */}
      <div className="adm-create-bar">
        <input
          className="form-input"
          placeholder="New organisation name…"
          value={newOrg}
          onChange={e => setNewOrg(e.target.value)}
          onKeyDown={e => e.key === "Enter" && createOrg()}
        />
        <button className="btn btn-primary" onClick={createOrg} disabled={creating || !newOrg.trim()}>
          {creating ? <span className="btn-spinner" /> : null}
          {creating ? "Creating…" : "+ Create Org"}
        </button>
      </div>

      {loading ? (
        <div className="skeleton-list">
          {[1,2,3].map(i => <div key={i} className="skeleton-card" />)}
        </div>
      ) : orgs.length === 0 ? (
        <div className="adm-empty">
          <span>🏢</span>
          <p>No organisations yet. Create one above.</p>
        </div>
      ) : (
        <div className="org-grid">
          {orgs.map(org => (
            <div key={org.name} className="org-card">
              <div className="org-card-head">
                <div className="org-icon">🏢</div>
                <div>
                  <div className="org-name">{org.name}</div>
                  <div className="org-stat">{org.projects.length} project{org.projects.length !== 1 ? "s" : ""}</div>
                </div>
              </div>

              <div className="org-projects">
                {org.projects.map(p => (
                  <span key={p} className="project-chip">{p}</span>
                ))}
              </div>

              <div className="org-add-project">
                <input
                  className="form-input form-input--sm"
                  placeholder="New project name…"
                  value={addProj[org.name] || ""}
                  onChange={e => setAddProj(prev => ({ ...prev, [org.name]: e.target.value }))}
                  onKeyDown={e => e.key === "Enter" && createProject(org.name)}
                />
                <button
                  className="btn btn-secondary btn-sm"
                  disabled={addingProj === org.name || !(addProj[org.name] || "").trim()}
                  onClick={() => createProject(org.name)}
                >
                  {addingProj === org.name ? "Adding…" : "+ Project"}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Users ─────────────────────────────────────────────────────────────────────
const EMPTY_FORM = { username: "", email: "", firstName: "", lastName: "", password: "" };

function parseUserGroups(groups) {
  const pts = (g) => g.split("/").filter(Boolean);
  const userOrgs       = [...new Set(groups.filter(g => pts(g).length === 1).map(g => pts(g)[0]))];
  const isOrgAdmin     = (org)          => groups.includes(`/${org}/admins`);
  const projectsInOrg  = (org)          => groups.filter(g => pts(g).length === 2 && pts(g)[0] === org && pts(g)[1] !== "admins").map(g => pts(g)[1]);
  const isProjectAdmin = (org, project) => groups.includes(`/${org}/${project}/admins`);
  return { userOrgs, isOrgAdmin, projectsInOrg, isProjectAdmin };
}

function UsersTab({ token, toast }) {
  const [users, setUsers]         = useState([]);
  const [search, setSearch]       = useState("");
  const [loadingUsers, setLU]     = useState(true);
  const [allOrgs, setAllOrgs]     = useState([]);
  const [allRoles, setAllRoles]   = useState([]);
  const [managingId, setManaging] = useState(null);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm]           = useState(EMPTY_FORM);
  const [creating, setCreating]   = useState(false);

  async function loadUsers(q = "") {
    setLU(true);
    try {
      const d = await apiFetch(`/api/admin/super/users${q ? `?search=${encodeURIComponent(q)}` : ""}`, "GET", undefined, token);
      setUsers(d.users || []);
    } catch (e) { toast.error(e.message); }
    finally { setLU(false); }
  }

  useEffect(() => {
    Promise.all([
      loadUsers(),
      apiFetch("/api/admin/super/orgs",  "GET", undefined, token).then(d => setAllOrgs(d.orgs  || [])),
      apiFetch("/api/admin/super/roles", "GET", undefined, token).then(d => setAllRoles(d.roles || [])),
    ]);
  }, []);

  const setF = (k) => (e) => setForm(p => ({ ...p, [k]: e.target.value }));

  async function createUser(e) {
    e.preventDefault();
    if (!form.username.trim() || !form.password.trim()) { toast.error("Username and password are required"); return; }
    setCreating(true);
    try {
      await apiFetch("/api/admin/super/users", "POST", {
        username:  form.username.trim(),
        email:     form.email.trim()     || undefined,
        firstName: form.firstName.trim() || undefined,
        lastName:  form.lastName.trim()  || undefined,
        password:  form.password,
      }, token);
      toast.success(`User "${form.username}" created`);
      setForm(EMPTY_FORM);
      setShowCreate(false);
      loadUsers(search);
    } catch (e) { toast.error(e.message); }
    finally { setCreating(false); }
  }

  const displayed = search
    ? users.filter(u => u.username?.toLowerCase().includes(search.toLowerCase()) || u.email?.toLowerCase().includes(search.toLowerCase()))
    : users;

  if (managingId) {
    return (
      <UserManagePanel
        key={managingId}
        userId={managingId}
        token={token}
        toast={toast}
        allOrgs={allOrgs}
        allRoles={allRoles}
        onBack={() => { setManaging(null); loadUsers(search); }}
      />
    );
  }

  return (
    <div className="adm-section">
      {/* Create user form */}
      <div className="adm-add-block">
        <div className="block-header-row">
          <p className="adm-block-label" style={{ margin: 0 }}>Create a new user</p>
          <button className="btn btn-secondary btn-sm" onClick={() => setShowCreate(v => !v)}>
            {showCreate ? "Cancel" : "+ New User"}
          </button>
        </div>
        {showCreate && (
          <form className="create-user-form" onSubmit={createUser} autoComplete="off">
            <div className="form-row">
              <div className="form-field">
                <label className="form-label">Username <span className="req">*</span></label>
                <input className="form-input" placeholder="e.g. john.doe" value={form.username} onChange={setF("username")} required />
              </div>
              <div className="form-field">
                <label className="form-label">Password <span className="req">*</span></label>
                <input className="form-input" type="password" placeholder="Initial password" value={form.password} onChange={setF("password")} required />
              </div>
            </div>
            <div className="form-row">
              <div className="form-field">
                <label className="form-label">First name</label>
                <input className="form-input" placeholder="First" value={form.firstName} onChange={setF("firstName")} />
              </div>
              <div className="form-field">
                <label className="form-label">Last name</label>
                <input className="form-input" placeholder="Last" value={form.lastName} onChange={setF("lastName")} />
              </div>
            </div>
            <div className="form-field">
              <label className="form-label">Email</label>
              <input className="form-input" type="email" placeholder="user@example.com" value={form.email} onChange={setF("email")} />
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <button className="btn btn-primary" type="submit" disabled={creating}>
                {creating ? "Creating…" : "Create User"}
              </button>
            </div>
          </form>
        )}
      </div>

      {/* User list */}
      <div className="user-list-search">
        <input
          className="form-input"
          placeholder="Filter by username or email…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        <button className="btn btn-secondary btn-sm" onClick={() => loadUsers(search)}>Search KC</button>
      </div>

      {loadingUsers ? (
        <div className="skeleton-list">{[1,2,3,4].map(i => <div key={i} className="skeleton-row" />)}</div>
      ) : displayed.length === 0 ? (
        <div className="adm-empty adm-empty--sm"><span>👤</span><p>No users found.</p></div>
      ) : (
        <div className="user-list">
          {displayed.map(u => (
            <div key={u.id} className="user-list-row">
              <span className="user-avatar">{(u.username?.[0] || "?").toUpperCase()}</span>
              <div className="member-info">
                <span className="member-name">{u.username}</span>
                <span className="member-email">{u.email || "—"}</span>
              </div>
              <button className="btn btn-secondary btn-sm" onClick={() => setManaging(u.id)}>
                Manage →
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Full User Management Panel ─────────────────────────────────────────────────
function UserManagePanel({ userId, token, toast, allOrgs, allRoles, onBack }) {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy]       = useState(false);

  async function reload() {
    try {
      const d = await apiFetch(`/api/admin/super/users/${userId}`, "GET", undefined, token);
      setProfile(d);
    } catch (e) { toast.error(e.message); }
    finally { setLoading(false); }
  }

  useEffect(() => { reload(); }, []);

  async function act(fn, successMsg) {
    setBusy(true);
    try {
      await fn();
      if (successMsg) toast.success(successMsg);
      await reload();
    } catch (e) { toast.error(e.message); }
    finally { setBusy(false); }
  }

  const addToGroup = (path) => act(() => apiFetch(`/api/admin/super/users/${userId}/groups`, "POST",   { path }, token));
  const addRole    = (name) => act(() => apiFetch(`/api/admin/super/users/${userId}/roles`,  "POST",   { name }, token), `Role "${name}" added`);
  const removeRole = (name) => act(() => apiFetch(`/api/admin/super/users/${userId}/roles/${name}`, "DELETE", undefined, token), `Role "${name}" removed`);

  async function leaveOrg(org) {
    const orgGroups = (profile.groups || []).filter(g => g === `/${org}` || g.startsWith(`/${org}/`));
    setBusy(true);
    try {
      for (const path of orgGroups) {
        await apiFetch(`/api/admin/super/users/${userId}/groups`, "DELETE", { path }, token).catch(() => null);
      }
      toast.success(`Removed from ${org}`);
      await reload();
    } catch (e) { toast.error(e.message); }
    finally { setBusy(false); }
  }

  async function removeFromProject(org, project) {
    setBusy(true);
    try {
      // silently clean up the project-admins subgroup too if present
      await apiFetch(`/api/admin/super/users/${userId}/groups`, "DELETE", { path: `/${org}/${project}/admins` }, token).catch(() => null);
      await apiFetch(`/api/admin/super/users/${userId}/groups`, "DELETE", { path: `/${org}/${project}` }, token);
      await reload();
    } catch (e) { toast.error(e.message); }
    finally { setBusy(false); }
  }

  if (loading || !profile) return (
    <div className="adm-section">
      <div className="skeleton-list">{[1,2,3].map(i => <div key={i} className="skeleton-card" />)}</div>
      {!loading && !profile && (
        <div style={{ textAlign: "center", padding: "1rem" }}>
          <p style={{ color: "var(--danger)", fontSize: "0.875rem" }}>Failed to load user profile.</p>
          <button className="btn btn-secondary btn-sm" style={{ marginTop: "0.5rem" }} onClick={onBack}>← Back</button>
        </div>
      )}
    </div>
  );

  const { userOrgs, projectsInOrg } = parseUserGroups(profile?.groups || []);

  const currentRoleNames = (profile?.roles || []).map(r => r.name);
  const availableRoles   = allRoles.filter(r => !currentRoleNames.includes(r.name));
  const orgsNotIn        = allOrgs.filter(o => !userOrgs.includes(o.name));

  return (
    <div className="adm-section">
      {/* Header */}
      <div className="panel-header">
        <button className="btn btn-ghost-sm" onClick={onBack}>← All Users</button>
        <div className="panel-user-info">
          <span className="user-avatar user-avatar--lg">{(profile.username?.[0] || "?").toUpperCase()}</span>
          <div>
            <div className="panel-username">{profile.username}</div>
            <div className="panel-email">{profile.email || "—"}</div>
          </div>
        </div>
      </div>

      {/* ── Roles ── */}
      <div className="mgmt-card">
        <div className="mgmt-card-title">Roles</div>
        <div className="mgmt-tags-row">
          {(profile.roles || []).map(r => (
            <span key={r.id} className="mgmt-tag">
              <span className="role-badge role-generic">{r.name}</span>
              <button className="tag-remove" disabled={busy} onClick={() => removeRole(r.name)} title="Remove role">×</button>
            </span>
          ))}
          {(profile.roles || []).length === 0 && (
            <span className="text-muted" style={{ fontSize: "0.82rem" }}>No roles assigned</span>
          )}
        </div>
        {availableRoles.length > 0 ? (
          <select className="form-select" disabled={busy}
            value="" onChange={e => e.target.value && addRole(e.target.value)}>
            <option value="">+ Assign role…</option>
            {availableRoles.map(r => <option key={r.id} value={r.name}>{r.name}</option>)}
          </select>
        ) : (
          <p className="text-muted" style={{ fontSize: "0.78rem" }}>All available roles assigned.</p>
        )}
      </div>

      {/* ── Org & Project memberships ── */}
      <div className="mgmt-card">
        <div className="mgmt-card-title">Organisations &amp; Projects</div>

        {userOrgs.length === 0 && (
          <p className="text-muted" style={{ fontSize: "0.82rem", marginBottom: "0.5rem" }}>
            Not a member of any organisation yet.
          </p>
        )}

        {userOrgs.map(org => {
          const projects   = projectsInOrg(org);
          const projsNotIn = (allOrgs.find(o => o.name === org)?.projects || []).filter(p => !projects.includes(p));

          return (
            <div key={org} className="org-membership-block">
              <div className="org-mem-header">
                <span className="org-mem-name">🏢 {org}</span>
                <button className="btn btn-danger btn-sm" disabled={busy} onClick={() => leaveOrg(org)}>
                  Leave Org
                </button>
              </div>

              <div className="org-mem-row org-mem-row--wrap">
                <span className="org-mem-label">Projects</span>
                <div className="project-tags">
                  {projects.map(p => (
                    <span key={p} className="proj-tag">
                      <span className="proj-tag-name">📂 {p}</span>
                      <button
                        className="tag-remove"
                        disabled={busy}
                        title="Remove from project"
                        onClick={() => removeFromProject(org, p)}
                      >×</button>
                    </span>
                  ))}
                  {projects.length === 0 && (
                    <span className="text-muted" style={{ fontSize: "0.8rem" }}>No projects</span>
                  )}
                </div>
                {projsNotIn.length > 0 && (
                  <select className="form-select" disabled={busy}
                    value="" onChange={e => e.target.value && addToGroup(`/${org}/${e.target.value}`)}>
                    <option value="">+ Add to project…</option>
                    {projsNotIn.map(p => <option key={p} value={p}>{p}</option>)}
                  </select>
                )}
              </div>
            </div>
          );
        })}

        {orgsNotIn.length > 0 && (
          <select className="form-select" style={{ marginTop: "0.5rem" }} disabled={busy}
            value="" onChange={e => e.target.value && addToGroup(`/${e.target.value}`)}>
            <option value="">+ Add to organisation…</option>
            {orgsNotIn.map(o => <option key={o.name} value={o.name}>{o.name}</option>)}
          </select>
        )}
      </div>
    </div>
  );
}

// ── Authentication ────────────────────────────────────────────────────────────
const KC_ACCOUNT  = "http://localhost:8080/realms/app-realm/account/";
const KC_ADMIN    = "http://localhost:8080/admin/master/console/#/app-realm";

const KNOWN_AUTHENTICATORS = [
  {
    alias: "CONFIGURE_TOTP",
    name: "Authenticator App (TOTP)",
    icon: "📱",
    desc: "Time-based one-time passwords via Google Authenticator, Authy, or any TOTP app.",
    alwaysOn: true,
    userLink:  KC_ACCOUNT,
    adminLink: `${KC_ADMIN}/authentication/flows`,
  },
  {
    alias: "webauthn-register",
    name: "WebAuthn / Security Key",
    icon: "🔑",
    desc: "Hardware security keys (YubiKey, etc.) and platform authenticators (Touch ID, Face ID).",
    alwaysOn: false,
    userLink:  KC_ACCOUNT,
    adminLink: `${KC_ADMIN}/authentication/required-actions`,
  },
  {
    alias: "webauthn-register-passwordless",
    name: "Passkeys (Passwordless)",
    icon: "🛡",
    desc: "Fully passwordless login using device biometrics or FIDO2 keys.",
    alwaysOn: false,
    userLink:  KC_ACCOUNT,
    adminLink: `${KC_ADMIN}/authentication/required-actions`,
  },
];

const IDP_META = {
  google:    { icon: "🔵", color: "var(--primary)",  label: "Google"    },
  microsoft: { icon: "🟦", color: "#0078d4",          label: "Microsoft" },
};

function AuthTab({ token }) {
  const [idps, setIdps]       = useState([]);
  const [actions, setActions] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      apiFetch("/api/admin/super/auth/idps",    "GET", undefined, token),
      apiFetch("/api/admin/super/auth/actions", "GET", undefined, token),
    ]).then(([idpRes, actRes]) => {
      setIdps(idpRes.idps || []);
      setActions(actRes.actions || []);
    }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const actionMap = Object.fromEntries(actions.map(a => [a.alias, a]));

  if (loading) {
    return (
      <div className="skeleton-list">
        {[1,2,3].map(i => <div key={i} className="skeleton-card" />)}
      </div>
    );
  }

  return (
    <div className="adm-section">

      {/* ── SSO Identity Providers ── */}
      <div className="auth-section-head">
        <div>
          <h3 className="auth-section-title">SSO Identity Providers</h3>
          <p className="auth-section-desc">
            Allow users to log in with an external identity provider.
            {" "}<a className="auth-link auth-link--muted" href={`${KC_ADMIN}/identity-providers`} target="_blank" rel="noreferrer">Keycloak Admin →</a>
          </p>
        </div>
      </div>

      {idps.length === 0 ? (
        <div className="auth-idp-empty">
          <span>🔗</span>
          <p>No identity providers configured yet.</p>
          <p className="auth-idp-empty-hint">
            Set <code>GOOGLE_CLIENT_ID</code> / <code>MICROSOFT_CLIENT_ID</code> in your <code>.env</code> and restart to enable SSO.
          </p>
          <a className="btn btn-secondary btn-sm" href={`${KC_ADMIN}/identity-providers`} target="_blank" rel="noreferrer">
            Keycloak Admin → Identity Providers
          </a>
        </div>
      ) : (
        <div className="auth-idp-grid">
          {idps.map(idp => {
            const meta = IDP_META[idp.alias] || { icon: "🔗", color: "var(--text-muted)", label: idp.displayName };
            return (
              <div key={idp.alias} className={`auth-idp-card ${idp.enabled ? "auth-idp-card--on" : "auth-idp-card--off"}`}>
                <span className="auth-idp-icon">{meta.icon}</span>
                <div className="auth-idp-info">
                  <span className="auth-idp-name">{meta.label}</span>
                  <span className="auth-idp-provider">{idp.providerId}</span>
                </div>
                <span className={`auth-status-badge ${idp.enabled ? "auth-status-badge--on" : "auth-status-badge--off"}`}>
                  {idp.enabled ? "Enabled" : "Disabled"}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* ── MFA & Authenticators ── */}
      <div className="auth-section-head" style={{ marginTop: "0.5rem" }}>
        <div>
          <h3 className="auth-section-title">MFA &amp; Authenticators</h3>
          <p className="auth-section-desc">
            Multi-factor authentication methods available to users.
            {" "}<a className="auth-link auth-link--muted" href={`${KC_ADMIN}/authentication`} target="_blank" rel="noreferrer">Keycloak Admin →</a>
          </p>
        </div>
      </div>

      <div className="auth-mfa-grid">
        {KNOWN_AUTHENTICATORS.map(a => {
          const live    = actionMap[a.alias];
          const enabled = a.alwaysOn || (live?.enabled ?? false);
          return (
            <div key={a.alias} className="auth-mfa-card">
              <div className="auth-mfa-head">
                <span className="auth-mfa-icon">{a.icon}</span>
                <div>
                  <div className="auth-mfa-name">{a.name}</div>
                  <span className={`auth-status-badge ${enabled ? "auth-status-badge--on" : "auth-status-badge--off"}`}>
                    {enabled ? "Enabled" : "Disabled"}
                    {a.alwaysOn && " (built-in)"}
                  </span>
                </div>
              </div>
              <p className="auth-mfa-desc">{a.desc}</p>
              <div className="auth-mfa-links">
                <a className="auth-link" href={a.userLink} target="_blank" rel="noreferrer">
                  User setup →
                </a>
                <a className="auth-link auth-link--muted" href={a.adminLink} target="_blank" rel="noreferrer">
                  Admin flow
                </a>
              </div>
            </div>
          );
        })}
      </div>

      {/* ── Account Self-Service ── */}
      <div className="auth-account-banner">
        <span className="auth-account-icon">👤</span>
        <div>
          <div className="auth-account-title">User Self-Service MFA</div>
          <div className="auth-account-desc">
            Users can set up TOTP, WebAuthn, and passkeys from their Keycloak account page.
          </div>
        </div>
        <a
          className="btn btn-secondary btn-sm"
          href="http://localhost:8080/realms/app-realm/account/"
          target="_blank"
          rel="noreferrer"
        >
          Account Settings →
        </a>
      </div>

    </div>
  );
}

// ── Roles ─────────────────────────────────────────────────────────────────────
function RolesTab({ token, toast }) {
  const [roles, setRoles]            = useState([]);
  const [orgs, setOrgs]              = useState([]);
  const [loading, setLoading]        = useState(true);
  const [name, setName]              = useState("");
  const [desc, setDesc]              = useState("");
  const [roleType, setRoleType]      = useState("global");
  const [orgScope, setOrgScope]      = useState("");
  const [selectedPerms, setSelPerms] = useState([]);
  const [projectScope, setProjScope] = useState([]);
  const [creating, setCreating]      = useState(false);

  async function load() {
    setLoading(true);
    try {
      const d = await apiFetch("/api/admin/super/roles", "GET", undefined, token);
      setRoles(d.roles);
    } catch (e) {
      toast.error(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    apiFetch("/api/admin/super/orgs", "GET", undefined, token)
      .then(d => setOrgs(d.orgs || []))
      .catch(() => {});
  }, []);

  function togglePerm(key) {
    setSelPerms(prev => prev.includes(key) ? prev.filter(k => k !== key) : [...prev, key]);
  }

  function toggleProjectScope(val) {
    setProjScope(prev => prev.includes(val) ? prev.filter(v => v !== val) : [...prev, val]);
  }

  async function create() {
    if (!name.trim()) return;
    setCreating(true);
    try {
      await apiFetch("/api/admin/super/roles", "POST", {
        name:         name.trim(),
        description:  desc.trim(),
        roleType,
        orgScope:     roleType === "org" ? orgScope || undefined : undefined,
        permissions:  selectedPerms,
        projectScope,
      }, token);
      setName(""); setDesc(""); setRoleType("global"); setOrgScope(""); setSelPerms([]); setProjScope([]);
      toast.success(`Role "${name}" created`);
      await load();
    } catch (e) {
      toast.error(e.message);
    } finally {
      setCreating(false);
    }
  }

  // Projects available in the picker – filtered by orgScope when in org mode
  const scopeOrgs = (roleType === "org" && orgScope)
    ? orgs.filter(o => o.name === orgScope)
    : orgs;

  const globalRoles = roles.filter(r => r.roleType === "global" || !r.roleType);
  const orgRoles    = roles.filter(r => r.roleType === "org");

  function methodBadgeStyle(method) {
    const m = method.split("/")[0];
    if (m === "GET")    return { background: "rgba(16,185,129,0.18)",  color: "#6ee7b7"  };
    if (m === "POST")   return { background: "rgba(99,102,241,0.18)",  color: "#a5b4fc"  };
    if (m === "PUT")    return { background: "rgba(245,158,11,0.18)",  color: "#fcd34d"  };
    if (m === "DELETE") return { background: "rgba(239,68,68,0.18)",   color: "#fca5a5"  };
    return { background: "rgba(148,163,184,0.15)", color: "#94a3b8" };
  }

  return (
    <div className="adm-section">
      {/* ── System Roles (built-in, read-only) ── */}
      <div className="system-roles-section">
        <div className="system-roles-title">
          <span>🔒 System Roles</span>
          <span className="system-roles-badge">Built-in</span>
        </div>
        <p className="system-roles-desc">
          These roles are built into the platform and cannot be modified or deleted.
          Every authenticated user is automatically a <strong>User</strong>.
        </p>
        <div className="system-roles-grid">
          {[
            { name: "Super Admin", icon: "⚡", badge: "role-super",   desc: "Full access to all organisations, projects, users, and system configuration." },
            { name: "Org Admin",   icon: "🏢", badge: "role-org",     desc: "Manages members and projects within a specific organisation." },
            { name: "Project Admin", icon: "📂", badge: "role-proj",  desc: "Manages members within a specific project inside an organisation." },
            { name: "User",        icon: "👤", badge: "role-user",    desc: "Default role for every authenticated user. Grants access to assigned orgs and projects." },
          ].map(r => (
            <div key={r.name} className="system-role-card">
              <div className="system-role-header">
                <span className="system-role-icon">{r.icon}</span>
                <span className={`role-badge ${r.badge}`}>{r.name}</span>
              </div>
              <p className="system-role-desc">{r.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* ── Create Role Panel ── */}
      <div className="adm-add-block">
        <p className="adm-block-label">Create a new role</p>

        <div className="form-row">
          <div className="form-field">
            <label className="form-label">Role name <span className="req">*</span></label>
            <input
              className="form-input"
              placeholder="e.g. editor"
              value={name}
              onChange={e => setName(e.target.value)}
              onKeyDown={e => e.key === "Enter" && create()}
            />
          </div>
          <div className="form-field">
            <label className="form-label">Description</label>
            <input
              className="form-input"
              placeholder="Optional description"
              value={desc}
              onChange={e => setDesc(e.target.value)}
              onKeyDown={e => e.key === "Enter" && create()}
            />
          </div>
        </div>

        {/* Role type toggle */}
        <div className="form-field">
          <label className="form-label">Role type</label>
          <div className="role-type-row">
            <button
              type="button"
              className={`role-type-btn ${roleType === "global" ? "role-type-btn--active" : ""}`}
              onClick={() => setRoleType("global")}
            >
              🌐 Global Role
            </button>
            <button
              type="button"
              className={`role-type-btn ${roleType === "org" ? "role-type-btn--active role-type-btn--active-org" : ""}`}
              onClick={() => setRoleType("org")}
            >
              🏢 Organizational Role
            </button>
          </div>
          <p style={{ fontSize: "0.78rem", color: "var(--text-muted)", marginTop: "0.3rem" }}>
            {roleType === "global"
              ? "Applies system-wide across all organisations and projects."
              : "Scoped to a specific organisation."}
          </p>
        </div>

        {/* Org scope – only for org roles */}
        {roleType === "org" && (
          <div className="form-field">
            <label className="form-label">Organisation scope</label>
            <select
              className="form-select"
              value={orgScope}
              onChange={e => setOrgScope(e.target.value)}
            >
              <option value="">— Select organisation —</option>
              {orgs.map(o => <option key={o.name} value={o.name}>{o.name}</option>)}
            </select>
          </div>
        )}

        {/* API permissions grid */}
        <div className="form-field">
          <label className="form-label">
            API Permissions — Membership APIs
            <span style={{ marginLeft: "0.5rem", color: "var(--text-muted)" }}>
              {selectedPerms.length > 0 ? `(${selectedPerms.length} selected)` : ""}
            </span>
          </label>
          <div className="perm-section">
            <div className="perm-section-title">Membership &amp; Administration APIs</div>
            <div className="perm-grid">
              {MEMBERSHIP_APIS.map(api => {
                const checked = selectedPerms.includes(api.key);
                const mStyle  = methodBadgeStyle(api.method);
                return (
                  <label key={api.key} className={`perm-item${checked ? " perm-item--checked" : ""}`}>
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => togglePerm(api.key)}
                    />
                    <div>
                      <div className="perm-item-label">{api.label}</div>
                      <div className="perm-item-meta">
                        <span className="perm-method-badge" style={mStyle}>{api.method}</span>
                        {api.path}
                      </div>
                    </div>
                  </label>
                );
              })}
            </div>
          </div>
        </div>

        {/* Project Scope */}
        <div className="form-field">
          <label className="form-label">
            Project Scope
            <span style={{ marginLeft: "0.5rem", color: "var(--text-muted)" }}>
              {projectScope.length > 0
                ? `(${projectScope.length} project${projectScope.length !== 1 ? "s" : ""} selected)`
                : "(all projects)"}
            </span>
          </label>
          <p style={{ fontSize: "0.78rem", color: "var(--text-muted)", marginBottom: "0.5rem" }}>
            Leave empty to allow access to all projects. Select specific projects to restrict access.
          </p>
          {scopeOrgs.some(o => o.projects.length > 0) ? (
            <div className="project-scope-picker">
              {scopeOrgs.map(org =>
                org.projects.length === 0 ? null : (
                  <div key={org.name} className="scope-org-group">
                    <div className="scope-org-label">🏢 {org.name}</div>
                    <div className="scope-project-list">
                      {org.projects.map(p => {
                        const val     = `${org.name}/${p}`;
                        const checked = projectScope.includes(val);
                        return (
                          <label key={val} className={`scope-project-item${checked ? " scope-project-item--checked" : ""}`}>
                            <input
                              type="checkbox"
                              checked={checked}
                              onChange={() => toggleProjectScope(val)}
                            />
                            📂 {p}
                          </label>
                        );
                      })}
                    </div>
                  </div>
                )
              )}
            </div>
          ) : (
            <p className="scope-empty-hint">
              {roleType === "org" && !orgScope
                ? "Select an organisation above to see its projects."
                : "No projects found."}
            </p>
          )}
        </div>

        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <button className="btn btn-primary" onClick={create} disabled={creating || !name.trim()}>
            {creating ? <span className="btn-spinner" /> : null}
            {creating ? "Creating…" : "+ Create Role"}
          </button>
        </div>
      </div>

      {/* ── Role lists ── */}
      {loading ? (
        <div className="skeleton-list">
          {[1,2,3].map(i => <div key={i} className="skeleton-row" />)}
        </div>
      ) : (
        <>
          <div className="role-group">
            <div className="role-group-title">🌐 Global Roles</div>
            {globalRoles.length === 0 ? (
              <p className="text-muted" style={{ fontSize: "0.85rem" }}>No global roles yet.</p>
            ) : (
              <div className="role-list">
                {globalRoles.map(r => (
                  <div key={r.id} className="role-row role-row--expanded">
                    <div className="role-row-header">
                      <span className="role-badge role-generic">{r.name}</span>
                      <span className="role-desc">{r.description || "—"}</span>
                    </div>
                    {r.permissions && r.permissions.length > 0 && (
                      <>
                        <div className="role-detail-label">Permissions</div>
                        <div className="perm-tags">
                          {r.permissions.map(p => <span key={p} className="perm-tag">{p}</span>)}
                        </div>
                      </>
                    )}
                    {r.projectScope && r.projectScope.length > 0 && (
                      <>
                        <div className="role-detail-label">Projects</div>
                        <div className="perm-tags">
                          {r.projectScope.map(p => <span key={p} className="perm-tag perm-tag--project">📂 {p}</span>)}
                        </div>
                      </>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="role-group">
            <div className="role-group-title">🏢 Organizational Roles</div>
            {orgRoles.length === 0 ? (
              <p className="text-muted" style={{ fontSize: "0.85rem" }}>No organizational roles yet.</p>
            ) : (
              <div className="role-list">
                {orgRoles.map(r => (
                  <div key={r.id} className="role-row role-row--expanded">
                    <div className="role-row-header">
                      <span className="role-badge role-generic">{r.name}</span>
                      {r.orgScope && <span className="role-scope-tag">🏢 {r.orgScope}</span>}
                      <span className="role-desc">{r.description || "—"}</span>
                    </div>
                    {r.permissions && r.permissions.length > 0 && (
                      <>
                        <div className="role-detail-label">Permissions</div>
                        <div className="perm-tags">
                          {r.permissions.map(p => <span key={p} className="perm-tag">{p}</span>)}
                        </div>
                      </>
                    )}
                    {r.projectScope && r.projectScope.length > 0 && (
                      <>
                        <div className="role-detail-label">Projects</div>
                        <div className="perm-tags">
                          {r.projectScope.map(p => <span key={p} className="perm-tag perm-tag--project">📂 {p}</span>)}
                        </div>
                      </>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
