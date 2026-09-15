#!/usr/bin/env python3
"""
End-to-end verification for the autom-realm org/project login + switch flow.

Drives the REAL browser-based login (credentials -> org picker -> project
picker -> authorization code -> token exchange) exactly as l3-react-autom-
business does, using only the Python standard library (no third-party HTTP
client needed against KC's own pages). Then calls the custom
PUT .../autom/switch-project endpoint to move to a different org/project,
refreshes the token, and reports which claims changed vs stayed the same
against what's expected:

  - autom_organization_id, project_id, active_role, organization_alias:
    expected to CHANGE on a switch (session-note-backed custom claims).
  - the native `organization` claim and `scope`: expected to STAY THE SAME
    (Keycloak can't silently re-scope a refresh token to a different org —
    this is a known, deliberate limitation, not a bug).

Optionally also re-checks the .NET backend (/api/organizations,
/api/me/permissions) before and after the switch, if --api-url is given.

Usage:
  python verify_login_flow.py \\
      --username you@example.com --password '<password>' \\
      --org test-3 --project p3 \\
      --switch-org test-4 --switch-project p4 \\
      --api-url http://localhost:5000

  # Local dev origin (default). For prod, e.g.:
  python verify_login_flow.py --redirect-uri https://automation-v2.inb.seliselocal.com/ ...
"""

import argparse
import base64
import hashlib
import http.cookiejar
import json
import re
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request

KC_DEFAULT = "https://keycloak.inb.seliselocal.com"
REALM_DEFAULT = "autom-realm"
CLIENT_ID_DEFAULT = "autom-app"
REDIRECT_URI_DEFAULT = "https://automation.inb.seliselocal.com:5173/"


class NoRedirect(urllib.request.HTTPErrorProcessor):
    def http_response(self, request, response):
        return response

    https_response = http_response


