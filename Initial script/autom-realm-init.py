"""
autom-realm initialiser.

Creates the autom-realm on the Keycloak server at 172.16.2.42:8080 with:
  - Clients: autom-app (SPA), autom-superadmin (SPA), autom-backend (service account)
  - Roles:   super-admin, user
  - Groups:  /org-{name}, /org-{name}/admins, /org-{name}/{project}, /org-{name}/{project}/admins
  - Demo users: alice (super-admin), bob (org-admin), carol (project-admin), dave (user)
  - Security: brute-force protection, password policy, session timeouts
  - TOTP required action enabled
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

KC_URL   = os.environ.get("KC_URL",               "http://172.16.2.42:8080")
REALM    = os.environ.get("KC_REALM",             "autom-realm")
ADMIN    = os.environ.get("KEYCLOAK_ADMIN",       "admin")
ADMIN_PW = os.environ.get("KEYCLOAK_ADMIN_PASSWORD", "admin")

# Origins to allow for each SPA client (add more as needed)
APP_ORIGINS       = ["http://localhost:5173", "http://localhost:3000"]
SUPERADMIN_ORIGINS = ["http://localhost:5174", "http://localhost:3001"]

# Public HTTPS URL where Keycloak is exposed via the superadmin nginx proxy.
# Keycloak's frontendUrl is set to this so login pages and token issuers use
# the HTTPS path instead of the raw http://172.16.2.42:8080 address.
KEYCLOAK_FRONTEND_URL = "https://superadmin-autom.inb.seliselocal.com/auth"


# ── HTTP helpers ──────────────────────────────────────────────────────────────

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
        with urllib.request.urlopen(req, timeout=15) as r:
            body = r.read()
            return r.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read()
        return e.code, json.loads(body) if body else {}


def get(url, token=None):
    _, data = _req("GET", url, token=token)
    return data


def post(url, payload, token=None, form=False):
    if form:
        data = urllib.parse.urlencode(payload).encode()
        return _req("POST", url, data=data, token=token,
                    content_type="application/x-www-form-urlencoded")
    return _req("POST", url, data=payload, token=token)


def put_body(url, payload, token=None):
    return _req("PUT", url, data=payload, token=token)


def delete(url, token=None):
    return _req("DELETE", url, token=token)


# ── Auth ──────────────────────────────────────────────────────────────────────

def get_token():
    _, resp = post(
        f"{KC_URL}/realms/master/protocol/openid-connect/token",
        {"grant_type": "password", "client_id": "admin-cli",
         "username": ADMIN, "password": ADMIN_PW},
        form=True,
    )
    return resp.get("access_token")


# ── Wait for Keycloak ─────────────────────────────────────────────────────────

def wait_for_keycloak():
    print(f"Waiting for Keycloak at {KC_URL} …", flush=True)
    for _ in range(60):
        try:
            urllib.request.urlopen(f"{KC_URL}/realms/master", timeout=5)
            print("Keycloak is ready.", flush=True)
            return
        except Exception:
            print("  still waiting …", flush=True)
            time.sleep(5)
    raise RuntimeError("Keycloak did not become ready in time.")


# ── Realm ─────────────────────────────────────────────────────────────────────

def ensure_realm(token):
    status, _ = _req("GET", f"{KC_URL}/admin/realms/{REALM}", token=token)
    if status == 200:
        print(f"  Realm '{REALM}' already exists.", flush=True)
        return
    status, resp = post(
        f"{KC_URL}/admin/realms",
        {
            "realm": REALM,
            "displayName": "Autom",
            "enabled": True,
            "registrationAllowed": False,
            "resetPasswordAllowed": False,
            "editUsernameAllowed": False,
            "sslRequired": "external",
        },
        token=token,
    )
    if status == 201:
        print(f"  Created realm '{REALM}'.", flush=True)
    else:
        raise RuntimeError(f"Could not create realm '{REALM}': HTTP {status} — {resp}")


# ── Roles ─────────────────────────────────────────────────────────────────────

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
    else:
        print(f"  Warning: role '{name}' returned {status}", flush=True)


def get_realm_role(token, name):
    return get(f"{KC_URL}/admin/realms/{REALM}/roles/{name}", token)


def assign_realm_roles(token, user_id, roles):
    post(
        f"{KC_URL}/admin/realms/{REALM}/users/{user_id}/role-mappings/realm",
        roles,
        token=token,
    )


# ── Clients ───────────────────────────────────────────────────────────────────

def _redirect_uris(origins):
    return [f"{o}/*" for o in origins] + ["http://localhost:*"]


def ensure_public_client(token, client_id, name, origins):
    """Create a public (SPA) PKCE client if it doesn't exist."""
    clients = get(f"{KC_URL}/admin/realms/{REALM}/clients?clientId={client_id}", token)
    if clients:
        print(f"  Client '{client_id}' already exists — syncing URIs", flush=True)
        internal_id = clients[0]["id"]
        # Keep redirect URIs and web origins in sync with what the script defines.
        put_body(
            f"{KC_URL}/admin/realms/{REALM}/clients/{internal_id}",
            {
                "redirectUris": _redirect_uris(origins),
                "webOrigins": origins,
            },
            token=token,
        )
    else:
        status, _ = post(
            f"{KC_URL}/admin/realms/{REALM}/clients",
            {
                "clientId": client_id,
                "name": name,
                "enabled": True,
                "publicClient": True,
                "standardFlowEnabled": True,
                "implicitFlowEnabled": False,
                "directAccessGrantsEnabled": False,
                "serviceAccountsEnabled": False,
                "redirectUris": _redirect_uris(origins),
                "webOrigins": origins,
                "attributes": {
                    "pkce.code.challenge.method": "S256",
                    "post.logout.redirect.uris": "+",
                },
            },
            token=token,
        )
        if status == 201:
            print(f"  Created public client '{client_id}'", flush=True)
        else:
            print(f"  Warning: create client '{client_id}' returned {status}", flush=True)
            return None
        clients = get(f"{KC_URL}/admin/realms/{REALM}/clients?clientId={client_id}", token)
        internal_id = clients[0]["id"]

    _ensure_group_mapper(token, internal_id, client_id)
    _ensure_audience_mapper(token, internal_id, client_id)
    if client_id == "autom-superadmin":
        _set_browser_flow_override(token, internal_id, client_id)
    return internal_id


