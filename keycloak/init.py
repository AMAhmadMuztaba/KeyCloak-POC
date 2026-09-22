"""
Keycloak Autom initializer.

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

KC_URL            = os.environ.get("KC_URL",                    "http://keycloak:8080")
REALM             = os.environ.get("KC_REALM",                  "autom-realm")
CLIENT_ID         = os.environ.get("KC_CLIENT_ID",              "autom-app")
ADMIN             = os.environ.get("KEYCLOAK_ADMIN",            "admin")
ADMIN_PW          = os.environ.get("KEYCLOAK_ADMIN_PASSWORD",   "")
GOOGLE_CLIENT_ID  = os.environ.get("GOOGLE_CLIENT_ID",          "")
GOOGLE_SECRET     = os.environ.get("GOOGLE_CLIENT_SECRET",      "")
MS_CLIENT_ID      = os.environ.get("MICROSOFT_CLIENT_ID",       "")
MS_SECRET         = os.environ.get("MICROSOFT_CLIENT_SECRET",   "")


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


def put_body(url, payload, token=None):
    return _req("PUT", url, data=payload, token=token)


def delete(url, token=None):
    return _req("DELETE", url, token=token)


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


def force_required_action(token, user_id, username, action_alias):
    """Add a required action to a user if not already present."""
    user = get(f"{KC_URL}/admin/realms/{REALM}/users/{user_id}", token)
    existing = user.get("requiredActions", [])
    if action_alias in existing:
        print(f"  {username}: {action_alias} already pending", flush=True)
        return
    status, _ = put_body(
        f"{KC_URL}/admin/realms/{REALM}/users/{user_id}",
        {**user, "requiredActions": existing + [action_alias]},
        token=token,
    )
    if status in (200, 204):
        print(f"  {username}: assigned required action {action_alias}", flush=True)
    else:
        print(f"  {username}: warning – assign {action_alias} returned {status}", flush=True)


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


# ── Native Organization helpers ─────────────────────────────────────────────

def enable_organizations(token):
    """Enable the Keycloak Organizations feature for this realm."""
    realm = get(f"{KC_URL}/admin/realms/{REALM}", token)
    status, _ = put_body(
        f"{KC_URL}/admin/realms/{REALM}",
        {**realm, "organizationsEnabled": True},
        token=token,
    )
    if status not in (200, 204):
        raise RuntimeError(f"Could not enable Keycloak Organizations (HTTP {status}).")


def list_organizations(token):
    return get(f"{KC_URL}/admin/realms/{REALM}/organizations?max=500", token)


def ensure_organization(token, name, alias):
    existing = next((org for org in list_organizations(token)
                     if org.get("alias") == alias or org.get("name") == name), None)
    if existing:
        print(f"  Organization '{alias}' already exists", flush=True)
        return existing["id"]

    status, _ = post(
        f"{KC_URL}/admin/realms/{REALM}/organizations",
        {"name": name, "alias": alias, "enabled": True},
        token=token,
    )
    if status not in (201, 204):
        raise RuntimeError(f"Could not create Keycloak Organization '{alias}' (HTTP {status}).")
    created = next((org for org in list_organizations(token) if org.get("alias") == alias), None)
    if not created:
        raise RuntimeError(f"Created Keycloak Organization '{alias}' could not be read back.")
    print(f"  Created Keycloak Organization '{alias}'", flush=True)
    return created["id"]


def add_organization_scope_to_client(token, client_id):
    clients = get(f"{KC_URL}/admin/realms/{REALM}/clients?clientId={urllib.parse.quote(client_id)}", token)
    client = next((item for item in clients if item.get("clientId") == client_id), None)
    if not client:
        print(f"  Warning: client '{client_id}' was not found; org scope was not assigned", flush=True)
        return
    scopes = get(f"{KC_URL}/admin/realms/{REALM}/client-scopes", token)
    scope = next((item for item in scopes if item.get("name") == "organization"), None)
    if not scope:
        raise RuntimeError("The built-in 'organization' client scope is missing.")
    status, _ = put(
        f"{KC_URL}/admin/realms/{REALM}/clients/{client['id']}/default-client-scopes/{scope['id']}",
        token=token,
    )
    if status not in (204, 409):
        raise RuntimeError(f"Could not attach organization scope to '{client_id}' (HTTP {status}).")


# ── Identity Provider helpers ─────────────────────────────────────────────────

def ensure_idp(token, alias, display_name, provider_id, config):
    status, _ = _req("GET", f"{KC_URL}/admin/realms/{REALM}/identity-provider/instances/{alias}", token=token)
    if status == 200:
        print(f"  IdP '{alias}' already exists", flush=True)
        return
    payload = {
        "alias": alias,
        "displayName": display_name,
        "providerId": provider_id,
        "enabled": True,
        "trustEmail": True,
        "storeToken": False,
        "addReadTokenRoleOnCreate": False,
        "authenticateByDefault": False,
        "linkOnly": False,
        "firstBrokerLoginFlowAlias": "first broker login",
        "config": config,
    }
    status, _ = post(f"{KC_URL}/admin/realms/{REALM}/identity-provider/instances", payload, token=token)
    if status == 201:
        print(f"  Created IdP '{alias}' ({display_name})", flush=True)
    elif status == 409:
        print(f"  IdP '{alias}' already exists", flush=True)
    else:
        print(f"  Warning: IdP '{alias}' create returned {status}", flush=True)


# ── WebAuthn policy helpers ───────────────────────────────────────────────────

def configure_webauthn_policy(token):
    """Set rpId, authenticatorAttachment, requireResidentKey, userVerification."""
    payload = {
        # Security Key (2FA – cross-platform hardware key)
        "webAuthnPolicyRpEntityName":                   "keycloak",
        "webAuthnPolicyRpId":                           "localhost",
        "webAuthnPolicySignatureAlgorithms":            ["ES256"],
        "webAuthnPolicyAttestationConveyancePreference":"none",
        "webAuthnPolicyAuthenticatorAttachment":        "cross-platform",
        "webAuthnPolicyRequireResidentKey":             "No",
        "webAuthnPolicyUserVerificationRequirement":    "preferred",
        "webAuthnPolicyCreateTimeout":                  0,
        "webAuthnPolicyAvoidSameAuthenticatorRegister": False,
        # Passkey (passwordless – platform biometrics)
        "webAuthnPolicyPasswordlessRpEntityName":                   "keycloak",
        "webAuthnPolicyPasswordlessRpId":                           "localhost",
        "webAuthnPolicyPasswordlessSignatureAlgorithms":            ["ES256"],
        "webAuthnPolicyPasswordlessAttestationConveyancePreference":"none",
        "webAuthnPolicyPasswordlessAuthenticatorAttachment":        "platform",
        "webAuthnPolicyPasswordlessRequireResidentKey":             "Yes",
        "webAuthnPolicyPasswordlessUserVerificationRequirement":    "required",
        "webAuthnPolicyPasswordlessCreateTimeout":                  0,
        "webAuthnPolicyPasswordlessAvoidSameAuthenticatorRegister": False,
    }
    status, _ = put_body(f"{KC_URL}/admin/realms/{REALM}", payload, token=token)
    if status in (200, 204):
        print("  WebAuthn policies configured (rpId=localhost, passkeys=platform+resident)", flush=True)
    else:
        print(f"  Warning: WebAuthn policy update returned {status}", flush=True)


# ── WebAuthn browser-flow helpers ─────────────────────────────────────────────

def _get_token_header(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _raise_priority(exec_id, token):
    _req("POST", f"{KC_URL}/admin/realms/{REALM}/authentication/executions/{exec_id}/raise-priority", token=token)


def _lower_priority(exec_id, token):
    _req("POST", f"{KC_URL}/admin/realms/{REALM}/authentication/executions/{exec_id}/lower-priority", token=token)


def setup_webauthn_browser_flow(token):
    """
    Create a 'webauthn-browser' flow (copy of the organization-aware browser
    flow when available) that adds:
      • WebAuthn Passwordless Authenticator (ALTERNATIVE) – for passkey login
      • WebAuthn Authenticator (ALTERNATIVE) inside forms subflow – for security-key 2FA
    The flow is NOT bound to the realm; assign it per-client for passkey-enabled clients.
    """
    FLOW_ALIAS = "webauthn-browser"

    # 1 – Preserve Keycloak's organization identity-first execution. Copying
    # the old `browser` flow would silently move org selection back to the SPA.
    flows = get(f"{KC_URL}/admin/realms/{REALM}/authentication/flows", token)
    source_flow = "organization" if any(f.get("alias") == "organization" for f in flows) else "browser"
    if not any(f.get("alias") == FLOW_ALIAS for f in flows):
        status, _ = post(
            f"{KC_URL}/admin/realms/{REALM}/authentication/flows/{urllib.parse.quote(source_flow, safe='')}/copy",
            {"newName": FLOW_ALIAS},
            token=token,
        )
        if status in (200, 201):
            print(f"  Copied '{source_flow}' → '{FLOW_ALIAS}'", flush=True)
        else:
            print(f"  Warning: copy {source_flow} flow returned {status}", flush=True)
            return
    else:
        print(f"  Flow '{FLOW_ALIAS}' already exists", flush=True)

    encoded_alias = urllib.parse.quote(FLOW_ALIAS, safe="")
    execs_url = f"{KC_URL}/admin/realms/{REALM}/authentication/flows/{encoded_alias}/executions"

    # 2 – add WebAuthn Passwordless at top level if missing
    execs = get(execs_url, token)
    has_pl = any(e.get("providerId") == "webauthn-authenticator-passwordless" for e in execs)
    if not has_pl:
        status, _ = post(
            f"{execs_url}/execution",
            {"provider": "webauthn-authenticator-passwordless"},
            token=token,
        )
        if status in (200, 201):
            print("  Added WebAuthn Passwordless Authenticator", flush=True)
        else:
            print(f"  Warning: add WebAuthn Passwordless returned {status}", flush=True)

    # 3 – set it to ALTERNATIVE and raise priority to appear before forms
    execs = get(execs_url, token)
    for e in execs:
        if e.get("providerId") == "webauthn-authenticator-passwordless":
            if e.get("requirement") != "ALTERNATIVE":
                e["requirement"] = "ALTERNATIVE"
                put_body(execs_url, e, token=token)
                print("  Set WebAuthn Passwordless → ALTERNATIVE", flush=True)
            # raise priority until it's above the 'forms' subflow
            # (raise it len(execs) times to ensure it floats up)
            for _ in range(len(execs)):
                _raise_priority(e["id"], token)
            # restore: lower past cookie/kerberos/idp – we only need it before forms
            # re-fetch and check level-0 order
            break

    # 4 – inside the forms subflow, add WebAuthn Authenticator for 2FA
    execs = get(execs_url, token)
    forms_flow_id = None
    for e in execs:
        if e.get("displayName") == "forms" and e.get("level") == 0:
            forms_flow_id = e.get("flowId")
            break

    # 4 – add WebAuthn Authenticator inside the forms subflow for security-key 2FA
    # The copied forms subflow alias is its displayName (e.g. "webauthn-browser forms")
    execs = get(execs_url, token)
    forms_display_name = None
    for e in execs:
        if "forms" in (e.get("displayName") or "").lower() and e.get("level") == 0:
            forms_display_name = e.get("displayName")
            break

    if forms_display_name:
        has_wa = any(
            e.get("providerId") == "webauthn-authenticator"
            for e in execs
            if e.get("level") == 1
        )
        if not has_wa:
            forms_alias = urllib.parse.quote(forms_display_name, safe="")
            status, _ = post(
                f"{KC_URL}/admin/realms/{REALM}/authentication/flows/{forms_alias}/executions/execution",
                {"provider": "webauthn-authenticator"},
                token=token,
            )
            if status in (200, 201):
                print("  Added WebAuthn Authenticator inside forms (2FA)", flush=True)
            else:
                print(f"  Warning: add WebAuthn Authenticator inside forms returned {status}", flush=True)
        else:
            print("  WebAuthn Authenticator already in forms subflow", flush=True)

        execs = get(execs_url, token)
        for e in execs:
            if e.get("providerId") == "webauthn-authenticator" and e.get("level") == 1:
                if e.get("requirement") != "ALTERNATIVE":
                    e["requirement"] = "ALTERNATIVE"
                    put_body(execs_url, e, token=token)
                    print("  Set WebAuthn Authenticator (forms) → ALTERNATIVE", flush=True)
                else:
                    print("  WebAuthn Authenticator (forms) already ALTERNATIVE", flush=True)
                break
    else:
        print("  Warning: could not find 'forms' subflow to add WebAuthn 2FA", flush=True)

    # The webauthn-browser flow is NOT bound to the realm. It exists for optional
    # per-client assignment (clients that support passkeys). The realm default
    # stays as autom-post-password-org-browser-v1 (set by setup_autom_browser_flow).
    print(f"  Flow '{FLOW_ALIAS}' configured (not bound to realm — use per-client override if needed)", flush=True)


# ── Autom custom browser flow ────────────────────────────────────────────────

AUTOM_FLOW_ALIAS = "autom-post-password-org-browser-v1"
POST_AUTH_SUBFLOW_ALIAS = "autom-post-auth-selectors"


def setup_autom_browser_flow(token):
    """
    Creates the Autom browser flow with:
    - Organization Identity-First subflow DISABLED (our plugin handles org/project selection)
    - CONDITIONAL post-auth subflow INSIDE forms (same level as 2FA — KC-safe pattern)

      [ALT]  auth-cookie                          level 0
      [ALT]  identity-provider-redirector          level 0
      [DIS]  Organization subflow                  level 0  disabled — plugin replaces it
      [ALT]  forms subflow                         level 0
               [REQ] Username Password Form         level 1  (email + password together)
               [COND] autom-post-auth-selectors     level 1
                       [REQ] autom-condition-always       level 2
                       [REQ] autom-post-password-org-selector level 2
                       [REQ] autom-post-org-project-selector  level 2
                       [REQ] autom-mfa-enforcement         level 2
               [COND] 2FA conditional               level 1  (from browser copy)

    KC 26 rule: CONDITIONAL at TOP level alongside ALTERNATIVE triggers the conflict.
    CONDITIONAL inside a subflow (level 1+) is safe.

    Cookie auth: forms skipped -> CONDITIONAL selectors never run.
    Fresh auth:  email+password on ONE page -> CONDITIONAL selectors -> optional 2FA.

    Idempotent: deletes and recreates the flow on every run.
    """
    flows = get(f"{KC_URL}/admin/realms/{REALM}/authentication/flows", token)

    # Delete existing flow for a clean rebuild.
    existing = next((f for f in flows if f.get("alias") == AUTOM_FLOW_ALIAS), None)
    if existing:
        realm_data = get(f"{KC_URL}/admin/realms/{REALM}", token)
        if realm_data.get("browserFlow") == AUTOM_FLOW_ALIAS:
            put_body(f"{KC_URL}/admin/realms/{REALM}", {"browserFlow": "browser"}, token=token)
            print("  Temporarily bound realm to 'browser' for flow cleanup", flush=True)
        status, _ = delete(
            f"{KC_URL}/admin/realms/{REALM}/authentication/flows/{existing['id']}",
            token=token,
        )
        print(f"  Deleted existing '{AUTOM_FLOW_ALIAS}' (status {status}) for clean rebuild", flush=True)

    # 1. Copy built-in browser flow as the starting point.
    status, _ = post(
        f"{KC_URL}/admin/realms/{REALM}/authentication/flows/browser/copy",
        {"newName": AUTOM_FLOW_ALIAS},
        token=token,
    )
    if status not in (200, 201):
        print(f"  ERROR: copy browser flow returned {status}", flush=True)
        return
    print(f"  Copied 'browser' -> '{AUTOM_FLOW_ALIAS}'", flush=True)

    encoded_alias = urllib.parse.quote(AUTOM_FLOW_ALIAS, safe="")
    execs_url = f"{KC_URL}/admin/realms/{REALM}/authentication/flows/{encoded_alias}/executions"

    # 2. Disable the KC 26 Organization Identity-First subflow (level 0).
    #    Our custom autom-post-password-org-selector plugin handles org selection
    #    after authentication — we don't need KC's identity-first email-only page.
    execs = get(execs_url, token)
    org_subflow = next(
        (e for e in execs
         if e.get("authenticationFlow")
         and "organization" in e.get("displayName", "").lower()
         and e.get("level") == 0),
        None,
    )
    if org_subflow:
        if org_subflow.get("requirement") != "DISABLED":
            org_subflow["requirement"] = "DISABLED"
            put_body(execs_url, org_subflow, token=token)
        print(f"  Disabled Organization Identity-First subflow (org selection handled by plugin)", flush=True)
    else:
        print("  Organization subflow not found at level 0 (may already be absent)", flush=True)

    # 3. Find the forms subflow at level 0 (KC names it "{AUTOM_FLOW_ALIAS} forms").
    execs = get(execs_url, token)
    forms_exec = next(
        (e for e in execs
         if e.get("authenticationFlow") and "forms" in e.get("displayName", "").lower()
         and e.get("level") == 0),
        None,
    )
    if not forms_exec:
        print("  ERROR: forms subflow not found at level 0 in the copied browser flow", flush=True)
        return
    forms_alias = forms_exec.get("displayName")
    print(f"  Found forms subflow: '{forms_alias}'", flush=True)

    # 3. Add the CONDITIONAL post-auth subflow INSIDE the forms subflow (level 1).
    forms_encoded = urllib.parse.quote(forms_alias, safe="")
    status, _ = post(
        f"{KC_URL}/admin/realms/{REALM}/authentication/flows/{forms_encoded}/executions/flow",
        {"alias": POST_AUTH_SUBFLOW_ALIAS, "type": "basic-flow",
         "description": "Autom org+project selection (always-true condition)"},
        token=token,
    )
    if status not in (200, 201):
        print(f"  ERROR: create post-auth subflow inside forms returned {status}", flush=True)
        return
    print(f"  Created '{POST_AUTH_SUBFLOW_ALIAS}' inside '{forms_alias}'", flush=True)

    # 4. Set the new subflow's requirement to CONDITIONAL.
    execs = get(execs_url, token)
    post_auth_exec = next(
        (e for e in execs
         if e.get("displayName") == POST_AUTH_SUBFLOW_ALIAS and e.get("authenticationFlow")),
        None,
    )
    if not post_auth_exec:
        print(f"  ERROR: '{POST_AUTH_SUBFLOW_ALIAS}' not found in executions after creation", flush=True)
        return
    post_auth_exec["requirement"] = "CONDITIONAL"
    put_body(execs_url, post_auth_exec, token=token)
    print(f"  Set '{POST_AUTH_SUBFLOW_ALIAS}' -> CONDITIONAL", flush=True)

    # 5. Add four providers inside the CONDITIONAL subflow.
    subflow_encoded = urllib.parse.quote(POST_AUTH_SUBFLOW_ALIAS, safe="")
    for provider_id, label in [
        ("autom-condition-always",           "condition (always-true)"),
        ("autom-post-password-org-selector", "org selector"),
        ("autom-post-org-project-selector",  "project selector"),
        ("autom-mfa-enforcement",            "MFA enforcement (org mfaMandatory)"),
    ]:
        status, _ = post(
            f"{KC_URL}/admin/realms/{REALM}/authentication/flows/{subflow_encoded}/executions/execution",
            {"provider": provider_id},
            token=token,
        )
        if status in (200, 201):
            print(f"  Added {label}", flush=True)
        else:
            print(f"  Warning: add {label} returned {status}", flush=True)

    # 6. Set all four inner executions to REQUIRED.
    execs = get(execs_url, token)
    for e in execs:
        pid = e.get("providerId")
        if pid in ("autom-condition-always",
                   "autom-post-password-org-selector",
                   "autom-post-org-project-selector",
                   "autom-mfa-enforcement"):
            if e.get("requirement") != "REQUIRED":
                e["requirement"] = "REQUIRED"
                put_body(execs_url, e, token=token)
                print(f"  Set {pid} -> REQUIRED", flush=True)

    # 7. Bind realm browser flow.
    realm_data = get(f"{KC_URL}/admin/realms/{REALM}", token)
    if realm_data.get("browserFlow") != AUTOM_FLOW_ALIAS:
        status, _ = put_body(
            f"{KC_URL}/admin/realms/{REALM}",
            {"browserFlow": AUTOM_FLOW_ALIAS},
            token=token,
        )
        if status in (200, 204):
            print(f"  Realm browserFlow -> '{AUTOM_FLOW_ALIAS}'", flush=True)
        else:
            print(f"  Warning: set browserFlow returned {status}", flush=True)
    else:
        print(f"  Realm already bound to '{AUTOM_FLOW_ALIAS}'", flush=True)


def add_project_mapper(token):
    """
    Adds User Session Note mappers to the autom-app client: the selected
    project group ID ('project_id'), its name ('project_name'), the active
    organization ('autom_organization_id'), and the caller's resolved
    org/project role ('active_role') — all kept current on every org/project
    switch by the custom Keycloak provider, without a login redirect.
    """
    clients = get(
        f"{KC_URL}/admin/realms/{REALM}/clients?clientId={urllib.parse.quote(CLIENT_ID)}", token
    )
    client = next((c for c in clients if c.get("clientId") == CLIENT_ID), None)
    if not client:
        print(f"  Warning: client '{CLIENT_ID}' not found", flush=True)
        return

    existing = get(
        f"{KC_URL}/admin/realms/{REALM}/clients/{client['id']}/protocol-mappers/models", token
    ) or []
    mappings = [
        ("autom-project-id", "autom.project.group.id", "project_id"),
        ("autom-project-name", "autom.project.name", "project_name"),
        ("autom-active-organization-id", "autom.organization.id", "autom_organization_id"),
        # Set by AutomRoleResolver (PostOrgProjectSelectorAuthenticator at login,
        # AutomProjectSwitchResource on every switch) from Keycloak group
        # membership: org-admin (/{org}/admins or legacy /owners), project-admin
        # (/{org}/{project}/admins), or project-member (plain /{org}/{project}).
        # Cannot distinguish "owner" from "org-admin" — that split only exists in
        # the business backend's own OrgMember.OrgRole field, which already
        # treats them identically for permissions.
        ("autom-active-role", "autom.active.role", "active_role"),
        # KC's own native `organization` claim only reflects the alias requested
        # at ORIGINAL login (organization:<alias> scope) — a refresh token can't
        # silently re-scope to a different org, so it goes stale after an
        # in-session org switch. This note is kept current on every switch by
        # AutomProjectSwitchResource, giving the frontend a reliable alias for
        # building the next login/silent-check's scope hint (see
        # requestedOidcScope() / rememberOrganizationAlias() in main.tsx).
        ("autom-organization-alias", "autom.organization.alias", "organization_alias"),
    ]
    for name, note, claim in mappings:
        if any(m.get("config", {}).get("user.session.note") == note for m in existing):
            print(f"  {claim} mapper already on {CLIENT_ID}", flush=True)
            continue
        status, _ = post(
            f"{KC_URL}/admin/realms/{REALM}/clients/{client['id']}/protocol-mappers/models",
            {"name": name, "protocol": "openid-connect", "protocolMapper": "oidc-usersessionmodel-note-mapper",
             "consentRequired": False,
             "config": {"user.session.note": note, "claim.name": claim, "jsonType.label": "String",
                        "id.token.claim": "true", "access.token.claim": "true", "userinfo.token.claim": "true"}},
            token=token,
        )
        if status in (200, 201):
            print(f"  Added {claim} mapper to {CLIENT_ID}", flush=True)
        else:
            print(f"  Warning: add {claim} mapper returned {status}", flush=True)


# ── Organization member helpers ───────────────────────────────────────────────

def add_org_member(token, org_id, user_id):
    """Add a user to a native KC organization."""
    status, _ = post(
        f"{KC_URL}/admin/realms/{REALM}/organizations/{org_id}/members",
        {"id": user_id},
        token=token,
    )
    if status not in (201, 204, 409):
        print(f"  Warning: add org member returned {status}", flush=True)


def setup_demo_users(token, groups):
    """
    Creates demo users and assigns them to orgs + project groups.

      alice  – super-admin (no org membership)
      bob    – org-admin for org-alpha (member of /org-alpha/admins)
      carol  – project-admin for org-beta/project-3 (/org-beta/project-3/admins)
      dave   – project-member for org-alpha/project-1 (/org-alpha/project-1)
    """
    print("\nCreating demo users …", flush=True)

    demo = [
        ("alice",  "alice@example.com",  "Alice",  "Admin",   "Password1!"),
        ("bob",    "bob@example.com",    "Bob",    "OrgAdmin","Password1!"),
        ("carol",  "carol@example.com",  "Carol",  "ProjAdmin","Password1!"),
        ("dave",   "dave@example.com",   "Dave",   "Member",  "Password1!"),
    ]
    for username, email, first, last, pw in demo:
        create_user(token, username, email, first, last, pw)

    def uid(username):
        return get_user_id(token, username)

    # alice → super-admin realm role
    alice_id = uid("alice")
    if alice_id:
        super_admin_role = get_realm_role(token, "super-admin")
        if super_admin_role:
            assign_realm_roles(token, alice_id, [super_admin_role])
            print("  alice → super-admin role", flush=True)

    # Fetch orgs for membership assignment
    orgs = {o["alias"]: o["id"] for o in list_organizations(token)}

    # bob → org-alpha member + /org-alpha/admins group
    bob_id = uid("bob")
    if bob_id and "org-alpha" in orgs:
        add_org_member(token, orgs["org-alpha"], bob_id)
        g = groups.get("/org-alpha/admins")
        if g:
            assign_group(token, bob_id, g)
        print("  bob → org-alpha (admins)", flush=True)

    # carol → org-beta member + /org-beta/project-3/admins
    carol_id = uid("carol")
    if carol_id and "org-beta" in orgs:
        add_org_member(token, orgs["org-beta"], carol_id)
        g = groups.get("/org-beta/project-3/admins")
        if g:
            assign_group(token, carol_id, g)
        print("  carol → org-beta / project-3/admins", flush=True)

    # dave → org-alpha member + /org-alpha/project-1
    dave_id = uid("dave")
    if dave_id and "org-alpha" in orgs:
        add_org_member(token, orgs["org-alpha"], dave_id)
        g = groups.get("/org-alpha/project-1")
        if g:
            assign_group(token, dave_id, g)
        print("  dave → org-alpha / project-1", flush=True)


# ── Realm security settings ──────────────────────────────────────────────────

def _build_security_headers():
    """Build KC browserSecurityHeaders with correctly quoted CSP keywords.

    Single quotes are constructed with chr(39) so the string survives bash
    heredoc quoting (which strips literal single quotes from the script body).
    """
    q = chr(39)
    # A host-source with no port (https://*.seliselocal.com) only matches the
    # scheme's DEFAULT port (443) per the CSP spec — it silently excludes local
    # dev origins like automation.inb.seliselocal.com:5173, blocking the silent
    # check-sso iframe with a frame-ancestors violation. The :* variant is the
    # same wildcard-port treatment already given to the localhost entries.
    csp = (
        f"frame-src {q}self{q}; "
        f"frame-ancestors {q}self{q} https://*.seliselocal.com https://*.seliselocal.com:* "
        f"http://localhost:* https://localhost:*; "
        f"object-src {q}none{q};"
    )
    return {
        "contentSecurityPolicy": csp,
        "xFrameOptions": "",          # cleared — conflicts with frame-ancestors in Chrome
        "xContentTypeOptions": "nosniff",
        "referrerPolicy": "no-referrer",
        "xRobotsTag": "none",
        "strictTransportSecurity": "max-age=31536000; includeSubDomains",
    }


def configure_realm_security(token):
    """Apply brute-force protection, password policy, session timeouts, and CSP headers."""
    payload = {
        "bruteForceProtected":            True,
        "permanentLockout":               False,
        "maxFailureWaitSeconds":          900,
        "minimumQuickLoginWaitSeconds":   60,
        "waitIncrementSeconds":           60,
        "quickLoginCheckMilliSeconds":    1000,
        "maxDeltaTimeSeconds":            43200,
        "failureFactor":                  5,
        # Must stay comfortably above minimumQuickLoginWaitSeconds (60) above.
        # KC's default (60s) governs how long a single login-form step (the
        # session_code/execution behind the password page) stays valid before
        # KC silently discards it and restarts the whole flow -- no error, no
        # log event, just a fresh /auth redirect that looks exactly like the
        # app bounced you back to login. A user who gets locked out and does
        # the sensible thing (waits the ~60s for the lockout to clear before
        # retyping their password) was landing EXACTLY on that expired window
        # every single time, on the very next attempt. Confirmed live: a
        # correct-password submission 70s after the login page loaded bounced
        # silently with the 60s default, and succeeded cleanly once raised.
        "accessCodeLifespan":             300,
        "passwordPolicy":                 "length(12) and upperCase(1) and lowerCase(1) and digits(1) and notUsername() and passwordHistory(3)",
        "accessTokenLifespan":            300,
        "ssoSessionIdleTimeout":          1800,
        "ssoSessionMaxLifespan":          28800,
        "refreshTokenMaxReuse":           0,
        "resetPasswordAllowed":           False,
        # Allow the app to load KC in a hidden iframe for silent SSO check
        # (keycloak-js onLoad:'check-sso' + silentCheckSsoRedirectUri).
        # xFrameOptions is cleared because it conflicts with frame-ancestors in Chrome.
        # Single quotes are built with chr(39) to survive bash heredoc quoting.
        "browserSecurityHeaders": _build_security_headers(),
    }
    status, _ = put_body(f"{KC_URL}/admin/realms/{REALM}", payload, token=token)
    if status in (200, 204):
        print("  Realm security settings applied (brute-force, password policy, session timeouts, CSP)", flush=True)
    else:
        print(f"  Warning: realm security update returned {status}", flush=True)


def configure_client_security(token):
    """Remove '+' wildcard from webOrigins and add audience mapper to app-client."""
    clients = get(f"{KC_URL}/admin/realms/{REALM}/clients?clientId=app-client", token)
    if not clients:
        print("  Warning: app-client not found", flush=True)
        return
    client    = clients[0]
    client_id = client["id"]

    # Remove '+' wildcard from webOrigins
    origins = [o for o in (client.get("webOrigins") or []) if o != "+"]
    if origins != client.get("webOrigins"):
        status, _ = put_body(
            f"{KC_URL}/admin/realms/{REALM}/clients/{client_id}",
            {**client, "webOrigins": origins},
            token=token,
        )
        if status in (200, 204):
            print(f"  Removed '+' wildcard from app-client webOrigins → {origins}", flush=True)
        else:
            print(f"  Warning: update app-client webOrigins returned {status}", flush=True)
    else:
        print("  app-client webOrigins already clean (no '+' wildcard)", flush=True)

    # Add audience mapper if missing
    mappers = client.get("protocolMappers") or []
    if not any(m.get("protocolMapper") == "oidc-audience-mapper" for m in mappers):
        status, _ = post(
            f"{KC_URL}/admin/realms/{REALM}/clients/{client_id}/protocol-mappers/models",
            {
                "name":            "audience-mapper",
                "protocol":        "openid-connect",
                "protocolMapper":  "oidc-audience-mapper",
                "consentRequired": False,
                "config": {
                    "included.client.audience": "app-client",
                    "id.token.claim":           "false",
                    "access.token.claim":       "true",
                },
            },
            token=token,
        )
        if status in (200, 201):
            print("  Added audience mapper to app-client", flush=True)
        else:
            print(f"  Warning: add audience mapper returned {status}", flush=True)
    else:
        print("  Audience mapper already present on app-client", flush=True)


# ── autom-app PKCE enforcement ───────────────────────────────────────────────

def configure_autom_app_pkce(token):
    """Require PKCE S256 on autom-app so the server rejects auth-code exchanges
    that lack a code_verifier (prevents auth-code interception attacks)."""
    clients = get(
        f"{KC_URL}/admin/realms/{REALM}/clients?clientId={urllib.parse.quote(CLIENT_ID)}", token
    )
    client = next((c for c in clients if c.get("clientId") == CLIENT_ID), None)
    if not client:
        print(f"  Warning: client '{CLIENT_ID}' not found", flush=True)
        return
    attrs = client.get("attributes") or {}
    if attrs.get("pkce.code.challenge.method") == "S256":
        print(f"  {CLIENT_ID}: PKCE S256 already enforced", flush=True)
        return
    attrs["pkce.code.challenge.method"] = "S256"
    status, _ = put_body(
        f"{KC_URL}/admin/realms/{REALM}/clients/{client['id']}",
        {**client, "attributes": attrs},
        token=token,
    )
    if status in (200, 204):
        print(f"  {CLIENT_ID}: PKCE S256 enforcement enabled", flush=True)
    else:
        print(f"  Warning: set PKCE on {CLIENT_ID} returned {status}", flush=True)


# ── Browser - SuperAdmin only flow ───────────────────────────────────────────

SUPERADMIN_FLOW_ALIAS = "Browser - SuperAdmin only"
SUPERADMIN_CLIENT_ID  = "autom-superadmin"


def setup_superadmin_browser_flow(token):
    """
    Creates a 'Browser - SuperAdmin only' KC authentication flow that denies
    login to any user who does NOT have the 'super-admin' realm role.

    Flow structure (copy of browser):
      Cookie (DISABLED)                         ← see below, was ALTERNATIVE
      Identity Provider Redirector (ALTERNATIVE)
      forms subflow (ALTERNATIVE)
        Username Password Form (REQUIRED)
        2FA conditional (CONDITIONAL)
        Role gate (CONDITIONAL)                 ← blocks non-super-admins
          Condition - user role (REQUIRED)      ← condUserRole=super-admin, negate=true
          Deny access (REQUIRED)

    Cookie is deliberately DISABLED here (unlike the main 'browser' flow it was
    copied from, where it stays ALTERNATIVE): as an ALTERNATIVE at the same
    level as 'forms', a valid pre-existing SSO session cookie short-circuits
    the whole ALTERNATIVE group and 'forms' — including the Role gate inside
    it — never runs at all. Concretely: a plain business-portal user with a
    live SSO cookie could get a token minted for autom-superadmin without ever
    being role-checked (confirmed live, 2026-09-20, before this fix — see
    project memory / D:\\AutomNew\\l3-react-autom-superadmin's main.tsx history).
    Disabling Cookie here forces every login attempt on this flow through
    'forms' unconditionally, so the Role gate always runs. This mirrors the FE
    fix (prompt: 'login' on both portals' keycloak.login() calls) at the KC
    layer, and is the one that also protects a caller hitting the authorize
    endpoint directly instead of going through the React app.

    Then binds the flow as a browser-flow override on the autom-superadmin client.
    """
    flows = get(f"{KC_URL}/admin/realms/{REALM}/authentication/flows", token)
    if not any(f.get("alias") == SUPERADMIN_FLOW_ALIAS for f in flows):
        status, _ = post(
            f"{KC_URL}/admin/realms/{REALM}/authentication/flows/browser/copy",
            {"newName": SUPERADMIN_FLOW_ALIAS},
            token=token,
        )
        if status not in (200, 201):
            print(f"  Warning: copy browser flow for super-admin returned {status}", flush=True)
            return
        print(f"  Copied 'browser' → '{SUPERADMIN_FLOW_ALIAS}'", flush=True)
    else:
        print(f"  Flow '{SUPERADMIN_FLOW_ALIAS}' already exists – verifying role gate", flush=True)

    encoded_alias = urllib.parse.quote(SUPERADMIN_FLOW_ALIAS, safe="")
    execs_url = f"{KC_URL}/admin/realms/{REALM}/authentication/flows/{encoded_alias}/executions"
    execs = get(execs_url, token)

    # Disable the top-level Cookie (auth-cookie) execution -- see the
    # docstring above for why. Without this, an existing SSO session cookie
    # bypasses 'forms' (and the Role gate inside it) entirely.
    cookie_exec = next(
        (e for e in execs if e.get("level") == 0 and e.get("providerId") == "auth-cookie"),
        None,
    )
    if cookie_exec and cookie_exec.get("requirement") != "DISABLED":
        cookie_exec["requirement"] = "DISABLED"
        status, _ = put_body(execs_url, cookie_exec, token=token)
        if status in (200, 204):
            print("  Disabled Cookie execution (was bypassing the Role gate)", flush=True)
        else:
            print(f"  Warning: disable Cookie execution returned {status}", flush=True)
    elif cookie_exec:
        print("  Cookie execution already DISABLED", flush=True)
    else:
        print("  Warning: no top-level 'auth-cookie' execution found to disable", flush=True)

    # Locate the forms subflow.
    forms_name = next(
        (e.get("displayName") for e in execs
         if "forms" in (e.get("displayName") or "").lower()
         and e.get("level") == 0 and e.get("authenticationFlow")),
        None,
    )
    if not forms_name:
        print("  Warning: could not find forms subflow in super-admin flow", flush=True)
        return
    forms_alias = urllib.parse.quote(forms_name, safe="")

    # Add a Role gate (CONDITIONAL subflow) inside the forms subflow if missing.
    has_role_gate = any(
        (e.get("displayName") or "").lower() == "role gate" and e.get("level") == 1
        for e in execs
    )
    if not has_role_gate:
        status, _ = post(
            f"{KC_URL}/admin/realms/{REALM}/authentication/flows/{forms_alias}/executions/flow",
            {"alias": "Role gate", "description": "", "type": "basic-flow", "provider": "registration-page-form"},
            token=token,
        )
        if status in (200, 201):
            print("  Created 'Role gate' subflow", flush=True)
        else:
            print(f"  Warning: create Role gate returned {status}", flush=True)
            return

    # Set the Role gate to CONDITIONAL.
    execs = get(execs_url, token)
    role_gate = next(
        (e for e in execs
         if (e.get("displayName") or "").lower() == "role gate" and e.get("level") == 1),
        None,
    )
    if role_gate and role_gate.get("requirement") != "CONDITIONAL":
        role_gate["requirement"] = "CONDITIONAL"
        put_body(execs_url, role_gate, token=token)
        print("  Role gate set to CONDITIONAL", flush=True)

    # Inside Role gate: add conditional-user-role and deny-access if missing.
    role_gate_name = role_gate["displayName"] if role_gate else "Role gate"
    role_gate_alias = urllib.parse.quote(role_gate_name, safe="")

    def _add_to_role_gate(provider_id, label):
        execs = get(execs_url, token)
        if any(e.get("providerId") == provider_id and e.get("level") == 2 for e in execs):
            print(f"  {label} already in Role gate", flush=True)
            return
        status, _ = post(
            f"{KC_URL}/admin/realms/{REALM}/authentication/flows/{role_gate_alias}/executions/execution",
            {"provider": provider_id},
            token=token,
        )
        if status in (200, 201):
            print(f"  Added {label} to Role gate", flush=True)
        else:
            print(f"  Warning: add {label} returned {status}", flush=True)

    _add_to_role_gate("conditional-user-role", "Condition - user role")
    _add_to_role_gate("deny-access-authenticator", "Deny access")

    # Set both to REQUIRED.
    execs = get(execs_url, token)
    for e in execs:
        if e.get("providerId") in ("conditional-user-role", "deny-access-authenticator") \
                and e.get("level") == 2 and e.get("requirement") != "REQUIRED":
            e["requirement"] = "REQUIRED"
            put_body(execs_url, e, token=token)
            print(f"  Set {e['providerId']} → REQUIRED", flush=True)

    # Configure conditional-user-role: super-admin with NEGATIVE logic
    # (deny users who do NOT have the super-admin role).
    execs = get(execs_url, token)
    cond_exec = next(
        (e for e in execs if e.get("providerId") == "conditional-user-role" and e.get("level") == 2),
        None,
    )
    if cond_exec:
        existing_cfg_id = cond_exec.get("authenticationConfig")
        if not existing_cfg_id:
            status, _ = post(
                f"{KC_URL}/admin/realms/{REALM}/authentication/executions/{cond_exec['id']}/config",
                {"alias": "super-admin-only", "config": {"condUserRole": "super-admin", "negate": "true"}},
                token=token,
            )
            if status in (200, 201):
                print("  Configured role gate: condUserRole=super-admin, negate=true", flush=True)
            else:
                print(f"  Warning: configure role gate returned {status}", flush=True)
        else:
            status, _ = put_body(
                f"{KC_URL}/admin/realms/{REALM}/authentication/config/{existing_cfg_id}",
                {"alias": "super-admin-only", "config": {"condUserRole": "super-admin", "negate": "true"}},
                token=token,
            )
            if status in (200, 204):
                print("  Updated role gate config", flush=True)

    # Bind the flow as a browser-flow override on the autom-superadmin client.
    clients = get(
        f"{KC_URL}/admin/realms/{REALM}/clients?clientId={urllib.parse.quote(SUPERADMIN_CLIENT_ID)}", token
    )
    sa_client = next((c for c in clients if c.get("clientId") == SUPERADMIN_CLIENT_ID), None)
    if not sa_client:
        print(f"  Warning: '{SUPERADMIN_CLIENT_ID}' client not found – flow created but not bound", flush=True)
        return

    flows = get(f"{KC_URL}/admin/realms/{REALM}/authentication/flows", token)
    flow_id = next((f["id"] for f in flows if f.get("alias") == SUPERADMIN_FLOW_ALIAS), None)
    if not flow_id:
        print("  Warning: could not read back flow ID", flush=True)
        return

    overrides = sa_client.get("authenticationFlowBindingOverrides") or {}
    if overrides.get("browser") == flow_id:
        print(f"  '{SUPERADMIN_CLIENT_ID}' already bound to '{SUPERADMIN_FLOW_ALIAS}'", flush=True)
        return

    overrides["browser"] = flow_id
    status, _ = put_body(
        f"{KC_URL}/admin/realms/{REALM}/clients/{sa_client['id']}",
        {**sa_client, "authenticationFlowBindingOverrides": overrides},
        token=token,
    )
    if status in (200, 204):
        print(f"  Bound '{SUPERADMIN_FLOW_ALIAS}' to '{SUPERADMIN_CLIENT_ID}' client", flush=True)
    else:
        print(f"  Warning: bind flow to client returned {status}", flush=True)


# ── Required-action helpers ───────────────────────────────────────────────────

def enable_required_action(token, alias, label, default=False):
    actions = get(f"{KC_URL}/admin/realms/{REALM}/authentication/required-actions", token)
    for action in actions:
        if action.get("alias") == alias:
            changed = False
            if not action.get("enabled"):
                action["enabled"] = True
                changed = True
            if default and not action.get("defaultAction"):
                action["defaultAction"] = True
                changed = True
            elif not default and action.get("defaultAction"):
                action["defaultAction"] = False
                changed = True
            if changed:
                put_body(
                    f"{KC_URL}/admin/realms/{REALM}/authentication/required-actions/{urllib.parse.quote(alias, safe='')}",
                    action,
                    token=token,
                )
                tag = " (default=ON)" if default else ""
                print(f"  Configured required action: {label}{tag}", flush=True)
            else:
                print(f"  Required action already configured: {label}", flush=True)
            return
    print(f"  Required action not found in realm: {alias}", flush=True)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    wait_for_realm()

    print("Acquiring admin token …", flush=True)
    token = get_token()
    if not token:
        raise RuntimeError("Could not obtain admin token – check credentials.")

    # ── Ensure roles exist ────────────────────────────────────────────────
    print("\nEnsuring realm roles …", flush=True)
    ensure_realm_role(token, "super-admin", "System-wide super administrator; super-admin portal only")
    ensure_realm_role(token, "owner", "Organization owner")
    ensure_realm_role(token, "org-admin", "Organization administrator")
    ensure_realm_role(token, "project-admin", "Project administrator")
    ensure_realm_role(token, "project-member", "Project member")

    # Native Organizations own the login-time org picker and emit the signed
    # `organization` claim. Realm groups below remain only as legacy project
    # hierarchy data for the POC; they are not used to authorize org access.
    print("\nEnabling native Keycloak Organizations …", flush=True)
    enable_organizations(token)
    for org in ("org-alpha", "org-beta", "org-gamma"):
        ensure_organization(token, org.replace("-", " ").title(), org)
    add_organization_scope_to_client(token, CLIENT_ID)

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

    # ── Identity Providers (SSO) ──────────────────────────────────────────
    print("\nConfiguring Identity Providers …", flush=True)
    if GOOGLE_CLIENT_ID and GOOGLE_SECRET:
        ensure_idp(token, "google", "Google", "google", {
            "clientId":     GOOGLE_CLIENT_ID,
            "clientSecret": GOOGLE_SECRET,
            "syncMode":     "IMPORT",
            "useJwksUrl":   "true",
        })
    else:
        print("  GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET not set – skipping Google IdP", flush=True)

    if MS_CLIENT_ID and MS_SECRET:
        ensure_idp(token, "microsoft", "Microsoft", "microsoft", {
            "clientId":     MS_CLIENT_ID,
            "clientSecret": MS_SECRET,
            "syncMode":     "IMPORT",
            "tenant":       "common",
        })
    else:
        print("  MICROSOFT_CLIENT_ID / MICROSOFT_CLIENT_SECRET not set – skipping Microsoft IdP", flush=True)

    # ── Realm security hardening ──────────────────────────────────────────
    print("\nApplying realm security settings …", flush=True)
    configure_realm_security(token)

    print("\nHardening app-client (webOrigins, audience mapper) …", flush=True)
    configure_client_security(token)

    # ── Autom custom browser flow (org + project selector) ───────────────
    print("\nSetting up Autom post-password org/project browser flow …", flush=True)
    setup_autom_browser_flow(token)

    print("\nAdding project_id token mapper …", flush=True)
    add_project_mapper(token)

    print("\nEnforcing PKCE S256 on autom-app …", flush=True)
    configure_autom_app_pkce(token)

    print("\nSetting up Browser-SuperAdmin-only auth flow …", flush=True)
    setup_superadmin_browser_flow(token)

    # ── Demo users ───────────────────────────────────────────────────────
    setup_demo_users(token, groups)

    # ── Modern Authenticators ─────────────────────────────────────────────
    print("\nEnabling modern authenticators …", flush=True)
    enable_required_action(token, "CONFIGURE_TOTP",                 "Configure OTP",                default=True)
    enable_required_action(token, "webauthn-register",              "WebAuthn Register")
    enable_required_action(token, "webauthn-register-passwordless", "WebAuthn Passwordless Register")

    print("\nConfiguring WebAuthn policies …", flush=True)
    configure_webauthn_policy(token)

    print("\nSetting up WebAuthn browser flow …", flush=True)
    setup_webauthn_browser_flow(token)

    print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Keycloak demo data ready!

 Keycloak admin console: http://localhost:8080  (use KEYCLOAK_ADMIN / KEYCLOAK_ADMIN_PASSWORD from your .env)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""", flush=True)


if __name__ == "__main__":
    main()
