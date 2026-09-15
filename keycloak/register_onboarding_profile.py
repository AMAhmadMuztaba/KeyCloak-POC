#!/usr/bin/env python3
"""
Registers the new custom required action (autom-onboarding-profile, provided
by AutomOnboardingProfile.java) on the realm's required-actions list.
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
PROVIDER_ID = "autom-onboarding-profile"


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

    code, existing = kc_admin_request("GET", f"/admin/realms/{REALM}/authentication/required-actions", token)
    if code != 200:
        print("FAILED to list required actions:", code, existing)
        sys.exit(1)
    aliases = [a["alias"] for a in existing]

    if PROVIDER_ID not in aliases:
        print(f"Registering unregistered provider {PROVIDER_ID} ...")
        code, resp = kc_admin_request(
            "POST", f"/admin/realms/{REALM}/authentication/register-required-action", token,
            {"providerId": PROVIDER_ID, "name": "Update Profile (Autom onboarding)"},
        )
        print("register-required-action:", code, resp)
        if code not in (200, 201, 204):
            print("FAILED to register. Aborting.")
            sys.exit(1)
    else:
        print(f"{PROVIDER_ID} already registered.")

    code, action = kc_admin_request("GET", f"/admin/realms/{REALM}/authentication/required-actions/{PROVIDER_ID}", token)
    if code != 200:
        print("FAILED to fetch action config. Aborting.")
        sys.exit(1)

    # Same priority as stock UPDATE_PROFILE (40) -- this REPLACES it in the
    # invite flow, not stacks alongside it, so ordering vs UPDATE_PASSWORD(57)/
    # VERIFY_EMAIL(50)/autom-optional-totp(58) is unchanged.
    action["enabled"] = True
    action["defaultAction"] = False
    action["priority"] = 40
    code, resp = kc_admin_request("PUT", f"/admin/realms/{REALM}/authentication/required-actions/{PROVIDER_ID}", token, action)
    print(f"Updated {PROVIDER_ID}: enabled=True, priority=40 ->", code)
    if code not in (200, 204):
        print("FAILED to update. Aborting.")
        sys.exit(1)

    code, final = kc_admin_request("GET", f"/admin/realms/{REALM}/authentication/required-actions/{PROVIDER_ID}", token)
    print("\nFinal config:", json.dumps(final, indent=2))


if __name__ == "__main__":
    main()
