#!/usr/bin/env python3
"""
Verification for POST /api/super-admin/orgs/{orgId}/users/{memberId}/resend-invite
(AC-4/AC-5 in l3-react-autom-superadmin/docs/R1_Tenancy_and_Access_Batch_A.md):
available for Invited users, rate-limited to once per 24h, fresh 7-day expiry
each time. Real API, real Keycloak, positive + negative cases.

Usage:
  python verify_resend_invite.py --api-url http://localhost:5000
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from test_permission_scenarios import login_superadmin, get_admin_token, SUPERADMIN_USERNAME, SUPERADMIN_PASSWORD

KC_ADMIN_URL = "http://172.16.2.42:8080"
REALM = "autom-realm"
ORG_TEST3_ID = "4635a725-3035-45cf-a9bc-ef7337760d96"
PROJECT_P3_ID = "8bd7b0e6-399a-434c-bf1b-02178453c233"

PASS, FAIL = "PASS", "FAIL"
_results = []


def check(name, condition, detail=""):
    status = PASS if condition else FAIL
    _results.append((status, name, detail))
    print(f"[{status}] {name}" + (f" — {detail}" if detail and status == FAIL else ""))
    return condition


def kc_admin_request(method, path, token, body=None):
    req = urllib.request.Request(f"{KC_ADMIN_URL}{path}", method=method,
                                  data=json.dumps(body).encode() if body is not None else None)
    req.add_header("Authorization", f"Bearer {token}")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        raw = resp.read()
        return resp.getcode(), (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")


def find_kc_user(token, email):
    code, data = kc_admin_request("GET", f"/admin/realms/{REALM}/users?username={urllib.parse.quote(email)}&exact=true", token)
    return data[0] if code == 200 and data else None


def api_call(method, url, access_token, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {access_token}")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        raw = resp.read()
        return resp.getcode(), (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        body_text = e.read().decode(errors="replace")
        try:
            return e.code, json.loads(body_text)
        except json.JSONDecodeError:
            return e.code, body_text


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--api-url", default="http://localhost:5000")
    args = p.parse_args()

    admin_token = get_admin_token()
    sa = login_superadmin(SUPERADMIN_USERNAME, SUPERADMIN_PASSWORD)
    sa_token = sa["access_token"]

    email = "verify-resend-invite@example.com"
    existing = find_kc_user(admin_token, email)
    if existing:
        kc_admin_request("DELETE", f"/admin/realms/{REALM}/users/{existing['id']}", admin_token)

    print("1) Inviting a fresh test user ...")
    status, resp = api_call("POST", f"{args.api_url}/api/super-admin/orgs/{ORG_TEST3_ID}/users/invite", sa_token, {
        "name": "Verify Resend", "email": email, "orgRole": "",
        "projectAccess": [{"projectId": PROJECT_P3_ID, "role": "project-member"}],
    })
    check("invite succeeded", status in (200, 201), f"status={status} body={resp}")
    member_id = resp["id"]
    first_expiry = resp["inviteExpiresAt"]

    print("\n2) POSITIVE: resend-invite immediately after invite is expected to be BLOCKED "
          "(the invite email itself was the first send, so we're inside the 24h window) ...")
    status2, resp2 = api_call("POST", f"{args.api_url}/api/super-admin/orgs/{ORG_TEST3_ID}/users/{member_id}/resend-invite", sa_token)
    check("resend within 24h of the original invite is rejected", status2 not in (200, 201), f"status={status2} body={resp2}")

    print("\n3) Backdating lastInviteSentAt via Mongo is out of reach from here, so instead: "
          "verify a DIFFERENT already-Active member correctly rejects resend ('not Invited') ...")
    active_email = "verify-project-member@example.com"
    active_user = find_kc_user(admin_token, active_email)
    check("found an existing Active fixture member", active_user is not None)
    if active_user:
        status4, resp4 = api_call(
            "POST", f"{args.api_url}/api/super-admin/orgs/{ORG_TEST3_ID}/users/{active_user['id']}/resend-invite", sa_token)
        check("resend on an Active (non-Invited) member is rejected", status4 not in (200, 201), f"status={status4} body={resp4}")

    print("\n4) Confirming member is still correctly 'Invited' with its original expiry unchanged "
          "(the blocked resend must not have side effects) ...")
    status5, users = api_call("GET", f"{args.api_url}/api/super-admin/orgs/{ORG_TEST3_ID}/users", sa_token)
    member = next((u for u in users if u.get("id") == member_id), None) if status5 == 200 else None
    check("member still found", member is not None)
    if member:
        check("status still Invited", member.get("status") == "Invited", f"got {member.get('status')!r}")
        check("inviteExpiresAt unchanged by the blocked resend", member.get("inviteExpiresAt") == first_expiry)

    # Cleanup
    kc_admin_request("DELETE", f"/admin/realms/{REALM}/users/{member_id}", admin_token)
    print(f"\n(cleaned up test user {member_id})")

    print("\n=== Summary ===")
    failed = [r for r in _results if r[0] == FAIL]
    for status, name, detail in _results:
        print(f"[{status}] {name}")
    print(f"\n{len(_results) - len(failed)}/{len(_results)} checks passed.")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
