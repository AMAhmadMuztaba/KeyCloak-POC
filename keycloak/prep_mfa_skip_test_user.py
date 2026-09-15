#!/usr/bin/env python3
"""
Administratively puts the MFA-skip test user into the exact state a real
click-through of the invite email would leave EXCEPT it leaves
autom-optional-totp queued (instead of clearing everything), so a real
browser login lands directly on the MFA page to test the Skip button live.
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

EMAIL = sys.argv[1]
PASSWORD = sys.argv[2] if len(sys.argv) > 2 else "MfaSkipTest#2026"


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


def main():
    token = login_superadmin(SUPERADMIN_USERNAME, SUPERADMIN_PASSWORD)["access_token"]

    code, users = kc_admin_request("GET", f"/admin/realms/{REALM}/users?username={EMAIL}&exact=true", token)
    if code != 200 or not users:
        print("User not found:", code, users)
        sys.exit(1)
    user_id = users[0]["id"]

    code, resp = kc_admin_request("PUT", f"/admin/realms/{REALM}/users/{user_id}/reset-password", token,
                                   {"type": "password", "value": PASSWORD, "temporary": False})
    print("reset-password ->", code, resp)

    code, resp = kc_admin_request("PUT", f"/admin/realms/{REALM}/users/{user_id}", token,
                                   {"requiredActions": ["autom-optional-totp"], "emailVerified": True})
    print("set requiredActions=[autom-optional-totp], emailVerified=true ->", code, resp)

    code, user = kc_admin_request("GET", f"/admin/realms/{REALM}/users/{user_id}", token)
    print("\nFinal user state:")
    print("  requiredActions:", user.get("requiredActions"))
    print("  emailVerified:", user.get("emailVerified"))
    print(f"\nUser id: {user_id}")
    print(f"Password: {PASSWORD}")


if __name__ == "__main__":
    main()
