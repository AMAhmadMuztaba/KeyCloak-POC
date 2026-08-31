"""
Keycloak demo-data initialiser – role hierarchy edition.

Roles
  super-admin  →  alice
  org admin    →  bob  (org-alpha/admins)
  project admin→  carol (org-beta/project-3/admins)
  user         →  dave
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

KC_URL   = os.environ.get("KC_URL",                    "http://keycloak:8080")
REALM    = os.environ.get("KC_REALM",                  "app-realm")
ADMIN    = os.environ.get("KEYCLOAK_ADMIN",            "admin")
ADMIN_PW = os.environ.get("KEYCLOAK_ADMIN_PASSWORD",   "admin123")


# ── HTTP helpers ─────────────────────────────────────────────────────────────

def _req(method, url, data=None, token=None, content_type="application/json"):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if data is not None:
        if isinstance(data, (dict, list)):
            data = json.dumps(data).encode()
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            body = r.read()
            return r.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        return e.code, {}


def get(url, token=None):
    _, data = _req("GET", url, token=token)
    return data


def post(url, payload, token=None, form=False):
    if form:
        data = urllib.parse.urlencode(payload).encode()
        return _req("POST", url, data=data, token=token,
                    content_type="application/x-www-form-urlencoded")
    return _req("POST", url, data=payload, token=token)


def put(url, token=None):
    return _req("PUT", url, token=token)


# ── Auth ─────────────────────────────────────────────────────────────────────

def get_token():
    _, resp = post(
        f"{KC_URL}/realms/master/protocol/openid-connect/token",
        {"grant_type": "password", "client_id": "admin-cli",
         "username": ADMIN, "password": ADMIN_PW},
        form=True,
    )
    return resp.get("access_token")


# ── Wait for realm ────────────────────────────────────────────────────────────

def wait_for_realm():
    print(f"Waiting for realm '{REALM}' …", flush=True)
    while True:
        try:
            urllib.request.urlopen(f"{KC_URL}/realms/{REALM}", timeout=5)
            print("Realm is ready.", flush=True)
            return
        except Exception:
            print("  still waiting …", flush=True)
            time.sleep(5)


# ── Realm-role helpers ────────────────────────────────────────────────────────

def ensure_realm_role(token, name, description=""):
    status, _ = post(
        f"{KC_URL}/admin/realms/{REALM}/roles",
        {"name": name, "description": description},
        token=token,
    )
    if status == 201:
        print(f"  Created realm role '{name}'", flush=True)
    elif status == 409:
        print(f"  Role '{name}' already exists", flush=True)


def get_realm_role(token, name):
    return get(f"{KC_URL}/admin/realms/{REALM}/roles/{name}", token)


def assign_realm_roles(token, user_id, roles):
    post(
        f"{KC_URL}/admin/realms/{REALM}/users/{user_id}/role-mappings/realm",
        roles,
        token=token,
    )


# ── User helpers ──────────────────────────────────────────────────────────────

def create_user(token, username, email, first, last, password):
    status, _ = post(
        f"{KC_URL}/admin/realms/{REALM}/users",
        {
            "username": username, "email": email,
            "firstName": first,   "lastName": last,
            "enabled": True, "emailVerified": True,
            "credentials": [{"type": "password", "value": password, "temporary": False}],
        },
        token=token,
    )
    if status == 201:
        print(f"  Created  {username}", flush=True)
    elif status == 409:
        print(f"  {username} already exists – skipping", flush=True)
    else:
        print(f"  {username}: unexpected HTTP {status}", flush=True)


def get_user_id(token, username):
    users = get(
        f"{KC_URL}/admin/realms/{REALM}/users?username={username}&exact=true",
        token,
    )
    return users[0]["id"] if users else None


# ── Group helpers ─────────────────────────────────────────────────────────────

def get_all_groups(token):
    """Flat map  path → id  for every group + subgroup.
    Keycloak 24 returns empty subGroups in brief repr; we call /children explicitly."""
    top = get(f"{KC_URL}/admin/realms/{REALM}/groups", token)
    mapping = {}

    def recurse(groups):
        for g in groups:
            mapping[g["path"]] = g["id"]
            children = get(
                f"{KC_URL}/admin/realms/{REALM}/groups/{g['id']}/children", token
            )
            if children:
                recurse(children)

    recurse(top)
    return mapping


def ensure_subgroup(token, parent_id, name, all_groups_ref, parent_path):
    """Create subgroup under parent if it doesn't exist; update all_groups_ref in place."""
    full_path = f"{parent_path}/{name}"
    if full_path in all_groups_ref:
        return all_groups_ref[full_path]
    status, _ = post(
        f"{KC_URL}/admin/realms/{REALM}/groups/{parent_id}/children",
        {"name": name},
        token=token,
    )
    if status in (201, 204):
        print(f"  Created subgroup '{full_path}'", flush=True)
        # Re-fetch to get the new id
        fresh = get_all_groups(token)
        all_groups_ref.update(fresh)
        return all_groups_ref.get(full_path)
    elif status == 409:
        fresh = get_all_groups(token)
        all_groups_ref.update(fresh)
        return all_groups_ref.get(full_path)
    else:
        print(f"  Warning: subgroup create '{full_path}' returned {status}", flush=True)
        return None


