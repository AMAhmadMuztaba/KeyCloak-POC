import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Search } from "lucide-react";
import { getUsers, createUser } from "../api";
import Drawer from "../components/Drawer";

export default function UsersPage() {
  const navigate  = useNavigate();
  const [users,   setUsers]   = useState([]);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);
  const [search,  setSearch]  = useState("");
  const [open,    setOpen]    = useState(false);
  const [saving,  setSaving]  = useState(false);
  const [formErr, setFormErr] = useState(null);
  const [form,    setForm]    = useState({ username: "", firstName: "", lastName: "", email: "", password: "" });

  const load = useCallback((q = "") => {
    setLoading(true);
    getUsers(q)
      .then((d) => { setUsers(d.users || []); setError(null); })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    const t = setTimeout(() => load(search), 350);
    return () => clearTimeout(t);
  }, [search, load]);

  function set(key) {
    return (e) => setForm((f) => ({ ...f, [key]: e.target.value }));
  }

  async function handleCreate(e) {
    e.preventDefault();
    if (!form.username.trim()) { setFormErr("Username is required"); return; }
    if (!form.password)        { setFormErr("Password is required"); return; }
    setSaving(true); setFormErr(null);
    try {
      await createUser(form);
      setOpen(false);
      setForm({ username: "", firstName: "", lastName: "", email: "", password: "" });
      load(search);
    } catch (e) {
      setFormErr(e.message || "Failed to create user");
    } finally {
      setSaving(false);
    }
  }

  const initials = (u) =>
    [u.firstName, u.lastName].filter(Boolean).map((s) => s[0].toUpperCase()).join("") ||
    (u.username?.[0]?.toUpperCase() ?? "?");

  const skeletons = Array.from({ length: 5 });

  return (
    <>
      <div className="adm-header">
        <div>
          <h1 className="adm-title">Users</h1>
          <p className="adm-sub">Manage user accounts and role assignments.</p>
        </div>
        <button className="btn btn-primary btn-sm" onClick={() => setOpen(true)}>
          <Plus size={14} /> New user
        </button>
      </div>

      {error && <p className="error-msg">{error}</p>}

      <div className="search-bar">
        <div className="search-input-wrap">
          <Search size={14} className="search-icon" style={{ color: "var(--text-muted)" }} />
          <input
            className="form-input"
            placeholder="Search users…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        {!loading && (
          <span style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>
            {users.length} user{users.length !== 1 ? "s" : ""}
          </span>
        )}
      </div>

      <div className="table-card">
        <table className="admin-table">
          <thead>
            <tr>
              <th>User</th>
              <th>Username</th>
              <th>Status</th>
              <th style={{ width: 40 }} />
            </tr>
          </thead>
          <tbody>
            {loading ? (
              skeletons.map((_, i) => (
                <tr key={i}>
                  <td><div className="skeleton-row" style={{ width: "50%", height: 16 }} /></td>
                  <td><div className="skeleton-row" style={{ width: "40%", height: 16 }} /></td>
                  <td><div className="skeleton-row" style={{ width: "25%", height: 16 }} /></td>
                  <td />
                </tr>
              ))
            ) : users.length === 0 ? (
              <tr>
                <td colSpan={4}>
                  <div className="adm-empty">
                    <span>👤</span>
                    <p>{search ? "No users match that search." : "No users yet."}</p>
                  </div>
                </td>
              </tr>
            ) : (
              users.map((u) => (
                <tr
                  key={u.id}
                  style={{ cursor: "pointer" }}
                  onClick={() => navigate(`/users/${u.id}`)}
                >
                  <td>
                    <span style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <div className="user-avatar" style={{ width: 28, height: 28, fontSize: "0.72rem" }}>
                        {initials(u)}
                      </div>
                      <span style={{ fontWeight: 500 }}>
                        {[u.firstName, u.lastName].filter(Boolean).join(" ") || u.username}
                      </span>
                    </span>
                  </td>
                  <td>
                    <code style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>{u.username}</code>
                  </td>
                  <td>
                    <span className={`badge ${u.enabled !== false ? "badge-admin" : "badge-user"}`}
                      style={{ fontSize: "0.68rem" }}>
                      {u.enabled !== false ? "Active" : "Disabled"}
                    </span>
                  </td>
                  <td style={{ color: "var(--text-muted)", textAlign: "right" }}>→</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <Drawer
        open={open}
        onClose={() => { setOpen(false); setForm({ username: "", firstName: "", lastName: "", email: "", password: "" }); setFormErr(null); }}
        title="New user"
        description="Password must be 12+ chars with uppercase, lowercase, number, and symbol."
        onSubmit={handleCreate}
        isPending={saving}
        submitLabel="Create user"
      >
        <div className="form-field">
          <label className="form-label">Username <span className="req">*</span></label>
          <input className="form-input" placeholder="alice" value={form.username} onChange={set("username")} autoFocus />
        </div>
        <div className="form-row">
          <div className="form-field">
            <label className="form-label">First name</label>
            <input className="form-input" placeholder="Alice" value={form.firstName} onChange={set("firstName")} />
          </div>
          <div className="form-field">
            <label className="form-label">Last name</label>
            <input className="form-input" placeholder="Smith" value={form.lastName} onChange={set("lastName")} />
          </div>
        </div>
        <div className="form-field">
          <label className="form-label">Email</label>
          <input className="form-input" type="email" placeholder="alice@example.com" value={form.email} onChange={set("email")} />
        </div>
        <div className="form-field">
          <label className="form-label">Password <span className="req">*</span></label>
          <input className="form-input" type="password" placeholder="12+ characters" value={form.password} onChange={set("password")} />
        </div>
        {formErr && <p className="error-msg">{formErr}</p>}
      </Drawer>
    </>
  );
}
