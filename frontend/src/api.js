import keycloak from "./keycloak";

async function authFetch(path, opts = {}) {
  await keycloak.updateToken(30).catch(() => keycloak.login());
  const res = await fetch(path, {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${keycloak.token}`,
      ...opts.headers,
    },
  });
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.error || `HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return data;
}

// ── Organisations ─────────────────────────────────────────────────────────────
export const getOrgs   = ()     => authFetch("/api/admin/super/orgs");
export const createOrg = (name) => authFetch("/api/admin/super/orgs", { method: "POST", body: JSON.stringify({ name }) });

// ── Projects ──────────────────────────────────────────────────────────────────
export const createProject = (org, name) =>
  authFetch(`/api/admin/super/orgs/${org}/projects`, { method: "POST", body: JSON.stringify({ name }) });

// ── Users ─────────────────────────────────────────────────────────────────────
export const getUsers      = (search = "") =>
  authFetch(`/api/admin/super/users${search ? `?search=${encodeURIComponent(search)}` : ""}`);
export const createUser    = (data)   => authFetch("/api/admin/super/users", { method: "POST", body: JSON.stringify(data) });
export const getUserDetail = (userId) => authFetch(`/api/admin/super/users/${userId}`);
export const assignRole    = (userId, name) =>
  authFetch(`/api/admin/super/users/${userId}/roles`, { method: "POST", body: JSON.stringify({ name }) });
export const removeRole    = (userId, roleName) =>
  authFetch(`/api/admin/super/users/${userId}/roles/${encodeURIComponent(roleName)}`, { method: "DELETE" });
export const addUserToGroup    = (userId, path) =>
  authFetch(`/api/admin/super/users/${userId}/groups`, { method: "POST", body: JSON.stringify({ path }) });
export const removeUserFromGroup = (userId, path) =>
  authFetch(`/api/admin/super/users/${userId}/groups`, { method: "DELETE", body: JSON.stringify({ path }) });

// ── Org members ───────────────────────────────────────────────────────────────
export const getOrgMembers   = (org)         => authFetch(`/api/admin/org/${org}/members`);
export const addOrgMember    = (org, userId) => authFetch(`/api/admin/org/${org}/members/${userId}`, { method: "PUT" });
export const removeOrgMember = (org, userId) => authFetch(`/api/admin/org/${org}/members/${userId}`, { method: "DELETE" });

// ── Roles ─────────────────────────────────────────────────────────────────────
export const getRoles   = ()     => authFetch("/api/admin/super/roles");
export const createRole = (data) => authFetch("/api/admin/super/roles", { method: "POST", body: JSON.stringify(data) });