class Flow:
    def __init__(self, kc_url, realm, client_id, redirect_uri):
        self.kc_url = kc_url.rstrip("/")
        self.realm = realm
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cj), NoRedirect()
        )
        verifier_bytes = secrets.token_bytes(32)
        self.code_verifier = self._b64url(verifier_bytes)
        self.code_challenge = self._b64url(hashlib.sha256(self.code_verifier.encode()).digest())

    @staticmethod
    def _b64url(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    @staticmethod
    def _form_action(html: str):
        m = re.search(r'<form[^>]+action="([^"]+)"', html)
        return m.group(1).replace("&amp;", "&") if m else None

    def _request(self, method, url, data=None):
        body = urllib.parse.urlencode(data).encode() if data is not None else None
        req = urllib.request.Request(url, data=body, method=method)
        if body is not None:
            req.add_header("Content-Type", "application/x-www-form-urlencoded")
        resp = self.opener.open(req)
        return resp.getcode(), resp.headers.get("Location"), resp.read().decode(errors="replace")

    def login(self, username, password, org_alias, project_id_or_name, project_lookup=None):
        """Full interactive login: credentials -> org picker -> project picker -> token."""
        auth_params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "response_mode": "fragment",
            "scope": "openid profile email organization",
            "code_challenge": self.code_challenge,
            "code_challenge_method": "S256",
            "state": secrets.token_urlsafe(8),
            "nonce": secrets.token_urlsafe(8),
        }
        auth_url = f"{self.kc_url}/realms/{self.realm}/protocol/openid-connect/auth?" + urllib.parse.urlencode(auth_params)
        _, _, html = self._request("GET", auth_url)
        action = self._form_action(html)
        if not action:
            raise RuntimeError(f"No login form found. Response snippet: {html[:500]}")

        code, loc, html = self._request("POST", action, {"username": username, "password": password, "credentialId": ""})
        if "Invalid username or password" in html:
            raise RuntimeError("Invalid username or password")
        if code in (302, 303):
            code, loc, html = self._request("GET", loc)
        action = self._form_action(html)
        if action is None:
            raise RuntimeError(f"Login did not advance to next step. Snippet: {html[:800]}")

        # Org picker step (skipped by KC if the user has exactly one org).
        if 'name="organization"' in html:
            code, loc, html = self._request("POST", action, {"organization": org_alias})
            if code in (302, 303):
                code, loc, html = self._request("GET", loc)
            action = self._form_action(html)
            if action is None:
                raise RuntimeError(f"Org picker did not advance. Snippet: {html[:800]}")

        # Project picker step.
        if 'name="project"' in html:
            project_value = project_id_or_name
            if project_lookup and project_id_or_name in project_lookup:
                project_value = project_lookup[project_id_or_name]
            elif project_id_or_name not in re.findall(r'name="project" value="([^"]+)"', html):
                # Caller passed a NAME, not an id — resolve it from the picker HTML.
                for m in re.finditer(r'value="([^"]+)">\s*<span[^>]*>.*?<strong>([^<]+)</strong>', html, re.S):
                    if m.group(2).strip().lower() == project_id_or_name.lower():
                        project_value = m.group(1)
                        break
            code, loc, html = self._request("POST", action, {"project": project_value})
        else:
            raise RuntimeError(f"No project picker shown. Snippet: {html[:800]}")

        # Follow redirects to our redirect_uri with the auth code in the fragment.
        final_loc = loc
        hops = 0
        while final_loc and "code=" not in final_loc and hops < 5:
            _, final_loc, _ = self._request("GET", final_loc)
            hops += 1
        if not final_loc or "code=" not in final_loc:
            raise RuntimeError(f"Never reached redirect_uri with a code. Last location: {loc}")

        frag = final_loc.split("#", 1)[1] if "#" in final_loc else final_loc.split("?", 1)[1]
        params = dict(urllib.parse.parse_qsl(frag))
        auth_code = params.get("code")
        if not auth_code:
            raise RuntimeError(f"No code in final redirect: {final_loc}")

        token_data = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "code": auth_code,
            "code_verifier": self.code_verifier,
        }
        token_req = urllib.request.Request(
            f"{self.kc_url}/realms/{self.realm}/protocol/openid-connect/token",
            data=urllib.parse.urlencode(token_data).encode(),
            method="POST",
        )
        token_req.add_header("Content-Type", "application/x-www-form-urlencoded")
        token_json = json.loads(urllib.request.urlopen(token_req).read().decode())
        return token_json

    def refresh(self, refresh_token):
        token_req = urllib.request.Request(
            f"{self.kc_url}/realms/{self.realm}/protocol/openid-connect/token",
            data=urllib.parse.urlencode({
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "refresh_token": refresh_token,
            }).encode(),
            method="POST",
        )
        token_req.add_header("Content-Type", "application/x-www-form-urlencoded")
        return json.loads(urllib.request.urlopen(token_req).read().decode())

    def switch_project(self, access_token, organization_id, project_id, origin=None):
        req = urllib.request.Request(
            f"{self.kc_url}/realms/{self.realm}/autom/switch-project",
            data=json.dumps({"organizationId": organization_id, "projectId": project_id}).encode(),
            method="PUT",
        )
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {access_token}")
        if origin:
            req.add_header("Origin", origin)
        try:
            resp = urllib.request.urlopen(req)
            return resp.getcode(), resp.read().decode(errors="replace")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode(errors="replace")

    def get_projects(self, access_token, kc_org_id, origin=None):
        req = urllib.request.Request(
            f"{self.kc_url}/realms/{self.realm}/autom/projects?organizationId={urllib.parse.quote(kc_org_id)}"
        )
        req.add_header("Authorization", f"Bearer {access_token}")
        if origin:
            req.add_header("Origin", origin)
        resp = urllib.request.urlopen(req)
        return json.loads(resp.read().decode())


def decode_jwt(access_token: str) -> dict:
    payload = access_token.split(".")[1]
    padded = payload + "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(padded))


def call_api(url, access_token, origin=None):
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {access_token}")
    if origin:
        req.add_header("Origin", origin)
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        return resp.getcode(), json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")
    except Exception as e:  # noqa: BLE001 - report, don't crash the whole run
        return None, str(e)