def ensure_confidential_client(token, client_id, name):
    """Create a confidential client with service-account for backend use."""
    clients = get(f"{KC_URL}/admin/realms/{REALM}/clients?clientId={client_id}", token)
    if clients:
        print(f"  Client '{client_id}' already exists", flush=True)
        internal_id = clients[0]["id"]
    else:
        status, _ = post(
            f"{KC_URL}/admin/realms/{REALM}/clients",
            {
                "clientId": client_id,
                "name": name,
                "enabled": True,
                "publicClient": False,
                "standardFlowEnabled": False,
                "serviceAccountsEnabled": True,
                "directAccessGrantsEnabled": False,
                "authorizationServicesEnabled": False,
            },
            token=token,
        )
        if status == 201:
            print(f"  Created confidential client '{client_id}'", flush=True)
        else:
            print(f"  Warning: create client '{client_id}' returned {status}", flush=True)
            return None
        clients = get(f"{KC_URL}/admin/realms/{REALM}/clients?clientId={client_id}", token)
        internal_id = clients[0]["id"]

    # Grant the service account realm-management roles so it can call Admin API
    _grant_admin_roles_to_service_account(token, internal_id, client_id)
    return internal_id


def _get_flow_id_by_alias(token, alias):
    flows = get(f"{KC_URL}/admin/realms/{REALM}/authentication/flows", token)
    flow = next((f for f in flows if f.get("alias") == alias), None)
    return flow["id"] if flow else None


def _copy_flow(token, source_alias, new_alias):
    """Duplicate a flow by alias. Returns the new flow's UUID."""
    new_id = _get_flow_id_by_alias(token, new_alias)
    if new_id:
        return new_id  # already exists
    status, _ = post(
        f"{KC_URL}/admin/realms/{REALM}/authentication/flows/{urllib.parse.quote(source_alias)}/copy",
        {"newName": new_alias},
        token=token,
    )
    if status not in (201, 204):
        print(f"  Warning: copy flow '{source_alias}' → '{new_alias}' returned {status}", flush=True)
        return None
    return _get_flow_id_by_alias(token, new_alias)


def _get_flow_executions(token, flow_alias):
    return get(
        f"{KC_URL}/admin/realms/{REALM}/authentication/flows/{urllib.parse.quote(flow_alias)}/executions",
        token,
    ) or []


def _update_execution_in_flow(token, parent_flow_alias, exec_data, requirement):
    """Update an execution's requirement via its DIRECT parent flow's executions endpoint.

    KC has two representations for executions:
      GET /flows/{alias}/executions  → AuthenticationExecutionInfoRepresentation
      PUT /executions/{id}           → AuthenticationExecutionRepresentation (different fields!)

    The only API that accepts the InfoRepresentation (what GET returns) is:
      PUT /flows/{alias}/executions  ← this is what the Admin Console uses

    Always pass the IMMEDIATE parent alias, not the top-level flow alias.
    """
    payload = dict(exec_data)
    payload["requirement"] = requirement
    status, _ = put_body(
        f"{KC_URL}/admin/realms/{REALM}/authentication/flows/{urllib.parse.quote(parent_flow_alias)}/executions",
        payload,
        token=token,
    )
    return status


def _add_execution_to_flow(token, flow_alias, provider_id):
    """Add a new authenticator execution to a named flow or sub-flow."""
    status, _ = post(
        f"{KC_URL}/admin/realms/{REALM}/authentication/flows/{urllib.parse.quote(flow_alias)}/executions/execution",
        {"provider": provider_id},
        token=token,
    )
    return status


def _add_sub_flow(token, parent_alias, sub_alias, description=""):
    """Add a new sub-flow to an existing flow."""
    status, _ = post(
        f"{KC_URL}/admin/realms/{REALM}/authentication/flows/{urllib.parse.quote(parent_alias)}/executions/flow",
        {"alias": sub_alias, "type": "basic-flow", "description": description,
         "provider": "registration-page-form"},
        token=token,
    )
    return status


def _set_exec_config(token, exec_id, config_alias, config):
    """Attach authenticator-specific configuration to an execution."""
    status, _ = post(
        f"{KC_URL}/admin/realms/{REALM}/authentication/executions/{exec_id}/config",
        {"alias": config_alias, "config": config},
        token=token,
    )
    return status


