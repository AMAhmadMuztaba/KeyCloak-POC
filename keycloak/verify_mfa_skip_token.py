#!/usr/bin/env python3
"""
Exchanges the real authorization code obtained by the live browser walkthrough
of the autom-optional-totp Skip flow for tokens, to prove the login genuinely
completed (not just that the browser redirected). Also confirms via the admin
API that the user has no OTP credential registered (proving Skip, not a
silent auto-configure).
"""
import base64
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

from test_permission_scenarios import login_superadmin

KC_URL = "https://keycloak.inb.seliselocal.com"
KC_ADMIN_URL = "http://172.16.2.42:8080"
REALM = "autom-realm"
CLIENT_ID = "autom-app"
REDIRECT_URI = "https://automation.inb.seliselocal.com:5173/"
CODE_VERIFIER = "zIR31dsazxCe_8SIFUIt4aEeAeajhMG8DIbM9fsjpUY"

AUTH_CODE = sys.argv[1]
USER_ID = "02782547-d9e1-4f9f-bb4a-7e437931be08"


def decode_jwt(access_token: str) -> dict:
    payload = access_token.split(".")[1]
    padded = payload + "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(padded))


def kc_admin_request(method, path, token):
    req = urllib.request.Request(f"{KC_ADMIN_URL}{path}", method=method)
    req.add_header("Authorization", f"Bearer {token}")
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        raw = resp.read()
        return resp.getcode(), (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")


def main():
    token_req = urllib.request.Request(
        f"{KC_URL}/realms/{REALM}/protocol/openid-connect/token",
        data=urllib.parse.urlencode({
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "code": AUTH_CODE,
            "code_verifier": CODE_VERIFIER,
        }).encode(),
        method="POST",
    )
    token_req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        token_json = json.loads(urllib.request.urlopen(token_req).read().decode())
    except urllib.error.HTTPError as e:
        print("TOKEN EXCHANGE FAILED:", e.code, e.read().decode(errors="replace"))
        sys.exit(1)

    print("[PASS] Token exchange succeeded — the real browser flow issued a valid access token.")
    claims = decode_jwt(token_json["access_token"])
    print(f"  sub: {claims.get('sub')}")
    print(f"  preferred_username / email: {claims.get('preferred_username')} / {claims.get('email')}")
    print(f"  autom_organization_id: {claims.get('autom_organization_id')}")
    print(f"  project_id: {claims.get('project_id')}")

    admin_token = login_superadmin("alice", "VerifyTest#2026")["access_token"]
    code, user = kc_admin_request("GET", f"/admin/realms/{REALM}/users/{USER_ID}", admin_token)
    print(f"\n[INFO] Post-skip requiredActions: {user.get('requiredActions')}")
    ok = user.get("requiredActions") == []
    print(f"[{'PASS' if ok else 'FAIL'}] requiredActions cleared (autom-optional-totp consumed, not re-queued)")

    code, creds = kc_admin_request("GET", f"/admin/realms/{REALM}/users/{USER_ID}/credentials", admin_token)
    otp_creds = [c for c in creds if c.get("type") == "otp"]
    print(f"[{'PASS' if not otp_creds else 'FAIL'}] no OTP credential was registered (genuine skip, not silent auto-configure) — found: {otp_creds}")


if __name__ == "__main__":
    main()
