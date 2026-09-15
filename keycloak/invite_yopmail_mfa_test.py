#!/usr/bin/env python3
"""
Invites a real yopmail.com test user via the real .NET API invite endpoint,
so it can be walked live in the browser (per standing project instruction:
invite via yopmail and self-verify, don't just assert from server-side
dispatch). This does NOT complete the flow itself -- that's done by hand
via claude-in-chrome against the real emailed link, to prove the new
autom-optional-totp Skip button genuinely works end-to-end.
"""
import json
import os
import sys
import urllib.error
import urllib.request

from test_permission_scenarios import login_superadmin

KC_ADMIN_URL = "http://172.16.2.42:8080"
REALM = "autom-realm"
# Set KC_SUPERADMIN_USERNAME/KC_SUPERADMIN_PASSWORD before running.
SUPERADMIN_USERNAME = os.environ.get("KC_SUPERADMIN_USERNAME", "alice")
SUPERADMIN_PASSWORD = os.environ["KC_SUPERADMIN_PASSWORD"]

API_URL = "http://localhost:5000"
ORG_ID = "4635a725-3035-45cf-a9bc-ef7337760d96"   # Test_3
PROJECT_ID = "8bd7b0e6-399a-434c-bf1b-02178453c233"  # p3

EMAIL = sys.argv[1] if len(sys.argv) > 1 else "15-09-2026-mfa-skip-test@yopmail.com"
NAME = "MFA Skip Test"


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


def api_post(url, access_token, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST")
    req.add_header("Authorization", f"Bearer {access_token}")
    req.add_header("Content-Type", "application/json")
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        return resp.getcode(), json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")


def main():
    admin_token = login_superadmin(SUPERADMIN_USERNAME, SUPERADMIN_PASSWORD)["access_token"]

    code, existing = kc_admin_request(
        "GET", f"/admin/realms/{REALM}/users?username={urllib.parse.quote(EMAIL)}&exact=true"
        if False else f"/admin/realms/{REALM}/users?username={EMAIL}&exact=true", admin_token,
    )
    if code == 200 and existing:
        kc_admin_request("DELETE", f"/admin/realms/{REALM}/users/{existing[0]['id']}", admin_token)
        print(f"(cleaned up leftover KC user for {EMAIL})")

    sa_token = login_superadmin(SUPERADMIN_USERNAME, SUPERADMIN_PASSWORD)["access_token"]

    body = {
        "name": NAME,
        "email": EMAIL,
        "orgRole": "",
        "projectAccess": [{"projectId": PROJECT_ID, "role": "project-member"}],
    }
    code, resp = api_post(f"{API_URL}/api/super-admin/orgs/{ORG_ID}/users/invite", sa_token, body)
    print(f"Invite call -> {code}")
    print(json.dumps(resp, indent=2) if isinstance(resp, dict) else resp)

    code, user = kc_admin_request("GET", f"/admin/realms/{REALM}/users?username={EMAIL}&exact=true", admin_token)
    if code == 200 and user:
        print("\nKC user requiredActions:", user[0].get("requiredActions"))
        print(f"KC user id: {user[0]['id']}")
    else:
        print("Could not find KC user after invite:", code, user)


if __name__ == "__main__":
    import urllib.parse
    main()
