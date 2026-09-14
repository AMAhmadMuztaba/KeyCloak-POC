import { useState, useEffect } from "react";
import { NavLink, useParams } from "react-router-dom";
import { ChevronLeft, Plus, Trash2 } from "lucide-react";
import { getUserDetail, getRoles, assignRole, removeRole } from "../api";
import ConfirmModal from "../components/ConfirmModal";

export default function UserDetailPage() {
  const { userId } = useParams();
  const [user,       setUser]       = useState(null);
  const [allRoles,   setAllRoles]   = useState([]);
  const [loading,    setLoading]    = useState(true);
  const [error,      setError]      = useState(null);
  const [addRole,    setAddRole]    = useState("");
  const [isAdding,   setIsAdding]   = useState(false);
  const [toRemove,   setToRemove]   = useState(null);
  const [isRemoving, setIsRemoving] = useState(false);

  function load() {
    setLoading(true);
    Promise.all([getUserDetail(userId), getRoles()])
      .then(([u, r]) => { setUser(u); setAllRoles(r.roles || []); setError(null); })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }
  useEffect(load, [userId]);

  async function handleAssign() {
    if (!addRole) return;
    setIsAdding(true);
    try { await assignRole(userId, addRole); setAddRole(""); load(); }
    catch (e) { setError(e.message); }
    finally { setIsAdding(false); }
  }

  async function handleRemove() {
    setIsRemoving(true);
    try { await removeRole(userId, toRemove); setToRemove(null); load(); }
    catch (e) { setError(e.message); }
    finally { setIsRemoving(false); }
  }

  const displayName = user
    ? [user.firstName, user.lastName].filter(Boolean).join(" ") || user.username
    : "";

  const assignedNames = new Set((user?.roles || []).map((r) => r.name));
  const available = allRoles.filter((r) => !assignedNames.has(r.name));

  const initials =
    [user?.firstName, user?.lastName].filter(Boolean).map((s) => s[0].toUpperCase()).join("") ||
    (user?.username?.[0]?.toUpperCase() ?? "?");

  if (loading) {
    return (
      <div style={{ padding: "3rem 0", textAlign: "center", color: "var(--text-muted)" }}>
        Loading…
      </div>
    );
  }

  return (
    <>
      <div>
        <NavLink to="/users" className="back-link">
          <ChevronLeft size={14} /> Users
        </NavLink>
        <div className="adm-header" style={{ marginBottom: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <div className="user-avatar user-avatar--lg">{initials}</div>
            <div>
              <h1 className="adm-title" style={{ marginBottom: 0 }}>{displayName}</h1>
              <p className="adm-sub">{user?.email || user?.username}</p>
            </div>
          </div>
        </div>
      </div>

      {error && <p className="error-msg">{error}</p>}

      {/* Realm roles */}
      <div className="adm-section">
        <p className="section-title">Realm Roles</p>

        <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.75rem", flexWrap: "wrap" }}>
          <select
            className="form-select"
            value={addRole}
            onChange={(e) => setAddRole(e.target.value)}
            style={{ minWidth: 200 }}
          >
            <option value="">Assign a role…</option>
            {available.map((r) => (
              <option key={r.name} value={r.name}>{r.name}</option>
            ))}
          </select>
          <button
            className="btn btn-secondary btn-sm"
            onClick={handleAssign}
            disabled={!addRole || isAdding}
          >
            <Plus size={14} /> Assign
          </button>
        </div>

        {(user?.roles || []).length === 0 ? (
          <div className="adm-empty adm-empty--sm">
            <span>🛡</span>
            <p>No roles assigned.</p>
          </div>
        ) : (
          <div className="role-list">
            {(user.roles || []).map((r) => (
              <div key={r.name} className="role-row">
                <span className={`role-badge ${r.name === "super-admin" ? "role-super" : "role-generic"}`}>
                  {r.name}
                </span>
                <span className="role-desc" style={{ flex: 1 }}>{r.description || "—"}</span>
                <button
                  className="btn-ghost btn-ghost-sm"
                  onClick={() => setToRemove(r.name)}
                  title="Remove role"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Group memberships */}
      <div className="adm-section">
        <p className="section-title">Group Memberships</p>
        {(user?.groups || []).length === 0 ? (
          <div className="adm-empty adm-empty--sm">
            <span>🔗</span>
            <p>No group memberships.</p>
          </div>
        ) : (
          <div className="table-card">
            <table className="admin-table">
              <thead>
                <tr><th>Group path</th></tr>
              </thead>
              <tbody>
                {user.groups.map((g) => (
                  <tr key={g}>
                    <td>
                      <code style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>{g}</code>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <ConfirmModal
        open={toRemove !== null}
        title={`Remove role "${toRemove}"?`}
        body="This will revoke the role from the user immediately."
        confirmLabel="Remove"
        danger
        isPending={isRemoving}
        onConfirm={handleRemove}
        onClose={() => setToRemove(null)}
      />
    </>
  );
}
