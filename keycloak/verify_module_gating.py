#!/usr/bin/env python3
"""
Live, scripted proof that org module entitlement gates API access BEFORE the
caller's own custom-role permission — a custom role granting tests:write is
irrelevant if the org isn't entitled to test-factory at all.

Uses real HTTP calls against the real .NET API + Keycloak, no mocks. Org
Test_3 (4635a725-3035-45cf-a9bc-ef7337760d96) currently lacks "test-factory"
(confirmed live via GET .../entitlements before this script runs) — this
script proves that gap actually blocks access, not just that the flag exists.

Usage: python verify_module_gating.py --api-url http://localhost:5000
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

from verify_login_flow import Flow, decode_jwt
from test_permission_scenarios import login_superadmin

KC_URL = "https://keycloak.inb.seliselocal.com"
KC_ADMIN_URL = "http://172.16.2.42:8080"
REALM = "autom-realm"
CLIENT_ID = "autom-app"
REDIRECT_URI = "https://automation.inb.seliselocal.com:5173/"

# Set KC_SUPERADMIN_USERNAME/KC_SUPERADMIN_PASSWORD before running.
SUPERADMIN_USERNAME = os.environ.get("KC_SUPERADMIN_USERNAME", "alice")
SUPERADMIN_PASSWORD = os.environ["KC_SUPERADMIN_PASSWORD"]

ORG_ID = "4635a725-3035-45cf-a9bc-ef7337760d96"  # Test_3
PROJECT_ID = "8bd7b0e6-399a-434c-bf1b-02178453c233"  # p3
ORG_ALIAS = "test-3"

TEST_EMAIL = "module-gating-verify@example.com"
TEST_NAME = "Module Gating Verify"
TEST_PASSWORD = "ModuleGate#2026"
ROLE_NAME = "module-gating-test-role"

PASS, FAIL = "PASS", "FAIL"
_results = []


def check(name, condition, detail=""):
    status = PASS if condition else FAIL
    _results.append((status, name, detail))
    print(f"[{status}] {name}" + (f" — {detail}" if detail and status == FAIL else ""))
    return condition


def kc_admin_request(method, path, token, body=None):
    req = urllib.request.Request(
        f"{KC_ADMIN_URL}{path}", method=method,
        data=json.dumps(body).encode() if body is not None else None,
    )
    req.add_header("Authorization", f"Bearer {token}")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        raw = resp.read()
        return resp.getcode(), (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")


def api(method, url, token, body=None):
    req = urllib.request.Request(
        url, method=method,
        data=json.dumps(body).encode() if body is not None else None,
    )
    req.add_header("Authorization", f"Bearer {token}")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        raw = resp.read()
        return resp.getcode(), (json.loads(raw) if raw else raw.decode(errors="replace"))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--api-url", default="http://localhost:5000")
    args = p.parse_args()

    sa_token = login_superadmin(SUPERADMIN_USERNAME, SUPERADMIN_PASSWORD)["access_token"]

    print("0) Confirming Test_3's current entitlements (baseline, will be restored at the end)...")
    code, ent = api("GET", f"{args.api_url}/api/super-admin/orgs/{ORG_ID}/entitlements", sa_token)
    check("read baseline entitlements", code == 200, f"status={code} body={ent}")
    baseline_modules = set(ent.get("modules", [])) if isinstance(ent, dict) else set()
    has_test_factory_initially = "test-factory" in baseline_modules
    print(f"   baseline modules: {sorted(baseline_modules)} (test-factory present: {has_test_factory_initially})")

    try:
        print(f"\n1) Cleaning up any leftover test user/role from a prior run...")
        code, existing = kc_admin_request("GET", f"/admin/realms/{REALM}/users?username={TEST_EMAIL}&exact=true", sa_token)
        if code == 200 and existing:
            kc_admin_request("DELETE", f"/admin/realms/{REALM}/users/{existing[0]['id']}", sa_token)
            print(f"   deleted leftover KC user {existing[0]['id']}")

        print(f"\n2) Inviting {TEST_EMAIL} as a plain project-member of Test_3/p3...")
        invite_body = {"name": TEST_NAME, "email": TEST_EMAIL, "orgRole": "",
                       "projectAccess": [{"projectId": PROJECT_ID, "role": "project-member"}]}
        code, resp = api("POST", f"{args.api_url}/api/super-admin/orgs/{ORG_ID}/users/invite", sa_token, invite_body)
        check("invite succeeded", code in (200, 201), f"status={code} body={resp}")

        code, kcuser = kc_admin_request("GET", f"/admin/realms/{REALM}/users?username={TEST_EMAIL}&exact=true", sa_token)
        user_id = kcuser[0]["id"]

        print("   administratively completing onboarding (password set, required actions cleared)...")
        kc_admin_request("PUT", f"/admin/realms/{REALM}/users/{user_id}/reset-password", sa_token,
                          {"type": "password", "value": TEST_PASSWORD, "temporary": False})
        kc_admin_request("PUT", f"/admin/realms/{REALM}/users/{user_id}", sa_token,
                          {"requiredActions": [], "emailVerified": True})

        print(f"\n3) Creating custom role '{ROLE_NAME}' with tests:read/tests:write in Test_3...")
        code, resp = api("POST", f"{args.api_url}/api/super-admin/orgs/{ORG_ID}/roles", sa_token,
                          {"name": ROLE_NAME, "description": "verify_module_gating.py test role"})
        check("role created (or already existed)", code in (200, 201, 204, 409), f"status={code} body={resp}")

        code, resp = api("PUT", f"{args.api_url}/api/super-admin/orgs/{ORG_ID}/roles/{ROLE_NAME}/permissions",
                          sa_token, {"permissions": ["tests:read", "tests:write"]})
        check("role permissions set to tests:read/tests:write", code in (200, 204), f"status={code} body={resp}")

        print(f"\n4) Assigning '{ROLE_NAME}' to the member as a PROJECT-scoped custom role on p3...")
        code, resp = api(
            "PUT",
            f"{args.api_url}/api/super-admin/orgs/{ORG_ID}/users/{user_id}/projects/{PROJECT_ID}/custom-roles",
            sa_token, {"customRoles": [ROLE_NAME]})
        check("custom role assigned", code in (200, 204), f"status={code} body={resp}")

        print(f"\n5) Logging in as the member via the real org/project browser flow...")
        flow = Flow(KC_URL, REALM, CLIENT_ID, REDIRECT_URI)
        token = flow.login(TEST_EMAIL, TEST_PASSWORD, ORG_ALIAS, "p3")
        claims = decode_jwt(token["access_token"])
        check("login succeeded, project_id claim present", claims.get("project_id") == PROJECT_ID,
              f"project_id={claims.get('project_id')}")

        print("\n6) Confirming /api/me/permissions resolves tests:write for this member (permission layer alone)...")
        code, perms = api("GET", f"{args.api_url}/api/me/permissions", token["access_token"])
        check("tests:write resolved by /api/me/permissions", code == 200 and "tests:write" in (perms or []),
              f"status={code} body={perms}")

        test_case_body = {
            "name": "module-gating-test-case", "testSuiteId": "nonexistent-suite-id",
            "components": [], "actions": [], "mobileActions": [],
            "testCaseDescription": None, "isActive": True, "automationType": "Web",
            "classificationId": None, "classificationName": None,
        }

        if has_test_factory_initially:
            print("\n   NOTE: Test_3 ALREADY had test-factory entitled before this run — temporarily removing it "
                  "to prove the 'org lacks module -> blocked' direction, then restoring it.")
            api("PATCH", f"{args.api_url}/api/super-admin/orgs/{ORG_ID}/entitlements", sa_token,
                {"moduleId": "test-factory", "enabled": False})

        print("\n7) Org does NOT have test-factory entitled — POST /test-cases with a full tests:write "
              "permission should be BLOCKED by the module gate, before permission is even considered...")
        code, resp = api("POST", f"{args.api_url}/api/projects/{PROJECT_ID}/test-cases",
                          token["access_token"], test_case_body)
        check("blocked (403) despite having tests:write — module gate wins", code == 403,
              f"status={code} body={resp}")

        print("\n8) Enabling test-factory for Test_3...")
        code, resp = api("PATCH", f"{args.api_url}/api/super-admin/orgs/{ORG_ID}/entitlements", sa_token,
                          {"moduleId": "test-factory", "enabled": True})
        check("entitlement PATCH succeeded", code in (200, 204), f"status={code} body={resp}")

        print("\n9) Same call again — module now entitled AND user has tests:write — should NOT be blocked "
              "by authorization (403) anymore (may still 400 on the dummy testSuiteId, that's fine)...")
        code, resp = api("POST", f"{args.api_url}/api/projects/{PROJECT_ID}/test-cases",
                          token["access_token"], test_case_body)
        check("no longer 403 once both module entitlement and permission are satisfied", code != 403,
              f"status={code} body={resp}")

        print("\n10) Removing the custom-role assignment (module entitled, but NO permission this time) — "
              "should be blocked again, proving the permission layer independently still applies...")
        api("PUT", f"{args.api_url}/api/super-admin/orgs/{ORG_ID}/users/{user_id}/projects/{PROJECT_ID}/custom-roles",
            sa_token, {"customRoles": []})
        code, perms2 = api("GET", f"{args.api_url}/api/me/permissions", token["access_token"])
        check("tests:write no longer resolved after removing the custom role", "tests:write" not in (perms2 or []),
              f"body={perms2}")
        code, resp = api("POST", f"{args.api_url}/api/projects/{PROJECT_ID}/test-cases",
                          token["access_token"], test_case_body)
        check("blocked (403) again — module entitled but no permission", code == 403, f"status={code} body={resp}")

    finally:
        print("\nCleanup: restoring Test_3's entitlements to the original baseline, removing test user/role...")
        if not has_test_factory_initially:
            api("PATCH", f"{args.api_url}/api/super-admin/orgs/{ORG_ID}/entitlements", sa_token,
                {"moduleId": "test-factory", "enabled": False})
        else:
            api("PATCH", f"{args.api_url}/api/super-admin/orgs/{ORG_ID}/entitlements", sa_token,
                {"moduleId": "test-factory", "enabled": True})
        code, ent_final = api("GET", f"{args.api_url}/api/super-admin/orgs/{ORG_ID}/entitlements", sa_token)
        check("entitlements restored to baseline", set(ent_final.get("modules", [])) == baseline_modules,
              f"final={ent_final}")

        code, kcuser = kc_admin_request("GET", f"/admin/realms/{REALM}/users?username={TEST_EMAIL}&exact=true", sa_token)
        if code == 200 and kcuser:
            kc_admin_request("DELETE", f"/admin/realms/{REALM}/users/{kcuser[0]['id']}", sa_token)
            print(f"   deleted test user {kcuser[0]['id']}")

    print("\n=== Summary ===")
    for status, name, detail in _results:
        print(f"[{status}] {name}")
    failed = [r for r in _results if r[0] == FAIL]
    print(f"\n{len(_results) - len(failed)}/{len(_results)} checks passed.")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
