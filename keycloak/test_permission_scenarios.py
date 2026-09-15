#!/usr/bin/env python3
"""
Full regression suite for the autom-realm org/project/role/permission system.

Exercises real logins, real Keycloak group membership, and the real .NET
Autom.Api backend (no mocks) — everything here was manually verified once
during the 2026-09-14 Keycloak/permissions fix session and is captured here
so it can be re-run instead of re-derived from scratch.

Prerequisites:
  - Keycloak reachable at KC_URL, autom-realm's autom-app client configured
    (redirect URIs / CORS / CSP fixes from the 2026-09-14 session applied).
  - l3-net-autom-business's Autom.Api running locally on API_URL.
  - The fixture users/roles below exist. Run --setup once to (re)create them
    via the real SuperAdmin API (needs SUPERADMIN_USERNAME/PASSWORD — a demo
    account with the `super-admin` realm role, e.g. alice from init.py, with
    a password set via `PUT /admin/realms/autom-realm/users/{id}/reset-password`
    since demo accounts don't ship with a known password otherwise).

Usage:
  python test_permission_scenarios.py --setup   # (re)create fixture users/roles
  python test_permission_scenarios.py           # run all scenarios
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

from verify_login_flow import Flow, decode_jwt, call_api

KC_URL = "https://keycloak.inb.seliselocal.com"
REALM = "autom-realm"
CLIENT_ID = "autom-app"
REDIRECT_URI = "https://automation.inb.seliselocal.com:5173/"
API_URL = "http://localhost:5000"

# All credentials below are read from the environment — nothing here is a
# real secret. Set these before running (values fixed for repeatable test
# runs across the fixture accounts these scripts create/reuse):
#   KC_MASTER_ADMIN_USERNAME / KC_MASTER_ADMIN_PASSWORD — realm "master" admin-cli login
#   KC_SUPERADMIN_USERNAME / KC_SUPERADMIN_PASSWORD      — demo super-admin account (alice)
#   KC_ORG_ADMIN_TEST_EMAIL / KC_ORG_ADMIN_TEST_PASSWORD — pre-existing org-admin fixture
#   KC_TEST_FIXTURE_PASSWORD                             — shared password for the
#       project-member/project-admin/dual-role fixture accounts this script creates
MASTER_ADMIN_USERNAME = os.environ["KC_MASTER_ADMIN_USERNAME"]
MASTER_ADMIN_PASSWORD = os.environ["KC_MASTER_ADMIN_PASSWORD"]
SUPERADMIN_USERNAME = os.environ.get("KC_SUPERADMIN_USERNAME", "alice")
SUPERADMIN_PASSWORD = os.environ["KC_SUPERADMIN_PASSWORD"]

# ── Realm fixtures (Test_3 / test_4 orgs, p3/p5 projects under Test_3) ──────
ORG_TEST3_MONGO_ID = "4635a725-3035-45cf-a9bc-ef7337760d96"   # Organization.ItemId == KC top group id
ORG_TEST4_MONGO_ID = "70f9e9f8-d192-4337-ae5d-71e0b8d8afc4"
ORG_TEST3_KC_ID = "a1f8ff69-4680-45b8-adf5-b026463807fe"       # KC native Organization id
ORG_TEST4_KC_ID = "ea58a135-5e6c-4f65-b2f4-57de2e36e1d6"
PROJECT_P3_ID = "8bd7b0e6-399a-434c-bf1b-02178453c233"
PROJECT_P5_ID = "17e66a0a-7564-4034-8e48-866e3eb3d387"
PROJECT_P4_ID = "fbc583df-f4be-445c-9c18-568a42519a84"

# ── Test accounts (created by --setup; passwords fixed for repeatable runs) ──
_TEST_FIXTURE_PASSWORD = os.environ.get("KC_TEST_FIXTURE_PASSWORD", SUPERADMIN_PASSWORD)
ORG_ADMIN_USER = (os.environ["KC_ORG_ADMIN_TEST_EMAIL"], os.environ["KC_ORG_ADMIN_TEST_PASSWORD"])  # pre-existing; org-admin in Test_3, plain member of test_4
PROJECT_MEMBER_USER = ("verify-project-member@example.com", _TEST_FIXTURE_PASSWORD)   # project-member on p5
PROJECT_ADMIN_USER = ("verify-project-admin2@example.com", _TEST_FIXTURE_PASSWORD)    # project-admin on p5
DUAL_ROLE_USER = ("verify-dual-role@example.com", _TEST_FIXTURE_PASSWORD)            # project-admin on p5 + project-member on p3 (until promoted to org-admin by test 9)

PASS, FAIL = "PASS", "FAIL"
_results = []


def check(name, condition, detail=""):
    status = PASS if condition else FAIL
    _results.append((status, name, detail))
    print(f"[{status}] {name}" + (f" — {detail}" if detail and status == FAIL else ""))
    return condition


def login(username, password, org, project):
    flow = Flow(KC_URL, REALM, CLIENT_ID, REDIRECT_URI)
    return flow, flow.login(username, password, org, project)


def login_superadmin(username, password):
    """Super-admins skip org/project selection entirely (no KC org membership),
    so credentials POST redirects straight to redirect_uri#code=... — unlike
    Flow.login(), which expects an org/project picker step in between."""
    flow = Flow(KC_URL, REALM, CLIENT_ID, REDIRECT_URI)
    auth_params = {
        "client_id": CLIENT_ID, "redirect_uri": REDIRECT_URI, "response_type": "code",
        "response_mode": "fragment", "scope": "openid profile email",
        "code_challenge": flow.code_challenge, "code_challenge_method": "S256",
        "state": "s1", "nonce": "n1",
    }
    auth_url = f"{KC_URL}/realms/{REALM}/protocol/openid-connect/auth?" + urllib.parse.urlencode(auth_params)
    _, _, html = flow._request("GET", auth_url)
    action = flow._form_action(html)
    _, loc, html = flow._request("POST", action, {"username": username, "password": password, "credentialId": ""})
    if "Invalid username or password" in html:
        raise RuntimeError("Invalid super-admin credentials")

    final_loc = loc
    hops = 0
    while final_loc and "code=" not in final_loc and hops < 5:
        _, final_loc, _ = flow._request("GET", final_loc)
        hops += 1
    frag = final_loc.split("#", 1)[1] if "#" in final_loc else final_loc.split("?", 1)[1]
    auth_code = dict(urllib.parse.parse_qsl(frag)).get("code")

    token_req = urllib.request.Request(
        f"{KC_URL}/realms/{REALM}/protocol/openid-connect/token",
        data=urllib.parse.urlencode({
            "grant_type": "authorization_code", "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI, "code": auth_code, "code_verifier": flow.code_verifier,
        }).encode(),
        method="POST",
    )
    token_req.add_header("Content-Type", "application/x-www-form-urlencoded")
    return json.loads(urllib.request.urlopen(token_req).read().decode())


def get_admin_token():
    req = urllib.request.Request(
        f"{KC_URL}/realms/master/protocol/openid-connect/token",
        data=urllib.parse.urlencode({
            "grant_type": "password", "client_id": "admin-cli",
            "username": MASTER_ADMIN_USERNAME, "password": MASTER_ADMIN_PASSWORD,
        }).encode(),
        method="POST",
    )
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    return json.loads(urllib.request.urlopen(req).read().decode())["access_token"]


# ── Scenario 1: fresh login claim sanity ────────────────────────────────────
def test_fresh_login_claims():
    print("\n=== 1. Fresh login: claim sanity (org-admin user) ===")
    _, token = login(*ORG_ADMIN_USER, "test-3", "p3")
    claims = decode_jwt(token["access_token"])
    check("autom_organization_id present", bool(claims.get("autom_organization_id")))
    check("project_id present", bool(claims.get("project_id")))
    check("active_role == org-admin", claims.get("active_role") == "org-admin", claims.get("active_role"))
    check("organization_alias == test-3", claims.get("organization_alias") == "test-3", claims.get("organization_alias"))
    check("native organization claim is ABSENT (removed 2026-09-14)", claims.get("organization") is None, claims.get("organization"))


# ── Scenario 2: org-admin switches org + project ────────────────────────────
def test_org_admin_switch_org_and_project():
    print("\n=== 2. Org-admin switches org (test-3 -> test-4) and project (p3 -> p4) ===")
    flow, token = login(*ORG_ADMIN_USER, "test-3", "p3")
    before = decode_jwt(token["access_token"])
    status, _ = flow.switch_project(token["access_token"], ORG_TEST4_KC_ID, PROJECT_P4_ID)
    check("switch-project returns 204", status == 204, status)
    token2 = flow.refresh(token["refresh_token"])
    after = decode_jwt(token2["access_token"])

    check("autom_organization_id changed", before["autom_organization_id"] != after["autom_organization_id"])
    check("project_id changed", before["project_id"] != after["project_id"])
    check("organization_alias changed (test-3 -> test-4)", after.get("organization_alias") == "test-4", after.get("organization_alias"))
    check("native organization claim stays absent", after.get("organization") is None)
    check("scope string unchanged", before["scope"] == after["scope"])
    check("active_role stays org-admin (org-wide access in both orgs)", after.get("active_role") == "org-admin", after.get("active_role"))

    s1, orgs = call_api(f"{API_URL}/api/organizations", token2["access_token"])
    check(".NET /api/organizations reflects both orgs, 200", s1 == 200 and len(orgs) >= 2, (s1, orgs))
    s2, perms = call_api(f"{API_URL}/api/me/permissions", token2["access_token"])
    check(".NET /api/me/permissions full access after switch", s2 == 200 and "api:read" in perms, (s2, perms))


# ── Scenario 3: SAME user's role changes across projects in the SAME org ───
def test_same_user_role_changes_with_project_switch():
    print("\n=== 3. Same user, same org, switch project p5 (project-admin) -> p3 (project-member) ===")
    flow, token = login(*DUAL_ROLE_USER_FIXTURE(), "test-3", "p5")
    before = decode_jwt(token["access_token"])
    check("initial active_role == project-admin", before.get("active_role") == "project-admin", before.get("active_role"))
    s0, perms0 = call_api(f"{API_URL}/api/me/permissions", token["access_token"])
    check("initial permissions are full (project-admin)", s0 == 200 and "api:read" in perms0, (s0, perms0))

    status, _ = flow.switch_project(token["access_token"], ORG_TEST3_KC_ID, PROJECT_P3_ID)
    check("switch-project (same org) returns 204", status == 204, status)
    token2 = flow.refresh(token["refresh_token"])
    after = decode_jwt(token2["access_token"])

    check("autom_organization_id UNCHANGED (same org)", before["autom_organization_id"] == after["autom_organization_id"])
    check("project_id changed", before["project_id"] != after["project_id"])
    check("active_role changed to project-member", after.get("active_role") == "project-member", after.get("active_role"))
    s1, perms1 = call_api(f"{API_URL}/api/me/permissions", token2["access_token"])
    check("permissions now empty (plain project-member, no custom roles)", s1 == 200 and perms1 == [], (s1, perms1))


def DUAL_ROLE_USER_FIXTURE():
    return DUAL_ROLE_USER


# ── Scenario 4/5: unauthorized switch is rejected ───────────────────────────
def test_unauthorized_switch_denied():
    print("\n=== 4/5. project-member denied switching to a project/org they don't belong to ===")
    flow, token = login(*PROJECT_MEMBER_USER, "test-3", "p5")
    status, body = flow.switch_project(token["access_token"], ORG_TEST3_KC_ID, PROJECT_P3_ID)
    check("switch to unauthorized project in same org -> 403", status == 403, (status, body))
    status, body = flow.switch_project(token["access_token"], ORG_TEST4_KC_ID, PROJECT_P4_ID)
    check("switch to unauthorized org -> 403", status == 403, (status, body))


# ── Scenario 6: custom role permission format ───────────────────────────────
def test_custom_role_permission_format(admin_token):
    print("\n=== 6. Custom role permission format: colon accepted, dot rejected for non-super-admin roles ===")
    _ensure_role(admin_token, ORG_TEST3_MONGO_ID, "test-format-role")
    status, body = _set_role_permissions(admin_token, ORG_TEST3_MONGO_ID, "test-format-role", ["api:read", "web-ui:write"])
    check("colon-format feature permissions accepted (204)", status == 204, (status, body))
    status, body = _set_role_permissions(admin_token, ORG_TEST3_MONGO_ID, "test-format-role", ["users.impersonate"])
    check("dot-format admin permission on non-super-admin role REJECTED (400)", status == 400, (status, body))
    _set_role_permissions(admin_token, ORG_TEST3_MONGO_ID, "test-format-role", [])  # leave it harmless


# ── Scenario 7: custom role assignment is Mongo-only, never a KC realm role ─
def test_custom_role_is_kc_safe(admin_token):
    print("\n=== 7. Custom role assignment never touches Keycloak realm roles (privilege-escalation guard) ===")
    _ensure_role(admin_token, ORG_TEST3_MONGO_ID, "test-safe-role")
    _set_role_permissions(admin_token, ORG_TEST3_MONGO_ID, "test-safe-role", ["api:read", "tests:read"])
    member_id = _member_id_of(admin_token, PROJECT_MEMBER_USER[0])
    status, _ = _put(admin_token, f"{API_URL}/api/super-admin/orgs/{ORG_TEST3_MONGO_ID}/users/{member_id}/custom-roles",
                      {"customRoles": ["test-safe-role"]})
    check("assign custom role via safe Mongo-only endpoint -> 204", status == 204, status)

    flow, token = login(*PROJECT_MEMBER_USER, "test-3", "p5")
    claims = decode_jwt(token["access_token"])
    check("custom role name NOT in realm_access.roles (no KC leak)",
          "test-safe-role" not in claims["realm_access"]["roles"], claims["realm_access"]["roles"])
    status, perms = call_api(f"{API_URL}/api/me/permissions", token["access_token"])
    check("permissions match the custom role exactly", status == 200 and set(perms) == {"api:read", "tests:read"}, (status, perms))

    # cleanup: leave the member with no custom roles for a clean re-run
    _put(admin_token, f"{API_URL}/api/super-admin/orgs/{ORG_TEST3_MONGO_ID}/users/{member_id}/custom-roles", {"customRoles": []})


# ── Scenario 8: live custom-role permission edit propagates without re-login ─
def test_live_permission_edit_propagates(admin_token):
    print("\n=== 8. Editing a custom role's permissions propagates immediately (no re-login needed for a NEW token) ===")
    _ensure_role(admin_token, ORG_TEST3_MONGO_ID, "test-live-role")
    member_id = _member_id_of(admin_token, PROJECT_MEMBER_USER[0])
    _put(admin_token, f"{API_URL}/api/super-admin/orgs/{ORG_TEST3_MONGO_ID}/users/{member_id}/custom-roles",
         {"customRoles": ["test-live-role"]})
    _set_role_permissions(admin_token, ORG_TEST3_MONGO_ID, "test-live-role", ["api:read"])

    _, token = login(*PROJECT_MEMBER_USER, "test-3", "p5")
    s1, perms1 = call_api(f"{API_URL}/api/me/permissions", token["access_token"])
    check("permissions reflect first version", s1 == 200 and perms1 == ["api:read"], (s1, perms1))

    _set_role_permissions(admin_token, ORG_TEST3_MONGO_ID, "test-live-role", ["tests:read", "reports:read"])
    s2, perms2 = call_api(f"{API_URL}/api/me/permissions", token["access_token"])
    check("SAME token, updated permission set now returned (cache busted)",
          s2 == 200 and set(perms2) == {"tests:read", "reports:read"}, (s2, perms2))

    _put(admin_token, f"{API_URL}/api/super-admin/orgs/{ORG_TEST3_MONGO_ID}/users/{member_id}/custom-roles", {"customRoles": []})


# ── Scenario 9: promote a project-scoped member to org-admin ───────────────
def test_promote_to_org_admin(admin_token):
    print("\n=== 9. Promote a project-scoped member to org-admin: groups + role + permissions all update ===")
    member_id = _member_id_of(admin_token, DUAL_ROLE_USER[0])
    status, _ = _patch(admin_token, f"{API_URL}/api/super-admin/orgs/{ORG_TEST3_MONGO_ID}/users/{member_id}",
                        {"orgRole": "org-admin", "projectAccess": []})
    check("promote to org-admin -> 200", status == 200, status)

    _, token = login(*DUAL_ROLE_USER, "test-3", "p3")
    claims = decode_jwt(token["access_token"])
    check("old project groups removed from token", "/Test_3/p5/admins" not in claims["groups"] and "/Test_3/p3" not in claims["groups"], claims["groups"])
    check("now a member of /Test_3/admins", "/Test_3/admins" in claims["groups"], claims["groups"])
    check("active_role == org-admin", claims.get("active_role") == "org-admin", claims.get("active_role"))
    status, perms = call_api(f"{API_URL}/api/me/permissions", token["access_token"])
    check("full permissions after promotion", status == 200 and "api:read" in perms, (status, perms))


# ── Scenario 10: role catalogs are per-organization, never shared (2026-09-14 fix) ─
def test_roles_are_org_scoped(admin_token):
    print("\n=== 10. Two orgs can each have a role with the SAME name, with DIFFERENT permissions, no collision ===")
    _ensure_role(admin_token, ORG_TEST3_MONGO_ID, "shared-name-role")
    _ensure_role(admin_token, ORG_TEST4_MONGO_ID, "shared-name-role")
    _set_role_permissions(admin_token, ORG_TEST3_MONGO_ID, "shared-name-role", ["api:read"])
    _set_role_permissions(admin_token, ORG_TEST4_MONGO_ID, "shared-name-role", ["tests:write"])

    def _get_perms(org_id):
        req = urllib.request.Request(f"{API_URL}/api/super-admin/orgs/{org_id}/roles/shared-name-role/permissions")
        req.add_header("Authorization", f"Bearer {admin_token}")
        return json.loads(urllib.request.urlopen(req).read().decode())

    org3 = _get_perms(ORG_TEST3_MONGO_ID)
    org4 = _get_perms(ORG_TEST4_MONGO_ID)
    check("Test_3's 'shared-name-role' keeps its own permissions", org3["permissions"] == ["api:read"], org3)
    check("test_4's 'shared-name-role' keeps its own DIFFERENT permissions (no cross-org leak)",
          org4["permissions"] == ["tests:write"], org4)

    test3_roles = {r["name"] for r in _list_roles(admin_token, ORG_TEST3_MONGO_ID)}
    test4_roles = {r["name"] for r in _list_roles(admin_token, ORG_TEST4_MONGO_ID)}
    check("Test_3's role list doesn't leak org-specific roles some other org made up",
          "shared-name-role" in test3_roles and "shared-name-role" in test4_roles)

    _set_role_permissions(admin_token, ORG_TEST3_MONGO_ID, "shared-name-role", [])
    _set_role_permissions(admin_token, ORG_TEST4_MONGO_ID, "shared-name-role", [])


# ── Scenario 11: a custom role scoped to ONE project only applies there ─────
def test_project_scoped_custom_role(admin_token):
    print("\n=== 11. Custom role assigned to a member for ONE project only applies while that project is active ===")
    _ensure_role(admin_token, ORG_TEST3_MONGO_ID, "test-project-scoped-role")
    _set_role_permissions(admin_token, ORG_TEST3_MONGO_ID, "test-project-scoped-role", ["migration:read"])

    member_id = _member_id_of(admin_token, PROJECT_MEMBER_USER[0])  # project-member on p5, no org-wide role
    status, _ = _put(
        admin_token,
        f"{API_URL}/api/super-admin/orgs/{ORG_TEST3_MONGO_ID}/users/{member_id}/projects/{PROJECT_P5_ID}/custom-roles",
        {"customRoles": ["test-project-scoped-role"]},
    )
    check("assign project-scoped custom role -> 204", status == 204, status)

    _, token_p5 = login(*PROJECT_MEMBER_USER, "test-3", "p5")
    s1, perms_p5 = call_api(f"{API_URL}/api/me/permissions", token_p5["access_token"])
    check("permissions include the project-scoped role's grant while active in p5",
          s1 == 200 and "migration:read" in perms_p5, (s1, perms_p5))

    # cleanup
    _put(admin_token, f"{API_URL}/api/super-admin/orgs/{ORG_TEST3_MONGO_ID}/users/{member_id}/projects/{PROJECT_P5_ID}/custom-roles",
         {"customRoles": []})
    _set_role_permissions(admin_token, ORG_TEST3_MONGO_ID, "test-project-scoped-role", [])


# ── HTTP helpers for the SuperAdmin API ─────────────────────────────────────
def _put(token, url, body):
    return _send("PUT", token, url, body)


def _patch(token, url, body):
    return _send("PATCH", token, url, body)


def _post(token, url, body):
    return _send("POST", token, url, body)


def _send(method, token, url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {token}")
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        return resp.getcode(), resp.read().decode(errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")


def _ensure_role(admin_token, org_id, name):
    return _post(admin_token, f"{API_URL}/api/super-admin/orgs/{org_id}/roles", {"name": name, "description": "test fixture"})


def _set_role_permissions(admin_token, org_id, role, permissions):
    return _put(admin_token, f"{API_URL}/api/super-admin/orgs/{org_id}/roles/{role}/permissions", {"permissions": permissions})


def _list_roles(admin_token, org_id):
    req = urllib.request.Request(f"{API_URL}/api/super-admin/orgs/{org_id}/roles")
    req.add_header("Authorization", f"Bearer {admin_token}")
    return json.loads(urllib.request.urlopen(req).read().decode())


def _member_id_of(admin_token, email):
    # Look up via KC (admin-cli) since email -> KC user id isn't exposed by the .NET API directly.
    kc_token = get_admin_token()
    req = urllib.request.Request(f"{KC_URL}/admin/realms/{REALM}/users?email={urllib.parse.quote(email)}")
    req.add_header("Authorization", f"Bearer {kc_token}")
    users = json.loads(urllib.request.urlopen(req).read().decode())
    return users[0]["id"]


def setup_superadmin_password():
    """One-time: set a known password on the demo super-admin account (alice)."""
    kc_token = get_admin_token()
    req = urllib.request.Request(f"{KC_URL}/admin/realms/{REALM}/users?username=alice")
    req.add_header("Authorization", f"Bearer {kc_token}")
    users = json.loads(urllib.request.urlopen(req).read().decode())
    alice_id = users[0]["id"]
    req = urllib.request.Request(
        f"{KC_URL}/admin/realms/{REALM}/users/{alice_id}/reset-password",
        data=json.dumps({"type": "password", "value": SUPERADMIN_PASSWORD, "temporary": False}).encode(),
        method="PUT",
    )
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {kc_token}")
    urllib.request.urlopen(req)
    print(f"alice password set to {SUPERADMIN_PASSWORD!r}")


def reset_dual_role_fixture(admin_token):
    """Scenario 3 needs DUAL_ROLE_USER back in its starting shape (project-admin
    on p5 + project-member on p3) — scenario 9 promotes them to org-admin, so a
    prior run (or manual testing) can leave them promoted. Reset unconditionally
    before each run so the suite is repeatable from any starting state."""
    member_id = _member_id_of(admin_token, DUAL_ROLE_USER[0])
    _patch(admin_token, f"{API_URL}/api/super-admin/orgs/{ORG_TEST3_MONGO_ID}/users/{member_id}", {
        "orgRole": "",
        "projectAccess": [
            {"projectId": PROJECT_P5_ID, "role": "project-admin"},
            {"projectId": PROJECT_P3_ID, "role": "project-member"},
        ],
    })


def reset_project_member_fixture(admin_token):
    """Scenarios 7/8/11 each assign a custom role to PROJECT_MEMBER_USER and clean
    up on success — reset defensively in case a prior run failed partway through."""
    member_id = _member_id_of(admin_token, PROJECT_MEMBER_USER[0])
    _put(admin_token, f"{API_URL}/api/super-admin/orgs/{ORG_TEST3_MONGO_ID}/users/{member_id}/custom-roles",
         {"customRoles": []})
    _put(admin_token, f"{API_URL}/api/super-admin/orgs/{ORG_TEST3_MONGO_ID}/users/{member_id}/projects/{PROJECT_P5_ID}/custom-roles",
         {"customRoles": []})


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--setup", action="store_true", help="Set alice's password before running (one-time)")
    args = p.parse_args()

    if args.setup:
        setup_superadmin_password()
        return 0

    admin_token = login_superadmin(SUPERADMIN_USERNAME, SUPERADMIN_PASSWORD)["access_token"]
    reset_dual_role_fixture(admin_token)
    reset_project_member_fixture(admin_token)

    test_fresh_login_claims()
    test_org_admin_switch_org_and_project()
    test_same_user_role_changes_with_project_switch()
    test_unauthorized_switch_denied()

    test_custom_role_permission_format(admin_token)
    test_custom_role_is_kc_safe(admin_token)
    test_live_permission_edit_propagates(admin_token)
    test_promote_to_org_admin(admin_token)
    test_roles_are_org_scoped(admin_token)
    test_project_scoped_custom_role(admin_token)

    print("\n" + "=" * 60)
    passed = sum(1 for s, _, _ in _results if s == PASS)
    failed = sum(1 for s, _, _ in _results if s == FAIL)
    print(f"RESULTS: {passed} passed, {failed} failed, {len(_results)} total")
    if failed:
        print("\nFailures:")
        for status, name, detail in _results:
            if status == FAIL:
                print(f"  - {name}: {detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
