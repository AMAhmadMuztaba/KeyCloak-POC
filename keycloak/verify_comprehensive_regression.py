#!/usr/bin/env python3
"""
Comprehensive regression pass added 2026-09-21, after the login-collision +
onboarding-flow fixes shipped this session. Two parts:

1. Re-runs the reusable scenarios from test_permission_scenarios.py that don't
   depend on the pre-existing ORG_ADMIN_USER fixture (whose current password
   isn't known here) -- switching, custom roles + permissions, permission
   propagation, org-scoping, project-scoped roles. These already existed;
   this just gives a way to run them without that one external dependency.

2. New scenarios, using throwaway users this script creates and deletes:
   - Multi-project picker: a user in ONE org with TWO projects must still see
     the project picker (the "auto-select if exactly one" fix must not fire
     when there's a real choice).
   - Multi-org picker: a user in TWO orgs must see the org picker list both,
     and each org's own project picker must show only that org's projects.
   - Org switching: the real switch-project endpoint moving between two orgs
     this script controls (mirrors test_permission_scenarios.py's scenario 2,
     without needing that external fixture).
   - Two simultaneous portal sessions: a plain user (business, autom-app) and
     a super-admin (autom-superadmin) logged in via two independent Flow/
     cookie-jar instances at once, each portal's API calls checked
     independently -- proves no session bleed between the two clients.

Usage:
  python verify_comprehensive_regression.py [--api-url http://localhost:5000]

Requires KC_MASTER_ADMIN_USERNAME / KC_MASTER_ADMIN_PASSWORD and
KC_SUPERADMIN_PASSWORD in the environment.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from verify_login_flow import Flow, decode_jwt, call_api
import test_permission_scenarios as tps

PASS, FAIL = "PASS", "FAIL"
_results = []


def check(name, condition, detail=""):
    status = PASS if condition else FAIL
    _results.append((status, name, detail))
    print(f"[{status}] {name}" + (f" — {detail}" if detail and status == FAIL else ""))
    return condition


# ── Part 1: re-run the fixture-independent existing scenarios ──────────────
def run_existing_reusable_scenarios(admin_token):
    print("\n" + "=" * 60)
    print("PART 1: existing scenarios that don't need the ORG_ADMIN_USER fixture")
    print("=" * 60)
    tps.reset_dual_role_fixture(admin_token)
    tps.reset_project_member_fixture(admin_token)

    tps.test_same_user_role_changes_with_project_switch()
    tps.test_unauthorized_switch_denied()
    tps.test_custom_role_permission_format(admin_token)
    tps.test_custom_role_is_kc_safe(admin_token)
    tps.test_live_permission_edit_propagates(admin_token)
    tps.test_promote_to_org_admin(admin_token)
    tps.test_roles_are_org_scoped(admin_token)
    tps.test_project_scoped_custom_role(admin_token)

    _results.extend(tps._results)
    tps._results.clear()


# ── Admin-API helpers for throwaway multi-org/multi-project users ──────────
def admin_request(method, path, token, body=None):
    req = urllib.request.Request(
        f"{tps.KC_ADMIN_URL if hasattr(tps, 'KC_ADMIN_URL') else 'http://172.16.2.42:8080'}{path}",
        method=method, data=json.dumps(body).encode() if body is not None else None,
    )
    req.add_header("Authorization", f"Bearer {token}")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        raw = resp.read()
        return resp.getcode(), (json.loads(raw) if raw else None), resp.headers.get("Location")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace"), None


def get_admin_token():
    return tps.get_admin_token()


def find_group_id(token, name, parent_id=None):
    base = "/admin/realms/autom-realm/groups"
    if parent_id is None:
        code, data, _ = admin_request("GET", f"{base}?search={urllib.parse.quote(name)}", token)
        return next((g["id"] for g in (data or []) if g["name"] == name), None)
    code, data, _ = admin_request("GET", f"{base}/{parent_id}/children", token)
    return next((g["id"] for g in (data or []) if g["name"] == name), None)


def find_native_org(token, alias):
    code, orgs, _ = admin_request("GET", "/admin/realms/autom-realm/organizations?briefRepresentation=false", token)
    return next((o for o in (orgs or []) if o.get("alias") == alias), None)


def delete_user_if_exists(token, email):
    code, users, _ = admin_request("GET", f"/admin/realms/autom-realm/users?username={urllib.parse.quote(email)}&exact=true", token)
    if users:
        admin_request("DELETE", f"/admin/realms/autom-realm/users/{users[0]['id']}", token)


def create_throwaway_user(token, email, password, memberships):
    """memberships: list of (org_alias, org_group_name, project_name_or_None) --
    joins the plain KC group AND the native org for each, so both the group-
    based project picker and the org-aware login flow both work."""
    delete_user_if_exists(token, email)
    code, body, location = admin_request("POST", "/admin/realms/autom-realm/users", token, {
        "username": email, "email": email, "enabled": True, "emailVerified": True,
        "firstName": "Regression", "lastName": "Check",
        "credentials": [{"type": "password", "value": password, "temporary": False}],
    })
    if code != 201:
        raise RuntimeError(f"create user failed: {code} {body}")
    user_id = location.rstrip("/").rsplit("/", 1)[-1]

    for org_alias, org_group_name, project_name in memberships:
        org_group_id = find_group_id(token, org_group_name)
        if not org_group_id:
            raise RuntimeError(f"org group {org_group_name!r} not found")
        target_group_id = org_group_id
        if project_name:
            target_group_id = find_group_id(token, project_name, parent_id=org_group_id)
            if not target_group_id:
                raise RuntimeError(f"project group {project_name!r} not found under {org_group_name!r}")
        code, _, _ = admin_request("PUT", f"/admin/realms/autom-realm/users/{user_id}/groups/{target_group_id}", token)
        if code != 204:
            raise RuntimeError(f"join group failed: {code}")

        native_org = find_native_org(token, org_alias)
        if not native_org:
            raise RuntimeError(f"native org alias {org_alias!r} not found")
        req = urllib.request.Request(
            f"http://172.16.2.42:8080/admin/realms/autom-realm/organizations/{native_org['id']}/members",
            data=json.dumps(user_id).encode(), method="POST",
        )
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Content-Type", "application/json")
        try:
            urllib.request.urlopen(req, timeout=15)
        except urllib.error.HTTPError as e:
            # Already a member is fine (can happen on a re-run after a partial failure).
            if e.code != 409:
                raise RuntimeError(f"native org join failed: {e.code} {e.read().decode(errors='replace')}")

    return user_id, native_org


# ── Part 2a: multi-project picker ───────────────────────────────────────────
def test_multi_project_picker_shows_both(admin_token):
    print("\n" + "=" * 60)
    print("PART 2a: user with TWO projects in one org sees the project picker (not auto-skipped)")
    print("=" * 60)
    email, password = "verify-multi-project@example.com", "MultiProject#2026"
    create_throwaway_user(admin_token, email, password, [
        ("test-3", "Test_3", "p3"),
        ("test-3", "Test_3", "p5"),
    ])
    try:
        flow = Flow(tps.KC_URL, tps.REALM, "autom-app", tps.REDIRECT_URI)
        auth_params = {
            "client_id": "autom-app", "redirect_uri": flow.redirect_uri, "response_type": "code",
            "response_mode": "fragment", "scope": "openid profile email organization",
            "code_challenge": flow.code_challenge, "code_challenge_method": "S256",
            "state": "x", "nonce": "y",
        }
        auth_url = f"{flow.kc_url}/realms/{flow.realm}/protocol/openid-connect/auth?" + urllib.parse.urlencode(auth_params)
        _, _, html = flow._request("GET", auth_url)
        action = flow._form_action(html)
        code, loc, html = flow._request("POST", action, {"username": email, "password": password, "credentialId": ""})
        if code in (302, 303):
            code, loc, html = flow._request("GET", loc)
        action = flow._form_action(html)
        check("project picker IS shown (not auto-skipped) for a 2-project user",
              action is not None and 'name="project"' in html,
              f"action={action!r}")
        project_values = set(__import__("re").findall(r'name="project" value="([^"]+)"', html))
        check("both projects (p3, p5) appear as options", len(project_values) == 2, project_values)
    finally:
        delete_user_if_exists(admin_token, email)


# ── Part 2b: multi-org picker + org switching ───────────────────────────────
def test_multi_org_picker_and_switch(admin_token):
    print("\n" + "=" * 60)
    print("PART 2b: user in TWO orgs sees the org picker; each org's own project(s) only")
    print("=" * 60)
    email, password = "verify-multi-org@example.com", "MultiOrg#2026"
    user_id, _ = create_throwaway_user(admin_token, email, password, [
        ("test-3", "Test_3", "p3"),
        ("test-muztaba-2", "Test_Muztaba_2", "p2"),
    ])
    try:
        flow = Flow(tps.KC_URL, tps.REALM, "autom-app", tps.REDIRECT_URI)
        auth_params = {
            "client_id": "autom-app", "redirect_uri": flow.redirect_uri, "response_type": "code",
            "response_mode": "fragment", "scope": "openid profile email organization",
            "code_challenge": flow.code_challenge, "code_challenge_method": "S256",
            "state": "x", "nonce": "y",
        }
        auth_url = f"{flow.kc_url}/realms/{flow.realm}/protocol/openid-connect/auth?" + urllib.parse.urlencode(auth_params)
        _, _, html = flow._request("GET", auth_url)
        action = flow._form_action(html)
        code, loc, html = flow._request("POST", action, {"username": email, "password": password, "credentialId": ""})
        if code in (302, 303):
            code, loc, html = flow._request("GET", loc)

        check("org picker IS shown for a 2-org user", 'name="organization"' in html)
        org_values = set(__import__("re").findall(r'name="organization" value="([^"]+)"', html))
        check("both orgs (test-3, test-muztaba-2) appear as options", len(org_values) == 2, org_values)

        # Pick test-3, confirm ONLY p3 (not p2 from test-muztaba-2) shows.
        action = flow._form_action(html)
        code, loc, html = flow._request("POST", action, {"organization": "test-3"})
        # A single-project org auto-skips the project picker entirely (this
        # session's own fix) -- check for an already-completed code redirect
        # before assuming a project-picker form follows.
        final_loc = flow._code_redirect_or_none(code, loc)
        if final_loc is None:
            if code in (302, 303):
                code, loc, html = flow._request("GET", loc)
            if 'name="project"' in html:
                project_values = set(__import__("re").findall(r'name="project" value="([^"]+)"', html))
                check("test-3's picker shows exactly its own project (p3), not test-muztaba-2's",
                      len(project_values) == 1, project_values)
                action = flow._form_action(html)
                code, loc, html = flow._request("POST", action, {"project": list(project_values)[0]})
            # else: single project may have been auto-selected -- also correct.
            final_loc = loc
        hops = 0
        while final_loc and "code=" not in final_loc and hops < 5:
            _, final_loc, _ = flow._request("GET", final_loc)
            hops += 1
        frag = final_loc.split("#", 1)[1]
        auth_code = dict(urllib.parse.parse_qsl(frag)).get("code")
        token_req = urllib.request.Request(
            f"{flow.kc_url}/realms/{flow.realm}/protocol/openid-connect/token",
            data=urllib.parse.urlencode({
                "grant_type": "authorization_code", "client_id": "autom-app",
                "redirect_uri": flow.redirect_uri, "code": auth_code, "code_verifier": flow.code_verifier,
            }).encode(), method="POST",
        )
        token_req.add_header("Content-Type", "application/x-www-form-urlencoded")
        tokens = json.loads(urllib.request.urlopen(token_req).read().decode())
        claims = decode_jwt(tokens["access_token"])
        check("logged-in org alias is test-3", claims.get("organization_alias") == "test-3", claims.get("organization_alias"))

        # Now switch to test-muztaba-2 via the real endpoint.
        org2 = find_native_org(admin_token, "test-muztaba-2")
        org2_group_id = find_group_id(admin_token, "p2", parent_id=find_group_id(admin_token, "Test_Muztaba_2"))
        status, _ = flow.switch_project(tokens["access_token"], org2["id"], org2_group_id)
        check("switch-project to the second org returns 204", status == 204, status)
        token2 = flow.refresh(tokens["refresh_token"])
        after = decode_jwt(token2["access_token"])
        check("organization_alias changed to test-muztaba-2", after.get("organization_alias") == "test-muztaba-2", after.get("organization_alias"))
        check("autom_organization_id changed", claims["autom_organization_id"] != after["autom_organization_id"])
    finally:
        delete_user_if_exists(admin_token, email)


# ── Part 2c: two simultaneous portal sessions, no bleed ─────────────────────
def test_two_simultaneous_portal_sessions(admin_token, api_url):
    print("\n" + "=" * 60)
    print("PART 2c: business user + super-admin logged in simultaneously, independent sessions")
    print("=" * 60)
    biz_email, biz_password = "verify-simul-business@example.com", "SimulBiz#2026"
    sa_email, sa_password = "verify-simul-superadmin@example.com", "SimulSA#2026"
    create_throwaway_user(admin_token, biz_email, biz_password, [("test-3", "Test_3", "p3")])
    sa_user_id, _ = create_throwaway_user(admin_token, sa_email, sa_password, [("test-3", "Test_3", "p3")])
    role_code, role_body, _ = admin_request("GET", "/admin/realms/autom-realm/roles/super-admin", admin_token)
    admin_request("POST", f"/admin/realms/autom-realm/users/{sa_user_id}/role-mappings/realm", admin_token, [role_body])

    try:
        # Independent Flow instances = independent cookie jars = two real, separate browser sessions.
        biz_flow = Flow(tps.KC_URL, tps.REALM, "autom-app", tps.REDIRECT_URI)
        biz_tokens = biz_flow.login(biz_email, biz_password, "test-3", "p3")
        check("business session login succeeded", bool(biz_tokens.get("access_token")))

        sa_flow = Flow(tps.KC_URL, tps.REALM, "autom-superadmin", "http://localhost:5174/")
        auth_params = {
            "client_id": "autom-superadmin", "redirect_uri": sa_flow.redirect_uri, "response_type": "code",
            "response_mode": "fragment", "scope": "openid", "code_challenge": sa_flow.code_challenge,
            "code_challenge_method": "S256", "state": "x", "nonce": "y", "prompt": "login",
        }
        auth_url = f"{sa_flow.kc_url}/realms/{sa_flow.realm}/protocol/openid-connect/auth?" + urllib.parse.urlencode(auth_params)
        _, _, html = sa_flow._request("GET", auth_url)
        action = sa_flow._form_action(html)
        code, loc, html = sa_flow._request("POST", action, {"username": sa_email, "password": sa_password, "credentialId": ""})
        final_loc = loc
        hops = 0
        while final_loc and "code=" not in final_loc and hops < 5:
            _, final_loc, _ = sa_flow._request("GET", final_loc)
            hops += 1
        frag = final_loc.split("#", 1)[1]
        auth_code = dict(urllib.parse.parse_qsl(frag)).get("code")
        token_req = urllib.request.Request(
            f"{sa_flow.kc_url}/realms/{sa_flow.realm}/protocol/openid-connect/token",
            data=urllib.parse.urlencode({
                "grant_type": "authorization_code", "client_id": "autom-superadmin",
                "redirect_uri": sa_flow.redirect_uri, "code": auth_code, "code_verifier": sa_flow.code_verifier,
            }).encode(), method="POST",
        )
        token_req.add_header("Content-Type", "application/x-www-form-urlencoded")
        sa_tokens = json.loads(urllib.request.urlopen(token_req).read().decode())
        check("super-admin session login succeeded (independently)", bool(sa_tokens.get("access_token")))

        biz_claims = decode_jwt(biz_tokens["access_token"])
        sa_claims = decode_jwt(sa_tokens["access_token"])
        check("business token subject != super-admin token subject (no bleed)",
              biz_claims["sub"] != sa_claims["sub"], (biz_claims["sub"], sa_claims["sub"]))
        check("business token aud is autom-app", biz_claims.get("azp") == "autom-app", biz_claims.get("azp"))
        check("super-admin token aud is autom-superadmin", sa_claims.get("azp") == "autom-superadmin", sa_claims.get("azp"))

        s1, orgs = call_api(f"{api_url}/api/organizations", biz_tokens["access_token"])
        check("business token still works against the business API after both logins", s1 == 200, (s1, orgs))
        s2, sa_orgs = call_api(f"{api_url}/api/super-admin/orgs", sa_tokens["access_token"])
        check("super-admin token still works against the super-admin API after both logins", s2 == 200, (s2, sa_orgs))
    finally:
        delete_user_if_exists(admin_token, biz_email)
        delete_user_if_exists(admin_token, sa_email)


# ── Part 2e: a token active in project P cannot read a DIFFERENT project's data
#    in the same org, even with real permissions on P (cross-project IDOR) ──
def test_cross_project_access_blocked(api_url):
    print("\n" + "=" * 60)
    print("PART 2e: a project-scoped token cannot reach a DIFFERENT project's data (IDOR)")
    print("=" * 60)
    flow, token = tps.login(*tps.PROJECT_ADMIN_USER, "test-3", "p5")
    s0, body0 = call_api(f"{api_url}/api/projects/{tps.PROJECT_P5_ID}/dashboard/summary?environment=dev", token["access_token"])
    check("own active project (p5, has reports:read) dashboard loads", s0 == 200, (s0, body0))

    s1, body1 = call_api(f"{api_url}/api/projects/{tps.PROJECT_P3_ID}/dashboard/summary?environment=dev", token["access_token"])
    check("a DIFFERENT project (p3, same org, not a member) is rejected, not served",
          s1 == 403, (s1, body1))


# ── Part 2d: switching INTO an MFA-mandatory org without MFA set up is blocked ──
def set_mfa_mandatory(admin_token, alias, mandatory):
    org = find_native_org(admin_token, alias)
    org["attributes"] = org.get("attributes", {})
    org["attributes"]["mfaMandatory"] = ["true" if mandatory else "false"]
    code, _, _ = admin_request("PUT", f"/admin/realms/autom-realm/organizations/{org['id']}", admin_token, org)
    if code not in (200, 204):
        raise RuntimeError(f"failed to set mfaMandatory={mandatory} on {alias}: {code}")


def test_mfa_required_blocks_switch(admin_token):
    print("\n" + "=" * 60)
    print("PART 2d: switching into an MFA-mandatory org without MFA set up is blocked")
    print("=" * 60)
    # A dedicated org, isolated from test-muztaba-2 (used by Part 2b, whose
    # fixture never sets up MFA -- leaving mfaMandatory on there would break
    # that test on a later run).
    mandatory_alias = "test-muztaba-3"
    email, password = "verify-mfa-switch@example.com", "MfaSwitch#2026"
    set_mfa_mandatory(admin_token, mandatory_alias, True)
    try:
        create_throwaway_user(admin_token, email, password, [
            ("test-3", "Test_3", "p3"),
            (mandatory_alias, "Test_Muztaba_3", "p_test"),
        ])
        try:
            flow = Flow(tps.KC_URL, tps.REALM, "autom-app", tps.REDIRECT_URI)
            tokens = flow.login(email, password, "test-3", "p3")
            claims = decode_jwt(tokens["access_token"])
            check("initial login into the non-mandatory org succeeds without an MFA prompt",
                  claims.get("organization_alias") == "test-3", claims.get("organization_alias"))

            org2 = find_native_org(admin_token, mandatory_alias)
            p_group = find_group_id(admin_token, "p_test", parent_id=find_group_id(admin_token, "Test_Muztaba_3"))
            status, body = flow.switch_project(tokens["access_token"], org2["id"], p_group)
            check("switch into the MFA-mandatory org is rejected (403)", status == 403, (status, body))
            check("rejection reason is mfa_required", body and "mfa_required" in body, body)

            token2 = flow.refresh(tokens["refresh_token"])
            after = decode_jwt(token2["access_token"])
            check("active org unchanged after the blocked switch",
                  after.get("organization_alias") == "test-3", after.get("organization_alias"))
        finally:
            delete_user_if_exists(admin_token, email)
    finally:
        set_mfa_mandatory(admin_token, mandatory_alias, False)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--api-url", default="http://localhost:5000")
    args = p.parse_args()

    admin_token = tps.login_superadmin(tps.SUPERADMIN_USERNAME, tps.SUPERADMIN_PASSWORD)["access_token"]
    kc_admin_token = get_admin_token()

    run_existing_reusable_scenarios(admin_token)
    test_multi_project_picker_shows_both(kc_admin_token)
    test_multi_org_picker_and_switch(kc_admin_token)
    test_two_simultaneous_portal_sessions(kc_admin_token, args.api_url)
    test_cross_project_access_blocked(args.api_url)
    test_mfa_required_blocks_switch(kc_admin_token)

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
