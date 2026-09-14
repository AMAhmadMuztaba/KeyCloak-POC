import { useState, useEffect } from "react";
import { Plus } from "lucide-react";
import { getRoles, createRole } from "../api";
import Drawer from "../components/Drawer";

export default function RolesPage() {
  const [roles,   setRoles]   = useState([]);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);
  const [open,    setOpen]    = useState(false);
  const [saving,  setSaving]  = useState(false);
  const [formErr, setFormErr] = useState(null);
  const [form,    setForm]    = useState({ name: "", description: "", roleType: "global" });

  function load() {
    setLoading(true);
    getRoles()
      .then((d) => { setRoles(d.roles || []); setError(null); })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }
  useEffect(load, []);

  function set(key) {
    return (e) => setForm((f) => ({ ...f, [key]: e.target.value }));
  }

  async function handleCreate(e) {
    e.preventDefault();
    if (!form.name.trim()) { setFormErr("Name is required"); return; }
    setSaving(true); setFormErr(null);
    try {
      await createRole({ name: form.name.trim(), description: form.description, roleType: form.roleType });
      setOpen(false);
      setForm({ name: "", description: "", roleType: "global" });
      load();
    } catch (e) {
      setFormErr(e.message || "Failed to create role");
    } finally {
      setSaving(false);
    }
  }

  const badgeClass = (r) => {
    if (r.name === "super-admin") return "role-super";
    if (r.roleType === "org")     return "role-org";
    return "role-generic";
  };

  const skeletons = Array.from({ length: 4 });

  return (
    <>
      <div className="adm-header">
        <div>
          <h1 className="adm-title">Roles</h1>
          <p className="adm-sub">Manage realm roles and assign them to users.</p>
        </div>
        <button className="btn btn-primary btn-sm" onClick={() => setOpen(true)}>
          <Plus size={14} /> New role
        </button>
      </div>

      {error && <p className="error-msg">{error}</p>}

      <div className="table-card">
        <table className="admin-table">
          <thead>
            <tr>
              <th>Role</th>
              <th>Type</th>
              <th>Description</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              skeletons.map((_, i) => (
                <tr key={i}>
                  <td><div className="skeleton-row" style={{ width: "45%", height: 16 }} /></td>
                  <td><div className="skeleton-row" style={{ width: "25%", height: 16 }} /></td>
                  <td><div className="skeleton-row" style={{ width: "60%", height: 16 }} /></td>
                </tr>
              ))
            ) : roles.length === 0 ? (
              <tr>
                <td colSpan={3}>
                  <div className="adm-empty">
                    <span>🛡</span>
                    <p>No custom roles yet.</p>
                  </div>
                </td>
              </tr>
            ) : (
              roles.map((r) => (
                <tr key={r.id || r.name}>
                  <td>
                    <span className={`role-badge ${badgeClass(r)}`}>{r.name}</span>
                  </td>
                  <td>
                    <span style={{ fontSize: "0.82rem", color: "var(--text-muted)", textTransform: "capitalize" }}>
                      {r.roleType || "global"}
                    </span>
                  </td>
                  <td style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>
                    {r.description || "—"}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <Drawer
        open={open}
        onClose={() => { setOpen(false); setForm({ name: "", description: "", roleType: "global" }); setFormErr(null); }}
        title="New role"
        description="Realm roles control what users can access across the system."
        onSubmit={handleCreate}
        isPending={saving}
        submitLabel="Create role"
      >
        <div className="form-field">
          <label className="form-label">Name <span className="req">*</span></label>
          <input
            className="form-input"
            placeholder="org-viewer"
            value={form.name}
            onChange={set("name")}
            autoFocus
          />
        </div>

        <div className="form-field">
          <label className="form-label">Description</label>
          <textarea
            className="form-input"
            style={{ minHeight: 72, resize: "vertical", padding: "0.5rem 0.75rem" }}
            placeholder="What this role allows…"
            value={form.description}
            onChange={set("description")}
          />
        </div>

        <div className="form-field">
          <label className="form-label">Type</label>
          <div className="role-type-row">
            <button
              type="button"
              className={`role-type-btn ${form.roleType === "global" ? "role-type-btn--active" : ""}`}
              onClick={() => setForm((f) => ({ ...f, roleType: "global" }))}
            >
              Global
            </button>
            <button
              type="button"
              className={`role-type-btn ${form.roleType === "org" ? "role-type-btn--active role-type-btn--active-org" : ""}`}
              onClick={() => setForm((f) => ({ ...f, roleType: "org" }))}
            >
              Org-scoped
            </button>
          </div>
        </div>

        {formErr && <p className="error-msg">{formErr}</p>}
      </Drawer>
    </>
  );
}