def ensure_superadmin_browser_flow(token):
    """Build the 'Browser - SuperAdmin only' authentication flow from scratch.

    Built from scratch (NOT copied from 'browser') to avoid pulling in KC 26's
    Organization Identity-First Login sub-flow, which would show an email-only
    form before credentials — wrong UX for a super-admin portal.

    Structure:
        Browser - SuperAdmin only (top-level, basic-flow)
        ├── Cookie [ALTERNATIVE]
        ├── Identity Provider Redirector [ALTERNATIVE]
        └── Browser - SuperAdmin only forms [ALTERNATIVE]
            ├── Username Password Form [REQUIRED]
            └── Browser - SuperAdmin only super-admin gate [CONDITIONAL]
                ├── Condition - user role [REQUIRED]
                │   negate=true, condUserRole=super-admin
                │   → sub-flow activates only when user lacks super-admin role
                └── Deny access [REQUIRED]
                    → non-super-admins are blocked here

    Returns the flow's UUID.
    """
    FLOW_ALIAS  = "Browser - SuperAdmin only"
    FORMS_ALIAS = f"{FLOW_ALIAS} forms"
    GATE_ALIAS  = f"{FLOW_ALIAS} super-admin gate"

    existing_id = _get_flow_id_by_alias(token, FLOW_ALIAS)
    if existing_id:
        print(f"  Auth flow '{FLOW_ALIAS}' already exists — skipping creation", flush=True)
        return existing_id

    # Create top-level flow from scratch.
    status, _ = post(
        f"{KC_URL}/admin/realms/{REALM}/authentication/flows",
        {
            "alias":       FLOW_ALIAS,
            "providerId":  "basic-flow",
            "description": "Super-admin portal login — username/password + role gate, no org step",
            "topLevel":    True,
            "builtIn":     False,
        },
        token=token,
    )
    if status not in (201, 204):
        print(f"  Warning: creating '{FLOW_ALIAS}' returned {status}", flush=True)
        return None

    def latest_exec(provider_id):
        execs = _get_flow_executions(token, FLOW_ALIAS)
        return next((e for e in reversed(execs) if e.get("providerId") == provider_id), None)

    def latest_subflow(alias):
        execs = _get_flow_executions(token, FLOW_ALIAS)
        return next(
            (e for e in reversed(execs)
             if e.get("displayName") == alias or e.get("flowAlias") == alias),
            None,
        )

    # Cookie [ALTERNATIVE]
    _add_execution_to_flow(token, FLOW_ALIAS, "auth-cookie")
    exc = latest_exec("auth-cookie")
    if exc:
        _update_execution_in_flow(token, FLOW_ALIAS, exc, "ALTERNATIVE")

    # Identity Provider Redirector [ALTERNATIVE]
    _add_execution_to_flow(token, FLOW_ALIAS, "identity-provider-redirector")
    exc = latest_exec("identity-provider-redirector")
    if exc:
        _update_execution_in_flow(token, FLOW_ALIAS, exc, "ALTERNATIVE")

    # forms sub-flow [ALTERNATIVE]
    _add_sub_flow(token, FLOW_ALIAS, FORMS_ALIAS, "Super-admin credentials")
    exc = latest_subflow(FORMS_ALIAS)
    if exc:
        _update_execution_in_flow(token, FLOW_ALIAS, exc, "ALTERNATIVE")

    # Username Password Form [REQUIRED] inside forms
    _add_execution_to_flow(token, FORMS_ALIAS, "auth-username-password-form")
    exc = latest_exec("auth-username-password-form")
    if exc:
        _update_execution_in_flow(token, FORMS_ALIAS, exc, "REQUIRED")

    # super-admin gate [CONDITIONAL] inside forms
    _add_sub_flow(token, FORMS_ALIAS, GATE_ALIAS,
                  "Deny access to users who do not have the super-admin realm role")
    exc = latest_subflow(GATE_ALIAS)
    if exc:
        _update_execution_in_flow(token, FORMS_ALIAS, exc, "CONDITIONAL")

    # Condition - user role [REQUIRED] inside gate
    _add_execution_to_flow(token, GATE_ALIAS, "conditional-user-role")
    exc = latest_exec("conditional-user-role")
    if exc:
        _update_execution_in_flow(token, GATE_ALIAS, exc, "REQUIRED")
        _set_exec_config(
            token, exc["id"],
            "no-super-admin",
            {"condUserRole": "super-admin", "negate": "true"},
        )

    # Deny access [REQUIRED] inside gate
    _add_execution_to_flow(token, GATE_ALIAS, "deny-access-authenticator")
    exc = latest_exec("deny-access-authenticator")
    if exc:
        _update_execution_in_flow(token, GATE_ALIAS, exc, "REQUIRED")

    print(f"  Created super-admin browser flow '{FLOW_ALIAS}'", flush=True)
    return _get_flow_id_by_alias(token, FLOW_ALIAS)


def _set_browser_flow_override(token, internal_id, client_id):
    """Pin autom-superadmin to the 'Browser - SuperAdmin only' browser flow.

    This flow extends the built-in KC 26 browser flow (which includes the
    org-aware Organization sub-flow) with a role gate that denies access to
    any user who is not a super-admin.  Super-admin users are never KC org
    members, so the Organization sub-flow is skipped for them automatically.
    """
    flow_id = ensure_superadmin_browser_flow(token)
    if not flow_id:
        print(f"  Warning: superadmin browser flow unavailable — skipping override for '{client_id}'",
              flush=True)
        return

    status, _ = put_body(
        f"{KC_URL}/admin/realms/{REALM}/clients/{internal_id}",
        {"authenticationFlowBindingOverrides": {"browser": flow_id}},
        token=token,
    )
    if status in (200, 204):
        print(f"  Browser-flow override: 'Browser - SuperAdmin only' on '{client_id}'", flush=True)
    else:
        print(f"  Warning: setting browser-flow override returned {status}", flush=True)


def _ensure_group_mapper(token, internal_id, client_id):
    mappers = get(f"{KC_URL}/admin/realms/{REALM}/clients/{internal_id}/protocol-mappers/models", token)
    if any(m.get("name") == "groups" for m in mappers):
        print(f"  Group mapper already on '{client_id}'", flush=True)
        return
    status, _ = post(
        f"{KC_URL}/admin/realms/{REALM}/clients/{internal_id}/protocol-mappers/models",
        {
            "name": "groups",
            "protocol": "openid-connect",
            "protocolMapper": "oidc-group-membership-mapper",
            "consentRequired": False,
            "config": {
                "full.path": "true",
                "id.token.claim": "true",
                "access.token.claim": "true",
                "userinfo.token.claim": "true",
                "claim.name": "groups",
            },
        },
        token=token,
    )
    if status in (200, 201):
        print(f"  Added group mapper to '{client_id}'", flush=True)


def _ensure_audience_mapper(token, internal_id, client_id):
    mappers = get(f"{KC_URL}/admin/realms/{REALM}/clients/{internal_id}/protocol-mappers/models", token)
    if any(m.get("name") == "audience-mapper" for m in mappers):
        print(f"  Audience mapper already on '{client_id}'", flush=True)
        return
    status, _ = post(
        f"{KC_URL}/admin/realms/{REALM}/clients/{internal_id}/protocol-mappers/models",
        {
            "name": "audience-mapper",
            "protocol": "openid-connect",
            "protocolMapper": "oidc-audience-mapper",
            "consentRequired": False,
            "config": {
                "included.client.audience": client_id,
                "id.token.claim": "false",
                "access.token.claim": "true",
            },
        },
        token=token,
    )
    if status in (200, 201):
        print(f"  Added audience mapper to '{client_id}'", flush=True)


def _ensure_user_session_note_mapper(token, internal_id, name, note, claim):
    """Expose selected server-side workspace context in signed tokens."""
    mappers = get(f"{KC_URL}/admin/realms/{REALM}/clients/{internal_id}/protocol-mappers/models", token)
    if any(m.get("name") == name for m in mappers):
        return
    status, _ = post(
        f"{KC_URL}/admin/realms/{REALM}/clients/{internal_id}/protocol-mappers/models",
        {"name": name, "protocol": "openid-connect", "protocolMapper": "oidc-usersessionmodel-note-mapper",
         "consentRequired": False,
         "config": {"user.session.note": note, "claim.name": claim, "jsonType.label": "String",
                    "access.token.claim": "true", "id.token.claim": "true", "userinfo.token.claim": "true"}},
        token=token)
    if status in (200, 201):
        print(f"  Added session context mapper '{claim}'", flush=True)