def assign_group(token, user_id, group_id):
    put(f"{KC_URL}/admin/realms/{REALM}/users/{user_id}/groups/{group_id}", token)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    wait_for_realm()

    print("Acquiring admin token …", flush=True)
    token = get_token()
    if not token:
        raise RuntimeError("Could not obtain admin token – check credentials.")

    # ── Ensure roles exist ────────────────────────────────────────────────
    print("\nEnsuring realm roles …", flush=True)
    ensure_realm_role(token, "super-admin",
                      "System-wide super administrator")
    ensure_realm_role(token, "user",
                      "Regular project member")

    # ── Create demo users ─────────────────────────────────────────────────
    print("\nCreating demo users …", flush=True)
    create_user(token, "alice", "alice@example.com", "Alice", "Admin",   "alice123")
    create_user(token, "bob",   "bob@example.com",   "Bob",   "OrgAdm",  "bob123")
    create_user(token, "carol", "carol@example.com", "Carol", "ProjAdm", "carol123")
    create_user(token, "dave",  "dave@example.com",  "Dave",  "User",    "dave123")

    alice_id = get_user_id(token, "alice")
    bob_id   = get_user_id(token, "bob")
    carol_id = get_user_id(token, "carol")
    dave_id  = get_user_id(token, "dave")

    # ── Assign realm roles ────────────────────────────────────────────────
    print("\nAssigning realm roles …", flush=True)
    super_admin_role = get_realm_role(token, "super-admin")
    user_role        = get_realm_role(token, "user")

    assign_realm_roles(token, alice_id, [super_admin_role])   # alice = super-admin
    assign_realm_roles(token, bob_id,   [user_role])          # bob   = user + org-admin via group
    assign_realm_roles(token, carol_id, [user_role])          # carol = user + project-admin via group
    assign_realm_roles(token, dave_id,  [user_role])          # dave  = regular user
    print("  Realm roles assigned.", flush=True)

    # ── Fetch / ensure group tree ─────────────────────────────────────────
    print("\nBuilding org/project group tree …", flush=True)
    groups = get_all_groups(token)

    # Ensure each org has an 'admins' subgroup,
    # and each project under that org has an 'admins' subgroup.
    org_structure = {
        "org-alpha":  ["project-1", "project-2"],
        "org-beta":   ["project-3"],
        "org-gamma":  ["project-4", "project-5"],
    }

    for org, projects in org_structure.items():
        org_path = f"/{org}"
        org_id   = groups.get(org_path)
        if not org_id:
            print(f"  Group not found: {org_path} – realm import may not have run", flush=True)
            continue

        # /org/admins
        ensure_subgroup(token, org_id, "admins", groups, org_path)

        for project in projects:
            proj_path = f"{org_path}/{project}"
            proj_id   = groups.get(proj_path)
            if not proj_id:
                print(f"  Group not found: {proj_path}", flush=True)
                continue
            # /org/project/admins
            ensure_subgroup(token, proj_id, "admins", groups, proj_path)

    print("  Group tree ready.", flush=True)

    # Re-fetch after potential group creation
    groups = get_all_groups(token)

    def gid(path):
        g = groups.get(path)
        if not g:
            print(f"  WARNING – group not found: {path}", flush=True)
        return g

    # ── alice – super admin, member of ALL orgs + projects ─────────────
    print("\nAssigning alice to all orgs/projects …", flush=True)
    alice_paths = [
        "/org-alpha", "/org-alpha/admins",
        "/org-alpha/project-1", "/org-alpha/project-1/admins",
        "/org-alpha/project-2", "/org-alpha/project-2/admins",
        "/org-beta",  "/org-beta/admins",
        "/org-beta/project-3",  "/org-beta/project-3/admins",
        "/org-gamma", "/org-gamma/admins",
        "/org-gamma/project-4", "/org-gamma/project-4/admins",
        "/org-gamma/project-5", "/org-gamma/project-5/admins",
    ]
    for path in alice_paths:
        g = gid(path)
        if g:
            assign_group(token, alice_id, g)

    # ── bob – org admin of org-alpha, member of project-1 ─────────────
    print("Assigning bob …", flush=True)
    bob_paths = [
        "/org-alpha", "/org-alpha/admins",
        "/org-alpha/project-1",
    ]
    for path in bob_paths:
        g = gid(path)
        if g:
            assign_group(token, bob_id, g)

    # ── carol – project admin of org-beta/project-3 ───────────────────
    print("Assigning carol …", flush=True)
    carol_paths = [
        "/org-beta", "/org-beta/project-3", "/org-beta/project-3/admins",
    ]
    for path in carol_paths:
        g = gid(path)
        if g:
            assign_group(token, carol_id, g)

    # ── dave – regular user in org-alpha + org-gamma ──────────────────
    print("Assigning dave …", flush=True)
    dave_paths = [
        "/org-alpha", "/org-alpha/project-2",
        "/org-gamma", "/org-gamma/project-4", "/org-gamma/project-5",
    ]
    for path in dave_paths:
        g = gid(path)
        if g:
            assign_group(token, dave_id, g)

    print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Keycloak demo data ready!

 Demo accounts
 ┌──────┬──────────┬─────────────┬───────────────────────────────────────────┐
 │ User │ Password │ Role        │ Access                                    │
 ├──────┼──────────┼─────────────┼───────────────────────────────────────────┤
 │alice │ alice123 │ super-admin │ All orgs/projects – full system admin     │
 │bob   │ bob123   │ user        │ org-alpha (ORG ADMIN) + project-1 member  │
 │carol │ carol123 │ user        │ org-beta / project-3 (PROJECT ADMIN)      │
 │dave  │ dave123  │ user        │ org-alpha/project-2 + org-gamma           │
 └──────┴──────────┴─────────────┴───────────────────────────────────────────┘

 Keycloak admin console: http://localhost:8080  (admin / admin123)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""", flush=True)


if __name__ == "__main__":
    main()
