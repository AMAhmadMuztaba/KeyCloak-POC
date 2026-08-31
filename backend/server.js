require("dotenv").config();
const express = require("express");
const cors    = require("cors");
const { expressjwt: jwt } = require("express-jwt");
const jwksRsa = require("jwks-rsa");

const app           = express();
const PORT          = process.env.PORT              || 4000;
const KC_URL        = process.env.KC_URL            || "http://localhost:8080";
// KC_ISSUER = the public URL that appears in JWT iss claim (what the browser uses).
// Inside Docker, KC_URL is the internal hostname; KC_ISSUER must be the public one.
const KC_ISSUER     = process.env.KC_ISSUER         || KC_URL;
const KC_REALM      = process.env.KC_REALM          || "app-realm";
const KC_ADMIN      = process.env.KC_ADMIN          || "admin";
const KC_ADMIN_PW   = process.env.KC_ADMIN_PASSWORD || "admin123";

app.use(cors({ origin: ["http://localhost:3000", "http://localhost:5173"] }));
app.use(express.json());

// ── JWT middleware ──────────────────────────────────────────────────────────
const checkJwt = jwt({
  secret: jwksRsa.expressJwtSecret({
    cache: true,
    rateLimit: true,
    jwksRequestsPerMinute: 10,
    jwksUri: `${KC_URL}/realms/${KC_REALM}/protocol/openid-connect/certs`,
  }),
  issuer:     `${KC_ISSUER}/realms/${KC_REALM}`,
  algorithms: ["RS256"],
});

// ── Keycloak Admin API client ───────────────────────────────────────────────
async function getAdminToken() {
  const body = new URLSearchParams({
    grant_type: "password",
    client_id:  "admin-cli",
    username:   KC_ADMIN,
    password:   KC_ADMIN_PW,
  });
  const res = await fetch(
    `${KC_URL}/realms/master/protocol/openid-connect/token`,
    { method: "POST", body, headers: { "Content-Type": "application/x-www-form-urlencoded" } }
  );
  const data = await res.json();
  return data.access_token;
}