def ensure_active_context_mappers(token, internal_id):
    # Native `organization` is retained for backward compatibility. These values
    # are authoritative after a silent organization/project switch in KC 26.
    _ensure_user_session_note_mapper(token, internal_id, "autom-active-organization-id",
                                     "autom.organization.id", "autom_organization_id")
    _ensure_user_session_note_mapper(token, internal_id, "autom-active-project-id",
                                     "autom.project.group.id", "project_id")
    _ensure_user_session_note_mapper(token, internal_id, "autom-active-project-name",
                                     "autom.project.name", "project_name")


def _grant_admin_roles_to_service_account(token, internal_id, client_id):
    """Grant realm-management view/manage roles to the backend service account."""
    # Get the service account user id
    sa_user = get(f"{KC_URL}/admin/realms/{REALM}/clients/{internal_id}/service-account-user", token)
    sa_id = sa_user.get("id")
    if not sa_id:
        print(f"  Warning: could not get service account for '{client_id}'", flush=True)
        return

    # Find realm-management client
    rm_clients = get(f"{KC_URL}/admin/realms/{REALM}/clients?clientId=realm-management", token)
    if not rm_clients:
        print("  Warning: realm-management client not found", flush=True)
        return
    rm_id = rm_clients[0]["id"]

    # Get the roles we need
    needed = ["view-users", "manage-users", "view-realm", "manage-realm",
              "view-clients", "manage-clients", "query-groups", "query-users"]
    rm_roles = get(f"{KC_URL}/admin/realms/{REALM}/clients/{rm_id}/roles", token)
    roles_to_assign = [r for r in rm_roles if r.get("name") in needed]

    if roles_to_assign:
        status, _ = post(
            f"{KC_URL}/admin/realms/{REALM}/users/{sa_id}/role-mappings/clients/{rm_id}",
            roles_to_assign,
            token=token,
        )
        if status in (200, 204):
            print(f"  Granted realm-management roles to '{client_id}' service account", flush=True)
        else:
            print(f"  Warning: grant service account roles returned {status}", flush=True)


def get_client_secret(token, client_id):
    clients = get(f"{KC_URL}/admin/realms/{REALM}/clients?clientId={client_id}", token)
    if not clients:
        return None
    internal_id = clients[0]["id"]
    secret_data = get(f"{KC_URL}/admin/realms/{REALM}/clients/{internal_id}/client-secret", token)
    return secret_data.get("value")


# ── Users ─────────────────────────────────────────────────────────────────────

def create_user(token, username, email, first, last, password):
    status, _ = post(
        f"{KC_URL}/admin/realms/{REALM}/users",
        {
            "username": username,
            "email": email,
            "firstName": first,
            "lastName": last,
            "enabled": True,
            "emailVerified": True,
            "credentials": [{"type": "password", "value": password, "temporary": False}],
        },
        token=token,
    )
    if status == 201:
        print(f"  Created user '{username}'", flush=True)
    elif status == 409:
        print(f"  User '{username}' already exists – skipping", flush=True)
    else:
        print(f"  Warning: user '{username}' returned {status}", flush=True)


def get_user_id(token, username):
    users = get(f"{KC_URL}/admin/realms/{REALM}/users?username={username}&exact=true", token)
    return users[0]["id"] if users else None


# ── Groups ────────────────────────────────────────────────────────────────────

def ensure_top_group(token, name):
    """Create a top-level group if it doesn't exist."""
    groups = get(f"{KC_URL}/admin/realms/{REALM}/groups?search={name}", token)
    for g in groups:
        if g.get("name") == name and g.get("path") == f"/{name}":
            return g["id"]
    status, _ = post(
        f"{KC_URL}/admin/realms/{REALM}/groups",
        {"name": name},
        token=token,
    )
    if status == 201:
        print(f"  Created group '/{name}'", flush=True)
    elif status == 409:
        print(f"  Group '/{name}' already exists", flush=True)
    else:
        print(f"  Warning: group '/{name}' returned {status}", flush=True)
    groups = get(f"{KC_URL}/admin/realms/{REALM}/groups?search={name}", token)
    for g in groups:
        if g.get("name") == name:
            return g["id"]
    return None


def get_all_groups(token):
    """Flat map  path → id  for every group + subgroup."""
    top = get(f"{KC_URL}/admin/realms/{REALM}/groups", token)
    mapping = {}

    def recurse(groups):
        for g in groups:
            mapping[g["path"]] = g["id"]
            children = get(f"{KC_URL}/admin/realms/{REALM}/groups/{g['id']}/children", token)
            if children:
                recurse(children)

    recurse(top)
    return mapping


def ensure_subgroup(token, parent_id, name, all_groups_ref, parent_path):
    full_path = f"{parent_path}/{name}"
    if full_path in all_groups_ref:
        return all_groups_ref[full_path]
    status, _ = post(
        f"{KC_URL}/admin/realms/{REALM}/groups/{parent_id}/children",
        {"name": name},
        token=token,
    )
    if status in (201, 204, 409):
        print(f"  Subgroup '{full_path}' ensured", flush=True)
    else:
        print(f"  Warning: subgroup '{full_path}' returned {status}", flush=True)
    fresh = get_all_groups(token)
    all_groups_ref.update(fresh)
    return all_groups_ref.get(full_path)


def assign_group(token, user_id, group_id):
    _req("PUT", f"{KC_URL}/admin/realms/{REALM}/users/{user_id}/groups/{group_id}", token=token)


# ── Keycloak Organizations ────────────────────────────────────────────────────

def create_kc_org(token, name, alias):
    """Create a Keycloak Organization (idempotent). Returns the KC org UUID.

    After creation the four system roles (owner, org-admin, project-admin,
    project-member) are provisioned on the org automatically so they appear
    in the JWT's `organization.<id>.roles` claim after a kc_org token exchange.
    """
    orgs = get(f"{KC_URL}/admin/realms/{REALM}/organizations?search={urllib.parse.quote(alias)}&max=10", token)
    for org in orgs:
        if org.get("alias") == alias:
            print(f"  KC org '{alias}' already exists (id={org['id']})", flush=True)
            ensure_org_roles(token, org["id"], alias)
            return org["id"]

    status, _ = post(
        f"{KC_URL}/admin/realms/{REALM}/organizations",
        {"name": name, "alias": alias, "enabled": True},
        token=token,
    )
    if status not in (201, 409):
        print(f"  Warning: KC org '{alias}' creation returned {status}", flush=True)
        return None

    orgs = get(f"{KC_URL}/admin/realms/{REALM}/organizations?search={urllib.parse.quote(alias)}&max=10", token)
    for org in orgs:
        if org.get("alias") == alias:
            print(f"  Created KC org '{alias}' (id={org['id']})", flush=True)
            ensure_org_roles(token, org["id"], alias)
            return org["id"]
    return None


