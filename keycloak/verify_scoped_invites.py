#!/usr/bin/env python3
"""
End-to-end verification for the 2026-09-15 org-admin/project-admin scoped
invite feature (POST /api/org-admin/{orgName}/members/invite and
POST /api/project-admin/{orgName}/{projectName}/members/invite).

Real logins, real HTTP calls to the real .NET API and Keycloak, positive AND
negative cases (per this project's verification-rigor convention: a fix that
touches an authorization boundary must be checked from the denied side too,
not just the allowed side).

Usage:
  python verify_scoped_invites.py --api-url http://localhost:5000
"""

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

from verify_login_flow import Flow, call_api
from test_permission_scenarios import login, get_admin_token, ORG_ADMIN_USER, PROJECT_ADMIN_USER, PROJECT_MEMBER_USER

KC_ADMIN_URL = "http://172.16.2.42:8080"
REALM = "autom-realm"

ORG_NAME = "Test_3"
FOREIGN_ORG_NAME = "test_4"
PROJECT_P5 = "p5"
PROJECT_P3 = "p3"
PROJECT_P4_ID = "fbc583df-f4be-445c-9c18-568a42519a84"  # belongs to test_4, not Test_3

PASS, FAIL = "PASS", "FAIL"
_results = []
_cleanup_emails = []


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

    def unique_email(tag):
        email = f"verify-scoped-{tag}@example.com"
        _cleanup_emails.append(email)
        existing = find_kc_user(admin_token, email)
        if existing:
            kc_admin_request("DELETE", f"/admin/realms/{REALM}/users/{existing['id']}", admin_token)
        return email

    print("1) Logging in as org-admin (11-09-2026@yopmail.com, org-admin in Test_3) ...")
    _, org_admin_token = login(*ORG_ADMIN_USER, "test-3", "p3")
    check("org-admin login succeeded", bool(org_admin_token.get("access_token")))

    print("\n2) POSITIVE: org-admin invites a NEW user as project-admin on p5 (a project they administer) ...")
    email_a = unique_email("org-admin-invite-projectadmin")
    status, resp = api_call(
        "POST", f"{args.api_url}/api/org-admin/{ORG_NAME}/members/invite",
        org_admin_token["access_token"],
        {"name": "Scoped Invite A", "email": email_a, "orgRole": "",
         "projectAccess": [{"projectId": "17e66a0a-7564-4034-8e48-866e3eb3d387", "role": "project-admin"}]})
    check("org-admin can invite a project-admin on their own org's project", status in (200, 201), f"status={status} body={resp}")

    print("\n3) POSITIVE: org-admin invites a NEW user as org-admin (org-wide) ...")
    email_b = unique_email("org-admin-invite-orgadmin")
    status, resp = api_call(
        "POST", f"{args.api_url}/api/org-admin/{ORG_NAME}/members/invite",
        org_admin_token["access_token"],
        {"name": "Scoped Invite B", "email": email_b, "orgRole": "org-admin", "projectAccess": []})
    check("org-admin can invite another org-admin", status in (200, 201), f"status={status} body={resp}")

    print("\n4) NEGATIVE: org-admin tries to grant access to a project from a DIFFERENT org (p4, in test_4) ...")
    email_c = unique_email("org-admin-invite-foreign-project")
    status, resp = api_call(
        "POST", f"{args.api_url}/api/org-admin/{ORG_NAME}/members/invite",
        org_admin_token["access_token"],
        {"name": "Scoped Invite C", "email": email_c, "orgRole": "",
         "projectAccess": [{"projectId": PROJECT_P4_ID, "role": "project-member"}]})
    check("org-admin CANNOT grant access to a foreign org's project", status not in (200, 201), f"status={status} body={resp}")
    check("foreign-project user was NOT created in Keycloak", find_kc_user(admin_token, email_c) is None)

    print("\n5) Logging in as project-admin (verify-project-admin2@example.com, project-admin on p5) ...")
    _, proj_admin_token = login(*PROJECT_ADMIN_USER, "test-3", "p5")
    check("project-admin login succeeded", bool(proj_admin_token.get("access_token")))

    print("\n6) POSITIVE: project-admin invites a NEW user as a plain member of p5 (their own project) ...")
    email_d = unique_email("project-admin-invite-member")
    status, resp = api_call(
        "POST", f"{args.api_url}/api/project-admin/{ORG_NAME}/{PROJECT_P5}/members/invite",
        proj_admin_token["access_token"],
        {"name": "Scoped Invite D", "email": email_d})
    check("project-admin can invite a plain member into their own project", status in (200, 201), f"status={status} body={resp}")
    check("invited member's orgRole is empty (no admin access granted)", resp.get("orgRole") == "" if isinstance(resp, dict) else False,
          f"got {resp!r}")

    print("\n7) NEGATIVE: project-admin (only admin on p5) tries to invite into p3, where they have no admin rights ...")
    email_e = unique_email("project-admin-invite-wrong-project")
    status, resp = api_call(
        "POST", f"{args.api_url}/api/project-admin/{ORG_NAME}/{PROJECT_P3}/members/invite",
        proj_admin_token["access_token"],
        {"name": "Scoped Invite E", "email": email_e})
    check("project-admin CANNOT invite into a project they don't administer", status == 403, f"status={status} body={resp}")
    check("wrong-project user was NOT created in Keycloak", find_kc_user(admin_token, email_e) is None)

    print("\n8) NEGATIVE: a plain project-member (no admin rights anywhere) tries the org-admin invite endpoint ...")
    _, member_token = login(*PROJECT_MEMBER_USER, "test-3", "p5")
    email_f = unique_email("member-invite-orgscope")
    status, resp = api_call(
        "POST", f"{args.api_url}/api/org-admin/{ORG_NAME}/members/invite",
        member_token["access_token"],
        {"name": "Scoped Invite F", "email": email_f, "orgRole": "org-admin", "projectAccess": []})
    check("plain member CANNOT reach the org-admin invite endpoint", status == 403, f"status={status} body={resp}")
    check("unauthorized-invite user was NOT created in Keycloak", find_kc_user(admin_token, email_f) is None)

    # Cleanup
    for email in _cleanup_emails:
        u = find_kc_user(admin_token, email)
        if u:
            kc_admin_request("DELETE", f"/admin/realms/{REALM}/users/{u['id']}", admin_token)
    print(f"\n(cleaned up {len(_cleanup_emails)} test users)")

    print("\n=== Summary ===")
    failed = [r for r in _results if r[0] == FAIL]
    for status, name, detail in _results:
        print(f"[{status}] {name}")
    print(f"\n{len(_results) - len(failed)}/{len(_results)} checks passed.")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
