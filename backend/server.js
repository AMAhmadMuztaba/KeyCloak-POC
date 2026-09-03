require("dotenv").config();
const express   = require("express");
const cors      = require("cors");
const helmet    = require("helmet");
const rateLimit = require("express-rate-limit");
const { expressjwt: jwt } = require("express-jwt");
const jwksRsa   = require("jwks-rsa");

const app          = express();
const PORT         = process.env.PORT              || 4000;
const KC_URL       = process.env.KC_URL            || "http://localhost:8080";
const KC_ISSUER    = process.env.KC_ISSUER         || KC_URL;
const KC_REALM     = process.env.KC_REALM          || "app-realm";
const KC_CLIENT_ID = process.env.KC_CLIENT_ID      || "app-client";
const KC_ADMIN     = process.env.KC_ADMIN          || "admin";
const KC_ADMIN_PW  = process.env.KC_ADMIN_PASSWORD || "";

// ── Helmet (H3) ──────────────────────────────────────────────────────────────
app.use(helmet({
  crossOriginEmbedderPolicy: false, // allow silent-check-sso iframe
  contentSecurityPolicy: {
    directives: {
      defaultSrc: ["'self'"],
      connectSrc: ["'self'", KC_ISSUER],
      frameSrc:   ["'self'", KC_ISSUER],
      scriptSrc:  ["'self'"],
      styleSrc:   ["'self'", "'unsafe-inline'"],
      imgSrc:     ["'self'", "data:"],
    },
  },
}));

// ── CORS — driven from env (H4) ──────────────────────────────────────────────
const allowedOrigins = (process.env.ALLOWED_ORIGINS || "http://localhost:3000,http://localhost:5173")
  .split(",").map(s => s.trim()).filter(Boolean);
app.use(cors({ origin: allowedOrigins, credentials: true }));

app.use(express.json({ limit: "64kb" }));

// ── Rate limiting (H2) ───────────────────────────────────────────────────────
const globalLimiter = rateLimit({
  windowMs: 60_000, max: 120,
  standardHeaders: true, legacyHeaders: false,
  message: { error: "Too many requests" },
});
const writeLimiter = rateLimit({
  windowMs: 60_000, max: 20,
  standardHeaders: true, legacyHeaders: false,
  message: { error: "Too many write requests" },
});
app.use(globalLimiter);
app.use("/api/admin", writeLimiter);

// ── JWT middleware — with audience (C5) ──────────────────────────────────────
const checkJwt = jwt({
  secret: jwksRsa.expressJwtSecret({
    cache: true,
    rateLimit: true,
    jwksRequestsPerMinute: 10,
    jwksUri: `${KC_URL}/realms/${KC_REALM}/protocol/openid-connect/certs`,
  }),
  issuer:     `${KC_ISSUER}/realms/${KC_REALM}`,
  audience:   KC_CLIENT_ID,
  algorithms: ["RS256"],
});

// ── Admin token cache (C6) ───────────────────────────────────────────────────
let _adminToken = null, _adminTokenExpiry = 0;