def remove_kc_org_member(token, kc_org_id, user_id):
    """Remove a user from a Keycloak Organization — blocks kc_org token exchange for that org."""
    status, _ = delete(f"{KC_URL}/admin/realms/{REALM}/organizations/{kc_org_id}/members/{user_id}", token)
    if status in (200, 204):
        print(f"  Removed user {user_id} from KC org {kc_org_id}", flush=True)
    elif status == 404:
        print(f"  User {user_id} not in KC org {kc_org_id} (already removed)", flush=True)
    else:
        print(f"  Warning: remove member returned {status}", flush=True)


def purge_all_kc_orgs(token):
    """Delete every Keycloak Organization in the realm (clean-slate for fresh provisioning)."""
    orgs = get(f"{KC_URL}/admin/realms/{REALM}/organizations?max=500", token)
    if not isinstance(orgs, list):
        print("  No KC organizations to remove (feature not enabled or empty).", flush=True)
        return
    if not orgs:
        print("  No KC organizations to remove.", flush=True)
        return
    for org in orgs:
        if not isinstance(org, dict):
            continue
        oid = org.get("id", "")
        name = org.get("name", oid)
        status, _ = delete(f"{KC_URL}/admin/realms/{REALM}/organizations/{oid}", token)
        if status in (200, 204):
            print(f"  Deleted KC org '{name}'", flush=True)
        else:
            print(f"  Warning: delete KC org '{name}' returned {status}", flush=True)


def purge_all_groups(token):
    """Delete every top-level group (and its subtree) in the realm."""
    top = get(f"{KC_URL}/admin/realms/{REALM}/groups", token)
    if not isinstance(top, list):
        print("  No groups to remove.", flush=True)
        return
    if not top:
        print("  No groups to remove.", flush=True)
        return
    for g in top:
        if not isinstance(g, dict):
            continue
        gid = g.get("id", "")
        name = g.get("name", gid)
        status, _ = delete(f"{KC_URL}/admin/realms/{REALM}/groups/{gid}", token)
        if status in (200, 204):
            print(f"  Deleted group '/{name}'", flush=True)
        else:
            print(f"  Warning: delete group '/{name}' returned {status}", flush=True)


def enable_organizations(token):
    """Enable Keycloak 26.x native Organizations on the realm."""
    status, _ = put_body(
        f"{KC_URL}/admin/realms/{REALM}",
        {"organizationsEnabled": True},
        token=token,
    )
    if status in (200, 204):
        print("  Organizations feature enabled on realm", flush=True)
    else:
        print(f"  Warning: enabling Organizations returned {status}", flush=True)


def legacy_ensure_autom_org_browser_flow(token):
    """Build (or rebuild) the credentials-first org-aware browser flow for autom-app.

    Structure — org selection is INSIDE autom-org-forms so it always runs after
    credentials regardless of KC's ALTERNATIVE sibling processing order:

        autom-org-browser
        ├── Cookie [ALTERNATIVE]
        ├── Identity Provider Redirector [ALTERNATIVE]
        └── autom-org-forms [ALTERNATIVE]
            ├── Username Password Form [REQUIRED]       ← page 1: username + password
            └── autom-org-cond [CONDITIONAL]
                ├── Condition - user configured [REQUIRED]
                │   Returns TRUE only when the authenticated user is a member of
                │   at least one KC Organization → sub-flow skipped for non-org users.
                └── Organization Identity-First Login [REQUIRED]
                    Called AFTER the user is already authenticated.
                    • 1 org  → auto-selected silently; no additional UI shown.
                    • 2+ orgs → KC shows its own org-picker page (no React involved).

    Non-org users: autom-org-cond is SKIPPED (condition false) → flow completes,
                   token issued without organization claim.
    Org users:     org context is embedded in session → token carries the
                   'organization' claim → React reads it on first render.

    If the flow already exists it is deleted and rebuilt so the structure stays
    current across script re-runs.
    """
    # Versioned because Keycloak does not permit deleting an existing custom
    # browser flow through every Admin API deployment.  Keeping the old flow
    # lets a live realm move safely to the corrected sequential flow.
    FLOW_ALIAS  = "autom-org-browser-v2"
    FORMS_ALIAS = "autom-org-forms"
    COND_ALIAS  = "autom-org-cond"

    existing_id = _get_flow_id_by_alias(token, FLOW_ALIAS)
    if existing_id:
        # Reset realm default first so KC allows deletion of the active flow.
        put_body(f"{KC_URL}/admin/realms/{REALM}", {"browserFlow": "browser"}, token=token)
        status, _ = delete(
            f"{KC_URL}/admin/realms/{REALM}/authentication/flows/{existing_id}",
            token=token,
        )
        if status in (200, 204):
            print(f"  Deleted existing '{FLOW_ALIAS}' for rebuild", flush=True)
        else:
            print(f"  Warning: delete '{FLOW_ALIAS}' returned {status} — keeping existing flow",
                  flush=True)
            return existing_id

    status, _ = post(
        f"{KC_URL}/admin/realms/{REALM}/authentication/flows",
        {
            "alias":       FLOW_ALIAS,
            "providerId":  "basic-flow",
            "description": "Credentials-first with KC-native org selection inside forms sub-flow",
            "topLevel":    True,
            "builtIn":     False,
        },
        token=token,
    )
    if status not in (201, 204):
        print(f"  Warning: creating '{FLOW_ALIAS}' returned {status}", flush=True)
        return None

    def latest_exec(provider_id):
        execs = _get_flow_executions(token, FLOW_ALIAS)
        return next((e for e in reversed(execs) if e.get("providerId") == provider_id), None)

    def latest_subflow(alias):
        execs = _get_flow_executions(token, FLOW_ALIAS)
        return next(
            (e for e in reversed(execs)
             if e.get("displayName") == alias or e.get("flowAlias") == alias),
            None,
        )

    # ── Top level ──────────────────────────────────────────────────────────────
    # Cookie [ALTERNATIVE]
    _add_execution_to_flow(token, FLOW_ALIAS, "auth-cookie")
    exc = latest_exec("auth-cookie")
    if exc:
        _update_execution_in_flow(token, FLOW_ALIAS, exc, "ALTERNATIVE")

    # Identity Provider Redirector [ALTERNATIVE]
    _add_execution_to_flow(token, FLOW_ALIAS, "identity-provider-redirector")
    exc = latest_exec("identity-provider-redirector")
    if exc:
        _update_execution_in_flow(token, FLOW_ALIAS, exc, "ALTERNATIVE")

    # autom-org-forms [ALTERNATIVE] — credentials + org selection in one sub-flow
    _add_sub_flow(token, FLOW_ALIAS, FORMS_ALIAS, "Credentials and KC org selection")
    exc = latest_subflow(FORMS_ALIAS)
    if exc:
        _update_execution_in_flow(token, FLOW_ALIAS, exc, "ALTERNATIVE")

    # ── Inside autom-org-forms ─────────────────────────────────────────────────
    # Username Password Form [REQUIRED] — shows username+password fields together
    _add_execution_to_flow(token, FORMS_ALIAS, "auth-username-password-form")
    exc = latest_exec("auth-username-password-form")
    if exc:
        _update_execution_in_flow(token, FORMS_ALIAS, exc, "REQUIRED")

    # autom-org-cond [CONDITIONAL] — only activates when user is a KC org member
    _add_sub_flow(token, FORMS_ALIAS, COND_ALIAS, "Org selection — runs only for KC org members")
    exc = latest_subflow(COND_ALIAS)
    if exc:
        _update_execution_in_flow(token, FORMS_ALIAS, exc, "CONDITIONAL")

    # ── Inside autom-org-cond ──────────────────────────────────────────────────
    # Condition - user configured [REQUIRED] — TRUE when user is in >= 1 KC Organization
    _add_execution_to_flow(token, COND_ALIAS, "conditional-user-configured")
    exc = latest_exec("conditional-user-configured")
    if exc:
        _update_execution_in_flow(token, COND_ALIAS, exc, "REQUIRED")

    # Organization Identity-First Login [REQUIRED] — called post-credentials:
    #   authenticated user, 1 org → auto-select silently
    #   authenticated user, 2+ orgs → KC shows org-picker page
    _add_execution_to_flow(token, COND_ALIAS, "organization")
    exc = latest_exec("organization")
    if exc:
        _update_execution_in_flow(token, COND_ALIAS, exc, "REQUIRED")

    print(f"  Built org-aware credentials-first flow '{FLOW_ALIAS}'", flush=True)
    return _get_flow_id_by_alias(token, FLOW_ALIAS)


