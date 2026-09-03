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

KC_URL            = os.environ.get("KC_URL",                    "http://keycloak:8080")
REALM             = os.environ.get("KC_REALM",                  "app-realm")
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


def setup_webauthn_browser_flow(token):
    """
    Create a 'webauthn-browser' flow (copy of browser) that adds:
      • WebAuthn Passwordless Authenticator (ALTERNATIVE) – for passkey login
      • WebAuthn Authenticator (ALTERNATIVE) inside forms subflow – for security-key 2FA
    Then binds the realm to this flow.
    """
    FLOW_ALIAS = "webauthn-browser"

    # 1 – copy browser flow if not yet present
    flows = get(f"{KC_URL}/admin/realms/{REALM}/authentication/flows", token)
    if not any(f.get("alias") == FLOW_ALIAS for f in flows):
        status, _ = post(
            f"{KC_URL}/admin/realms/{REALM}/authentication/flows/browser/copy",
            {"newName": FLOW_ALIAS},
            token=token,
        )
        if status in (200, 201):
            print(f"  Copied 'browser' → '{FLOW_ALIAS}'", flush=True)
        else:
            print(f"  Warning: copy browser flow returned {status}", flush=True)
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

    # 5 – bind realm to this flow
    realm_data = get(f"{KC_URL}/admin/realms/{REALM}", token)
    if realm_data.get("browserFlow") != FLOW_ALIAS:
        status, _ = put_body(
            f"{KC_URL}/admin/realms/{REALM}",
            {"browserFlow": FLOW_ALIAS},
            token=token,
        )
        if status in (200, 204):
            print(f"  Realm browserFlow → '{FLOW_ALIAS}'", flush=True)
        else:
            print(f"  Warning: set browserFlow returned {status}", flush=True)
    else:
        print(f"  Realm already bound to '{FLOW_ALIAS}'", flush=True)


# ── Realm security settings ──────────────────────────────────────────────────

def configure_realm_security(token):
    """Apply brute-force protection, password policy, and session timeouts."""
    payload = {
        "bruteForceProtected":            True,
        "permanentLockout":               False,
        "maxFailureWaitSeconds":          900,
        "minimumQuickLoginWaitSeconds":   60,
        "waitIncrementSeconds":           60,
        "quickLoginCheckMilliSeconds":    1000,
        "maxDeltaTimeSeconds":            43200,
        "failureFactor":                  5,
        "passwordPolicy":                 "length(12) and upperCase(1) and lowerCase(1) and digits(1) and notUsername() and passwordHistory(3)",
        "accessTokenLifespan":            300,
        "ssoSessionIdleTimeout":          1800,
        "ssoSessionMaxLifespan":          28800,
        "refreshTokenMaxReuse":           0,
        "resetPasswordAllowed":           False,
    }
    status, _ = put_body(f"{KC_URL}/admin/realms/{REALM}", payload, token=token)
    if status in (200, 204):
        print("  Realm security settings applied (brute-force, password policy, session timeouts)", flush=True)
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

    # ── Force TOTP setup for all demo users ───────────────────────────────
    print("\nForcing TOTP setup for demo users …", flush=True)
    for uid, uname in [(alice_id, "alice"), (bob_id, "bob"), (carol_id, "carol"), (dave_id, "dave")]:
        force_required_action(token, uid, uname, "CONFIGURE_TOTP")

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
