import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Search, Building2 } from "lucide-react";
import { getOrgs, createOrg } from "../api";
import Drawer from "../components/Drawer";

export default function OrganisationsPage() {
  const navigate = useNavigate();
  const [orgs,      setOrgs]      = useState([]);
  const [loading,   setLoading]   = useState(true);
  const [error,     setError]     = useState(null);
  const [search,    setSearch]    = useState("");
  const [open,      setOpen]      = useState(false);
  const [name,      setName]      = useState("");
  const [formErr,   setFormErr]   = useState(null);
  const [saving,    setSaving]    = useState(false);

  function load() {
    setLoading(true);
    getOrgs()
      .then((d) => { setOrgs(d.orgs || []); setError(null); })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }
  useEffect(load, []);

  const filtered = orgs.filter((o) => o.name.toLowerCase().includes(search.toLowerCase()));

  async function handleCreate(e) {
    e.preventDefault();
    if (!name.trim()) { setFormErr("Name is required"); return; }
    setSaving(true); setFormErr(null);
    try {
      await createOrg(name.trim());
      setOpen(false); setName(""); load();
    } catch (e) {
      setFormErr(e.message || "Failed to create organisation");
    } finally {
      setSaving(false);
    }
  }

  const skeletons = Array.from({ length: 5 });

  return (
    <>
      <div className="adm-header">
        <div>
          <h1 className="adm-title">Organisations</h1>
          <p className="adm-sub">Manage organisations and their projects.</p>
        </div>
        <button className="btn btn-primary btn-sm" onClick={() => setOpen(true)}>
          <Plus size={14} /> New organisation
        </button>
      </div>

      {error && <p className="error-msg">{error}</p>}

      <div className="search-bar">
        <div className="search-input-wrap">
          <Search size={14} className="search-icon" style={{ color: "var(--text-muted)" }} />
          <input
            className="form-input"
            placeholder="Search organisations…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <span style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>
          {!loading && `${filtered.length} organisation${filtered.length !== 1 ? "s" : ""}`}
        </span>
      </div>

      <div className="table-card">
        <table className="admin-table">
          <thead>
            <tr>
              <th>Organisation</th>
              <th>Projects</th>
              <th style={{ width: 40 }} />
            </tr>
          </thead>
          <tbody>
            {loading ? (
              skeletons.map((_, i) => (
                <tr key={i}>
                  <td><div className="skeleton-row" style={{ width: "55%", height: 16 }} /></td>
                  <td><div className="skeleton-row" style={{ width: "30%", height: 16 }} /></td>
                  <td />
                </tr>
              ))
            ) : filtered.length === 0 ? (
              <tr>
                <td colSpan={3}>
                  <div className="adm-empty">
                    <span>🏢</span>
                    <p>{search ? "No results for that search." : "No organisations yet."}</p>
                  </div>
                </td>
              </tr>
            ) : (
              filtered.map((org) => (
                <tr
                  key={org.name}
                  style={{ cursor: "pointer" }}
                  onClick={() => navigate(`/organisations/${org.name}`)}
                >
                  <td>
                    <span style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontWeight: 500 }}>
                      <Building2 size={14} style={{ color: "var(--text-muted)", flexShrink: 0 }} />
                      {org.name}
                    </span>
                  </td>
                  <td>
                    <span style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>
                      {org.projects?.length ?? 0} project{org.projects?.length !== 1 ? "s" : ""}
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
        onClose={() => { setOpen(false); setName(""); setFormErr(null); }}
        title="New organisation"
        description="Lowercase letters, numbers, and hyphens only."
        onSubmit={handleCreate}
        isPending={saving}
        submitLabel="Create"
      >
        <div className="form-field">
          <label className="form-label">Name <span className="req">*</span></label>
          <input
            className="form-input"
            placeholder="my-organisation"
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