def ensure_autom_org_browser_flow(token):
    """Create the credentials-first flow backed by the custom KC provider.

    The built-in ``organization`` authenticator is identity-first. This provider
    runs after Username Password Form, verifies native KC membership, and saves
    the selected organization UUID for the built-in organization token mapper.
    """
    flow_alias = "autom-post-password-org-project-browser-v2"
    forms_alias = "autom-post-password-org-project-forms-v2"
    otp_alias = "autom-post-password-conditional-otp-v2"
    if _get_flow_id_by_alias(token, flow_alias):
        return _get_flow_id_by_alias(token, flow_alias)

    status, _ = post(
        f"{KC_URL}/admin/realms/{REALM}/authentication/flows",
        {"alias": flow_alias, "providerId": "basic-flow", "topLevel": True,
         "builtIn": False, "description": "Autom credentials-first organization selection"},
        token=token,
    )
    if status not in (201, 204):
        print(f"  Warning: creating '{flow_alias}' returned {status}", flush=True)
        return None

    def execution(flow, provider):
        return next((item for item in reversed(_get_flow_executions(token, flow))
                     if item.get("providerId") == provider), None)

    _add_execution_to_flow(token, flow_alias, "auth-cookie")
    item = execution(flow_alias, "auth-cookie")
    if item:
        _update_execution_in_flow(token, flow_alias, item, "ALTERNATIVE")
    _add_execution_to_flow(token, flow_alias, "identity-provider-redirector")
    item = execution(flow_alias, "identity-provider-redirector")
    if item:
        _update_execution_in_flow(token, flow_alias, item, "ALTERNATIVE")

    _add_sub_flow(token, flow_alias, forms_alias, "Credentials then organization selection")
    forms_execution = next((item for item in reversed(_get_flow_executions(token, flow_alias))
                            if item.get("displayName") == forms_alias or item.get("flowAlias") == forms_alias), None)
    if not forms_execution:
        print("  Could not create credentials sub-flow; browser flow unchanged", flush=True)
        return None
    _update_execution_in_flow(token, flow_alias, forms_execution, "ALTERNATIVE")

    _add_execution_to_flow(token, forms_alias, "auth-username-password-form")
    item = execution(forms_alias, "auth-username-password-form")
    if not item:
        print("  Could not add Username Password Form; browser flow unchanged", flush=True)
        return None
    _update_execution_in_flow(token, forms_alias, item, "REQUIRED")

    # MFA runs immediately after password and before organization/project context.
    _add_sub_flow(token, forms_alias, otp_alias, "MFA when configured")
    otp_execution = next((item for item in reversed(_get_flow_executions(token, forms_alias))
                          if item.get("displayName") == otp_alias or item.get("flowAlias") == otp_alias), None)
    if otp_execution:
        _update_execution_in_flow(token, forms_alias, otp_execution, "CONDITIONAL")
        _add_execution_to_flow(token, otp_alias, "conditional-user-configured")
        item = execution(otp_alias, "conditional-user-configured")
        if item:
            _update_execution_in_flow(token, otp_alias, item, "REQUIRED")
        _add_execution_to_flow(token, otp_alias, "auth-otp-form")
        item = execution(otp_alias, "auth-otp-form")
        if item:
            _update_execution_in_flow(token, otp_alias, item, "REQUIRED")

    provider_status = _add_execution_to_flow(token, forms_alias, "autom-post-password-org-selector")
    if provider_status not in (201, 204):
        print("  Post-password org selector provider is not installed; browser flow unchanged", flush=True)
        return None
    item = execution(forms_alias, "autom-post-password-org-selector")
    if not item:
        print("  Post-password org selector execution was not created; browser flow unchanged", flush=True)
        return None
    _update_execution_in_flow(token, forms_alias, item, "REQUIRED")
    provider_status = _add_execution_to_flow(token, forms_alias, "autom-post-org-project-selector")
    if provider_status not in (201, 204):
        print("  Post-org project selector provider is not installed; browser flow unchanged", flush=True)
        return None
    item = execution(forms_alias, "autom-post-org-project-selector")
    if not item:
        print("  Could not add project selector; browser flow unchanged", flush=True)
        return None
    _update_execution_in_flow(token, forms_alias, item, "REQUIRED")
    print(f"  Built post-password MFA → organization → project flow '{flow_alias}'", flush=True)
    return _get_flow_id_by_alias(token, flow_alias)


