#!/usr/bin/env python3
"""
Adds the new autom-mfa-enforcement authenticator as a 4th provider inside the
existing CONDITIONAL post-auth subflow (autom-post-auth-selectors), positioned
after autom-post-org-project-selector (new executions append at the end) --
matching the requirement "after selecting org and project". Idempotent: skips
if the provider is already present.

Does NOT touch the rest of the realm (unlike re-running the whole init.py,
which would also re-provision demo users/IdPs/WebAuthn — far bigger blast
radius than needed for this one addition to an already-live flow).
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

from test_permission_scenarios import login_superadmin

KC_URL = "http://172.16.2.42:8080"
REALM = "autom-realm"
# Set KC_SUPERADMIN_USERNAME/KC_SUPERADMIN_PASSWORD before running.
SUPERADMIN_USERNAME = os.environ.get("KC_SUPERADMIN_USERNAME", "alice")
SUPERADMIN_PASSWORD = os.environ["KC_SUPERADMIN_PASSWORD"]

AUTOM_FLOW_ALIAS = "autom-post-password-org-browser-v1"
POST_AUTH_SUBFLOW_ALIAS = "autom-post-auth-selectors"
NEW_PROVIDER_ID = "autom-mfa-enforcement"


def req(method, url, token, body=None):
    r = urllib.request.Request(
        url, method=method,
        data=json.dumps(body).encode() if body is not None else None,
    )
    r.add_header("Authorization", f"Bearer {token}")
    if body is not None:
        r.add_header("Content-Type", "application/json")
    try:
        resp = urllib.request.urlopen(r, timeout=15)
        raw = resp.read()
        return resp.getcode(), (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")


def main():
    token = login_superadmin(SUPERADMIN_USERNAME, SUPERADMIN_PASSWORD)["access_token"]

    encoded_flow = urllib.parse.quote(AUTOM_FLOW_ALIAS, safe="")
    execs_url = f"{KC_URL}/admin/realms/{REALM}/authentication/flows/{encoded_flow}/executions"

    code, execs = req("GET", execs_url, token)
    if code != 200:
        print("FAILED to list executions:", code, execs)
        sys.exit(1)

    existing = next((e for e in execs if e.get("providerId") == NEW_PROVIDER_ID), None)
    if existing:
        print(f"{NEW_PROVIDER_ID} already present (requirement={existing.get('requirement')}) — nothing to do.")
        if existing.get("requirement") != "REQUIRED":
            existing["requirement"] = "REQUIRED"
            code, resp = req("PUT", execs_url, token, existing)
            print(f"Set {NEW_PROVIDER_ID} -> REQUIRED:", code)
        return

    subflow_encoded = urllib.parse.quote(POST_AUTH_SUBFLOW_ALIAS, safe="")
    code, resp = req(
        "POST",
        f"{KC_URL}/admin/realms/{REALM}/authentication/flows/{subflow_encoded}/executions/execution",
        token,
        {"provider": NEW_PROVIDER_ID},
    )
    print(f"Add {NEW_PROVIDER_ID} to '{POST_AUTH_SUBFLOW_ALIAS}':", code, resp)
    if code not in (200, 201):
        print("FAILED to add execution. Aborting.")
        sys.exit(1)

    code, execs = req("GET", execs_url, token)
    if code != 200:
        print("FAILED to re-list executions:", code, execs)
        sys.exit(1)
    new_exec = next((e for e in execs if e.get("providerId") == NEW_PROVIDER_ID), None)
    if not new_exec:
        print(f"FAILED: {NEW_PROVIDER_ID} not found in executions after adding it.")
        sys.exit(1)

    print(f"New execution level={new_exec.get('level')} index={new_exec.get('index')} requirement={new_exec.get('requirement')}")
    new_exec["requirement"] = "REQUIRED"
    code, resp = req("PUT", execs_url, token, new_exec)
    print(f"Set {NEW_PROVIDER_ID} -> REQUIRED:", code)
    if code not in (200, 204):
        print("FAILED to set requirement. Aborting.")
        sys.exit(1)

    code, execs = req("GET", execs_url, token)
    print("\nFinal executions in flow:")
    for e in execs:
        print(f"  level={e.get('level')} index={e.get('index')} provider={e.get('providerId')} flow={e.get('displayName') if e.get('authenticationFlow') else None} requirement={e.get('requirement')}")


if __name__ == "__main__":
    main()