async function getAdminToken() {
  if (_adminToken && Date.now() < _adminTokenExpiry - 30_000) return _adminToken;
  const body = new URLSearchParams({
    grant_type: "password", client_id: "admin-cli",
    username: KC_ADMIN, password: KC_ADMIN_PW,
  });
  const res  = await fetch(`${KC_URL}/realms/master/protocol/openid-connect/token`, {
    method: "POST", body,
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  const data = await res.json();
  if (!data.access_token) throw new Error("Failed to acquire admin token");
  _adminToken       = data.access_token;
  _adminTokenExpiry = Date.now() + (data.expires_in || 60) * 1000;
  return _adminToken;
}

async function kcFetch(path, method = "GET", body) {
  const token = await getAdminToken();
  const res   = await fetch(`${KC_URL}/admin/realms/${KC_REALM}${path}`, {
    method,
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (res.status === 204 || res.status === 201) return { status: res.status };
  const data = await res.json().catch(() => ({}));
  return { status: res.status, data };
}

// ── Group path validation (H7) ───────────────────────────────────────────────
const GROUP_PATH_RE = /^\/[a-z0-9][a-z0-9-]*(\/(admins|[a-z0-9][a-z0-9-]*))*$/;
function isValidGroupPath(p) {
  return typeof p === "string" && GROUP_PATH_RE.test(p) && p.split("/").filter(Boolean).length <= 3;
}

// ── Password strength (H5 backend enforcement) ────────────────────────────────
function validatePassword(pw) {
  if (!pw || pw.length < 12)      return "Password must be at least 12 characters";
  if (!/[A-Z]/.test(pw))         return "Password must contain an uppercase letter";
  if (!/[a-z]/.test(pw))         return "Password must contain a lowercase letter";
  if (!/\d/.test(pw))            return "Password must contain a number";
  if (!/[^A-Za-z0-9]/.test(pw)) return "Password must contain a special character";
  return null;
}

// ── Group tree helpers ───────────────────────────────────────────────────────
async function fetchAllGroups() {
  const { data: top } = await kcFetch("/groups?max=200");
  if (!Array.isArray(top) || !top.length) return {};

  const mapping = {};
  top.forEach(g => { mapping[g.path] = g.id; });

  const level2Results = await Promise.all(
    top.map(g => kcFetch(`/groups/${g.id}/children?max=200`).then(r => r.data || []))
  );
  const level2 = level2Results.flat();
  level2.forEach(g => { mapping[g.path] = g.id; });

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
  const map  = await fetchAllGroups();
  const full = `${parentPath}/${name}`;
  if (map[full]) return map[full];
  await kcFetch(`/groups/${parentId}/children`, "POST", { name });
  const fresh = await fetchAllGroups();
  return fresh[full] || null;
}

// ── Permission helpers ───────────────────────────────────────────────────────
function roles(req)  { return req.auth?.realm_access?.roles || []; }
function groups(req) { return req.auth?.groups || []; }
const isSuperAdmin = (req) => roles(req).includes("super-admin");
const isOrgAdmin   = (req, org) =>
  isSuperAdmin(req) || groups(req).includes(`/${org}/admins`);
const isProjAdmin  = (req, org, project) =>
  isSuperAdmin(req) ||
  groups(req).includes(`/${org}/admins`) ||
  groups(req).includes(`/${org}/${project}/admins`);

const requireSuperAdmin = [checkJwt, (req, res, next) => {
  if (!isSuperAdmin(req)) return res.status(403).json({ error: "Super-admin required" });
  next();
}];

function requireOrgAdmin(param = "org") {
  return [checkJwt, (req, res, next) => {
    if (!isOrgAdmin(req, req.params[param]))
      return res.status(403).json({ error: "Org-admin required" });
    next();
  }];
}

function requireProjectAdmin() {
  return [checkJwt, (req, res, next) => {
    const { org, project } = req.params;
    if (!isProjAdmin(req, org, project))
      return res.status(403).json({ error: "Project-admin required" });
    next();
  }];
}

// ── parseGroups ──────────────────────────────────────────────────────────────
function parseGroups(claims) {
  const gs    = claims.groups || [];
  const parts = (g) => g.split("/").filter(Boolean);
  const orgs  = [...new Set(
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
// USER ROUTES
// ═══════════════════════════════════════════════════════════════════════════

app.get("/api/me", checkJwt, (req, res) => {
  const c = req.auth;
  const { orgs, projectsForOrg } = parseGroups(c);
  res.json({
    sub:         c.sub,
    username:    c.preferred_username,
    email:       c.email,
    firstName:   c.given_name,
    lastName:    c.family_name,
    isSuperAdmin: isSuperAdmin(req),
    orgs,
    allProjects: Object.fromEntries(orgs.map(o => [o, projectsForOrg(o)])),
  });
});

app.get("/api/orgs", checkJwt, (req, res) => {
  const { orgs } = parseGroups(req.auth);
  res.json({ orgs });
});

app.get("/api/orgs/:org/projects", checkJwt, (req, res) => {
  const { org } = req.params;
  const { orgs, projectsForOrg } = parseGroups(req.auth);
  if (!orgs.includes(org))
    return res.status(403).json({ error: "Not a member of this organisation" });
  res.json({ org, projects: projectsForOrg(org) });
});

// ═══════════════════════════════════════════════════════════════════════════
// USER MFA ROUTES
// ═══════════════════════════════════════════════════════════════════════════

app.get("/api/user/mfa-status", checkJwt, async (req, res) => {
  const userId = req.auth.sub;
  try {
    const { data } = await kcFetch(`/users/${userId}/credentials`);
    const creds = data || [];
    res.json({
      totp:     creds.some(c => c.type === "otp"),
      webauthn: creds.filter(c => c.type === "webauthn").map(c => ({ id: c.id, label: c.userLabel || "Security Key" })),
      passkeys: creds.filter(c => c.type === "webauthn-passwordless").map(c => ({ id: c.id, label: c.userLabel || "Passkey" })),
    });
  } catch (e) {
    console.error("[mfa-status]", e.message);
    res.status(500).json({ error: "Failed to fetch MFA status" });
  }
});

app.delete("/api/user/mfa/:credentialId", checkJwt, async (req, res) => {
  const userId       = req.auth.sub;
  const { credentialId } = req.params;
  if (!/^[a-f0-9-]{36}$/.test(credentialId))
    return res.status(400).json({ error: "Invalid credential ID" });
  try {
    const { data: creds } = await kcFetch(`/users/${userId}/credentials`);
    if (!(creds || []).some(c => c.id === credentialId))
      return res.status(403).json({ error: "Credential not found" });
    await kcFetch(`/users/${userId}/credentials/${credentialId}`, "DELETE");
    res.json({ ok: true });
  } catch (e) {
    console.error("[mfa-delete]", e.message);
    res.status(500).json({ error: "Failed to remove credential" });
  }
});

// ═══════════════════════════════════════════════════════════════════════════
// SHARED ADMIN UTILITIES
// ═══════════════════════════════════════════════════════════════════════════

// User search — scoped to org jurisdiction for non-super-admins (M8)
app.get("/api/admin/users", checkJwt, (req, res, next) => {
  const isAnyAdmin =
    isSuperAdmin(req) ||
    (req.auth?.groups || []).some(g => g.endsWith("/admins"));
  if (!isAnyAdmin) return res.status(403).json({ error: "Admin access required" });
  next();
}, async (req, res) => {
  try {
    const search = req.query.search ? `&search=${encodeURIComponent(req.query.search)}` : "";
    const { data } = await kcFetch(`/users?max=50${search}`);
    let users = (data || []).map(u => ({
      id: u.id, username: u.username, email: u.email,
      firstName: u.firstName, lastName: u.lastName,
    }));

    if (!isSuperAdmin(req)) {
      // Only return users who belong to groups this admin manages
      const adminOrgPaths = (req.auth?.groups || [])
        .filter(g => g.endsWith("/admins"))
        .map(g => g.replace("/admins", ""));
      const allowed = new Set();
      await Promise.all(adminOrgPaths.map(async orgPath => {
        const orgId = await getGroupId(orgPath);
        if (!orgId) return;
        const { data: members } = await kcFetch(`/groups/${orgId}/members?max=500`);
        (members || []).forEach(m => allowed.add(m.id));
      }));
      users = users.filter(u => allowed.has(u.id));
    }

    res.json({ users });
  } catch (e) {
    console.error("[admin-users]", e.message);
    res.status(500).json({ error: "Failed to search users" });
  }
});

// ═══════════════════════════════════════════════════════════════════════════
// SUPER-ADMIN ROUTES
// ═══════════════════════════════════════════════════════════════════════════

app.get("/api/admin/super/orgs", requireSuperAdmin, async (req, res) => {
  try {
    const groupMap = await fetchAllGroups();
    const orgs = Object.entries(groupMap)
      .filter(([path]) => path.split("/").filter(Boolean).length === 1)
      .map(([path, id]) => {
        const name     = path.slice(1);
        const projects = Object.keys(groupMap).filter(p => {
          const pts = p.split("/").filter(Boolean);
          return pts.length === 2 && pts[0] === name && pts[1] !== "admins";
        }).map(p => p.split("/").filter(Boolean)[1]);
        return { name, id, projects };
      });
    res.json({ orgs });
  } catch (e) {
    console.error("[super-orgs]", e.message);
    res.status(500).json({ error: "Failed to list orgs" });
  }
});

app.post("/api/admin/super/orgs", requireSuperAdmin, async (req, res) => {
  const { name } = req.body;
  if (!name || typeof name !== "string" || !/^[a-z0-9][a-z0-9-]{0,48}$/.test(name.trim().toLowerCase()))
    return res.status(400).json({ error: "Invalid org name (lowercase letters, numbers, hyphens only)" });
  const slug      = name.trim().toLowerCase().replace(/\s+/g, "-");
  const { status } = await kcFetch("/groups", "POST", { name: slug });
  if (status === 201) {
    const id = await getGroupId(`/${slug}`);
    if (id) await kcFetch(`/groups/${id}/children`, "POST", { name: "admins" });
    return res.status(201).json({ name: slug });
  }
  if (status === 409) return res.status(409).json({ error: "Org already exists" });
  res.status(500).json({ error: "Failed to create org" });
});

app.post("/api/admin/super/orgs/:org/projects", requireSuperAdmin, async (req, res) => {
  const { org }  = req.params;
  const { name } = req.body;
  if (!name || typeof name !== "string" || !/^[a-z0-9][a-z0-9-]{0,48}$/.test(name.trim().toLowerCase()))
    return res.status(400).json({ error: "Invalid project name (lowercase letters, numbers, hyphens only)" });
  const slug  = name.trim().toLowerCase().replace(/\s+/g, "-");
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

app.post("/api/admin/super/users", requireSuperAdmin, async (req, res) => {
  const { username, email, firstName, lastName, password } = req.body;
  if (!username || typeof username !== "string" || username.trim().length < 3)
    return res.status(400).json({ error: "Username must be at least 3 characters" });
  const pwError = validatePassword(password);
  if (pwError) return res.status(400).json({ error: pwError });
  const { status, data } = await kcFetch("/users", "POST", {
    username:   username.trim(),
    email:      email      || undefined,
    firstName:  firstName  || undefined,
    lastName:   lastName   || undefined,
    enabled:    true,
    emailVerified: true,
    credentials: [{ type: "password", value: password, temporary: false }],
  });
  if (status === 201) return res.status(201).json({ ok: true });
  if (status === 409) return res.status(409).json({ error: "Username already exists" });
  console.error("[super-create-user] Keycloak error:", data);
  return res.status(500).json({ error: "Failed to create user" });
});

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
    console.error("[super-user-profile]", e.message);
    res.status(500).json({ error: "Failed to fetch user profile" });
  }
});

app.post("/api/admin/super/users/:userId/groups", requireSuperAdmin, async (req, res) => {
  const { userId } = req.params;
  const { path }   = req.body;
  if (!isValidGroupPath(path)) return res.status(400).json({ error: "Invalid group path" });
  const gid = await getGroupId(path);
  if (!gid) return res.status(404).json({ error: `Group not found: ${path}` });
  await kcFetch(`/users/${userId}/groups/${gid}`, "PUT");
  res.json({ ok: true });
});

app.delete("/api/admin/super/users/:userId/groups", requireSuperAdmin, async (req, res) => {
  const { userId } = req.params;
  const { path }   = req.body;
  if (!isValidGroupPath(path)) return res.status(400).json({ error: "Invalid group path" });
  const gid = await getGroupId(path);
  if (!gid) return res.status(404).json({ error: `Group not found: ${path}` });
  await kcFetch(`/users/${userId}/groups/${gid}`, "DELETE");
  res.json({ ok: true });
});

app.post("/api/admin/super/users/:userId/roles", requireSuperAdmin, async (req, res) => {
  const { userId } = req.params;
  const { name }   = req.body;
  if (!name || typeof name !== "string") return res.status(400).json({ error: "name required" });
  const { data: role } = await kcFetch(`/roles/${encodeURIComponent(name)}`);
  if (!role?.id) return res.status(404).json({ error: "Role not found" });
  await kcFetch(`/users/${userId}/role-mappings/realm`, "POST", [role]);
  res.json({ ok: true });
});

app.delete("/api/admin/super/users/:userId/roles/:roleName", requireSuperAdmin, async (req, res) => {
  const { userId, roleName } = req.params;
  const { data: role } = await kcFetch(`/roles/${encodeURIComponent(roleName)}`);
  if (!role?.id) return res.status(404).json({ error: "Role not found" });
  await kcFetch(`/users/${userId}/role-mappings/realm`, "DELETE", [role]);
  res.json({ ok: true });
});

app.get("/api/admin/super/users", requireSuperAdmin, async (req, res) => {
  const search = req.query.search ? `&search=${encodeURIComponent(req.query.search)}` : "";
  const { data } = await kcFetch(`/users?max=100${search}`);
  res.json({
    users: (data || []).map(u => ({
      id: u.id, username: u.username, email: u.email,
      firstName: u.firstName, lastName: u.lastName, enabled: u.enabled,
    })),
  });
});

app.get("/api/admin/super/roles", requireSuperAdmin, async (req, res) => {
  const { data } = await kcFetch("/roles");
  const SKIP = ["offline_access", "uma_authorization", `default-roles-${KC_REALM}`];
  res.json({
    roles: (data || [])
      .filter(r => !r.composite && !SKIP.includes(r.name))
      .map(r => ({
        id:          r.id,
        name:        r.name,
        description: r.description,
        roleType:    r.attributes?.type?.[0]     || "global",
        orgScope:    r.attributes?.orgScope?.[0] || null,
        permissions: r.attributes?.permissions   || [],
        projectScope: r.attributes?.projectScope || [],
      })),
  });
});

app.post("/api/admin/super/roles", requireSuperAdmin, async (req, res) => {
  const { name, description = "", roleType = "global", orgScope, permissions = [], projectScope = [] } = req.body;
  if (!name || typeof name !== "string") return res.status(400).json({ error: "name is required" });
  const attributes = { type: [roleType] };
  if (roleType === "org" && orgScope)  attributes.orgScope     = [orgScope];
  if (permissions.length > 0)         attributes.permissions  = permissions;
  if (projectScope.length > 0)        attributes.projectScope = projectScope;
  const { status } = await kcFetch("/roles", "POST", { name, description, attributes });
  if (status === 201) return res.status(201).json({ name });
  if (status === 409) return res.status(409).json({ error: "Role already exists" });
  res.status(500).json({ error: "Failed to create role" });
});

app.put("/api/admin/super/users/:userId/roles/:roleName", requireSuperAdmin, async (req, res) => {
  const { userId, roleName } = req.params;
  const { data: role } = await kcFetch(`/roles/${encodeURIComponent(roleName)}`);
  if (!role?.id) return res.status(404).json({ error: "Role not found" });
  const { status } = await kcFetch(`/users/${userId}/role-mappings/realm`, "POST", [role]);
  res.status(status === 204 ? 200 : status).json({ ok: status === 204 });
});

app.put("/api/admin/super/orgs/:org/admins/:userId", requireSuperAdmin, async (req, res) => {
  const { org, userId } = req.params;
  const map     = await fetchAllGroups();
  const orgId   = map[`/${org}`];
  const adminId = map[`/${org}/admins`];
  if (!orgId || !adminId) return res.status(404).json({ error: "Org or admins group not found" });
  await kcFetch(`/users/${userId}/groups/${orgId}`,   "PUT");
  await kcFetch(`/users/${userId}/groups/${adminId}`, "PUT");
  res.json({ ok: true });
});

app.put("/api/admin/super/orgs/:org/projects/:project/admins/:userId", requireSuperAdmin, async (req, res) => {
  const { org, project, userId } = req.params;
  const map     = await fetchAllGroups();
  const projId  = map[`/${org}/${project}`];
  const adminId = map[`/${org}/${project}/admins`];
  if (!projId || !adminId) return res.status(404).json({ error: "Project or admins group not found" });
  await kcFetch(`/users/${userId}/groups/${projId}`,  "PUT");
  await kcFetch(`/users/${userId}/groups/${adminId}`, "PUT");
  res.json({ ok: true });
});

app.get("/api/admin/super/auth/idps", requireSuperAdmin, async (req, res) => {
  try {
    const { data } = await kcFetch("/identity-provider/instances");
    res.json({
      idps: (data || []).map(p => ({
        alias: p.alias, displayName: p.displayName || p.alias,
        providerId: p.providerId, enabled: p.enabled,
      })),
    });
  } catch (e) {
    console.error("[super-auth-idps]", e.message);
    res.status(500).json({ error: "Failed to list identity providers" });
  }
});

app.get("/api/admin/super/auth/actions", requireSuperAdmin, async (req, res) => {
  try {
    const { data } = await kcFetch("/authentication/required-actions");
    res.json({
      actions: (data || []).map(a => ({
        alias: a.alias, name: a.name,
        enabled: a.enabled, defaultAction: a.defaultAction,
      })),
    });
  } catch (e) {
    console.error("[super-auth-actions]", e.message);
    res.status(500).json({ error: "Failed to list required actions" });
  }
});

// ═══════════════════════════════════════════════════════════════════════════
// ORG-ADMIN ROUTES
// ═══════════════════════════════════════════════════════════════════════════

app.get("/api/admin/org/:org/projects", requireOrgAdmin(), async (req, res) => {
  const { org } = req.params;
  try {
    const orgId = await getGroupId(`/${org}`);
    if (!orgId) return res.status(404).json({ error: "Org not found" });
    const { data } = await kcFetch(`/groups/${orgId}/children?max=200`);
    const projects = (data || []).filter(g => g.name !== "admins").map(g => g.name);
    res.json({ org, projects });
  } catch (e) {
    console.error("[org-projects]", e.message);
    res.status(500).json({ error: "Failed to list projects" });
  }
});

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
      id: uRes.data?.id, username: uRes.data?.username,
      email: uRes.data?.email, firstName: uRes.data?.firstName,
      lastName: uRes.data?.lastName, projects,
    });
  } catch (e) {
    console.error("[org-member]", e.message);
    res.status(500).json({ error: "Failed to fetch member details" });
  }
});

app.get("/api/admin/org/:org/members", requireOrgAdmin(), async (req, res) => {
  const { org } = req.params;
  const orgId   = await getGroupId(`/${org}`);
  if (!orgId) return res.status(404).json({ error: "Org not found" });
  const { data } = await kcFetch(`/groups/${orgId}/members`);
  res.json({
    org,
    members: (data || []).map(u => ({
      id: u.id, username: u.username, email: u.email,
      firstName: u.firstName, lastName: u.lastName,
    })),
  });
});

app.put("/api/admin/org/:org/members/:userId", requireOrgAdmin(), async (req, res) => {
  const { org, userId } = req.params;
  const orgId = await getGroupId(`/${org}`);
  if (!orgId) return res.status(404).json({ error: "Org not found" });
  const { status } = await kcFetch(`/users/${userId}/groups/${orgId}`, "PUT");
  res.json({ ok: status === 204 });
});

app.delete("/api/admin/org/:org/members/:userId", requireOrgAdmin(), async (req, res) => {
  const { org, userId } = req.params;
  const orgId = await getGroupId(`/${org}`);
  if (!orgId) return res.status(404).json({ error: "Org not found" });
  const { status } = await kcFetch(`/users/${userId}/groups/${orgId}`, "DELETE");
  res.json({ ok: status === 204 });
});

app.post("/api/admin/org/:org/projects", requireOrgAdmin(), async (req, res) => {
  const { org } = req.params;
  const { name } = req.body;
  if (!name || typeof name !== "string") return res.status(400).json({ error: "name is required" });
  const slug  = name.trim().toLowerCase().replace(/\s+/g, "-");
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

app.get("/api/admin/project/:org/:project/members", requireProjectAdmin(), async (req, res) => {
  const { org, project } = req.params;
  const projId = await getGroupId(`/${org}/${project}`);
  if (!projId) return res.status(404).json({ error: "Project not found" });
  const { data } = await kcFetch(`/groups/${projId}/members`);
  res.json({
    org, project,
    members: (data || []).map(u => ({
      id: u.id, username: u.username, email: u.email,
      firstName: u.firstName, lastName: u.lastName,
    })),
  });
});

app.put("/api/admin/project/:org/:project/members/:userId", requireProjectAdmin(), async (req, res) => {
  const { org, project, userId } = req.params;
  const map    = await fetchAllGroups();
  const orgId  = map[`/${org}`];
  const projId = map[`/${org}/${project}`];
  if (!projId) return res.status(404).json({ error: "Project not found" });
  if (orgId) await kcFetch(`/users/${userId}/groups/${orgId}`, "PUT");
  await kcFetch(`/users/${userId}/groups/${projId}`, "PUT");
  res.json({ ok: true });
});

app.delete("/api/admin/project/:org/:project/members/:userId", requireProjectAdmin(), async (req, res) => {
  const { org, project, userId } = req.params;
  const projId = await getGroupId(`/${org}/${project}`);
  if (!projId) return res.status(404).json({ error: "Project not found" });
  const { status } = await kcFetch(`/users/${userId}/groups/${projId}`, "DELETE");
  res.json({ ok: status === 204 });
});

// ── Error handler ────────────────────────────────────────────────────────────
app.use((err, _req, res, _next) => {
  if (err.name === "UnauthorizedError")
    return res.status(401).json({ error: "Invalid or missing token" });
  console.error("[unhandled]", err.message);
  res.status(500).json({ error: "Internal server error" });
});

app.listen(PORT, () => console.log(`Backend running on http://localhost:${PORT}`));