def ensure_org_browser_flow_as_default(token):
    """Create the versioned org browser flow and set it as the realm default."""
    flow_id = ensure_autom_org_browser_flow(token)
    if not flow_id:
        print("  Warning: could not create the organization browser flow — realm default unchanged",
              flush=True)
        return
    status, _ = put_body(
        f"{KC_URL}/admin/realms/{REALM}",
        {"browserFlow": "autom-post-password-org-project-browser-v2"},
        token=token,
    )
    if status in (200, 204):
        print("  Realm default browser flow set to 'autom-post-password-org-project-browser-v2'", flush=True)
    else:
        print(f"  Warning: setting realm browserFlow returned {status}", flush=True)


# ── Organization-level system roles ───────────────────────────────────────────

# These four roles are attached to every Keycloak Organization.
# They appear in the JWT's `organization.<orgId>.roles` array in the org-scoped
# token issued after KC's org-aware browser flow and are flattened to
# ClaimTypes.Role by the .NET claims transformer.  Access logic (what each role
# CAN do) is enforced entirely in application code — never via the permission store.
ORG_SYSTEM_ROLES = [
    {"name": "owner",          "description": "Organisation owner — full control over the organisation"},
    {"name": "org-admin",      "description": "Organisation administrator — manages members and projects"},
    {"name": "project-admin",  "description": "Project administrator — manages one project"},
    {"name": "project-member", "description": "Project member — read/write access within a project"},
]


def ensure_org_roles(token, kc_org_id, org_alias):
    """Create the four system roles on a Keycloak Organization (idempotent)."""
    existing_raw = get(f"{KC_URL}/admin/realms/{REALM}/organizations/{kc_org_id}/roles", token)
    existing = {r.get("name") for r in (existing_raw if isinstance(existing_raw, list) else [])}

    for role in ORG_SYSTEM_ROLES:
        if role["name"] in existing:
            continue
        status, _ = post(
            f"{KC_URL}/admin/realms/{REALM}/organizations/{kc_org_id}/roles",
            role,
            token=token,
        )
        if status in (201, 204):
            print(f"  Created org role '{role['name']}' on '{org_alias}'", flush=True)
        elif status == 409:
            pass  # already exists — fine
        else:
            print(f"  Warning: org role '{role['name']}' on '{org_alias}' returned {status}", flush=True)


def add_org_scope_to_client(token, internal_client_id, client_id):
    """Add the built-in 'organization' client scope to a client as a default scope.

    The 'organization' scope is created automatically by Keycloak when Organizations
    are enabled; it injects the `organization` claim into access tokens.
    """
    # Find the built-in scope named 'organization'
    scopes = get(f"{KC_URL}/admin/realms/{REALM}/client-scopes", token)
    org_scope = next((s for s in scopes if s.get("name") == "organization"), None)
    if not org_scope:
        print(f"  Warning: 'organization' client scope not found — run after enabling Organizations", flush=True)
        return

    scope_id = org_scope["id"]

    # Check if already a default scope on this client
    existing = get(f"{KC_URL}/admin/realms/{REALM}/clients/{internal_client_id}/default-client-scopes", token)
    if any(s.get("id") == scope_id for s in existing):
        print(f"  'organization' scope already on '{client_id}' defaults", flush=True)
        return

    status, _ = _req(
        "PUT",
        f"{KC_URL}/admin/realms/{REALM}/clients/{internal_client_id}/default-client-scopes/{scope_id}",
        token=token,
    )
    if status in (200, 204):
        print(f"  Added 'organization' scope to '{client_id}' defaults", flush=True)
    else:
        print(f"  Warning: adding 'organization' scope to '{client_id}' returned {status}", flush=True)


def configure_organization_claim_mapper(token):
    """Include KC organization UUIDs in the built-in organization claim.

    The API resolves an org from this signed UUID, never from a browser header
    or an alias supplied by the client. Keycloak otherwise maps aliases only.
    """
    scopes = get(f"{KC_URL}/admin/realms/{REALM}/client-scopes", token)
    scope = next((item for item in scopes if item.get("name") == "organization"), None)
    if not scope:
        print("  Warning: organization client scope missing", flush=True)
        return

    mappers = get(
        f"{KC_URL}/admin/realms/{REALM}/client-scopes/{scope['id']}/protocol-mappers/models",
        token,
    )
    mapper = next((item for item in mappers
                   if item.get("protocolMapper") == "oidc-organization-membership-mapper"), None)
    if not mapper:
        print("  Warning: organization membership mapper missing", flush=True)
        return

    config = mapper.setdefault("config", {})
    if config.get("addOrganizationId") == "true":
        print("  Organization token mapper already includes IDs", flush=True)
        return
    config["addOrganizationId"] = "true"
    status, _ = put_body(
        f"{KC_URL}/admin/realms/{REALM}/client-scopes/{scope['id']}/protocol-mappers/models/{mapper['id']}",
        mapper,
        token=token,
    )
    if status in (200, 204):
        print("  Organization token mapper configured to include IDs", flush=True)
    else:
        print(f"  Warning: organization mapper update returned {status}", flush=True)


# ── Security settings ─────────────────────────────────────────────────────────

