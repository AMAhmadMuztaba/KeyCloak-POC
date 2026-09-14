# Deploying the Autom Keycloak provider

The provider is a server extension, not a theme. Build its JAR, upload it to
the host directory mounted at `/opt/keycloak/providers`, then rebuild Keycloak
before switching the browser flow.

From this repository on the deployment machine:

```powershell
cd keycloak/providers/autom-post-password-org-selector
mvn.cmd clean package -DskipTests
scp target/autom-post-password-org-selector-1.0.0.jar inbserv@172.16.2.42:/home/inbserv/keycloak/providers/
scp -r ../../themes/autom inbserv@172.16.2.42:/home/inbserv/keycloak/themes/
```

The host compose/deploy configuration must mount both paths:

```yaml
volumes:
  - /home/inbserv/keycloak/themes:/opt/keycloak/themes:ro
  - /home/inbserv/keycloak/providers:/opt/keycloak/providers:ro
```

After the JAR is uploaded, run the Keycloak build from the service container
with the organization feature enabled, then restart the service. Only then run
the realm initializer to bind `autom-post-password-org-browser-v1` as the
business realm browser flow. Run `../../Initial script/autom-realm-init.py` from
the repository root. The initializer is intentionally fail-closed and
will not activate that flow if the provider is not present.