def report_diff(before: dict, after: dict, expected_changed: list, expected_same: list):
    print("\n--- Claim diff ---")
    ok = True
    for key in expected_changed:
        b, a = before.get(key), after.get(key)
        changed = b != a
        status = "OK  (changed)" if changed else "FAIL (did not change)"
        if not changed:
            ok = False
        print(f"  [{status}] {key}: {b!r} -> {a!r}")
    for key in expected_same:
        b, a = before.get(key), after.get(key)
        same = b == a
        status = "OK  (unchanged, as expected)" if same else "FAIL (changed unexpectedly)"
        if not same:
            ok = False
        print(f"  [{status}] {key}: {b!r} -> {a!r}")
    return ok


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--username", required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--org", required=True, help="Org alias to log into initially, e.g. test-3")
    p.add_argument("--project", required=True, help="Project name (e.g. p3) or KC group id to select initially")
    p.add_argument("--switch-org-id", help="KC Organization id to switch to (skip switch step if omitted)")
    p.add_argument("--switch-project-id", help="KC project group id to switch to")
    p.add_argument("--api-url", help="Base URL of the .NET Autom.Api, e.g. http://localhost:5000")
    p.add_argument("--kc-url", default=KC_DEFAULT)
    p.add_argument("--realm", default=REALM_DEFAULT)
    p.add_argument("--client-id", default=CLIENT_ID_DEFAULT)
    p.add_argument("--redirect-uri", default=REDIRECT_URI_DEFAULT)
    args = p.parse_args()

    origin = args.redirect_uri.rstrip("/").rsplit("/", 1)[0] if "//" in args.redirect_uri else None
    # Origin header = scheme+host+port only, no path.
    m = re.match(r"(https?://[^/]+)", args.redirect_uri)
    origin = m.group(1) if m else None

    flow = Flow(args.kc_url, args.realm, args.client_id, args.redirect_uri)

    print(f"1) Logging in as {args.username}, org={args.org}, project={args.project} ...")
    token = flow.login(args.username, args.password, args.org, args.project)
    claims_before = decode_jwt(token["access_token"])
    print("   OK. Initial claims:")
    for k in ["autom_organization_id", "project_id", "active_role", "organization", "organization_alias", "scope", "groups"]:
        print(f"     {k}: {claims_before.get(k)!r}")

    api_before = None
    if args.api_url:
        print("\n1a) Checking .NET backend with initial token ...")
        s1, orgs = call_api(f"{args.api_url}/api/organizations", token["access_token"], origin)
        s2, perms = call_api(f"{args.api_url}/api/me/permissions", token["access_token"], origin)
        print(f"    GET /api/organizations -> {s1}: {orgs}")
        print(f"    GET /api/me/permissions -> {s2}: {perms}")
        api_before = (s1, orgs, s2, perms)

    if not args.switch_org_id or not args.switch_project_id:
        print("\nNo --switch-org-id/--switch-project-id given - stopping after initial login check.")
        return 0

    print(f"\n2) Switching to org={args.switch_org_id} project={args.switch_project_id} ...")
    status, body = flow.switch_project(token["access_token"], args.switch_org_id, args.switch_project_id, origin)
    print(f"   PUT /autom/switch-project -> {status} {body}")
    if status != 204:
        print("   FAIL: switch-project did not return 204")
        return 1

    print("\n3) Refreshing token to pick up new claims ...")
    token2 = flow.refresh(token["refresh_token"])
    claims_after = decode_jwt(token2["access_token"])
    print("   New claims:")
    for k in ["autom_organization_id", "project_id", "active_role", "organization", "organization_alias", "scope", "groups"]:
        print(f"     {k}: {claims_after.get(k)!r}")

    ok = report_diff(
        claims_before,
        claims_after,
        expected_changed=["autom_organization_id", "project_id", "organization_alias"],
        expected_same=["organization", "scope"],
    )
    # active_role is expected to change ONLY if the resolved role actually
    # differs between the two orgs/projects - report it without pass/fail.
    print(f"  [INFO] active_role: {claims_before.get('active_role')!r} -> {claims_after.get('active_role')!r}")

    if args.api_url:
        print("\n3a) Checking .NET backend with the SWITCHED token ...")
        s1, orgs = call_api(f"{args.api_url}/api/organizations", token2["access_token"], origin)
        s2, perms = call_api(f"{args.api_url}/api/me/permissions", token2["access_token"], origin)
        print(f"    GET /api/organizations -> {s1}: {orgs}")
        print(f"    GET /api/me/permissions -> {s2}: {perms}")

    print(f"\n=== {'ALL CHECKS PASSED' if ok else 'SOME CHECKS FAILED'} ===")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