def configure_realm_security(token):
    payload = {
        "bruteForceProtected": True,
        "permanentLockout": False,
        "maxFailureWaitSeconds": 900,
        "minimumQuickLoginWaitSeconds": 60,
        "waitIncrementSeconds": 60,
        "quickLoginCheckMilliSeconds": 1000,
        "maxDeltaTimeSeconds": 43200,
        "failureFactor": 5,
        "passwordPolicy": "length(12) and upperCase(1) and lowerCase(1) and digits(1) and notUsername() and passwordHistory(3)",
        "accessTokenLifespan": 300,
        "ssoSessionIdleTimeout": 1800,
        "ssoSessionMaxLifespan": 28800,
        "refreshTokenMaxReuse": 0,
        "resetPasswordAllowed": False,
    }
    status, _ = put_body(f"{KC_URL}/admin/realms/{REALM}", payload, token=token)
    if status in (200, 204):
        print("  Realm security configured (brute-force, password policy, session timeouts)", flush=True)
    else:
        print(f"  Warning: realm security update returned {status}", flush=True)


def enable_required_action(token, alias, label, default=False):
    actions = get(f"{KC_URL}/admin/realms/{REALM}/authentication/required-actions", token)
    for action in actions:
        if action.get("alias") == alias:
            changed = False
            if not action.get("enabled"):
                action["enabled"] = True
                changed = True
            if default != action.get("defaultAction", False):
                action["defaultAction"] = default
                changed = True
            if changed:
                put_body(
                    f"{KC_URL}/admin/realms/{REALM}/authentication/required-actions/{urllib.parse.quote(alias, safe='')}",
                    action,
                    token=token,
                )
                print(f"  Required action configured: {label} (default={default})", flush=True)
            else:
                print(f"  Required action already set: {label}", flush=True)
            return
    print(f"  Required action not found: {alias}", flush=True)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    wait_for_keycloak()

    print("\nAcquiring master admin token …", flush=True)
    token = get_token()
    if not token:
        raise RuntimeError("Could not obtain admin token — check KEYCLOAK_ADMIN / KEYCLOAK_ADMIN_PASSWORD.")

    # ── Realm ──────────────────────────────────────────────────────────────
    print(f"\nEnsuring realm '{REALM}' …", flush=True)
    ensure_realm(token)

    # Re-acquire token after realm creation (same master token is fine)

    # ── Roles ──────────────────────────────────────────────────────────────
    print("\nEnsuring realm roles …", flush=True)
    ensure_realm_role(token, "super-admin", "System-wide super administrator")
    ensure_realm_role(token, "user",        "Regular project member")

    # ── Organizations ──────────────────────────────────────────────────────
    print("\nEnabling Keycloak Organizations …", flush=True)
    enable_organizations(token)

    # The custom provider preserves the normal credentials page and then shows
    # a server-side, Keycloak-hosted organization picker for multi-org users.
    print("\nSetting post-password organization browser flow as realm default …", flush=True)
    ensure_org_browser_flow_as_default(token)

    # ── Clients ────────────────────────────────────────────────────────────
    print("\nEnsuring clients …", flush=True)
    app_internal_id = ensure_public_client(token, "autom-app",        "Autom Business App", APP_ORIGINS)
    # Return value unused: browser-flow override is applied inside ensure_public_client.
    ensure_public_client(token, "autom-superadmin", "Autom Super-Admin", SUPERADMIN_ORIGINS)
    ensure_confidential_client(token, "autom-backend", "Autom Backend Service")

    # Wire the 'organization' scope to autom-app ONLY.
    # autom-superadmin is intentionally excluded — super-admin users are never
    # KC org members, so the organization claim is meaningless there and its
    # presence would expose org context to a portal that must stay org-agnostic.
    print("\nWiring 'organization' scope to autom-app …", flush=True)
    if app_internal_id:
        add_org_scope_to_client(token, app_internal_id, "autom-app")
        ensure_active_context_mappers(token, app_internal_id)
    configure_organization_claim_mapper(token)

    backend_secret = get_client_secret(token, "autom-backend")

    # Orgs, groups, and projects are managed via the Keycloak admin console or
    # the super-admin API — NOT by this script.  The script owns the framework
    # (realm, clients, roles, security policy) only.
    # purge_all_kc_orgs / purge_all_groups are helper functions kept for
    # emergency use — never call them from main().
    kc_org_ids: dict = {}

    # ── Security hardening ──────────────────────────────────────────────────
    print("\nApplying realm security …", flush=True)
    configure_realm_security(token)

    print("\nEnabling required actions …", flush=True)
    enable_required_action(token, "CONFIGURE_TOTP", "Configure OTP", default=False)

    kc_org_summary = "\n".join(
        f"   {name:20s}  {oid}" for name, oid in kc_org_ids.items()
    ) or "   (none created)"

    print(f"""
------------------------------------------------------------------------
 autom-realm is ready!

 Realm            : {REALM}
 Keycloak console : {KC_URL}/admin/master/console/#/autom-realm

 Auth flow model
   autom-app        — autom-post-password-org-browser-v1 (username+password first, then KC
                      org picker if user is in multiple orgs, token with org)
   autom-superadmin — 'Browser - SuperAdmin only' override (username+password
                      + role gate; no org step; super-admins are never org members)

 Portals are audience-isolated: autom-app tokens carry aud=autom-app,
 autom-superadmin tokens carry aud=autom-superadmin.  The .NET backend
 validates aud=autom-app, so superadmin tokens are rejected at the API
 layer.  Super-admins who hit the business portal are rejected at boot by
 main.tsx before any UI renders.

 System roles (owner, org-admin, project-admin, project-member)
   Created automatically on each KC org via ensure_org_roles().
   They appear in organization.<orgId>.roles in org-scoped JWTs.
   Access logic is enforced in application code — NEVER via the
   permission store.  Do not add them to PermissionDefaults.Matrix.

 Clients
   autom-app        — public SPA (React business app)      port 5173
   autom-superadmin — public SPA (React super-admin)       port 5174
   autom-backend    — confidential service account (.NET)
     client secret  : {backend_secret or '(could not retrieve — check Keycloak console)'}

 Add the autom-backend client secret to your .NET appsettings:
   "Keycloak": {{
     "ClientSecret": "{backend_secret or '<paste-secret-from-console>'}"
   }}

 Keycloak Organization IDs — copy these into each Organization document's
 KcOrgId field in MongoDB so the backend can resolve org from JWT:
{kc_org_summary}

 To block a user from an org, remove them from the KC Organization:
   DELETE /admin/realms/{REALM}/organizations/{{kcOrgId}}/members/{{userId}}
   (or call keycloakAdmin.RemoveKcOrgMemberAsync from the backend)
------------------------------------------------------------------------
""", flush=True)


if __name__ == "__main__":
    main()