async function kcFetch(path, method = "GET", body) {
  const token = await getAdminToken();
  const res = await fetch(`${KC_URL}/admin/realms/${KC_REALM}${path}`, {
    method,
    headers: {
      Authorization:  `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (res.status === 204 || res.status === 201) return { status: res.status };
  const data = await res.json().catch(() => ({}));
  return { status: res.status, data };
}

// ── Group tree helpers ──────────────────────────────────────────────────────
// Three parallel rounds instead of sequential recursion (KC24 returns empty
// subGroups in brief repr so we must call /children, but we can parallelise).
async function fetchAllGroups() {
  const { data: top } = await kcFetch("/groups?max=200");
  if (!Array.isArray(top) || !top.length) return {};

  const mapping = {};
  top.forEach(g => { mapping[g.path] = g.id; });

  // Round 2: all level-2 children in parallel
  const level2Results = await Promise.all(
    top.map(g => kcFetch(`/groups/${g.id}/children?max=200`).then(r => r.data || []))
  );
  const level2 = level2Results.flat();
  level2.forEach(g => { mapping[g.path] = g.id; });

  // Round 3: all level-3 children (project/admins) in parallel
  if (level2.length) {
    const level3Results = await Promise.all(
      level2.map(g => kcFetch(`/groups/${g.id}/children?max=100`).then(r => r.data || []))
    );
    level3Results.flat().forEach(g => { mapping[g.path] = g.id; });
  }

  return mapping;
}

async function getGroupId(path) {
  const map = await fetchAllGroups();
  return map[path] || null;
}

async function getOrCreateSubgroup(parentId, name, parentPath) {
  const map = await fetchAllGroups();
  const full = `${parentPath}/${name}`;
  if (map[full]) return map[full];
  await kcFetch(`/groups/${parentId}/children`, "POST", { name });
  const fresh = await fetchAllGroups();
  return fresh[full] || null;
}

// ── Helpers for permission checks ───────────────────────────────────────────
function roles(req)  { return req.auth?.realm_access?.roles || []; }
function groups(req) { return req.auth?.groups || []; }
const isSuperAdmin = (req) => roles(req).includes("super-admin");
const isOrgAdmin   = (req, org) =>
  isSuperAdmin(req) || groups(req).includes(`/${org}/admins`);
const isProjAdmin  = (req, org, project) =>
  isSuperAdmin(req) ||
  groups(req).includes(`/${org}/admins`) ||
  groups(req).includes(`/${org}/${project}/admins`);

// ── Auth middleware factories ────────────────────────────────────────────────
const requireSuperAdmin = [checkJwt, (req, res, next) => {
  if (!isSuperAdmin(req)) return res.status(403).json({ error: "Super-admin required" });
  next();
}];

function requireOrgAdmin(param = "org") {
  return [checkJwt, (req, res, next) => {
    if (!isOrgAdmin(req, req.params[param])) {
      return res.status(403).json({ error: "Org-admin required" });
    }
    next();
  }];
}

function requireProjectAdmin() {
  return [checkJwt, (req, res, next) => {
    const { org, project } = req.params;
    if (!isProjAdmin(req, org, project)) {
      return res.status(403).json({ error: "Project-admin required" });
    }
    next();
  }];
}

// ── parseGroups – strips 'admins' helper groups from user-facing lists ───────
function parseGroups(claims) {
  const gs = claims.groups || [];
  const parts = (g) => g.split("/").filter(Boolean);
  const orgs = [...new Set(
    gs.filter(g => parts(g).length === 1).map(g => parts(g)[0])
  )];
  const projectsForOrg = (org) =>
    gs
      .filter(g => parts(g).length === 2 && parts(g)[0] === org && parts(g)[1] !== "admins")
      .map(g => parts(g)[1]);
  return { orgs, projectsForOrg };
}

// ═══════════════════════════════════════════════════════════════════════════
// PUBLIC ROUTES
// ═══════════════════════════════════════════════════════════════════════════

app.get("/api/health", (_req, res) => res.json({ status: "ok" }));

// ═══════════════════════════════════════════════════════════════════════════
// USER ROUTES (any authenticated user)
// ═══════════════════════════════════════════════════════════════════════════

app.get("/api/me", checkJwt, (req, res) => {
  const c = req.auth;
  const { orgs, projectsForOrg } = parseGroups(c);
  res.json({
    sub:          c.sub,
    username:     c.preferred_username,
    email:        c.email,
    firstName:    c.given_name,
    lastName:     c.family_name,
    isSuperAdmin: isSuperAdmin(req),
    orgs,
    allProjects:  Object.fromEntries(orgs.map(o => [o, projectsForOrg(o)])),
  });
});

app.get("/api/orgs", checkJwt, (req, res) => {
  const { orgs } = parseGroups(req.auth);
  res.json({ orgs });
});

app.get("/api/orgs/:org/projects", checkJwt, (req, res) => {
  const { org } = req.params;
  const { orgs, projectsForOrg } = parseGroups(req.auth);
  if (!orgs.includes(org)) {
    return res.status(403).json({ error: "Not a member of this organisation" });
  }
  res.json({ org, projects: projectsForOrg(org) });
});

// ═══════════════════════════════════════════════════════════════════════════
// SHARED ADMIN UTILITIES  (any admin role)
// ═══════════════════════════════════════════════════════════════════════════

// GET /api/admin/users?search=  – user search available to all admins
app.get("/api/admin/users", checkJwt, (req, res, next) => {
  const isAnyAdmin =
    isSuperAdmin(req) ||
    (req.auth?.groups || []).some(g => g.endsWith("/admins"));
  if (!isAnyAdmin) return res.status(403).json({ error: "Admin access required" });
  next();
}, async (req, res) => {
  const search = req.query.search ? `&search=${encodeURIComponent(req.query.search)}` : "";
  const { data } = await kcFetch(`/users?max=50${search}`);
  res.json({
    users: (data || []).map(u => ({
      id: u.id, username: u.username, email: u.email,
      firstName: u.firstName, lastName: u.lastName,
    })),
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// SUPER-ADMIN ROUTES
// ═══════════════════════════════════════════════════════════════════════════

// GET /api/admin/super/orgs  – all orgs with projects (no member count, keeps it fast)
app.get("/api/admin/super/orgs", requireSuperAdmin, async (req, res) => {
  try {
    const groupMap = await fetchAllGroups();
    const orgs = Object.entries(groupMap)
      .filter(([path]) => path.split("/").filter(Boolean).length === 1)
      .map(([path, id]) => {
        const name = path.slice(1);
        const projects = Object.keys(groupMap).filter(p => {
          const pts = p.split("/").filter(Boolean);
          return pts.length === 2 && pts[0] === name && pts[1] !== "admins";
        }).map(p => p.split("/").filter(Boolean)[1]);
        return { name, id, projects };
      });
    res.json({ orgs });
  } catch (e) {
    console.error(e);
    res.status(500).json({ error: "Failed to list orgs" });
  }
});

// POST /api/admin/super/orgs  – create org
app.post("/api/admin/super/orgs", requireSuperAdmin, async (req, res) => {
  const { name } = req.body;
  if (!name) return res.status(400).json({ error: "name is required" });
  const slug = name.toLowerCase().replace(/\s+/g, "-");
  const { status } = await kcFetch("/groups", "POST", { name: slug });
  if (status === 201) {
    // Also create the admins subgroup
    const id = await getGroupId(`/${slug}`);
    if (id) await kcFetch(`/groups/${id}/children`, "POST", { name: "admins" });
    return res.status(201).json({ name: slug });
  }
  if (status === 409) return res.status(409).json({ error: "Org already exists" });
  res.status(500).json({ error: "Failed to create org" });
});

// POST /api/admin/super/orgs/:org/projects  – create project
app.post("/api/admin/super/orgs/:org/projects", requireSuperAdmin, async (req, res) => {
  const { org } = req.params;
  const { name } = req.body;
  if (!name) return res.status(400).json({ error: "name is required" });
  const slug = name.toLowerCase().replace(/\s+/g, "-");

  const orgId = await getGroupId(`/${org}`);
  if (!orgId) return res.status(404).json({ error: "Org not found" });

  const { status } = await kcFetch(`/groups/${orgId}/children`, "POST", { name: slug });
  if (status === 201) {
    const map = await fetchAllGroups();
    const projId = map[`/${org}/${slug}`];
    if (projId) await kcFetch(`/groups/${projId}/children`, "POST", { name: "admins" });
    return res.status(201).json({ org, project: slug });
  }
  if (status === 409) return res.status(409).json({ error: "Project already exists" });
  res.status(500).json({ error: "Failed to create project" });
});

// POST /api/admin/super/users  – create user
app.post("/api/admin/super/users", requireSuperAdmin, async (req, res) => {
  const { username, email, firstName, lastName, password } = req.body;
  if (!username || !password) {
    return res.status(400).json({ error: "username and password are required" });
  }
  const { status, data } = await kcFetch("/users", "POST", {
    username,
    email:    email    || undefined,
    firstName: firstName || undefined,
    lastName:  lastName  || undefined,
    enabled: true,
    emailVerified: true,
    credentials: [{ type: "password", value: password, temporary: false }],
  });
  if (status === 201) return res.status(201).json({ ok: true });
  if (status === 409) return res.status(409).json({ error: "Username already exists" });
  return res.status(500).json({ error: data?.errorMessage || "Failed to create user" });
});

// GET /api/admin/super/users/:userId  – full profile (groups + roles)
app.get("/api/admin/super/users/:userId", requireSuperAdmin, async (req, res) => {
  const { userId } = req.params;
  const SKIP = ["offline_access", "uma_authorization", `default-roles-${KC_REALM}`];
  try {
    const [uRes, gRes, rRes] = await Promise.all([
      kcFetch(`/users/${userId}`),
      kcFetch(`/users/${userId}/groups?max=200`),
      kcFetch(`/users/${userId}/role-mappings/realm`),
    ]);
    res.json({
      id:        uRes.data?.id,
      username:  uRes.data?.username,
      email:     uRes.data?.email,
      firstName: uRes.data?.firstName,
      lastName:  uRes.data?.lastName,
      groups:    (gRes.data || []).map(g => g.path),
      roles:     (rRes.data || []).filter(r => !SKIP.includes(r.name)).map(r => ({ id: r.id, name: r.name })),
    });
  } catch (e) {
    console.error(e);
    res.status(500).json({ error: "Failed to fetch user profile" });
  }
});

// POST /api/admin/super/users/:userId/groups  – add to group by path
app.post("/api/admin/super/users/:userId/groups", requireSuperAdmin, async (req, res) => {
  const { userId } = req.params;
  const { path } = req.body;
  if (!path) return res.status(400).json({ error: "path required" });
  const gid = await getGroupId(path);
  if (!gid) return res.status(404).json({ error: `Group not found: ${path}` });
  await kcFetch(`/users/${userId}/groups/${gid}`, "PUT");
  res.json({ ok: true });
});

// DELETE /api/admin/super/users/:userId/groups  – remove from group by path
app.delete("/api/admin/super/users/:userId/groups", requireSuperAdmin, async (req, res) => {
  const { userId } = req.params;
  const { path } = req.body;
  if (!path) return res.status(400).json({ error: "path required" });
  const gid = await getGroupId(path);
  if (!gid) return res.status(404).json({ error: `Group not found: ${path}` });
  await kcFetch(`/users/${userId}/groups/${gid}`, "DELETE");
  res.json({ ok: true });
});

// POST /api/admin/super/users/:userId/roles  – assign realm role
app.post("/api/admin/super/users/:userId/roles", requireSuperAdmin, async (req, res) => {
  const { userId } = req.params;
  const { name } = req.body;
  if (!name) return res.status(400).json({ error: "name required" });
  const { data: role } = await kcFetch(`/roles/${name}`);
  if (!role?.id) return res.status(404).json({ error: "Role not found" });
  await kcFetch(`/users/${userId}/role-mappings/realm`, "POST", [role]);
  res.json({ ok: true });
});

// DELETE /api/admin/super/users/:userId/roles/:roleName  – remove realm role
app.delete("/api/admin/super/users/:userId/roles/:roleName", requireSuperAdmin, async (req, res) => {
  const { userId, roleName } = req.params;
  const { data: role } = await kcFetch(`/roles/${roleName}`);
  if (!role?.id) return res.status(404).json({ error: "Role not found" });
  await kcFetch(`/users/${userId}/role-mappings/realm`, "DELETE", [role]);
  res.json({ ok: true });
});

// GET /api/admin/super/users  – list all users (with optional search)
app.get("/api/admin/super/users", requireSuperAdmin, async (req, res) => {
  const search = req.query.search ? `&search=${encodeURIComponent(req.query.search)}` : "";
  const { data } = await kcFetch(`/users?max=100${search}`);
  const users = (data || []).map(u => ({
    id:       u.id,
    username: u.username,
    email:    u.email,
    firstName: u.firstName,
    lastName:  u.lastName,
    enabled:   u.enabled,
  }));
  res.json({ users });
});

// GET /api/admin/super/roles  – list realm roles (includes type, orgScope, permissions attributes)
app.get("/api/admin/super/roles", requireSuperAdmin, async (req, res) => {
  const { data } = await kcFetch("/roles");
  const SKIP = ["offline_access", "uma_authorization", `default-roles-${KC_REALM}`];
  const roles = (data || [])
    .filter(r => !r.composite && !SKIP.includes(r.name))
    .map(r => ({
      id:           r.id,
      name:         r.name,
      description:  r.description,
      roleType:     r.attributes?.type?.[0]     || "global",
      orgScope:     r.attributes?.orgScope?.[0] || null,
      permissions:  r.attributes?.permissions   || [],
      projectScope: r.attributes?.projectScope  || [],
    }));
  res.json({ roles });
});

// POST /api/admin/super/roles  – create realm role with optional type/permissions
app.post("/api/admin/super/roles", requireSuperAdmin, async (req, res) => {
  const { name, description = "", roleType = "global", orgScope, permissions = [], projectScope = [] } = req.body;
  if (!name) return res.status(400).json({ error: "name is required" });

  const attributes = { type: [roleType] };
  if (roleType === "org" && orgScope)  attributes.orgScope     = [orgScope];
  if (permissions.length > 0)         attributes.permissions  = permissions;
  if (projectScope.length > 0)        attributes.projectScope = projectScope;

  const { status } = await kcFetch("/roles", "POST", { name, description, attributes });
  if (status === 201) return res.status(201).json({ name });
  if (status === 409) return res.status(409).json({ error: "Role already exists" });
  res.status(500).json({ error: "Failed to create role" });
});

// PUT /api/admin/super/users/:userId/roles/:roleName  – assign role to user
app.put("/api/admin/super/users/:userId/roles/:roleName", requireSuperAdmin, async (req, res) => {
  const { userId, roleName } = req.params;
  const { data: role } = await kcFetch(`/roles/${roleName}`);
  if (!role?.id) return res.status(404).json({ error: "Role not found" });
  const { status } = await kcFetch(`/users/${userId}/role-mappings/realm`, "POST", [role]);
  res.status(status === 204 ? 200 : status).json({ ok: status === 204 });
});

// PUT /api/admin/super/orgs/:org/admins/:userId  – make user org-admin
app.put("/api/admin/super/orgs/:org/admins/:userId", requireSuperAdmin, async (req, res) => {
  const { org, userId } = req.params;
  const map = await fetchAllGroups();
  // Ensure user is in the org group and the admins group
  const orgId   = map[`/${org}`];
  const adminId = map[`/${org}/admins`];
  if (!orgId || !adminId) return res.status(404).json({ error: "Org or admins group not found" });
  await kcFetch(`/users/${userId}/groups/${orgId}`,   "PUT");
  await kcFetch(`/users/${userId}/groups/${adminId}`, "PUT");
  res.json({ ok: true });
});

// PUT /api/admin/super/orgs/:org/projects/:project/admins/:userId  – make user project-admin
app.put("/api/admin/super/orgs/:org/projects/:project/admins/:userId", requireSuperAdmin, async (req, res) => {
  const { org, project, userId } = req.params;
  const map = await fetchAllGroups();
  const projId    = map[`/${org}/${project}`];
  const adminId   = map[`/${org}/${project}/admins`];
  if (!projId || !adminId) return res.status(404).json({ error: "Project or admins group not found" });
  await kcFetch(`/users/${userId}/groups/${projId}`,  "PUT");
  await kcFetch(`/users/${userId}/groups/${adminId}`, "PUT");
  res.json({ ok: true });
});

// ═══════════════════════════════════════════════════════════════════════════
// ORG-ADMIN ROUTES
// ═══════════════════════════════════════════════════════════════════════════

// GET /api/admin/org/:org/projects  – list projects in org (accessible to org admins)
app.get("/api/admin/org/:org/projects", requireOrgAdmin(), async (req, res) => {
  const { org } = req.params;
  try {
    const orgId = await getGroupId(`/${org}`);
    if (!orgId) return res.status(404).json({ error: "Org not found" });
    const { data } = await kcFetch(`/groups/${orgId}/children?max=200`);
    const projects = (data || []).filter(g => g.name !== "admins").map(g => g.name);
    res.json({ org, projects });
  } catch (e) {
    console.error(e);
    res.status(500).json({ error: "Failed to list projects" });
  }
});

// GET /api/admin/org/:org/members/:userId  – member's project memberships within the org
app.get("/api/admin/org/:org/members/:userId", requireOrgAdmin(), async (req, res) => {
  const { org, userId } = req.params;
  try {
    const [uRes, gRes] = await Promise.all([
      kcFetch(`/users/${userId}`),
      kcFetch(`/users/${userId}/groups?max=200`),
    ]);
    const pts = (g) => g.split("/").filter(Boolean);
    const projects = (gRes.data || [])
      .map(g => g.path)
      .filter(p => pts(p).length === 2 && pts(p)[0] === org && pts(p)[1] !== "admins")
      .map(p => pts(p)[1]);
    res.json({
      id:        uRes.data?.id,
      username:  uRes.data?.username,
      email:     uRes.data?.email,
      firstName: uRes.data?.firstName,
      lastName:  uRes.data?.lastName,
      projects,
    });
  } catch (e) {
    console.error(e);
    res.status(500).json({ error: "Failed to fetch member details" });
  }
});

// GET /api/admin/org/:org/members
app.get("/api/admin/org/:org/members", requireOrgAdmin(), async (req, res) => {
  const { org } = req.params;
  const orgId = await getGroupId(`/${org}`);
  if (!orgId) return res.status(404).json({ error: "Org not found" });
  const { data } = await kcFetch(`/groups/${orgId}/members`);
  const members = (data || []).map(u => ({
    id: u.id, username: u.username, email: u.email,
    firstName: u.firstName, lastName: u.lastName,
  }));
  res.json({ org, members });
});

// PUT /api/admin/org/:org/members/:userId  – add user to org
app.put("/api/admin/org/:org/members/:userId", requireOrgAdmin(), async (req, res) => {
  const { org, userId } = req.params;
  const orgId = await getGroupId(`/${org}`);
  if (!orgId) return res.status(404).json({ error: "Org not found" });
  const { status } = await kcFetch(`/users/${userId}/groups/${orgId}`, "PUT");
  res.json({ ok: status === 204 });
});

// DELETE /api/admin/org/:org/members/:userId  – remove user from org
app.delete("/api/admin/org/:org/members/:userId", requireOrgAdmin(), async (req, res) => {
  const { org, userId } = req.params;
  const orgId = await getGroupId(`/${org}`);
  if (!orgId) return res.status(404).json({ error: "Org not found" });
  const { status } = await kcFetch(`/users/${userId}/groups/${orgId}`, "DELETE");
  res.json({ ok: status === 204 });
});

// POST /api/admin/org/:org/projects  – org admin creates project
app.post("/api/admin/org/:org/projects", requireOrgAdmin(), async (req, res) => {
  const { org } = req.params;
  const { name } = req.body;
  if (!name) return res.status(400).json({ error: "name is required" });
  const slug  = name.toLowerCase().replace(/\s+/g, "-");
  const orgId = await getGroupId(`/${org}`);
  if (!orgId) return res.status(404).json({ error: "Org not found" });

  const { status } = await kcFetch(`/groups/${orgId}/children`, "POST", { name: slug });
  if (status === 201) {
    const map    = await fetchAllGroups();
    const projId = map[`/${org}/${slug}`];
    if (projId) await kcFetch(`/groups/${projId}/children`, "POST", { name: "admins" });
    return res.status(201).json({ org, project: slug });
  }
  if (status === 409) return res.status(409).json({ error: "Project already exists" });
  res.status(500).json({ error: "Failed to create project" });
});

// ═══════════════════════════════════════════════════════════════════════════
// PROJECT-ADMIN ROUTES
// ═══════════════════════════════════════════════════════════════════════════

// GET /api/admin/project/:org/:project/members
app.get("/api/admin/project/:org/:project/members", requireProjectAdmin(), async (req, res) => {
  const { org, project } = req.params;
  const projId = await getGroupId(`/${org}/${project}`);
  if (!projId) return res.status(404).json({ error: "Project not found" });
  const { data } = await kcFetch(`/groups/${projId}/members`);
  const members = (data || []).map(u => ({
    id: u.id, username: u.username, email: u.email,
    firstName: u.firstName, lastName: u.lastName,
  }));
  res.json({ org, project, members });
});

// PUT /api/admin/project/:org/:project/members/:userId
app.put("/api/admin/project/:org/:project/members/:userId", requireProjectAdmin(), async (req, res) => {
  const { org, project, userId } = req.params;
  const map    = await fetchAllGroups();
  const orgId  = map[`/${org}`];
  const projId = map[`/${org}/${project}`];
  if (!projId) return res.status(404).json({ error: "Project not found" });
  if (orgId)   await kcFetch(`/users/${userId}/groups/${orgId}`,  "PUT");
  await kcFetch(`/users/${userId}/groups/${projId}`, "PUT");
  res.json({ ok: true });
});

// DELETE /api/admin/project/:org/:project/members/:userId
app.delete("/api/admin/project/:org/:project/members/:userId", requireProjectAdmin(), async (req, res) => {
  const { org, project, userId } = req.params;
  const projId = await getGroupId(`/${org}/${project}`);
  if (!projId) return res.status(404).json({ error: "Project not found" });
  const { status } = await kcFetch(`/users/${userId}/groups/${projId}`, "DELETE");
  res.json({ ok: status === 204 });
});

// ── Error handler ───────────────────────────────────────────────────────────
app.use((err, _req, res, _next) => {
  if (err.name === "UnauthorizedError") {
    return res.status(401).json({ error: "Invalid or missing token" });
  }
  console.error(err);
  res.status(500).json({ error: "Internal server error" });
});

app.listen(PORT, () =>
  console.log(`Backend running on http://localhost:${PORT}`)
);
